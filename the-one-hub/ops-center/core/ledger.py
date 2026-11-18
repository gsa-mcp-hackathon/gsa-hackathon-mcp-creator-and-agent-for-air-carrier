"""Claim ledger: the third store (ARCHITECTURE.md), values with coordinates, tags and lineage.

Rules this module enforces, so callers cannot get them wrong:
  * Append-only by version. A row is keyed by (claim_id, version_sha). Rewriting the same
    claim with the same content is a no-op, so a rerun of a reader changes nothing. A
    changed value or coordinate writes a new version and marks the older live version
    superseded_by '<claim_id>@<new sha>'. Nothing is ever deleted or updated in place
    except superseded_by.
  * Withdrawal is a version too. withdraw() appends a copy of the live row with
    state 'withdrawn', the old version in its lineage and the reason in notes, and
    supersedes the old row with it. The value is kept, so the record shows what was
    withdrawn. A claim is never deleted.
  * The gate result is stored with the claim. A reader never promotes; zone stays what the
    handler set (RAW), and gate_decision records where the claim must go next.
  * value is DECIMAL(38,9), taken from repr(float), so a USD_M figure keeps its cents.

Table lives at catalog.CLAIM_LEDGER (users.xiaobing_shang1_civ.aircarrier_claim) until
the aircarrier catalog exists; then point catalog.CLAIM_LEDGER at {CATALOG}.claim.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timezone

from core import catalog
from core.contracts import Claim, Coordinate, RiskFlag, Tag, Zone

TABLE = catalog.CLAIM_LEDGER

DDL = f"""CREATE TABLE IF NOT EXISTS {TABLE} (
  claim_id STRING NOT NULL, version_sha STRING NOT NULL,
  hull STRING, layer STRING, element STRING, period STRING,
  value DECIMAL(38,9), unit STRING, discovered_at TIMESTAMP,
  coordinate STRUCT<artifact_id: STRING, exhibit: STRING, appropriation: STRING, line_item: STRING,
    column_header_chain: ARRAY<STRING>, row_label: STRING, page: INT, page_legends: ARRAY<STRING>,
    neighborhood: STRING>,
  tag STRING, confidence DOUBLE, zone STRING, source_system STRING,
  extraction_method STRING, prompt_version STRING, mlflow_trace_id STRING,
  risk_flags ARRAY<STRING>, lineage ARRAY<STRING>, superseded_by STRING, state STRING, notes STRING,
  gate_decision STRING, gate_rule STRING, gate_reason STRING, policy_violations ARRAY<STRING>,
  work_id STRING, run_id STRING, written_at TIMESTAMP)
