# Databricks notebook source
# DBTITLE 1,About
# MAGIC %md
# MAGIC # Publish the work register to Unity Catalog
# MAGIC
# MAGIC This notebook copies the gap and variance registers from the bundle's `app/data` JSON into Delta. It adds the serving views that `app/api/data.py` already names for its `uc` backend, plus one funnel view that agents read as their work queue.
# MAGIC
# MAGIC * **Source of truth is unchanged.** The data still comes from `etl/build_data.py` into `app/data/*.json`. This notebook only mirrors it, overwriting each run, so it can never become a second copy that drifts.
# MAGIC * **What gets written** in `users.xiaobing_shang1_civ`:
# MAGIC   * Base tables `aircarrier_gaps` and `aircarrier_variances`.
# MAGIC   * Views `aircarrier_v_gaps` and `aircarrier_v_variances`, the names the `uc` backend expects.
# MAGIC   * View `aircarrier_v_work_queue`: open gaps ranked by priority. It is the funnel, the unsolved items in the order to work them.
# MAGIC * **Writes:** only these five objects.
# MAGIC * **Run it** after each ETL build. Later it can move into the bundle as a job task.

# COMMAND ----------

# DBTITLE 1,Load registers from the bundle
import json, datetime as dt
import pandas as pd

FILES = "/Workspace/Users/xiaobing.shang1.civ@mail.mil/gsa-hackathon-mcp-creator-and-agent-for-cvn/the-one-hub/ops-center"
NS = "users.xiaobing_shang1_civ"
NOW = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)

def load(name):
    j = json.load(open(f"{FILES}/app/data/{name}.json"))
    rows = j["rows"]
    df = pd.DataFrame(rows)
    # Nested values (lists, dicts) become JSON text so the table schema stays flat and stable.
    for c in df.columns:
        if df[c].map(lambda x: isinstance(x, (list, dict))).any():
            df[c] = df[c].map(lambda x: json.dumps(x) if isinstance(x, (list, dict)) else x)
    df["_source"] = f"app/data/{name}.json ({j.get('source', '')})"
    df["_published_at"] = NOW
    return df, len(rows)

gaps, n_g = load("gaps")
var, n_v = load("variances")
print(n_g, "gaps,", n_v, "variances")
print("gap columns:", list(gaps.columns))
print("variance columns:", list(var.columns))

# COMMAND ----------

# DBTITLE 1,Write base tables and views
for name, df in [("gaps", gaps), ("variances", var)]:
    sdf = spark.createDataFrame(df.astype({c: "string" for c in df.columns
                                           if df[c].dtype == object}))
    sdf.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{NS}.aircarrier_{name}")
    spark.sql(f"CREATE OR REPLACE VIEW {NS}.aircarrier_v_{name} AS SELECT * FROM {NS}.aircarrier_{name}")

spark.sql(f"COMMENT ON TABLE {NS}.aircarrier_gaps IS 'Air Carrier gap register G1-G28. Mirror of app/data/gaps.json; overwrite on publish. Do not edit here.'")
spark.sql(f"COMMENT ON TABLE {NS}.aircarrier_variances IS 'Air Carrier variance register E-1-E-16. Mirror of app/data/variances.json; overwrite on publish. Do not edit here.'")

# The funnel: open gaps only, in the order an agent should take them. Closability first is
# the cheapest-first rule from the investigate skill. Priority comes from the register itself.
spark.sql(f"""
CREATE OR REPLACE VIEW {NS}.aircarrier_v_work_queue
COMMENT 'Open gaps ranked for work: register priority, then exposure. Read-only queue for agents.'
AS SELECT id, title, status, closability, executor, CAST(priority AS DOUBLE) AS priority,
          CAST(exposure_usd_m AS DOUBLE) AS exposure_usd_m, CAST(ignorance AS DOUBLE) AS ignorance,
          closability IN ('zero_access', 'query') AS free_now,
          row_number() OVER (ORDER BY CAST(priority AS DOUBLE) DESC, CAST(exposure_usd_m AS DOUBLE) DESC, id) AS queue_rank
FROM {NS}.aircarrier_gaps
WHERE NOT CAST(closed AS BOOLEAN)
""")
print("written")

# COMMAND ----------

# DBTITLE 1,Verify against the source JSON
checks = []
for name, n in [("gaps", n_g), ("variances", n_v)]:
    t = spark.table(f"{NS}.aircarrier_{name}").count()
    vw = spark.table(f"{NS}.aircarrier_v_{name}").count()
    checks.append((f"{name} rows", n, t, vw, n == t == vw))

