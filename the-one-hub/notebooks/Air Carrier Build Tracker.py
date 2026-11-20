# Databricks notebook source
# DBTITLE 1,About this tracker
# MAGIC %md
# MAGIC # Air Carrier build tracker (live)
# MAGIC
# MAGIC This notebook checks the **actual** state of the CVN-79 Air Carrier build each time it runs. It looks at the app, the jobs, the agents, the UC volumes, the knowledge base, the test suites and the evidence. Each result is compared with what the handoff documents claim.
# MAGIC
# MAGIC * It is read-only against the build. Its only write is one append per run to `users.xiaobing_shang1_civ.aircarrier_build_tracker`, so the history builds up over time.
# MAGIC * Status values:
# MAGIC   * PASS: works as claimed.
# MAGIC   * WARN: expected gap or partial.
# MAGIC   * FAIL: broken, or contradicts a claim.
# MAGIC   * INFO: a count.
# MAGIC * Sources:
# MAGIC   * The bundle source in the Git folder at `gsa-hackathon-mcp-creator-and-agent-for-cvn/the-one-hub/ops-center` (GitHub main is the source of truth since 2026-11-20; the old `the-ops-center/.bundle/aircarrier/dev/files` copy was removed).
# MAGIC   * The volumes `aircarrier_artifacts` and `aircarrier_extracted`.
# MAGIC   * The app `aircarrier-front-center-dev`.
# MAGIC   * The 6 bundle jobs (tieout, ingest, events, dispatcher, rule eval, harness).

# COMMAND ----------

# DBTITLE 1,Install test-suite dependencies
# MAGIC %pip install -q fastapi==0.115.6 jinja2 httpx pyyaml pypdf
# MAGIC %restart_python

# COMMAND ----------

# DBTITLE 1,Config and helpers
import json, os, pathlib, shutil, subprocess, sys, datetime as dt
from collections import Counter
import pandas as pd
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
REPO = "/Workspace/Users/xiaobing.shang1.civ@mail.mil/gsa-hackathon-mcp-creator-and-agent-for-cvn"  # Git folder
FILES = f"{REPO}/the-one-hub/ops-center"
VOL = "/Volumes/users/xiaobing_shang1_civ/aircarrier_artifacts"
KB = "/Volumes/users/xiaobing_shang1_civ/aircarrier_extracted/kb"
APP = "aircarrier-front-center-dev"
JOBS = {"tieout": 23948629990745, "ingest": 869549480050872,
        "events": 1095446053930907, "dispatcher": 955907313845753,
        "rule_eval": 661637569762117, "harness": 926377078634937}
TRACKER = "users.xiaobing_shang1_civ.aircarrier_build_tracker"
BRIEF = dt.date(2026, 11, 18)   # PLAN.md: brief window 18-21 Nov 2026
RUN_TS = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)

rows = []
def add(area, check, status, observed, claimed="", action=""):
    rows.append(dict(area=area, check=check, status=status,
                     observed=str(observed), claimed=claimed, action=action))

def _rows(x):
    return x if isinstance(x, list) else x.get("rows", [])

# COMMAND ----------

# DBTITLE 1,App checks
a = w.apps.get(APP)
dep = a.active_deployment
add("app", "App compute and status",
    "PASS" if a.app_status.state.value == "RUNNING" and dep.status.state.value == "SUCCEEDED" else "FAIL",
    f"{a.app_status.state.value}; deployment {dep.deployment_id} {dep.status.state.value} at {dep.update_time}")

