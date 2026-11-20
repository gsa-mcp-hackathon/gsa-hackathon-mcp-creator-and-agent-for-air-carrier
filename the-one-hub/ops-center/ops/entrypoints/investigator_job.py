"""Databricks job entry point for the investigator agent.

--source prose_questions (the only source so far):
  1. Triage every untriaged question in aircarrier_prose_notes (ops/agents/investigator/triage.py):
     attach to an open G-gap, propose a new gap (PQ-...), or drop with a cited mechanism.
  2. Plan each proposed gap with run(): the deterministic floor requirement plus model
     hypotheses, each validated (named target, grounded in a held mechanism, no figure).
  3. Write aircarrier_question_triage, aircarrier_proposed_gaps, aircarrier_collection_requirements,
     and a work row per proposed gap: kind gap, state collection_required, owner collect.
     Proposed gaps are not G-numbers; a person adopts them into LOG.md Part II.

Idempotent: questions already in the triage table are skipped; ids are content hashes.
Arguments: --source prose_questions, --limit N questions (default 1000), --dry-run.
"""
import argparse
import json
import pathlib
import sys
import uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
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
from core.contracts import Gap, GapType, Mechanism, State
from ops.agents.investigator import triage
from ops.agents.investigator.run import PROMPT_VERSION
from ops.agents.investigator.run import run as plan_gap
from ops.dispatcher.routing import next_action

S = catalog.STORE_SCHEMA
TRIAGE, PROPOSED, CRS = S + ".aircarrier_question_triage", S + ".aircarrier_proposed_gaps", S + ".aircarrier_collection_requirements"
LOG_MD = "/Volumes/users/xiaobing_shang1_civ/aircarrier_artifacts/11f858c166f2e31d/LOG.md"

DDL = [f"""CREATE TABLE IF NOT EXISTS {TRIAGE} (note_id STRING NOT NULL, artifact_id STRING, question STRING,
  action STRING, gap_ref STRING, mechanism_id STRING, reason STRING, model STRING, trace STRING,
  prompt_version STRING, run_id STRING, triaged_at TIMESTAMP)
  COMMENT 'Investigator disposition of each prose-read question: attach | new_gap | drop | untriaged.'""",
       f"""CREATE TABLE IF NOT EXISTS {PROPOSED} (gap_id STRING NOT NULL, question STRING, gap_type STRING,
  executor STRING, closability STRING, blocks STRING, mechanism_ids ARRAY<STRING>, question_ids ARRAY<STRING>,
  plan_notes STRING, n_requirements INT, n_dropped_hypotheses INT, run_id STRING, proposed_at TIMESTAMP)
  COMMENT 'Gaps proposed by the investigator from prose questions. Not G-numbers until a person adopts them into LOG.md Part II.'""",
       f"""CREATE TABLE IF NOT EXISTS {CRS} (cr_id STRING NOT NULL, gap_id STRING, instruction STRING,
  target_document STRING, target_system STRING, target_office STRING, period STRING, account STRING,
  hypothesis STRING, mechanism_ids ARRAY<STRING>, prior DOUBLE, prompt_version STRING, run_id STRING, created_at TIMESTAMP)
  COMMENT 'Collection requirements (D16): a specific retrieval instruction with a named target. Never a figure.'"""]


