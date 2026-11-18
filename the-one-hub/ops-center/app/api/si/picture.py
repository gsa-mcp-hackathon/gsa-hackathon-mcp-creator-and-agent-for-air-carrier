"""The Kennedy picture: the whole CVN-79 cost position on one page.

The demo's Comptroller picture, rebuilt around this program's one question:
can the DCFO stand behind the CVN-79 number at the brief, and what access is
needed for the rest? Every value is computed here from records read now, in
Decimal, and goes out as a Figure envelope (api.envelopes) with its
computation and source. The page draws; it never adds.

Reads degrade one source at a time. A source that cannot be read is named in
sources.failed and its panel says so; the others still render.
"""
from __future__ import annotations

import datetime as dt
from collections import defaultdict
from decimal import Decimal

from .. import envelopes as E
from .. import harness_sql as H
from ..sqlsafe import compose
from . import tasks as T
from .sdk import Ctx, money, now_iso
from .store import STORE, Store


def _fig(fid: str, label: str, value, unit: str, computation: str, source: str,
         as_of: str | None = None, record_ids: list[str] | None = None) -> dict:
    v = None if value is None else (format(value, "f") if isinstance(value, Decimal)
                                    else str(value))
    return E.figure(figure_id=f"picture.{fid}", label=label, value=v, unit=unit,
                    as_of=as_of, record_ids=record_ids or [], computation=computation,
                    source=source)


class _Reads:
    def __init__(self):
        self.ok: list[str] = []
        self.failed: list[dict] = []
        self.at = now_iso()

    def run(self, name: str, fn, default=None):
        try:
            out = fn()
            self.ok.append(name)
            return out
        except Exception as exc:  # noqa: BLE001 - named on the page
            self.failed.append({"source": name, "error": str(exc)[:240]})
            return default


def file_c_tieout(fc_rows: list[dict], tx_rows: list[dict]) -> list[dict]:
    """Per period: File C against the 2114 transactions under the three windows (TO-01)."""
    by_p: dict[str, Decimal] = defaultdict(Decimal)
    n_p: dict[str, int] = defaultdict(int)
    for r in fc_rows:
        by_p[r["period"]] += Decimal(str(r["amount"] or 0))
        n_p[r["period"]] += 1
    pts = [(str(r["action_date"])[:10], Decimal(str(r["amount"] or 0))) for r in tx_rows]
    out = []
    for p in sorted(by_p):
        try:
            fy, mon = T.period_bounds(p)
        except Exception:  # noqa: BLE001 - not a period this method reads
            continue
        end = T._fm_end(fy, mon).isoformat()
        wins = {"3 months": T._fm_start(fy, max(mon - 2, 1)).isoformat(),
                "fiscal year to date": T._fm_start(fy, 1).isoformat(),
                "1 month": T._fm_start(fy, mon).isoformat()}
        sums = {k: sum((v for d, v in pts if a <= d <= end), Decimal(0)) for k, a in wins.items()}
        best = min(sums, key=lambda k: abs(sums[k] - by_p[p]))
        delta = by_p[p] - sums[best]
        out.append({"period": p, "period_end": end, "rows": n_p[p],
                    "file_c": format(by_p[p], "f"), "file_c_display": money(by_p[p]),
                    "window": best, "transactions": format(sums[best], "f"),
                    "transactions_display": money(sums[best]),
                    "delta": format(delta, "f"), "delta_display": money(delta),
                    "ties": abs(delta) < Decimal("0.01")})
    return out


