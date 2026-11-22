"""Synthetic probe of the Air Carrier MCP servers, run as this app's own service principal.

For each target app, one sweep checks, in order:
  resolve       the app exists and has an active deployment (URL, deployment id)
  initialize    POST /mcp initialize returns a result
  tools_list    tools/list returns at least the expected number of tools
  known_answer  one read-only tool returns an answer we already know

A failed step stops that target's sweep. Every step is a row in the results
table, so a failure says where it broke.

What this proves, and what it does not: a green sweep means the app, the
platform's OAuth path for a non-human caller, the server code and its data
are all healthy. It cannot see one user's Genie Code connector authorization.
So if the probe is green and a user gets "Failed to generate OAuth token", the
cause is that user's connector, and the fix is to re-authenticate.

No token, header or payload is ever written; detail is a short reason.
"""
from __future__ import annotations

import json
import os
import re
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit, urlunsplit

PROTOCOL = "2025-06-18"
TIMEOUT_S = 60
DETAIL_MAX = 300

# Where the probe may send its service principal's bearer token: Databricks Apps hosts only.
ALLOWED_HOST_SUFFIX = os.getenv("PROBE_ALLOWED_HOST_SUFFIX", ".databricksapps.com").lower()
_HOST = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?)+$")


class UnsafeURL(ValueError):
    """A destination outside the allowlist; the token is never sent to it."""


def safe_mcp_url(url: str) -> str:
    """Return a rebuilt https://<app host>/mcp URL, or raise UnsafeURL.

    The token goes only to an https Databricks Apps host on the default port, at
    path /mcp, with no credentials, query or fragment in the URL.
    """
    try:
        p = urlsplit(url or "")
        port = p.port
    except ValueError as e:
        raise UnsafeURL("malformed URL") from e
    host = (p.hostname or "").lower()
    if p.scheme != "https":
        raise UnsafeURL("not https")
    if p.username or p.password or port not in (None, 443):
        raise UnsafeURL("credentials or non-default port in URL")
    if not _HOST.match(host) or not host.endswith(ALLOWED_HOST_SUFFIX) or host == ALLOWED_HOST_SUFFIX.lstrip("."):
        raise UnsafeURL("host not an allowed Databricks Apps host: " + host)
    if p.path != "/mcp" or p.query or p.fragment:
        raise UnsafeURL("path must be /mcp with no query or fragment")
    return urlunsplit(("https", host, "/mcp", "", ""))


def _docs(r: dict) -> str | None:
    # $13,529M is printed as "$13.529 billion" on the FY2027 MSAR, p. 8. Before the
    # 2026-11-11 fix the server reported it as not printed; this keeps that fixed.
    hits = r.get("text_hits") or []
    if not r.get("found", r.get("n_text_hits", 0) > 0):
        return "docs_find_figure(13529) found nothing"
    if not any("MSAR_FY2027" in (h.get("filename") or "") and h.get("page") == 8 for h in hits):
        return "13529 not found on CVN_78_MSAR_FY2027_PBv2.pdf p. 8"
    return None


def _analyst(r: dict) -> str | None:
    return None if str(r.get("engine", "")).startswith("analyst/") else "model_status has no engine"


def _ops(r: dict) -> str | None:
    n = ((r.get("totals") or {}).get("record_count")) or 0
    return None if int(n) > 0 else "work register totals returned 0 records"


def _bakehouse(r: dict) -> str | None:
    # The Creator's second build, on a non-CVN table (samples.bakehouse). Its
    # describe tool ships the data dictionary and needs no warehouse, so a wrong
    # answer means the generated server itself is broken.
    names = {f.get("name") for f in r.get("fields") or []}
    return None if r.get("source") == "sales" and "transactionID" in names else \
        "bakehouse_describe_sales did not return the sales dictionary"


def _hub(r: dict) -> str | None:
    # E-17: the December 2025 baseline of $13,529M is held for review; the gate
    # must route it to a person and never promote it.
    d = r.get("decision")
    return None if d == "human_review" else f"hub_check_claim(13529) returned {d!r}, not human_review"


def _creator(r: dict) -> str | None:
    # creator_list_library is read-only: the Creator's packaged skills, which every
    # design phase loads. A missing skill means the deployed build is broken.
    names = {s.get("name") for s in r.get("skills") or []}
    need = {"mcp-tool-design", "mcp-security-review", "databricks-mcp-deployment"}
    if len(names) >= 8 and need <= names:
        return None
    return f"creator_list_library returned {len(names)} skills, missing {sorted(need - names)}"


@dataclass(frozen=True)
class Target:
    app: str
    min_tools: int
    tool: str | None = None
    args: dict = field(default_factory=dict)
    check: Callable[[dict], str | None] | None = None


TARGETS = [
    Target("mcp-aircarrier-docs", 11, "docs_find_figure", {"value_musd": "13529"}, _docs),
    Target("mcp-aircarrier-analyst", 12, "analyst_model_status", {}, _analyst),
    Target("mcp-aircarrier-ops", 7, "carrier_work_register_counts", {}, _ops),
    Target("mcp-aircarrier-hub", 16, "hub_check_claim",
           {"hull": "CVN-79", "layer": "budget", "element": "Total Ship Estimate",
            "period": "FY2027 PB", "value_musd": "13529", "tag": "VERIFIED", "confidence": 0.9},
           _hub),
    Target("mcp-a-creator", 10, "creator_list_library", {}, _creator),  # read-only
]

