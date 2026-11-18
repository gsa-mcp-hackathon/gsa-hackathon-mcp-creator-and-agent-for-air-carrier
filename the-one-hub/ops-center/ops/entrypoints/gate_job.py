"""Databricks job entry point for the gate (seed/gate.yaml, core/policy/gate.py).

One run:
  1. Take work rows kind=claim, state=gated, owner=gate.
  2. Rebuild each claim's live ledger version and add the flags the challenger earned for
     that exact version (aircarrier_challenge.flags_after). A claim with no challenge row
     for its live version is not gated: it is sent back to the challenger.
  3. route(claim, evaluate(claim)), with no model. The decision is logged with the rule,
     reason, exposure share, flags and the challenger's tells (aircarrier_gate).
  4. Move the work row by decision:
       human_review         -> state human_review; it joins aircarrier_v_review_queue,
                               ranked by exposure (gate.yaml review_queue)
       promote              -> the logged promotion event (D16): a new ledger version, zone V,
                               state promoted, lineage = the prior version. Work state promoted.
                               --no-promote logs the decision and parks the row instead.
       promote_if_tied_out  -> stays gated, owner tieout. It needs the two-axis close, which is
                               not a per-claim check yet, so nothing is promoted here.
       hold_candidate       -> stays gated, owner hold. It costs nothing and is not reviewed.
       gap                  -> state human_review, with reason; UNKNOWN never promotes.
     Rows parked under tieout/hold keep an owner, so the dispatcher does not re-enqueue them.

Idempotent: only gated rows owned by the gate are taken, and the log is keyed by
(claim_id, version_sha). Arguments: --limit N (default 20000), --dry-run, --no-promote.
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

from core import catalog, ledger                     # noqa: E402
from core.contracts import RiskFlag, State, Zone     # noqa: E402
from core.policy.decisions import evaluate           # noqa: E402
from core.policy.gate import Decision, route         # noqa: E402

GATE_LOG = catalog.STORE_SCHEMA + ".aircarrier_gate"
REVIEW_QUEUE = catalog.STORE_SCHEMA + ".aircarrier_v_review_queue"
GATE = "gate/route-v1"

DDL = [f"""CREATE TABLE IF NOT EXISTS {GATE_LOG} (
  claim_id STRING NOT NULL, version_sha STRING NOT NULL, decision STRING, rule STRING, reason STRING,
  exposure_share DOUBLE, flags ARRAY<STRING>, tells ARRAY<STRING>, outcome STRING, promoted_version STRING,
  gate STRING, run_id STRING, gated_at TIMESTAMP)
