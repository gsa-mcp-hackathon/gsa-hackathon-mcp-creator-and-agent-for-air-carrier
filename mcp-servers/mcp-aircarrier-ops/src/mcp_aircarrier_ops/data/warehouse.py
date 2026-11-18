"""Databricks SQL warehouse access.

Two kinds of value reach a query and they are not interchangeable:

  - Identifiers (catalog, schema, table, column) cannot be bound as
    parameters, so they are validated against a plain identifier pattern and
    backtick-quoted.
  - Values (filters, dates, thresholds) are always bound as query parameters.
    Never concatenated into the statement.

Authentication works both locally (CLI profile or token) and inside a
Databricks App, where the platform injects the service principal credentials.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

from mcp_aircarrier_ops.config import settings

SAFE_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,254}$")
MAX_ROWS = 5000


class WarehouseError(RuntimeError):
    """A sanitized warehouse failure, safe to return to an MCP client."""


def quote_ident(part: str, label: str = "identifier") -> str:
    """Validate and backtick-quote one identifier.

    Raises:
        ValueError: if the part is not a plain identifier.
    """
    if not SAFE_IDENT.match(part or ""):
        raise ValueError(f"{label} is not a plain identifier")
    return f"`{part}`"


def qualified(*parts: str) -> str:
    """Build a quoted, dotted Unity Catalog name from validated parts."""
    return ".".join(quote_ident(p) for p in parts if p)


def column(name: str, allowed: tuple[str, ...]) -> str:
    """Quote a column name only if it is one of the known columns.

    An allowlist beats a pattern check: a caller cannot name a column the
    table does not have, so a typo fails loudly instead of leaking schema.

    Raises:
        ValueError: if the column is not in the allowlist.
    """
    if name not in allowed:
        raise ValueError(f"unknown column {name!r}")
    return quote_ident(name)


@lru_cache(maxsize=1)
def _connection_kwargs() -> dict[str, Any]:
    """Build connection arguments once, preferring OAuth over a token."""
    host = settings.databricks_host.replace("https://", "").rstrip("/")
    if not host:
        raise WarehouseError(
            "DATABRICKS_HOST is not set. Databricks Apps injects it; set it "
            "in .env for local development."
        )
    if not settings.databricks_warehouse_id:
        raise WarehouseError(
            "No SQL warehouse is configured. Bind one in app.yaml with "
            "'valueFrom: sql_warehouse', or set DATABRICKS_WAREHOUSE_ID."
        )
    kwargs: dict[str, Any] = {
        "server_hostname": host,
        "http_path": f"/sql/1.0/warehouses/{settings.databricks_warehouse_id}",
    }
    if settings.databricks_client_id and settings.databricks_client_secret:
        from databricks.sdk.core import Config, oauth_service_principal

        config = Config(
            host=f"https://{host}",
            client_id=settings.databricks_client_id,
            client_secret=settings.databricks_client_secret,
        )

        def credentials_provider():
            return oauth_service_principal(config)

        kwargs["credentials_provider"] = credentials_provider
    elif settings.databricks_token:
        kwargs["access_token"] = settings.databricks_token
    else:
        raise WarehouseError(
            "No Databricks credentials found. Inside an App these are "
            "injected; locally set DATABRICKS_TOKEN in .env."
        )
    return kwargs


def _plain(value: Any) -> Any:
    """Make a connector value JSON-safe without losing exactness.

    ARRAY columns (legends, history) arrive as numpy arrays, which the MCP
    serializer rejects. DECIMAL arrives as Decimal and is returned as its exact
    string, never a float, so a cost figure is never rounded in transit.
    """
    from decimal import Decimal

    if hasattr(value, "tolist"):
        return [_plain(v) for v in value.tolist()]
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, Decimal):
        return str(value)
    return value


def run_query(sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
    """Run a parameterized query and return at most MAX_ROWS rows as dicts.

    Raises:
        WarehouseError: with a sanitized message. Upstream errors are never
            returned verbatim, because they can carry credentials or data.
    """
    try:
        from databricks import sql as dbsql
    except ImportError as error:
        raise WarehouseError(
            "databricks-sql-connector is not installed. Add it to "
            "requirements.txt and pyproject.toml, then redeploy."
        ) from error

    kwargs = _connection_kwargs()
    try:
        with dbsql.connect(**kwargs) as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, params or [])
                if cursor.description is None:
                    return []
                columns = [c[0] for c in cursor.description]
                rows = cursor.fetchmany(MAX_ROWS)
        return [{k: _plain(v) for k, v in zip(columns, row)} for row in rows]
    except WarehouseError:
        raise
    except Exception:
        raise WarehouseError(
            "The warehouse query failed. Check that the app service "
            "principal has USE CATALOG, USE SCHEMA, SELECT on the table, "
            "and CAN USE on the warehouse."
        ) from None


def scalar(sql: str, params: list[Any] | None = None) -> Any:
    """Run a query and return the first column of the first row, or None."""
    rows = run_query(sql, params)
    if not rows:
        return None
    return next(iter(rows[0].values()))
