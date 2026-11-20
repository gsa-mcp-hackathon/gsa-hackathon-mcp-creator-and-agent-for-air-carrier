"""Databricks job entry point for the reader agent.

One run:
  1. Claim. Lock up to --limit work rows owned by the reader in state material_in_hand
     (claimed_at set, attempts + 1). A lock older than LOCK_HOURS is treated as abandoned.
  2. Read. Pick the handler from what the stores say about the artifact, not from its name:
       * a source table with award_id_piid and federal_action_obligation -> transaction
       * another source table -> deferred until a handler for that table exists
       * a PDF with exhibit-titled tables in the cell store            -> exhibit
       * any other PDF                                                  -> prose (mechanisms)
       * a non-PDF document (markdown, txt)                             -> deferred
  3. Gate. Every claim is run through policy.evaluate and gate.route. The reader never
     promotes: the ledger records where the claim must go, the claim keeps zone RAW.
  4. Write. Claims go to the ledger (core/ledger.py, idempotent by content). Each new claim
     gets a work row claim/candidate owned by the challenger (routing.py).
  5. Hand off. The artifact row moves to closed with a history line. A refusal also
     closes it, with the reason in last_error (e.g. WORKING notes, which are not authority).
     A prose PDF closes once its mechanisms and notes are in the mechanism store. Files no
     handler can read stay material_in_hand, unlocked, with last_error 'deferred: ...', and
     are skipped until cleared (or named with --artifact).

Arguments: --limit N (default 50), --artifact ID (only this one), --dry-run (read and gate,
write nothing), --root PATH (repository root; the job passes ${workspace.file_path}).
"""
import argparse
import json
import os
import pathlib
import sys
import traceback
import uuid
from datetime import datetime, timezone


def _root() -> pathlib.Path:
    """Repository root without relying on __file__ (serverless exec()s the file unbound).

    Order: --root, then __file__, then an upward walk from the working directory.
    The full rationale is in ops/entrypoints/tieout_job._root.
    """
    argv = sys.argv
    if "--root" in argv and argv.index("--root") + 1 < len(argv):
        return pathlib.Path(argv[argv.index("--root") + 1])
    here = globals().get("__file__")
    if here:
        return pathlib.Path(here).resolve().parents[2]
    start = pathlib.Path.cwd().resolve()
    for base in (start, *start.parents):
        if (base / "ops" / "entrypoints").is_dir():
            return base
    raise RuntimeError(f"cannot locate the repository root from {start}; "
                       "pass --root ${workspace.file_path} in the job definition")


ROOT = _root()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core import catalog, ledger, mechanisms
from core.contracts import State
from core.policy.decisions import evaluate
from core.policy.gate import route
from ops.agents.reader.handlers import exhibit, prose, transaction
from ops.dispatcher.routing import next_action

MANIFEST = os.environ.get("AIRCARRIER_MANIFEST",
                          "/Volumes/users/xiaobing_shang1_civ/aircarrier_artifacts/MANIFEST.json")
LOCK_HOURS = 2
DEFERRED = "deferred: "


def _spark():
    from pyspark.sql import SparkSession
    return SparkSession.builder.getOrCreate()


def _ts(now: datetime) -> str:
    return f"TIMESTAMP'{now:%Y-%m-%d %H:%M:%S}'"


def choose_handler(spark, artifact_id: str, manifest_row: dict) -> str:
    if manifest_row["route"] == "table":
        return "transaction"
    n = spark.sql(f"SELECT count(*) n FROM {catalog.PDF_TABLES} WHERE artifact_id = :a "
                  r"AND title_block RLIKE 'Exhibit\\s+P-'", args={"a": artifact_id}).first().n
    return "exhibit" if n else "prose"


def read_one(spark, artifact_id: str, manifest_row: dict) -> dict:
    h = choose_handler(spark, artifact_id, manifest_row)
    if h == "transaction":
        r = transaction.aggregate(artifact_id)
        if r["refused"] and r["refused"].startswith("no contract table"):
            # Not a refusal on the merits: the file is a table no handler reads yet (funding
            # history, award summaries, sub-awards). Keep it queued instead of closing it.
            return {"handler": transaction.VERSION, "claims": [], "refused": None, "checks": {},
                    "deferred": "no table handler for this file yet"}
        return {"handler": transaction.VERSION, "claims": r["claims"], "refused": r["refused"], "checks": r["checks"]}
    if h == "exhibit":
        return {"handler": exhibit.VERSION, "claims": exhibit.extract(artifact_id), "refused": None, "checks": {}}
    if manifest_row.get("grade") not in prose.AUTHORITY_GRADES:   # refusal on the merits, before file type
        return {"handler": prose.VERSION, "claims": [], "checks": {},
                "refused": f"grade {manifest_row.get('grade')}: working notes are not authority and cannot establish a mechanism"}
    # MANIFEST suffix has no dot ('pdf', 'md', 'txt'); normalise either form.
    if not artifact_id or manifest_row.get("suffix", "").lower().lstrip(".") != "pdf":
        return {"handler": prose.VERSION, "claims": [], "refused": None, "checks": {},
                "deferred": "prose reader reads the PDF page store; no page text for this file type"}
    pr = prose.read(artifact_id, open_gaps=_open_gaps(spark), known_mechanisms=mechanisms.held(),
                    grade=manifest_row.get("grade", ""))
    return {"handler": prose.VERSION, "claims": [], "refused": pr.refused, "prose": pr,
            "checks": {"mechanisms": len(pr.mechanisms), "rejected_passages": len(pr.rejected),
                       "model_calls": len(pr.calls), "implications": len(pr.implications),
                       "contradictions": len(pr.contradictions), "questions": len(pr.questions)}}