COMMENT 'Claim ledger (ARCHITECTURE.md store 3). Append-only by (claim_id, version_sha); superseded_by is the only field ever updated. Written by core/ledger.py only.'"""

_CONTENT = ("hull", "layer", "element", "period", "value", "unit", "tag", "zone", "source_system",
            "extraction_method", "prompt_version", "risk_flags", "lineage", "coordinate")


def _spark():
    from pyspark.sql import SparkSession
    return SparkSession.builder.getOrCreate()


def ensure() -> None:
    _spark().sql(DDL)


def _enum(x):
    return x.value if hasattr(x, "value") else x


def to_row(c: Claim, *, gate=None, violations=(), work_id: str | None = None, run_id: str = "") -> dict:
    coord = asdict(c.coordinate) if c.coordinate else None
    flags = sorted(_enum(f) for f in c.risk_flags)
    row = dict(claim_id=c.claim_id, hull=c.hull, layer=c.layer, element=c.element, period=c.period,
               value=None if c.value is None else repr(float(c.value)), unit=c.unit,
               discovered_at=c.discovered_at, coordinate=coord, tag=_enum(c.tag), confidence=float(c.confidence),
               zone=_enum(c.zone), source_system=c.source_system, extraction_method=c.extraction_method,
               prompt_version=c.prompt_version, mlflow_trace_id=c.mlflow_trace_id, risk_flags=flags,
               lineage=list(c.lineage), superseded_by=None, state=c.state, notes=c.notes,
               gate_decision=_enum(gate.decision) if gate else None, gate_rule=gate.rule if gate else None,
               gate_reason=gate.reason if gate else None,
               policy_violations=[f"{getattr(v, 'decision', '?')}: {v}" for v in violations],
               work_id=work_id, run_id=run_id)
    # version identity is content only: discovered_at, run_id and gate text do not make a new version
    row["version_sha"] = hashlib.sha256(json.dumps({k: row[k] for k in _CONTENT}, sort_keys=True,
                                                   default=str).encode()).hexdigest()[:16]
    return row


def write(rows: list[dict]) -> dict:
    """Append new versions; supersede older live versions. Returns counts.

    Supersede only when the incoming version is genuinely new. If its content already
    exists as an older row of the claim, writing it again must not touch the live row:
      * kept_derived   the live version descends from it (lineage holds claim@sha), e.g.
                       a re-read of the content the gate promoted from. Nothing changed.
      * reverts_skipped the content went back to an older version. Not applied: the
                       live version stays, and the claim ids are returned for review.
    Before 2026-11-10 both cases superseded the live row with a pointer to a row that
    was itself superseded, leaving the claim with no live version (reproduced on a
    scratch ledger). The postcondition below now refuses any write that ends that way.
    """
    if not rows:
        return {"inserted": 0, "superseded": 0}
    ids = [r["claim_id"] for r in rows]
    if len(ids) != len(set(ids)):   # one version per claim per write, or the supersede MERGE is ambiguous
        raise ValueError("duplicate claim_id in one ledger write: " + str(sorted({i for i in ids if ids.count(i) > 1})[:5]))
    spark = _spark()
    ensure()
    now = datetime.now(timezone.utc).replace(microsecond=0, tzinfo=None)
    schema = spark.table(TABLE).schema
    from decimal import Decimal
    data = [{**r, "value": None if r["value"] is None else Decimal(r["value"]).quantize(Decimal("1e-9")),
             "written_at": now} for r in rows]
    df = spark.createDataFrame(data, schema)
    df.createOrReplaceTempView("_ledger_in")
    # What already exists, collected BEFORE the insert (a view would re-read after it).
    prior = spark.sql(f"""SELECT s.claim_id,
          max(CASE WHEN t.version_sha = s.version_sha THEN 1 ELSE 0 END) AS existed,
          max(CASE WHEN t.version_sha = s.version_sha AND t.superseded_by IS NULL THEN 1 ELSE 0 END) AS is_live,
          max(CASE WHEN t.superseded_by IS NULL
                    AND array_contains(t.lineage, concat(s.claim_id, '@', s.version_sha)) THEN 1 ELSE 0 END) AS derived
        FROM _ledger_in s LEFT JOIN {TABLE} t ON t.claim_id = s.claim_id
        GROUP BY s.claim_id""").collect()
    new_ids = [p.claim_id for p in prior if not p.existed]
    kept = [p.claim_id for p in prior if p.existed and not p.is_live and p.derived]
    reverts = [p.claim_id for p in prior if p.existed and not p.is_live and not p.derived]
    spark.createDataFrame([(i,) for i in new_ids] or [(None,)], "claim_id string") \
        .createOrReplaceTempView("_ledger_new")
    ins = spark.sql(f"""MERGE INTO {TABLE} t USING _ledger_in s
        ON t.claim_id = s.claim_id AND t.version_sha = s.version_sha
        WHEN NOT MATCHED THEN INSERT *""").first()
    sup = spark.sql(f"""MERGE INTO {TABLE} t
        USING (SELECT s.* FROM _ledger_in s JOIN _ledger_new n ON n.claim_id = s.claim_id) s
        ON t.claim_id = s.claim_id AND t.version_sha <> s.version_sha AND t.superseded_by IS NULL
        WHEN MATCHED THEN UPDATE SET superseded_by = concat(s.claim_id, '@', s.version_sha)""").first()
    bad = spark.sql(f"""SELECT s.claim_id, count(t.claim_id) n FROM _ledger_in s
        LEFT JOIN {TABLE} t ON t.claim_id = s.claim_id AND t.superseded_by IS NULL
        GROUP BY s.claim_id HAVING count(t.claim_id) <> 1""").collect()
    if bad:
        raise RuntimeError("ledger write left claims without exactly one live version: "
                           + str([(b.claim_id, b.n) for b in bad[:5]]))
    return {"inserted": int(ins.num_inserted_rows), "superseded": int(sup.num_updated_rows),
            "kept_derived": len(kept), "reverts_skipped": len(reverts), "revert_ids": reverts[:50]}


WITHDRAWN = "withdrawn"


def withdrawal_row(live: dict, *, reason: str, by: str, run_id: str) -> dict:
    """The withdrawal version of one live ledger row (a dict of its columns).

    Its version_sha covers the content plus the withdrawal, so it differs from every
    read of the same content, and a later reader that emits the claim again
    supersedes the withdrawal as ordinary new evidence."""
    if not reason.strip():
        raise ValueError("a withdrawal needs a reason")
    if live.get("superseded_by") is not None:
        raise ValueError(f"{live['claim_id']}@{live['version_sha']} is not the live version")
    if live.get("state") == WITHDRAWN:
        raise ValueError(f"{live['claim_id']} is already withdrawn")
    prior = f"{live['claim_id']}@{live['version_sha']}"
    row = {**live, "lineage": [*(live.get("lineage") or []), prior], "state": WITHDRAWN,
           "notes": f"withdrawn by {by}: {reason}", "superseded_by": None, "run_id": run_id,
           "gate_decision": None, "gate_rule": None, "gate_reason": None, "policy_violations": []}
    content = {k: row[k] for k in _CONTENT}
    content["value"] = None if row["value"] is None else repr(float(row["value"]))
    row["version_sha"] = hashlib.sha256(json.dumps({**content, "withdrawn": True}, sort_keys=True,
                                                   default=str).encode()).hexdigest()[:16]
    return row


def withdraw(claim_ids: list[str], *, reason: str, by: str, run_id: str) -> dict:
    """Withdraw live claims: one withdrawal version each, older version superseded,
    and the claim's work row closed so no queue (challenger, human review) still
    holds it. Refuses the whole batch if any id has no single live version or is
    already withdrawn. Returns counts."""
    ids = sorted(set(claim_ids))
    if not ids:
        return {"withdrawn": 0, "superseded": 0, "work_closed": 0}
    spark = _spark()
    spark.createDataFrame([(i,) for i in ids], "claim_id string").createOrReplaceTempView("_wd_ids")
    live = [r.asDict(recursive=True) for r in spark.sql(
        f"SELECT t.* FROM {TABLE} t JOIN _wd_ids USING (claim_id) WHERE t.superseded_by IS NULL").collect()]
    if len(live) != len(ids) or len({r["claim_id"] for r in live}) != len(ids):
        raise RuntimeError(f"withdraw: {len(ids)} ids but {len(live)} live rows; nothing written")
    now = datetime.now(timezone.utc).replace(microsecond=0, tzinfo=None)
    rows = [{**withdrawal_row(r, reason=reason, by=by, run_id=run_id), "written_at": now} for r in live]
    spark.createDataFrame(rows, spark.table(TABLE).schema).createOrReplaceTempView("_wd_in")
    ins = spark.sql(f"""MERGE INTO {TABLE} t USING _wd_in s
        ON t.claim_id = s.claim_id AND t.version_sha = s.version_sha
        WHEN NOT MATCHED THEN INSERT *""").first()
    sup = spark.sql(f"""MERGE INTO {TABLE} t USING _wd_in s
        ON t.claim_id = s.claim_id AND t.version_sha <> s.version_sha AND t.superseded_by IS NULL
        WHEN MATCHED THEN UPDATE SET superseded_by = concat(s.claim_id, '@', s.version_sha)""").first()
    bad = spark.sql(f"""SELECT s.claim_id FROM _wd_in s LEFT JOIN {TABLE} t
        ON t.claim_id = s.claim_id AND t.superseded_by IS NULL
        GROUP BY s.claim_id HAVING count(t.claim_id) <> 1 OR max(t.state) <> '{WITHDRAWN}'""").collect()
    if bad:
        raise RuntimeError("withdraw left claims without exactly one live withdrawn version: "
                           + str([b.claim_id for b in bad[:5]]))
    note = f"{now.isoformat()} claim withdrawn by {by} ({run_id}): {reason}"[:500]
    work = spark.sql(f"""UPDATE {catalog.WORK_REGISTER} SET state = 'closed', owner_agent = NULL,
        claimed_at = NULL, updated_at = current_timestamp(), history = array_append(history, :note)
        WHERE work_id IN (SELECT concat('claim:', claim_id) FROM _wd_ids) AND state <> 'closed'""",
                     args={"note": note}).first()
    return {"withdrawn": int(ins.num_inserted_rows), "superseded": int(sup.num_updated_rows),
            "work_closed": int(work.num_affected_rows)}


def read(claim_id: str, *, include_superseded: bool = False) -> list[Claim]:
    """Rebuild Claim objects from the ledger (live version only unless asked)."""
    where = "" if include_superseded else " AND superseded_by IS NULL"
    return [row_to_claim(r) for r in _spark().sql(
        f"SELECT * FROM {TABLE} WHERE claim_id = :cid{where} ORDER BY written_at", args={"cid": claim_id}).collect()]


def read_live(claim_ids_view: str) -> list[tuple[str, Claim]]:
    """Bulk read: live versions for the claim ids in a temp view with column claim_id.
    Returns (version_sha, Claim) pairs."""
    rows = _spark().sql(f"SELECT l.* FROM {TABLE} l JOIN {claim_ids_view} v USING (claim_id) "
                        "WHERE l.superseded_by IS NULL").collect()
    return [(r.version_sha, row_to_claim(r)) for r in rows]


def row_to_claim(r) -> Claim:
    co = r.coordinate.asDict() if r.coordinate else None
    if co:
        co["column_header_chain"] = list(co["column_header_chain"] or [])
        co["page_legends"] = list(co["page_legends"] or [])
    return (Claim(claim_id=r.claim_id, hull=r.hull, layer=r.layer, element=r.element, period=r.period,
                         value=None if r.value is None else float(r.value), unit=r.unit,
                         discovered_at=r.discovered_at.replace(tzinfo=timezone.utc) if r.discovered_at else None,
                         coordinate=Coordinate(**co) if co else None, tag=Tag(r.tag), confidence=r.confidence,
                         zone=Zone(r.zone), source_system=r.source_system, extraction_method=r.extraction_method,
                         prompt_version=r.prompt_version, mlflow_trace_id=r.mlflow_trace_id,
                         risk_flags={RiskFlag(f) for f in r.risk_flags or []}, lineage=list(r.lineage or []),
                         superseded_by=r.superseded_by, state=r.state, notes=r.notes))
