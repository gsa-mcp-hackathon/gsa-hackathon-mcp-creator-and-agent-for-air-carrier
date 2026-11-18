"""Transaction data: USAspending and FPDS extracts.

Already authoritative at the row level. The work is aggregation under the D33
and D34 constraints. The deterministic prototypes are checks/tx.py (transaction
history by fiscal year, largest actions, deobligations) and checks/faf.py
(federal account funding by TAS, object class, program activity).

An externally supplied extract routes here with SupplyRoute.EXTERNALLY_SUPPLIED
set, which triggers re-derivation rather than reconciliation: the question
asked of it is what method produced what we hold, not whether it agrees.
"""
import json
import re
from datetime import datetime, timezone
from decimal import Decimal

from core import catalog
from core.contracts import Claim, Coordinate, Tag, Zone
from core.contracts.risk import RiskFlag
from core.policy.decisions import COLLISION_PAIRS, NOT_THIS_HULL

VERSION = "transaction/0.2"
LAYER = "L5"   # Evidence: feeder-system documents beneath the ledger (etl/build_data.py layers)
SOURCE_SYSTEM = "USASPENDING_TRANSACTIONS"   # D33 whitelist
MEASURE = "federal_action_obligation"        # D33: never total_dollars_obligated, a running total


def _spark():
    from pyspark.sql import SparkSession
    return SparkSession.builder.getOrCreate()


def _piid(raw: str) -> str | None:
    m = re.fullmatch(r"([A-Z]\d{5})(\d{2})([A-Z])(\d{4})", raw or "")
    return f"{m[1]}-{m[2]}-{m[3]}-{m[4]}" if m else None


def _hull_for(spark, piid: str) -> tuple[str, str | None]:
    """Hull from the seed-derived graph only. Returns (hull, relation)."""
    rows = spark.sql(
        f"SELECT rel, dst FROM {catalog.KG_EDGES} WHERE src = 'contract:{piid}' AND dst LIKE 'hull:%'"
    ).collect()
    for r in rows:
        if r.rel == "prime_contract_for":
            return r.dst[5:], r.rel
    return "UNATTRIBUTED", (rows[0].rel if rows else None)


def aggregate(artifact_id: str) -> dict:
    """Obligation claims for one transaction artifact, read from the lossless source store.

    Returns {"claims": [...], "checks": {...}, "refused": reason-or-None}. Exact sums are
    computed in DECIMAL and kept verbatim in notes; Claim.value is USD millions.
    """
    spark = _spark()
    reg = [r for r in spark.table(catalog.SRC_REGISTRY).where(f"artifact_id = '{artifact_id}'").collect()
           if {MEASURE, "award_id_piid"} <= set(json.loads(r.column_map))]
    if not reg:
        # Assistance files carry FAIN, not PIID, and are not contract obligations.
        return {"claims": [], "checks": {}, "refused": f"no contract table with {MEASURE} and award_id_piid for {artifact_id}"}
    if all(r.rows_in_source == 0 for r in reg):
        return {"claims": [], "checks": {}, "refused": "source file has a header and no rows"}
    r = reg[0]
    t = r.table_name
    piids = [x.v for x in spark.sql(f"SELECT DISTINCT award_id_piid v FROM {t}").collect()]
    if len(piids) != 1 or not _piid(piids[0]):
        return {"claims": [], "checks": {"piids": piids}, "refused": "table does not resolve to exactly one full PIID (D34)"}
    piid = _piid(piids[0])
    if piid in NOT_THIS_HULL:
        return {"claims": [], "checks": {"piid": piid}, "refused": f"{piid} is do-not-use (G27)"}
    hull, rel = _hull_for(spark, piid)

    tot = spark.sql(f"""SELECT count(*) n, count(DISTINCT _row_sha) u,
        sum(CAST({MEASURE} AS DECIMAL(20,2))) s, min(action_date_fiscal_year) fy0, max(action_date_fiscal_year) fy1,
        max(action_date) asof FROM {t}""").first()
    byfy = spark.sql(f"""SELECT action_date_fiscal_year fy, count(*) n, sum(CAST({MEASURE} AS DECIMAL(20,2))) s
        FROM {t} GROUP BY 1 ORDER BY 1""").collect()
    assert sum((x.s for x in byfy), Decimal(0)) == tot.s, "fiscal-year split does not sum to total"

    now = datetime.now(timezone.utc)
    flags = set() if hull != "UNATTRIBUTED" else {RiskFlag.KEY}
    partner = [b if a == piid else a for a, b in COLLISION_PAIRS if piid in (a, b)]
    note_c = f" Collision partner {partner[0]} is a different contract (D34)." if partner else ""

    def claim(cid, period, s, n, label):
        return Claim(
            claim_id=cid, hull=hull, layer=LAYER, element=f"obligations {piid}", period=period,
            value=float(s / Decimal(1_000_000)), unit="USD_M", discovered_at=now,
            coordinate=Coordinate(artifact_id, row_label=label,
                                  column_header_chain=[MEASURE], neighborhood=f"{t} ({n} rows)"),
            tag=Tag.VERIFIED, confidence=0.97, zone=Zone.RAW, source_system=SOURCE_SYSTEM,
            extraction_method=VERSION, risk_flags=set(flags),
            notes=f"exact {s} USD, SUM({MEASURE}) over {n} transactions; as of {tot.asof}; hull via {rel}.{note_c}")

    claims = [claim(f"{artifact_id}:obl:total", f"FY{tot.fy0}-FY{tot.fy1}", tot.s, tot.n, "all transactions")]
    claims += [claim(f"{artifact_id}:obl:FY{x.fy}", f"FY{x.fy}", x.s, x.n, f"fiscal year {x.fy}") for x in byfy]
    return {"claims": claims, "refused": None,
            "checks": {"table": t, "piid": piid, "hull": hull, "rows": tot.n, "unique_rows": tot.u,
                       "rows_in_source": r.rows_in_source, "total_usd": str(tot.s), "fiscal_years": len(byfy)}}
