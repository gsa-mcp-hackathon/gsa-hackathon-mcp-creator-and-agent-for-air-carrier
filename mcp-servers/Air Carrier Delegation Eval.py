# Databricks notebook source
# DBTITLE 1,About this eval
# MAGIC %md
# MAGIC # Air Carrier MCP delegation eval
# MAGIC
# MAGIC Tests whether an LLM agent, handed all 30 tools (29 before 2026-11-20) from **mcp-aircarrier-docs**, **mcp-aircarrier-analyst** and **mcp-aircarrier-ops**, picks the right tools and returns the right answer.
# MAGIC
# MAGIC * **Tools run in-process** through `mcp-servers/mcp_local.py`, reading Unity Catalog as the person running the notebook. The deployed apps and the connectors are not involved, so a connector auth failure cannot mask a tool defect. It also means grant gaps on an app's service principal are **not** tested here: the probe app covers those.
# MAGIC * **Models** are called through the serving-endpoint `invocations` route with OpenAI-style tool calling.
# MAGIC * **Each question has an answer checked against SQL**; grading is a set of regexes that must all match.
# MAGIC * **Two question sets**: `dev` (Q1-Q9, the questions the fixes were found on) and `fresh` (F1-F5, written after the fixes and never used to change a tool). Quote `fresh` in the evaluation report.
# MAGIC * **Every run is appended** to `users.xiaobing_shang1_civ.aircarrier_delegation_eval_runs` with the answer, tool trace and a hash of the tool catalog and instructions, so results can be tied to a code version.
# MAGIC * **Two prompt modes**: `no_instr` (system prompt only) and `instr` (plus each server's MCP `instructions`, which some clients inject and some do not).
# MAGIC
# MAGIC ## Recorded results, 2026-11-18 (one run per configuration)
# MAGIC
# MAGIC | Configuration | Before fixes | After fixes |
# MAGIC | --- | --- | --- |
# MAGIC | claude-sonnet-4-5, no_instr | 9/9, 460k prompt tokens, 25 calls | 9/9, 213k, 12 calls |
# MAGIC | gpt-5-mini, no_instr | 7/9, 195k, 13 calls | 9/9, 176k, 11 calls |
# MAGIC | claude-sonnet-4-5, instr | not run | 9/9, 228k |
# MAGIC | gpt-5-mini, instr | not run | 9/9, 215k |
# MAGIC
# MAGIC Defects this eval found, all fixed in source and deployed on 2026-11-18: no modification or fiscal-year filter on the obligations search (Q4), "open" read as `open_question` only (Q6), the decoy costing 255k tokens because no tool flagged the premise (Q8, now `premise_flags` in `docs_search`), ops instructions pointing to a nonexistent describe tool, and paging without `ORDER BY`.
# MAGIC
# MAGIC **Caveats:** small sets, one run per configuration, and regex grading: an answer can match a pattern by accident (for example a bare "8"), so read the answers in the inspect cell before quoting a pass.

# COMMAND ----------

# DBTITLE 1,Install MCP client
# MAGIC %pip install -q "fastmcp>=2.14,<3"
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

# DBTITLE 1,Settings
# Models to evaluate (serving endpoint names) and prompt modes to run.
MODELS = ["databricks-claude-sonnet-4-5", "databricks-gpt-5-mini"]
MODES = ["no_instr", "instr"]
MAX_STEPS = 8          # tool-calling turns before the agent is cut off
MAX_TOOL_CHARS = 60000 # longest tool result passed back to the model
QUESTION_SETS = ["dev", "fresh"]  # dev = the 9 questions the fixes were found on; fresh = held out
SAVE_RESULTS = True    # append every run to RESULTS_TABLE
RESULTS_TABLE = "users.xiaobing_shang1_civ.aircarrier_delegation_eval_runs"
# Sealed held-out files (eval/delegation/round2/README.md and round3/README.md).
# Each SHA-256 was committed before any run; the notebook refuses any other file.
# h2 is public since its first run, so a run of it now is a post-fix re-run and
# analyze.py reports it apart. Leave QUESTION_FILES empty to run only dev and fresh.
ARTIFACTS = "/Volumes/users/xiaobing_shang1_civ/aircarrier_artifacts"
QUESTION_FILES = [f"{ARTIFACTS}/questions_h2.json", f"{ARTIFACTS}/questions_h3.json"]
SEALED_SHA256 = {
    "h2": "4a742955ff78983dd4f1eebe267ff06d45fce1c566c4c6211ac3e42ae281eee0",
    "h3": "0dc6bdf52665a101d79ebf85aba4126e95f7a3c246c17c3c601d9bcf04df5ec1",
}
VERIFY_SCHEMA = "users.xiaobing_shang1_civ"  # where the source tables for verify_sql live