def _mech(r) -> Mechanism:
    return Mechanism(mechanism_id=r.mechanism_id, statement=r.statement, passage=r.passage,
                     artifact_id=r.artifact_id, citation=r.citation, scope=list(r.scope or []),
                     confidence=r.confidence or 0.0, consequence=r.consequence or "")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="investigator_job")
    ap.add_argument("--root", default=None, help="repository root; consumed by _root() at import")
    ap.add_argument("--source", default="prose_questions", choices=["prose_questions"])
    ap.add_argument("--limit", type=int, default=1000)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args(argv or [])
    from pyspark.sql import SparkSession
    spark = SparkSession.builder.getOrCreate()
    from core.adapters.commercial.llm import make_llm
    llm = make_llm()
    run_id = f"investigator-{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).replace(microsecond=0, tzinfo=None)
    if not a.dry_run:
        for d in DDL:
            spark.sql(d)
    done = "" if not spark.catalog.tableExists(TRIAGE) else f"AND note_id NOT IN (SELECT note_id FROM {TRIAGE})"
    qs = [r.asDict() for r in spark.sql(f"""SELECT n.note_id, n.artifact_id, n.text, coalesce(p.filename, n.artifact_id) source
        FROM {catalog.PROSE_NOTES} n LEFT JOIN (SELECT DISTINCT artifact_id, filename FROM {catalog.PDF_PAGES}) p USING (artifact_id)
        WHERE n.kind = 'question' {done} ORDER BY n.artifact_id, n.note_id LIMIT {int(a.limit)}""").collect()]
    status = {n.label: json.loads(n.props).get("status") for n in spark.sql(
        f"SELECT label, props FROM {catalog.KG_NODES} WHERE node_type = 'gap'").collect()}
    gaps = triage.open_gaps_from_log(open(LOG_MD).read(), status)
    mrows = spark.sql(f"SELECT * FROM {catalog.MECHANISM_STORE} WHERE superseded_by IS NULL").collect()
    mech_by_art: dict[str, list] = {}
    for r in mrows:
        mech_by_art.setdefault(r.artifact_id, []).append(r)
    all_mech = {r.mechanism_id: r for r in mrows}

    # batches never mix too many documents, so each prompt carries only relevant mechanisms
    batches, cur = [], []
    for q in qs:
        if cur and (len(cur) >= triage.BATCH or len({x["artifact_id"] for x in cur} | {q["artifact_id"]}) > 3):
            batches.append(cur)
            cur = []
        cur.append(q)
    batches += [cur] if cur else []

    def do_batch(b):
        arts = {q["artifact_id"] for q in b}
        mechs = {r.mechanism_id: r.statement for art in arts for r in mech_by_art.get(art, [])}
        return b, *triage.triage_batch(llm, b, gaps, mechs)

    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        results = list(ex.map(do_batch, batches))
    trows, proposed = [], {}
    for b, res, call in results:
        qmap = {q["note_id"]: q for q in b}
        for qid, d in res["dispositions"].items():
            trows.append((qid, qmap[qid]["artifact_id"], qmap[qid]["text"], d["action"], d.get("gap_ref"),
                          d.get("mechanism_id"), d.get("reason"), call["model"], call["trace"], triage.PROMPT_VERSION,
                          run_id, now))
        for g in res["new_gaps"]:
            if g["gap_id"] in proposed:
                proposed[g["gap_id"]]["question_ids"] += g["question_ids"]
            else:
                proposed[g["gap_id"]] = g

    def do_plan(g):
        gap = Gap(gap_id=g["gap_id"], question=g["question"], gap_type=GapType(g["gap_type"]),
                  executor=g["executor"], blocks=g["blocks"], closability=g["closability"])
        arts = {all_mech[m].artifact_id for m in g["mechanism_ids"]}
        ms = [_mech(all_mech[m]) for m in g["mechanism_ids"]] + \
             [_mech(r) for art in arts for r in mech_by_art[art] if r.mechanism_id not in g["mechanism_ids"]][:30]
        return g, plan_gap(gap, mechanisms=ms, llm=llm)

    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        plans = list(ex.map(do_plan, proposed.values()))
    prows, crows = [], []
    for g, plan in plans:
        hyp_by_cr = {h.confirms_at.cr_id: h for h in plan.hypotheses}
        for cr in plan.requirements:
            h = hyp_by_cr.get(cr.cr_id)
            crows.append((cr.cr_id, g["gap_id"], cr.instruction, cr.target_document, cr.target_system, cr.target_office,
                          cr.period, cr.account, h.statement if h else "floor: the gap's own type and executor",
                          h.mechanism_ids if h else [], float(h.prior) if h else None, PROMPT_VERSION, run_id, now))
        prows.append((g["gap_id"], g["question"], g["gap_type"], g["executor"], g["closability"], g["blocks"],
                      g["mechanism_ids"], sorted(set(g["question_ids"])), plan.notes, len(plan.requirements),
                      len(plan.dropped), run_id, now))
    report = {"run_id": run_id, "dry_run": a.dry_run, "questions": len(qs), "batches": len(batches),
              "open_gaps_offered": len(gaps), "actions": dict(Counter(r[3] for r in trows)),
              "proposed_gaps": len(prows), "requirements": len(crows),
              "dropped_hypotheses": sum(r[10] for r in prows),
              "models": sorted({c["model"] for _, _, c in results})}
    if not a.dry_run:
        for rows, table, key in ((trows, TRIAGE, "note_id"), (prows, PROPOSED, "gap_id"), (crows, CRS, "cr_id")):
            if rows:
                spark.createDataFrame(rows, spark.table(table).schema).createOrReplaceTempView("_inv")
                spark.sql(f"MERGE INTO {table} t USING _inv s ON t.{key} = s.{key} WHEN NOT MATCHED THEN INSERT *")
        if prows:
            owner = next_action("gap", State.COLLECTION_REQUIRED)
            spark.createDataFrame([(f"gap:{r[0]}", r[0]) for r in prows], "work_id string, ref_id string") \
                .createOrReplaceTempView("_pg")
            report["work_rows"] = int(spark.sql(f"""MERGE INTO {catalog.WORK_REGISTER} w USING _pg p ON w.work_id = p.work_id
              WHEN NOT MATCHED THEN INSERT (work_id, kind, ref_id, state, owner_agent, claimed_at, exposure_usd_m, attempts,
                last_error, history, updated_at)
              VALUES (p.work_id, 'gap', p.ref_id, '{State.COLLECTION_REQUIRED.value}', '{owner}', NULL, 0.0, 0, NULL,
                array('{now.isoformat()} proposed by investigator from prose questions ({run_id}); adopt into LOG.md Part II'),
                TIMESTAMP'{now:%Y-%m-%d %H:%M:%S}')""").first().num_inserted_rows)
    print(json.dumps(report, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
