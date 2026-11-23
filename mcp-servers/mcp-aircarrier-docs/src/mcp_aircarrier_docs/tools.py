"""MCP tools: validate, call the service, return. Every tool is read-only."""
from __future__ import annotations

from enum import Enum
from typing import Annotated, Any

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import BaseModel, Field

from docs_core import extract
from mcp_aircarrier_docs import service, store, volume, warehouse
from mcp_aircarrier_docs.output_models import (
    CompareResult,
    DocumentMapResult,
    DocumentSummary,
    FigureResult,
    LineItemResult,
    PageResult,
    ParsePdfResult,
    SearchResult,
    StatusResult,
    TableResult,
    TieoutDocumentResult,
)

READ = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}


class Kind(str, Enum):
    any = ""
    budget_justification = "budget_justification"
    selected_acquisition_report = "selected_acquisition_report"
    crs_report = "crs_report"
    gao_report = "gao_report"
    thesis_or_study = "thesis_or_study"
    regulation_or_manual = "regulation_or_manual"
    other = "other"


class Content(str, Enum):
    any = "any"
    table = "table"
    prose = "prose"


class Figure(BaseModel):
    label: str = Field("", max_length=120, description="What the figure is claimed to be.")
    value_musd: str = Field(..., max_length=32, description="The value in millions of dollars, e.g. 13409.97.")


AID = Annotated[str, Field(min_length=16, max_length=16, pattern=r"^[0-9a-f]{16}$",
                           description="16-hex artifact id from docs_list_documents.")]
TID = Annotated[str, Field(max_length=40, pattern=r"^[0-9a-f]{16}:\d{4}:\d{2}$",
                           description="Table id, e.g. bb2e90fd1d91a0bc:0095:00 (artifact:page:index).")]


def _guard(fn, *a, **k) -> Any:
    try:
        return fn(*a, **k)
    except (service.DocsError, volume.VolumeError, extract.ExtractError, warehouse.WarehouseError) as e:
        raise ToolError(str(e)) from None


def _c():
    return _guard(store.corpus)