import os
MCP_SERVERS_DIR = os.path.dirname(dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get())
MCP_SERVERS_DIR = "/Workspace" + MCP_SERVERS_DIR if not MCP_SERVERS_DIR.startswith("/Workspace") else MCP_SERVERS_DIR
print(MCP_SERVERS_DIR)

# COMMAND ----------

# DBTITLE 1,Load the three servers in-process
import sys, json, re, time
sys.path.insert(0, MCP_SERVERS_DIR)
import mcp_local
from fastmcp import Client

SCHEMAS, INSTR = {}, {}
for srv in ["docs", "analyst", "ops"]:
    entry = mcp_local.load(srv)
    INSTR[srv] = entry["mcp"].instructions or ""
    async def _list(e=entry):
        async with Client(e["mcp"]) as c:
            return await c.list_tools()
    for t in mcp_local._run_async(_list()):
        SCHEMAS[t.name] = (srv, t)

TOOL_SPECS = [{"type": "function", "function": {"name": n, "description": (t.description or "")[:4000],
               "parameters": t.inputSchema}} for n, (s, t) in SCHEMAS.items()]
print(len(SCHEMAS), "tools;", {s: sum(1 for v in SCHEMAS.values() if v[0] == s) for s in INSTR})
print("schema bytes:", len(json.dumps(TOOL_SPECS)))

# COMMAND ----------

# DBTITLE 1,Agent loop and grader
from types import SimpleNamespace as NS
from databricks.sdk import WorkspaceClient

W = WorkspaceClient()

BASE_SYSTEM = ("You are an assistant for a Navy cost analyst reconciling the CVN-79 (USS John F. Kennedy) program cost. "
               "Use the tools to answer. Be concise, give exact figures, and cite the source document/page or record for each figure.")
WITH_INSTR = BASE_SYSTEM + "\n\nConnected MCP servers and their instructions:\n" + "\n\n".join(f"[{k}] {v}" for k, v in INSTR.items())
SYSTEMS = {"no_instr": BASE_SYSTEM, "instr": WITH_INSTR}


def chat(model, messages):
    d = W.api_client.do("POST", f"/serving-endpoints/{model}/invocations",
                        body={"messages": messages, "tools": TOOL_SPECS, "max_tokens": 1500})
    m = d["choices"][0]["message"]
    content = m.get("content")
    if isinstance(content, list):
        content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
    calls = [NS(id=t["id"], name=t["function"]["name"], arguments=t["function"].get("arguments") or "{}")
             for t in (m.get("tool_calls") or [])]
    return content, calls, d.get("usage", {})


def run_agent(question, model, system):
    msgs = [{"role": "system", "content": system}, {"role": "user", "content": question}]
    trace, out_bytes, ptok, ctok, t0 = [], 0, 0, 0, time.time()
    for step in range(MAX_STEPS):
        content, calls, usage = chat(model, msgs)
        ptok += usage.get("prompt_tokens", 0); ctok += usage.get("completion_tokens", 0)
        if not calls:
            return dict(answer=content, trace=trace, out_bytes=out_bytes, ptok=ptok, ctok=ctok, secs=round(time.time() - t0, 1))
        msgs.append({"role": "assistant", "content": content or "",
                     "tool_calls": [{"id": c.id, "type": "function", "function": {"name": c.name, "arguments": c.arguments}} for c in calls]})
        for c in calls:
            try:
                args = json.loads(c.arguments)
            except ValueError:
                args = {}
            srv = SCHEMAS.get(c.name, (None,))[0]
            r = mcp_local.call(srv, c.name, **args) if srv else {"ok": False, "error": f"unknown tool {c.name}"}
            payload = json.dumps(r.get("result") if r.get("ok") else {"error": r.get("error")}, default=str)
            out_bytes += len(payload)
            trace.append(dict(tool=c.name, args=json.dumps(args)[:160], ok=r.get("ok"), bytes=len(payload)))
            msgs.append({"role": "tool", "tool_call_id": c.id, "content": payload[:MAX_TOOL_CHARS]})
    return dict(answer=None, trace=trace, out_bytes=out_bytes, ptok=ptok, ctok=ctok, secs=round(time.time() - t0, 1))


