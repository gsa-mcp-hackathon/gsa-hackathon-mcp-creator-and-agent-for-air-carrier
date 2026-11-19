"""Run the unit tests, then the investigator on real Unity Catalog data, on serverless.

Submitted as a one-off job run (spark_python_task). The workspace file system
blocks __pycache__, so everything runs from a /tmp copy. warehouse.run is
rebound to Spark SQL so no SQL warehouse or app resource is needed.
"""
import json
import os
import shutil
import subprocess  # nosec B404 - runs pytest only
import sys
import time

ROOT = "/Workspace/Users/xiaobing.shang1.civ@mail.mil/mcp-servers/mcp-aircarrier-analyst"
shutil.rmtree("/tmp/mca", ignore_errors=True)
shutil.copytree(ROOT, "/tmp/mca", ignore=shutil.ignore_patterns("__pycache__", ".git"))

res = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests"],  # nosec B603
                     check=False, cwd="/tmp/mca", capture_output=True, text=True, env={**os.environ, "PYTHONPATH": "/tmp/mca/src",
                                                                          "PYTHONDONTWRITEBYTECODE": "1"})
print("PYTEST_EXIT", res.returncode)
print(res.stdout[-6000:])
print(res.stderr[-2000:])

sys.path.insert(0, "/tmp/mca/src")
from pyspark.sql import SparkSession

spark = SparkSession.builder.getOrCreate()
from mcp_aircarrier_analyst import investigator as inv
from mcp_aircarrier_analyst import library, warehouse


def spark_run(sql, params=None):
    df = spark.sql(sql, args=list(params or []))
    return [{k: warehouse._plain(v) for k, v in r.asDict().items()} for r in df.collect()]


warehouse.run = spark_run
t = time.time()
K = library.knowledge()
print("KNOWLEDGE", round(time.time() - t, 1), "s", json.dumps({
    "contracts": len(K.contracts), "neg_terms": len(K.neg_terms), "vendors": list(K.vendors),
    "cvn79_tas": len(K.cvn79_tas), "program_codes": K.program_codes, "psc": sorted(K.psc_codes),
    "artifacts": len(K.artifacts), "budget_links": K.budget_links}, default=str))

sub = spark_run("SELECT subawardee_name, subaward_amount FROM users.xiaobing_shang1_civ.aircarrier_src_2114_subawards "
                "WHERE subaward_amount IS NOT NULL ORDER BY CAST(subaward_amount AS DOUBLE) DESC LIMIT 1")[0]
RECORDS = {
    "A_gl_amount_only": {"GL Amount": "$454,765,071.00"},
    "B_gl_amount_and_date": {"Posting Date": "2021-01-14", "Obligation Amount": "56,000,000.00", "Fund": "1611"},
    "C_kennedy_text": {"Description": "JFK hull outfitting material", "amount": "125000.00", "fund": "1611"},
    "D_collision_contract": {"contract": "N00024-16-C-2116", "amount": "1,000,000.00"},
    "E_submarine_item": {"memo": "Large Aperture Bow array component", "appropriation": "017-2019/2023-1611-000"},
    "F_subaward_vendor": {"vendor": sub["subawardee_name"], "amount": sub["subaward_amount"]},
    "G_shared_pe": {"pe": "0604112N", "description": "RDT&E class development"},
    "H_tas_only": {"tas": "017-2018/2022-1611-000"},
    "I_emals": {"contract": "N00019-14-C-0037", "memo": "EMALS AAG production"},
}
src = library.SqlSources()
for name, rec in RECORDS.items():
    t = time.time()
    try:
        r = inv.investigate(rec, K, src)
    except Exception as e:  # noqa: BLE001
        print("CASE", name, "ERROR", repr(e))
        continue
    print("CASE", name, json.dumps({
        "secs": round(time.time() - t, 1), "record": rec,
        "present": r["profile"]["present"],
        "cases": [(c["case"], c["confidence"], c["basis"]) for c in r["cases"]],
        "perfect": r["perfect_match"], "review": r["human_review"],
        "trail": [(s["hop"], s["skill"], s["on"][:50], str(s["found"])[:140], s.get("new_clues", [])[:4])
                  for s in r["trail"]],
        "top_for": [(e["skill"], e["weight"], e["statement"][:120]) for e in r["cases"][0]["for"]],
        "recovered": {k: [(x["value"][:50], x["confidence"]) for x in v][:3]
                      for k, v in r["data_elements_recovered"].items()},
        "still_missing": [m["element"] for m in r["still_missing"]],
        "flags": r["flags"], "caveats": r["rules_and_caveats"][:3]}, default=str))

print("DOCSEARCH", json.dumps(library.search_documents("government furnished", "regulation", 3), default=str)[:1500])
print("TRACE", json.dumps(library.trace_entity("N00024-15-C-2114"), default=str)[:2500])
print("SOURCES", json.dumps(library.list_sources(K), default=str)[:2500])
