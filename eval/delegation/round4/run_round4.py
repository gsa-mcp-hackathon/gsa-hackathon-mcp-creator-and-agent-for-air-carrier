"""Round 4 runner: the sealed question file, grader v2, every tool offered at once.

The agent loop, system prompt and limits are the ones in the notebook's evaluation
report cell (mcp-servers/Air Carrier Delegation Eval.py), so round 4 is comparable
with rounds 1-3. Three things change:

* questions come from questions_h4.json and the run refuses a file whose SHA-256
  differs from the hash committed in SEAL.md;
* answers are graded by grade.py (v2), and each run's checks are kept;
* runs execute in parallel threads (tools in-process through mcp_local, as before).

Modes: no_tools (same model and prompt, no tools) and tools_rep1..3.

The full run (552 calls) takes longer than one notebook/assistant command may run, so
every finished row is appended to a JSONL checkpoint at once. Calling run() again with
the same run_id skips the rows already done and returns them with the new ones, so a
timeout loses at most the runs in flight (the checkpoint is local to the session's
driver; a restarted session starts it again). Transient serving errors (429, 5xx,
timeouts) are retried with backoff; the attempt count is kept in each row.

In a Databricks session with fastmcp installed:

    import runpy
    r = runpy.run_path(".../eval/delegation/round4/run_round4.py")
    rows = r["run"](spark, repo_dir=".../gsa-hackathon-mcp-creator-and-agent-for-cvn",
                    run_id="r4-<id>", budget_s=420)   # repeat until "0 left"
    r["save"](spark, rows)                            # once, with every row
"""
from __future__ import annotations

import concurrent.futures as cf
import datetime
import hashlib
import importlib.util
import json
import os
import random
import sys
import threading
import time
import uuid

SEALED_SHA256 = {"h4": "f806640cb94139be5928a0be0a63096ba74f17cef9b8396b793a7534cdebf5a8"}
QUESTIONS = "/Volumes/users/xiaobing_shang1_civ/aircarrier_artifacts/questions_h4.json"
RESULTS_TABLE = "users.xiaobing_shang1_civ.aircarrier_delegation_eval_runs"
MODELS = ["databricks-claude-sonnet-4-5", "databricks-gpt-5-mini"]
REPEATS = 3
MAX_STEPS = 8           # tool-calling turns before the agent is cut off
MAX_TOOL_CHARS = 60000  # longest tool result passed back to the model
MAX_TOKENS = 1500
RETRIES = 5             # attempts per serving call on a transient error
CHECKPOINT_DIR = "/tmp/round4_checkpoints"
_TRANSIENT = ("429", "500", "502", "503", "504", "rate limit", "temporarily", "timed out", "timeout",
              "connection", "overloaded", "REQUEST_LIMIT_EXCEEDED", "TEMPORARILY_UNAVAILABLE")
BASE_SYSTEM = ("You are an assistant for a Navy cost analyst reconciling the CVN-79 (USS John F. Kennedy) program cost. "
               "Use the tools to answer. Be concise, give exact figures, and cite the source document/page or record for each figure.")


def load_questions(path: str = QUESTIONS) -> dict:
    blob = open(path, "rb").read()
    doc = json.loads(blob)
    sha = hashlib.sha256(blob).hexdigest()
    if SEALED_SHA256.get(doc.get("question_set")) != sha:
        raise RuntimeError(f"{path}: SHA-256 {sha} is not the sealed hash; refusing to run")
    return doc