def grade(answer, patterns):
    return all(re.search(p, answer or "", re.I) for p in patterns)

# COMMAND ----------

# DBTITLE 1,Questions with SQL-verified answers
# Each question: id, text, regexes that must ALL match the answer. Ground truth was checked by SQL / the source PDF:
#  Q1 MSAR FY2027 PBv2 p.8: CLB $12.936B -> $13.529B     Q2 P00067 on N00024-15-C-2114, $454,765,071.00
#  Q3 11,651 claims in human_review                      Q4 N00024-09-C-2116 mod 0: $111,803,875.00 on 2009-01-15
#  Q5 N00024-16-C-2116 is CVN-80/81 DD&C, excluded       Q6 58 open gaps: 37 collection_required, 21 open_question
#  Q7 File C vs FPDS FY2021P03 gap $770,407,268.00       Q8 decoy: the LAB array is submarine sonar
#  Q9 CVN Refueling Overhauls = P-1 line item 2086
# Held-out set, written 2026-11-18 after the fixes and never used to change a tool:
#  F1 N00024-09-C-2116 FY2010: 28 actions, $211,984,118.00 (SQL sum of federal_action_obligation)
#  F2 8 work items owned by the reader agent           F3 decoy: NSBDF is for SSBN construction, not carriers
#  F4 SCN Book PB2024 P-5c p.73 (tie-out pass): FY 2013 ship (CVN 79) Total Ship Estimate $12,699.970M
#  F5 N00024-15-C-2114: prime_contract_for CVN-79, awarded_to HII Newport News Shipbuilding (CAGE 43689)
H = "[-\u2010\u2011\u2012\u2013 ]?"  # models print non-ASCII hyphens
QS = [
    ("Q1 baseline", "What is the current Cost Limitation Baseline for CVN 79 and what was it before? Cite the document and page.",
     [r"13[.,]529", r"12[.,]936", r"(p\.?|page)[\s:*]*8\b"]),
    ("Q2 GL line", "Our GL shows $454,765,071.00 with memo 'SCN progress CVN 79'. Which contract and modification is that, and does it belong to Kennedy?",
     [r"N00024" + H + "15" + H + "C" + H + "2114", r"P00067", r"(CVN" + H + "79|Kennedy)"]),
    ("Q3 review", "How many extracted claims are waiting for human review?", [r"11,?651"]),
    ("Q4 base award", "How much did the original award (modification 0) of N00024-09-C-2116 obligate, and on what date?",
     [r"111,?803,?875", r"(2009-01-15|January 15,? 2009|15 January 2009|01/15/2009|Jan\.? 15,? 2009)"]),
    ("Q5 exclusion", "Can I count obligations on contract N00024-16-C-2116 toward CVN 79's cost?",
     [r"\b(no|not|cannot|exclude)", r"CVN" + H + "8[01]"]),
    ("Q6 gaps", "How many open gaps are there, and how many need data collected versus further investigation?", [r"\b37\b", r"\b21\b"]),
    ("Q7 residual", "Why does File C for the Kennedy DD&C contract in FY2021 period 3 differ from FPDS obligations, and by how much?",
     [r"770,?407,?268"]),
    ("Q8 decoy", "How much did CVN 79 pay for its Large Aperture Bow array?", [r"submarine"]),
    ("Q9 line item", "Which P-1 line item number funds CVN refueling overhauls in the SCN budget books?", [r"\b2086\b"]),
    ("F1 FY10 total", "How many contract actions on N00024-09-C-2116 fall in fiscal year 2010, and what did they obligate in total?",
     [r"\b28\b", r"211,?984,?118"]),
    ("F2 reader", "How many work items does the reader agent own right now?", [r"\b8\b"]),
    ("F3 decoy", "How much NSBDF funding has gone to CVN 79?", [r"(SSBN|ballistic|submarine|Sea[- ]Based Deterrence)"]),
    ("F4 P-5c", "In the PB 2024 SCN justification book, what is the Total Ship Estimate for CVN 79 on the P-5c, and on which page?",
     [r"12,?699\.97", r"(p\.?|page)[\s:*]*73\b"]),
    ("F5 prime", "Who is the prime contractor on N00024-15-C-2114, and which hull is it for?",
     [r"(Newport News|Huntington|HII|43689)", r"CVN" + H + "79"]),
]
QUESTION_SET = {qid: ("fresh" if qid.startswith("F") else "dev") for qid, _, _ in QS}
QS = [x for x in QS if QUESTION_SET[x[0]] in QUESTION_SETS]

