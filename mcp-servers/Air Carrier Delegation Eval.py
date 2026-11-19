# Databricks notebook source
# DBTITLE 1,About this eval
# MAGIC %md
# MAGIC # Air Carrier MCP delegation eval
# MAGIC
# MAGIC Tests whether an LLM agent, handed all 29 tools from **mcp-aircarrier-docs**, **mcp-aircarrier-analyst** and **mcp-aircarrier-ops**, picks the right tools and returns the right answer.
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
print(len(QS), "questions:", {s: sum(QUESTION_SET[q] == s for q, _, _ in QS) for s in QUESTION_SETS})

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

import base64; exec(base64.b64decode("aW1wb3J0IHRpbWUsIGpzb24KIyBEQlRJVExFIDEsRXZhbHVhdGlvbiByZXBvcnQ6IG5vLXRvb2wgYmFzZWxpbmUgYW5kIDMgcmVwZWF0cyAocGFzdGUgYWZ0ZXIgIlNhdmUgdGhpcyBydW4gdG8gRGVsdGEiLCBjZWxsIDgpCiMgQWRkcyB0aGUgdHdvIHRoaW5ncyB0aGUgZXZhbHVhdGlvbiB0ZW1wbGF0ZSBhc2tzIGZvcjoKIyAgICogYSBuby10b29sIGJhc2VsaW5lOiB0aGUgc2FtZSBtb2RlbCBhbmQgc3lzdGVtIHByb21wdCB3aXRoIG5vIHRvb2xzIGF0dGFjaGVkLAojICAgICB3aGljaCBzaG93cyB3aGF0IHRoZSBNQ1Agc2VydmVycyBhZGQ7CiMgICAqIHJlcGVhdHM6IGV2ZXJ5IHF1ZXN0aW9uIDMgdGltZXMgcGVyIG1vZGVsLCB3aGljaCBzaG93cyBjb25zaXN0ZW5jeS4KIyBVc2VzIGV2ZXJ5IHF1ZXN0aW9uIChkZXYgUTEtUTkgYW5kIGhlbGQtb3V0IEYxLUY1KSBhbmQgdGhlIG5vX2luc3RyIHByb21wdC4KIyBSb3dzIGFyZSBhcHBlbmRlZCB0byBSRVNVTFRTX1RBQkxFIHdpdGggbW9kZSA9ICJub190b29scyIgb3IgInRvb2xzX3JlcDxuPiIuCmltcG9ydCBzdGF0aXN0aWNzLCB1dWlkLCBkYXRldGltZSwgaGFzaGxpYgoKUkVQRUFUUyA9IDMKQUxMX1FTID0gW3ggZm9yIHggaW4gWypRU11dICAjIFFTIGFscmVhZHkgZmlsdGVyZWQgYnkgUVVFU1RJT05fU0VUUzsgc2V0IFFVRVNUSU9OX1NFVFMgPSBbImRldiIsICJmcmVzaCJdCgoKZGVmIHJ1bl9ub190b29scyhxdWVzdGlvbiwgbW9kZWwsIHN5c3RlbSk6CiAgICB0MCA9IHRpbWUudGltZSgpCiAgICBkID0gVy5hcGlfY2xpZW50LmRvKCJQT1NUIiwgZiIvc2VydmluZy1lbmRwb2ludHMve21vZGVsfS9pbnZvY2F0aW9ucyIsCiAgICAgICAgICAgICAgICAgICAgICAgIGJvZHk9eyJtZXNzYWdlcyI6IFt7InJvbGUiOiAic3lzdGVtIiwgImNvbnRlbnQiOiBzeXN0ZW19LAogICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgeyJyb2xlIjogInVzZXIiLCAiY29udGVudCI6IHF1ZXN0aW9ufV0sCiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICJtYXhfdG9rZW5zIjogMTUwMH0pCiAgICBtID0gZFsiY2hvaWNlcyJdWzBdWyJtZXNzYWdlIl0KICAgIGNvbnRlbnQgPSBtLmdldCgiY29udGVudCIpCiAgICBpZiBpc2luc3RhbmNlKGNvbnRlbnQsIGxpc3QpOgogICAgICAgIGNvbnRlbnQgPSAiIi5qb2luKHAuZ2V0KCJ0ZXh0IiwgIiIpIGZvciBwIGluIGNvbnRlbnQgaWYgaXNpbnN0YW5jZShwLCBkaWN0KSkKICAgIHUgPSBkLmdldCgidXNhZ2UiLCB7fSkKICAgIHJldHVybiBkaWN0KGFuc3dlcj1jb250ZW50LCB0cmFjZT1bXSwgb3V0X2J5dGVzPTAsIHB0b2s9dS5nZXQoInByb21wdF90b2tlbnMiLCAwKSwKICAgICAgICAgICAgICAgIGN0b2s9dS5nZXQoImNvbXBsZXRpb25fdG9rZW5zIiwgMCksIHNlY3M9cm91bmQodGltZS50aW1lKCkgLSB0MCwgMSkpCgoKRVZBTF9SVU5fSUQgPSAicnB0LSIgKyB1dWlkLnV1aWQ0KCkuaGV4Wzo4XQpFVkFMX1JVTl9BVCA9IGRhdGV0aW1lLmRhdGV0aW1lLm5vdyhkYXRldGltZS50aW1lem9uZS51dGMpCkVWQUwgPSBbXQpmb3IgbW9kZWwgaW4gTU9ERUxTOgogICAgZm9yIHFpZCwgcSwgcGF0cyBpbiBBTExfUVM6CiAgICAgICAgdHJ5OgogICAgICAgICAgICByID0gcnVuX25vX3Rvb2xzKHEsIG1vZGVsLCBCQVNFX1NZU1RFTSkKICAgICAgICBleGNlcHQgRXhjZXB0aW9uIGFzIGU6CiAgICAgICAgICAgIHIgPSBkaWN0KGFuc3dlcj1Ob25lLCB0cmFjZT1bXSwgb3V0X2J5dGVzPTAsIHB0b2s9MCwgY3Rvaz0wLCBzZWNzPTAsIGVycm9yPXN0cihlKVs6MzAwXSkKICAgICAgICByLnVwZGF0ZShtb2RlbD1tb2RlbCwgbW9kZT0ibm9fdG9vbHMiLCBxaWQ9cWlkLCBxdWVzdGlvbj1xLAogICAgICAgICAgICAgICAgIHF1ZXN0aW9uX3NldD1RVUVTVElPTl9TRVRbcWlkXSwgcGFzc2VkPWdyYWRlKHJbImFuc3dlciJdLCBwYXRzKSkKICAgICAgICBFVkFMLmFwcGVuZChyKQogICAgICAgIGZvciByZXAgaW4gcmFuZ2UoMSwgUkVQRUFUUyArIDEpOgogICAgICAgICAgICB0cnk6CiAgICAgICAgICAgICAgICByID0gcnVuX2FnZW50KHEsIG1vZGVsLCBCQVNFX1NZU1RFTSkKICAgICAgICAgICAgZXhjZXB0IEV4Y2VwdGlvbiBhcyBlOgogICAgICAgICAgICAgICAgciA9IGRpY3QoYW5zd2VyPU5vbmUsIHRyYWNlPVtdLCBvdXRfYnl0ZXM9MCwgcHRvaz0wLCBjdG9rPTAsIHNlY3M9MCwgZXJyb3I9c3RyKGUpWzozMDBdKQogICAgICAgICAgICByLnVwZGF0ZShtb2RlbD1tb2RlbCwgbW9kZT1mInRvb2xzX3JlcHtyZXB9IiwgcWlkPXFpZCwgcXVlc3Rpb249cSwKICAgICAgICAgICAgICAgICAgICAgcXVlc3Rpb25fc2V0PVFVRVNUSU9OX1NFVFtxaWRdLCBwYXNzZWQ9Z3JhZGUoclsiYW5zd2VyIl0sIHBhdHMpKQogICAgICAgICAgICBFVkFMLmFwcGVuZChyKQogICAgICAgIHByaW50KG1vZGVsLCBxaWQsICJkb25lIikKCmlmIFNBVkVfUkVTVUxUUzoKICAgIHJvd3MgPSBbKEVWQUxfUlVOX0lELCBFVkFMX1JVTl9BVCwgQ0FUQUxPR19TSEEsIElOU1RSX1NIQSwgclsibW9kZWwiXSwgclsibW9kZSJdLCByWyJxdWVzdGlvbl9zZXQiXSwKICAgICAgICAgICAgIHJbInFpZCJdLCByWyJxdWVzdGlvbiJdLCBib29sKHJbInBhc3NlZCJdKSwgbGVuKHJbInRyYWNlIl0pLCBpbnQoclsib3V0X2J5dGVzIl0pLAogICAgICAgICAgICAgaW50KHJbInB0b2siXSksIGludChyWyJjdG9rIl0pLCBmbG9hdChyWyJzZWNzIl0pLCByWyJhbnN3ZXIiXSwganNvbi5kdW1wcyhyWyJ0cmFjZSJdKSwKICAgICAgICAgICAgIHIuZ2V0KCJlcnJvciIpKSBmb3IgciBpbiBFVkFMXQogICAgc3BhcmsuY3JlYXRlRGF0YUZyYW1lKHJvd3MsIFJFU1VMVF9TQ0hFTUEpLndyaXRlLm1vZGUoImFwcGVuZCIpLnNhdmVBc1RhYmxlKFJFU1VMVFNfVEFCTEUpCgojIE9uZSBwbGFpbi10ZXh0IHN1bW1hcnkgdG8gY29weSBpbnRvIHRoZSByZXBvcnQuCnByaW50KCJcbj09PSBFVkFMIFJFUE9SVCBTVU1NQVJZIiwgRVZBTF9SVU5fSUQsICJjYXRhbG9nIiwgQ0FUQUxPR19TSEEsICI9PT0iKQpmb3IgbW9kZWwgaW4gTU9ERUxTOgogICAgZm9yIHFzZXQgaW4gKCJkZXYiLCAiZnJlc2giKToKICAgICAgICBiYXNlID0gW3IgZm9yIHIgaW4gRVZBTCBpZiByWyJtb2RlbCJdID09IG1vZGVsIGFuZCByWyJtb2RlIl0gPT0gIm5vX3Rvb2xzIiBhbmQgclsicXVlc3Rpb25fc2V0Il0gPT0gcXNldF0KICAgICAgICB0b29scyA9IFtyIGZvciByIGluIEVWQUwgaWYgclsibW9kZWwiXSA9PSBtb2RlbCBhbmQgclsibW9kZSJdLnN0YXJ0c3dpdGgoInRvb2xzX3JlcCIpIGFuZCByWyJxdWVzdGlvbl9zZXQiXSA9PSBxc2V0XQogICAgICAgIGlmIG5vdCBiYXNlOgogICAgICAgICAgICBjb250aW51ZQogICAgICAgIHNlY3MgPSBbclsic2VjcyJdIGZvciByIGluIHRvb2xzIGlmIHJbInNlY3MiXV0KICAgICAgICBjYWxscyA9IFtsZW4oclsidHJhY2UiXSkgZm9yIHIgaW4gdG9vbHNdCiAgICAgICAgcHRvayA9IFtyWyJwdG9rIl0gZm9yIHIgaW4gdG9vbHNdCiAgICAgICAgcHJpbnQoZiJ7bW9kZWx9IHwge3FzZXR9IHwgYmFzZWxpbmUge3N1bShyWydwYXNzZWQnXSBmb3IgciBpbiBiYXNlKX0ve2xlbihiYXNlKX0iCiAgICAgICAgICAgICAgZiIgfCB0b29scyB7c3VtKHJbJ3Bhc3NlZCddIGZvciByIGluIHRvb2xzKX0ve2xlbih0b29scyl9IgogICAgICAgICAgICAgIGYiIHwgbWVkaWFuIHtzdGF0aXN0aWNzLm1lZGlhbihzZWNzKSBpZiBzZWNzIGVsc2UgMH1zLCBwOTAge3NvcnRlZChzZWNzKVtpbnQoMC45KmxlbihzZWNzKSktMV0gaWYgc2VjcyBlbHNlIDB9cyIKICAgICAgICAgICAgICBmIiB8IG1lYW4gY2FsbHMge3JvdW5kKHN0YXRpc3RpY3MubWVhbihjYWxscyksIDEpIGlmIGNhbGxzIGVsc2UgMH0iCiAgICAgICAgICAgICAgZiIgfCBtZWFuIHByb21wdCB0b2tlbnMge3JvdW5kKHN0YXRpc3RpY3MubWVhbihwdG9rKSkgaWYgcHRvayBlbHNlIDB9IikKcHJpbnQoIi0tLSBwZXIgcXVlc3Rpb246IHBhc3NlcyBvdXQgb2YiLCBSRVBFQVRTLCAiKHRvb2xzKSBhbmQgYmFzZWxpbmUgcGFzcyIpCmZvciBtb2RlbCBpbiBNT0RFTFM6CiAgICBmb3IgcWlkLCBfLCBfIGluIEFMTF9RUzoKICAgICAgICByZXBzID0gW3IgZm9yIHIgaW4gRVZBTCBpZiByWyJtb2RlbCJdID09IG1vZGVsIGFuZCByWyJxaWQiXSA9PSBxaWQgYW5kIHJbIm1vZGUiXS5zdGFydHN3aXRoKCJ0b29sc19yZXAiKV0KICAgICAgICBiYXNlID0gbmV4dChyIGZvciByIGluIEVWQUwgaWYgclsibW9kZWwiXSA9PSBtb2RlbCBhbmQgclsicWlkIl0gPT0gcWlkIGFuZCByWyJtb2RlIl0gPT0gIm5vX3Rvb2xzIikKICAgICAgICBwcmludChmInttb2RlbH0ge3FpZH06IHRvb2xzIHtzdW0oclsncGFzc2VkJ10gZm9yIHIgaW4gcmVwcyl9L3tsZW4ocmVwcyl9LCBiYXNlbGluZSB7J1BBU1MnIGlmIGJhc2VbJ3Bhc3NlZCddIGVsc2UgJ0ZBSUwnfSIpCnByaW50KCI9PT0gRU5EID09PSIpCg==").decode())

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