# Git-sourced deployments have no workspace snapshot (deployment_artifacts is None); the code is
# the resolved commit. Check the Git folder's app/ instead, and prove it equals that commit.
gs = dep.git_source
if gs and gs.resolved_commit:
    snap = f"{REPO}/{gs.source_code_path}"
    git = lambda *a: subprocess.run(["git", "-C", REPO, *a], capture_output=True, text=True)
    committed = git("diff", "--name-only", gs.resolved_commit, "HEAD", "--", gs.source_code_path)
    local = git("status", "--porcelain", "--", gs.source_code_path)
    if committed.returncode or local.returncode:
        status, obs = "WARN", f"git check failed: {(committed.stderr or local.stderr).strip()[:200]}"
    else:
        changed = committed.stdout.split() + local.stdout.splitlines()
        status = "PASS" if not changed else "WARN"
        obs = f"{gs.branch}@{gs.resolved_commit[:7]}; Git folder app/ " + ("identical" if not changed else f"differs: {changed[:5]}")
    add("app", "Deployed commit matches the Git folder app/", status, obs,
        "DEPLOYMENT.md: front center deploys from GitHub main",
        "" if status == "PASS" else "Commit/push, then redeploy with all 15 env_vars")
    ls = lambda p: [f"{p}/{n}" for n in os.listdir(p)]
elif dep.deployment_artifacts and dep.deployment_artifacts.source_code_path:
    snap = dep.deployment_artifacts.source_code_path
    ls = lambda p: [o.path for o in w.workspace.list(p)]
else:
    snap, ls = None, None
    add("app", "Deployed code location", "FAIL", "deployment has neither git_source nor a snapshot")

tpl = [p for p in ls(f"{snap}/templates") if p.endswith(".html")] if snap else []
add("app", "Templates present in the deployed snapshot", "PASS" if len(tpl) >= 18 else "FAIL",
    f"{len(tpl)} .html files in the snapshot",
    "APP-500-HANDOFF: TemplateNotFound on every page",
    "Open <app-url>/api/_diag in a browser to confirm the pages render")

top = sorted(pathlib.Path(p).name for p in ls(snap)) if snap else []
add("app", "Retrieval code shipped with the app (/api/search)", "PASS" if "_ops" in top else "FAIL",
    f"snapshot top level: {top}",
    "HANDOFF: /knowledge has live search with citations",
    "Vendor ops/ingest into app/_ops (as sync_core_to_app does for core) or move search into app/api")

try:
    eff = w.grants.get_effective(securable_type="volume",
                                 full_name="users.xiaobing_shang1_civ.aircarrier_extracted",
                                 principal=a.service_principal_client_id)
    privs = [p.privilege.value for pa in (eff.privilege_assignments or []) for p in (pa.privileges or [])]
except Exception as e:
    privs = [f"error {type(e).__name__}"]
# WARN, not FAIL: main._kb_dir() falls back to the index shipped in app/data/kb when the
# volume path is unreadable, so search still works, from an older build of the same corpus.
add("app", "App service principal can read the KB volume",
    "PASS" if {"READ_VOLUME", "ALL_PRIVILEGES"} & set(privs) else "WARN",
    f"effective privileges: {privs or 'none'}; app falls back to shipped data/kb",
    "app.yml sets AIRCARRIER_KB_DIR to the volume",
    "Add a volume resource (READ_VOLUME) in resources/app.yml; Apps have no /Volumes mount, so read it through the Files API")

# COMMAND ----------

# DBTITLE 1,Job checks
CLAIM = {"tieout": "HANDOFF/TRANSFER: implemented, scheduled daily 11:00 ET",
         "ingest": "on demand; builds the KB in the volume",
         "events": "PAUSED until the reader has a body",
         "dispatcher": "PAUSED until the dispatcher has a body",
         "rule_eval": "resources/jobs.yml: daily 12:00 ET (dev mode pauses it)",
         "harness": "resources/jobs.yml: daily 12:30 ET (dev mode pauses it)"}
