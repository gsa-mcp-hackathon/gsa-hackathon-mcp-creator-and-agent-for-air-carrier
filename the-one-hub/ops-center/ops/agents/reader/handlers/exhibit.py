"""Structured exhibit documents: SCN book, SAR, MSAR, budget exhibits.

Carries numbered exhibits with fixed schemas: P-1, P-5 / P-5a / P-5c, P-8a,
P-10, P-21, and the MSAR contract tables.

THE RULE THIS HANDLER EXISTS TO ENFORCE
Never return a cell without its full coordinate chain and every legend printed
on its page. Both of the worst errors in the record were prevented by this one
storage rule rather than by a smarter model:
  Error 1  a column was captured without the header chain that would have
           identified its platform. The columns were Columbia-class.
  Error 2  a dagger was interpreted without capturing its definition, which was
           printed on the same page.

Known exhibit hazards are in ../../../../seed/exhibits.yaml and are attached to
the exhibit type, so every extraction inherits them. Example: the printed P-1
line number is renumbered between budget years while BLI 2001 stays fixed, so
a multi-year query keyed on the printed number breaks silently.
"""
import json
import re
from datetime import datetime, timezone

from core import catalog
from core.contracts import Claim, Coordinate, Tag, Zone
from core.contracts.risk import RiskFlag

VERSION = "exhibit/0.4"   # 0.3: unit resolved from row, column, table, title, page (resolve_unit)
                           # 0.4: identifier columns (Hull Number) are not claims
LAYER = "L1"   # Budget: P-5c categories, P-40 streams (etl/build_data.py layers)
TITLE_EXH = re.compile(r"Exhibit\s+(P-\d+[a-z]?)\b")
TITLE_BLI = re.compile(r"Line Item Number / Title:\s*(\d{4})\b")
TITLE_APP = re.compile(r"Sub Activity:\s*(\d{4}[A-Z])\b")
FY = re.compile(r"\bFY\s?(\d{4})\b")


# Units as printed. Budget exhibits put the unit in different places: P-40 and P-5
# in the row label ("Gross/Weapon System Cost ($ in Millions)"), P-10 and P-35 in
# the table's column header ("Total Cost ($ M)", "Qty (Each)"), P-1 once per page
# ("(Dollars in Thousands)"). exhibit/0.2 read only the cell's header chain and so
# left 4,753 claims UNKNOWN. EACH is matched only in its printed forms, because the
# bare word is common in prose legends ("Each DDG 1000 will carry...").
UNIT_RX = {
    "USD_M": re.compile(r"(?i)\$\s*in\s+millions|dollars\s+in\s+millions|\(\s*\$\s*M\s*\)|\$\s*M\b"),
    "USD_K": re.compile(r"(?i)\$\s*in\s+thousands|dollars\s+in\s+thousands|\(\s*\$\s*K\s*\)|\(\s*\$000\s*\)"),
    "EACH": re.compile(r"(?i)\(\s*(units\s+in\s+)?each\s*\)"),
    "MONTHS": re.compile(r"(?i)\(\s*months\s*\)"),
    "PERCENT": re.compile(r"(?i)\(\s*%\s*\)|\bpercent\b"),
}
# A page-wide legend counts only in its formal form, and only when the page prints
# no other unit: a page with both "($ M)" and "(Each)" columns says nothing about
# a cell that has neither.
PAGE_LEGEND_RX = {
    "USD_M": re.compile(r"(?i)\(\s*dollars\s+in\s+millions\s*\)"),
    "USD_K": re.compile(r"(?i)\(\s*dollars\s+in\s+thousands\s*\)"),
}


# Columns that print an identifier, not a quantity. P-29 and P-30 list each ship by
# hull (a "Hull Number" of 1714 names a ship; it is not 1,714 of anything);
# exhibit/0.3 emitted 397 such cells as numeric claims with no unit. A number in
# one of these columns is a label for the row, so it is not a claim at all.
IDENTIFIER_COLUMN_RX = re.compile(r"(?i)^\s*hull\s*(number|no\.?)\s*$")


def is_identifier_column(col_chain: list[str], table_col_header: str | None) -> bool:
    """True when the cell's own column is an identifier column (see IDENTIFIER_COLUMN_RX)."""
    return any(IDENTIFIER_COLUMN_RX.match(h or "") for h in [*(col_chain or []), table_col_header])


def unit_kinds(text: str | None) -> set[str]:
    return {u for u, rx in UNIT_RX.items() if text and rx.search(text)}


def page_unit(text: str | None) -> str | None:
    """The page's unit if it prints exactly one formal money legend and no other unit."""
    leg = {u for u, rx in PAGE_LEGEND_RX.items() if text and rx.search(text)}
    if len(leg) != 1:
        return None
    return next(iter(leg)) if unit_kinds(text) <= leg else None