def _open_gaps(spark) -> list[str]:
    out = []
    for n in spark.sql(f"SELECT label, props FROM {catalog.KG_NODES} WHERE node_type = 'gap'").collect():
        p = json.loads(n.props)
        if p.get("status") in ("open", "narrowed", "reframed"):
            note = " ".join((p.get("note") or "").split())[:240]
            out.append(f"{n.label} ({p.get('type')}, executor {p.get('executor')}){': ' + note if note else ''}")
    return out


def _lock(spark, now, limit: int, artifact: str | None) -> list:
    W = catalog.WORK_REGISTER
    only = "AND ref_id = :a" if artifact else ""
    args = {"a": artifact} if artifact else {}
    ids = [r.work_id for r in spark.sql(f"""SELECT work_id FROM {W}
        WHERE kind = 'artifact' AND owner_agent = 'reader' AND state = '{State.MATERIAL_IN_HAND.value}'
          AND (last_error IS NULL OR NOT startswith(last_error, '{DEFERRED}') OR :a2 IS NOT NULL)
          AND (claimed_at IS NULL OR claimed_at < {_ts(now)} - INTERVAL {LOCK_HOURS} HOURS) {only}
        ORDER BY work_id LIMIT {int(limit)}""", args={**args, "a2": artifact}).collect()]
    if not ids:
        return []
    spark.createDataFrame([(i,) for i in ids], "work_id string").createOrReplaceTempView("_lock")
    spark.sql(f"""MERGE INTO {W} w USING _lock l ON w.work_id = l.work_id AND w.state = '{State.MATERIAL_IN_HAND.value}'
        WHEN MATCHED THEN UPDATE SET claimed_at = {_ts(now)}, attempts = w.attempts + 1, updated_at = {_ts(now)}""")
    return spark.sql(f"SELECT work_id, ref_id FROM {W} WHERE claimed_at = {_ts(now)} AND owner_agent = 'reader'").collect()


def _finish(spark, now, work_id: str, state: State, note: str, error: str | None, unlock_only: bool = False):
    W = catalog.WORK_REGISTER
    st = "" if unlock_only else f"state = '{state.value}', owner_agent = :owner,"
    spark.sql(f"""UPDATE {W} SET {st} claimed_at = NULL, last_error = :err, updated_at = {_ts(now)},
        history = array_append(history, :note) WHERE work_id = :w""",
              args={"w": work_id, "err": error, "note": f"{now.isoformat()} {note}",
                    "owner": next_action("artifact", state)})


