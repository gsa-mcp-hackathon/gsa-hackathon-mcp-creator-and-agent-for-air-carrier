"""Propose the tool surface for a design.

Phase 3. The designer proposes only tools the profiled fields can support,
and reports what it left out and why. Edit the result with the user before
generating: the tool names are the part they will read.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp import FastMCP
from pydantic import Field

from mcp_server_creator import designs
from mcp_server_creator.designer import (
    MAX_TOOLS,
    describe_reading,
    design_tools,
    parse_reading,
)


def _reading(plan: Any, jobs: list[str]) -> dict[str, Any]:
    """The recorded question a tool answers and how the tool reads it."""
    reading = describe_reading(plan) if plan.goal in jobs else None
    return {"question": plan.goal, "reading": reading} if reading else {}


def parse_readings(lines: list[str]) -> tuple[list[Any], list[str]]:
    """The readings that parse, and a note for each line that does not."""
    parsed: list[Any] = []
    notes: list[str] = []
    for number, line in enumerate(lines, start=1):
        reading, problem = parse_reading(line)
        if reading is None:
            notes.append(f"Reading {number} was ignored: {problem}")
        else:
            parsed.append(reading)
    return parsed, notes


def register(mcp: FastMCP) -> None:
    """Register the tool designer with the MCP server."""

    @mcp.tool(
        name="creator_design_tools",
        annotations={
            "title": "Design the tool surface",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    def creator_design_tools(
        design_id: Annotated[
            str,
            Field(
                max_length=16,
                pattern=r"^$|^dsn_[0-9a-f]{8}$",
                description=designs.DESIGN_ID_DESCRIPTION,
            ),
        ] = "",
        spec_json: Annotated[
            str, Field(max_length=500_000, description=designs.SPEC_JSON_DESCRIPTION)
        ] = "",
        drop: Annotated[
            list[Annotated[str, Field(max_length=64)]],
            Field(
                max_length=50,
                description=(
                    "Tool names to remove from the proposal, after the user "
                    "has looked at it."
                ),
            ),
        ] = [],
        keep_only: Annotated[
            list[Annotated[str, Field(max_length=64)]],
            Field(
                max_length=50,
                description=(
                    "Keep only these tool names. Use this when the user has "
                    "picked a short list; it beats dropping one at a time."
                ),
            ),
        ] = [],
        readings: Annotated[
            list[Annotated[str, Field(max_length=700)]],
            Field(
                max_length=20,
                description=(
                    "Corrections: '<question> => shape=ranking; "
                    "measure=<col>; group_by=<col>'."
                ),
            ),
        ] = [],
    ) -> dict[str, Any]:
        """Propose tools the data can support, and name what it cannot.

        One tool per question shape per source, named after the user's own
        questions where they were recorded. Three to six tools beats twelve:
        a model choosing between many similar tools chooses worse.

        The designer reads each question with rules, and rules misread
        phrasing they have not met. Each tool that answers a recorded
        question comes back with its `question` and its `reading`. Compare
        them. To correct one, call again with `readings`, one string per
        question:

            <question> => shape=ranking; aggregation=sum; measure=<column>;
            group_by=<column>; filters=<column>,<column>

        shape is total, ranking, trend (add granularity=day, week or month)
        or list (add key=<column>, the column whose value selects the
        records). aggregation is sum, avg, count or count_distinct. Columns
        are checked against the profiled source; a reading that does not fit
        is reported in `design_notes` and the designer's own reading is
        kept. Send every correction on each call. creator_review_server then
        compares every tool with the words of its question again.

        Returns: `tools` with each name, pattern, source, question and
        reading; `design_notes` saying what was left out and why;
        `review_first` reminding you to confirm the names with the user; and
        the updated `design_id`.
        """
        spec, _, failure = designs.resolve_result(design_id, spec_json)
        if failure:
            return failure
        assert spec is not None

        if not spec.data_sources:
            return {
                "error": "The design has no data sources yet.",
                "hint": (
                    "Call creator_add_data_source at least once. Without a "
                    "profiled source there is nothing to design against."
                ),
            }

        parsed, unread = parse_readings(readings)
        plans, notes = design_tools(spec, parsed)
        notes = unread + notes

        wanted = {name.strip() for name in keep_only if name.strip()}
        unwanted = {name.strip() for name in drop if name.strip()}
        if wanted:
            plans = [plan for plan in plans if plan.name in wanted]
            missing = wanted - {plan.name for plan in plans}
            if missing:
                notes.append(
                    "keep_only named tools the designer did not propose: "
                    + ", ".join(sorted(missing))
                )
        if unwanted:
            plans = [plan for plan in plans if plan.name not in unwanted]

        spec.tools = plans
        designs.persist(spec, design_id)

        by_source: dict[str, list[str]] = {}
        for plan in plans:
            by_source.setdefault(plan.source, []).append(plan.name)

        return {
            "design_id": design_id or "",
            "tools": [
                {
                    "name": plan.name,
                    "title": plan.title,
                    "goal": plan.goal,
                    "pattern": plan.pattern.value,
                    "source": plan.source,
                    "parameters": [param.name for param in plan.params],
                    "paginated": plan.paginated,
                    **_reading(plan, spec.jobs_to_be_done),
                }
                for plan in plans
            ],
            "tool_count": len(plans),
            "by_source": by_source,
            "design_notes": notes,
            "review_first": (
                "Read each tool name aloud to the person whose job it is. If "
                "they would not recognize it as something they do, rename "
                f"it. Drop anything they do not need: {MAX_TOOLS} tools is "
                "the ceiling for a focused server."
            ),
            "spec": spec.model_dump(mode="json") if not design_id else None,
            "next_step": (
                "Check each tool's reading against its question and correct "
                "any misreading with `readings`. Confirm the tool list with "
                "the user, then call creator_review_server, then "
                "creator_generate_project."
            ),
        }
