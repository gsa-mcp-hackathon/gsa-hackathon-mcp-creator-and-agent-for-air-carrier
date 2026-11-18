"""Live reads from Unity Catalog, through the app's SQL warehouse resource.

The page backend (api.data) stays on the shipped JSON bundles, which is what
lets the product run at every access level including zero (D11). This module
is the second, optional path, used by the detail table, the decision
dashboard panels and the agent: when the app has a warehouse and SELECT on the
allowlisted tables it reads them live; when it does not, callers fall back to
the extracts in app/data/extracts/ (etl/build_extracts.py) and say so on
the page.

Authentication is the app's own service principal, which the Apps runtime
injects. Nothing here holds a token. The warehouse comes from the resource
bound under the key sql-warehouse (DATABRICKS_WAREHOUSE_ID via valueFrom).

The allowlist is the only set of tables this module will touch, and the agent
SQL guard enforces it before a statement leaves the process. The service
principal's grants enforce it again on the warehouse side.
"""
from __future__ import annotations

import os
import re
import threading
import time

from .sqlsafe import Fragment, compose, ident

CATALOG = os.environ.get("AIRCARRIER_CATALOG", "aircarrier")
SCHEMA = os.environ.get("AIRCARRIER_SCHEMA", "default")
PREFIX = os.environ.get("AIRCARRIER_STORE_PREFIX", "aircarrier_")
WAREHOUSE = os.environ.get("DATABRICKS_WAREHOUSE_ID", "").strip()

# logical name -> table suffix after the store prefix. Keep in step with the
# SELECT grants in deploy/grants_front_center.sql; checks/test_app.py compares
# the two so a table cannot be allowlisted here and left ungranted there.
# Source data is read ONLY through the read-only aircarrier_srcv_* views
# (B29, invariant 10). The app SP holds no grant on any src_ base table.
TABLES = {
    "transactions_2114": "srcv_fpds_2114_transactions",
    "transactions_2116": "srcv_fpds_2116_transactions",
    "file_c": "srcv_file_c_2114",
    "file_c_2116": "srcv_file_c_2116",
    "subawards": "srcv_subawards_2114",
    "pdf_tables": "pdf_tables",
    "pdf_cells": "pdf_cells",
    "claim": "claim",
    "gate": "gate",
    "mechanism": "mechanism",
    "analyst_leads": "analyst_leads",
    "collection_requirements": "collection_requirements",
    "variances": "variances",
}


def fqn(logical: str) -> str:
    """catalog.schema.table for a logical name, checked to be an identifier
    (the parts come from env vars, so a bad value fails here, not in SQL)."""
    return ident(f"{CATALOG}.{SCHEMA}.{PREFIX}{TABLES[logical]}")


class LiveError(RuntimeError):
    pass


_client = None
_lock = threading.Lock()


def _w():
    global _client
    with _lock:
        if _client is None:
            from databricks.sdk import WorkspaceClient
            _client = WorkspaceClient()
        return _client


_NUM = {"INT", "LONG", "SHORT", "BYTE", "BIGINT", "SMALLINT", "TINYINT"}
_FLT = {"DOUBLE", "FLOAT", "DECIMAL"}


def _cast(v, t: str):
    if v is None:
        return None
    try:
        if t in _NUM:
            return int(v)
        if t in _FLT:
            return float(v)
    except (TypeError, ValueError):
        return v
    return v


def query(sql: str, params: dict | None = None, row_limit: int = 5000,
          timeout_s: int = 60, client=None) -> tuple[list[str], list[dict]]:
    """Run one statement on the bound warehouse. Returns (columns, rows).

    client is a WorkspaceClient to run as. None means the app's service
    principal. Authority-bearing statements pass the end user's on-behalf-of
    client (api.identity.user_client), so Unity Catalog sees the user, and
    current_user() inside the statement is the user, not the app.
    """
    if not WAREHOUSE:
        raise LiveError("no SQL warehouse is bound to this app "
                        "(DATABRICKS_WAREHOUSE_ID is unset)")
    from databricks.sdk.service.sql import (StatementParameterListItem,
                                            StatementState)
    w = client or _w()
    plist = [StatementParameterListItem(name=k, value=None if v is None else str(v))
             for k, v in (params or {}).items()]
    r = w.statement_execution.execute_statement(
        statement=sql, warehouse_id=WAREHOUSE, catalog=CATALOG, schema=SCHEMA,
        parameters=plist or None, row_limit=row_limit, wait_timeout="30s")
    deadline = time.time() + timeout_s
    while r.status and r.status.state in (StatementState.PENDING, StatementState.RUNNING):
        if time.time() > deadline:
            try:
                w.statement_execution.cancel_execution(r.statement_id)
            finally:
                raise LiveError(f"statement exceeded {timeout_s}s")
        time.sleep(1.0)
        r = w.statement_execution.get_statement(r.statement_id)
    if not r.status or r.status.state != StatementState.SUCCEEDED:
        msg = (r.status.error.message if r.status and r.status.error else "unknown")
        raise LiveError(f"{r.status.state.value if r.status else 'FAILED'}: {msg}")
    cols = [c.name for c in r.manifest.schema.columns]
    types = [(c.type_name.value if c.type_name else "STRING") for c in r.manifest.schema.columns]
    data = list(r.result.data_array or []) if r.result else []
    nxt = r.result.next_chunk_index if r.result else None
    while nxt is not None:
        ch = w.statement_execution.get_statement_result_chunk_n(r.statement_id, nxt)
        data.extend(ch.data_array or [])
        nxt = ch.next_chunk_index
    rows = [{c: _cast(v, t) for c, t, v in zip(cols, types, row)} for row in data]
    return cols, rows