# Not a target: the bakehouse app was deleted on 2026-11-21 so the hub could take its
# slot (the shared workspace is capped at 100 apps). Add BAKEHOUSE back if it returns.
BAKEHOUSE = Target("mcp-bakehouse-sales", 7, "bakehouse_describe_sales", {}, _bakehouse)


def _clip(s: Any) -> str:
    s = " ".join(str(s).split())
    return s if len(s) <= DETAIL_MAX else s[:DETAIL_MAX - 3] + "..."


def parse_rpc(text: str) -> dict:
    """A JSON-RPC reply as JSON or as server-sent events (the last data: line wins)."""
    t = (text or "").strip()
    if t.startswith("{"):
        return json.loads(t)
    data = [ln[5:].strip() for ln in t.splitlines() if ln.startswith("data:")]
    if not data:
        raise ValueError("no JSON-RPC body")
    return json.loads(data[-1])


def tool_body(result: dict) -> Any:
    """The tool's answer from a tools/call result: structuredContent, else the text block as JSON."""
    if result.get("isError"):
        text = " ".join(c.get("text", "") for c in result.get("content") or [])
        raise RuntimeError(f"tool error: {text}")
    sc = result.get("structuredContent")
    if isinstance(sc, dict):
        return sc.get("result", sc) if set(sc) == {"result"} else sc
    text = "".join(c.get("text", "") for c in result.get("content") or [])
    return json.loads(text)


class Sweep:
    """One pass over all targets. post(url, headers, json) -> (status, text)."""

    def __init__(self, resolve, headers, post, now=lambda: datetime.now(UTC)):
        self.resolve, self.headers, self.post, self.now = resolve, headers, post, now
        self.run_id = "probe-" + uuid.uuid4().hex[:12]
        self.rows: list[dict] = []

    def _row(self, target, step, ok, status=None, ms=None, detail=None, dep=None):
        self.rows.append({"probe_run_id": self.run_id, "target": target, "step": step, "ok": bool(ok),
                          "http_status": status, "latency_ms": ms,
                          "detail": None if detail is None else _clip(detail),
                          "deployment_id": dep, "checked_at": self.now().isoformat()})
        return ok

    def _rpc(self, url, method, params, i):
        h = {**self.headers(), "Accept": "application/json, text/event-stream",
             "Content-Type": "application/json"}
        t0 = time.monotonic()
        status, text = self.post(url, h, {"jsonrpc": "2.0", "id": i, "method": method, "params": params})
        ms = int((time.monotonic() - t0) * 1000)
        if status != 200:
            return status, ms, None, f"HTTP {status}"
        try:
            msg = parse_rpc(text)
        except ValueError as e:
            return status, ms, None, f"unreadable reply: {e}"
        if "error" in msg:
            return status, ms, None, f"JSON-RPC error {msg['error'].get('code')}: {msg['error'].get('message')}"
        return status, ms, msg.get("result"), None

    def target(self, t: Target) -> bool:
        try:
            url, dep = self.resolve(t.app)
        except Exception as e:  # noqa: BLE001 - recorded, not raised
            return self._row(t.app, "resolve", False, detail=f"{type(e).__name__}: {e}")
        if not url or not dep:
            return self._row(t.app, "resolve", False, detail="no URL or no active deployment", dep=dep)
        try:
            mcp = safe_mcp_url(url.rstrip("/") + "/mcp")
        except UnsafeURL as e:
            return self._row(t.app, "resolve", False, detail=f"refused URL: {e}", dep=dep)
        self._row(t.app, "resolve", True, dep=dep)
        try:
            s, ms, res, err = self._rpc(mcp, "initialize", {
                "protocolVersion": PROTOCOL, "capabilities": {},
                "clientInfo": {"name": "aircarrier-mcp-probe", "version": "1.0"}}, 1)
            if not self._row(t.app, "initialize", err is None and res is not None, s, ms, err, dep):
                return False
            s, ms, res, err = self._rpc(mcp, "tools/list", {}, 2)
            n = len((res or {}).get("tools") or [])
            if err is None and n < t.min_tools:
                err = f"{n} tools, expected at least {t.min_tools}"
            if not self._row(t.app, "tools_list", err is None, s, ms, err or f"{n} tools", dep):
                return False
            if not t.tool:
                return True
            s, ms, res, err = self._rpc(mcp, "tools/call", {"name": t.tool, "arguments": t.args}, 3)
            if err is None:
                try:
                    err = t.check(tool_body(res or {}))
                except Exception as e:  # noqa: BLE001
                    err = f"{type(e).__name__}: {e}"
            return self._row(t.app, "known_answer", err is None, s, ms, err or f"{t.tool} ok", dep)
        except Exception as e:  # noqa: BLE001 - a network error is a failed step, not a crash
            return self._row(t.app, "transport", False, detail=f"{type(e).__name__}: {e}", dep=dep)

    def run(self, targets=TARGETS) -> dict:
        for t in targets:
            self.target(t)
        failing = sorted({r["target"] for r in self.rows if not r["ok"]})
        return {"probe_run_id": self.run_id, "ok": not failing, "failing": failing,
                "targets": len(targets), "rows": self.rows}


# The columns of every row, in the order read_files is given them (see CONNECTOR_RUNBOOK.md).
COLUMNS = ["probe_run_id", "target", "step", "ok", "http_status", "latency_ms", "detail",
           "deployment_id", "checked_at"]
