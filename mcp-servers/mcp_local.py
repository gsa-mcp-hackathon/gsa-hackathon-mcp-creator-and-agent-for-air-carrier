"""Run the Air Carrier MCP servers in-process when the connector cannot reach them.

Why this exists
---------------
Genie Code reaches each server (a Databricks App) through a connector that
mints a per-user OAuth token for the app. When that token cannot be minted,
for example because the user's connector authorization has expired, every tool
call fails with "Failed to generate OAuth token" before the request reaches the
app. The servers are healthy in that case; only the transport is down.

What this does
--------------
It imports the deployed server's own package from its workspace source folder.
It builds the same FastMCP instance and calls tools through FastMCP's in-memory
client, so the same tool code, validation, schemas and error handling run. The
only part swapped is the server's single SQL entry point, which uses the
caller's Spark session instead of the app's warehouse connection.

What changes, and why it is safe
--------------------------------
* Identity: queries run as the person calling, under their own Unity Catalog
  grants, not as the app service principal. Nobody gets data they could not
  already read, and every result is labeled with transport and identity.
* Writes: refused by default. A tool that writes, such as the analyst lead log,
  gets the server's own WarehouseError and degrades the way it already does
  when the warehouse fails. allow_writes=True turns writes on, for a deliberate
  case only, because the audit trail would then name the person instead of the app.
* Source: the code is the workspace source folder the app deploys from. If
  that folder has changed since the last deployment, results can differ from
  the deployed app, so source_path and the deployment id go into every result.

Use
---
    import sys; sys.path.insert(0, "/Workspace/Users/xiaobing.shang1.civ@mail.mil/gsa-hackathon-mcp-creator-and-agent-for-cvn/mcp-servers")
    import mcp_local
    mcp_local.call("docs", "docs_search", query="Cost Limitation Baseline", top_k=3)
    mcp_local.list_tools("ops")

It needs fastmcp>=3.2,<4 in the session (the servers pin the same range).
mcp-a-creator is excluded on purpose: it writes projects and deploys apps,
and it should run only as itself.
"""
from __future__ import annotations

import asyncio
import importlib
import json
import os
import re
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Server:
    app: str               # Databricks App name
    package: str           # top-level package with app.py
    warehouse: str         # module holding the SQL entry point
    run_name: str          # the entry point's name in that module

    @property
    def src(self) -> Path:
        return ROOT / self.app / "src"


SERVERS: dict[str, Server] = {
    "docs": Server("mcp-aircarrier-docs", "mcp_aircarrier_docs", "mcp_aircarrier_docs.warehouse", "run"),
    "analyst": Server("mcp-aircarrier-analyst", "mcp_aircarrier_analyst", "mcp_aircarrier_analyst.warehouse", "run"),
    "ops": Server("mcp-aircarrier-ops", "mcp_aircarrier_ops", "mcp_aircarrier_ops.data.warehouse", "run_query"),
}

READ_FIRST = {"SELECT", "WITH", "SHOW", "DESCRIBE", "DESC", "EXPLAIN", "VALUES"}
WRITE_WORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|MERGE|CREATE|DROP|ALTER|TRUNCATE|GRANT|REVOKE|COPY|OPTIMIZE|"
    r"VACUUM|REFRESH|REPLACE|RESTORE|SET|USE|CALL)\b", re.I)