for name, jid in JOBS.items():
    j = w.jobs.get(jid)
    sched = j.settings.schedule.pause_status.value if j.settings.schedule else "no schedule"
    runs = list(w.jobs.list_runs(job_id=jid, limit=10))
    if not runs:
        status = "WARN" if name in ("events", "dispatcher") else "FAIL"
        add("jobs", f"aircarrier_{name}", status, f"schedule {sched}; never run", CLAIM[name],
            "tieout: bundle dev mode pauses schedules; run it once, then unpause (or deploy -t il5/prod)" if name == "tieout" else "")
        continue
    r = runs[0]
    res = r.state.result_state.value if r.state.result_state else r.state.life_cycle_state.value
    when = dt.datetime.fromtimestamp(r.start_time / 1000, dt.timezone.utc).strftime("%Y-%m-%d %H:%MZ")
    err = ""
    if res != "SUCCESS":
        t = w.jobs.get_run(r.run_id).tasks[-1]
        err = (w.jobs.get_run_output(t.run_id).error or "").split("\n")[0]
    status = "PASS" if res == "SUCCESS" else "FAIL"
    action = ""
    if name == "tieout" and sched == "PAUSED" and status == "PASS":
        # The docs promise a daily run; a green manual run does not make that true.
        status, action = "WARN", "Unpause in resources/jobs.yml (dev mode pauses schedules) or deploy -t il5"
    if status == "FAIL" and "SystemExit: 0" in err:
        status, action = "WARN", "Work succeeded; the SystemExit(0) fix is in the code. Re-run the job to turn it green"
    add("jobs", f"aircarrier_{name}", status,
        f"schedule {sched}; {len(runs)} recent run(s); last {res} at {when} {err}", CLAIM[name], action)

# COMMAND ----------

# DBTITLE 1,Agent, data and register checks
g = _rows(json.load(open(f"{FILES}/app/data/gaps.json")))
v = _rows(json.load(open(f"{FILES}/app/data/variances.json")))

stubs = sorted(str(f.relative_to(FILES)) for f in pathlib.Path(FILES, "ops").rglob("*.py")
               if "raise NotImplementedError" in f.read_text())
agents = ["investigator", "reader", "tieout", "challenger", "attributor", "briefer"]
impl = [x for x in agents if f"ops/entrypoints/{x}_job.py" not in stubs]
add("ops", "Agent entry points with a body", "PASS" if len(impl) == 6 else "WARN",
    f"{len(impl)}/6 implemented {impl}; {len(stubs)} stub files",
    "README: iteration 1, bodies raise NotImplementedError; HANDOFF next step 4 = reader")

s = json.load(open(f"{KB}/summary.json"))
add("data", "Knowledge base index in the volume", "PASS" if s["chunks"] and not s["missing"] else "FAIL",
    f"{s['chunks']:,} chunks, {len(s['missing'])} missing, built {s['built_at']}", "HANDOFF: 2,732 chunks")

vm = json.load(open(f"{VOL}/MANIFEST.json")); wm = json.load(open(f"{FILES}/corpus/MANIFEST.json"))
miss = [r["filename"] for r in vm["rows"] if not os.path.exists(f"{VOL}/{r['artifact_id']}/{r['filename']}")]
# Superseded editions stay in the volume by design (content addressing), and are listed.
extra = ({d for d in os.listdir(VOL) if os.path.isdir(f"{VOL}/{d}")} - {r["artifact_id"] for r in vm["rows"]}
         - {s["artifact_id"] for s in vm.get("superseded", [])})
add("data", "Volume matches its MANIFEST.json", "PASS" if not miss and not extra else "FAIL",
    f"{len(vm['rows'])} rows, {len(miss)} missing files, {len(extra)} unlisted folders")
emb_miss = [r["filename"] for r in wm["rows"] if r["route"] == "embed"
            and not os.path.exists(f"{VOL}/{r['artifact_id']}/{r['filename']}")]
add("data", "Bundle manifest (what ingest reads) vs volume",
    "FAIL" if emb_miss else ("WARN" if len(wm["rows"]) != len(vm["rows"]) else "PASS"),
    f"bundle {len(wm['rows'])} rows vs volume {len(vm['rows'])}; embed docs missing {len(emb_miss)}",
    "", "Bring corpus/MANIFEST.json in the workspace into line with the volume (see Air Carrier Work Register Publish)")