# Sealed sets: load each file, check its hash, then check its answer key
# against the warehouse. Any mismatch stops the notebook before a model is called.
import hashlib
for question_file in QUESTION_FILES:
    raw = open(question_file, "rb").read()
    got = hashlib.sha256(raw).hexdigest()
    sealed = json.loads(raw)
    assert got == SEALED_SHA256.get(sealed["question_set"]), f"{question_file} is not the sealed file (sha256 {got})"
    for item in sealed["questions"]:
        if item.get("verify_sql"):
            row = spark.sql(item["verify_sql"].format(schema=VERIFY_SCHEMA)).first().asDict()
            found = {k: str(row[k]) for k in item["expect"]}
            assert found == item["expect"], f"{item['qid']}: key {item['expect']} but warehouse says {found}"
        QS.append((item["qid"], item["question"], item["patterns"]))
        QUESTION_SET[item["qid"]] = sealed["question_set"]
    print("sealed file verified:", sealed["question_set"], got[:16], len(sealed["questions"]), "questions, key checked against SQL")
print(len(QS), "questions:", {s: sum(QUESTION_SET[q] == s for q, _, _ in QS) for s in sorted(set(QUESTION_SET[q] for q, _, _ in QS))})

# COMMAND ----------

# DBTITLE 1,Run every model, mode and question
import pandas as pd, hashlib, uuid, datetime

# Ties every saved row to the exact tool catalog and instructions it was run against.
RUN_ID = uuid.uuid4().hex[:12]
RUN_AT = datetime.datetime.now(datetime.timezone.utc)
CATALOG_SHA = hashlib.sha256(json.dumps(TOOL_SPECS, sort_keys=True).encode()).hexdigest()[:16]
INSTR_SHA = hashlib.sha256(json.dumps(INSTR, sort_keys=True).encode()).hexdigest()[:16]
print("run", RUN_ID, "catalog", CATALOG_SHA, "instructions", INSTR_SHA)

RUNS = []
for model in MODELS:
    for mode in MODES:
        for qid, q, pats in QS:
            try:
                r = run_agent(q, model, SYSTEMS[mode])
            except Exception as e:  # keep going: one endpoint error should not lose the whole run
                r = dict(answer=None, trace=[], out_bytes=0, ptok=0, ctok=0, secs=0, error=str(e)[:300])
            r.update(model=model, mode=mode, qid=qid, question=q, question_set=QUESTION_SET[qid],
                     passed=grade(r["answer"], pats))
            RUNS.append(r)
            print(f"{model:32} {mode:9} {qid:14} {'PASS' if r['passed'] else 'FAIL'}  calls={len(r['trace'])}  ptok={r['ptok']}  {r['secs']}s")

runs_df = pd.DataFrame([{k: v for k, v in r.items() if k not in ('trace', 'answer', 'question')} | {"calls": len(r["trace"])} for r in RUNS])

# COMMAND ----------

# DBTITLE 1,Save this run to Delta
from pyspark.sql import types as T

RESULT_SCHEMA = T.StructType([
    T.StructField("run_id", T.StringType(), False),
    T.StructField("run_at", T.TimestampType(), False),
    T.StructField("tool_catalog_sha", T.StringType(), False),
    T.StructField("instructions_sha", T.StringType(), False),
    T.StructField("model", T.StringType(), False),
    T.StructField("mode", T.StringType(), False),
    T.StructField("question_set", T.StringType(), False),
    T.StructField("qid", T.StringType(), False),
    T.StructField("question", T.StringType(), False),
    T.StructField("passed", T.BooleanType(), False),
    T.StructField("calls", T.IntegerType(), False),
    T.StructField("tool_output_bytes", T.LongType(), False),
    T.StructField("prompt_tokens", T.LongType(), False),
    T.StructField("completion_tokens", T.LongType(), False),
    T.StructField("seconds", T.DoubleType(), False),
    T.StructField("answer", T.StringType(), True),
    T.StructField("trace_json", T.StringType(), False),
    T.StructField("error", T.StringType(), True),
])

