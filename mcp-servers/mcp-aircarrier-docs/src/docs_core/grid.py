"""A PDF table as a grid of cells with headers.

Input is the verbatim pdfplumber grid (a list of rows of strings). Header
rows are the leading rows with no numeric cell. A column header is the stack
of header cells above it, carried right across merged (empty) cells; a row
header is the first text cell of the row. A cell's unit comes from its column
header first, then the table's title block and legends; a column that counts
(Qty, Each, %) never takes the table's money unit.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from decimal import Decimal

from docs_core import numbers as N

COUNT = re.compile(r"\b(qty|quantity|each|units?|percent|ratio|index|fte|count|number of)\b|%", re.IGNORECASE)
TITLE_ROW = ("Exhibit", "Appropriation", "P-1 Line")


@dataclass
class Cell:
    row: int
    col: int
    text: str
    value: Decimal | None
    places: int
    row_header: str
    col_header: str
    scale: str | None

    def as_dict(self) -> dict:
        d = {"row": self.row, "col": self.col, "text": self.text, "row_header": self.row_header,
             "col_header": self.col_header, "scale": self.scale}
        if self.value is not None:
            d["value"] = str(self.value)
            m = N.to_millions(self.value, self.scale)
            if m is not None:
                d["value_musd"] = str(m)
        return d


@dataclass
class Table:
    table_id: str
    artifact_id: str
    filename: str
    page: int
    grid: list[list[str]]
    title_block: list[str] = field(default_factory=list)
    legends: list[str] = field(default_factory=list)
    exhibits: list[str] = field(default_factory=list)
    continuation_of: str | None = None
    extractor: str = ""
    header_rows: int = 0
    col_headers: list[str] = field(default_factory=list)
    cells: list[Cell] = field(default_factory=list)
    scale: str | None = None
    link_inferred: bool = False
    _at: dict = field(default_factory=dict, repr=False)

    @property
    def n_rows(self) -> int:
        return len(self.grid)

    @property
    def n_cols(self) -> int:
        return max((len(r) for r in self.grid), default=0)

    def row_label(self, r: int) -> str:
        for c in self.grid[r]:
            t = " ".join((c or "").split())
            if t and N.parse(t) is None and not N.is_nil(t):
                return t
        return ""

    def numeric(self, r: int, c: int) -> Cell | None:
        return self._at.get((r, c))

    def markdown(self, max_rows: int = 80) -> str:
        rows = [[" ".join((c or "").split()).replace("|", "/") for c in r] for r in self.grid[:max_rows]]
        if not rows:
            return ""
        w = self.n_cols
        rows = [r + [""] * (w - len(r)) for r in rows]
        out = ["| " + " | ".join(rows[0]) + " |", "|" + "---|" * w]
        out += ["| " + " | ".join(r) + " |" for r in rows[1:]]
        return "\n".join(out)


def _row_is_numeric(row: list[str]) -> bool:
    return any(N.parse(c) is not None for c in row[1:] if c)


def build(table_id: str, artifact_id: str, filename: str, page: int, grid,
          title_block=None, legends=None, exhibits=None, continuation_of=None, extractor="") -> Table:
    if isinstance(grid, str):
        grid = json.loads(grid)
    grid = [[("" if c is None else str(c)) for c in row] for row in (grid or [])]
    t = Table(table_id, artifact_id, filename, page, grid,
              list(title_block or []), list(legends or []), list(exhibits or []), continuation_of, extractor)
    h = 0
    while h < len(grid) and not _row_is_numeric(grid[h]):
        h += 1
    if h == len(grid):  # a text-only table: its first row is the header
        h = 1 if grid else 0
    t.header_rows = h
    w = t.n_cols
    stacks: list[list[str]] = [[] for _ in range(w)]
    title_like = {" ".join(x.split()) for x in t.title_block}
    for r in range(h):
        carry = ""
        row = grid[r] + [""] * (w - len(grid[r]))
        texts = [" ".join(c.split()) for c in row]
        filled = [x for x in texts if x]
        if len(filled) <= 2 and any(x in title_like or x.startswith(TITLE_ROW) for x in filled):
            continue  # the exhibit title repeated inside the grid, not a column header
        for c in range(w):
            x = texts[c]
            if x:
                carry = x
            elif r < h - 1:
                x = carry  # a merged header spans the empty cells to its right
            if c == 0:
                continue
            if x and (not stacks[c] or stacks[c][-1] != x):
                stacks[c].append(x)
    t.col_headers = [" > ".join(s) for s in stacks]
    unit_text = " ".join(t.title_block + t.legends + [" ".join(c.split()) for r in grid[:h] for c in r])
    t.scale = (N.scale_of(unit_text) or (None, None))[1]
    for r in range(h, len(grid)):
        rh = t.row_label(r)
        for c, txt in enumerate(grid[r]):
            v = N.parse(txt)
            if v is None and not N.is_nil(txt):
                continue
            ch = t.col_headers[c] if c < len(t.col_headers) else ""
            own = N.scale_of(ch)
            sc = own[1] if own else (None if COUNT.search(ch) else t.scale)
            cell = Cell(r, c, " ".join(txt.split()), v, N.places(txt) if v is not None else 0, rh, ch, sc)
            t.cells.append(cell)
            if v is not None:
                t._at[(r, c)] = cell
    return t
