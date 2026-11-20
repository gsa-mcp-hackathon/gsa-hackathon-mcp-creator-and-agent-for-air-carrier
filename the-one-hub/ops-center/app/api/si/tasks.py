"""The SI task registry: what each page may ask, and how each answer is built.

One TaskTemplate per job. Each names its specialist, the rules it works
under, the pages that may trigger it, and three pieces of code:

  packer   SQL (or the shipped extract when no warehouse is bound) that reads
           exactly the records the task needs, and the Facts computed from
           them in Decimal. This is the only place a figure is made.
  steps    the specialist's code steps, one line each with its rule.
  draft    the proposals, addressed by code to the role that owns them.
  canvas   an independent recompute (integer cents, a different grouping)
           that the run's figures must match.

The rule book below restates rules this project already holds (the /ask
system rules, the E-16 resolution, the File C tie-out method, the claim
zones) so a run can cite them by id. It is not the UC rule register, which
governs exceptions.
"""
from __future__ import annotations

import datetime as dt
import os
import re
from collections import defaultdict
from decimal import Decimal

from ..sqlsafe import Fragment, compose
from .sdk import Agent, Ctx, Pack, Proposal, Refused, TaskTemplate, check, money

RULEBOOK: dict[str, str] = {
    "OB-01": "A contract's obligations are federal_action_obligation summed per action in "
             "exact decimal. total_dollars_obligated is a running total and is never summed.",
    "OB-02": "A contract total is stated with its PIID. N00024-09-C-2116 (construction "
             "preparation) and N00024-15-C-2114 (detail design and construction) are never "
             "labelled as each other (E-16).",
    "OB-03": "FPDS is the contract action record, not the accounting record. A reconciled "
             "FPDS total leaves the accounting-system total as a marked blank for the office "
             "that holds it.",
    "TO-01": "A File C period ties when one transaction window (three months to the period "
             "end, fiscal year to date, or the single month) matches its File C amount to the "
             "cent. Which window matched is reported, never assumed.",
    "TO-02": "A period that does not tie is a residual to explain, not an error to correct. "
             "The explanation names the account and the office that can confirm it.",
    "GP-01": "A gap is worked toward one collection request: the document, the system and "
             "the office the record names. A missing office is a marked blank.",
    "BR-01": "Only promoted claims (zone V) are stated as standing at the brief. Every other "
             "figure is a lead and says so.",
    "BR-02": "Every sentence in a brief draft cites a claim, variance or gap id. Nothing "
             "goes to the sponsor from here.",
    "EC-01": "Nothing is saved until a person applies it.",
    "EC-02": "Every stated amount, count and date matches a packed record.",
    "EC-03": "Where the record is silent, the draft keeps a marked blank and names who "
             "fills it.",
}

# The authority roles (aircarrier_app_authority) and the office each stands for.
OFFICES = {
    "PMS379": "PEO Carriers, PMS 379 business financial manager",
    "NAVY_FMO": "ASN(FM&C) Office of Financial Operations",
    "NAVY_FMC": "ASN(FM&C) FMB",
    "OUSD_C_FMO": "OUSD(C) Deputy CFO office",
}

# The brief's goal: named access in these two offices (project brief, 2026-11).
ACCESS_TO = "NAVSEA 01 and PEO Carriers"

CONTRACTS = {
    "N0002409C2116": {"table": "transactions_2116", "display": "N00024-09-C-2116",
                      "desc": "construction preparation"},
    "N0002415C2114": {"table": "transactions_2114", "display": "N00024-15-C-2114",
                      "desc": "detail design and construction"},
}

BRIEF_DATE = os.environ.get("AIRCARRIER_BRIEF_DATE", "2026-11-18")


def piid(s: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (s or "").upper())


def _cents(values) -> int:
    """Independent recompute for the canvas: integer cents, not Decimal."""
    total = 0
    for v in values:
        s = str(v or "0").strip()
        neg = s.startswith("-")
        whole, _, frac = s.lstrip("-").partition(".")
        c = int(whole or "0") * 100 + int((frac + "00")[:2] or "0")
        total += -c if neg else c
    return total


def _usd_from_cents(c: int) -> str:
    return money(Decimal(c) / 100)


def _extract(name: str) -> list[dict]:
    if name.startswith("__"):
        return []
    try:
        from api import explore
        return explore._file(name).get("rows", [])
    except Exception:  # noqa: BLE001 - no extract is an empty read, said by the caller
        return []


def _read(ctx: Ctx, sql: str, params: dict, extract: str, keep, pack_notes: list[str]):
    """Live rows, or the shipped extract (filtered by keep) with a note saying so."""
    if ctx.q_app is not None:
        try:
            return ctx.q_app(sql, params), True
        except Exception as exc:  # noqa: BLE001 - the note says why
            pack_notes.append(f"Live read failed, so the shipped extract was read instead: "
                              f"{str(exc)[:160]}")
    else:
        pack_notes.append("No warehouse is bound, so the shipped extract was read.")
    return [r for r in _extract(extract) if keep(r)], False