COMMENT 'Gate decisions, one row per claim version (seed/gate.yaml). outcome is what the job did with the decision.'""",
       f"""CREATE OR REPLACE VIEW {REVIEW_QUEUE}
  COMMENT 'Human review queue (gate.yaml review_queue): claim, flag, the specific tell, what it bears on, ranked by exposure.'
  AS SELECT g.claim_id, l.hull, l.layer, l.element, l.period, l.value, l.unit, g.exposure_share,
    g.rule, g.reason, g.flags, g.tells, l.coordinate.artifact_id, l.coordinate.exhibit, l.coordinate.page,
    l.coordinate.row_label, l.coordinate.column_header_chain, l.source_system, g.gated_at
  FROM {GATE_LOG} g JOIN {catalog.CLAIM_LEDGER} l ON l.claim_id = g.claim_id AND l.version_sha = g.version_sha
  WHERE g.outcome = 'human_review' AND l.superseded_by IS NULL   -- live versions only; a re-read must not double the queue
  ORDER BY g.exposure_share DESC"""]


def _ts(now):
    return f"TIMESTAMP'{now:%Y-%m-%d %H:%M:%S}'"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="gate_job")
    ap.add_argument("--root", default=None, help="repository root; consumed by _root() at import")
    ap.add_argument("--limit", type=int, default=20000)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-promote", action="store_true")
    a = ap.parse_args(argv or [])
    from pyspark.sql import SparkSession
    spark = SparkSession.builder.getOrCreate()
    W = catalog.WORK_REGISTER
    run_id = f"gate-{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).replace(microsecond=0, tzinfo=None)
    spark.sql(f"""SELECT ref_id AS claim_id FROM {W} WHERE kind = 'claim' AND state = '{State.GATED.value}'
                  AND owner_agent = 'gate' ORDER BY work_id LIMIT {int(a.limit)}""").createOrReplaceTempView("_gtodo")
    ch = {(r.claim_id, r.version_sha): r for r in spark.sql(
        f"SELECT c.* FROM {catalog.CHALLENGE_LOG} c JOIN _gtodo USING (claim_id)").collect()}

    log, promote_rows, moves, outcomes = [], [], {}, Counter()
    for sha, c in ledger.read_live("_gtodo"):
        cr = ch.get((c.claim_id, sha))
        if cr is None:
            moves[c.claim_id] = (State.CANDIDATE, "challenger", "no challenge for the live version; back to the challenger")
            outcomes["rechallenge"] += 1
            continue
        c2 = copy.deepcopy(c)
        c2.risk_flags = {RiskFlag(f) for f in cr.flags_after}
        g = route(c2, evaluate(c2))
        d = g.decision
        promoted_version = None
        if d is Decision.PROMOTE and not a.no_promote:
            p = copy.deepcopy(c2)
            p.zone, p.state = Zone.VALIDATED, State.PROMOTED.value
            p.lineage = list(p.lineage) + [f"{c.claim_id}@{sha}"]
            p.notes = (p.notes + f" | promoted by {GATE} rule {g.rule} ({run_id}): {g.reason}").strip(" |")
            row = ledger.to_row(p, gate=g, violations=[], work_id=f"claim:{c.claim_id}", run_id=run_id)
            promote_rows.append(row)
            promoted_version = f"{c.claim_id}@{row['version_sha']}"
            moves[c.claim_id] = (State.PROMOTED, None, f"promoted by {g.rule}: {promoted_version}")
            outcome = "promoted"
        elif d is Decision.PROMOTE:
            moves[c.claim_id] = (State.GATED, "gate-held", f"{g.rule} promote held by --no-promote")
            outcome = "promote_held"
        elif d is Decision.PROMOTE_IF_TIED_OUT:
            moves[c.claim_id] = (State.GATED, "tieout", f"{g.rule}: awaiting the two-axis close")
            outcome = "awaiting_tieout"
        elif d is Decision.HOLD_CANDIDATE:
            moves[c.claim_id] = (State.GATED, "hold", f"{g.rule}: {g.reason}")
            outcome = "held"
        else:   # HUMAN_REVIEW and GAP both need a person
            moves[c.claim_id] = (State.HUMAN_REVIEW, None, f"{g.rule}: {g.reason}")
            outcome = "human_review"
        outcomes[outcome] += 1
        log.append((c.claim_id, sha, d.value, g.rule, g.reason, float(g.exposure_share), g.flags,
                    list(cr.tells or []), outcome, promoted_version, GATE, run_id, now))

    report = {"run_id": run_id, "dry_run": a.dry_run, "claims": len(log) + outcomes["rechallenge"],
              "outcomes": dict(outcomes),
              "by_rule": dict(Counter(f"{r[3]} {r[2]}" for r in log).most_common())}
    if not a.dry_run and moves:
        for d in DDL[:1]:
            spark.sql(d)
        if log:
            spark.createDataFrame(log, spark.table(GATE_LOG).schema).createOrReplaceTempView("_glog")
            report["logged"] = int(spark.sql(f"""MERGE INTO {GATE_LOG} t USING _glog s
                ON t.claim_id = s.claim_id AND t.version_sha = s.version_sha WHEN NOT MATCHED THEN INSERT *""").first().num_inserted_rows)
        spark.sql(DDL[1])
        if promote_rows:
            report["ledger"] = ledger.write(promote_rows)
        spark.createDataFrame([(f"claim:{k}", s.value, o, n) for k, (s, o, n) in moves.items()],
                              "work_id string, state string, owner string, note string").createOrReplaceTempView("_gmove")
        report["moved"] = int(spark.sql(f"""MERGE INTO {W} w USING _gmove m
            ON w.work_id = m.work_id AND w.state = '{State.GATED.value}' AND w.owner_agent = 'gate'
            WHEN MATCHED THEN UPDATE SET state = m.state, owner_agent = m.owner, updated_at = {_ts(now)},
              history = array_append(w.history, concat('{now.isoformat()} {GATE} ({run_id}): ', m.note))""").first().num_updated_rows)
    print(json.dumps(report, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
