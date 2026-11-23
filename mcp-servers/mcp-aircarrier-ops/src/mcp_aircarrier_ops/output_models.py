"""Return models for this server's tools.

Each tool declares one of these as its return type, so its MCP listing
carries an output schema: a client and its model can see what comes back
before calling. The same convention as the One Hub server
(the-one-hub/ops-center/mcp/hub_models.py).

The tools still return plain dicts; FastMCP checks each result against the
schema before it leaves the server. A tool here reports a failure as a body
with ``error`` and ``hint`` (error_contract.py marks it isError). So every
field is optional: a model names what a page of results carries, and a
failure body still validates. Every model allows extra keys.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _Out(BaseModel):
    model_config = ConfigDict(extra="allow")

    error: str | None = Field(
        None, description="Set when the call failed; the result is then isError."
    )
    hint: str | None = Field(None, description="What to do about the error.")
    as_of: Any = Field(None, description="When the source data was last loaded.")


class _Page(_Out):
    """One page of matching records, with what is needed to ask for the next."""

    total: int | None = Field(None, description="Matching records across every page.")
    count: int | None = Field(None, description="Records on this page.")
    offset: int | None = None
    has_more: bool | None = None
    next_offset: int | None = Field(
        None, description="Pass as offset for the next page; null on the last page."
    )


class SearchResult(_Page):
    items: list[dict[str, Any]] | None = Field(
        None, description="The matching records."
    )
    fields_searched: list[Any] | None = Field(
        None, description="The text columns the query was matched against."
    )


class ObligationsResult(SearchResult):
    contract: str | None = None
    order: str | None = None
    obligation_total: Any = Field(
        None,
        description="Sum of federal_action_obligation over every matching action.",
    )
    detail: str | None = Field(None, description="summary or full.")


class ExhibitCellsResult(_Page):
    table_id: str | None = None
    cells: list[dict[str, Any]] | None = Field(
        None, description="The table's cells in page, row and column order."
    )


class WorkRegisterCountsResult(_Out):
    totals: dict[str, Any] | None = Field(None, description="record_count.")
    by_kind_state: list[dict[str, Any]] | None = Field(
        None, description="Records per kind, state and owner_agent."
    )
    filters_applied: int | None = None
    exposure: dict[str, Any] | None = Field(
        None, description="Present only when a work item carries a dollar exposure."
    )
    exposure_note: str | None = None