# ===================================================== 1 reconcile_obligations
RECONCILER = Agent(
    "obligation_reconciler", "Obligation Reconciler", "SPECIALIST",
    "Recomputes a CVN-79 contract's obligations from its FPDS actions, tests any reported "
    "figure against them, and drafts the baseline and any correction.",
    ("Never sums total_dollars_obligated", "Never moves or commits funds"),
    ("Obligation arithmetic", "Evidence and citation discipline"))


def _tx_rows(ctx: Ctx, key: str, notes: list[str]) -> tuple[list[dict], bool]:
    from api import live
    c = CONTRACTS[key]
    sql = ("SELECT _row_sha AS record_id, award_id_piid AS piid, modification_number AS mod, "
           "CAST(action_date AS STRING) AS action_date, "
           "CAST(action_date_fiscal_year AS STRING) AS fy, "
           "CAST(federal_action_obligation AS STRING) AS amount, "
           "transaction_description AS description "
           f"FROM {live.fqn(c['table'])} ORDER BY action_date, _row_num")
    rows, is_live = _read(ctx, sql, {}, "transactions",
                          lambda r: r.get("award_id_piid") == key, notes)
    if not is_live:
        rows = [{"record_id": r["_row_sha"], "piid": r["award_id_piid"],
                 "mod": r["modification_number"], "action_date": r["action_date"],
                 "fy": r["action_date_fiscal_year"], "amount": r["federal_action_obligation"],
                 "description": r.get("transaction_description")} for r in rows]
    return rows, is_live


def pack_reconcile(ctx: Ctx, subject: str, params: dict) -> Pack:
    key = piid(subject)
    if key not in CONTRACTS:
        raise Refused(f"{subject} is not a CVN-79 prime contract in this product. "
                      "Known: N00024-09-C-2116, N00024-15-C-2114.")
    c = CONTRACTS[key]
    notes: list[str] = []
    rows, is_live = _tx_rows(ctx, key, notes)
    if not rows:
        raise Refused(f"No FPDS actions were found for {c['display']}.")
    amounts = [Decimal(str(r["amount"] or "0")) for r in rows]
    total = sum(amounts, Decimal(0))
    p = Pack("contract", key, "FPDS actions",
             f"FPDS prime transactions for {c['display']}" + ("" if is_live else " (extract)"),
             rows, [r["record_id"] for r in rows], live=is_live, notes=notes)
    p.add("total", f"Obligations, {c['display']}", total, "USD",
          "sum of federal_action_obligation over every action, exact decimal", "OB-01")
    p.add("count", "FPDS actions", len(rows), "COUNT", "row count", "OB-01")
    dates = sorted(str(r["action_date"])[:10] for r in rows if r.get("action_date"))
    p.add("first_date", "First action", dates[0], "DATE", "min(action_date)")
    p.add("last_date", "Last action (as of)", dates[-1], "DATE", "max(action_date)")
    big = max(rows, key=lambda r: Decimal(str(r["amount"] or "0")))
    p.add("largest", "Largest single action", Decimal(str(big["amount"])), "USD",
          f"max(federal_action_obligation): mod {big['mod']} on {str(big['action_date'])[:10]}")
    p.add("largest_date", "Date of the largest action", str(big["action_date"])[:10], "DATE",
          "action_date of the largest action")
    p.context["largest_mod"] = big["mod"]
    neg = [a for a in amounts if a < 0]
    p.add("deob_count", "Deobligations", len(neg), "COUNT", "actions with a negative amount")
    p.add("deob_total", "Deobligated", sum(neg, Decimal(0)), "USD",
          "sum of the negative actions")
    by_fy: dict[str, list] = defaultdict(lambda: [Decimal(0), 0])
    for r, a in zip(rows, amounts):
        by_fy[str(r["fy"])][0] += a
        by_fy[str(r["fy"])][1] += 1
    cum, series = Decimal(0), []
    for fy in sorted(by_fy):
        cum += by_fy[fy][0]
        series.append({"fy": fy, "amount": format(by_fy[fy][0], "f"), "count": by_fy[fy][1],
                       "cumulative": format(cum, "f"), "display": money(by_fy[fy][0]),
                       "cumulative_display": money(cum)})
    p.series["by_fy"] = series
    p.add("fy_count", "Fiscal years with actions", len(series), "COUNT", "distinct FY")
    p.context.update(contract=c["display"], description=c["desc"])
    reported = params.get("reported_total")
    if reported not in (None, ""):
        rep = Decimal(str(reported).replace("$", "").replace(",", ""))
        label = piid(params.get("reported_label") or key)
        p.add("reported", "Reported figure", rep, "USD", "as given by the caller")
        p.add("delta", "Reported less recomputed", rep - total, "USD",
              "reported - total", "OB-02")
        p.context.update(reported_label=CONTRACTS.get(label, {}).get("display", label))
        if label in CONTRACTS:     # packed, so a model that names it is grounded
            p.context["reported_label_description"] = CONTRACTS[label]["desc"]
        if label != key and label in CONTRACTS:
            other, _ = _tx_rows(ctx, label, notes)
            p.add("label_total", f"Obligations, {CONTRACTS[label]['display']}",
                  sum((Decimal(str(r["amount"] or 0)) for r in other), Decimal(0)), "USD",
                  f"the same sum over {len(other)} actions of the contract the figure was "
                  "labelled with", "OB-02")
            p.add("label_count", f"FPDS actions, {CONTRACTS[label]['display']}", len(other),
                  "COUNT", "row count")
    p.records = [{k: r.get(k) for k in ("record_id", "mod", "action_date", "fy", "amount",
                                        "description")} for r in rows]
    return p