_STRINGS = re.compile(r"'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"|`[^`]*`")
_COMMENTS = re.compile(r"--[^\n]*|/\*.*?\*/", re.S)

_loaded: dict[str, dict[str, Any]] = {}
_lock = threading.Lock()


def is_read_only(sql: str) -> bool:
    """True only for a single statement that starts with a read keyword and has no write keyword.

    Conservative on purpose: string literals, quoted identifiers and comments are
    removed first, then any write keyword anywhere refuses the statement.
    """
    body = _STRINGS.sub("''", _COMMENTS.sub(" ", sql or "")).strip().lstrip("(").strip()
    if not body or ";" in body.rstrip(";"):
        return False
    first = body.split(None, 1)[0].upper()
    return first in READ_FIRST and not WRITE_WORDS.search(body)


def spark_runner(spark, module, allow_writes: bool = False) -> Callable[..., list[dict]]:
    """A drop-in for the server's warehouse entry point, backed by the caller's Spark session.

    Same contract: (sql, params) with ? markers, at most MAX_ROWS rows as dicts
    of plain values, and failures raised as the module's own sanitized
    WarehouseError, so the tool code handles them exactly as it does in the app.
    """
    err = module.WarehouseError
    plain = getattr(module, "_plain", lambda v: v)
    max_rows = int(getattr(module, "MAX_ROWS", 20000))

    def run(sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
        if not allow_writes and not is_read_only(sql):
            raise err("In-process mode is read-only: this statement was not run. "
                      "Writes go through the deployed app, as its service principal.")
        try:
            df = spark.sql(sql, args=list(params)) if params else spark.sql(sql)
            rows = df.take(max_rows) if df.columns else []
        except err:
            raise
        except Exception as e:  # sanitized like the app: no upstream text, only the class
            raise err(f"The query failed in the caller's session ({type(e).__name__}). "
                      "Check the caller's Unity Catalog grants on the table.") from None
        return [{k: plain(v) for k, v in r.asDict(recursive=True).items()} for r in rows]

    return run


def _env_from_app_yaml(server: Server) -> None:
    """Set the literal env values app.yaml gives the app, without overriding the caller's."""
    path = server.src.parent / "app.yaml"
    if not path.exists():
        return
    name = None
    for line in path.read_text().splitlines():
        s = line.strip()
        if s.startswith("- name:"):
            name = s.split(":", 1)[1].strip()
        elif s.startswith("value:") and name:
            os.environ.setdefault(name, s.split(":", 1)[1].strip().strip('"').strip("'"))
            name = None
        elif s.startswith("valueFrom:"):
            name = None


def _top_level(src: Path) -> list[str]:
    return sorted(p.name for p in src.iterdir() if p.is_dir() and (p / "__init__.py").exists())


def _conflicts(src: Path) -> list[str]:
    """Top-level packages this server needs that are already imported from somewhere else."""
    out = []
    for name in _top_level(src):
        mod = sys.modules.get(name)
        where = getattr(mod, "__file__", None) if mod else None
        if mod is not None and (where is None or not Path(where).resolve().is_relative_to(src.resolve())):
            out.append(f"{name} (already imported from {where or 'a namespace package'})")
    return out


def _deployment(app: str) -> str | None:
    try:
        from databricks.sdk import WorkspaceClient
        a = WorkspaceClient().apps.get(app)
        return a.active_deployment.deployment_id if a.active_deployment else None
    except Exception:  # informative only
        return None


def _stash(names: list[str]) -> dict[str, Any]:
    """Remove these top-level packages (and their submodules) from sys.modules; return them."""
    out = {}
    for k in list(sys.modules):
        if k.split(".", 1)[0] in names:
            out[k] = sys.modules.pop(k)
    return out


def load(name: str, spark=None, allow_writes: bool = False, isolate: bool = True) -> dict[str, Any]:
    """Import one server with its SQL entry point bound to Spark; cached per session.

    Package clash: the analyst ships a top-level package named core, and so does
    the Air Carrier bundle. With isolate (the default), the session's copy is set
    aside while the server imports, and then put back. The server keeps
    references to its own copy. That is safe only because the servers import
    everything at module top level (checked: no imports inside functions), so
    nothing resolves the name again later. isolate=False refuses instead.
    """
    if name not in SERVERS:
        raise KeyError(f"unknown server {name!r}; one of {sorted(SERVERS)}")
    with _lock:
        if name in _loaded:
            if _loaded[name]["allow_writes"] != allow_writes:
                raise RuntimeError(f"{name} is already loaded with allow_writes="
                                   f"{_loaded[name]['allow_writes']}; start a new session to change it")
            return _loaded[name]
        server = SERVERS[name]
        if not server.src.is_dir():
            raise FileNotFoundError(f"no source folder at {server.src}")
        clash = _conflicts(server.src)
        if clash and not isolate:
            raise ImportError(f"{server.app} cannot load in this session; package name clash: "
                              + "; ".join(clash) + ". Use a fresh session, or isolate=True.")
        clash_names = [c.split(" ", 1)[0] for c in clash]
        try:
            import fastmcp  # noqa: F401
        except ImportError:
            raise ImportError("fastmcp is not installed in this session; install "
                              "'fastmcp>=3.2,<4' 'mcp>=1.24,<2' (the range the servers pin)") from None
        if spark is None:
            from pyspark.sql import SparkSession
            spark = SparkSession.getActiveSession() or SparkSession.builder.getOrCreate()
        _env_from_app_yaml(server)
        saved = _stash(clash_names)
        sys.path.insert(0, str(server.src))
        try:
            # Patch before the tools import: some tools bind the entry point by name.
            wh = importlib.import_module(server.warehouse)
            setattr(wh, server.run_name, spark_runner(spark, wh, allow_writes))
            app = importlib.import_module(f"{server.package}.app")
        finally:
            # The server's copies of clashing packages leave sys.modules; the session's come back.
            _stash(clash_names)
            sys.modules.update(saved)
            sys.path.remove(str(server.src))
            if not clash_names:
                sys.path.insert(0, str(server.src))
        try:
            who = spark.sql("SELECT current_user() AS u").first()["u"]
        except Exception:
            who = None
        _loaded[name] = {"server": server, "mcp": app.mcp, "allow_writes": allow_writes,
                         "identity": who, "source_path": str(server.src.parent),
                         "isolated": clash_names,
                         "deployment_id": _deployment(server.app)}
        return _loaded[name]


def _run_async(coro):
    """Run a coroutine whether or not this thread already has an event loop (notebooks do)."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    box: dict[str, Any] = {}

    def target():
        try:
            box["v"] = asyncio.run(coro)
        except BaseException as e:  # re-raised in the caller's thread
            box["e"] = e
    t = threading.Thread(target=target, daemon=True)
    t.start()
    t.join()
    if "e" in box:
        raise box["e"]
    return box["v"]


def _meta(entry: dict) -> dict:
    return {"transport": "in-process", "identity": entry["identity"], "app": entry["server"].app,
            "source_path": entry["source_path"], "deployment_id": entry["deployment_id"],
            "writes": "allowed" if entry["allow_writes"] else "refused"}


def list_tools(name: str, spark=None) -> list[dict]:
    entry = load(name, spark)
    from fastmcp import Client

    async def go():
        async with Client(entry["mcp"]) as c:
            return await c.list_tools()
    return [{"name": t.name, "description": (t.description or "").split("\n", 1)[0]}
            for t in _run_async(go())]


def call(name: str, tool: str, spark=None, allow_writes: bool = False, **arguments) -> dict:
    """Call one tool exactly as the connector would. Returns {ok, result | error, _mcp}."""
    entry = load(name, spark, allow_writes)
    from fastmcp import Client

    async def go():
        async with Client(entry["mcp"]) as c:
            return await c.call_tool(tool, arguments, raise_on_error=False)
    res = _run_async(go())
    text = "\n".join(getattr(b, "text", "") for b in (res.content or []))
    if res.is_error:
        return {"ok": False, "error": text, "_mcp": _meta(entry)}
    body = res.structured_content
    if isinstance(body, dict) and set(body) == {"result"}:
        body = body["result"]
    if body is None:
        try:
            body = json.loads(text)
        except ValueError:
            body = text
    return {"ok": True, "result": body, "_mcp": _meta(entry)}
