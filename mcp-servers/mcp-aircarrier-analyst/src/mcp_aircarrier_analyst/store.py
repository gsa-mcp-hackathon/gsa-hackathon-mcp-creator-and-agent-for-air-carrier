"""Reads the corpus, writes leads and outcomes. The only module that does I/O.

Tables (all in core.catalog.STORE_SCHEMA):
  aircarrier_src_*                 read  - lossless FPDS and File C rows
  aircarrier_analyst_leads         write - one row per option of every answer
  aircarrier_analyst_outcomes      write - confirmed answers; the training labels

A lead write is best effort: if it fails the answer is still returned,
marked lead_logged=false. An outcome write is not: it must land or fail.
"""
from __future__ import annotations

import json
import threading
import time
import uuid

from core import catalog
from core.analyst import engine, sources
from mcp_aircarrier_analyst import service, warehouse
from mcp_aircarrier_analyst.warehouse import render as Q

LEADS = f"{catalog.STORE_SCHEMA}.aircarrier_analyst_leads"
OUTCOMES = f"{catalog.STORE_SCHEMA}.aircarrier_analyst_outcomes"
FC_COLS = ("submission_period", "award_id_piid", "treasury_account_symbol", "object_class_code",
           "program_activity_code", "transaction_obligated_amount", "_source_locator", "_row_num")
TTL_SECONDS = 900

_lock = threading.Lock()
_cache: dict = {}


def _select(tbl: str, cols: tuple[str, ...], piid: str) -> list[dict]:
    sql = Q("SELECT {cols} FROM {src} WHERE award_id_piid = ?", tables={"src": tbl}, cols={"cols": cols})
    return warehouse.run(sql, [piid])


def _load() -> engine.Corpus:
    tx, fc = [], []
    for piid in service.PIIDS:
        tx += _select(sources.TX_TABLES[piid], sources.TX_COLS, piid)
        if piid in sources.FC_TABLES:
            fc += _select(sources.FC_TABLES[piid], FC_COLS, piid)
    return sources.load_rows(tx, fc)


def corpus() -> engine.Corpus:
    """Every known PIID's transactions and File C rows, cached for TTL_SECONDS."""
    with _lock:
        hit = _cache.get("corpus")
        if hit and time.time() - hit[0] < TTL_SECONDS:
            return hit[1]
    c = _load()
    engine.clear_cache()
    with _lock:
        _cache["corpus"] = (time.time(), c)
        _cache.pop("weights", None)
    return c


def as_of() -> str:
    hit = _cache.get("corpus")
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(hit[0] if hit else time.time()))


def outcomes() -> list[dict]:
    sql = Q("SELECT outcome_id, lead_id, kind, piid, subject_key, period, truth, evidence_type, "
            "recorded_at FROM {outcomes} ORDER BY recorded_at", tables={"outcomes": OUTCOMES})
    return warehouse.run(sql)


def weights() -> tuple[dict, dict]:
    """Current weights: refit on deduced labels plus confirmed outcomes."""
    c = corpus()
    with _lock:
        hit = _cache.get("weights")
        if hit and time.time() - hit[0] < TTL_SECONDS:
            return hit[1]
    try:
        outs = outcomes()
        src = "aircarrier_analyst_outcomes"
    except warehouse.WarehouseError:
        outs, src = [], "outcomes table unreadable; deduced labels only"
    w, info = service.current_weights(c, outs)
    info["outcomes_source"] = src
    with _lock:
        _cache["weights"] = (time.time(), (w, info))
    return w, info


def invalidate_weights() -> None:
    with _lock:
        _cache.pop("weights", None)


def log_lead(result: dict, piid: str, subject_key: str | None, period: str | None) -> dict:
    """Store one row per option; return {lead_id, lead_logged}."""
    lead_id = "lead-" + uuid.uuid4().hex[:16]
    opts = result.get("options") or [{}]
    params = []
    for o in opts:
        params += [lead_id, result.get("engine"), result.get("question"), o.get("rank"),
                   o.get("confidence", o.get("expected_share")), result.get("none_of_these"),
                   json.dumps(o, default=str), result.get("kind"), piid, subject_key, period]
    sql = Q("INSERT INTO {leads} (run_id, engine, question, rank, confidence, "
            "none_of_these, option, grade, status, created_at, kind, piid, subject_key, period) VALUES {rows}",
            tables={"leads": LEADS},
            repeat={"rows": ("(?, ?, ?, ?, ?, ?, ?, 'LEAD', 'open', current_timestamp(), ?, ?, ?, ?)",
                             len(opts), ", ")})
    try:
        warehouse.run(sql, params)
        return {"lead_id": lead_id, "lead_logged": True}
    except warehouse.WarehouseError:
        return {"lead_id": lead_id, "lead_logged": False,
                "lead_note": "Answer not logged; record_outcome cannot be used against this lead_id."}


def get_lead(lead_id: str) -> dict | None:
    sql = Q("SELECT run_id, kind, piid, subject_key, period, rank, option, status "
            "FROM {leads} WHERE run_id = ? ORDER BY rank", tables={"leads": LEADS})
    rows = warehouse.run(sql, [lead_id])
    if not rows:
        return None
    first = rows[0]
    return {"lead_id": lead_id, "kind": first["kind"], "piid": first["piid"],
            "subject_key": first["subject_key"], "period": first["period"], "status": first["status"],
            "options": [json.loads(r["option"]) for r in rows if r.get("option")]}


def save_outcome(lead_id: str, row: dict, note: str, recorded_by: str, rank_of_truth: int | None) -> str:
    outcome_id = "out-" + uuid.uuid4().hex[:16]
    sql = Q("INSERT INTO {outcomes} (outcome_id, lead_id, kind, piid, subject_key, period, "
            "truth, rank_of_truth, evidence_type, evidence_locator, confirming_office, note, recorded_by, "
            "recorded_at, engine) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, current_timestamp(), ?)",
            tables={"outcomes": OUTCOMES})
    warehouse.run(sql, [outcome_id, lead_id, row["kind"], row["piid"], row["subject_key"], row["period"],
                        row["truth"], rank_of_truth, row["evidence_type"], row["evidence_locator"],
                        row["confirming_office"], note, recorded_by, engine.ENGINE_VERSION])
    upd = Q("UPDATE {leads} SET status = 'resolved' WHERE run_id = ?", tables={"leads": LEADS})
    try:
        warehouse.run(upd, [lead_id])
    except warehouse.WarehouseError:
        pass  # the outcome is the record; the status flag is a convenience
    invalidate_weights()
    return outcome_id