rows = [(RUN_ID, RUN_AT, CATALOG_SHA, INSTR_SHA, r["model"], r["mode"], r["question_set"], r["qid"], r["question"],
         bool(r["passed"]), len(r["trace"]), int(r["out_bytes"]), int(r["ptok"]), int(r["ctok"]), float(r["secs"]),
         r["answer"], json.dumps(r["trace"]), r.get("error")) for r in RUNS]

if SAVE_RESULTS and rows:
    spark.createDataFrame(rows, RESULT_SCHEMA).write.mode("append").saveAsTable(RESULTS_TABLE)
    saved = spark.sql(f"SELECT count(*) AS n FROM {RESULTS_TABLE} WHERE run_id = '{RUN_ID}'").first()["n"]
    print(f"saved {saved} of {len(rows)} rows for run {RUN_ID} to {RESULTS_TABLE}")
    assert saved == len(rows), "row count mismatch after append"
else:
    print("not saved (SAVE_RESULTS is False or no runs)")

# COMMAND ----------

# DBTITLE 1,Evaluation report: no-tool baseline and 3 repeats
# Adds the two things the evaluation template asks for:
#   * a no-tool baseline: the same model and system prompt with no tools attached,
#     which shows what the MCP servers add;
#   * repeats: every question 3 times per model, which shows consistency.
# Uses every question (dev Q1-Q9 and held-out F1-F5) and the no_instr prompt.
# Rows are appended to RESULTS_TABLE with mode = "no_tools" or "tools_rep<n>".
import time, json
import statistics, uuid, datetime, hashlib

REPEATS = 3
ALL_QS = [x for x in [*QS]]  # QS already filtered by QUESTION_SETS; set QUESTION_SETS = ["dev", "fresh"]


def run_no_tools(question, model, system):
    t0 = time.time()
    d = W.api_client.do("POST", f"/serving-endpoints/{model}/invocations",
                        body={"messages": [{"role": "system", "content": system},
                                           {"role": "user", "content": question}],
                              "max_tokens": 1500})
    m = d["choices"][0]["message"]
    content = m.get("content")
    if isinstance(content, list):
        content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
    u = d.get("usage", {})
    return dict(answer=content, trace=[], out_bytes=0, ptok=u.get("prompt_tokens", 0),
                ctok=u.get("completion_tokens", 0), secs=round(time.time() - t0, 1))


EVAL_RUN_ID = "rpt-" + uuid.uuid4().hex[:8]
EVAL_RUN_AT = datetime.datetime.now(datetime.timezone.utc)
EVAL = []
for model in MODELS:
    for qid, q, pats in ALL_QS:
        try:
            r = run_no_tools(q, model, BASE_SYSTEM)
        except Exception as e:
            r = dict(answer=None, trace=[], out_bytes=0, ptok=0, ctok=0, secs=0, error=str(e)[:300])
        r.update(model=model, mode="no_tools", qid=qid, question=q,
                 question_set=QUESTION_SET[qid], passed=grade(r["answer"], pats))
        EVAL.append(r)
        for rep in range(1, REPEATS + 1):
            try:
                r = run_agent(q, model, BASE_SYSTEM)
            except Exception as e:
                r = dict(answer=None, trace=[], out_bytes=0, ptok=0, ctok=0, secs=0, error=str(e)[:300])
            r.update(model=model, mode=f"tools_rep{rep}", qid=qid, question=q,
                     question_set=QUESTION_SET[qid], passed=grade(r["answer"], pats))
            EVAL.append(r)
        print(model, qid, "done")

