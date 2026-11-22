"""The dispatcher job.

Reads the work register against the routing table and enqueues. Scheduled, not
event-driven, because every step is idempotent and a missed tick costs nothing.

It does not orchestrate a DAG. Each agent claims rows in a state and moves them.
"""


import json
import os
import pathlib
import sys
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

from core import catalog
from core.contracts import State
from ops.dispatcher.routing import ROUTES

MANIFEST = os.environ.get("AIRCARRIER_MANIFEST", catalog.ARTIFACTS_VOLUME + "/MANIFEST.json")

# Seed-register status -> state machine. Anything not listed stays out of the register
# and is reported, so a new status word is never silently mapped.
GAP_STATE = {"open": State.OPEN_QUESTION, "narrowed": State.OPEN_QUESTION, "reframed": State.OPEN_QUESTION,
             "closed": State.CLOSED, "resolved": State.CLOSED, "resolved_negative": State.CLOSED,
             "closed_for_pb2027": State.CLOSED}
VARIANCE_STATE = {"live": State.OPEN_QUESTION, "recorded": State.CLOSED, "resolved": State.CLOSED}
ARTIFACT_ROUTES = {"embed", "table"}   # imagery (route asset) has no reader yet

DDL = f"""CREATE TABLE IF NOT EXISTS {catalog.WORK_REGISTER} (
  work_id STRING, kind STRING, ref_id STRING, state STRING, owner_agent STRING, claimed_at TIMESTAMP,
  exposure_usd_m DOUBLE, attempts INT, last_error STRING, history ARRAY<STRING>, updated_at TIMESTAMP)
COMMENT 'Work register (ARCHITECTURE.md: the fourth store). Agents never call each other; a handoff is a state change on a row here. Written only by the dispatcher and the agents.'"""


def _spark():
    from pyspark.sql import SparkSession
    return SparkSession.builder.getOrCreate()


def candidates(spark) -> tuple[list[dict], list[str]]:
    rows, skipped = [], []
    for n in spark.sql(f"SELECT node_id, node_type, props FROM {catalog.KG_NODES} "
                       f"WHERE node_type IN ('gap','variance')").collect():
        status = json.loads(n.props).get("status")
        st = (GAP_STATE if n.node_type == "gap" else VARIANCE_STATE).get(status)
        if st is None:
            skipped.append(f"{n.node_id}: unmapped status {status!r}")
            continue
        rows.append({"kind": n.node_type, "ref_id": n.node_id.split(":", 1)[1], "state": st})
    for a in json.loads(pathlib.Path(MANIFEST).read_text())["rows"]:
        if a["route"] in ARTIFACT_ROUTES:
            rows.append({"kind": "artifact", "ref_id": a["artifact_id"], "state": State.MATERIAL_IN_HAND})
    return rows, skipped


def main(dry_run: bool = False) -> dict:
    """One tick. Idempotent: rerunning changes nothing unless a source register changed.

    1. Register: insert rows for new gaps, variances and artifacts. Existing rows are never
       overwritten here; their state belongs to the agent that moved them.
    2. Enqueue: every unowned row whose (kind, state) has a route gets owner_agent set and a
       history entry. Rows with no route (closed, terminal) are left alone.
    """
    spark = _spark()
    now = datetime.now(timezone.utc).replace(microsecond=0)
    rows, skipped = candidates(spark)
    if not dry_run:
        spark.sql(DDL)
    spark.createDataFrame(
        [(f"{r['kind']}:{r['ref_id']}", r["kind"], r["ref_id"], r["state"].value) for r in rows],
        "work_id string, kind string, ref_id string, state string").createOrReplaceTempView("_cand")
    routes = [(k, s.value, agent) for (k, s), agent in ROUTES.items()]
    spark.createDataFrame(routes, "kind string, state string, agent string").createOrReplaceTempView("_routes")
    if dry_run:
        return {"candidates": len(rows), "skipped": skipped}
    ins = spark.sql(f"""MERGE INTO {catalog.WORK_REGISTER} w USING _cand c ON w.work_id = c.work_id
      WHEN NOT MATCHED THEN INSERT (work_id, kind, ref_id, state, owner_agent, claimed_at, exposure_usd_m, attempts,
        last_error, history, updated_at)
      VALUES (c.work_id, c.kind, c.ref_id, c.state, NULL, NULL, 0.0, 0, NULL,
        array(concat('{now.isoformat()} registered as ', c.state)), TIMESTAMP'{now:%Y-%m-%d %H:%M:%S}')""").first()
    enq = spark.sql(f"""MERGE INTO {catalog.WORK_REGISTER} w
      USING (SELECT w.work_id, r.agent FROM {catalog.WORK_REGISTER} w JOIN _routes r ON w.kind = r.kind AND w.state = r.state
             WHERE w.owner_agent IS NULL) q ON w.work_id = q.work_id
      WHEN MATCHED THEN UPDATE SET owner_agent = q.agent, updated_at = TIMESTAMP'{now:%Y-%m-%d %H:%M:%S}',
        history = array_append(w.history, concat('{now.isoformat()} enqueued for ', q.agent))""").first()
    summary = {r.k: r.n for r in spark.sql(f"SELECT concat(kind,'/',state,'/',coalesce(owner_agent,'-')) k, count(*) n "
                                           f"FROM {catalog.WORK_REGISTER} GROUP BY 1 ORDER BY 1").collect()}
    return {"inserted": ins.num_inserted_rows, "enqueued": enq.num_updated_rows, "skipped": skipped, "register": summary}


if __name__ == "__main__":
    print(json.dumps(main(), indent=1, default=str))
