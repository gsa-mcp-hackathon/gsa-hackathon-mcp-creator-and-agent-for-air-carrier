"""Mechanism store: the second store (ARCHITECTURE.md), rules with establishing passages.

A mechanism without a verbatim passage does not enter (core/contracts/mechanism.py). The prose
reader checks that before calling write(); this module refuses an empty passage as a backstop.
mechanism_id is a hash of artifact + normalised passage, so rereading a document is a no-op.
The other three parts of a prose read (implications, contradictions, questions) go to
PROSE_NOTES so the Investigator can turn them into gaps; they never become mechanisms.
"""
from __future__ import annotations

from datetime import datetime, timezone

from core import catalog
from core.contracts import Mechanism

TABLE = catalog.MECHANISM_STORE
NOTES = catalog.PROSE_NOTES

DDL = [f"""CREATE TABLE IF NOT EXISTS {TABLE} (
  mechanism_id STRING NOT NULL, statement STRING, passage STRING NOT NULL, artifact_id STRING, citation STRING,
  page INT, scope ARRAY<STRING>, established_at TIMESTAMP, confidence DOUBLE, consequence STRING,
  superseded_by STRING, decision_ref STRING, extraction_method STRING, prompt_version STRING, model STRING,
  mlflow_trace_id STRING, review_state STRING, run_id STRING, written_at TIMESTAMP)
COMMENT 'Mechanism store (ARCHITECTURE.md store 2). Every row carries a passage verified verbatim against aircarrier_pdf_pages. review_state starts at candidate; a person promotes. Written by core/mechanisms.py only.'""",
       f"""CREATE TABLE IF NOT EXISTS {NOTES} (
  note_id STRING NOT NULL, artifact_id STRING, kind STRING, text STRING, extraction_method STRING,
  prompt_version STRING, run_id STRING, written_at TIMESTAMP)
COMMENT 'Prose read parts 2-4: implications, contradictions, questions. Leads for the Investigator, never figures or mechanisms.'"""]


def _spark():
    from pyspark.sql import SparkSession
    return SparkSession.builder.getOrCreate()


def ensure() -> None:
    for d in DDL:
        _spark().sql(d)


def held(limit: int = 300) -> list[str]:
    """Statements already held, as the prose prompt's MECHANISMS ALREADY HELD list."""
    spark = _spark()
    if not spark.catalog.tableExists(TABLE):
        return []
    return [f"{r.mechanism_id}: {r.statement}" for r in spark.sql(
        f"SELECT mechanism_id, statement FROM {TABLE} WHERE superseded_by IS NULL ORDER BY confidence DESC LIMIT {int(limit)}").collect()]


def write(mechs: list[Mechanism], *, notes: dict[str, list[str]], artifact_id: str, extraction_method: str,
          prompt_version: str, model: str | None, trace_id: str | None, run_id: str) -> dict:
    import hashlib
    spark = _spark()
    ensure()
    now = datetime.now(timezone.utc).replace(microsecond=0, tzinfo=None)
    bad = [m.mechanism_id for m in mechs if not (m.passage or "").strip()]
    if bad:
        raise ValueError(f"mechanisms without a passage cannot enter: {bad[:5]}")
    rows = [(m.mechanism_id, m.statement, m.passage, m.artifact_id, m.citation,
             int(m.citation.rsplit("p.", 1)[1]) if "p." in m.citation else None, list(m.scope),
             m.established_at.replace(tzinfo=None) if m.established_at else None, float(m.confidence), m.consequence,
             None, m.decision_ref, extraction_method, prompt_version, model, trace_id, "candidate", run_id, now)
            for m in mechs]
    out = {"mechanisms_inserted": 0, "notes_inserted": 0}
    if rows:
        spark.createDataFrame(rows, spark.table(TABLE).schema).createOrReplaceTempView("_mech_in")
        out["mechanisms_inserted"] = int(spark.sql(f"""MERGE INTO {TABLE} t USING _mech_in s ON t.mechanism_id = s.mechanism_id
            WHEN NOT MATCHED THEN INSERT *""").first().num_inserted_rows)
    nrows = []
    for kind, items in notes.items():
        for text in dict.fromkeys(t.strip() for t in items if t and t.strip()):
            nid = hashlib.sha256(f"{artifact_id}|{kind}|{text.lower()}".encode()).hexdigest()[:16]
            nrows.append((nid, artifact_id, kind, text, extraction_method, prompt_version, run_id, now))
    if nrows:
        spark.createDataFrame(nrows, spark.table(NOTES).schema).createOrReplaceTempView("_notes_in")
        out["notes_inserted"] = int(spark.sql(f"""MERGE INTO {NOTES} t USING _notes_in s ON t.note_id = s.note_id
            WHEN NOT MATCHED THEN INSERT *""").first().num_inserted_rows)
    return out
