"""Analyst engine: infer a missing line of accounting and score three options.

The question it answers: for a transaction (or a whole reporting period) whose
line of accounting is not recorded, which Treasury account, object class and
program activity most likely funded it, and how sure can we be?

Method, in order:
  1. Candidates are only the accounts the award itself lists, plus any File C
     row for the award. Nothing else can be an answer.
  2. Hard exclusions: an account not yet available, or cancelled, on the
     action date cannot fund it (31 U.S.C. 1552).
  3. Evidence features per candidate, from the transaction itself, from File C
     for the same period, from linear-programming bounds on how the period's
     transactions can split across File C rows, and from every other period of
     the same award (cross-transaction inference).
  4. A conditional-logit score with one weight per feature, plus an explicit
     "none of these" option. Weights start at stated expert priors and are
     refit from confirmed outcomes (see learn.py), shrunk toward the priors.

Output is always a LEAD: three options with a confidence, the evidence that
moved each one, and a collection requirement naming who can confirm it. It is
never a figure and never enters the claim ledger (D16).
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from core.analyst import loa

ENGINE_VERSION = "analyst/0.1"

# Expert priors. Units are log-odds per unit of feature. Every number here is
# a judgement, stated so it can be refit and audited.
PRIOR_WEIGHTS: dict[str, float] = {
    "fc_present": 1.5,      # account has a same-sign File C row in the tx's period
    "fc_absent": -2.5,      # period is covered by File C, account not in it
    "fc_exact": 3.0,        # a File C row equals the tx amount to the cent
    "fc_capacity": 1.0,     # log(min(1, |row| / |tx|)); a small row cannot be primary
    "lp_forced": 5.0,       # LP proves >= 50% of the tx must come from this account
    "lp_impossible": -8.0,  # LP proves this account funds none of the tx
    "text_match": 1.2,      # description names this account's colour (LR ~3.3)
    "text_other": -1.2,     # description names only other colours
    "history": 1.0,         # log of the account's time-decayed share in other periods
    "recency": 0.7,         # newest current account of its main account
    "expired_pos": -1.5,    # new money on an expired account
    "expired_neg": -0.3,    # downward adjustment on an expired account
    "none_bias": -3.0,      # score of "none of these"
}

CONFIRMERS = {
    "tx": (
        "SUPSHIP Newport News or NAVSEA 02 (contracting officer)",
        "PIEE EDA: the conformed modification, Section G accounting data (ACRN to LOA)",
    ),
    "ledger": (
        "DFAS Columbus or NAVSEA 01 (comptroller)",
        "Navy ERP obligation postings for the document number, by TAS and period",
    ),
}


@dataclass(frozen=True)
class Tx:
    key: str
    piid: str
    date: str
    mod: str
    amount: int  # cents
    action_type: str = ""
    desc: str = ""
    award_tas: tuple[str, ...] = ()
    award_oc: tuple[str, ...] = ()
    award_pa: tuple[str, ...] = ()


@dataclass(frozen=True)
class FCRow:
    period: str
    piid: str
    tas: str
    oc: str
    pa: str
    amount: int  # cents
    locator: str = ""


@dataclass
class Corpus:
    tx: list[Tx]
    fc: list[FCRow]
    hidden: frozenset = field(default_factory=frozenset)

    def without_period(self, label: str) -> "Corpus":
        return Corpus(self.tx, [r for r in self.fc if r.period != label], self.hidden | {label})

    def periods(self, piid: str) -> list[str]:
        return sorted({r.period for r in self.fc if r.piid == piid})

    def period_of(self, t: Tx) -> str | None:
        for p in self.periods(t.piid):
            if loa.in_window(t.date, p):
                return p
        return None

    def rows(self, piid: str, label: str) -> list[FCRow]:
        return [r for r in self.fc if r.piid == piid and r.period == label]

    def tx_in(self, piid: str, label: str) -> list[Tx]:
        return [t for t in self.tx if t.piid == piid and loa.in_window(t.date, label)]

    def tied(self, piid: str, label: str) -> bool:
        rows = self.rows(piid, label)
        return bool(rows) and sum(r.amount for r in rows) == sum(t.amount for t in self.tx_in(piid, label))

    def get(self, key: str) -> Tx:
        for t in self.tx:
            if t.key == key or f"{t.piid}:{t.mod}" == key:
                return t
        raise KeyError(f"no transaction {key!r}")


# ---------------------------------------------------------------- LP bounds

def allocation_bounds(txs: list[Tx], rows: list[FCRow]) -> dict | None:
    """Min and max cents of each tx that can come from each account.

    Constraints: each tx splits across accounts and its parts sum to it; each
    account's parts sum to its File C total; every part has the tx's sign
    (a deobligation does not fund anything). Returns {(tx.key, tas): (lo, hi)}
    or None when scipy is missing or the system is infeasible.
    """
    try:
        import numpy as np
        from scipy.optimize import linprog
    except ImportError:
        return None
    txs = [t for t in txs if t.amount != 0]
    acct: dict[str, int] = {}
    for r in rows:
        acct[r.tas] = acct.get(r.tas, 0) + r.amount
    names = sorted(acct)
    n, m = len(txs), len(names)
    if not n or not m:
        return None
    N = n * m
    a_eq, b_eq = [], []
    for i, t in enumerate(txs):
        v = np.zeros(N); v[i * m:(i + 1) * m] = 1; a_eq.append(v); b_eq.append(t.amount)
    for j, s in enumerate(names):
        v = np.zeros(N); v[j::m] = 1; a_eq.append(v); b_eq.append(acct[s])
    bounds = [((0, None) if t.amount > 0 else (None, 0)) for t in txs for _ in names]
    base = linprog(np.zeros(N), A_eq=a_eq, b_eq=b_eq, bounds=bounds, method="highs")
    if base.status != 0:
        return None
    out = {}
    for i, t in enumerate(txs):
        for j, s in enumerate(names):
            c = np.zeros(N); c[i * m + j] = 1
            lo = linprog(c, A_eq=a_eq, b_eq=b_eq, bounds=bounds, method="highs").fun
            hi = -linprog(-c, A_eq=a_eq, b_eq=b_eq, bounds=bounds, method="highs").fun
            out[(t.key, s)] = (round(lo), round(hi))
    return out


def guaranteed(lo: int, hi: int, amount: int) -> int:
    """Cents of the tx that MUST come from the account, as a magnitude.

    For new money the guaranteed part is the lower bound. For a deobligation
    the parts are <= 0, so the guaranteed part is the bound nearest zero.
    """
    return max(0, lo) if amount > 0 else max(0, -hi)


_LP_CACHE: dict = {}


def _bounds(corpus: Corpus, piid: str, label: str):
    k = (piid, label, corpus.hidden, len(corpus.fc), len(corpus.tx))
    if k not in _LP_CACHE:
        _LP_CACHE[k] = (
            allocation_bounds(corpus.tx_in(piid, label), corpus.rows(piid, label))
            if corpus.tied(piid, label) else None
        )
    return _LP_CACHE[k]


# ---------------------------------------------------------------- features

def _months(a: str, b: str) -> int:
    fa, pa = a if isinstance(a, tuple) else loa.fiscal(a)
    fb, pb = b if isinstance(b, tuple) else loa.fiscal(b)
    return abs((fa * 12 + pa) - (fb * 12 + pb))


def history_share(corpus: Corpus, t: Tx, cands: list[str], skip: str | None) -> dict[str, float]:
    """Time-decayed share of each candidate in the award's other File C rows.

    Half-life 12 months. Smoothed so an account never seen gets a small, equal
    share instead of zero (log(0) would veto it on history alone).
    """
    tf = loa.fiscal(t.date)
    w = {c: 0.0 for c in cands}
    for r in corpus.fc:
        if r.piid != t.piid or r.period == skip or r.tas not in w:
            continue
        if (r.amount > 0) != (t.amount > 0):
            continue
        fy, _, hi = loa.period_window(r.period)
        w[r.tas] += abs(r.amount) * 0.5 ** (_months(tf, (fy, hi)) / 12)
    tot, k, alpha = sum(w.values()), len(cands), 0.25
    if tot == 0:
        return {c: 1.0 / k for c in cands}
    return {c: (1 - alpha) * w[c] / tot + alpha / k for c in cands}


def _colours_in(desc: str) -> set[str]:
    d = (desc or "").upper()
    return {col for col, pats in loa.COLOUR_CUES.items() if any(re.search(p, d) for p in pats)}


def candidates(corpus: Corpus, t: Tx) -> tuple[list[str], list[dict]]:
    pool = set(t.award_tas) | {r.tas for r in corpus.fc if r.piid == t.piid}
    fy, _ = loa.fiscal(t.date)
    keep, excluded = [], []
    for s in sorted(pool):
        p = loa.parse_tas(s)
        if p is None:
            excluded.append({"tas": s, "reason": "unparseable TAS"}); continue
        st = p.status_in(fy)
        if st in ("unavailable", "cancelled"):
            excluded.append({"tas": s, "reason": f"{st} in FY{fy} (availability {p.bpoa}/{p.epoa})"}); continue
        keep.append(s)
    return keep, excluded


def features(corpus: Corpus, t: Tx, cands: list[str]) -> dict[str, dict[str, float]]:
    fy, _ = loa.fiscal(t.date)
    label = corpus.period_of(t)
    rows = corpus.rows(t.piid, label) if label else []
    by_tas: dict[str, int] = {}
    for r in rows:
        by_tas[r.tas] = by_tas.get(r.tas, 0) + r.amount
    lp = _bounds(corpus, t.piid, label) if label else None
    hist = history_share(corpus, t, cands, label)
    cols = _colours_in(t.desc)
    newest: dict[str, int] = {}
    for s in cands:
        p = loa.parse_tas(s)
        if p.status_in(fy) == "current" and p.bpoa is not None:
            newest[p.main] = max(newest.get(p.main, 0), p.bpoa)
    out = {}
    for s in cands:
        p = loa.parse_tas(s)
        f: dict[str, float] = {}
        if label:
            amt = by_tas.get(s)
            same = amt is not None and amt != 0 and (amt > 0) == (t.amount > 0)
            if same:
                f["fc_present"] = 1.0
                if t.amount:
                    f["fc_capacity"] = math.log(min(1.0, abs(amt) / abs(t.amount)))
            elif amt is None:
                f["fc_absent"] = 1.0
            if any(r.tas == s and r.amount == t.amount and t.amount for r in rows):
                f["fc_exact"] = 1.0
            if lp is not None and t.amount:
                lo, hi = lp.get((t.key, s), (0, 0))
                if guaranteed(lo, hi, t.amount) * 2 >= abs(t.amount):
                    f["lp_forced"] = 1.0
                if hi == 0 and lo == 0:
                    f["lp_impossible"] = 1.0
        if cols:
            if p.colour in cols:
                f["text_match"] = 1.0
            else:
                f["text_other"] = 1.0
        f["history"] = math.log(hist[s])
        if p.bpoa is not None and newest.get(p.main) == p.bpoa:
            f["recency"] = 1.0
        if p.status_in(fy) == "expired":
            f["expired_pos" if t.amount > 0 else "expired_neg"] = 1.0
        out[s] = f
    return out


# ---------------------------------------------------------------- scoring

def posterior(feats: dict[str, dict[str, float]], w: dict[str, float]) -> tuple[dict[str, float], float]:
    scores = {c: sum(w.get(k, 0.0) * v for k, v in f.items()) for c, f in feats.items()}
    none = w.get("none_bias", PRIOR_WEIGHTS["none_bias"])
    mx = max([none, *scores.values()])
    ex = {c: math.exp(s - mx) for c, s in scores.items()}
    en = math.exp(none - mx)
    z = sum(ex.values()) + en
    return {c: v / z for c, v in ex.items()}, en / z


def _attr_for(corpus: Corpus, t: Tx, tas: str, kind: str) -> dict:
    """Object class or program activity for an account, with its basis."""
    tally: dict[str, int] = {}
    for r in corpus.fc:
        if r.piid == t.piid and r.tas == tas:
            v = (r.oc if kind == "oc" else r.pa) or "(blank)"
            tally[v] = tally.get(v, 0) + abs(r.amount)
    if tally:
        tot = sum(tally.values()) or 1
        best = max(tally, key=tally.get)
        return {"value": best, "share": round(tally[best] / tot, 4), "basis": f"File C rows for {tas} on this award"}
    award = t.award_oc if kind == "oc" else t.award_pa
    if len(award) == 1:
        return {"value": loa.code_of(award[0]), "share": 1.0, "basis": "the award lists exactly one"}
    return {"value": None, "share": 0.0, "basis": f"award lists {len(award)}; no File C row for this account"}


def _cr(t: Tx, tas: str) -> dict:
    office, doc = CONFIRMERS["tx"]
    office2, doc2 = CONFIRMERS["ledger"]
    return {
        "instruction": f"Retrieve the accounting lines for {t.piid} modification {t.mod} ({t.date}) and confirm whether {tas} carries it.",
        "target_document": doc,
        "target_office": office,
        "cross_check": f"{doc2}, from {office2}",
        "period": t.date,
        "account": tas,
    }


def investigate_tx(corpus: Corpus, key: str, weights: dict[str, float] | None = None) -> dict:
    w = {**PRIOR_WEIGHTS, **(weights or {})}
    t = corpus.get(key)
    cands, excluded = candidates(corpus, t)
    feats = features(corpus, t, cands)
    post, none = posterior(feats, w)
    ranked = sorted(post, key=post.get, reverse=True)
    label = corpus.period_of(t)
    options = []
    for i, s in enumerate(ranked[:3], 1):
        p = loa.parse_tas(s)
        ev = sorted(
            ({"method": k, "value": round(v, 4), "weight": w.get(k, 0.0), "contribution": round(w.get(k, 0.0) * v, 3)}
             for k, v in feats[s].items()),
            key=lambda e: -abs(e["contribution"]),
        )
        options.append({
            "rank": i,
            "confidence": round(post[s], 4),
            "loa": {
                "tas": s, "appropriation": p.title, "colour": p.colour,
                "availability": f"{p.bpoa}/{p.epoa}", "status_on_action_date": p.status_in(loa.fiscal(t.date)[0]),
                "object_class": _attr_for(corpus, t, s, "oc"),
                "program_activity": _attr_for(corpus, t, s, "pa"),
            },
            "deductive": "lp_forced" in feats[s],
            "evidence": ev,
            "collection_requirement": _cr(t, s),
        })
    return {
        "engine": ENGINE_VERSION,
        "question": f"Which line of accounting primarily funds {t.piid} {t.mod} ({t.date}, {loa.dollars(t.amount)})?",
        "subject": {"piid": t.piid, "mod": t.mod, "date": t.date, "amount": loa.dollars(t.amount), "key": t.key},
        "grade": "LEAD",
        "options": options,
        "none_of_these": round(none, 4),
        "posterior_all": {s: round(post[s], 6) for s in ranked},
        "n_candidates": len(cands),
        "excluded": excluded,
        "context": {
            "file_c_period": label,
            "period_ties_to_cent": bool(label and corpus.tied(t.piid, label)),
            "hidden_periods": sorted(corpus.hidden),
        },
        "caveat": "A lead, not a figure. Confirm through the collection requirement before any use; the claim gate still applies.",
    }


def investigate_window(corpus: Corpus, piid: str, fy: int, lo: int, hi: int,
                       weights: dict[str, float] | None = None, label: str | None = None) -> dict:
    """Which accounts carry a window's obligations: the expected split.

    Each transaction's posterior is weighted by its absolute amount, so the
    answer is the amount-weighted vote of every line in the window.
    """
    w = {**PRIOR_WEIGHTS, **(weights or {})}
    txs = [t for t in corpus.tx if t.piid == piid and t.amount and loa.fiscal(t.date)[0] == fy and lo <= loa.fiscal(t.date)[1] <= hi]
    mass: dict[str, float] = {}
    none_mass, total = 0.0, 0
    for t in txs:
        cands, _ = candidates(corpus, t)
        post, none = posterior(features(corpus, t, cands), w)
        for c, p in post.items():
            mass[c] = mass.get(c, 0.0) + p * abs(t.amount)
        none_mass += none * abs(t.amount)
        total += abs(t.amount)
    total = total or 1
    ranked = sorted(mass, key=mass.get, reverse=True)
    return {
        "engine": ENGINE_VERSION,
        "question": f"Which accounts carry {piid} obligations in FY{fy} P{lo:02d}-P{hi:02d}{' (' + label + ')' if label else ''}?",
        "grade": "LEAD",
        "n_transactions": len(txs),
        "gross_amount": loa.dollars(sum(abs(t.amount) for t in txs)),
        "net_amount": loa.dollars(sum(t.amount for t in txs)),
        "options": [
            {"rank": i, "tas": s, "appropriation": loa.parse_tas(s).title, "expected_share": round(mass[s] / total, 4)}
            for i, s in enumerate(ranked[:3], 1)
        ],
        "none_of_these": round(none_mass / total, 4),
        # every candidate's share, so a truth outside the top 3 still has a
        # probability (the backtest's log loss and split error read this)
        "posterior_all": {s: round(mass[s] / total, 6) for s in ranked},
        "hidden_periods": sorted(corpus.hidden),
    }


def clear_cache() -> None:
    _LP_CACHE.clear()
