"""Tool logic, independent of FastMCP and of the warehouse.

Every function takes an engine.Corpus (and, where relevant, weights and
recorded outcomes) and returns a JSON-safe dict, so it can be tested on a
synthetic corpus with no network. The analyst code itself is the vendored
core.analyst package; nothing here re-implements a scoring rule.

Every answer is grade LEAD (D16): it never enters the claim ledger.
"""
from __future__ import annotations

from core.analyst import backtest, engine, learn, loa, residual, sources

PIIDS: tuple[str, ...] = tuple(sources.TX_TABLES)

# Documents that can settle a lead. Anything else is not evidence enough to
# become a training label.
EVIDENCE_TYPES: dict[str, str] = {
    "section_g_accounting_data": "Conformed modification, Section G accounting data (ACRN to LOA), from PIEE EDA",
    "erp_obligation_posting": "Navy ERP obligation posting by document number, TAS and period",
    "file_c_submission": "DATA Act File C (award financial) submission as certified by the agency",
    "dfas_certified_report": "DFAS or comptroller certified report naming the account",
    "conformed_contract_or_modification": "Conformed contract or modification (PIEE EDA) naming the hull or scope",
    "budget_exhibit_line": "Budget exhibit line (P-5, P-40, P-8a) that carries the item for a named hull",
}
RESIDUAL_CAUSES = ("timing", "unmirrored", "restatement", "other")
NONE = "NONE_OF_THESE"
CAVEAT = ("Grade LEAD. A scored hypothesis, not a figure: do not quote it as a value, "
          "do not enter it in the claim ledger, confirm it through the collection requirement.")


class AnalystError(ValueError):
    """A caller error with a message safe to return to the client."""


def check_piid(piid: str) -> str:
    if piid not in PIIDS:
        raise AnalystError(f"Unknown PIID {piid!r}. Exact match only (09-C-2116 is not 16-C-2116). Known: {', '.join(PIIDS)}.")
    return piid


# ------------------------------------------------------------ questions

def open_questions(corpus: engine.Corpus, piid: str, limit: int = 10) -> dict:
    """What is still unknown for a contract, largest first, with the tool to work each."""
    check_piid(piid)
    periods = corpus.periods(piid)
    txs = [t for t in corpus.tx if t.piid == piid and t.amount]
    out: dict = {"piid": piid, "grade": "LEAD", "n_transactions": len(txs), "file_c_periods": periods}

    resid = []
    for p in periods:
        fc = sum(r.amount for r in corpus.rows(piid, p))
        tx = sum(t.amount for t in corpus.tx_in(piid, p))
        if fc != tx:
            resid.append({"period": p, "file_c": loa.dollars(fc), "fpds_in_window": loa.dollars(tx),
                          "gap": loa.dollars(fc - tx), "_abs": abs(fc - tx),
                          "next": {"tool": "analyst_explain_residual", "submission_period": p}})
    resid.sort(key=lambda r: -r["_abs"])
    for r in resid:
        del r["_abs"]
    out["residual_periods"] = resid[:limit]
    out["tied_periods"] = [p for p in periods if corpus.tied(piid, p)]

    if periods:
        covered = residual._covered_months(corpus, piid)
        first = loa.period_window(periods[0])
        last = loa.period_window(periods[-1])
        lo_m, hi_m = first[0] * 12 + first[1], last[0] * 12 + last[2]
        months: dict[tuple[int, int], list[int]] = {}
        for t in txs:
            f = loa.fiscal(t.date)
            if f not in covered and lo_m <= f[0] * 12 + f[1] <= hi_m:
                months.setdefault(f, []).append(t.amount)
        out["uncovered_months"] = [
            {"fiscal_year": fy, "period": p, "n": len(v), "net": loa.dollars(sum(v)),
             "next": {"tool": "analyst_investigate_window", "fiscal_year": fy, "first_period": p, "last_period": p}}
            for (fy, p), v in sorted(months.items())
        ]
    else:
        out["uncovered_months"] = []
        out["note"] = ("No File C (federal account funding) is loaded for this PIID, so no period can be "
                       "tied or deduced. Every transaction's line of accounting is open; the engine falls "
                       "back to the award's own account list, availability and description cues.")

    proven = {lb["key"] for lb in learn.deduced_labels(corpus, piid)}
    big = sorted((t for t in txs if t.key not in proven), key=lambda t: -abs(t.amount))[:limit]
    out["largest_unattributed_transactions"] = [
        {"modification_number": t.mod, "action_date": t.date, "amount": loa.dollars(t.amount),
         "transaction_key": t.key,
         "next": {"tool": "analyst_investigate_transaction", "transaction_key": t.key}}
        for t in big
    ]
    out["proven_by_arithmetic"] = len(proven)
    out["caveat"] = CAVEAT
    return out


