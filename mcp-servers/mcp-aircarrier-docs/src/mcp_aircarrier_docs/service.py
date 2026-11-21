"""What each tool does, as plain functions over a Corpus. No MCP here."""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from docs_core import extract, structure
from docs_core.corpus import Corpus
from mcp_aircarrier_docs import config

GRADE = ("Every value is read verbatim from the PDF with its page, row and column. A table is usable as "
         "arithmetic only when its tie-outs pass; a figure found in one document is a citation, not a fact "
         "about the ship, until the documents that should agree have been compared.")
AUTHORITATIVE = ("budget_justification", "selected_acquisition_report")


class DocsError(ValueError):
    pass


# No left boundary: the books are named SCN_BookPB2024.pdf and SCN_Bookpb2006.pdf, with the
# cycle fused to the word before it. Requiring a separator there read no cycle from 21 of the
# 22 SCN books, so a filter on PB2024 found nothing (round 2, question F4: 0 of 6).
_CYCLE = re.compile(r"(?:PB|FY)[ _-]?(?:20)?(\d{2})(?!\d)", re.IGNORECASE)
_PAGE_CYCLE = re.compile(r"\bPB\s?(20\d{2})\b")


def budget_cycle(text: str) -> str:
    """The President's Budget cycle a document or a request names, as PB2024.

    J-book filenames say PB24 or PB 2024; people ask for "the PB 2024 book" or
    "FY2024". Keyword search cannot join those spellings, which is how a model
    lands on the wrong year's P-5c (evaluation finding F7). Empty when none.
    """
    m = _CYCLE.search(text or "")
    return f"PB20{m.group(1)}" if m else ""


def doc_cycle(d) -> str:
    """A document's budget cycle: from its filename, else from its exhibit headers.

    Every modern exhibit header prints the cycle ("Exhibit P-5c, Ship Cost Analysis: PB 2024
    Navy"), so a book with an uninformative filename still gets one. The most frequent value in
    the first 60 pages wins.
    """
    found = budget_cycle(d.filename)
    if found:
        return found
    counts: dict[str, int] = {}
    for page in sorted(d.pages)[:60]:
        for year in _PAGE_CYCLE.findall(d.pages[page] or ""):
            counts[year] = counts.get(year, 0) + 1
    return f"PB{max(counts, key=counts.get)}" if counts else ""


_P1_LINE = re.compile(r"P-1 Line Item Number\s*/\s*Title:?\s*(\d{4})\b")


def _p1_line(text: str) -> str:
    m = _P1_LINE.search(text or "")
    return m.group(1) if m else ""


def _ship_cost_labels(parts: list[dict], line_item: str = "") -> None:
    """On a ship cost exhibit (P-5, P-5c), name each column's hull and each cost's share.

    The columns are headed by the hull's full-funding year, so a model reading "FY 2018" has to
    know that is CVN-80; in round 2 one took Propulsion Equipment from that column for CVN-79.
    Each cost category also gets its share of the same column's Total Ship Estimate, computed
    here so no model does the division (another round 2 miss: 63.09% for 63.11%).

    The hull depends on the P-1 line as well as the year: "FY 2020" is CVN-81 on line 2004 and a
    refueling overhaul on line 2086. With no line found, columns keep ship_fy and get no hull.
    """
    title = " ".join(x for part in parts for x in part.get("title_block") or [])
    if not re.search(r"P-5c?\b", title) or "Ship Cost" not in title:
        return
    cells = [c for part in parts for c in part["numeric_cells"]]
    totals = {}
    for c in cells:
        if (c.get("row_header") or "").strip().lower().startswith("total ship estimate") and c.get("value_musd"):
            totals[c["col_header"]] = Decimal(c["value_musd"])
    for c in cells:
        year = re.search(r"FY\s?(20\d{2}|19\d{2})", c.get("col_header") or "")
        if year:
            c["ship_fy"] = year.group(1)
            hull = config.SHIP_HULLS.get((line_item, year.group(1)))
            if hull:
                c["hull"] = hull
            if line_item:
                c["p1_line"] = line_item
        total = totals.get(c.get("col_header"))
        head = (c.get("row_header") or "").strip().lower()
        if total and c.get("value_musd") and not head.startswith(("total", "less", "net")):
            share = Decimal(c["value_musd"]) / total * 100
            c["share_of_total_ship_estimate_pct"] = str(share.quantize(Decimal("0.01")))


