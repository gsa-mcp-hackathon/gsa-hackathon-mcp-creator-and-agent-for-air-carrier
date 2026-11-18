"""Publish the app's page documents to Unity Catalog (docs/UC_SERVING_VIEWS.md, phase 1).

The files backend serves app/data/<name>.json. This copies the exact text of every
one of those files into one table, keyed by name, and keeps one view per name over it.
The uc backend (app/api/data.py) reads the views, so both backends serve the same bytes.

  table  <prefix>serving_doc (name, doc, content_sha, built_at, published_by)
  views  <prefix>v_doc_<name>, SELECT doc, content_sha, built_at for that name

Idempotent: a row is rewritten only when its content_sha changes, and a view is
replaced with the same definition. A document whose file is gone is left in the
table and reported, never deleted here.

Run after etl/build_data.py and etl/build_delivery.py. Needs Spark.
Arguments: --root PATH (repository root), --dry-run (report only).
"""
from __future__ import annotations

import argparse
import hashlib
import os
import pathlib
import sys
from datetime import datetime, timezone

CATALOG = os.environ.get("AIRCARRIER_CATALOG", "users")
SCHEMA = os.environ.get("AIRCARRIER_SCHEMA", "xiaobing_shang1_civ")
PREFIX = os.environ.get("AIRCARRIER_STORE_PREFIX", "aircarrier_")
FQ = f"{CATALOG}.{SCHEMA}.{PREFIX}"
TABLE = f"{FQ}serving_doc"
VERSION = "publish_serving_docs/0.1"

DDL = f"""CREATE TABLE IF NOT EXISTS {TABLE} (
  name STRING NOT NULL, doc STRING NOT NULL, content_sha STRING NOT NULL,
  built_at TIMESTAMP NOT NULL, published_by STRING NOT NULL)
COMMENT 'Page documents for the app uc backend: the exact text of app/data/<name>.json. Written by etl/publish_serving_docs.py only; read through the v_doc_<name> views.'"""


def view_name(name: str) -> str:
    return f"{FQ}v_doc_{name}"


def view_ddl(name: str) -> str:
    return (f"CREATE OR REPLACE VIEW {view_name(name)} "
            f"COMMENT 'Page document {name} for the app uc backend (etl/publish_serving_docs.py).' AS "
            f"SELECT doc, content_sha, built_at FROM {TABLE} WHERE name = '{name}'")


def documents(data_dir: pathlib.Path) -> dict[str, str]:
    """name -> exact file text, for every top-level JSON file the app serves."""
    return {p.stem: p.read_text() for p in sorted(data_dir.glob("*.json"))}


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="publish_serving_docs")
    ap.add_argument("--root", default=None)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv or [])
    root = pathlib.Path(a.root) if a.root else pathlib.Path(__file__).resolve().parents[1]
    docs = documents(root / "app" / "data")
    if not docs:
        print(f"no documents under {root / 'app' / 'data'}")
        return 1
    if a.dry_run:   # no Spark needed
        print({"documents": len(docs), "names": sorted(docs)})
        return 0
    from pyspark.sql import SparkSession
    spark = SparkSession.builder.getOrCreate()
    now = datetime.now(timezone.utc).replace(microsecond=0, tzinfo=None)
    rows = [(n, t, sha(t), now, VERSION) for n, t in docs.items()]
    spark.sql(DDL)
    spark.createDataFrame(rows, "name string, doc string, content_sha string, built_at timestamp, "
                                "published_by string").createOrReplaceTempView("_docs_in")
    r = spark.sql(f"""MERGE INTO {TABLE} t USING _docs_in s ON t.name = s.name
        WHEN MATCHED AND t.content_sha <> s.content_sha THEN UPDATE SET *
        WHEN NOT MATCHED THEN INSERT *""").first()
    for n in docs:
        spark.sql(view_ddl(n))
    held = {x.name for x in spark.sql(f"SELECT name FROM {TABLE}").collect()}
    report = {"documents": len(docs), "inserted": int(r.num_inserted_rows),
              "updated": int(r.num_updated_rows), "views": len(docs),
              "in_table_without_file": sorted(held - set(docs))}
    print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
