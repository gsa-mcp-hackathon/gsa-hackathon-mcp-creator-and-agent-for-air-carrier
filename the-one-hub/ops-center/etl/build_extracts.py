#!/usr/bin/env python3
"""Bundled extracts for the front center.

The app reads Unity Catalog live when it has a warehouse and the grants, and
falls back to these files when it does not. That is D11 applied to the new
pages: the dashboard, the detail table and the agent all work at every access
level, including zero, and say which mode they are in.

Everything here is read from the stores the ops center already writes. No
figure is typed. Rebuild after an ingest, tie-out or investigator run:

    python etl/build_extracts.py --root <bundle files dir>      # on Spark

Writes app/data/extracts/*.json and a meta.json naming the tables, row counts
and build time, so a page can show how old its offline copy is.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
from decimal import Decimal

TX_COLS = ["award_id_piid", "modification_number", "action_date",
           "action_date_fiscal_year", "action_type", "federal_action_obligation",
           "transaction_description", "funding_office_name",
           "product_or_service_code", "_artifact_id", "_row_sha",
           "_source_locator"]
# Never total_dollars_obligated: it is a per-row running total and summing it
# is the error recorded in LOG. The extract does not carry it, so the detail
# table and the agent cannot sum it by accident.


def _num(v) -> str | None:
    return None if v is None else format(Decimal(str(v)).quantize(Decimal("0.01")), "f")


# ------------------------------------------------------------------ tie-out
def _fm_start(fy: int, m: int) -> dt.date:
    """First day of fiscal month m (1 = October) of fiscal year fy."""
    cal = (m + 8) % 12 + 1
    return dt.date(fy - 1 if m <= 3 else fy, cal, 1)


def _fm_end(fy: int, m: int) -> dt.date:
    if m == 12:
        return dt.date(fy, 9, 30)
    return _fm_start(fy, m + 1) - dt.timedelta(days=1)


def tieout(file_c: list[dict], tx: list[dict]) -> dict:
    """File C against the transaction record, per submission period.

    Three window readings are tried for each period: the three months ending
    at the period, fiscal year to date, and the single month. A period ties
    when any reading matches to the cent. Which reading matched is reported,
    never assumed, because the periods do not share one."""
    by_p: dict[str, Decimal] = {}
    n_p: dict[str, int] = {}
    for r in file_c:
        p = r["submission_period"]
        by_p[p] = by_p.get(p, Decimal(0)) + Decimal(str(r["transaction_obligated_amount"] or 0))
        n_p[p] = n_p.get(p, 0) + 1
    pts = [(dt.date.fromisoformat(str(r["action_date"])[:10]),
            Decimal(str(r["federal_action_obligation"] or 0))) for r in tx]

    def s(a, b):
        return sum((v for d, v in pts if a <= d <= b), Decimal(0))

    rows = []
    for p in sorted(by_p):
        m = re.match(r"FY(\d{4})(Q|P)(\d+)$", p)
        if not m:
            continue
        fy, mon = int(m[1]), int(m[3]) * 3 if m[2] == "Q" else int(m[3])
        end = _fm_end(fy, mon)
        win = {"3 months": s(_fm_start(fy, max(mon - 2, 1)), end),
               "fiscal year to date": s(_fm_start(fy, 1), end),
               "1 month": s(_fm_start(fy, mon), end)}
        best = min(win, key=lambda k: abs(win[k] - by_p[p]))
        ties = abs(win[best] - by_p[p]) < Decimal("0.01")
        rows.append({"period": p, "file_c_rows": n_p[p], "file_c": _num(by_p[p]),
                     "window": best, "transactions": _num(win[best]),
                     "delta": _num(by_p[p] - win[best]), "ties": ties,
                     "windows": {k: _num(v) for k, v in win.items()},
                     "period_end": end.isoformat()})
    return {"piid": "N0002415C2114", "rows": rows,
            "n_periods": len(rows), "n_tie": sum(r["ties"] for r in rows)}


# ---------------------------------------------------------------- gap map
def pq_to_g(log_text: str) -> dict[str, str]:
    """PQ- id to adopted G id, read from the LOG headings rather than typed."""
    out = {}
    for g, body in re.findall(r"^#+\s*(G\d+)\b[^\n]*\n(.*?)(?=^#+\s*G\d+\b|\Z)",
                              log_text, re.M | re.S):
        m = re.search(r"PQ-[0-9a-f]{8}", body)
        if m and re.fullmatch(r"G\d+", g):
            out[m[0]] = g
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, help="bundle files directory")
    ap.add_argument("--catalog", default="users")
    ap.add_argument("--schema", default="xiaobing_shang1_civ")
    ap.add_argument("--prefix", default="aircarrier_")
    a = ap.parse_args()

    from pyspark.sql import SparkSession
    spark = SparkSession.builder.getOrCreate()
    root = pathlib.Path(a.root)
    out = root / "app" / "data" / "extracts"
    out.mkdir(parents=True, exist_ok=True)
    fq = f"{a.catalog}.{a.schema}.{a.prefix}"

    def rows(sql):
        return [r.asDict(recursive=True) for r in spark.sql(sql).collect()]

    counts, written = {}, {}

    def write(name, obj, n):
        (out / f"{name}.json").write_text(json.dumps(obj, default=str, indent=1))
        counts[name] = n

    # transactions, both primes, the columns the detail table shows
    cols = ", ".join(TX_COLS)
    tx = rows(f"select {cols} from {fq}src_2114_contract_transactions union all "
              f"select {cols} from {fq}src_2116_contract_transactions "
              "order by award_id_piid, action_date, modification_number")
    for r in tx:
        r["federal_action_obligation"] = _num(r["federal_action_obligation"])
        r["action_date"] = str(r["action_date"])[:10]
    write("transactions", {"columns": TX_COLS, "rows": tx}, len(tx))

    # File C tie-out, 2114 only: no File C was published for 2116
    fc = rows(f"select submission_period, transaction_obligated_amount "
              f"from {fq}src_2114_federal_account_funding")
    t = tieout(fc, [r for r in tx if r["award_id_piid"] == "N0002415C2114"])
    write("tieout", t, t["n_periods"])

    # evidence pipeline
    pipe = {
        "claims": rows(f"select zone, state, count(*) n from {fq}claim "
                       "where superseded_by is null group by 1, 2 order by 3 desc"),
        "claims_total": rows(f"select count(*) n from {fq}claim")[0]["n"],
        "claims_superseded": rows(f"select count(*) n from {fq}claim "
                                  "where superseded_by is not null")[0]["n"],
        "gate": rows(f"select outcome, count(*) n from {fq}gate group by 1 order by 2 desc"),
        "challenge_changed": rows(
            f"select count(*) n from {fq}challenge "
            "where coalesce(gate_before,'') <> coalesce(gate_after,'')")[0]["n"],
        "challenge_total": rows(f"select count(*) n from {fq}challenge")[0]["n"],
        "review_queue": rows(f"select count(*) n from {fq}v_review_queue")[0]["n"],
    }
    write("pipeline", pipe, pipe["claims_total"])

    # analyst leads, every option, ranked
    leads = rows(f"select question, rank, confidence, none_of_these, option, grade, "
                 f"status, kind, piid, period, engine, run_id, created_at "
                 f"from {fq}analyst_leads order by question, kind, rank")
    for r in leads:
        try:
            r["option"] = json.loads(r["option"])
        except (TypeError, ValueError):
            pass
    write("leads", {"rows": leads}, len(leads))

    # collection requirements, mapped onto adopted gap ids
    log = (root / "corpus" / "durable" / "LOG.md").read_text()
    m = pq_to_g(log)
    reqs = rows(f"select cr_id, gap_id, instruction, target_document, target_system, "
                f"target_office, period, account, hypothesis from {fq}collection_requirements")
    for r in reqs:
        r["pq_id"] = r.pop("gap_id")
        r["gap_id"] = m.get(r["pq_id"])
    write("requirements", {"rows": reqs, "pq_to_g": m,
                           "unmapped": sorted({r["pq_id"] for r in reqs if not r["gap_id"]})},
          len(reqs))

    # exhibit tables index; cells are live only (144k rows does not ship)
    ex = rows(f"select table_id, artifact_id, filename, page, table_idx, n_rows, n_cols, "
              f"exhibits, substr(title_block, 1, 240) title from {fq}pdf_tables "
              "order by filename, page, table_idx")
    write("exhibits", {"rows": ex}, len(ex))

    meta = {"built_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "source": fq.rstrip("_") + "*", "counts": counts}
    (out / "meta.json").write_text(json.dumps(meta, indent=1))
    print(json.dumps(meta, indent=1))
    return 0


if __name__ == "__main__":
    # Serverless runs spark_python_task under IPython, which reports even
    # SystemExit(0) as a failed run. Raise only on a real failure.
    rc = main()
    if rc:
        raise SystemExit(rc)