def register_tools(mcp: FastMCP) -> None:
    @mcp.tool(name="docs_status", annotations={**READ, "title": "Corpus status"})
    def docs_status() -> StatusResult:
        """How many documents, pages, tables and chunks are loaded, by kind, and when."""
        return _guard(service.status, _c(), store.as_of())

    @mcp.tool(name="docs_list_documents", annotations={**READ, "title": "List documents"})
    def docs_list_documents(
        kind: Annotated[Kind, Field(description=(
            "Limit to one document kind, e.g. budget_justification or gao_report. any means all."))] = Kind.any,
    ) -> list[DocumentSummary]:
        """Every loaded PDF with its artifact_id, kind (budget_justification = J-book,
        selected_acquisition_report = SAR/MSAR, crs_report, gao_report ...), budget_cycle (PB2024
        for a J-book named PB24 or PB 2024), pages and tables."""
        return _guard(service.list_documents, _c(), kind.value)

    @mcp.tool(name="docs_document_map", annotations={**READ, "title": "Map a document's structure"})
    def docs_document_map(
        artifact_id: AID,
        line_item: Annotated[str, Field(max_length=4, description="Optional P-1 line item, e.g. 2001.")] = "",
    ) -> DocumentMapResult:
        """The layout of one document as page ranges: for a J-book each exhibit (P-40, P-5c, P-27,
        P-8a, P-35, P-10) of each P-1 line item with appropriation and date; for a SAR its sections
        and dollar bases (BY/TY); for CRS and GAO the numbered tables and figures."""
        return _guard(service.document_map, _c(), artifact_id, line_item)

    @mcp.tool(name="docs_read_page", annotations={**READ, "title": "Read a page"})
    def docs_read_page(
        artifact_id: AID,
        page: Annotated[int, Field(ge=1, le=5000, description="1-based page number, as cited in search hits.")],
        max_chars: Annotated[int, Field(ge=500, le=30000, description="Cut the page text at this many characters.")] = 12000,
    ) -> PageResult:
        """The full text of one page, its structural labels, and the ids of the tables on it."""
        return _guard(service.read_page, _c(), artifact_id, page, max_chars)

    @mcp.tool(name="docs_get_table", annotations={**READ, "title": "Get a table with tie-outs"})
    def docs_get_table(
        table_id: TID,
        include_continuations: Annotated[bool, Field(description=(
            "Join the table's continuation pages into one table (true) or return this page only."))] = True,
        max_rows: Annotated[int, Field(ge=5, le=400, description="Return at most this many rows.")] = 120,
    ) -> TableResult:
        """One table as printed (markdown), its column headers and unit, every numeric cell as an
        exact decimal with its row and column header and its value in $M, and the tie-outs: totals
        and subtotals against their rows and, for a P-5c, total ship estimate less prior funding
        against net P-1. Continuation pages are joined. Use the cells as arithmetic only when
        tieout_status is pass. On a ship cost exhibit (P-5, P-5c) each cell also carries ship_fy,
        hull (the column's hull: the columns are headed by funding year, not by hull name) and
        share_of_total_ship_estimate_pct; read the hull's column and quote the share as given."""
        return _guard(service.get_table, _c(), table_id, include_continuations, max_rows)

    @mcp.tool(name="docs_find_line_item", annotations={**READ, "title": "Find a budget line item"})
    def docs_find_line_item(
        line_item: Annotated[str, Field(min_length=4, max_length=4, pattern=r"^\d{4}$",
                                        description=("4-digit P-1 line item number, e.g. 2001 (Carrier Replacement "
                                                     "Program). If you only know the title, "
                                                     "docs_search it first; hits carry labels.line_item."))],
        exhibit: Annotated[str, Field(max_length=6, description="Optional exhibit, e.g. P-5c, P-8a, P-40.")] = "",
        budget_cycle: Annotated[str, Field(max_length=12, description=(
            "Optional President's Budget cycle of the book, e.g. PB2024 (PB 2024, PB24 and FY2024 "
            "also work). Empty means every loaded J-book."))] = "",
    ) -> LineItemResult:
        """Where a P-1 line item sits in every loaded J-book: page ranges per exhibit and its tables.

        Each J-book is one budget cycle, so the same exhibit appears once per book with different
        figures. When a question names a book ("the PB 2024 SCN book"), pass budget_cycle; each
        section carries its book's budget_cycle and printed page numbers. On a P-5c each hull is
        a column headed by its fiscal year: CVN 79 is the FY 2013 ship."""
        return _guard(service.find_line_item, _c(), line_item, exhibit, budget_cycle)

    @mcp.tool(name="docs_search", annotations={**READ, "title": "Search the documents"})
    def docs_search(
        query: Annotated[str, Field(min_length=1, max_length=400, description=(
            "Words or a figure to find. Keyword ranking, not semantic: use the terms printed in "
            "the documents (e.g. 'Cost Limitation Baseline', '13,529')."))],
        kind: Annotated[Kind, Field(description=(
            "Limit to one document kind: budget_justification (SCN J-books), "
            "selected_acquisition_report (SAR/MSAR), gao_report, crs_report ... Empty means all."))] = Kind.any,
        artifact_id: Annotated[str, Field(max_length=16, description=(
            "Limit to one document (artifact_id from docs_list_documents). Empty means all."))] = "",
        content: Annotated[Content, Field(description=(
            "table for exhibit tables only, prose for running text only, any for both."))] = Content.any,
        top_k: Annotated[int, Field(ge=1, le=25, description=(
            "Number of hits (about 1.5 KB each). 5-8 is usually enough."))] = 8,
    ) -> SearchResult:
        """Search whole tables and prose passages. Numbers match on their digits, so 13,409.970 and
        13409.97 are the same. Every hit has its document, page and labels. If the query names a
        known premise trap (submarine-only equipment, another hull or its contract, a method that
        must not be used), premise_flags says which and why: answer with that first."""
        return _guard(service.search, _c(), query, kind.value, artifact_id, content.value, top_k,
                      store.premise_terms())

    @mcp.tool(name="docs_find_figure", annotations={**READ, "title": "Find where a figure is printed"})
    def docs_find_figure(
        value_musd: Annotated[str, Field(max_length=32, description="Value in $M, e.g. 13409.97 or 12936.")],
        tolerance_musd: Annotated[str, Field(max_length=16, description=(
            "Allowed difference in $M, e.g. 0.5 to catch rounding. 0 means exact."))] = "0",
    ) -> FigureResult:
        """Every place a dollar figure is printed: table cells (converted with their column unit, with
        row and column headers) and page text. found=false means no loaded document prints it."""
        return _guard(service.find_figure, _c(), value_musd, tolerance_musd)

    @mcp.tool(name="docs_compare_figures", annotations={**READ, "title": "Check figures against the sources"})
    def docs_compare_figures(
        figures: Annotated[list[Figure], Field(min_length=1, max_length=20, description=(
            "One to twenty claimed figures to check, each with its value in $M."))],
        tolerance_musd: Annotated[str, Field(max_length=16, description=(
            "Allowed difference in $M, e.g. 0.5 to catch rounding. 0 means exact."))] = "0",
    ) -> CompareResult:
        """For each claimed figure: is it printed anywhere, in which documents, and is any of them a
        J-book exhibit or SAR (authoritative) rather than CRS or GAO (secondary)."""
        return _guard(service.compare_figures, _c(), [f.model_dump() for f in figures], tolerance_musd)

    @mcp.tool(name="docs_tieout_document", annotations={**READ, "title": "Tie out a document's tables"})
    def docs_tieout_document(
        artifact_id: AID,
        first_page: Annotated[int, Field(ge=0, le=5000, description=(
            "First page of the range, 1-based. 0 means from the start of the document."))] = 0,
        last_page: Annotated[int, Field(ge=0, le=5000, description=(
            "Last page of the range. 0 means to the end of the document."))] = 0,
    ) -> TieoutDocumentResult:
        """Run every tie-out in a document (or page range) and list the tables that do not add up."""
        return _guard(service.tieout_document, _c(), artifact_id, first_page, last_page)

    @mcp.tool(name="docs_parse_pdf", annotations={**READ, "title": "Parse a PDF from a volume"})
    def docs_parse_pdf(
        volume_path: Annotated[str, Field(max_length=500, description="/Volumes/... path to a .pdf")],
        pages: Annotated[str, Field(max_length=60, description="Pages, e.g. 1-10,15. At most 40.")] = "",
    ) -> ParsePdfResult:
        """Read a PDF that is not in the corpus yet, straight from a Unity Catalog volume: its
        structure map, every table with headers and unit, and the tie-outs. Nothing is stored."""
        def go():
            data = volume.read(volume_path, extract.MAX_BYTES)
            return service.parse_pdf(data, volume_path.rsplit("/", 1)[-1], pages or None)
        return _guard(go)
