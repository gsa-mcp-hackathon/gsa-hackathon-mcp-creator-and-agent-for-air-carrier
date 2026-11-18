"""Find a figure everywhere it is printed.

A figure is a value in $M. It is found two ways: as a table cell whose value,
converted with its column unit, equals it to the printed precision; and as
text on a page in any of the ways prose prints money. Each hit keeps the row
and column header (or the sentence), the page and the document, so two hits
of one number can be compared on what they claim to be.
"""
from __future__ import annotations

from decimal import Decimal

from docs_core import numbers as N


def match_cell(cell, target_m: Decimal, tolerance_m: Decimal) -> bool:
    if cell.value is None:
        return False
    m = N.to_millions(cell.value, cell.scale)
    if m is None:
        return False
    # a cell printed to fewer places than the target matches within its own rounding
    half_unit = Decimal(1).scaleb(-cell.places) / 2 if cell.scale == "M" else Decimal(0)
    return abs(m - target_m) <= max(tolerance_m, half_unit)


def sentence_around(text: str, start: int, end: int, width: int = 220) -> str:
    return " ".join(text[max(0, start - width):min(len(text), end + width)].split())


def find_in_text(text: str, target_m: Decimal) -> list[tuple[int, int, str]]:
    hits = []
    for pat in N.variants(target_m):
        for m in pat.finditer(text or ""):
            hits.append((m.start(), m.end(), m.group(0)))
    hits.sort()
    out, last = [], -1
    for h in hits:
        if h[0] > last:
            out.append(h)
            last = h[1]
    return out