def steps_reconcile(p: Pack) -> list[tuple[str, str]]:
    f = p.facts
    out = [((f"Summed federal_action_obligation over {f['count'].display()} actions in exact "
            f"decimal: {f['total'].display()}. total_dollars_obligated was not read."), "OB-01"),
           ((f"Actions run from {f['first_date'].display()} to {f['last_date'].display()} "
            f"across {f['fy_count'].display()} fiscal years. The largest is "
            f"{f['largest'].display()} (mod {p.context['largest_mod']}, "
            f"{f['largest_date'].display()})."), "OB-01"),
           ((f"Found {f['deob_count'].display()} deobligations totalling "
            f"{f['deob_total'].display()}."), "OB-01")]
    if "reported" in f:
        out.append(((f"Tested the reported {f['reported'].display()}, labelled "
                    f"{p.context['reported_label']}, against {f['total'].display()} for "
                    f"{p.context['contract']}: the difference is {f['delta'].display()}."),
                    "OB-02"))
        if "label_total" in f:
            out.append(((f"The contract it was labelled with, {p.context['reported_label']}, "
                        f"recomputes to {f['label_total'].display()}."), "OB-02"))
    return out


def draft_reconcile(p: Pack) -> list[Proposal]:
    f, c = p.facts, p.context
    out = [Proposal(
        "baseline", "obligation_baseline",
        f"Record the FPDS obligation baseline for {c['contract']}",
        "PMS379", OFFICES["PMS379"],
        f"Record {f['total'].display()} across {f['count'].display()} actions, as of "
        f"{f['last_date'].display()}, as the FPDS obligation baseline for {c['contract']} "
        f"({c['description']}).",
        f"Recomputed from {f['count'].display()} FPDS actions in exact decimal, including "
        f"{f['deob_count'].display()} deobligations of {f['deob_total'].display()}. This is the "
        "contract action record; the accounting-system total is still owed.",
        "OB-01", ["total", "count", "last_date", "deob_total"],
        marked_blanks=[{"field": "Accounting-system obligation total on the same date",
                        "who_fills": "NAVSEA 01 or DFAS",
                        "why": "FPDS is the contract action record, not the accounting "
                               "record (OB-03)."}])]
    if "reported" in f:
        same_amount = Decimal(f["delta"].value) == 0
        mislabelled = "label_total" in f
        if mislabelled and same_amount:
            out.append(Proposal(
                "relabel", "correction", f"Relabel the reported figure as {c['contract']}",
                "PMS379", OFFICES["PMS379"],
                f"Relabel {f['reported'].display()} as {c['contract']} ({c['description']}). "
                f"{c['reported_label']} recomputes to {f['label_total'].display()}.",
                f"The amount matches {c['contract']} to the cent and is labelled "
                f"{c['reported_label']}: the wrong contract (E-16).", "OB-02",
                ["reported", "total", "label_total"],
                flags=[{"severity": "high", "text": "A figure labelled with the wrong "
                        "contract would reach the brief."}]))
        elif not same_amount:
            out.append(Proposal(
                "correct", "correction", f"Correct the reported figure for {c['contract']}",
                "PMS379", OFFICES["PMS379"],
                f"Replace {f['reported'].display()} with {f['total'].display()} for "
                f"{c['contract']}, as of {f['last_date'].display()}, or record the as-of date "
                "that explains the difference.",
                f"The reported figure differs from the FPDS record by {f['delta'].display()}. "
                "A difference this size is often an as-of date (E-16); the record does not "
                "say which.", "OB-02", ["reported", "total", "delta"],
                marked_blanks=[{"field": "As-of date of the reported figure",
                                "who_fills": "the office that reported it",
                                "why": "The record is silent on it (EC-03)."}],
                flags=[{"severity": "medium", "text": "Reported and recorded figures "
                        "disagree."}]))
    return out


def canvas_reconcile(p: Pack, proposals: list[Proposal]) -> list[dict]:
    f = p.facts
    cents = _cents(r["amount"] for r in p.records)
    by_fy_cents = sum(_cents([s["amount"]]) for s in p.series["by_fy"])
    out = [check("row count equals the packed record ids", len(p.record_ids), len(p.records)),
           check("record ids are unique", len(p.record_ids), len(set(p.record_ids))),
           check("total recomputed in integer cents", f["total"].display(),
                 _usd_from_cents(cents)),
           check("fiscal-year series adds to the total", f["total"].display(),
                 _usd_from_cents(by_fy_cents)),
           check("no packed record carries total_dollars_obligated", "absent",
                 "present" if any("total_dollars_obligated" in r for r in p.records)
                 else "absent")]
    if "reported" in f:
        out.append(check("reported figure compared with the recomputed total",
                         f["total"].display(), f["reported"].display(), ok=True))
    for pr in proposals:
        out.append(check(f"{pr.key}: addressed to an authority role", "known role",
                         pr.goes_to_role, ok=pr.goes_to_role in OFFICES))
    return out