# Which editions each index was built from. The app serves app/data/kb (it cannot read the
# volume), so if that index cites superseded editions the app quotes text that was corrected.
cur = {r["artifact_id"] for r in vm["rows"] if r["route"] == "embed"}
for label, kbdir in [("volume KB (agents, jobs)", KB), ("app-shipped KB (what the app serves)", f"{FILES}/app/data/kb")]:
    ids = {c["artifact_id"] for c in json.load(open(f"{kbdir}/chunks.json")).values()}
    stale = sorted(ids - cur)
    add("data", f"Index built from current editions: {label}", "PASS" if not stale else "WARN",
        f"{len(ids)} documents indexed; {len(stale)} superseded or unknown: {stale[:4]}", "",
        "" if not stale else ("Re-run aircarrier_ingest" if kbdir == KB else
         "Copy chunks.json, lexical.json and summary.json from the volume KB into app/data/kb, then redeploy, or grant the app the volume and read it through the Files API"))

import hashlib
def sha(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()
ring = [r for r in vm["rows"] if r["filename"] == "RING0_CVN79.md"]
if ring:
    same = sha(f"{FILES}/corpus/dossier/RING0_CVN79.md") == sha(f"{VOL}/{ring[0]['artifact_id']}/RING0_CVN79.md")
    add("data", "Dossier in the volume matches the workspace dossier", "PASS" if same else "WARN",
        "identical" if same else "workspace RING0 edited after the last upload, so the KB indexes the older text",
        "", "" if same else "Copy the workspace RING0 into the volume, then run the ingest job")


uc = {r.table_name for r in spark.sql("""SELECT table_name FROM users.information_schema.tables
         WHERE table_schema='xiaobing_shang1_civ' AND table_name LIKE 'aircarrier%'""").collect()}
# Which of the four architecture stores exist in UC. The work store is the gap and variance
# registers, published by the notebook "Air Carrier Work Register Publish".
stores = {"work": {"aircarrier_gaps", "aircarrier_variances"}, "source": {"aircarrier_sources"},
          "mechanism": {"aircarrier_mechanisms"}, "claim": {"aircarrier_claims"}}
have = [s for s, need in stores.items() if need <= uc]
add("data", "UC stores (work, source, mechanism, claim)", "PASS" if len(have) == 4 else "WARN",
    f"{len(have)}/4 in UC: {have}; app backend = files (JSON)",
    "ARCHITECTURE: four stores in UC; PLAN: event capture lands in Delta")

if stores["work"] <= uc:
    ug = spark.sql("SELECT id, status FROM users.xiaobing_shang1_civ.aircarrier_gaps").toPandas()
    uv = spark.sql("SELECT id, status FROM users.xiaobing_shang1_civ.aircarrier_variances").toPandas()
    same = (dict(zip(ug.id, ug.status)) == {x["id"]: x["status"] for x in g}
            and dict(zip(uv.id, uv.status)) == {x["id"]: x["status"] for x in v})
    add("data", "UC work store matches the register JSON", "PASS" if same else "FAIL",
        f"gaps {len(ug)} vs {len(g)}, variances {len(uv)} vs {len(v)}, statuses identical: {same}",
        "", "" if same else "Re-run the notebook Air Carrier Work Register Publish")

add("register", "Gap register", "INFO", f"{len(g)} gaps: {dict(Counter(x.get('status') for x in g))}")
add("register", "Variance register", "INFO", f"{len(v)} variances: {dict(Counter(x.get('status') for x in v))}")
add("plan", "Days to sponsor brief window (18-21 Nov 2026)", "INFO", f"{(BRIEF - dt.date.today()).days} days")

# COMMAND ----------

# DBTITLE 1,Test suites and tie-out, run from a temp copy
tmp = "/tmp/aircarrier_tracker"
shutil.rmtree(tmp, ignore_errors=True); shutil.copytree(FILES, tmp)
total_ok = total_fail = 0
for t in ["checks/test_gate.py", "checks/test_agents.py", "checks/test_app.py", "checks/test_serverless_entrypoints.py"]:
    p = subprocess.run([sys.executable, t], cwd=tmp, capture_output=True, text=True, timeout=600)
    out = p.stdout + p.stderr
    ok, bad = out.count("[ok"), out.lower().count("[fail")
    total_ok += ok; total_fail += bad
    add("tests", t, "PASS" if p.returncode == 0 and bad == 0 else "FAIL", f"rc={p.returncode}, {ok} ok, {bad} failed")
add("tests", "Total automated checks", "PASS" if total_fail == 0 else "FAIL",
    f"{total_ok} ok, {total_fail} failed", "HANDOFF: 77 checks pass (also says 73)")

p = subprocess.run([sys.executable, "ops/entrypoints/tieout_job.py", "--root", tmp], cwd=tmp,
                   capture_output=True, text=True, timeout=600)
add("tests", "Tie-out against the current tables", "PASS" if p.returncode == 0 else "FAIL",
    p.stdout.strip().splitlines()[-1] if p.stdout.strip() else p.stderr[-300:])

# Simulate the Apps container, which receives only app/
apponly = "/tmp/aircarrier_apponly"
shutil.rmtree(apponly, ignore_errors=True); shutil.copytree(f"{FILES}/app", apponly)
probe = ("from fastapi.testclient import TestClient; import main, json; c=TestClient(main.app); "
         "codes={p: c.get(p).status_code for p in ['/','/dashboard','/gaps','/knowledge','/variances','/delivery']}; "
         "r=c.get('/api/search', params={'q':'cost cap'}).json(); print(json.dumps({'codes':codes,'hits':r.get('count'),'error':r.get('error')}))")
p = subprocess.run([sys.executable, "-c", probe], cwd=apponly, capture_output=True, text=True, timeout=300)
res = json.loads(p.stdout.strip().splitlines()[-1])
add("tests", "Pages render in the app-only (deployed) layout",
    "PASS" if all(c == 200 for c in res["codes"].values()) else "FAIL", res["codes"])
add("tests", "Search works in the app-only (deployed) layout", "PASS" if res["hits"] else "FAIL",
    f"hits={res['hits']}; {res['error']}", "", "" if res["hits"] else "Run tools/sync_core_to_app.py so app/_ops exists")

# The vendored retrieval must rank exactly like the original, or the app and the agents
# cite different pages for the same question.
Q = ["cost cap", "N00024-09-C-2116", "SCN completion of prior year", "EMALS", "advance procurement CVN 79", "P-5c"]
probe = ("import sys, json, pathlib; sys.path.insert(0, sys.argv[1]); "
         "from ops.ingest.search import KnowledgeBase; kb = KnowledgeBase(pathlib.Path(sys.argv[2])); "
         f"print(json.dumps({{q: [h['chunk_id'] for h in kb.search(q, k=10)] for q in {Q!r}}}))")
tops = {}
for name, root in {"original": FILES, "vendored": f"{FILES}/app/_ops"}.items():
    p = subprocess.run([sys.executable, "-c", probe, root, KB], capture_output=True, text=True, timeout=300)
    tops[name] = json.loads(p.stdout.strip().splitlines()[-1]) if p.returncode == 0 else None
add("tests", "Vendored retrieval ranks identically to ops/ingest",
    "PASS" if tops["vendored"] and tops["original"] == tops["vendored"] else "FAIL",
    f"{len(Q)} queries, top-10 identical: {tops['original'] == tops['vendored']}")

# The sync tool is what keeps app/_ops alive across a bundle deploy from the laptop.
p = subprocess.run([sys.executable, "tools/sync_core_to_app.py"], cwd=tmp, capture_output=True, text=True)
made = sorted(str(x.relative_to(tmp)) for x in pathlib.Path(tmp, "app/_ops").rglob("*.py"))
add("tests", "sync_core_to_app vendors core and retrieval", "PASS" if p.returncode == 0 and len(made) == 4 else "FAIL",
    f"rc={p.returncode}; {made}")

# COMMAND ----------

# DBTITLE 1,Evidence re-check: obligations by contract (E-14, E-16)
def fao_sum(path):
    d = pd.read_csv(path, dtype=str, low_memory=False)
    return d.award_id_piid.iloc[0], pd.to_numeric(d.federal_action_obligation, errors="coerce").sum()

piid_a, cp = fao_sum(f"{VOL}/cf1037ec4fc2cbbd/Contracts_PrimeTransactions_2026-11-08_H03M58S53_1.csv")
piid_b, ddc = fao_sum(f"{VOL}/5e11a9f653f60044/Contract_N0002415C2114_TransactionHistory_1.csv")
att = {c["label"]: c["usd_m"] for c in json.load(open(f"{FILES}/app/data/attribution.json"))["components"]}
add("evidence", "Attribution ties to USAspending transactions",
    "PASS" if abs(att.get("CP contract N00024-09-C-2116", 0) - cp / 1e6) < 0.05
           and abs(att.get("DD&C contract N00024-15-C-2114", 0) - ddc / 1e6) < 0.05 else "FAIL",
    f"{piid_a} ${cp:,.2f}; {piid_b} ${ddc:,.2f}")
# E-16: recompute the resolution from the transactions instead of trusting the register text.
# The FPDS figure must equal the 09-C-2116 running total at one as-of date, and the register
# must name that contract and carry a status that matches the evidence.
FPDS_E16 = 4518716360.83
d16 = pd.read_csv(f"{VOL}/cf1037ec4fc2cbbd/Contracts_PrimeTransactions_2026-11-08_H03M58S53_1.csv", dtype=str, low_memory=False)
d16["fao"] = pd.to_numeric(d16.federal_action_obligation, errors="coerce")
cum = d16.groupby("action_date").fao.sum().sort_index().cumsum()
asof = list(cum[(cum - FPDS_E16).abs() < 0.005].index)
var16 = ([x for x in v if x.get("id") == "E-16"] or [{}])[0]
txt = var16.get("detail", "")
ok16 = bool(asof) and "N00024-09-C-2116" in txt and var16.get("status") == "resolved"
add("evidence", "E-16 resolution reproduces from the transactions", "PASS" if ok16 else "FAIL",
    f"{piid_a} running total equals the FPDS ${FPDS_E16:,.2f} at {asof or 'no date'}; "
    f"later actions {cp - FPDS_E16:,.2f}; register status {var16.get('status')}, names 09-C-2116: {'N00024-09-C-2116' in txt}",
    "E-16: as-of date on N00024-09-C-2116 (corrected 2026-11-08; it was labelled DD&C)",
    "" if ok16 else "Register text and transactions disagree. Re-open E-16")

# COMMAND ----------

# DBTITLE 1,Scorecard and history write
df = pd.DataFrame(rows)
df.insert(0, "run_ts", RUN_TS)
sdf = spark.createDataFrame(df.astype({c: str for c in df.columns if c != "run_ts"}))
sdf.write.mode("append").option("mergeSchema", "true").saveAsTable(TRACKER)
print(dict(Counter(df.status)))
order = {"FAIL": 0, "WARN": 1, "PASS": 2, "INFO": 3}
display(df.assign(_o=df.status.map(order)).sort_values(["_o", "area"]).drop(columns="_o"))

# COMMAND ----------

# DBTITLE 1,Trend across runs
# MAGIC %sql
# MAGIC SELECT run_ts,
# MAGIC        count_if(status = 'PASS') AS pass,
# MAGIC        count_if(status = 'WARN') AS warn,
# MAGIC        count_if(status = 'FAIL') AS fail,
# MAGIC        concat_ws('; ', collect_list(CASE WHEN status = 'FAIL' THEN `check` END)) AS failing
# MAGIC FROM users.xiaobing_shang1_civ.aircarrier_build_tracker
# MAGIC GROUP BY run_ts
# MAGIC ORDER BY run_ts DESC