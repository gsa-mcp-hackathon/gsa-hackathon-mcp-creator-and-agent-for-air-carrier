"""Search Work register.

Find Work register records whose text mentions something.

Source: work_register (uc_table).
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
from mcp_aircarrier_ops.models import (
    KindValue,
    OwnerAgentValue,
    StateValue,
    state_clause,
)
from mcp_aircarrier_ops.output_models import SearchResult

TOOL_NAME = "carrier_search_work_register"

TABLE = qualified(
    sources.WORK_REGISTER_CATALOG,
    sources.WORK_REGISTER_SCHEMA,
    sources.WORK_REGISTER_TABLE,
)
COLUMNS = sources.WORK_REGISTER_COLUMNS
AS_OF = sources.WORK_REGISTER_AS_OF


def register(mcp: FastMCP) -> None:
    """Register the carrier_search_work_register tool with the MCP server."""

    @mcp.tool(
        name=TOOL_NAME,
        annotations={
            "title": "Search Work register",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    def carrier_search_work_register(
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
        owner_agent: Annotated[
            OwnerAgentValue,
            Field(
                description=(
                    "Narrow to one owner agent: investigator (open questions), "
                    "reader (documents in hand) or collect (data to request)."
                ),
            ),
        ] = OwnerAgentValue.ANY,
        kind: Annotated[
            KindValue,
            Field(
                description=(
                    "Narrow to one kind: claim (an extracted figure), gap, "
                    "variance or artifact (a source document)."
                ),
            ),
        ] = KindValue.ANY,
        state: Annotated[
            StateValue,
            Field(
                description=(
                    "Narrow by state. open = everything not closed or promoted; "
                    "human_review = claims waiting for a person; open_question = "
                    "needs investigation; collection_required = needs data requested."
                ),
            ),
        ] = StateValue.ANY,
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
        """Find Work register records whose text mentions something.

        One record is one work item (kind + ref_id) with its current state and
        owner_agent. The source refreshes each dispatcher tick and currently reflects
        2026-11-08.

        Returns: A pagination envelope with total, count, offset, has_more, next_offset,
        and the matching records.

        Does not cover: Attribute a budget column to a hull (that is the Attributor's
        job and stays DERIVED); Sum total_dollars_obligated or announced modifications
        as obligations; Write to, promote, or edit any table.
        """
        filter_owner_agent = (
            "" if owner_agent is OwnerAgentValue.ANY else owner_agent.value
        )
        filter_kind = "" if kind is KindValue.ANY else kind.value
        clauses: list[str] = []
        params: list[Any] = []
        if filter_owner_agent:
            clauses.append(column("owner_agent", COLUMNS) + " = ?")
            params.append(filter_owner_agent)
        if filter_kind:
            clauses.append(column("kind", COLUMNS) + " = ?")
            params.append(filter_kind)
        state_sql, state_params = state_clause(column("state", COLUMNS), state)
        if state_sql:
            clauses.append(state_sql)
            params.extend(state_params)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        text_columns = ["work_id", "ref_id", "state", "last_error"]
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
                f"ORDER BY {column('work_id', COLUMNS)} "  # stable offset paging
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
