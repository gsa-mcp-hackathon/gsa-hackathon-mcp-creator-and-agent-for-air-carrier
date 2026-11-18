"""Explain a residual between File C and FPDS for one reporting period.

A large unexplained residual is a finding, not a remainder. This module never
labels one; it tests named causes and scores what survives:

  timing      transactions in months no File C submission covers, reported
              late in this one. Penalised when an earlier submission sat
              between those months and this one and did not carry them.
  unmirrored  the ledger posted obligations with no FPDS action in the window.
              Supported by the proven fact below.
  restatement an earlier obligation re-reported. Strong only with an
              exact-cent subset (k <= 3) and a low chance-match count.
  other       mass left for causes not modelled. Never zero.

Facts are kept apart from causes. "One File C account exceeds every
positive FPDS line in the window" is proven arithmetic, not a cause, so it
is reported as a fact and only feeds the scores. Causes are scored as
mutually exclusive primary explanations.

Scores are stated heuristics (residual/0.1), not fitted: there is no labelled
residual yet. Each record_outcome against this question becomes one.
"""
from __future__ import annotations

import math
from itertools import combinations

from core.analyst import engine, loa

VERSION = "residual/0.1"
PRIORS = {"timing": 0.0, "unmirrored": 0.5, "restatement": -0.5, "other": -0.5}


def _covered_months(corpus: engine.Corpus, piid: str) -> set[tuple[int, int]]:
    out = set()
    for p in corpus.periods(piid):
        fy, lo, hi = loa.period_window(p)
        out |= {(fy, m) for m in range(lo, hi + 1)}
    return out


