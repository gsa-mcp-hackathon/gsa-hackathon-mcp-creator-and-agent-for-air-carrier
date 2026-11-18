#!/usr/bin/env python3
"""Generate app/data/rules.json for the /rules page (app/api/rulebook.py).

The page reads the rule register live. This file holds what it cannot read
live from inside the app:

  gate_routes        seed/gate.yaml routes, in evaluation order. seed/ is not
                     deployed with the app.
  register_snapshot  the rule register at build time, grouped exactly as the
                     page groups it (the same SQL and the same grouping code).
                     Shown only when the live read fails, and labelled with
                     built_at and the reason.

No entry is typed. Rebuild after a rule version is inserted or retired, or
after gate.yaml changes:

    python etl/build_rules.py --root <bundle files dir>      # on Spark
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import sys

import yaml


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, help="bundle files directory")
    ap.add_argument("--catalog", default="users")
    ap.add_argument("--schema", default="xiaobing_shang1_civ")
    ap.add_argument("--prefix", default="aircarrier_")
    a = ap.parse_args()

    # api.live reads these at import, and harness_sql.tables() is built from it,
    # so they are set before the app modules are imported.
    os.environ.update(AIRCARRIER_CATALOG=a.catalog, AIRCARRIER_SCHEMA=a.schema,
                      AIRCARRIER_STORE_PREFIX=a.prefix)
    root = pathlib.Path(a.root)
    sys.path.insert(0, str(root / "app"))
    from api import harness_sql as H
    from api import rulebook
    from pyspark.sql import SparkSession

    spark = SparkSession.builder.getOrCreate()
    t = H.tables()
    rows = [r.asDict(recursive=True) for r in spark.sql(H.rule_catalog(t)).collect()]
    if not rows:
        print(f"{t['rule_register']} returned no rows; rules.json not written")
        return 1
    routes = rulebook.gate_routes(yaml.safe_load((root / "seed" / "gate.yaml").read_text()))

    built_at = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    out = {"built_at": built_at,
           "source": {"register": t["rule_register"], "gate_routes": "seed/gate.yaml"},
           "gate_routes": routes,
           "register_snapshot": {"built_at": built_at,
                                 "areas": rulebook.group_by_area(rows)}}
    path = root / "app" / "data" / "rules.json"
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"written": str(path), "built_at": built_at,
                      "rules": len(rows), "gate_routes": len(routes)}, indent=1))
    return 0


if __name__ == "__main__":
    # Serverless runs spark_python_task under IPython, which reports even
    # SystemExit(0) as a failed run. Raise only on a real failure.
    rc = main()
    if rc:
        raise SystemExit(rc)