def resolve_tx(corpus: engine.Corpus, piid: str, modification_number: str = "", transaction_key: str = "") -> engine.Tx:
    check_piid(piid)
    if transaction_key:
        hit = [t for t in corpus.tx if t.piid == piid and t.key == transaction_key]
    elif modification_number:
        hit = [t for t in corpus.tx if t.piid == piid and t.mod == modification_number.strip().upper()]
    else:
        raise AnalystError("Give a modification_number (for example P00067) or a transaction_key.")
    if not hit:
        raise AnalystError(f"No transaction for {piid} with that identifier. Use analyst_open_questions to list some.")
    if len(hit) > 1:
        lines = "; ".join(f"{t.key} ({t.date}, {loa.dollars(t.amount)})" for t in hit[:10])
        raise AnalystError(f"{len(hit)} transactions share modification {hit[0].mod}. Pass one transaction_key: {lines}")
    return hit[0]


def _trim(result: dict, keep: int = 10) -> dict:
    pa = result.get("posterior_all")
    if pa:
        result["posterior_all"] = dict(list(pa.items())[:keep])
    return result


def investigate_transaction(corpus: engine.Corpus, t: engine.Tx, weights: dict | None) -> dict:
    r = _trim(engine.investigate_tx(corpus, t.key, weights))
    r["kind"] = "tx"
    r["caveat"] = CAVEAT
    return r


def investigate_window(corpus: engine.Corpus, piid: str, fiscal_year: int, first_period: int,
                       last_period: int, weights: dict | None) -> dict:
    check_piid(piid)
    if not (1 <= first_period <= last_period <= 12):
        raise AnalystError("Periods run 1 (October) to 12 (September), first_period <= last_period.")
    r = engine.investigate_window(corpus, piid, fiscal_year, first_period, last_period, weights)
    if not r["n_transactions"]:
        raise AnalystError(f"No {piid} transactions in FY{fiscal_year} P{first_period:02d}-P{last_period:02d}.")
    r["kind"] = "window"
    r["caveat"] = CAVEAT
    return r


def explain_residual(corpus: engine.Corpus, piid: str, submission_period: str) -> dict:
    check_piid(piid)
    periods = corpus.periods(piid)
    if submission_period not in periods:
        raise AnalystError(f"No File C period {submission_period!r} for {piid}. Available: {', '.join(periods) or 'none'}.")
    r = residual.explain(corpus, piid, submission_period)
    r["kind"] = "residual"
    r["caveat"] = CAVEAT
    return r


# ------------------------------------------------------------ learning

def _tx_case(corpus: engine.Corpus, key: str, truth: str | None):
    t = corpus.get(key)
    label = corpus.period_of(t)
    # hide the answer's own period, exactly as the backtest does
    c = corpus.without_period(label) if label else corpus
    return learn._case(c, key, truth)


def training_cases(corpus: engine.Corpus, outcomes: list[dict]) -> tuple[list, dict]:
    """Deduced labels for every PIID plus confirmed transaction outcomes."""
    cases, n = [], {"deduced": 0, "confirmed_tx": 0, "confirmed_residual": 0, "skipped": 0}
    seen = set()
    for piid in PIIDS:
        for lb in learn.deduced_labels(corpus, piid):
            cases.append(_tx_case(corpus, lb["key"], lb["truth"]))
            seen.add(lb["key"])
            n["deduced"] += 1
    for o in outcomes:
        if o.get("kind") == "residual":
            n["confirmed_residual"] += 1  # stored; residual scoring is heuristic until enough exist
            continue
        key = o.get("subject_key")
        if o.get("kind") != "tx" or not key or key in seen:
            n["skipped"] += 1
            continue
        try:
            truth = None if o.get("truth") == NONE else o.get("truth")
            cases.append(_tx_case(corpus, key, truth))
            seen.add(key)
            n["confirmed_tx"] += 1
        except KeyError:
            n["skipped"] += 1
    return cases, n


