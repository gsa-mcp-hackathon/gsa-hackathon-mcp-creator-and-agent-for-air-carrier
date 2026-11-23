"""Return models for the docs_ tools.

Each docs_ tool declares one of these as its return type, so its MCP listing
carries an output schema: a client and its model can see what comes back
before calling. The same convention as the One Hub server
(the-one-hub/ops-center/mcp/hub_models.py).

The tools still return the service's plain dicts; FastMCP checks each result
against the schema before it leaves the server. So the rules here are:

* A field is required only when service.py sets it on every path.
* A value read from a document (a unit, a continuation link) is nullable.
* Every model allows extra keys, so a tool that adds a field, and the
  source_notice a result can carry, still validate.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class _Out(BaseModel):
    model_config = ConfigDict(extra="allow")


class StatusResult(_Out):
    documents: int = Field(description="Loaded PDFs.")
    pages: int
    tables: int
    chunks: int = Field(description="Search passages: whole tables and prose windows.")
    by_kind: dict[str, int] = Field(description="Documents per kind, e.g. budget_justification.")
    inferred_continuations: int = Field(description="Table links the server inferred across pages.")
    loaded_at: str | None = Field(description="UTC time the corpus was loaded; 'fixture' in tests.")
    grade: str = Field(description="How far a value read here can be relied on.")


class DocumentSummary(_Out):
    artifact_id: str = Field(description="16-hex id; pass it to the other docs_ tools.")
    filename: str
    kind: str = Field(description="budget_justification, selected_acquisition_report, gao_report ...")
    budget_cycle: str = Field(description="President's Budget cycle, e.g. PB2024. Empty when none.")
    pages: int
    tables: int


class DocumentMapResult(_Out):
    artifact_id: str
    filename: str
    kind: str
    pages: int
    sections: list[dict[str, Any]] = Field(
        description="Page ranges with their labels (exhibit, line_item, section), at most 400.")
    truncated: bool = Field(description="True when the document has more than 400 sections.")


class PageTable(_Out):
    table_id: str = Field(description="Pass to docs_get_table.")
    n_rows: int
    n_cols: int
    unit: str | None = Field(description="Printed unit of the table, when one was found.")
    continuation_of: str | None = Field(description="The table this one continues, if any.")


class PageResult(_Out):
    artifact_id: str
    filename: str
    page: int
    labels: dict[str, Any] = Field(description="Structural labels of the page (exhibit, line item).")
    text: str
    truncated: bool = Field(description="True when the text was cut at max_chars.")
    tables: list[PageTable]


class TablePart(_Out):
    table_id: str
    page: int
    unit: str | None = Field(description="Printed unit of this page's table.")
    column_headers: list[Any]
    markdown: str = Field(description="The table as printed.")
    numeric_cells: list[dict[str, Any]] = Field(
        description="Each numeric cell: row, col, text, row_header, col_header, scale, value, "
                    "value_musd, and on a ship cost exhibit ship_fy, hull and "
                    "share_of_total_ship_estimate_pct.")


class TableResult(_Out):
    filename: str
    artifact_id: str
    pages: list[int] = Field(description="The first page and every continuation page.")
    tables: list[TablePart] = Field(description="One entry per page of the table.")
    tieouts: list[dict[str, Any]] = Field(
        description="Each total checked against its rows: rule, row, printed, computed, passed.")
    tieout_status: Literal["no_totals_found", "pass", "fail"] = Field(
        description="Use the cells as arithmetic only when this is pass.")
    grade: str


class LineItemResult(_Out):
    line_item: str
    exhibit: str | None
    budget_cycle: str | None = Field(description="The cycle asked for, normalized, e.g. PB2024.")
    loaded_cycles: list[str] = Field(description="Every J-book cycle that is loaded.")
    sections: list[dict[str, Any]] = Field(
        description="One per exhibit per book: pages, artifact_id, filename, budget_cycle, "
                    "tables and table_chains (ids for docs_get_table).")
    note: str


class SearchResult(_Out):
    query: str
    n: int
    hits: list[dict[str, Any]] = Field(
        description="Each hit: chunk_id, score, kind, artifact_id, filename, page, table_id, "
                    "labels, text.")
    note: str
    premise_flags: list[dict[str, Any]] | None = Field(
        None, description="Present when the query names a known premise trap: term and why.")


class FigureResult(_Out):
    value_musd: str
    tolerance_musd: str
    n_table_cells: int
    n_text_hits: int
    documents: list[str] = Field(description="Filenames that print the figure.")
    table_cells: list[dict[str, Any]]
    text_hits: list[dict[str, Any]]
    found: bool = Field(description="False means no loaded document prints the figure.")


class CompareSummary(_Out):
    n: int
    found: int
    in_a_budget_exhibit_or_sar: int
    not_found: list[str]


class CompareResult(_Out):
    figures: list[dict[str, Any]] = Field(
        description="One per claimed figure: label, value_musd, found, documents, "
                    "document_kinds, authoritative, first_cell, first_text.")
    summary: CompareSummary
    reading: str = Field(description="How to read authoritative versus secondary.")


class TieoutDocumentResult(_Out):
    artifact_id: str
    filename: str
    tables_checked: int
    checks: int
    passed: int
    failed: int
    failed_within_rounding_bound: int
    failures: list[dict[str, Any]] = Field(description="The failed checks, at most 60.")
    tables_without_totals: int
    reading: str


class TieoutSummary(_Out):
    checks: int
    failed: int
    failed_within_rounding_bound: int


class ParsePdfResult(_Out):
    artifact_id: str
    n_pages: int
    filename: str
    kind: str
    map: list[dict[str, Any]] = Field(description="The document's structure, as page ranges.")
    tables: list[dict[str, Any]] = Field(description="At most 60 tables, each with its markdown.")
    tieouts: list[dict[str, Any]] = Field(description="At most 120 tie-out checks.")
    tieout_summary: TieoutSummary
    persisted: bool = Field(description="Always false: nothing is stored.")
    note: str
    grade: str