def _doc(c: Corpus, artifact_id: str):
    try:
        return c.doc(artifact_id)
    except KeyError:
        raise DocsError(f"unknown artifact_id {artifact_id!r}; call docs_list_documents") from None


def status(c: Corpus, as_of: str | None) -> dict:
    kinds: dict[str, int] = {}
    for d in c.docs.values():
        kinds[d.kind] = kinds.get(d.kind, 0) + 1
    return {"documents": len(c.docs), "pages": sum(len(d.pages) for d in c.docs.values()),
            "tables": len(c.tables), "chunks": len(c.chunks), "by_kind": kinds,
            "inferred_continuations": sum(t.link_inferred for t in c.tables.values()),
            "loaded_at": as_of, "grade": GRADE}


def list_documents(c: Corpus, kind: str = "") -> list[dict]:
    out = []
    for d in sorted(c.docs.values(), key=lambda d: (d.kind, d.filename)):
        if kind and d.kind != kind:
            continue
        out.append({"artifact_id": d.artifact_id, "filename": d.filename, "kind": d.kind,
                    "budget_cycle": doc_cycle(d),
                    "pages": len(d.pages), "tables": len(d.tables)})
    return out


def document_map(c: Corpus, artifact_id: str, line_item: str = "") -> dict:
    d = _doc(c, artifact_id)
    m = structure.document_map(d.kind, sorted(d.pages.items()))
    if line_item:
        m = [x for x in m if x.get("line_item") == line_item]
    return {"artifact_id": d.artifact_id, "filename": d.filename, "kind": d.kind, "pages": len(d.pages),
            "sections": m[:400], "truncated": len(m) > 400}


def read_page(c: Corpus, artifact_id: str, page: int, max_chars: int = 12000) -> dict:
    d = _doc(c, artifact_id)
    if page not in d.pages:
        raise DocsError(f"page {page} is not in {d.filename} (1-{max(d.pages) if d.pages else 0})")
    text = d.pages[page]
    tabs = [t for t in d.tables if c.tables[t].page == page]
    return {"artifact_id": d.artifact_id, "filename": d.filename, "page": page, "labels": d.labels.get(page, {}),
            "text": text[:max_chars], "truncated": len(text) > max_chars,
            "tables": [{"table_id": t, "n_rows": c.tables[t].n_rows, "n_cols": c.tables[t].n_cols,
                        "unit": c.tables[t].scale, "continuation_of": c.tables[t].continuation_of} for t in tabs]}


def get_table(c: Corpus, table_id: str, include_continuations: bool = True, max_rows: int = 120) -> dict:
    if table_id not in c.tables:
        raise DocsError(f"unknown table_id {table_id!r}; find one with docs_read_page or docs_search")
    chain = c.chain(table_id) if include_continuations else [c.tables[table_id]]
    parts = []
    for t in chain:
        cells = [x.as_dict() for x in t.cells if x.value is not None][: max_rows * 8]
        parts.append({"table_id": t.table_id, "page": t.page, "unit": t.scale, "extractor": t.extractor,
                      "continuation_of": t.continuation_of, "link_inferred": t.link_inferred,
                      "title_block": t.title_block, "legends": sorted(set(t.legends)),
                      "column_headers": t.col_headers, "markdown": t.markdown(max_rows), "numeric_cells": cells})
    head = chain[0]
    doc = c.docs.get(head.artifact_id)
    page_text = (doc.pages.get(head.page) if doc else "") or ""
    line = _p1_line(page_text) or _p1_line(" ".join(head.title_block or []))
    _ship_cost_labels(parts, line)
    ties = c.tieouts(chain[0].table_id)
    return {"filename": chain[0].filename, "artifact_id": chain[0].artifact_id, "pages": [t.page for t in chain],
            "tables": parts, "tieouts": ties,
            "tieout_status": "no_totals_found" if not ties else ("pass" if all(x["passed"] for x in ties) else "fail"),
            "grade": GRADE}


