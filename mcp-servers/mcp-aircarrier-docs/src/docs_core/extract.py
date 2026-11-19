"""PDF bytes to pages and table grids, for documents not yet in the store.

pdfplumber finds ruled tables (J-book exhibits are ruled); a page with no
ruled table but many numbers is retried with the text strategy. The output
rows have the same shape as the store (same artifact id: the first 16 hex of
the SHA-256 of the bytes), so the same grid, tie-out and search code reads
both. Hard limits keep one request from exhausting the app.
"""
from __future__ import annotations

import hashlib
import io
import re

MAX_BYTES = 60 * 1024 * 1024
MAX_PAGES = 40
_TITLE = re.compile(r"^\s*(Exhibit\s+[A-Z]-\d+|Appropriation|P-1 Line Item|Date:|Table\s+\d+\.|Figure\s+\d+\.)", re.IGNORECASE)
_NUMS = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+\.\d{2,}")


class ExtractError(ValueError):
    pass


def artifact_id(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


def parse_pages(spec: str | None, n: int) -> list[int]:
    """'1-5,9' to [1, 2, 3, 4, 5, 9], within 1..n."""
    if not spec:
        return list(range(1, min(n, MAX_PAGES) + 1))
    out: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if not re.fullmatch(r"\d+(-\d+)?", part):
            raise ExtractError(f"bad page range {part!r}; use e.g. 1-5,9")
        a, _, b = part.partition("-")
        lo, hi = int(a), int(b or a)
        if lo < 1 or hi < lo:
            raise ExtractError(f"bad page range {part!r}")
        if hi - lo >= MAX_PAGES:
            raise ExtractError(f"at most {MAX_PAGES} pages per call; narrow the range")
        out += [p for p in range(lo, hi + 1) if p <= n]
    out = sorted(set(out))
    if len(out) > MAX_PAGES:
        raise ExtractError(f"at most {MAX_PAGES} pages per call; narrow the range")
    if not out:
        raise ExtractError(f"no pages in range; the document has {n}")
    return out


def extract(data: bytes, filename: str, pages: str | None = None) -> tuple[list[dict], list[dict], dict]:
    if len(data) > MAX_BYTES:
        raise ExtractError("file is larger than 60 MB")
    if not data.startswith(b"%PDF"):
        raise ExtractError("not a PDF (missing %PDF header)")
    import pdfplumber

    aid = artifact_id(data)
    page_rows: list[dict] = []
    table_rows: list[dict] = []
    prev = None  # (table_id, title, n_cols) of the last table on the previous page
    try:
        pdf = pdfplumber.open(io.BytesIO(data))
    except Exception:  # noqa: BLE001
        raise ExtractError("the PDF could not be opened (damaged or encrypted)") from None
    with pdf:
        n = len(pdf.pages)
        sel = parse_pages(pages, n)
        for p in sel:
            pg = pdf.pages[p - 1]
            text = pg.extract_text() or ""
            title = [ln.strip() for ln in text.splitlines()[:14] if _TITLE.match(ln)]
            found = pg.find_tables()
            extractor = "pdfplumber-lines/v1"
            if not found and len(_NUMS.findall(text)) >= 12:
                found = pg.find_tables({"vertical_strategy": "text", "horizontal_strategy": "text"})
                extractor = "pdfplumber-text/v1"
            last = None
            for i, tb in enumerate(found):
                grid = tb.extract() or []
                if len(grid) < 2:
                    continue
                tid = f"{aid}:{p:04d}:{i:02d}"
                ncols = max(len(r) for r in grid)
                cont = prev[0] if (prev and i == 0 and title and prev[1] == title and prev[2] == ncols) else None
                table_rows.append({"table_id": tid, "artifact_id": aid, "filename": filename, "page": p,
                                   "grid_json": grid, "title_block": title, "legends": [], "exhibits": [],
                                   "continuation_of": cont, "extractor": extractor})
                last = (tid, title, ncols)
            prev = last
            page_rows.append({"artifact_id": aid, "filename": filename, "page": p, "text": text})
    return page_rows, table_rows, {"artifact_id": aid, "n_pages": n, "pages_read": sel, "bytes": len(data)}