src_status = json.load(open(f"{FILES}/app/data/gaps.json"))["rows"]
open_src = sorted(r["id"] for r in src_status if not r["closed"])
q = spark.table(f"{NS}.aircarrier_v_work_queue").orderBy("queue_rank").toPandas()
checks.append(("work queue = open gaps", len(open_src), len(q), None, sorted(q.id) == open_src))
vs = spark.sql(f"SELECT status FROM {NS}.aircarrier_variances WHERE id = 'E-16'").first()
checks.append(("E-16 status in UC", "resolved", vs.status, None, vs.status == "resolved"))
for c in checks:
    print(("PASS " if c[-1] else "FAIL ") + str(c[:-1]))
display(q.head(10))

# COMMAND ----------

# DBTITLE 1,Inspect corpus drift: workspace vs volume
import hashlib, os, subprocess
VOL = "/Volumes/users/xiaobing_shang1_civ/aircarrier_artifacts"
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
vm = json.load(open(f"{VOL}/MANIFEST.json"))
print("manifest row keys:", list(vm["rows"][0]))
# Which corpus files differ between the workspace (source of truth) and the volume (what ingest reads)?
drift = []
for r in vm["rows"]:
    for sub in ("dossier", "durable"):
        ws = f"{FILES}/corpus/{sub}/{r['filename']}"
        if os.path.exists(ws):
            vp = f"{VOL}/{r['artifact_id']}/{r['filename']}"
            if sha(ws) != sha(vp):
                drift.append((r["artifact_id"], r["filename"], sub, r.get("sha256", "")[:12], sha(ws)[:12], sha(vp)[:12]))
print("drifted:", drift)
print(subprocess.run(["grep", "-n", "sha\\|MISSING\\|mismatch\\|size", f"{FILES}/ops/entrypoints/ingest_job.py", f"{FILES}/ops/ingest/extract.py"],
                     capture_output=True, text=True).stdout[:3000])

# COMMAND ----------

# DBTITLE 1,Plan the edition change for drifted documents
# Content addressing (tools/build_corpus_manifest.py): artifact_id = sha256[:16]. An edited
# document is a new edition. It goes into a new folder beside the old one, and the manifest
# row moves to the new id, so the supersession is visible rather than silent.
wm_path = f"{FILES}/corpus/MANIFEST.json"
wm = json.load(open(wm_path))
plan = []
for old_id, fname, sub, *_ in drift:
    ws = f"{FILES}/corpus/{sub}/{fname}"
    new_sha = sha(ws)
    plan.append(dict(filename=fname, old_id=old_id, new_id=new_sha[:16], new_sha=new_sha,
                     bytes=os.path.getsize(ws), src=ws))
for p in plan:
    old = [r for r in vm["rows"] if r["artifact_id"] == p["old_id"]][0]
    print(p["filename"], "|", p["old_id"], "->", p["new_id"], "| bytes", old["bytes"], "->", p["bytes"])
    print('   old sha', old["sha256"])
# rows in the bundle manifest that no longer exist in the volume
vol_ids = {r["artifact_id"] for r in vm["rows"]}
print("bundle-only rows:", [(r["artifact_id"], r["filename"], len(r.get("members", []))) for r in wm["rows"] if r["artifact_id"] not in vol_ids])
print("bundle manifest top keys:", {k: (v if not isinstance(v, list) else len(v)) for k, v in wm.items()})
print("corpus.json same as bundle manifest:", json.load(open(f"{FILES}/app/data/corpus.json")) == wm)

# COMMAND ----------

# DBTITLE 1,Upload new editions and update the volume manifest
import io
from databricks.sdk import WorkspaceClient
w = WorkspaceClient()
TODAY = dt.date.today().isoformat()
vm = json.load(open(f"{VOL}/MANIFEST.json"))  # re-read, so re-running this cell is safe
seen = {s["artifact_id"] for s in vm.get("superseded", [])}
plan = [p for p in plan if p["old_id"] not in seen]

for p in plan:
    dst = f"{VOL}/{p['new_id']}/{p['filename']}"
    with open(p["src"], "rb") as f:
        w.files.upload(dst, f, overwrite=True)
    assert sha(dst) == p["new_sha"], f"upload of {p['filename']} does not hash to {p['new_id']}"
    # Move the manifest row to the new edition. Every other field is a property of the
    # document, not of the edition, so it carries over unchanged.
    for r in vm["rows"]:
        if r["artifact_id"] == p["old_id"]:
            r.update(artifact_id=p["new_id"], sha256=p["new_sha"], bytes=p["bytes"])
    # The old edition stays in the volume and is listed, so a citation to it still resolves
    # and the change is visible rather than silent.
    vm.setdefault("superseded", []).append(
        {"artifact_id": p["old_id"], "filename": p["filename"], "superseded_by": p["new_id"], "on": TODAY,
         "why": "E-16 correction edited in the workspace, which is the source of truth"})
    print("uploaded and verified", dst)

