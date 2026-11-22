# mcp-aircarrier-docs

> **Scorecard:** 11 tools · 50 tests · in the 421-call adversarial sweep · 7,703 of 7,712 tie-out checks pass on 34 PDFs (2026-11-21) · probe known answer 411 of 411. Every server's row: [SCORECARD.md](../../SCORECARD.md).

Deterministic reading of the CVN-79 PDF corpus (SCN J-book exhibits, SAR/MSAR, CRS, GAO). No model in the loop:
every number is an exact decimal with its document, page, row header, column header and unit.

## What it does

* **Structure.** Classifies each document (J-book, SAR, CRS, GAO, manual) and maps it as page ranges: J-book
  exhibit (P-40, P-5c, P-27, P-8a, P-35, P-10) by P-1 line item, SAR sections and dollar bases, CRS/GAO table captions.
* **Tables.** Whole tables from the pdfplumber grid, stacked column headers, unit from header/title (a Qty or %
  column never takes the money unit), continuation pages joined (stored links plus inferred ones, flagged).
* **Tie-outs.** Subtotal = rows since the previous subtotal; total = subtotals + loose rows; P-5c total ship
  estimate less every Less line = Net P-1 funding. Tolerance is one unit in the last printed place. A check that
  fails on its page is retried over the joined pages and the scope is reported.
* **Hybrid chunking and search.** Tables are one chunk each (never split); prose is packed into ~1,400-char
  windows with 250-char overlap. BM25 with numeric tokens normalised (13,409.970 = 13409.97).
* **Figure finder and cross-check.** Finds a $M figure in table cells (unit-converted) and in page text, and says
  whether any hit is in a J-book or SAR (authoritative) or only in CRS/GAO (secondary).
* **On-request parse.** Reads a PDF from an allowed UC volume (Files API) and returns map, tables and tie-outs
  without storing anything.

## Beyond CVN-79

The reader has no CVN-79 logic in it. Exhibit formats (P-40, P-5c, P-27, P-8a, P-35, P-10)
are standard across DoD procurement books, and SAR sections follow one template, so the same
structure map, table rebuild and tie-outs apply to any appropriation's justification books
and any program's SAR. Today 33 PDFs are loaded; `docs_parse_pdf` reads any other PDF from an
allowed volume on request. Users: budget analysts, cost estimators, congressional and GAO
staff, and auditors who now retype exhibits into spreadsheets.

## Tools

`docs_status`, `docs_list_documents`, `docs_document_map`, `docs_read_page`, `docs_get_table`,
`docs_find_line_item`, `docs_search`, `docs_find_figure`, `docs_compare_figures`, `docs_tieout_document`,
`docs_parse_pdf`. All read-only.

## Data and permissions

Reads `aircarrier_pdf_pages` and `aircarrier_pdf_tables` in `AIRCARRIER_STORE_SCHEMA` through the `sql-warehouse`
resource, loaded once and cached for `DOCS_CACHE_TTL_S`. The app service principal needs USE CATALOG/SCHEMA,
SELECT on those two tables, CAN USE on the warehouse, and READ VOLUME on each root in `DOCS_VOLUME_ROOTS`.

## Known limits (v0.1.0)

* Text-only tables (for example CRS RS20643 Table 2) are not rebuilt as grids; their figures are found in page text.
* Tie-outs, measured on the store on 2026-11-21: 7,703 of 7,712 checks pass over 34 documents (the first
  full run that day: 7,638 of 7,733). The earlier "4 of 818" counted PB2027 only; its 4 were cost elements named "Total ...", such
  as "Total Ship Test Program", read as totals. A Total row with a Subtotal below it is now read as a line
  item when that removes failures and adds none. Most of the 95 failures are layouts older books print: a
  P-40 money flow (Total Obligational Authority = Full Funding TOA plus Plus lines less Less lines) and P-10
  group rows followed by their items. Each is tried only when the plain sum fails, and taken only when it
  reproduces the printed total; quantity rows ("End Item Qty") are not money. The 9 left: rounding in two
  totals (PB2008 p.122, PB2007 p.66), one "First Destination" cell the extractor missed (PB2006 p.167), and
  subtotals whose items start on the previous page (PB2022 p.377, PB2023 p.449).
* The corpus (7,804 pages, about 11 s to load) refreshes on a background thread after `DOCS_CACHE_TTL_S`
  and loads at startup. Before 2026-11-21 the reload ran inside the request that found the cache expired:
  the slow mode (p50 12.6 s) of the probe's known-answer latency. After the fix: 11 of 11 at p50 1.19 s.
* A result holding text addressed to an AI assistant carries a `source_notice` (`source_notice.py`).
* `docs_parse_pdf` handles 40 pages and 60 MB per call and does not persist.

## Tests

`python -m pytest tests -q` with `src` on `PYTHONPATH`. Tests use fixtures only; no warehouse or network.
