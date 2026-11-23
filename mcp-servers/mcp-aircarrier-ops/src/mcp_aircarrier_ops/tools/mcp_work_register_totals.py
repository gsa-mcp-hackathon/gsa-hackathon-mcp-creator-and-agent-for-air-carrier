"""Work register counts.

How much work is there, by kind, state and owner agent.

The tool used to sum exposure_usd_m, but that column is 0.0 on every row
(read 2026-11-18), so the sum was a confident but empty number. It now counts
work items and reports exposure only when some row actually carries it.

Source: work_register (uc_table). Module name kept for import stability; the
tool is registered as carrier_work_register_counts.
"""

from __future__ import annotations

from datetime import datetime, timezone
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
from mcp_aircarrier_ops.output_models import WorkRegisterCountsResult

TOOL_NAME = "carrier_work_register_counts"

# The register refreshes each dispatcher tick. A newest row older than this
# means the ticks stopped, and the counts describe that day, not today.
STALE_AFTER_DAYS = 2


def freshness_note(as_of: str, now: datetime | None = None) -> str | None:
    """Say how old the register is when its newest row is past STALE_AFTER_DAYS."""
    try:
        stamp = datetime.fromisoformat(str(as_of)[:19].replace("T", " "))
    except ValueError:
        return None
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    age = (now - stamp).days
    if age <= STALE_AFTER_DAYS:
        return None
    return (
        f"The newest work item was updated {stamp:%Y-%m-%d}, {age} days ago, so "
        "these counts describe the register on that date. Say so when you report them."
    )


TABLE = qualified(
    sources.WORK_REGISTER_CATALOG,
    sources.WORK_REGISTER_SCHEMA,
    sources.WORK_REGISTER_TABLE,
)
COLUMNS = sources.WORK_REGISTER_COLUMNS
AS_OF = sources.WORK_REGISTER_AS_OF


def register(mcp: FastMCP) -> None:
    """Register the carrier_work_register_counts tool with the MCP server."""

    @mcp.tool(
        name=TOOL_NAME,
        annotations={
            "title": "Count work items by kind, state and owner",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    def carrier_work_register_counts(
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
                    "Narrow by state. open = everything not closed or promoted "
                    "(use it for 'how many open ...'); human_review = claims waiting "
                    "for a person; open_question = needs investigation; "
                    "collection_required = needs data requested."
                ),
            ),
        ] = StateValue.ANY,
    ) -> WorkRegisterCountsResult:
        """How much work is open on the CVN-79 cost reconciliation, and where it sits:
        work items counted by kind, state and owner agent.

        One record is one work item (kind + ref_id) with its current state and
        owner_agent. Claims are extracted figures; most wait in human_review.
        The source refreshes each dispatcher tick.

        Returns: totals.record_count for the filtered scope, by_kind_state with a
        count per kind, state and owner_agent, the newest updated_at, and exposure
        only if some row carries a non-zero exposure_usd_m (today none does).

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
        try:
            kind_c = column("kind", COLUMNS)
            state_c = column("state", COLUMNS)
            owner_c = column("owner_agent", COLUMNS)
            exposure_c = column("exposure_usd_m", COLUMNS)
            updated_c = column("updated_at", COLUMNS)
            rows = run_query(
                f"SELECT {kind_c} AS kind, {state_c} AS state, "  # nosemgrep # nosec B608
                f"{owner_c} AS owner_agent, COUNT(*) AS records, "
                f"COUNT_IF({exposure_c} <> 0) AS with_exposure, "
                f"SUM({exposure_c}) AS exposure_usd_m, "
                f"CAST(MAX({updated_c}) AS STRING) AS last_updated "
                f"FROM {TABLE}{where} GROUP BY 1, 2, 3 ORDER BY records DESC",
                list(params),
            )
        except (ValueError, WarehouseError) as error:
            return {
                "error": str(error),
                "hint": "Drop a filter; every value must be one of the listed choices.",
            }
        record_count = sum(int(r.get("records") or 0) for r in rows)
        with_exposure = sum(int(r.get("with_exposure") or 0) for r in rows)
        updated = [r.get("last_updated") for r in rows if r.get("last_updated")]
        by_kind_state = [
            {
                "kind": r.get("kind"),
                "state": r.get("state"),
                "owner_agent": r.get("owner_agent"),
                "records": int(r.get("records") or 0),
            }
            for r in rows
        ]
        out: dict[str, Any] = {
            "as_of": max(updated) if updated else AS_OF,
            "totals": {"record_count": record_count},
            "by_kind_state": by_kind_state,
            "filters_applied": len(clauses),
        }
        note = freshness_note(out["as_of"])
        if note:
            out["freshness_note"] = note
        if with_exposure:
            out["exposure"] = {
                "records_with_exposure": with_exposure,
                "exposure_usd_m": sum(
                    float(r.get("exposure_usd_m") or 0) for r in rows
                ),
            }
        else:
            out["exposure_note"] = (
                "No work item carries a dollar exposure yet (exposure_usd_m is 0 on "
                "every row), so none is reported. Do not read this as $0 at risk."
            )
        return out