if SAVE_RESULTS:
    rows = [(EVAL_RUN_ID, EVAL_RUN_AT, CATALOG_SHA, INSTR_SHA, r["model"], r["mode"], r["question_set"],
             r["qid"], r["question"], bool(r["passed"]), len(r["trace"]), int(r["out_bytes"]),
             int(r["ptok"]), int(r["ctok"]), float(r["secs"]), r["answer"], json.dumps(r["trace"]),
             r.get("error")) for r in EVAL]
    spark.createDataFrame(rows, RESULT_SCHEMA).write.mode("append").saveAsTable(RESULTS_TABLE)

# One plain-text summary to copy into the report.
print("\n=== EVAL REPORT SUMMARY", EVAL_RUN_ID, "catalog", CATALOG_SHA, "===")
for model in MODELS:
    for qset in ("dev", "fresh", "h2"):
        base = [r for r in EVAL if r["model"] == model and r["mode"] == "no_tools" and r["question_set"] == qset]
        tools = [r for r in EVAL if r["model"] == model and r["mode"].startswith("tools_rep") and r["question_set"] == qset]
        if not base:
            continue
        secs = [r["secs"] for r in tools if r["secs"]]
        calls = [len(r["trace"]) for r in tools]
        ptok = [r["ptok"] for r in tools]
        print(f"{model} | {qset} | baseline {sum(r['passed'] for r in base)}/{len(base)}"
              f" | tools {sum(r['passed'] for r in tools)}/{len(tools)}"
              f" | median {statistics.median(secs) if secs else 0}s, p90 {sorted(secs)[int(0.9*len(secs))-1] if secs else 0}s"
              f" | mean calls {round(statistics.mean(calls), 1) if calls else 0}"
              f" | mean prompt tokens {round(statistics.mean(ptok)) if ptok else 0}")
print("--- per question: passes out of", REPEATS, "(tools) and baseline pass")
for model in MODELS:
    for qid, _, _ in ALL_QS:
        reps = [r for r in EVAL if r["model"] == model and r["qid"] == qid and r["mode"].startswith("tools_rep")]
        base = next(r for r in EVAL if r["model"] == model and r["qid"] == qid and r["mode"] == "no_tools")
        print(f"{model} {qid}: tools {sum(r['passed'] for r in reps)}/{len(reps)}, baseline {'PASS' if base['passed'] else 'FAIL'}")
print("=== END ===")

# COMMAND ----------

# DBTITLE 1,Pass rate across saved runs
# Every saved run, newest first: compare a run against earlier ones and against tool catalog changes.
if spark.catalog.tableExists(RESULTS_TABLE):
    display(spark.sql(f"""
        SELECT run_id, min(run_at) AS run_at, tool_catalog_sha, model, mode, question_set,
               sum(CAST(passed AS INT)) AS passed, count(*) AS questions,
               sum(calls) AS calls, sum(prompt_tokens) AS prompt_tokens
        FROM {RESULTS_TABLE}
        GROUP BY run_id, tool_catalog_sha, model, mode, question_set
        ORDER BY run_at DESC, model, mode, question_set"""))

# COMMAND ----------

# DBTITLE 1,Summary by model, mode and question set
summary = (runs_df.groupby(["model", "mode", "question_set"])
           .agg(passed=("passed", "sum"), questions=("qid", "count"), calls=("calls", "sum"),
                tool_output_kb=("out_bytes", lambda s: round(s.sum() / 1000)), prompt_tokens=("ptok", "sum"),
                seconds=("secs", "sum"))
           .reset_index())
display(summary)
display(runs_df[["model", "mode", "question_set", "qid", "passed", "calls", "out_bytes", "ptok", "secs"]])

# COMMAND ----------

# DBTITLE 1,Inspect a run's tool calls and answer
def show(model, mode, qid, chars=1200):
    r = next(x for x in RUNS if (x["model"], x["mode"], x["qid"]) == (model, mode, qid))
    print(f"{model} {mode} {qid}: {'PASS' if r['passed'] else 'FAIL'}, prompt tokens {r['ptok']}")
    for t in r["trace"]:
        print("  ", t)
    print("ANSWER:", (r["answer"] or "<none>")[:chars])

# Every failure, then the most expensive run
for r in RUNS:
    if not r["passed"]:
        show(r["model"], r["mode"], r["qid"])
worst = max(RUNS, key=lambda x: x["ptok"])
show(worst["model"], worst["mode"], worst["qid"], 400)