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
PLUS = re.compile(r"^plus\b", re.IGNORECASE)
# A count, not money: "End Item Qty", "PLT in Months". "Economic Order Quantity" is money.
COUNT = re.compile(r"(?<!order )\b(qty|quantity)\s*(\(each\))?$|\bplt\b|\bin months\b", re.IGNORECASE)


def tolerance(*places: int) -> Decimal:
    """One unit in the last printed place: rounding can move a sum by that much."""
    return Decimal(1).scaleb(-max(places or (0,)))


def _money_cols(t: Table) -> list[int]:
    return sorted({c.col for c in t.cells if c.value is not None and c.scale})


def _followed_by_subtotal(labels: dict[int, str]) -> list[int]:
    """Total-labelled rows with a Subtotal below them before the next Total."""
    rows = sorted(labels)
    out = []
    for i, r in enumerate(rows):
        lab = labels[r]
        if not TOTAL.search(lab) or SUBTOTAL.search(lab):
            continue
        for later in rows[i + 1:]:
            if SUBTOTAL.search(labels[later]):
                out.append(r)
                break
            if TOTAL.search(labels[later]):
                break
    return out


def _failures(res: list[dict]) -> set[tuple[str, str]]:
    return {(r["row"], r["column"]) for r in res if not r["passed"]}


def check_totals(t: Table) -> list[dict]:
    """Every subtotal and total in the table, checked against its rows.

    Some cost elements are named "Total ...": "TOTAL SHIP COMPUTING
    ENVIRONMENT (TSCE)", "Total Ship Test Program". Read as totals they fail
    and break the subtotal below them. A Total row with a Subtotal below it is
    read as a line item only when that removes failures and adds none, so the
    arithmetic decides, and a real total that ties is never reclassified."""
    labels = {r: t.row_label(r) for r in range(t.header_rows, t.n_rows)}
    items: set[int] = set()
    res = _check_totals(t, labels, items)
    for r in _followed_by_subtotal(labels):
        if not any(not x["passed"] and x["row"] == labels[r] for x in res):
            continue
        trial = _check_totals(t, labels, items | {r})
        if _failures(trial) < _failures(res):  # a strict subset: fewer, none new
            items.add(r)
            res = trial
    return res


def _check_totals(t: Table, labels: dict[int, str], items: set[int]) -> list[dict]:
    out = []
    for col in _money_cols(t):
        loose: list = []
        subs: list = []
        flow: list = []
        prev_total = None
        for r in range(t.header_rows, t.n_rows):
            lab = labels[r]
            if NET.search(lab):
                continue
            c = t.numeric(r, col)
            is_sub = bool(SUBTOTAL.search(lab))
            is_tot = bool(TOTAL.search(lab)) and not is_sub and r not in items
            if not (is_sub or is_tot):
                if c is not None:
                    if LESS.search(lab):
                        flow.append(("less", c))
                    elif PLUS.search(lab):
                        flow.append(("plus", c))
                    elif not SKIP.search(lab) and not COUNT.search(lab):
                        loose.append(c)
                        flow.append(("item", c))
                continue
            if c is None:
                loose = []
                if is_tot:
                    subs, flow = [], []
                continue
            parts = loose if is_sub else subs + loose
            if len(parts) >= 2:
                s = sum((p.value for p in parts), Decimal(0))
                tol = tolerance(c.places, *(p.places for p in parts))
                rule = "subtotal_equals_sum_of_rows" if is_sub else "total_equals_sum_of_rows"
                if abs(c.value - s) > tol and not is_sub:
                    s, rule = _second_reading(c, parts, flow, prev_total, tol, s, rule)
                out.append({"rule": rule,
                            "table_id": t.table_id, "page": t.page, "row": lab, "column": c.col_header,
                            "printed": str(c.value), "computed": str(s), "difference": str(c.value - s),
                            "n_parts": len(parts), "passed": abs(c.value - s) <= tol, "tolerance": str(tol)})
            if is_sub:
                subs.append(c)
                loose = []
            else:
                loose, subs, flow = [], [], []
                prev_total = c
    return out


def _flow_value(flow: list, prev_total) -> Decimal | None:
    """A P-40 money flow: the last line that is not a Less or Plus line (End
    Cost, Full Funding TOA), or the previous total, then each Plus added and
    each Less taken away. "Total Obligational Authority" is that, not a sum
    of every line above it."""
    if not any(k in ("less", "plus") for k, _ in flow):
        return None
    start, value = 0, (prev_total.value if prev_total is not None else None)
    for i, (k, c) in enumerate(flow):
        if k == "item":
            start, value = i + 1, c.value
    if value is None:
        return None
    for k, c in flow[start:]:
        value += c.value if k == "plus" else -c.value
    return value


def _without_group_rows(parts: list, tol: Decimal) -> Decimal | None:
    """A P-10 outline: a group row ("GFE - ORDNANCE 73.8") is followed by its
    items (AEGIS 72.7, Tomahawk 1.1). Adding both counts the group twice.
    Drop each row that equals the sum of the rows right after it (one or
    more: "GFE - ELECTRONICS 13.8" can hold one item, "EXCOMM 13.8")."""
    vals = [p.value for p in parts]
    keep, i, dropped = [], 0, False
    while i < len(vals):
        run, j = Decimal(0), i + 1
        while j < len(vals) and run + vals[j] <= vals[i] + tol:
            run += vals[j]
            j += 1
            if abs(run - vals[i]) <= tol:
                break
        if j > i + 1 and abs(run - vals[i]) <= tol:
            keep.extend(vals[i + 1:j])
            i, dropped = j, True
        else:
            keep.append(vals[i])
            i += 1
    return sum(keep, Decimal(0)) if dropped else None


def _second_reading(c, parts, flow, prev_total, tol, s, rule):
    """When a total does not equal the sum of the rows above it, try the two
    structures budget exhibits print instead. A reading is taken only when it
    reproduces the printed total to its rounding; otherwise the plain sum and
    its failure are reported."""
    v = _flow_value(flow, prev_total)
    if v is not None and abs(c.value - v) <= tol:
        return v, "total_follows_less_and_plus_lines"
    v = _without_group_rows(parts, tol)
    if v is not None and abs(c.value - v) <= tol:
        return v, "total_equals_items_without_group_rows"
    return s, rule


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