# ========================================================= 2 explain_residual
ACCOUNT_ANALYST = Agent(
    "account_analyst", "Account Analyst", "SPECIALIST",
    "Ties a File C submission period to the contract's transactions under each window, "
    "names the residual and drafts the lead and the request that would explain it.",
    ("Never treats a residual as an error", ("Never attributes an account the records "
     "do not name")), ("File C tie-out", "Evidence and citation discipline"))


def _fm_start(fy: int, m: int) -> dt.date:
    cal = (m + 8) % 12 + 1
    return dt.date(fy - 1 if m <= 3 else fy, cal, 1)


def _fm_end(fy: int, m: int) -> dt.date:
    if m == 12:
        return dt.date(fy, 9, 30)
    return _fm_start(fy, m + 1) - dt.timedelta(days=1)


def period_bounds(period: str) -> tuple[int, int]:
    m = re.match(r"^FY(\d{4})(Q|P)(\d{1,2})$", (period or "").upper())
    if not m:
        raise Refused(f"{period} is not a File C submission period (FYyyyyQn or FYyyyyPnn).")
    fy, mon = int(m[1]), int(m[3]) * 3 if m[2] == "Q" else int(m[3])
    if not 1 <= mon <= 12:
        raise Refused(f"{period} names no fiscal month.")
    return fy, mon


def pack_residual(ctx: Ctx, subject: str, params: dict) -> Pack:
    from api import live
    period = subject.upper()
    fy, mon = period_bounds(period)
    notes: list[str] = []
    fc_sql = ("SELECT _row_sha AS record_id, submission_period AS period, "
              "treasury_account_symbol AS tas, object_class_code AS object_class, "
              "program_activity_name AS program_activity, "
              "CAST(transaction_obligated_amount AS STRING) AS amount "
              f"FROM {live.fqn('file_c')} WHERE submission_period = :period ORDER BY _row_num")
    fc, live_fc = _read(ctx, fc_sql, {"period": period}, "account_funding",
                         lambda r: (r.get("submission_period") == period
                                    and r.get("award_id_piid") == "N0002415C2114"),
                         notes)
    if not live_fc and fc:
        # Remap extract column names to the SQL aliases used below
        fc = [{"record_id": r.get("_source_locator", "")[:64], "period": r["submission_period"],
               "tas": r.get("treasury_account_symbol", ""),
               "object_class": r.get("object_class_code", ""),
               "program_activity": r.get("program_activity_name", ""),
               "amount": str(r.get("transaction_obligated_amount") or "0")} for r in fc]
    if not fc:
        raise Refused(f"File C has no rows for {period}.")
    start, end = _fm_start(fy, 1), _fm_end(fy, mon)
    tx_all, live_tx = _tx_rows(ctx, "N0002415C2114", notes)
    tx = [r for r in tx_all if start.isoformat() <= str(r["action_date"])[:10] <= end.isoformat()]
    p = Pack("period", period, "records (File C rows and FPDS actions)",
             "File C (federal account funding) and FPDS transactions for N00024-15-C-2114",
             [], [r["record_id"] for r in fc] + [r["record_id"] for r in tx],
             live=live_fc and live_tx, notes=notes)
    fct = sum((Decimal(str(r["amount"] or 0)) for r in fc), Decimal(0))
    p.add("file_c", f"File C obligations, {period}", fct, "USD",
          "sum of transaction_obligated_amount for the period", "TO-01")
    p.add("file_c_rows", "File C rows", len(fc), "COUNT", "row count")
    p.add("tx_rows", "FPDS actions in the fiscal year to the period end", len(tx), "COUNT",
          f"actions dated {start.isoformat()} to {end.isoformat()}")
    p.add("period_end", "Period end", end.isoformat(), "DATE", "last day of the fiscal month")
    wins = {"3 months": _fm_start(fy, max(mon - 2, 1)), "fiscal year to date": start,
            "1 month": _fm_start(fy, mon)}
    sums = {}
    for name, a in wins.items():
        sums[name] = sum((Decimal(str(r["amount"] or 0)) for r in tx
                          if a.isoformat() <= str(r["action_date"])[:10]), Decimal(0))
        p.add(f"win_{name.replace(' ', '_')}", f"Transactions, {name}", sums[name], "USD",
              f"federal_action_obligation dated {a.isoformat()} to {end.isoformat()}", "TO-01")
    best = min(sums, key=lambda k: abs(sums[k] - fct))
    ties = abs(sums[best] - fct) < Decimal("0.01")
    p.add("best_window", "Closest window", best, "TEXT", "the window whose sum is nearest")
    p.add("residual", "File C less transactions (closest window)", fct - sums[best], "USD",
          "file_c - closest window", "TO-02")
    p.add("ties", "Ties to the cent", "yes" if ties else "no", "TEXT", "|residual| < 0.01")
    by_tas: dict[str, Decimal] = defaultdict(Decimal)
    for r in fc:
        by_tas[r["tas"] or "(none)"] += Decimal(str(r["amount"] or 0))
    p.series["windows"] = [{"label": k, "amount": format(v, "f"), "display": money(v),
                            "best": k == best} for k, v in sums.items()]
    p.series["file_c_by_tas"] = [{"label": k, "amount": format(v, "f"), "display": money(v)}
                                 for k, v in sorted(by_tas.items(), key=lambda kv: -kv[1])]
    for i, (k, v) in enumerate(sorted(by_tas.items(), key=lambda kv: -kv[1])[:3]):
        p.add(f"tas_{i}", f"File C, {k}", v, "USD", "sum by treasury account symbol")
    c = CONTRACTS["N0002415C2114"]      # File C is read for this contract only
    p.context.update(period=period, tas=[k for k in by_tas],
                     contract=c["display"], description=c["desc"])
    p.records = ([{"record_id": r["record_id"], "source": "File C", "tas": r["tas"],
                   "object_class": r["object_class"], "amount": r["amount"]} for r in fc] +
                 [{"record_id": r["record_id"], "source": "FPDS", "mod": r["mod"],
                   "action_date": r["action_date"], "amount": r["amount"]} for r in tx])
    p.context["_fc"] = fc
    p.context["_wins"] = {k: v.isoformat() for k, v in wins.items()}
    return p