# --------------------------------------------------------------- availability
_status = {"checked": 0.0, "live": False, "reason": "not checked"}


def status(max_age_s: int = 120) -> dict:
    """Whether live reads work right now, and if not, why, in words a reader
    can act on. Probed with one cheap read and cached briefly, so a page does
    not pay a warehouse round trip on every render."""
    now = time.time()
    if now - _status["checked"] < max_age_s:
        return dict(_status)
    if not WAREHOUSE:
        _status.update(checked=now, live=False,
                       reason="No SQL warehouse is bound to the app, so tables "
                              "are read from the extracts shipped with it.")
    else:
        try:
            query(compose("SELECT 1 AS ok FROM {t} LIMIT 1", t=fqn("variances")),
                  row_limit=1, timeout_s=30)
            _status.update(checked=now, live=True, reason="")
        except Exception as exc:  # noqa: BLE001 - reported, not swallowed
            _status.update(checked=now, live=False,
                           reason=f"Live read failed, using shipped extracts: {exc}"[:400])
    _status["warehouse"] = WAREHOUSE or None
    return dict(_status)


_cache: dict[str, tuple[float, object]] = {}


def cached(key: str, ttl_s: int, fn):
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < ttl_s:
        return hit[1]
    val = fn()
    _cache[key] = (time.time(), val)
    return val


# ------------------------------------------------------------- agent SQL guard
_FORBID = re.compile(
    r"\b(insert|update|delete|merge|drop|create|alter|grant|revoke|truncate|copy|"
    r"optimize|vacuum|refresh|call|use|set|reset|msck|analyze|cache|uncache|"
    r"restore|clone|undrop|execute|declare|put|get|remove|list)\b", re.I)
_STR = re.compile(r"'(?:[^'\\]|\\.)*'")
_FROMFN = re.compile(r"(?i)\b(extract|trim|substring|position|overlay)\s*\([^()]*\)")


def allowed_tables() -> dict[str, str]:
    return {k: fqn(k) for k in TABLES}


def guard(sql: str, limit: int = 200) -> str:
    """Accept one read-only SELECT over allowlisted tables, or raise
    ValueError saying exactly why not. Returns the statement wrapped in an
    outer LIMIT."""
    s = (sql or "").strip().rstrip(";").strip()
    if not s:
        raise ValueError("empty statement")
    bare = _STR.sub("''", s)
    if ";" in bare:
        raise ValueError("one statement only")
    if not re.match(r"(?is)^\s*(select|with)\b", bare):
        raise ValueError("only SELECT or WITH ... SELECT is allowed")
    if _FORBID.search(bare):
        raise ValueError(f"keyword not allowed: {_FORBID.search(bare).group(1)}")
    # Mask the functions whose syntax contains FROM, so EXTRACT(year FROM d)
    # is not read as a table. Empty-argument calls such as current_date()
    # are collapsed first and the mask reapplied until stable, because the
    # mask only matches a paren group with no parens inside it. A subquery
    # cannot hide this way: it has parens and so is never masked.
    scan = re.sub(r"\b\w+\s*\(\s*\)", "f0", bare)
    while True:
        nxt = _FROMFN.sub("f0", scan)
        if nxt == scan:
            break
        scan = nxt
    ctes = {c.lower() for c in re.findall(r"(?i)(?:\bwith|,)\s*`?(\w+)`?\s+as\s*\(", scan)}
    ok = {v.lower() for v in allowed_tables().values()}
    for ref in re.findall(r"(?i)\b(?:from|join)\s+([`\w.]+)", scan):
        r = ref.replace("`", "").lower()
        if r in ctes or r in ok or f"{CATALOG}.{SCHEMA}.{r}".lower() in ok:
            continue
        raise ValueError(f"table not in the allowlist: {ref}. Allowed: "
                         + ", ".join(sorted(ok)))
    # s passed every check above, which is what makes it a Fragment here.
    return compose("SELECT * FROM ({q}) AS q LIMIT {n}", q=Fragment(s), n=int(limit))
