"""Search PDF exhibit table cells.

Find PDF exhibit table cells records whose text mentions something.

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
from mcp_aircarrier_ops.models import ExtractorValue, ValueKindValue

# A search hit only needs enough of a cell to recognise it; one prose cell
# measured 5 KB. Full text: docs_get_table on the docs server.
MAX_VALUE_CHARS = 400


CLIPPED_FIELDS = ("value", "row_header", "col_header")


def _clip(row: dict[str, Any]) -> dict[str, Any]:
    out = row
    for name in CLIPPED_FIELDS:
        text = row.get(name)
        if isinstance(text, str) and len(text) > MAX_VALUE_CHARS:
            if out is row:
                out = dict(row)
            out[name] = text[:MAX_VALUE_CHARS]
            out[f"{name}_truncated"] = True
            out[f"{name}_chars"] = len(text)
    return out


TABLE = qualified(
    sources.EXHIBIT_CELLS_CATALOG,
    sources.EXHIBIT_CELLS_SCHEMA,
    sources.EXHIBIT_CELLS_TABLE,
)
COLUMNS = sources.EXHIBIT_CELLS_COLUMNS
AS_OF = sources.EXHIBIT_CELLS_AS_OF


def register(mcp: FastMCP) -> None:
    """Register the carrier_search_exhibit_cells tool with the MCP server."""

    @mcp.tool(
        name="carrier_search_exhibit_cells",
        annotations={
            "title": "Search PDF exhibit table cells",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    def carrier_search_exhibit_cells(
        query: Annotated[
            str,
            Field(
                description=(
                    "Keywords to match. This is a substring match, not a semantic "
                    "search."
                ),
            ),
        ],
        value_kind: Annotated[
            ValueKindValue,
            Field(
                description=("Narrow results to one value kind."),
            ),
        ] = ValueKindValue.ANY,
        extractor: Annotated[
            ExtractorValue,
            Field(
                description=("Narrow results to one extractor."),
            ),
        ] = ExtractorValue.ANY,
        limit: Annotated[
            int,
            Field(
                description="Maximum rows to return.",
                ge=1,
                le=100,
            ),
        ] = 20,
        offset: Annotated[
            int,
            Field(
                description="Rows to skip from the start.",
                ge=0,
            ),
        ] = 0,
    ) -> dict[str, Any]:
        """Find PDF exhibit table cells records whose text mentions something.

        One record is one cell of one PDF table on one page; value verbatim, value_num
        exact decimal string, with row_header, col_header chain and page legends. The
        source refreshes rebuilt on demand when the corpus changes and currently
        reflects 2026-11-08.

        Returns: A pagination envelope with total, count, offset, has_more, next_offset,
        and the matching records.

        Does not cover: Attribute a budget column to a hull (that is the Attributor's
        job and stays DERIVED); Sum total_dollars_obligated or announced modifications
        as obligations; Write to, promote, or edit any table.
        """
        filter_value_kind = "" if value_kind is ValueKindValue.ANY else value_kind.value
        filter_extractor = "" if extractor is ExtractorValue.ANY else extractor.value
        clauses: list[str] = []
        params: list[Any] = []
        if filter_value_kind:
            clauses.append(column("value_kind", COLUMNS) + " = ?")
            params.append(filter_value_kind)
        if filter_extractor:
            clauses.append(column("extractor", COLUMNS) + " = ?")
            params.append(filter_extractor)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        # The verbatim cell, its row label and its header chain are what an analyst
        # searches by ("Basic Construction", "FY 2013", "13,409.970").
        text_columns = ["value", "row_header", "col_header", "table_id"]
        try:
            probe = f"%{query.strip().lower()}%"
            likes = [
                f"lower(CAST({column(c, COLUMNS)} AS STRING)) LIKE ?"
                for c in text_columns
            ]
            search_clause = "(" + " OR ".join(likes) + ")"
            if where:
                joined = f"{where} AND {search_clause}"  # nosemgrep
            else:
                joined = f" WHERE {search_clause}"  # nosemgrep
            bound = list(params) + [probe] * len(text_columns)
            totals = run_query(
                "SELECT COUNT(*) AS total "  # nosemgrep # nosec B608
                f"FROM {TABLE}{joined}",
                bound,
            )
            total = int(totals[0]["total"]) if totals else 0
            rows = run_query(
                f"SELECT * FROM {TABLE}{joined} "  # nosemgrep # nosec B608
                "ORDER BY "  # stable offset paging
                + ", ".join(
                    column(c, COLUMNS) for c in ("table_id", "row_idx", "col_idx")
                )
                + " LIMIT ? OFFSET ?",
                bound + [limit, offset],
            )
        except (ValueError, WarehouseError) as error:
            return {
                "error": str(error),
                "hint": "Try a shorter query, or drop a filter.",
            }
        next_offset = offset + len(rows)
        return {
            "as_of": AS_OF,
            "total": total,
            "count": len(rows),
            "offset": offset,
            "has_more": next_offset < total,
            "next_offset": next_offset if next_offset < total else None,
            "items": [_clip(r) for r in rows],
            "fields_searched": text_columns,
        }