def steps_residual(p: Pack) -> list[tuple[str, str]]:
    f = p.facts
    out = [((f"Summed {f['file_c_rows'].display()} File C rows for {p.subject_id}: "
            f"{f['file_c'].display()}."), "TO-01")]
    for w in p.series["windows"]:
        out.append(((f"Transactions, {w['label']} to {f['period_end'].display()}: "
                    f"{w['display']}."), "TO-01"))
    if f["ties"].value == "yes":
        out.append((f"The {f['best_window'].display()} window ties to the cent.", "TO-01"))
    else:
        out.append(((f"No window ties. The closest, {f['best_window'].display()}, leaves "
                    f"{f['residual'].display()} to explain."), "TO-02"))
    return out


def draft_residual(p: Pack) -> list[Proposal]:
    f = p.facts
    if f["ties"].value == "yes":
        return [Proposal(
            "tied", "tie_confirmed", f"Record that {p.subject_id} ties", "NAVY_FMO",
            OFFICES["NAVY_FMO"],
            f"Record that File C {p.subject_id} ({f['file_c'].display()}) ties to the "
            f"contract's transactions on the {f['best_window'].display()} window.",
            "Recomputed from both records; the window is the one that matched, not one "
            "assumed.", "TO-01", ["file_c", "best_window"])]
    return [
        Proposal(
            "lead", "attribution_lead", f"Open a residual lead for {p.subject_id}", "NAVY_FMO",
            OFFICES["NAVY_FMO"],
            f"Open a lead: File C {p.subject_id} reports {f['file_c'].display()}; the closest "
            f"transaction window ({f['best_window'].display()}) gives the residual "
            f"{f['residual'].display()}.",
            "Both records were recomputed in code. File C carries the account; the "
            "transactions carry only award-level account lists, so the account behind the "
            "residual is not in the records.", "TO-02", ["file_c", "residual"],
            marked_blanks=[{"field": "Account and transactions that carry the residual",
                            "who_fills": OFFICES["NAVY_FMO"],
                            "why": "Neither record names it (EC-03)."}]),
        Proposal(
            "request", "collection_request",
            f"Request the {p.subject_id} obligation detail", "PMS379", OFFICES["PMS379"],
            f"Ask {OFFICES['NAVY_FMO']} for the obligation-level detail behind File C "
            f"{p.subject_id} for N00024-15-C-2114, by treasury account and document number.",
            f"The residual of {f['residual'].display()} cannot be explained from public "
            "records; the accounting detail can.", "TO-02", ["residual"],
            marked_blanks=[{"field": "Point of contact", "who_fills": OFFICES["NAVY_FMO"],
                            "why": "No holder is named in the role map (EC-03)."}],
            addressed_to=OFFICES["NAVY_FMO"])]


def canvas_residual(p: Pack, proposals: list[Proposal]) -> list[dict]:
    f, fc = p.facts, p.context["_fc"]
    out = [check("File C total recomputed in integer cents", f["file_c"].display(),
                 _usd_from_cents(_cents(r["amount"] for r in fc))),
           check("TAS breakdown adds to the File C total", f["file_c"].display(),
                 _usd_from_cents(sum(_cents([s["amount"]]) for s in p.series["file_c_by_tas"])))]
    fp = [r for r in p.records if r["source"] == "FPDS"]
    end = f["period_end"].value
    for name, a in p.context["_wins"].items():
        c = _cents(r["amount"] for r in fp if a <= str(r["action_date"])[:10] <= end)
        out.append(check(f"window {name} recomputed in integer cents",
                         f[f"win_{name.replace(' ', '_')}"].display(), _usd_from_cents(c)))
    best = f[f"win_{f['best_window'].value.replace(' ', '_')}"].number()
    out.append(check("residual equals File C less the closest window", f["residual"].display(),
                     money(f["file_c"].number() - best)))
    return out


