"""Data access.

Two backends behind one interface, selected by AIRCARRIER_DATA_BACKEND.

  files  JSON bundles in app/data, built by etl/build_data.py. The app runs
         with no workspace at all. This is D11, graceful degradation, applied
         to the front end: the product works at every access level including
         zero.
  uc     one view per document, <prefix>v_doc_<name>, over <prefix>serving_doc,
         which etl/publish_serving_docs.py fills with the exact text of each
         app/data file (docs/UC_SERVING_VIEWS.md, phase 1). The app reads views,
         never base tables, so a new field is a view change rather than a grant
         change.

Nothing else in the app knows which backend is live.
"""
from __future__ import annotations

import functools
import json
import os
import pathlib

BACKEND = os.environ.get("AIRCARRIER_DATA_BACKEND", "files")
DATA = pathlib.Path(__file__).resolve().parent.parent / "data"
CATALOG = os.environ.get("AIRCARRIER_CATALOG", "aircarrier")
# Mirrors var.schema and var.store_prefix in databricks.yml. The build
# does not create either the catalog or the schema; it is pointed at
# them, and prefixes everything it owns inside.
SCHEMA = os.environ.get("AIRCARRIER_SCHEMA", "default")
STORE_PREFIX = os.environ.get("AIRCARRIER_STORE_PREFIX", "aircarrier_")

# Every document the app reads by name (all 23 app/data/*.json files; checked
# 2026-11-12 against every data.get("...") in app/). The old list had 20 and
# missed corpus, delivery and rules.
DOCUMENTS = (
    "anchor_chain", "asset", "attribution", "cap_history", "clue_map", "contracts",
    "corpus", "cost_categories", "delivery", "equipment", "estimate_history",
    "federal_accounts", "funding_streams", "gaps", "industrial", "layers",
    "obligations", "program", "rules", "sources", "subawards", "timeline", "variances",
)
VIEWS = {n: f"{CATALOG}.{SCHEMA}.{STORE_PREFIX}v_doc_{n}" for n in DOCUMENTS}
# A published document changes only when the ETL runs, so one read per document
# per minute is enough; a re-publish shows within UC_TTL_S.
UC_TTL_S = 60


@functools.lru_cache(maxsize=256)
def _read(path: str, _mtime_ns: int):
    """Cached on the file's modification time, so a rebuilt table is picked up
    on the next request and an unchanged one is not re-parsed.

    A plain lru_cache on the name alone holds the first read for the life of
    the process. On a serverless app that process is long lived, so an insight
    captured through the product, or a table rebuilt by the ETL, would never
    appear until someone restarted it, and nothing would look wrong. Found by
    the data disagreeing with the page that rendered it."""
    return json.loads(pathlib.Path(path).read_text())


def get(name: str):
    if BACKEND == "files":
        p = DATA / f"{name}.json"
        if not p.exists():
            return {}
        return _read(str(p), p.stat().st_mtime_ns)
    return _uc_get(name)


def _uc_get(name: str):
    """The document from its view, parsed and cached on its content_sha. An unknown
    name is {} as in the files backend. A failed read raises, so a page shows the
    error instead of rendering empty."""
    view = VIEWS.get(name)
    if view is None:
        return {}
    from . import live
    from .sqlsafe import compose
    def read():
        _cols, rows = live.query(compose("SELECT doc, content_sha FROM {view}", view=view))
        if len(rows) != 1:
            raise RuntimeError(f"{view} holds {len(rows)} rows; expected exactly 1. "
                               "Run etl/publish_serving_docs.py.")
        return rows[0]["content_sha"], rows[0]["doc"]
    content_sha, doc = live.cached(f"doc:{name}", UC_TTL_S, read)
    return _parse(content_sha, doc)


@functools.lru_cache(maxsize=64)
def _parse(_content_sha: str, doc: str):
    return json.loads(doc)


def available() -> list[str]:
    if BACKEND == "uc":
        return sorted(VIEWS)
    return sorted(p.stem for p in DATA.glob("*.json"))


def backend_info() -> dict:
    return {"backend": BACKEND, "tables": len(available()),
            "catalog": CATALOG if BACKEND == "uc" else None}
