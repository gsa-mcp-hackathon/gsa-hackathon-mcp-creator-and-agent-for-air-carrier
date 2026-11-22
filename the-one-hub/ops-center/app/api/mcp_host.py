"""The front center as an MCP host: Ask the evidence calls the MCP servers.

With AIRCARRIER_ASK_VIA_MCP=1 the /ask agent does not use its own in-app
tools. It lists the tools of the deployed MCP servers (docs, ops and the One
Hub server by default), offers them to the model as they are, and sends each
call to the server that owns it, over streamable HTTP, as the front center's
service principal. Every step of the trace names the server and tool, so a
person reading the run sees which MCP server answered.

If no server can be listed (an app is stopped, a grant is missing), the agent
falls back to its in-app tools and the answer says which transport it used.

The bearer token goes only to an https Databricks Apps host at path /mcp,
with no redirects followed: the same rule as aircarrier-mcp-probe.
"""
from __future__ import annotations

import json
import os
import re
import time
from collections.abc import Callable
from typing import Any
from urllib.parse import urlsplit, urlunsplit

PROTOCOL = "2025-06-18"
TIMEOUT_S = 60
DEFAULT_APPS = "mcp-aircarrier-docs,mcp-aircarrier-ops,mcp-aircarrier-hub"
ALLOWED_HOST_SUFFIX = os.getenv("AIRCARRIER_MCP_HOST_SUFFIX", ".databricksapps.com").lower()
_HOST = re.compile(
    r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?)+$")


def enabled() -> bool:
    return os.getenv("AIRCARRIER_ASK_VIA_MCP", "").strip().lower() in {"1", "true", "yes"}


def app_names() -> list[str]:
    raw = os.getenv("AIRCARRIER_MCP_APPS", DEFAULT_APPS)
    return [a.strip() for a in raw.split(",") if a.strip()]


class UnsafeURL(ValueError):
    """A destination outside the allowlist; the token is never sent to it."""


def safe_mcp_url(url: str) -> str:
    """https://<Databricks Apps host>/mcp, rebuilt, or UnsafeURL."""
    try:
        p = urlsplit((url or "").rstrip("/") + ("" if (url or "").rstrip("/").endswith("/mcp")
                                                 else "/mcp"))
        port = p.port
    except ValueError as e:
        raise UnsafeURL("malformed URL") from e
    host = (p.hostname or "").lower()
    if p.scheme != "https" or p.username or p.password or port not in (None, 443):
        raise UnsafeURL("not a plain https URL")
    if (not _HOST.match(host) or not host.endswith(ALLOWED_HOST_SUFFIX)
            or host == ALLOWED_HOST_SUFFIX.lstrip(".")):
        raise UnsafeURL("host not an allowed Databricks Apps host: " + host)
    if p.path != "/mcp" or p.query or p.fragment:
        raise UnsafeURL("path must be /mcp with no query or fragment")
    return urlunsplit(("https", host, "/mcp", "", ""))


def parse_rpc(text: str) -> dict:
    """A JSON-RPC reply as JSON or as server-sent events (the last data: line wins)."""
    t = (text or "").strip()
    if t.startswith("{"):
        return json.loads(t)
    data = [ln[5:].strip() for ln in t.splitlines() if ln.startswith("data:")]
    if not data:
        raise ValueError("no JSON-RPC body")
    return json.loads(data[-1])


class McpHost:
    """Tools of several MCP servers behind one call().

    resolve(app) -> url; headers() -> auth headers; post(url, headers, body) -> (status, text).
    """

    def __init__(self, resolve: Callable[[str], str], headers: Callable[[], dict],
                 post: Callable[[str, dict, dict], tuple[int, str]],
                 apps: list[str] | None = None):
        self.resolve, self.headers, self.post = resolve, headers, post
        self.apps = apps or app_names()
        self.urls: dict[str, str] = {}
        self.owner: dict[str, str] = {}      # tool name -> app
        self.tools: list[dict] = []          # MCP tool definitions, as listed
        self.unreachable: dict[str, str] = {}
        self._id = 0

    def _rpc(self, app: str, method: str, params: dict) -> Any:
        self._id += 1
        h = {**self.headers(), "Accept": "application/json, text/event-stream",
             "Content-Type": "application/json"}
        status, text = self.post(self.urls[app], h,
                                 {"jsonrpc": "2.0", "id": self._id, "method": method,
                                  "params": params})
        if status != 200:
            raise RuntimeError(f"HTTP {status}")
        msg = parse_rpc(text)
        if "error" in msg:
            raise RuntimeError(f"JSON-RPC error {msg['error'].get('message')}")
        return msg.get("result") or {}

    def connect(self) -> McpHost:
        """List every server's tools. A server that fails is recorded, not fatal."""
        for app in self.apps:
            try:
                self.urls[app] = safe_mcp_url(self.resolve(app))
                self._rpc(app, "initialize", {
                    "protocolVersion": PROTOCOL, "capabilities": {},
                    "clientInfo": {"name": "aircarrier-front-center", "version": "1"}})
                listed = self._rpc(app, "tools/list", {}).get("tools") or []
            except Exception as exc:  # noqa: BLE001 - recorded and shown with the answer
                self.unreachable[app] = str(exc)[:200]
                continue
            for t in listed:
                if t.get("name") and t["name"] not in self.owner:
                    self.owner[t["name"]] = app
                    self.tools.append(t)
        return self

    def openai_tools(self) -> list[dict]:
        """The listed tools as chat-completions function definitions."""
        return [{"type": "function", "function": {
            "name": t["name"], "description": (t.get("description") or "")[:1024],
            "parameters": t.get("inputSchema") or {"type": "object", "properties": {}}}}
            for t in self.tools]

    def call(self, name: str, args: dict) -> tuple[dict, dict]:
        """(answer, trace extras). A tool error comes back as {'error': ...}."""
        app = self.owner[name]
        t0 = time.monotonic()
        try:
            result = self._rpc(app, "tools/call", {"name": name, "arguments": args or {}})
        except Exception as exc:  # noqa: BLE001 - shown to the model as the tool's answer
            return {"error": f"{app}: {str(exc)[:240]}"}, {"server": app}
        ms = int((time.monotonic() - t0) * 1000)
        text = "".join(c.get("text", "") for c in result.get("content") or [])
        if result.get("isError"):
            return {"error": text[:2000] or "tool error"}, {"server": app, "ms": ms}
        body = result.get("structuredContent")
        if body is None:
            try:
                body = json.loads(text)
            except ValueError:
                body = {"text": text}
        return body, {"server": app, "ms": ms}


def from_workspace() -> McpHost:
    """An McpHost acting as this app's service principal."""
    import requests
    from databricks.sdk import WorkspaceClient

    w = WorkspaceClient()

    def resolve(app: str) -> str:
        return w.apps.get(app).url

    def post(url: str, headers: dict, body: dict) -> tuple[int, str]:
        r = requests.post(safe_mcp_url(url), headers=headers, json=body, timeout=TIMEOUT_S,
                          allow_redirects=False)
        return r.status_code, r.text

    return McpHost(resolve, w.config.authenticate, post).connect()
