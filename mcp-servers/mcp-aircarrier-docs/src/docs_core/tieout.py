"""Tie-outs: arithmetic a table promises about itself.

A subtotal must equal the rows since the previous subtotal; a total must equal
its subtotals plus any loose rows, to the precision printed. A J-book P-5c must
net from Total Ship Estimate, less every prior-year and cost-to-complete line,
to Net P-1 Funding across its continuation pages. A table that fails is
reported as failing with the printed and computed values; it is never used
silently.
"""
from __future__ import annotations

import re
from decimal import Decimal

from docs_core.grid import Table

TOTAL = re.compile(r"^(grand\s+)?total\b|\btotal ship estimate\b|\btotal$", re.IGNORECASE)
SUBTOTAL = re.compile(r"\bsub-?total\b", re.IGNORECASE)
LESS = re.compile(r"^less\b", re.IGNORECASE)
NET = re.compile(r"^net\b.*funding|^net p-1", re.IGNORECASE)
SKIP = re.compile(r"^(less|plus|memo|note|percent|%|unit cost|qty|quantity)\b", re.IGNORECASE)
SHIP_TOTAL = re.compile(r"total ship estimate|^total estimate", re.IGNORECASE)


def tolerance(*places: int) -> Decimal:
    """One unit in the last printed place: rounding can move a sum by that much."""
    return Decimal(1).scaleb(-max(places or (0,)))


def _money_cols(t: Table) -> list[int]:
    return sorted({c.col for c in t.cells if c.value is not None and c.scale})


def check_totals(t: Table) -> list[dict]:
    out = []
    labels = {r: t.row_label(r) for r in range(t.header_rows, t.n_rows)}
    for col in _money_cols(t):
        loose: list = []
        subs: list = []
        for r in range(t.header_rows, t.n_rows):
            lab = labels[r]
            if NET.search(lab):
                continue
            c = t.numeric(r, col)
            is_sub = bool(SUBTOTAL.search(lab))
            is_tot = bool(TOTAL.search(lab)) and not is_sub
            if not (is_sub or is_tot):
                if c is not None and not SKIP.search(lab):
                    loose.append(c)
                continue
            if c is None:
                loose = []
                if is_tot:
                    subs = []
                continue
            parts = loose if is_sub else subs + loose
            if len(parts) >= 2:
                s = sum((p.value for p in parts), Decimal(0))
                tol = tolerance(c.places, *(p.places for p in parts))
                out.append({"rule": "subtotal_equals_sum_of_rows" if is_sub else "total_equals_sum_of_rows",
                            "table_id": t.table_id, "page": t.page, "row": lab, "column": c.col_header,
                            "printed": str(c.value), "computed": str(s), "difference": str(c.value - s),
                            "n_parts": len(parts), "passed": abs(c.value - s) <= tol, "tolerance": str(tol)})
            if is_sub:
                subs.append(c)
                loose = []
            else:
                loose, subs = [], []
    return out


def check_net_funding(chain: list[Table]) -> list[dict]:
    """Total estimate less every Less line equals the Net line. chain is the
    table and its continuation pages, in order."""
    out = []
    if not chain:
        return out
    for col in sorted({c for t in chain for c in _money_cols(t)}):
        total = net = None
        less: list = []
        for t in chain:
            for r in range(t.header_rows, t.n_rows):
                lab = t.row_label(r)
                c = t.numeric(r, col)
                if c is None:
                    continue
                if SHIP_TOTAL.search(lab):
                    total = c
                elif LESS.search(lab):
                    less.append(c)
                elif NET.search(lab):
                    net = c
        if total is None or net is None:
            continue
        less_sum = sum((c.value for c in less), Decimal(0))
        computed = total.value - less_sum
        tol = tolerance(total.places, net.places, *(c.places for c in less))
        out.append({"rule": "total_less_prior_funding_equals_net", "table_id": chain[0].table_id,
                    "pages": [chain[0].page, chain[-1].page], "row": "Net P-1 Funding", "column": total.col_header,
                    "total": str(total.value), "less_lines": len(less), "less_sum": str(less_sum),
                    "printed": str(net.value), "computed": str(computed), "difference": str(net.value - computed),
                    "passed": abs(net.value - computed) <= tol, "tolerance": str(tol)})
    return out
