"""Databricks SQL warehouse access (same contract as mcp-aircarrier-ops).

Values are always bound as parameters; identifiers come only from the vendored
core.catalog and are validated before use. Errors are sanitized: upstream
messages can carry credentials or data, so they are never returned verbatim.
Inside a Databricks App the platform injects the service principal's
DATABRICKS_CLIENT_ID / DATABRICKS_CLIENT_SECRET and DATABRICKS_HOST.
"""
from __future__ import annotations

import logging
import os
import re
from decimal import Decimal
from functools import lru_cache
from typing import Any

log = logging.getLogger(__name__)
SAFE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*){2}$")
SAFE_COL = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
TOKEN = re.compile(r"\{([a-z_][a-z0-9_]*)\}")
BAD_FRAGMENT = re.compile(r"[{};]|--|/\*")
MAX_ROWS = 20000


class WarehouseError(RuntimeError):
    """A sanitized warehouse failure, safe to return to an MCP client."""


def table(name: str) -> str:
    """Validate a three-part UC name and backtick-quote each part."""
    if not SAFE_NAME.match(name or ""):
        raise ValueError(f"not a plain catalog.schema.table name: {name!r}")
    return ".".join("`" + p + "`" for p in name.split("."))


def column(name: str) -> str:
    """Validate a plain column name and backtick-quote it."""
    if not SAFE_COL.match(name or ""):
        raise ValueError("not a plain column name: " + repr(name))
    return "`" + name + "`"


def render(template: str, *, tables: dict | None = None, cols: dict | None = None,
           ints: dict | None = None, repeat: dict | None = None) -> str:
    """Fill the {token}s of a constant SQL template with vetted pieces only.

    tables  token -> catalog.schema.table, validated and backtick-quoted
    cols    token -> column names, each validated, rendered CAST(`c` AS STRING) AS `c`
    ints    token -> non-negative integer (LIMIT)
    repeat  token -> (fragment, n, sep): a constant fragment of ? markers repeated n >= 1 times

    Caller-supplied values never pass through here; they are bound as ? parameters in run().
    An unfilled token raises, so a template cannot silently run with a hole in it.
    """
    parts: dict[str, str] = {}
    for k, v in (tables or {}).items():
        parts[k] = table(v)
    for k, v in (cols or {}).items():
        if not v:
            raise ValueError("empty column list for token " + k)
        parts[k] = ", ".join("CAST(" + column(c) + " AS STRING) AS " + column(c) for c in v)
    for k, v in (ints or {}).items():
        n = int(v)
        if n < 0:
            raise ValueError("negative integer for token " + k)
        parts[k] = str(n)
    for k, (frag, n, sep) in (repeat or {}).items():
        n = int(n)
        if n < 1 or "?" not in frag or BAD_FRAGMENT.search(frag) or BAD_FRAGMENT.search(sep):
            raise ValueError("bad repeated fragment for token " + k)
        parts[k] = sep.join([frag] * n)

    def fill(m: re.Match) -> str:
        if m.group(1) not in parts:
            raise KeyError("unfilled SQL token: " + m.group(1))
        return parts[m.group(1)]

    return TOKEN.sub(fill, template)


@lru_cache(maxsize=1)
def _connection_kwargs() -> dict[str, Any]:
    host = os.getenv("DATABRICKS_HOST", "").replace("https://", "").rstrip("/")
    wh = os.getenv("DATABRICKS_WAREHOUSE_ID", "")
    if not host:
        raise WarehouseError(
            "DATABRICKS_HOST is not set. "
            "This server reads Unity Catalog tables through a SQL warehouse, so it "
            "answers only inside a Databricks workspace. With no workspace, run "
            "mcp-aircarrier-hub or MCP A Creator, which work locally (README, Run "
            "an MCP server locally)."
        )
    if not wh:
        raise WarehouseError("No SQL warehouse is configured (app.yaml valueFrom: sql_warehouse).")
    kw: dict[str, Any] = {"server_hostname": host, "http_path": f"/sql/1.0/warehouses/{wh}"}
    cid, secret = os.getenv("DATABRICKS_CLIENT_ID", ""), os.getenv("DATABRICKS_CLIENT_SECRET", "")
    token = os.getenv("DATABRICKS_TOKEN", "")
    if cid and secret:
        from databricks.sdk.core import Config, oauth_service_principal

        cfg = Config(host=f"https://{host}", client_id=cid, client_secret=secret)
        kw["credentials_provider"] = lambda: oauth_service_principal(cfg)
    elif token:
        kw["access_token"] = token
    else:
        raise WarehouseError("No Databricks credentials found.")
    return kw


def _plain(v: Any) -> Any:
    if hasattr(v, "tolist"):
        return [_plain(x) for x in v.tolist()]
    if isinstance(v, Decimal):
        return str(v)
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return v


def run(sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
    """Run one parameterized statement; return rows as dicts (empty for DML)."""
    try:
        from databricks import sql as dbsql
    except ImportError as e:
        raise WarehouseError("databricks-sql-connector is not installed.") from e
    kw = _connection_kwargs()
    try:
        with dbsql.connect(**kw) as conn, conn.cursor() as cur:
            cur.execute(sql, params or [])
            if cur.description is None:
                return []
            cols = [c[0] for c in cur.description]
            rows = cur.fetchmany(MAX_ROWS)
        return [{k: _plain(v) for k, v in zip(cols, r)} for r in rows]
    except Exception as e:  # noqa: BLE001 - sanitized on purpose
        log.warning("warehouse statement failed: %s", type(e).__name__)
        raise WarehouseError(
            "The warehouse statement failed. Check the app service principal has SELECT on the "
            "aircarrier_src_* tables, SELECT and MODIFY on aircarrier_analyst_leads and "
            "aircarrier_analyst_outcomes, and CAN USE on the warehouse."
        ) from None
