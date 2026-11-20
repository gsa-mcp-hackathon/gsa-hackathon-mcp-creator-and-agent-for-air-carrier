"""Databricks job entry point for the challenger agent.

One run:
  1. Take up to --limit work rows kind=claim, state=candidate, owner=challenger.
  2. Read each claim's live version from the ledger in one query.
  3. challenge() returns the flags it earns, each with its tell. Deterministic, no model.
  4. Re-gate the claim with its own flags plus the earned ones (policy.evaluate + gate.route).
  5. Write one row per claim version to the challenge log, then move the work row to
     gated, owned by the gate (routing.py). The ledger row is not touched: the challenger
     never promotes, never edits a value, and the gate decides what the flags mean (D26).

Idempotent: the log is keyed by (claim_id, version_sha), and only candidate rows are taken.
Arguments: --limit N (default 20000), --dry-run.
"""
import argparse
import copy
import json
import pathlib
import sys
import uuid
from collections import Counter
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

from core import catalog, ledger
from core.contracts import State
from core.policy.decisions import evaluate
from core.policy.gate import route
from ops.agents.challenger.run import challenge
from ops.dispatcher.routing import next_action

DDL = f"""CREATE TABLE IF NOT EXISTS {catalog.CHALLENGE_LOG} (
  claim_id STRING NOT NULL, version_sha STRING NOT NULL, earned_flags ARRAY<STRING>, tells ARRAY<STRING>,
  flags_after ARRAY<STRING>, gate_before STRING, gate_after STRING, gate_rule_after STRING, gate_reason_after STRING,
  challenger STRING, run_id STRING, challenged_at TIMESTAMP)
COMMENT 'Challenger verdicts, one row per claim version. Tells are evidence a person can check; no score, no value.'"""
CHALLENGER = "challenger/deterministic-v1"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="challenger_job")
    ap.add_argument("--root", default=None, help="repository root; consumed by _root() at import")
    ap.add_argument("--limit", type=int, default=20000)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv or [])
    from pyspark.sql import SparkSession
    spark = SparkSession.builder.getOrCreate()
    W = catalog.WORK_REGISTER
    run_id = f"challenger-{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).replace(microsecond=0, tzinfo=None)
    owner = next_action("claim", State.CANDIDATE)
    spark.sql(f"""SELECT ref_id AS claim_id FROM {W} WHERE kind = 'claim' AND state = '{State.CANDIDATE.value}'
                  AND owner_agent = '{owner}' ORDER BY work_id LIMIT {int(a.limit)}""").createOrReplaceTempView("_todo")
    gate_before = {r.claim_id: r.gate_decision for r in spark.sql(
        f"SELECT claim_id, gate_decision FROM {catalog.CLAIM_LEDGER} JOIN _todo USING (claim_id) "
        "WHERE superseded_by IS NULL").collect()}
    rows, moves = [], Counter()
    for sha, c in ledger.read_live("_todo"):
        found = challenge(c)
        c2 = copy.deepcopy(c)
        c2.risk_flags |= {f for f, _ in found}
        g = route(c2, evaluate(c2))
        moves[(gate_before.get(c.claim_id), g.decision.value)] += 1
        rows.append((c.claim_id, sha, sorted({f.value for f, _ in found}), [f"{f.value}: {t}" for f, t in found],
                     sorted(f.value for f in c2.risk_flags), gate_before.get(c.claim_id), g.decision.value, g.rule,
                     g.reason, CHALLENGER, run_id, now))
    report = {"run_id": run_id, "dry_run": a.dry_run, "claims": len(rows),
              "gate_moves": {f"{b} -> {x}": n for (b, x), n in moves.most_common()},
              "earned": Counter(f for r in rows for f in r[2])}
    if not a.dry_run and rows:
        spark.sql(DDL)
        spark.createDataFrame(rows, spark.table(catalog.CHALLENGE_LOG).schema).createOrReplaceTempView("_ch")
        report["logged"] = int(spark.sql(f"""MERGE INTO {catalog.CHALLENGE_LOG} t USING _ch s
            ON t.claim_id = s.claim_id AND t.version_sha = s.version_sha WHEN NOT MATCHED THEN INSERT *""").first().num_inserted_rows)
        nxt = next_action("claim", State.GATED)
        report["moved"] = int(spark.sql(f"""MERGE INTO {W} w USING (SELECT DISTINCT claim_id FROM _ch) s
            ON w.work_id = concat('claim:', s.claim_id) AND w.state = '{State.CANDIDATE.value}'
            WHEN MATCHED THEN UPDATE SET state = '{State.GATED.value}', owner_agent = '{nxt}',
              updated_at = TIMESTAMP'{now:%Y-%m-%d %H:%M:%S}',
              history = array_append(w.history, '{now.isoformat()} challenged by {CHALLENGER} ({run_id}), enqueued for {nxt}')
            """).first().num_updated_rows)
    print(json.dumps(report, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