def build(q_app, data_get, store: Store = STORE, today: dt.date | None = None) -> dict:
    from .. import live
    reads = _Reads()
    ctx = Ctx(q_app=q_app, data_get=data_get)
    today = today or dt.datetime.now(dt.timezone.utc).date()

    # --- contracts: both CVN-79 prime contracts, recomputed from every action
    contracts = []
    tx_by: dict[str, list[dict]] = {}
    for key, c in T.CONTRACTS.items():
        notes: list[str] = []
        rows = reads.run(f"FPDS {c['display']}", lambda k=key, n=notes: T._tx_rows(ctx, k, n)[0], [])
        tx_by[key] = rows or []
        if not rows:
            contracts.append({"piid": key, "display": c["display"], "desc": c["desc"],
                              "total": _fig(f"{key}.total", f"Obligations, {c['display']}",
                                            None, "USD", "no actions read", "FPDS"),
                              "series": [], "notes": notes})
            continue
        by_fy: dict[str, list] = defaultdict(lambda: [Decimal(0), 0])
        for r in rows:
            by_fy[str(r["fy"])][0] += Decimal(str(r["amount"] or 0))
            by_fy[str(r["fy"])][1] += 1
        cum, series = Decimal(0), []
        for fy in sorted(by_fy):
            cum += by_fy[fy][0]
            series.append({"fy": fy, "amount": format(by_fy[fy][0], "f"),
                           "display": money(by_fy[fy][0]), "count": by_fy[fy][1],
                           "cumulative": format(cum, "f"), "cumulative_display": money(cum)})
        last = max(str(r["action_date"])[:10] for r in rows)
        contracts.append({
            "piid": key, "display": c["display"], "desc": c["desc"], "last_action": last,
            "total": _fig(f"{key}.total", f"Obligations, {c['display']}", cum, "USD",
                          f"sum of federal_action_obligation over {len(rows)} actions, last "
                          f"action {last} (OB-01)",
                          f"FPDS prime transactions {c['display']}", as_of=reads.at),
            "count": len(rows), "series": series, "notes": notes,
            "task": {"task_id": "reconcile_obligations", "subject": c["display"]}})

    # --- claims: what the brief can stand on
    claims = reads.run("claim ledger", lambda: q_app(
        "SELECT claim_id, element, period, CAST(value AS STRING) AS value, unit, zone "
        f"FROM {live.fqn('claim')} WHERE hull = 'CVN-79' AND superseded_by IS NULL", {}), [])
    claims = claims or []
    promoted = [c for c in claims if c.get("zone") == "V"]
    tie_rows = []
    for c in contracts:
        tot = c["total"]["value"]
        match = next((x for x in claims if x.get("element") == f"obligations {c['display']}"
                      and "-" in str(x.get("period") or "")), None)
        claim_usd = (Decimal(match["value"]) * Decimal(10) ** 6).quantize(Decimal("0.01")) \
            if match and match.get("unit") == "USD_M" else None
        tie_rows.append({"display": c["display"], "claim_id": match and match["claim_id"],
                         "zone": match and match["zone"],
                         "ties": bool(tot is not None and claim_usd is not None
                                      and Decimal(tot) == claim_usd),
                         "claim_display": money(claim_usd) if claim_usd is not None else None})
    standing = sum(1 for r in tie_rows if r["ties"] and r["zone"] == "V")

    # --- File C against the DD&C transactions
    fc_rows = reads.run("File C", lambda: q_app(compose(
        "SELECT submission_period AS period, CAST(transaction_obligated_amount AS STRING) AS "
        "amount FROM {t}", t=live.fqn("file_c")), {}), None)
    if fc_rows is None:
        ext = (data_get("extracts/tieout") or {}) if callable(data_get) else {}
        file_c = [dict(r, file_c_display=money(r["file_c"]), transactions_display=money(
            r["transactions"]), delta_display=money(r["delta"])) for r in ext.get("rows", [])]
    else:
        file_c = file_c_tieout(fc_rows, tx_by.get("N0002415C2114", []))
    for r in file_c:
        r["task"] = {"task_id": "explain_residual", "subject": r["period"]}
    n_tie = sum(1 for r in file_c if r["ties"])

    # --- registers
    var_rows = reads.run("variance register", lambda: q_app(compose(
        "SELECT id, status, flag, title FROM {t} ORDER BY id", t=live.fqn("variances")), {}), None)
    if var_rows is None:
        var_rows = [{"id": v.get("id"), "status": v.get("status"), "flag": v.get("flag"),
                     "title": v.get("title")} for v in (data_get("variances") or {}).get("rows", [])]
    live_var = [v for v in var_rows if v.get("status") == "live"]
    gaps_all = (data_get("gaps") or {}).get("rows", [])
    open_gaps = [g for g in gaps_all if not g.get("closed")]
    top_gaps = sorted(open_gaps, key=lambda g: -(g.get("priority") or 0))[:6]
    by_exec: dict[str, int] = defaultdict(int)
    for g in open_gaps:
        by_exec[g.get("executor") or "unnamed"] += 1

    t = H.tables()
    exc_rows = reads.run("exceptions", lambda: q_app(compose(
        "SELECT owner_role, owner_office, count(*) AS n FROM {t} "
        "WHERE status = 'open' GROUP BY owner_role, owner_office", t=t["exceptions"]), {}), []) or []
    unnamed = reads.run("collection requirements", lambda: q_app(compose(
        "SELECT count(*) AS n, count(target_office) AS named FROM {t}",
        t=live.fqn("collection_requirements")), {}), None)

    # --- SI proposals waiting, by the role they go to
    pend: dict[tuple[str, str], int] = defaultdict(int)
    for run in store.list(limit=store.max_runs):
        for p in run.reviewable():
            pend[(p.goes_to_role, p.goes_to_office)] += 1

    brief = dt.date.fromisoformat(T.BRIEF_DATE)
    days = max((brief - today).days, 0)
    n_claims, n_prom = len(claims), len(promoted)
    pct = (Decimal(n_prom) * 100 / n_claims).quantize(Decimal("0.1")) if n_claims else None

    headline = {
        "question": "Can we stand behind the CVN-79 number at the brief, and what access do "
                    "we need?",
        "promoted": _fig("claims.promoted", "CVN-79 figures that tie to source records", n_prom,
                         "COUNT", "live claim versions, hull CVN-79, zone V (BR-01)",
                         "aircarrier_claim", record_ids=[c["claim_id"] for c in promoted]),
        "claims": _fig("claims.total", "CVN-79 figures in the claim ledger", n_claims, "COUNT",
                       "live claim versions, hull CVN-79", "aircarrier_claim"),
        "percent": _fig("claims.percent", "Share that ties", pct, "PERCENT",
                        "promoted / claims x 100, one decimal", "aircarrier_claim"),
        "brief_date": T.BRIEF_DATE, "days_to_brief": days,
        "text": (f"{n_prom} of {n_claims} CVN-79 figures tie to source records, "
                 f"{days} days before the DCFO brief." if n_claims else
                 "The claim ledger could not be read, so the headline is unknown."),
        "task": {"task_id": "brief_readiness", "subject": "CVN-79"},
    }
    kpis = [
        {"id": "contracts", "label": "Contract totals that stand",
         "figure": _fig("contracts.standing", "Contract totals tied to a promoted claim",
                        standing, "COUNT", "recomputed FPDS total = promoted claim, to the cent",
                        "FPDS + aircarrier_claim"),
         "of": len(contracts), "sub": "FPDS recomputed to the cent against the claim ledger",
         "tone": "ok" if standing == len(contracts) else "warn", "href": "#contracts"},
        {"id": "filec", "label": "File C periods that tie",
         "figure": _fig("filec.tie", "File C periods that tie", n_tie, "COUNT",
                        "periods where one window matches to the cent (TO-01)", "File C + FPDS"),
         "of": len(file_c), "sub": "N00024-15-C-2114, three windows tried per period",
         "tone": "ok" if n_tie == len(file_c) else "bad", "href": "#filec"},
        {"id": "variances", "label": "Live variances",
         "figure": _fig("variances.live", "Live variances", len(live_var), "COUNT",
                        "status = live", "aircarrier_variances"),
         "of": len(var_rows), "sub": "sources that disagree, each with a named cause or not",
         "tone": "warn" if live_var else "ok", "href": "/variances"},
        {"id": "gaps", "label": "Open gaps",
         "figure": _fig("gaps.open", "Open gaps", len(open_gaps), "COUNT",
                        "gap register, not closed", "gaps.json"),
         "of": len(gaps_all), "sub": f"top owner: {max(by_exec, key=by_exec.get)}"
                                    if by_exec else "",
         "tone": "warn", "href": "/gaps"},
        {"id": "days", "label": "Days to the DCFO brief",
         "figure": _fig("brief.days", "Days to the brief", days, "COUNT",
                        f"{T.BRIEF_DATE} - today", "AIRCARRIER_BRIEF_DATE"),
         "of": None, "sub": f"brief on {T.BRIEF_DATE}", "tone": "bad" if days <= 7 else "warn",
         "href": "#brief"},
    ]
    waiting = []
    for (role, office), n in sorted(pend.items(), key=lambda kv: -kv[1]):
        waiting.append({"what": "SI proposals to review", "who": office, "role": role,
                        "figure": _fig(f"waiting.si.{role}", "Proposals waiting", n, "COUNT",
                                       "pending SI proposals going to this role", "SI runs"),
                        "href": "/runs"})
    for r in exc_rows:
        waiting.append({"what": "Open exceptions", "who": r.get("owner_office"),
                        "role": r.get("owner_role"),
                        "figure": _fig(f"waiting.exc.{r.get('owner_role')}", "Open exceptions",
                                       r.get("n"), "COUNT", "status = open",
                                       "aircarrier_app_exceptions"), "href": "/work"})
    if unnamed:
        n_un = int(unnamed[0]["n"]) - int(unnamed[0]["named"])
        waiting.append({"what": "Collection requirements naming no office",
                        "who": "PEO Carriers (names the holder)", "role": "PMS379",
                        "figure": _fig("waiting.cr_unnamed", "Requirements with no office", n_un,
                                       "COUNT", "target_office is null",
                                       "aircarrier_collection_requirements"),
                        "href": "/gaps"})
    for g in top_gaps[:3]:
        waiting.append({"what": f"{g['id']}: {g['title']}", "who": g.get("executor"),
                        "role": None, "figure": None, "href": "/gaps",
                        "task": {"task_id": "investigate_gap", "subject": g["id"]}})
    zones = [{"label": "Tie to source (zone V)", "count": n_prom, "tone": "ok"},
             {"label": "Leads (zone R)", "count": n_claims - n_prom, "tone": "warn"}]
    badges = {"/position": len(file_c) - n_tie, "/variances": len(live_var),
              "/gaps": len(open_gaps), "/runs": len(store.runs),
              "/work": sum(int(r.get("n") or 0) for r in exc_rows) + sum(pend.values())}
    total_sources = len(reads.ok) + len(reads.failed)
    return {
        "as_of": reads.at, "headline": headline, "kpis": kpis, "waiting": waiting,
        "contracts": contracts, "contract_ties": tie_rows, "file_c": file_c, "zones": zones,
        "variances": live_var, "top_gaps": [{k: g.get(k) for k in (
            "id", "title", "status", "executor", "priority")} for g in top_gaps],
        "gaps_by_executor": sorted(({"executor": k, "count": v} for k, v in by_exec.items()),
                                   key=lambda r: -r["count"])[:8],
        "badges": badges, "triggers": T.for_page("/mission"),
        "sources": {"read": len(reads.ok), "total": total_sources, "at": reads.at,
                    "failed": reads.failed,
                    "text": f"Records: read from {len(reads.ok)} of {total_sources} sources "
                            f"at {reads.at[11:19]}Z."},
    }