vm["bytes"] = sum(r["bytes"] for r in vm["rows"]); vm["count"] = len(vm["rows"])
vm["generated_from"] = "workspace bundle corpus/ (source of truth since 2026-11-08) plus volume-only reference and imagery"
w.files.upload(f"{VOL}/MANIFEST.json", io.BytesIO(json.dumps(vm, indent=1).encode()), overwrite=True)
vm = json.load(open(f"{VOL}/MANIFEST.json"))
print("volume manifest:", vm["count"], "rows,", len(vm["superseded"]), "superseded editions")

# Exact fragments for patching the two workspace copies (bundle manifest and app/data/corpus.json)
raw = open(wm_path).read()
for r in wm["rows"]:
    if r["artifact_id"] not in vol_ids:
        frag = json.dumps(r, indent=1).replace("\n", "\n ")
        print("ZIP ROW FOUND VERBATIM:", (" " + frag) in raw, repr(frag[:80]))
print("HEADER:", repr(raw[:raw.find('"rows"')]))

# COMMAND ----------

# DBTITLE 1,Locate exact fragments in the workspace manifests
raw = open(wm_path).read()
for zid in [r["artifact_id"] for r in wm["rows"] if r["artifact_id"] not in vol_ids]:
    i = raw.find(f'"artifact_id": "{zid}"')
    start = raw.rfind("{", 0, i)          # the row's opening brace
    depth, j = 0, start
    while True:                           # walk to its matching close brace
        depth += {"{": 1, "}": -1}.get(raw[j], 0)
        if depth == 0: break
        j += 1
    print(f"ROW {zid}: chars {start}-{j}, preceded by {raw[start-4:start]!r}, followed by {raw[j+1:j+5]!r}")
    print(raw[start - 3:j + 1])
    print("=====")
for needle in ['"bytes": 191763,', '"bytes": 22620,', '"721d39f9237e6944', '"b36f08e3a240b632']:
    print(needle, raw.count(needle))
print("new editions:", [(s["filename"], [r["sha256"] for r in vm["rows"] if r["artifact_id"] == s["superseded_by"]][0]) for s in vm["superseded"]])
print("new header values:", vm["count"], vm["bytes"], vm["by_bucket"], vm["by_route"])

# COMMAND ----------

# DBTITLE 1,Verify the three manifests agree with the files
vm = json.load(open(f"{VOL}/MANIFEST.json"))
wm = json.load(open(f"{FILES}/corpus/MANIFEST.json"))      # parses, so the patches left valid JSON
cj = json.load(open(f"{FILES}/app/data/corpus.json"))
key = lambda m: sorted((r["artifact_id"], r["sha256"], r["filename"], r["bytes"]) for r in m["rows"])
print("PASS" if key(wm) == key(vm) else "FAIL", "bundle manifest rows == volume manifest rows", len(wm["rows"]), len(vm["rows"]))
print("PASS" if cj == wm else "FAIL", "app/data/corpus.json == bundle manifest")
print("PASS" if wm["count"] == len(wm["rows"]) and wm["bytes"] == sum(r["bytes"] for r in wm["rows"]) else "FAIL", "header totals match rows")
# every row hashes to its own id, read from the bytes on disk, not from the manifest
bad = [r["filename"] for r in vm["rows"] if sha(f"{VOL}/{r['artifact_id']}/{r['filename']}") != r["sha256"]]
print("PASS" if not bad else "FAIL", "every volume file hashes to its manifest sha", bad)
ws_bad = [r["filename"] for r in wm["rows"] if r["bucket"] in ("dossier", "durable")
          and sha(f"{FILES}/corpus/{r['path']}") != r["sha256"]]
print("PASS" if not ws_bad else "FAIL", "workspace dossier and durable files match their manifest sha", ws_bad)
folders = {d for d in os.listdir(VOL) if os.path.isdir(f"{VOL}/{d}")}
listed = {r["artifact_id"] for r in vm["rows"]} | {s["artifact_id"] for s in vm.get("superseded", [])}
print("PASS" if folders == listed else "FAIL", "every volume folder is a current or a superseded edition", folders ^ listed)

# COMMAND ----------