def _enqueue_claims(spark, now, written: list[tuple[str, str]]) -> dict:
    """Queue each written claim for the challenger. written = [(claim_id, version_sha)].

    New claims get a work row. A claim that already has one is REQUEUED when this run's
    version is now the live one and no challenger verdict exists for that version: a
    re-read that changed a claim (e.g. exhibit/0.3 units) must be challenged and gated
    again, and before 2026-11-10 it silently was not (NOT MATCHED only).

    Not requeued: a claim whose content did not change (its version already carries a
    verdict), a claim whose live version is not this run's (e.g. one the gate promoted),
    and a row already waiting as a candidate. Rerunning the reader is therefore a no-op.
    """
    owner = next_action("claim", State.CANDIDATE)
    cand = State.CANDIDATE.value
    spark.createDataFrame([(f"claim:{c}", c, v) for c, v in written],
                          "work_id string, ref_id string, version_sha string").createOrReplaceTempView("_written")
    verdicts = (f"LEFT JOIN {catalog.CHALLENGE_LOG} x ON x.claim_id = n.ref_id AND x.version_sha = n.version_sha"
                if spark.catalog.tableExists(catalog.CHALLENGE_LOG) else
                "LEFT JOIN (SELECT CAST(NULL AS STRING) claim_id) x ON false")
    spark.sql(f"""SELECT n.work_id, n.ref_id,
          (l.claim_id IS NOT NULL AND x.claim_id IS NULL) AS needs_check
        FROM _written n
        LEFT JOIN {catalog.CLAIM_LEDGER} l
          ON l.claim_id = n.ref_id AND l.version_sha = n.version_sha AND l.superseded_by IS NULL
        {verdicts}""").createOrReplaceTempView("_newclaims")
    r = spark.sql(f"""MERGE INTO {catalog.WORK_REGISTER} w USING _newclaims c ON w.work_id = c.work_id
      WHEN MATCHED AND c.needs_check AND w.state <> '{cand}' THEN UPDATE SET
        state = '{cand}', owner_agent = '{owner}', claimed_at = NULL, updated_at = {_ts(now)},
        history = array_append(w.history, '{now.isoformat()} new version written by reader, requeued for {owner}')
      WHEN NOT MATCHED THEN INSERT (work_id, kind, ref_id, state, owner_agent, claimed_at, exposure_usd_m, attempts,
        last_error, history, updated_at)
      VALUES (c.work_id, 'claim', c.ref_id, '{cand}', '{owner}', NULL, 0.0, 0, NULL,
        array('{now.isoformat()} written by reader, enqueued for {owner}'), {_ts(now)})""").first()
    return {"inserted": int(r.num_inserted_rows), "requeued": int(r.num_updated_rows)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="reader_job")
    ap.add_argument("--root", default=None, help="repository root; consumed by _root() at import")
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--artifact", default=None)
    ap.add_argument("--dry-run", action="store_true")
    # resources/jobs.yml (aircarrier events) passes these. --handler narrows the run to one
    # handler; --source is recorded in the report and the work history.
    ap.add_argument("--handler", choices=["transaction", "exhibit", "prose"], default=None)
    ap.add_argument("--source", default=None)
    a = ap.parse_args(argv or [])
    spark = _spark()
    run_id = f"reader-{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).replace(microsecond=0, tzinfo=None)
    manifest = {r["artifact_id"]: r for r in json.load(open(MANIFEST))["rows"]}
    if a.dry_run:
        q = [r.ref_id for r in spark.sql(f"SELECT ref_id FROM {catalog.WORK_REGISTER} WHERE owner_agent='reader' "
                                         f"AND state='{State.MATERIAL_IN_HAND.value}'").collect()]
        items = [(f"artifact:{x}", x) for x in q if not a.artifact or x == a.artifact][: a.limit]
    else:
        ledger.ensure()
        items = [(r.work_id, r.ref_id) for r in _lock(spark, now, a.limit, a.artifact)]
    report = {"run_id": run_id, "dry_run": a.dry_run, "handler": a.handler, "source": a.source, "items": []}
    failed = 0
    for work_id, artifact_id in items:
        item = {"work_id": work_id}
        try:
            if a.handler and choose_handler(spark, artifact_id, manifest[artifact_id]) != a.handler:
                if not a.dry_run:   # release the lock without spending the attempt on history noise
                    spark.sql(f"UPDATE {catalog.WORK_REGISTER} SET claimed_at = NULL, attempts = attempts - 1 "
                              "WHERE work_id = :w", args={"w": work_id})
                continue
            res = read_one(spark, artifact_id, manifest[artifact_id])
            rows, gates = [], {}
            for c in res["claims"]:
                v = evaluate(c)
                g = route(c, v)
                gates[g.decision.value] = gates.get(g.decision.value, 0) + 1
                rows.append(ledger.to_row(c, gate=g, violations=v, work_id=work_id, run_id=run_id))
            item.update(handler=res["handler"], claims=len(rows), gates=gates, refused=res["refused"],
                        deferred=res.get("deferred"), checks=res["checks"])
            if a.dry_run:
                report["items"].append(item)
                continue
            if res.get("deferred"):
                _finish(spark, now, work_id, State.MATERIAL_IN_HAND, f"deferred by {run_id}: {res['deferred']}",
                        DEFERRED + res["deferred"], unlock_only=True)
            elif res.get("prose") is not None and not res["refused"]:
                pr = res["prose"]
                item["store"] = mechanisms.write(
                    pr.mechanisms, notes={"implication": pr.implications, "contradiction": pr.contradictions,
                                          "question": pr.questions},
                    artifact_id=artifact_id, extraction_method=res["handler"], prompt_version=prose.PROMPT_VERSION,
                    model=",".join(sorted({c["model"] for c in pr.calls})),
                    trace_id=",".join(c["trace"] or "" for c in pr.calls)[:2000], run_id=run_id)
                _finish(spark, now, work_id, State.CLOSED,
                        f"read by {res['handler']} ({run_id}): {res['checks']}", None)
            elif res["refused"]:
                _finish(spark, now, work_id, State.CLOSED, f"refused by {res['handler']} ({run_id})",
                        "refused: " + res["refused"])
            else:
                item["ledger"] = ledger.write(rows)
                item["enqueued"] = _enqueue_claims(spark, now, [(r["claim_id"], r["version_sha"]) for r in rows])
                _finish(spark, now, work_id, State.CLOSED,
                        f"read by {res['handler']} ({run_id}): {len(rows)} claims, gates {gates}", None)
        except Exception as e:   # one bad artifact never stops the run; the row keeps the error
            failed += 1
            item["error"] = f"{type(e).__name__}: {e}"[:500]
            if not a.dry_run:
                _finish(spark, now, work_id, State.MATERIAL_IN_HAND, f"error in {run_id}", item["error"],
                        unlock_only=True)
            traceback.print_exc()
        report["items"].append(item)
    print(json.dumps(report, indent=1, default=str))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
