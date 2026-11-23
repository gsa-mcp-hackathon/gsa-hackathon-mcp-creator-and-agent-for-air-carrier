"""Search the variance register: where public sources disagree, and why.

Round 2 of the delegation evaluation asked two questions whose answers live only
in the variance register (H08, FPDS-NG against USAspending; H09, two USAspending
products against each other). The work register carries variances as work items
but not their text, so no tool could return them.

Source: variances (uc_table).
"""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp import FastMCP
from pydantic import Field

from mcp_aircarrier_ops.data import sources
from mcp_aircarrier_ops.data.warehouse import (
    WarehouseError,
    column,
    qualified,
    run_query,
)
from mcp_aircarrier_ops.models import VarianceStatusValue
from mcp_aircarrier_ops.output_models import SearchResult

TOOL_NAME = "carrier_search_variances"

TABLE = qualified(
    sources.VARIANCES_CATALOG,
    sources.VARIANCES_SCHEMA,
    sources.VARIANCES_TABLE,
)
COLUMNS = sources.VARIANCES_COLUMNS
AS_OF = sources.VARIANCES_AS_OF
TEXT_COLUMNS = ("id", "title", "detail", "flag")
RETURNED = ("id", "status", "flag", "title", "detail")


def register(mcp: FastMCP) -> None:
    """Register the carrier_search_variances tool with the MCP server."""

    @mcp.tool(
        name=TOOL_NAME,
        annotations={
            "title": "Search the variance register (where public sources disagree)",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    def carrier_search_variances(
        query: Annotated[
            str,
            Field(
                description=(
                    "Words or a figure to find in the variance id, title or "
                    "detail, e.g. 'FPDS', 'E-16', '5,880,250' or '2114' "
                    "(substring, not semantic). Empty lists every variance."
                ),
                max_length=200,
            ),
        ] = "",
        status: Annotated[
            VarianceStatusValue,
            Field(
                description=(
                    "live = still open; resolved = explained and closed; "
                    "recorded = kept for provenance. any = no filter."
                ),
            ),
        ] = VarianceStatusValue.ANY,
        limit: Annotated[
            int,
            Field(description="Maximum rows to return.", ge=1, le=50),
        ] = 20,
        offset: Annotated[
            int,
            Field(description="Rows to skip from the start.", ge=0),
        ] = 0,
    ) -> SearchResult:
        """Find variances: places where two public sources disagree about a CVN-79
        figure, with both figures, the difference, which one to use and why. Use it
        when a question asks why two systems or documents give different numbers,
        for example FPDS-NG against USAspending, or one USAspending product
        against another.

        One record is one variance (E-1 to E-17) with its status, risk flag, title
        and detail. The register is published from the front center on each update.

        Returns: A pagination envelope with total, count, offset, has_more,
        next_offset and the matching variances.

        Does not cover: Resolve a variance or pick a figure the register leaves
        open; Write to, promote, or edit any table.
        """
        clauses: list[str] = []
        params: list[Any] = []
        if status is not VarianceStatusValue.ANY:
            clauses.append(column("status", COLUMNS) + " = ?")
            params.append(status.value)
        if query.strip():
            probe = f"%{query.strip().lower()}%"
            likes = [
                f"lower(CAST({column(c, COLUMNS)} AS STRING)) LIKE ?"
                for c in TEXT_COLUMNS
            ]
            clauses.append("(" + " OR ".join(likes) + ")")
            params.extend([probe] * len(TEXT_COLUMNS))
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        select_list = ", ".join(column(c, COLUMNS) for c in RETURNED)
        try:
            totals = run_query(
                f"SELECT COUNT(*) AS total FROM {TABLE}{where}",  # nosemgrep # nosec B608
                params,
            )
            total = int(totals[0]["total"]) if totals else 0
            rows = run_query(
                f"SELECT {select_list} FROM {TABLE}{where} "  # nosemgrep # nosec B608
                f"ORDER BY {column('id', COLUMNS)} LIMIT ? OFFSET ?",
                params + [limit, offset],
            )
        except (ValueError, WarehouseError) as error:
            return {
                "error": str(error),
                "hint": "Try a shorter query, or drop the status filter.",
            }
        next_offset = offset + len(rows)
        return {
            "as_of": AS_OF,
            "total": total,
            "count": len(rows),
            "offset": offset,
            "has_more": next_offset < total,
            "next_offset": next_offset if next_offset < total else None,
            "items": rows,
            "fields_searched": list(TEXT_COLUMNS),
        }