def resolve_unit(row_header: str | None, col_chain: list[str], table_col_header: str | None,
                 title: list[str], legends: list[str], page: str | None) -> tuple[str, str]:
    """(unit, source). Nearest printed evidence wins: row label, cell column chain, the
    table's own column header, the title block and legends, then the page legend.
    Two units at one level is a conflict and stays UNKNOWN; this never guesses."""
    for src, text in (("row", row_header), ("column", " > ".join(col_chain or [])),
                      ("table_column", table_col_header)):
        k = unit_kinds(text)
        if len(k) == 1:
            return next(iter(k)), src
        if k:
            return "UNKNOWN", src + "_conflict"
    k = unit_kinds(" | ".join(list(title or []) + list(legends or [])))
    if len(k) == 1:
        return next(iter(k)), "title"
    if k:
        return "UNKNOWN", "title_conflict"
    if page:
        return page, "page"
    return "UNKNOWN", "none"


def _spark():
    from pyspark.sql import SparkSession
    return SparkSession.builder.getOrCreate()


def _title_field(title: list[str], rx) -> str | None:
    for line in title:
        m = rx.search(line)
        if m:
            return m[1]
    return None


def extract(artifact_id: str, *, target_exhibit: str | None = None) -> list[Claim]:
    """Every numeric body cell of the artifact's exhibit tables, as candidate claims.

    Read from the lossless PDF cell store, never from chunked text. Each claim carries the
    full coordinate: exhibit, appropriation and BLI from the table's own title block, the
    column header chain, the row label, the page, and every legend printed on the page.

    What it deliberately does not do:
      * attribute a column to a hull. P-5c "FY 2013" is CVN-79 only by crosswalk, which is
        the Attributor's job (DERIVED at best). hull is UNATTRIBUTED and PREMISE is set:
        N.7 Error 1 was exactly a column taken for the wrong platform.
      * resolve two values for one coordinate (D15). Continuation pages repeat headers and
        each cell keeps its own table_id.
    Cells from the text-strategy fallback also carry INTERPRETATION, because their column
    headers are reconstructed.
    """
    spark = _spark()
    where = f"t.artifact_id = '{artifact_id}' AND c.value_kind = 'number' AND NOT c.is_header AND c.col_idx > 0"
    rows = spark.sql(f"""SELECT t.table_id, t.page, t.extractor, t.title_block, t.col_headers,
        t.legends AS table_legends, p.text AS page_text, c.row_idx, c.col_idx, c.value, c.value_num,
        c.row_header, c.col_header, c.legends
        FROM {catalog.PDF_TABLES} t JOIN {catalog.PDF_CELLS} c USING (table_id)
        LEFT JOIN {catalog.PDF_PAGES} p ON p.artifact_id = t.artifact_id AND p.page = t.page
        WHERE {where}
        ORDER BY t.table_id, c.row_idx, c.col_idx""").collect()
    page_units: dict[int, str | None] = {}
    now = datetime.now(timezone.utc)
    out: list[Claim] = []
    for r in rows:
        title = json.loads(r.title_block)
        exh = _title_field(title, TITLE_EXH)
        if exh is None or (target_exhibit and exh.lower() != target_exhibit.lower()):
            continue
        chain = [h for h in (r.col_header or "").split(" > ") if h]
        fy = next((FY.search(h) for h in chain if FY.search(h)), None)
        flags = {RiskFlag.PREMISE}
        if r.extractor != "pdfplumber-lines/v1":
            flags.add(RiskFlag.INTERPRETATION)
        try:
            tcol = (json.loads(r.col_headers or "[]") or [])[r.col_idx] or ""
        except (IndexError, TypeError, ValueError):
            tcol = ""
        if is_identifier_column(chain, tcol):
            continue
        if r.page not in page_units:
            page_units[r.page] = page_unit(r.page_text)
        unit, unit_src = resolve_unit(r.row_header, chain, tcol, title,
                                      list(r.table_legends or []) + list(r.legends or []),
                                      page_units[r.page])
        out.append(Claim(
            claim_id=f"{r.table_id}:r{r.row_idx}c{r.col_idx}", hull="UNATTRIBUTED", layer=LAYER,
            element=r.row_header or f"row {r.row_idx}", period=f"FY{fy[1]}" if fy else "",
            value=float(r.value_num), unit=unit, discovered_at=now,
            coordinate=Coordinate(artifact_id, exhibit=exh, appropriation=_title_field(title, TITLE_APP),
                                  line_item=_title_field(title, TITLE_BLI), column_header_chain=chain,
                                  row_label=r.row_header, page=r.page, page_legends=list(r.legends or []),
                                  neighborhood=" | ".join(title[:4])),
            tag=Tag.VERIFIED, confidence=0.9 if r.extractor == "pdfplumber-lines/v1" else 0.6,
            zone=Zone.RAW, source_system=f"PDF_EXHIBIT:{exh}",
            extraction_method=f"{VERSION}+{r.extractor}", risk_flags=flags,
            notes=f"verbatim cell '{r.value}' at {r.table_id} r{r.row_idx} c{r.col_idx}; "
                  f"unit from {unit_src}"))
    return out
