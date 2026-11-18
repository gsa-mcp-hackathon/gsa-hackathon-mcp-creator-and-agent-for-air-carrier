"""The corpus, loaded once from Unity Catalog and refreshed on a TTL."""
from __future__ import annotations

import json
import logging
import threading
import time

from docs_core.corpus import Corpus
from mcp_aircarrier_docs import config, warehouse
from mcp_aircarrier_docs.warehouse import render as Q

_lock = threading.Lock()
_state: dict = {"corpus": None, "loaded": 0.0, "as_of": None}
_premise: dict = {"terms": None, "loaded": 0.0, "fixed": False}
log = logging.getLogger(__name__)


def load_premise_terms() -> list[tuple[str, str]]:
    rows = warehouse.run(Q("SELECT label, props FROM {nodes} WHERE node_type = 'negative_term'",
                           tables={"nodes": config.NODES}))
    out = []
    for r in rows:
        try:
            why = (json.loads(r.get("props") or "{}") or {}).get("why", "")
        except (TypeError, ValueError):
            why = ""
        if r.get("label"):
            out.append((str(r["label"]), str(why)))
    return out


def premise_terms(loader=load_premise_terms) -> list[tuple[str, str]]:
    """The premise-trap vocabulary, cached on the corpus TTL. Never raises: a missing
    grant or table means no flags, not a failed search."""
    with _lock:
        fresh = time.time() - _premise["loaded"] <= config.CACHE_TTL_S
        if _premise["fixed"] or (_premise["terms"] is not None and fresh):
            return _premise["terms"]
        try:
            _premise["terms"] = loader()
        except Exception as e:  # noqa: BLE001 - optional feature, logged not raised
            log.warning("premise terms unavailable (%s); docs_search adds no premise flags", type(e).__name__)
            _premise["terms"] = []
        _premise["loaded"] = time.time()
        return _premise["terms"]


def set_premise_terms(terms: list[tuple[str, str]]) -> None:
    """For tests and fixtures; never expires."""
    with _lock:
        _premise.update(terms=list(terms), loaded=time.time(), fixed=True)


def load_rows() -> tuple[list[dict], list[dict]]:
    pages = warehouse.run(Q("SELECT artifact_id, filename, page, text FROM {pages}",
                            tables={"pages": config.PAGES}))
    tables = warehouse.run(Q(
        "SELECT table_id, artifact_id, filename, page, grid_json, title_block, legends, exhibits, "
        "continuation_of, extractor FROM {tables}", tables={"tables": config.TABLES}))
    return pages, tables


def corpus(loader=load_rows) -> Corpus:
    with _lock:
        stale = time.time() - _state["loaded"] > config.CACHE_TTL_S and _state["as_of"] != "fixture"
        if _state["corpus"] is None or stale:
            pages, tables = loader()
            _state["corpus"] = Corpus(pages, tables)
            _state["loaded"] = time.time()
            _state["as_of"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        return _state["corpus"]


def as_of() -> str | None:
    return _state["as_of"]


def set_corpus(c: Corpus) -> None:
    """For tests and stdio runs with fixtures; never expires."""
    with _lock:
        _state.update(corpus=c, loaded=time.time(), as_of="fixture")