# ========================================================= 3 investigate_gap
GAP_INVESTIGATOR = Agent(
    "gap_investigator", "Gap Investigator", "SPECIALIST",
    "Reads one open gap and its collection requirements and drafts the request a named "
    "office can act on.", ("Never closes a gap", "Never sends a request"),
    ("Gap register", "Collection discipline"))


def pack_gap(ctx: Ctx, subject: str, params: dict) -> Pack:
    from api import live
    gid = subject.upper().strip()
    if not re.match(r"^G\d{1,3}$", gid):
        raise Refused(f"{subject} is not a gap id (G1 to G65).")
    gaps = {g["id"]: g for g in (ctx.data_get("gaps") or {}).get("rows", [])}
    g = gaps.get(gid)
    if g is None:
        raise Refused(f"{gid} is not in the gap register.")
    notes: list[str] = []
    # Requirements raised from a prose question carry its PQ id; the extract maps
    # each PQ to the G gap it was adopted as. Both ids are read.
    try:
        from api import explore
        pq_map = explore._file("requirements").get("pq_to_g") or {}
    except Exception:  # noqa: BLE001 - the G id alone still reads
        pq_map = {}
    ids = [gid] + sorted(k for k, v in pq_map.items() if v == gid)
    marks = ", ".join(f":g{i}" for i in range(len(ids)))
    sql = compose("SELECT cr_id, gap_id, instruction, target_document, target_system, "
                  "target_office, period, account FROM {t} WHERE gap_id IN ({marks}) "
                  "ORDER BY cr_id",
                  t=live.fqn("collection_requirements"), marks=Fragment(marks))  # :g0, :g1 ...
    crs, is_live = _read(ctx, sql, {f"g{i}": v for i, v in enumerate(ids)}, "requirements",
                         lambda r: r.get("gap_id") == gid, notes)
    p = Pack("gap", gid, "collection requirements", "gap register and collection requirements",
             [{k: r.get(k) for k in ("cr_id", "instruction", "target_document",
                                     "target_system", "target_office", "period", "account")}
              for r in crs], [gid] + [r["cr_id"] for r in crs], live=is_live, notes=notes)
    p.add("cr_count", "Collection requirements", len(crs), "COUNT", "rows for this gap")
    offices = sorted({r["target_office"] for r in crs if r.get("target_office")})
    p.add("office_count", "Offices named", len(offices), "COUNT", "distinct target_office")
    p.add("unnamed", "Requirements naming no office",
          sum(1 for r in crs if not r.get("target_office")), "COUNT", "target_office is null")
    exp = Decimal(str(g.get("exposure_usd_m") or 0)) * Decimal(10) ** 6
    p.add("exposure", "Exposure", exp, "USD", "exposure_usd_m x 1,000,000 from the register")
    p.context.update(gap={k: g.get(k) for k in ("id", "title", "status", "type", "executor",
                                                 "closability", "priority", "note")},
                     offices=offices)
    return p


def steps_gap(p: Pack) -> list[tuple[str, str]]:
    g, f = p.context["gap"], p.facts
    return [((f"{g['id']} is {g['status']}: {g['title'].rstrip('.?')}. The register names "
             f"{g['executor'] or 'no executor'} as the one who can close it."), "GP-01"),
            ((f"Read {f['cr_count'].display()} collection requirements; they name "
             f"{f['office_count'].display()} offices and {f['unnamed'].display()} name none."),
             "GP-01")]


def draft_gap(p: Pack) -> list[Proposal]:
    g = p.context["gap"]
    rows = sorted(p.records, key=lambda r: (r.get("target_office") is None, r["cr_id"]))[:2]
    out = []
    for i, r in enumerate(rows or [None]):
        office = (r or {}).get("target_office")
        doc = (r or {}).get("target_document") or "the record that answers it"
        instr = ((r or {}).get("instruction") or f"{g['title'].rstrip('.?')}?")[:420]
        blanks = [] if office else [{"field": "Office that holds it",
                                     "who_fills": g["executor"] or "PEO Carriers",
                                     "why": ("The requirement names no office (GP-01)." if r else
                                             "No collection requirement is recorded for this "
                                             "gap yet; the register names the executor only.")}]
        if not office and not r and g.get("executor"):
            office = f"the office the register names ({g['executor']})"
        out.append(Proposal(
            f"request_{i}", "collection_request",
            f"Request for {g['id']}" + (f" ({r['cr_id']})" if r else ""), "PMS379",
            OFFICES["PMS379"],
            f"Ask {office or 'the office that holds it'} for {doc}. {instr}",
            f"{g['id']} ({g['status']}) blocks: {g['title']}", "GP-01",
            ["cr_count"], marked_blanks=blanks, addressed_to=office or None))
    return out