def find_line_item(c: Corpus, line_item: str, exhibit: str = "", cycle: str = "") -> dict:
    if not re.fullmatch(r"\d{4}", line_item or ""):
        raise DocsError("line_item is the four-digit P-1 line item number, e.g. 2001")
    wanted = budget_cycle(cycle) if cycle else ""
    if cycle and not wanted:
        raise DocsError("budget_cycle names a President's Budget year, e.g. PB2024, PB 2024 or FY2024")
    hits = []
    loaded = sorted({doc_cycle(d) for d in c.docs.values()
                     if d.kind == "budget_justification"} - {""})
    for d in c.docs.values():
        if d.kind != "budget_justification":
            continue
        if wanted and doc_cycle(d) != wanted:
            continue
        for x in structure.document_map(d.kind, sorted(d.pages.items())):
            if x.get("line_item") != line_item or (exhibit and x.get("exhibit", "").lower() != exhibit.lower()):
                continue
            lo, hi = x["pages"]
            tabs = [t for t in d.tables if lo <= c.tables[t].page <= hi]
            heads = sorted({c.chain(t)[0].table_id for t in tabs})
            hits.append({**x, "artifact_id": d.artifact_id, "filename": d.filename,
                         "budget_cycle": doc_cycle(d), "tables": tabs,
                         "table_chains": heads})
    note = "Call docs_get_table on a table_chains id for the cells and their tie-outs."
    if wanted and not hits:
        note = (f"No loaded J-book is {wanted}. Loaded cycles: {', '.join(loaded) or 'none'}. "
                "Say the book is not loaded rather than answering from another year.")
    return {"line_item": line_item, "exhibit": exhibit or None, "budget_cycle": wanted or None,
            "loaded_cycles": loaded, "sections": hits, "note": note}


def premise_flags(query: str, terms) -> list[dict]:
    """Premise traps named in the query, e.g. submarine-only equipment or another hull's
    contract. Matched case-insensitively on word boundaries, longest term first."""
    import re

    q = query or ""
    found: list[dict] = []
    for term, why in sorted(terms or [], key=lambda t: -len(t[0])):
        if (term and re.search(r"(?<![A-Za-z0-9])" + re.escape(term) + r"(?![A-Za-z0-9])", q, re.IGNORECASE)
                and not any(term.lower() in f["term"].lower() for f in found)):
            found.append({"term": term, "why": why})
    return found


def search(c: Corpus, query: str, kind: str = "", artifact_id: str = "", content: str = "any", top_k: int = 8,
           terms=None) -> dict:
    if not (query or "").strip():
        raise DocsError("query is empty")
    hits = c.search(query, top_k, kind or None, artifact_id or None, None if content == "any" else content)
    out = {"query": query, "n": len(hits), "hits": hits,
           "note": "Lexical BM25 over whole tables and overlapping prose windows; numbers match on digits."}
    flags = premise_flags(query, terms)
    if flags:
        out["premise_flags"] = flags
        out["premise_note"] = ("The query names a known premise trap for CVN-79. Check each why before "
                               "using any hit: the question itself may be wrong.")
    return out


def _dec(v, name: str) -> Decimal:
    try:
        return Decimal(str(v).replace(",", "").replace("$", "").strip())
    except InvalidOperation:
        raise DocsError(f"{name} must be a number in $M, e.g. 13409.97") from None


