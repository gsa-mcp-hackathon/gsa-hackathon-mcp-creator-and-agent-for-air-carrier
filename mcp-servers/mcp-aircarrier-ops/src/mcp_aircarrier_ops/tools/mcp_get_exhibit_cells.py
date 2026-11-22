"""Get one PDF exhibit table cells record.

Show every cell of one PDF exhibit table, in row then column order.

Source: exhibit_cells (uc_table).
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

TABLE = qualified(
    sources.EXHIBIT_CELLS_CATALOG,
    sources.EXHIBIT_CELLS_SCHEMA,
    sources.EXHIBIT_CELLS_TABLE,
)
COLUMNS = sources.EXHIBIT_CELLS_COLUMNS
AS_OF = sources.EXHIBIT_CELLS_AS_OF


def register(mcp: FastMCP) -> None:
    """Register the carrier_get_exhibit_cells tool with the MCP server."""

    @mcp.tool(
        name="carrier_get_exhibit_cells",
        annotations={
            "title": "Get one PDF exhibit table cells record",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    def carrier_get_exhibit_cells(
        table_id: Annotated[
            str,
            Field(
                description=("Exact table id to fetch."),
                max_length=40,
            ),
        ],
        limit: Annotated[
            int,
            Field(description="Maximum cells to return.", ge=1, le=2000),
        ] = 500,
        offset: Annotated[
            int,
            Field(description="Cells to skip, in row then column order.", ge=0),
        ] = 0,
    ) -> dict[str, Any]:
        """Show every cell of one PDF exhibit table, in row then column order.

        One record is one cell of one PDF table on one page; value verbatim, value_num
        exact decimal string, with row_header, col_header chain and page legends. The
        source refreshes rebuilt on demand when the corpus changes and currently
        reflects 2026-11-08.

        Returns: Every cell of that table in row then column order, paged (total,
        count, has_more, next_offset). A table holds 2 to about 1,600 cells. An error
        with a hint when nothing matches.

        Does not cover: Attribute a budget column to a hull (that is the Attributor's
        job and stays DERIVED); Sum total_dollars_obligated or announced modifications
        as obligations; Write to, promote, or edit any table.
        """
        try:
            key_column = column("table_id", COLUMNS)
            order_by = ", ".join(
                column(c, COLUMNS) for c in ("page", "row_idx", "col_idx")
            )
            select_list = ", ".join(column(c, COLUMNS) for c in COLUMNS)
            totals = run_query(
                f"SELECT COUNT(*) AS total FROM {TABLE} "  # nosemgrep # nosec B608
                f"WHERE {key_column} = ?",
                [table_id],
            )
            total = int(totals[0]["total"]) if totals else 0
            rows = run_query(
                f"SELECT {select_list} FROM {TABLE} "  # nosemgrep # nosec B608
                f"WHERE {key_column} = ? ORDER BY {order_by} LIMIT ? OFFSET ?",
                [table_id, limit, offset],
            )
        except (ValueError, WarehouseError) as error:
            return {
                "error": str(error),
                "hint": "Check the identifier format and try again.",
            }
        if not total:
            return {
                "error": f"No record matched {table_id!r}.",
                "hint": (
                    "Identifiers are exact. Find a table_id with "
                    "carrier_search_exhibit_cells, or read the "
                    "mcp://dictionary/sources resource for the field list."
                ),
                "as_of": AS_OF,
            }
        next_offset = offset + len(rows)
        return {
            "as_of": AS_OF,
            "table_id": table_id,
            "total": total,
            "count": len(rows),
            "offset": offset,
            "has_more": next_offset < total,
            "next_offset": next_offset if next_offset < total else None,
            "cells": rows,
            "fields_used": ["table_id"],
        }
