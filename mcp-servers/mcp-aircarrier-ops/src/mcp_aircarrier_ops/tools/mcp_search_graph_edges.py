"""Search Knowledge graph edges.

Find Knowledge graph edges records whose text mentions something.

Source: graph_edges (uc_table).
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
from mcp_aircarrier_ops.models import RelValue
from mcp_aircarrier_ops.output_models import SearchResult

TABLE = qualified(
    sources.GRAPH_EDGES_CATALOG,
    sources.GRAPH_EDGES_SCHEMA,
    sources.GRAPH_EDGES_TABLE,
)
COLUMNS = sources.GRAPH_EDGES_COLUMNS
AS_OF = sources.GRAPH_EDGES_AS_OF


def register(mcp: FastMCP) -> None:
    """Register the carrier_search_graph_edges tool with the MCP server."""

    @mcp.tool(
        name="carrier_search_graph_edges",
        annotations={
            "title": "Search Knowledge graph edges",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    def carrier_search_graph_edges(
        query: Annotated[
            str,
            Field(
                description=(
                    "Keywords to match. This is a substring match, not a semantic "
                    "search."
                ),
                max_length=200,
            ),
        ],
        rel: Annotated[
            RelValue,
            Field(
                description=(
                    "Narrow results to one relation. Use prime_contract_for, "
                    "excluded_from, collides_with or resolved_not_this_hull to ask "
                    "whether a contract number is safe for CVN-79."
                ),
            ),
        ] = RelValue.ANY,
        rule: Annotated[
            str,
            Field(
                description=(
                    "Narrow results to one build rule, exact spelling, e.g. "
                    "'regex:piid_full', 'seed:keyset.hard_exclusions', "
                    "'store:pdf_tables.title_block'. Leave empty for all."
                ),
                max_length=80,
            ),
        ] = "",
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
    ) -> SearchResult:
        """Find Knowledge graph edges records whose text mentions something.

        One record is one directed edge src -rel-> dst between typed node ids
        (type:key). The source refreshes rebuilt by the Knowledge Graph Build notebook
        and currently reflects 2026-11-08.

        Returns: A pagination envelope with total, count, offset, has_more, next_offset,
        and the matching records.

        Does not cover: Attribute a budget column to a hull (that is the Attributor's
        job and stays DERIVED); Sum total_dollars_obligated or announced modifications
        as obligations; Write to, promote, or edit any table.
        """
        filter_rel = "" if rel is RelValue.ANY else rel.value
        filter_rule = rule.strip()
        clauses: list[str] = []
        params: list[Any] = []
        if filter_rel:
            clauses.append(column("rel", COLUMNS) + " = ?")
            params.append(filter_rel)
        if filter_rule:
            clauses.append(column("rule", COLUMNS) + " = ?")
            params.append(filter_rule)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        # src and dst hold node ids such as contract:N00024-09-C-2116; seed edges
        # carry no evidence text, so searching evidence_text alone misses them.
        text_columns = ["src", "dst", "evidence_text"]
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
                f"ORDER BY {column('edge_id', COLUMNS)} "  # stable offset paging
                "LIMIT ? OFFSET ?",
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
            "items": rows,
            "fields_searched": text_columns,
        }