def canvas_gap(p: Pack, proposals: list[Proposal]) -> list[dict]:
    ids = {r["cr_id"] for r in p.records}
    out = [check("requirement count equals the packed rows", p.facts["cr_count"].value,
                 len(p.records)),
           check("office count recomputed", p.facts["office_count"].value,
                 len({r["target_office"] for r in p.records if r.get("target_office")}))]
    for pr in proposals:
        cited = re.findall(r"\(([A-Z]{2}-[\w-]+)\)", pr.title)
        out.append(check(f"{pr.key}: cited requirement is packed", "packed",
                         "packed" if all(c in ids for c in cited) else "missing"))
        out.append(check(f"{pr.key}: office named or marked blank", "yes",
                         "yes" if (pr.marked_blanks or "Ask the office" not in pr.proposed)
                         else "no"))
    return out


# ======================================================== 4 brief_readiness
BRIEF_COMPOSER = Agent(
    "brief_composer", "Brief Composer", "SPECIALIST",
    "Says what the DCFO brief can stand behind today, what is still a lead, and which "
    "access would move the rest.", ("Never sends a brief", "Never states a lead as a fact"),
    ("Claim zones", "Evidence and citation discipline"))


def pack_brief(ctx: Ctx, subject: str, params: dict) -> Pack:
    from api import live
    hull = subject.upper().strip()
    if hull != "CVN-79":
        raise Refused("The brief covers CVN-79 only.")
    notes: list[str] = []
    sql = compose("SELECT claim_id, element, period, CAST(value AS STRING) AS value, unit, zone, "
                  "state, gate_rule, source_system FROM {t} "
                  "WHERE hull = :hull AND superseded_by IS NULL ORDER BY zone DESC, claim_id",
                  t=live.fqn("claim"))
    claims, is_live = _read(ctx, sql, {"hull": hull}, "__no_extract__", lambda r: False, notes)
    if not is_live and not claims:
        # No warehouse and no extract — proceed with zero claims so the brief
        # composer can still say what the brief cannot stand behind.
        notes.append("No warehouse bound and no claim extract: the brief reports zero claims.")
        claims = []
    var_rows, _ = _read(ctx, compose("SELECT id, status, title FROM {t} ORDER BY id",
                                     t=live.fqn("variances")),
                        {}, "__no_extract__", lambda r: False, notes)
    live_var = [v for v in var_rows if v.get("status") == "live"]
    gaps = [g for g in (ctx.data_get("gaps") or {}).get("rows", []) if not g.get("closed")]
    top = sorted(gaps, key=lambda g: -(g.get("priority") or 0))[:5]
    p = Pack("hull", hull, "claims", "claim ledger, variance register, gap register",
             [{k: c.get(k) for k in ("claim_id", "element", "period", "value", "unit", "zone",
                                     "state", "gate_rule")} for c in claims],
             [c["claim_id"] for c in claims], live=is_live, notes=notes)
    promoted = [c for c in claims if c.get("zone") == "V"]
    p.add("claims", "CVN-79 claims", len(claims), "COUNT", "live claim versions, hull CVN-79")
    p.add("promoted", "Promoted (zone V)", len(promoted), "COUNT", "zone = V", "BR-01")
    p.add("leads", "Still leads", len(claims) - len(promoted), "COUNT", "zone <> V", "BR-01")
    p.add("live_variances", "Live variances", len(live_var), "COUNT", "status = live")
    p.add("open_gaps", "Open gaps", len(gaps), "COUNT", "gap register, not closed")
    today = dt.datetime.now(dt.timezone.utc).date()
    days = (dt.date.fromisoformat(BRIEF_DATE) - today).days
    p.add("brief_date", "Brief date", BRIEF_DATE, "DATE", "AIRCARRIER_BRIEF_DATE")
    p.add("days_to_brief", "Days to the brief", max(days, 0), "COUNT", "brief date - today")
    p.context.update(promoted=[{"claim_id": c["claim_id"], "element": c["element"],
                                "period": c["period"]} for c in promoted[:6]],
                     live_variances=[v["id"] for v in live_var],
                     top_gaps=[{"id": g["id"], "title": g["title"], "executor": g["executor"]}
                               for g in top])
    p.series["zones"] = [{"label": "Promoted (V)", "count": len(promoted)},
                         {"label": "Lead (R)", "count": len(claims) - len(promoted)}]
    return p


def steps_brief(p: Pack) -> list[tuple[str, str]]:
    f = p.facts
    return [((f"{f['promoted'].display()} of {f['claims'].display()} CVN-79 claims are promoted "
             "and can be stated at the brief; the rest are leads."), "BR-01"),
            ((f"{f['live_variances'].display()} variances are live and {f['open_gaps'].display()} "
             "gaps are open."), "BR-02"),
            (f"The brief is on {f['brief_date'].display()}.", "BR-02")]


