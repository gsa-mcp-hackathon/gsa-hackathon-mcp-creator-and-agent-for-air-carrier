"""Databricks SQL warehouse access.

Values are bound as parameters and identifiers are validated. Errors are
sanitized: an upstream message can carry credentials or data, so it is never
returned verbatim. Inside a Databricks App the platform injects the service
principal's DATABRICKS_CLIENT_ID / DATABRICKS_CLIENT_SECRET and DATABRICKS_HOST.
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
TOKEN = re.compile(r"\{([a-z_][a-z0-9_]*)\}")
MAX_ROWS = 20000


class WarehouseError(RuntimeError):
    """A sanitized warehouse failure, safe to return to an MCP client."""


def table(name: str) -> str:
    if not SAFE_NAME.match(name or ""):
        raise ValueError(f"not a plain catalog.schema.table name: {name!r}")
    return ".".join("`" + p + "`" for p in name.split("."))


def render(template: str, *, tables: dict[str, str]) -> str:
    """Fill the {token}s of a constant SQL template with validated table names only.

    Caller-supplied values never pass through here; they are bound as ? parameters
    in run(). An unfilled token raises, so a template cannot run with a hole in it.
    """
    parts = {k: table(v) for k, v in tables.items()}

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
        raise WarehouseError("DATABRICKS_HOST is not set.")
    if not wh:
        raise WarehouseError("No SQL warehouse is configured (app.yaml valueFrom: sql-warehouse).")
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
    if isinstance(v, (list, tuple)):
        return [_plain(x) for x in v]
    if isinstance(v, Decimal):
        return str(v)
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return v


def run(sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
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
        raise WarehouseError("The warehouse statement failed. Check the app service principal has SELECT on "
                             "aircarrier_pdf_pages and aircarrier_pdf_tables and CAN USE on the warehouse.") from None
