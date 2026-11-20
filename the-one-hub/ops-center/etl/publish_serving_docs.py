"""Publish the app's page documents to Unity Catalog (docs/UC_SERVING_VIEWS.md, phase 1).

The files backend serves app/data/<name>.json. This copies the exact text of every
one of those files into one table, keyed by name, and keeps one view per name over it.
The uc backend (app/api/data.py) reads the views, so both backends serve the same bytes.

  table  <prefix>serving_doc (name, doc, content_sha, built_at, published_by)
  views  <prefix>v_doc_<name>, SELECT doc, content_sha, built_at for that name

Idempotent: a row is rewritten only when its content_sha changes, and a view is
replaced with the same definition. A document whose file is gone is left in the
table and reported, never deleted here.

Grants: replacing a view can drop its grants (2026-11-20: all 23 views came back
without the app service principal's SELECT and every page returned 500). So after
the views are (re)created, SELECT is granted on each one to every --grant-select-to
principal. GRANT is idempotent. The views run with the owner's rights, so the
principal needs nothing on the serving_doc table itself.

Run after etl/build_data.py and etl/build_delivery.py. Needs Spark.
Arguments: --root PATH (repository root), --dry-run (report only),
  --grant-select-to PRINCIPAL (repeatable; for a service principal, its
  application ID; defaults to AIRCARRIER_APP_SP, comma-separated).
"""
from __future__ import annotations

import argparse
import hashlib
import os
import pathlib
import re
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


# Users, groups and service principal application IDs. No backticks or quotes,
# so a principal can be placed inside `...` without escaping.
_PRINCIPAL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._@+ -]*")


def principals(values: list[str]) -> list[str]:
    """Split, strip, drop empties, dedupe in order; refuse anything not a principal."""
    out: list[str] = []
    for v in values:
        for p in (x.strip() for x in v.split(",")):
            if not p or p in out:
                continue
            if not _PRINCIPAL.fullmatch(p):
                raise ValueError(f"not a principal name: {p!r}")
            out.append(p)
    return out


def grant_ddl(name: str, principal: str) -> str:
    return f"GRANT SELECT ON TABLE {view_name(name)} TO `{principal}`"


def documents(data_dir: pathlib.Path) -> dict[str, str]:
    """name -> exact file text, for every top-level JSON file the app serves."""
    return {p.stem: p.read_text() for p in sorted(data_dir.glob("*.json"))}


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="publish_serving_docs")
    ap.add_argument("--root", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--grant-select-to", action="append", default=[])
    a = ap.parse_args(argv or [])
    root = pathlib.Path(a.root) if a.root else pathlib.Path(__file__).resolve().parents[1]
    grantees = principals(a.grant_select_to or [os.environ.get("AIRCARRIER_APP_SP", "")])
    docs = documents(root / "app" / "data")
    if not docs:
        print(f"no documents under {root / 'app' / 'data'}")
        return 1
    if a.dry_run:   # no Spark needed
        print({"documents": len(docs), "names": sorted(docs), "grant_select_to": grantees})
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
    for n in docs:
        for p in grantees:
            spark.sql(grant_ddl(n, p))
    held = {x.name for x in spark.sql(f"SELECT name FROM {TABLE}").collect()}
    report = {"documents": len(docs), "inserted": int(r.num_inserted_rows),
              "updated": int(r.num_updated_rows), "views": len(docs),
              "grant_select_to": grantees,
              "in_table_without_file": sorted(held - set(docs))}
    if not grantees:
        report["warning"] = ("no --grant-select-to: views carry no app grant; "
                             "the app's uc backend will fail with INSUFFICIENT_PERMISSIONS")
    print(report)
    return 0


if __name__ == "__main__":
    rc = main(sys.argv[1:])
    if rc:  # the serverless wrapper reports any SystemExit, even 0, as a failure
        raise SystemExit(rc)