def _grader(repo_dir: str):
    spec = importlib.util.spec_from_file_location("grade_v2", f"{repo_dir}/eval/delegation/round4/grade.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_tools(repo_dir: str):
    """The three servers in-process; tool specs exactly as the notebook builds them."""
    sys.path.insert(0, f"{repo_dir}/mcp-servers")
    import mcp_local
    from fastmcp import Client
    schemas, instr = {}, {}
    for srv in ("docs", "analyst", "ops"):
        entry = mcp_local.load(srv)
        instr[srv] = entry["mcp"].instructions or ""

        async def _list(e=entry):
            async with Client(e["mcp"]) as c:
                return await c.list_tools()
        for t in mcp_local._run_async(_list()):
            schemas[t.name] = (srv, t)
    specs = [{"type": "function", "function": {"name": n, "description": (t.description or "")[:4000],
                                               "parameters": t.inputSchema}} for n, (s, t) in schemas.items()]
    return mcp_local, schemas, instr, specs


def _content(m: dict) -> str | None:
    c = m.get("content")
    if isinstance(c, list):
        c = "".join(p.get("text", "") for p in c if isinstance(p, dict))
    return c


def _invoke(W, model: str, body: dict, stats: dict) -> dict:
    """One serving call, retried with jittered backoff on a transient error only."""
    for attempt in range(1, RETRIES + 1):
        try:
            return W.api_client.do("POST", f"/serving-endpoints/{model}/invocations", body=body)
        except Exception as e:
            msg = f"{type(e).__name__}: {e}"
            if attempt == RETRIES or not any(t.lower() in msg.lower() for t in _TRANSIENT):
                raise
            stats["retries"] = stats.get("retries", 0) + 1
            time.sleep(min(60, 2 ** attempt) + random.random())


def run_agent(W, mcp_local, schemas, specs, question: str, model: str) -> dict:
    msgs = [{"role": "system", "content": BASE_SYSTEM}, {"role": "user", "content": question}]
    trace, out_bytes, ptok, ctok, t0, stats = [], 0, 0, 0, time.time(), {}
    for _ in range(MAX_STEPS):
        d = _invoke(W, model, {"messages": msgs, "tools": specs, "max_tokens": MAX_TOKENS}, stats)
        m = d["choices"][0]["message"]
        u = d.get("usage", {})
        ptok += u.get("prompt_tokens", 0)
        ctok += u.get("completion_tokens", 0)
        calls = m.get("tool_calls") or []
        if not calls:
            return dict(answer=_content(m), trace=trace, out_bytes=out_bytes, ptok=ptok, ctok=ctok,
                        secs=round(time.time() - t0, 1), retries=stats.get("retries", 0))
        msgs.append({"role": "assistant", "content": _content(m) or "", "tool_calls": [
            {"id": c["id"], "type": "function", "function": {"name": c["function"]["name"],
                                                           "arguments": c["function"].get("arguments") or "{}"}}
            for c in calls]})
        for c in calls:
            name = c["function"]["name"]
            try:
                args = json.loads(c["function"].get("arguments") or "{}")
            except ValueError:
                args = {}
            srv = schemas.get(name, (None,))[0]
            if not isinstance(args, dict):  # a model can send a list or a scalar; the tool gets the error
                r = {"ok": False, "error": "tool arguments must be a JSON object"}
            elif not srv:
                r = {"ok": False, "error": f"unknown tool {name}"}
            else:
                try:
                    r = mcp_local.call(srv, name, **args)
                except Exception as e:  # e.g. an argument name that clashes with call()'s own
                    r = {"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}
            payload = json.dumps(r.get("result") if r.get("ok") else {"error": r.get("error")}, default=str)
            out_bytes += len(payload)
            trace.append(dict(tool=name, args=json.dumps(args)[:160], ok=r.get("ok"), bytes=len(payload)))
            msgs.append({"role": "tool", "tool_call_id": c["id"], "content": payload[:MAX_TOOL_CHARS]})
    return dict(answer=None, trace=trace, out_bytes=out_bytes, ptok=ptok, ctok=ctok, secs=round(time.time() - t0, 1),
                retries=stats.get("retries", 0), cutoff=f"no answer after {MAX_STEPS} tool turns")


def run_no_tools(W, question: str, model: str) -> dict:
    t0, stats = time.time(), {}
    d = _invoke(W, model, {"messages": [{"role": "system", "content": BASE_SYSTEM},
                                       {"role": "user", "content": question}], "max_tokens": MAX_TOKENS}, stats)
    u = d.get("usage", {})
    return dict(answer=_content(d["choices"][0]["message"]), trace=[], out_bytes=0, ptok=u.get("prompt_tokens", 0),
                ctok=u.get("completion_tokens", 0), secs=round(time.time() - t0, 1), retries=stats.get("retries", 0))


def checkpoint_path(run_id: str, directory: str = CHECKPOINT_DIR) -> str:
    return os.path.join(directory, f"{run_id}.jsonl")


def read_checkpoint(path: str) -> list[dict]:
    """Rows already finished; a half-written last line (killed mid-write) is ignored."""
    if not os.path.exists(path):
        return []
    out = []
    for line in open(path, encoding="utf-8"):
        try:
            r = json.loads(line)
        except ValueError:
            continue
        r["run_at"] = datetime.datetime.fromisoformat(r["run_at"])
        out.append(r)
    return out


def run(spark, repo_dir: str, questions_path: str = QUESTIONS, models=MODELS, repeats: int = REPEATS,
        workers: int = 8, only: list[str] | None = None, run_id: str | None = None,
        budget_s: float | None = None, checkpoint_dir: str = CHECKPOINT_DIR) -> list[dict]:
    """Every (model, mode, question). only: a list of qid prefixes, for a smoke test.

    Resumable: rows already in the run's checkpoint are skipped. budget_s stops
    starting new runs after that many seconds (runs in flight finish), so a caller
    with a time limit gets its rows back and calls run() again with the same run_id.
    Returns every row of the run so far (checkpoint included).
    """
    from databricks.sdk import WorkspaceClient
    W = WorkspaceClient()
    doc = load_questions(questions_path)
    G = _grader(repo_dir)
    mcp_local, schemas, instr, specs = load_tools(repo_dir)
    catalog = hashlib.sha256(json.dumps(specs, sort_keys=True).encode()).hexdigest()[:16]
    instr_sha = hashlib.sha256(json.dumps(instr, sort_keys=True).encode()).hexdigest()[:16]
    qs = [q for q in doc["questions"] if not only or any(q["qid"].startswith(p) for p in only)]
    run_id = run_id or "r4-" + uuid.uuid4().hex[:8]
    os.makedirs(checkpoint_dir, exist_ok=True)
    ckpt = checkpoint_path(run_id, checkpoint_dir)
    done = read_checkpoint(ckpt)
    have = {(r["model"], r["mode"], r["qid"]) for r in done}
    run_at = done[0]["run_at"] if done else datetime.datetime.now(datetime.timezone.utc)
    jobs = [(m, mode, q) for m in models for q in qs for mode in ["no_tools"] + [f"tools_rep{i}" for i in range(1, repeats + 1)]
            if (m, mode, q["qid"]) not in have]
    wlock = threading.Lock()

    def one(job):
        model, mode, q = job
        try:
            r = run_no_tools(W, q["question"], model) if mode == "no_tools" else \
                run_agent(W, mcp_local, schemas, specs, q["question"], model)
            err = None
        except Exception as e:  # recorded, not raised: one failed call must not stop the run
            r, err = dict(answer=None, trace=[], out_bytes=0, ptok=0, ctok=0, secs=0.0, retries=0), f"{type(e).__name__}: {e}"[:300]
        err = err or r.pop("cutoff", None)
        g = G.grade(r["answer"], q["expect"])
        row = dict(r, run_id=run_id, run_at=run_at, catalog=catalog, instr_sha=instr_sha, model=model, mode=mode,
                   qid=q["qid"], question=q["question"], set=q["set"], category=q["category"],
                   passed=g["passed"], checks=g["checks"], error=err)
        with wlock, open(ckpt, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, default=str) + "\n")
        return row

    print(f"run {run_id}: {len(jobs)} to do, {len(done)} already in {ckpt}, {len(qs)} questions, "
          f"{len(specs)} tools, catalog {catalog}")
    rows, t0 = list(done), time.time()
    ex = cf.ThreadPoolExecutor(workers)
    try:
        pending, it = set(), iter(jobs)
        while True:
            while len(pending) < workers and (budget_s is None or time.time() - t0 < budget_s):
                job = next(it, None)
                if job is None:
                    break
                pending.add(ex.submit(one, job))
            if not pending:
                break
            fin, pending = cf.wait(pending, return_when=cf.FIRST_COMPLETED)
            for fu in fin:
                rows.append(fu.result())
                n = len(rows) - len(done)
                if n % 25 == 0:
                    print(f"  {n}/{len(jobs)} new, {sum(r['passed'] for r in rows)} passed of {len(rows)}, "
                          f"{round(time.time() - t0)}s")
    finally:
        ex.shutdown(wait=True)
    left = len(jobs) - (len(rows) - len(done))
    print(f"run {run_id}: {len(rows)} rows, {left} left" + (" - call run() again with this run_id" if left else ""))
    return rows


def save(spark, rows: list[dict], table: str = RESULTS_TABLE) -> int:
    """Append to the runs table in its existing schema; trace_json keeps the calls and the grader's checks."""
    from pyspark.sql import types as T
    schema = T.StructType([T.StructField(n, t, nullable) for n, t, nullable in [
        ("run_id", T.StringType(), False), ("run_at", T.TimestampType(), False),
        ("tool_catalog_sha", T.StringType(), False), ("instructions_sha", T.StringType(), False),
        ("model", T.StringType(), False), ("mode", T.StringType(), False), ("question_set", T.StringType(), False),
        ("qid", T.StringType(), False), ("question", T.StringType(), False), ("passed", T.BooleanType(), False),
        ("calls", T.IntegerType(), False), ("tool_output_bytes", T.LongType(), False),
        ("prompt_tokens", T.LongType(), False), ("completion_tokens", T.LongType(), False),
        ("seconds", T.DoubleType(), False), ("answer", T.StringType(), True), ("trace_json", T.StringType(), False),
        ("error", T.StringType(), True)]])
    ids = sorted({r["run_id"] for r in rows})
    keys = [(r["run_id"], r["model"], r["mode"], r["qid"]) for r in rows]
    if len(set(keys)) != len(keys):
        raise RuntimeError("duplicate (run_id, model, mode, qid) rows; refusing to save")
    prior = spark.sql(f"SELECT count(*) n FROM {table} WHERE run_id IN ({', '.join(repr(i) for i in ids)})").first()["n"]
    if prior:
        raise RuntimeError(f"{prior} rows of {ids} are already saved; refusing to append twice")
    data = [(r["run_id"], r["run_at"], r["catalog"], r["instr_sha"], r["model"], r["mode"], f"h4-{r['set']}", r["qid"],
             r["question"], bool(r["passed"]), len(r["trace"]), int(r["out_bytes"]), int(r["ptok"]), int(r["ctok"]),
             float(r["secs"]), r["answer"], json.dumps({"calls": r["trace"], "checks": r["checks"], "retries": r.get("retries", 0)}), r["error"])
            for r in rows]
    spark.createDataFrame(data, schema).write.mode("append").saveAsTable(table)
    n = spark.sql(f"SELECT count(*) n FROM {table} WHERE run_id IN ({', '.join(repr(i) for i in ids)})").first()["n"]
    if n != len(rows):
        raise RuntimeError(f"saved {n} rows, expected {len(rows)}")
    return n