def current_weights(corpus: engine.Corpus, outcomes: list[dict]) -> tuple[dict, dict]:
    """Weights refit on every label we have, shrunk toward the expert priors."""
    cases, n = training_cases(corpus, outcomes)
    w = learn.fit(cases, engine.PRIOR_WEIGHTS)
    moved = {k: {"prior": engine.PRIOR_WEIGHTS[k], "current": w[k]}
             for k in w if abs(w[k] - engine.PRIOR_WEIGHTS[k]) >= 0.01}
    return w, {"labels": n, "n_cases": len(cases), "moved_from_prior": moved,
               "method": "maximum likelihood with an L2 pull toward the priors (lam=2.0)"}


def backtest_summary(corpus: engine.Corpus, piid: str, weights: dict | None) -> dict:
    check_piid(piid)
    rep = backtest.run(corpus, piid, weights)
    rep["reading"] = (
        "Each answer is scored with its own File C period hidden. n is small; read top1/top3 "
        "with n, and compare period top1 with period_baseline_top1 (always pick the account "
        "with the most File C money elsewhere). The engine has skill only if it beats the baseline. "
        "split scores the whole account split (tvd) and the probability given to the truth "
        "(log loss) against the same baseline; lower is better, compare with the smoothed baseline."
    )
    return rep


# ------------------------------------------------------------ outcomes

def validate_outcome(lead: dict, truth: str, evidence_type: str, evidence_locator: str,
                     confirming_office: str, corpus: engine.Corpus) -> dict:
    """Check an outcome before it becomes a label. Returns the row to store."""
    if evidence_type not in EVIDENCE_TYPES:
        raise AnalystError(f"evidence_type must be one of: {', '.join(EVIDENCE_TYPES)}.")
    if len((evidence_locator or "").strip()) < 8:
        raise AnalystError("evidence_locator must point at the document (document number, page, line or URL).")
    if len((confirming_office or "").strip()) < 3:
        raise AnalystError("confirming_office must name who confirmed it.")
    kind = lead.get("kind")
    truth = (truth or "").strip()
    if kind == "tx":
        if truth != NONE:
            t = corpus.get(lead["subject_key"])
            cands, excluded = engine.candidates(corpus, t)
            if loa.parse_tas(truth) is None:
                raise AnalystError("truth must be a TAS like 017-2018/2022-1611-000, or NONE_OF_THESE.")
            if truth not in cands:
                why = next((e["reason"] for e in excluded if e["tas"] == truth), "not listed on the award or in File C")
                raise AnalystError(f"{truth} cannot fund this transaction ({why}). Check the document; if it really "
                                   f"does, record it with truth=NONE_OF_THESE and the TAS in the note.")
    elif kind == "residual":
        if truth not in RESIDUAL_CAUSES:
            raise AnalystError(f"For a residual lead, truth is one of: {', '.join(RESIDUAL_CAUSES)}.")
    elif kind == "case":
        from mcp_aircarrier_analyst.investigator import HYPOTHESES
        if truth not in HYPOTHESES:
            raise AnalystError(f"For a case lead, truth is one of: {', '.join(HYPOTHESES)}.")
    else:
        raise AnalystError("Outcomes are recorded only against transaction, residual or case leads.")
    return {"kind": kind, "piid": lead.get("piid"), "subject_key": lead.get("subject_key"),
            "period": lead.get("period"), "truth": truth, "evidence_type": evidence_type,
            "evidence_locator": evidence_locator.strip(), "confirming_office": confirming_office.strip()}


def rank_of_truth(lead_options: list[dict], truth: str) -> int | None:
    for o in lead_options:
        name = o.get("loa", {}).get("tas") if "loa" in o else o.get("cause", o.get("case", o.get("tas")))
        if name == truth:
            return o.get("rank")
    return None