def find_figure(c: Corpus, value_musd, tolerance_musd="0", limit: int = 25) -> dict:
    v, t = _dec(value_musd, "value_musd"), _dec(tolerance_musd, "tolerance_musd")
    if not v.is_finite() or not t.is_finite() or t < 0 or t > abs(v) * Decimal("0.05") + 1:
        raise DocsError("tolerance_musd must be between 0 and 5% of the value")
    r = c.find_figure(str(v), str(t), limit)
    r["found"] = bool(r["n_table_cells"] or r["n_text_hits"])
    if not r["found"]:
        r["note"] = "Not printed in any loaded document at this precision. Treat any use of it as unsourced."
    return r


def compare_figures(c: Corpus, figures: list[dict], tolerance_musd="0") -> dict:
    if not figures or len(figures) > 20:
        raise DocsError("give between 1 and 20 figures")
    rows = []
    for f in figures:
        label = str(f.get("label") or f.get("value_musd"))[:120]
        r = find_figure(c, f.get("value_musd"), tolerance_musd, limit=5)
        kinds = sorted({x["kind"] for x in r["table_cells"] + r["text_hits"]})
        rows.append({"label": label, "value_musd": r["value_musd"], "found": r["found"],
                     "documents": r["documents"], "document_kinds": kinds,
                     "authoritative": any(k in AUTHORITATIVE for k in kinds),
                     "first_cell": (r["table_cells"] or [None])[0], "first_text": (r["text_hits"] or [None])[0]})
    return {"figures": rows,
            "summary": {"n": len(rows), "found": sum(r["found"] for r in rows),
                        "in_a_budget_exhibit_or_sar": sum(r["authoritative"] for r in rows),
                        "not_found": [r["label"] for r in rows if not r["found"]]},
            "reading": ("authoritative means printed in a J-book exhibit or a SAR/MSAR. A figure found only in "
                        "CRS or GAO is a secondary citation; one found nowhere is unsourced.")}


def tieout_document(c: Corpus, artifact_id: str, first_page: int = 0, last_page: int = 0) -> dict:
    d = _doc(c, artifact_id)
    heads: list[str] = []
    for tid in d.tables:
        t = c.tables[tid]
        if (first_page and t.page < first_page) or (last_page and t.page > last_page):
            continue
        h = c.chain(tid)[0].table_id
        if h not in heads:
            heads.append(h)
    per = {h: c.tieouts(h) for h in heads}
    res = [x for v in per.values() for x in v]
    fails = [x for x in res if not x["passed"]]
    return {"artifact_id": d.artifact_id, "filename": d.filename, "tables_checked": len(heads),
            "checks": len(res), "passed": len(res) - len(fails), "failed": len(fails),
            "failures": fails[:60], "tables_without_totals": sum(1 for v in per.values() if not v),
            "reading": "A failure means the table as extracted does not add up: check the page before using it."}


def parse_pdf(data: bytes, filename: str, pages: str | None) -> dict:
    try:
        page_rows, table_rows, meta = extract.extract(data, filename, pages)
    except extract.ExtractError as e:
        raise DocsError(str(e)) from None
    mini = Corpus(page_rows, table_rows)
    d = next(iter(mini.docs.values()), None)
    tables, heads = [], []
    for tid, t in mini.tables.items():
        h = mini.chain(tid)[0].table_id
        if h not in heads:
            heads.append(h)
        tables.append({"table_id": tid, "page": t.page, "unit": t.scale, "n_rows": t.n_rows, "n_cols": t.n_cols,
                       "column_headers": t.col_headers, "continuation_of": t.continuation_of,
                       "markdown": t.markdown(40)})
    ties = [x for h in heads for x in mini.tieouts(h)]
    return {**meta, "filename": filename, "kind": d.kind if d else "",
            "map": structure.document_map(d.kind, sorted(d.pages.items())) if d else [],
            "tables": tables[:60], "tieouts": ties[:120],
            "tieout_summary": {"checks": len(ties), "failed": sum(1 for x in ties if not x["passed"])},
            "persisted": False,
            "note": "Parsed on request and not stored. To add it to the corpus, load it into the PDF store tables.",
            "grade": GRADE}