def explain(corpus: engine.Corpus, piid: str, label: str, lookback_months: int = 12) -> dict:
    rows = corpus.rows(piid, label)
    txs = corpus.tx_in(piid, label)
    fc_sum = sum(r.amount for r in rows)
    tx_sum = sum(t.amount for t in txs)
    gap = fc_sum - tx_sum
    fy, lo, hi = loa.period_window(label)
    if gap == 0:
        return {"engine": VERSION, "question": f"Why does File C for {piid} {label} differ from FPDS?",
                "grade": "LEAD", "file_c": loa.dollars(fc_sum), "fpds_in_window": loa.dollars(tx_sum),
                "gap": loa.dollars(0), "facts": [{"fact": f"{label} ties to the cent.", "proof": "sum vs sum"}],
                "options": [], "none_of_these": 0.0}
    end = fy * 12 + hi
    covered = _covered_months(corpus, piid)
    hyps = []

    # timing: uncovered months before this window
    unc = [t for t in corpus.tx if t.piid == piid and loa.fiscal(t.date) not in covered
           and 0 < end - (loa.fiscal(t.date)[0] * 12 + loa.fiscal(t.date)[1]) <= lookback_months + (hi - lo)]
    unc_sum = sum(t.amount for t in unc)
    months = sorted({loa.fiscal(t.date) for t in unc})
    if unc and gap and (unc_sum > 0) == (gap > 0):
        # agreement in size, not just coverage: 467M cannot explain a 0.8M gap
        frac = min(abs(unc_sum), abs(gap)) / max(abs(unc_sum), abs(gap))
        last = max(months)
        between = [p for p in corpus.periods(piid) if p != label
                   and (loa.period_window(p)[0], loa.period_window(p)[1]) > last
                   and (loa.period_window(p)[0] * 12 + loa.period_window(p)[2]) < (fy * 12 + lo)]
        hyps.append({
            "cause": "timing",
            "statement": (f"{loa.dollars(unc_sum)} obligated in months no File C submission covers "
                          f"({', '.join(f'FY{a} P{b:02d}' for a, b in months)}) was reported in {label}."),
            "explains": loa.dollars(min(abs(unc_sum), abs(gap)) * (1 if gap > 0 else -1)),
            "fraction_explained": round(frac, 4),
            "exact_to_cent": unc_sum == gap,
            "score": PRIORS["timing"] + 2.0 * frac + (3.0 if unc_sum == gap else 0.0) - (1.5 if between else 0.0),
            "against": (f"Submission(s) {', '.join(between)} came after those months and before {label} "
                        f"and did not carry them.") if between else None,
            "test": "sum of FPDS federal_action_obligation over the uncovered months",
            "lines": [f"{t.mod} {t.date} {loa.dollars(t.amount)}" for t in sorted(unc, key=lambda t: -abs(t.amount))[:5]],
        })

    # subset: exact-cent, outside the window, k <= 3
    outside = [t for t in corpus.tx if t.piid == piid and t.amount and not loa.in_window(t.date, label)]
    big = sorted([t for t in outside if abs(t.amount) >= abs(gap) // 1000],
                 key=lambda t: -abs(t.amount))[:200] if gap else []
    targets = {"full gap": gap}
    if hyps and not hyps[0]["exact_to_cent"]:
        targets["gap after timing"] = gap - unc_sum
    for name, target in targets.items():
        found, tried = [], 0
        for k in (1, 2, 3):
            for combo in combinations(big, k):
                tried += 1
                if sum(t.amount for t in combo) == target:
                    found.append(combo)
        spread = max(1, sum(abs(t.amount) for t in big))
        expected_chance = tried / spread  # matches expected by luck at 1-cent resolution
        if found:
            hyps.append({
                "cause": "restatement",
                "statement": f"The {name} equals {len(found[0])} line(s) dated outside {label}, to the cent.",
                "explains": loa.dollars(target), "exact_to_cent": True,
                "expected_chance_matches": expected_chance,
                "score": PRIORS["restatement"] + (4.0 if expected_chance < 0.05 else 0.5),
                "lines": [f"{t.mod} {t.date} {loa.dollars(t.amount)}" for t in found[0]],
                "test": f"{tried:,} combinations of {len(big)} lines; {len(found)} exact",
            })
        else:
            hyps.append({"cause": "restatement", "rejected": True,
                         "statement": f"No exact-cent subset (k<=3) of {len(big)} out-of-window lines equals the {name} {loa.dollars(target)}.",
                         "test": f"{tried:,} combinations", "score": None})

    # ledger: one account exceeds every FPDS line in the window
    pos_tx = sum(t.amount for t in txs if t.amount > 0)
    acct: dict[str, int] = {}
    for r in rows:
        acct[r.tas] = acct.get(r.tas, 0) + r.amount
    top = max(acct, key=acct.get) if acct else None
    facts = []
    excess = 0
    if top:
        excess = acct[top] - pos_tx
        if excess > 0:
            facts.append({
                "fact": (f"File C records {loa.dollars(acct[top])} on {top} in {label}; every positive FPDS line "
                         f"in the window totals {loa.dollars(pos_tx)}. At least {loa.dollars(excess)} on that "
                         f"account has no FPDS action in the window."),
                "proof": "single File C account total minus the sum of positive FPDS lines in the window",
            })
    if not any(h["cause"] == "restatement" and not h.get("rejected") for h in hyps):
        hyps.append({"cause": "restatement", "statement": "Earlier obligations re-reported in this submission, not as an exact subset of FPDS lines.",
                     "score": PRIORS["restatement"]})
    if gap:
        share = max(0, excess) / abs(gap) if gap > 0 else 0.0
        hyps.append({
            "cause": "unmirrored",
            "statement": (
                f"The ledger posted obligations on {top} with no matching FPDS action in the window "
                f"(a funding action not reported to FPDS, or reported under another date or PIID)."
                if gap > 0 else
                "FPDS carries actions in the window that the ledger did not post in this period "
                "(posted earlier or later, or never obligated in accounting)."),
            "explains": loa.dollars(gap),
            "score": PRIORS["unmirrored"] + (1.0 if share >= 0.5 else 0.0),
            "test": "supported by the proven lower bound; confirm against Navy ERP postings by document number",
        })

    hyps.append({"cause": "other", "statement": "A cause not modelled here (restatement, a missing FPDS action, a File C error).",
                 "score": PRIORS["other"]})
    live = [h for h in hyps if h.get("score") is not None]
    mx = max(h["score"] for h in live)
    z = sum(math.exp(h["score"] - mx) for h in live)
    for h in live:
        h["confidence"] = round(math.exp(h["score"] - mx) / z, 4)
    ranked = sorted([h for h in live if h["cause"] != "other"], key=lambda h: -h["confidence"])
    other = next(h for h in live if h["cause"] == "other")
    return {
        "engine": VERSION,
        "question": f"Why does File C for {piid} {label} differ from FPDS?",
        "grade": "LEAD",
        "file_c": loa.dollars(fc_sum), "fpds_in_window": loa.dollars(tx_sum), "gap": loa.dollars(gap),
        "facts": facts,
        "options": [{"rank": i, **h} for i, h in enumerate(ranked[:3], 1)],
        "none_of_these": other["confidence"],
        "scoring": "stated heuristics, not fitted (no labelled residual yet)",
        "rejected": [h for h in hyps if h.get("rejected")],
        "collection_requirement": {
            "instruction": (f"Retrieve the File C (award financial) submission for {piid} for {label} and the period before it, "
                            f"and the Navy ERP obligation postings on {top} for the same months, by document number."),
            "target_system": "DATA Act Broker (File C) and Navy ERP",
            "target_office": "DFAS Columbus or NAVSEA 01 (comptroller)",
            "account": top, "period": label,
        },
    }