def draft_brief(p: Pack) -> list[Proposal]:
    f, c = p.facts, p.context
    stand = "; ".join(f"{x['element']} {x['period']} [{x['claim_id']}]" for x in c["promoted"][:3])
    gaps = ", ".join(g["id"] for g in c["top_gaps"][:3])
    return [
        Proposal(
            "draft", "brief_draft", "Brief draft: what the CVN-79 number can stand on",
            "OUSD_C_FMO", OFFICES["OUSD_C_FMO"],
            f"Of {f['claims'].display()} CVN-79 figures, {f['promoted'].display()} tie to source "
            f"records and can be stated: {stand}. {f['leads'].display()} are leads and are shown "
            f"as leads. Open variances: {', '.join(c['live_variances'][:6])}.",
            "Only zone V claims are stated as standing (BR-01); every sentence cites its id "
            "(BR-02). Nothing is sent from here.", "BR-02", ["claims", "promoted", "leads"]),
        Proposal(
            "access", "access_request", "Ask for named access to move the leads", "PMS379",
            OFFICES["PMS379"],
            f"Request named access from {ACCESS_TO} for the gaps that block the most: {gaps}. "
            "Each names the office that can close it.",
            f"{f['leads'].display()} figures stay leads until the accounting record is read; "
            "the access ask is the brief's goal.", "BR-01", ["leads"],
            marked_blanks=[{"field": "Named holder in NAVSEA 01 / PEO Carriers",
                            "who_fills": "PEO Carriers",
                            "why": "No holder is in the role map (EC-03)."}],
            addressed_to=ACCESS_TO)]


def canvas_brief(p: Pack, proposals: list[Proposal]) -> list[dict]:
    ids = {r["claim_id"]: r for r in p.records}
    out = [check("promoted count recomputed", p.facts["promoted"].value,
                 sum(1 for r in p.records if r["zone"] == "V")),
           check("claims count recomputed", p.facts["claims"].value, len(p.records))]
    for pr in proposals:
        cited = re.findall(r"\[([0-9a-f]{16}:[^\]]+)\]", pr.text())
        ok = all(ci in ids and ids[ci]["zone"] == "V" for ci in cited)
        out.append(check(f"{pr.key}: every cited claim is promoted", "all zone V",
                         "all zone V" if ok else "a cited claim is not zone V"))
    return out


# ================================================================ registry
TASKS: dict[str, TaskTemplate] = {t.task_id: t for t in (
    TaskTemplate("reconcile_obligations", "Reconcile {subject}",
                 "Does this contract's reported cost tie to its recorded obligations?",
                 RECONCILER, "contract", ("OB-01", "OB-02", "OB-03", "EC-02", "EC-03"),
                 ("/mission", "/variances", "/position"), pack_reconcile, steps_reconcile,
                 draft_reconcile, canvas_reconcile,
                 validate_subject=lambda s: piid(s) in CONTRACTS,
                 examples=("N00024-09-C-2116", "N00024-15-C-2114")),
    TaskTemplate("explain_residual", "Explain File C {subject}",
                 "Why does this File C period not tie to the transactions?",
                 ACCOUNT_ANALYST, "period", ("TO-01", "TO-02", "EC-02", "EC-03"),
                 ("/mission", "/position", "/execution"), pack_residual, steps_residual,
                 draft_residual, canvas_residual,
                 validate_subject=lambda s: bool(re.match(r"^FY\d{4}(Q\d|P\d{1,2})$",
                                                          (s or "").upper())),
                 examples=("FY2021P03", "FY2020P09", "FY2019Q3")),
    TaskTemplate("investigate_gap", "Work gap {subject}",
                 "Which office can close this gap, and what exactly do we ask for?",
                 GAP_INVESTIGATOR, "gap", ("GP-01", "EC-02", "EC-03"),
                 ("/mission", "/gaps"), pack_gap, steps_gap, draft_gap, canvas_gap,
                 validate_subject=lambda s: bool(re.match(r"^G\d{1,3}$", (s or "").upper())),
                 examples=("G46", "G52", "G14")),
    TaskTemplate("brief_readiness", "Brief readiness for {subject}",
                 "Can we stand behind the CVN-79 number at the brief, and what access do we "
                 "need?", BRIEF_COMPOSER, "hull", ("BR-01", "BR-02", "EC-02", "EC-03"),
                 ("/mission", "/"), pack_brief, steps_brief, draft_brief, canvas_brief,
                 validate_subject=lambda s: (s or "").upper() == "CVN-79",
                 examples=("CVN-79",)),
)}


def route(task_id: str, subject: str) -> TaskTemplate:
    """The Orchestrator's routing table. Unknown pairs are refused, never improvised."""
    tpl = TASKS.get(task_id)
    if tpl is None:
        raise Refused(f"No SI task is named {task_id!r}. Tasks: {', '.join(TASKS)}.")
    if not tpl.validate_subject(subject):
        raise Refused(f"{subject!r} is not a {tpl.subject_kind} the {tpl.specialist.name} "
                      "works on.")
    return tpl


def normalize(task_id: str, subject: str) -> str:
    """The subject as people write it: N00024-09-C-2116, FY2021P03, G14, CVN-79."""
    s = (subject or "").strip()
    if task_id == "reconcile_obligations" and piid(s) in CONTRACTS:
        return CONTRACTS[piid(s)]["display"]
    return s.upper()


def for_page(page: str) -> list[dict]:
    return [t.card() for t in TASKS.values() if page in t.pages]
