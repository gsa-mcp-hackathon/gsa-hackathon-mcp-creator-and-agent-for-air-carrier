"""aircarrier-mcp-probe: probes the Air Carrier MCP apps on a timer, as its own service principal.

The platform injects DATABRICKS_HOST, DATABRICKS_CLIENT_ID and DATABRICKS_CLIENT_SECRET
for this app's service principal; nobody handles a secret. Each sweep is one
JSON-lines file in PROBE_VOLUME/<date>/, written with the Files API, so the
probe does not depend on a SQL warehouse (the servers do, and a monitor should
not share its subject's failure). An alert reads the files with read_files and
fires on a failed target or on silence (no sweep for 40 minutes), so a dead
probe is noticed too.

Routes: GET / (last sweep summary), GET /health (process alive), POST /run (sweep now).
"""
from __future__ import annotations

import io
import json
import logging
import os
import threading
import time

import requests
from databricks.sdk import WorkspaceClient
from fastapi import FastAPI

import probe

log = logging.getLogger("probe")
logging.basicConfig(level=logging.INFO)

INTERVAL_S = int(os.getenv("PROBE_INTERVAL_S", "900"))
# Set in app.yaml; no workspace's own path lives in code.
VOLUME = os.getenv("PROBE_VOLUME", "/Volumes/main/aircarrier/mcp_probe_runs").rstrip("/")

w = WorkspaceClient()
app = FastAPI(title="aircarrier-mcp-probe")
_state: dict = {"last": None, "written": None, "error": None}
_run_lock = threading.Lock()


def _resolve(name: str):
    a = w.apps.get(name)
    return a.url, (a.active_deployment.deployment_id if a.active_deployment else None)


def _post(url, headers, body):
    # Re-checked here, at the only network call that carries the token: allowlisted
    # Databricks Apps host, https, /mcp only, and no redirects (a redirect could move
    # the bearer token to a host that was never checked).
    safe = probe.safe_mcp_url(url)
    r = requests.post(safe, headers=headers, json=body, timeout=probe.TIMEOUT_S, allow_redirects=False)
    return r.status_code, r.text


def _write(rows):
    """One immutable file per sweep; never overwrites (append-only by construction)."""
    if not rows:
        return
    day = rows[0]["checked_at"][:10]
    path = f"{VOLUME}/{day}/{rows[0]['probe_run_id']}.jsonl"
    body = "\n".join(json.dumps(r, default=str) for r in rows).encode()
    w.files.upload(path, io.BytesIO(body), overwrite=False)
    return path


def sweep() -> dict:
    with _run_lock:
        s = probe.Sweep(_resolve, lambda: w.config.authenticate(), _post)
        out = s.run()
        try:
            _state.update(written=_write(out["rows"]), error=None)
        except Exception as e:  # noqa: BLE001 - keep probing; the alert sees the silence
            _state.update(written=False, error=f"{type(e).__name__}: {str(e)[:200]}")
            log.error("write failed: %s", _state["error"])
        _state["last"] = {k: out[k] for k in ("probe_run_id", "ok", "failing", "targets")} | {
            "steps": [{k: r[k] for k in ("target", "step", "ok", "latency_ms", "detail")} for r in out["rows"]]}
        log.info("sweep %s ok=%s failing=%s", out["probe_run_id"], out["ok"], out["failing"])
        return _state["last"]


def _loop():
    time.sleep(10)
    while True:
        try:
            sweep()
        except Exception:
            log.exception("sweep crashed")
        time.sleep(INTERVAL_S)


@app.on_event("startup")
def _start():
    threading.Thread(target=_loop, daemon=True, name="probe-loop").start()


@app.get("/")
def status():
    return {"interval_s": INTERVAL_S, "volume": VOLUME, **_state}


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/run")
def run_now():
    return sweep()
