"""Fixture tests: known answers, deliberate failures, input limits. No warehouse, no network."""
import asyncio
import json
import os
import sys
from decimal import Decimal

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from docs_core import extract, grid, search, structure, tieout
from docs_core import numbers as N
from docs_core.corpus import Corpus
from mcp_aircarrier_docs import service, store, volume

AID = "bb2e90fd1d91a0bc"
TITLE = ["Exhibit P-5c, Ship Cost Analysis: PB 2027 Navy", "Date: April 2026"]
HEAD = [["Exhibit P-5c, Ship Cost Analysis: PB 2027 Navy", "", "", "Date: April 2026"],
        ["Cost Categories", "FY 2013", "", ""],
        ["", "Qty (Each)", "", "Total Cost ($ M)"]]
P95 = HEAD + [["Plan Costs", "1", "", "898.865"], ["Basic Construction/Conversion", "", "", "8,463.156"],
              ["Change Orders", "", "", "432.065"], ["Electronics (\u2020)", "", "", "263.359"],
              ["Propulsion Equipment", "", "", "2,041.582"], ["HM&E (\u2020)", "", "", "30.302"],
              ["Ordnance (\u2020)", "", "", "1,149.651"], ["Other Cost", "", "", "130.990"],
              ["Total Ship Estimate", "", "", "13,409.970"], ["Less Advance Procurement FY 2007", "", "", "10,831.718"]]
P96 = HEAD + [["Less Cost to Complete FY 2022", "", "", "2,087.300"], ["Net P-1 Funding", "", "", "490.952"]]
PAGE_TEXT = ("Exhibit P-40, Budget Line Item Justification: PB 2027 Navy\nLI 2001 - Carrier Replacement Program\n"
             "The total ship estimate is $13,409.970 million.")
P5C_TEXT = "Exhibit P-5c, Ship Cost Analysis: PB 2027 Navy\nP-1 Line Item Number / Title:\n2001 / Carrier Replacement Program"


def rows(p95=P95, p96=P96, link=True):
    pages = [{"artifact_id": AID, "filename": "SCN_Book PB27.pdf", "page": 93, "text": PAGE_TEXT},
             {"artifact_id": AID, "filename": "SCN_Book PB27.pdf", "page": 95, "text": P5C_TEXT},
             {"artifact_id": AID, "filename": "SCN_Book PB27.pdf", "page": 96, "text": P5C_TEXT},
             {"artifact_id": "c" * 16, "filename": "RS20643 CRS.pdf", "page": 14,
              "text": "Table 2. CVN-79 estimates\nFY25 12,936.0 FY26 13,196.0"}]
    tables = [{"table_id": f"{AID}:0095:00", "artifact_id": AID, "filename": "SCN_Book PB27.pdf", "page": 95,
               "grid_json": p95, "title_block": TITLE, "legends": [], "exhibits": [], "continuation_of": None},
              {"artifact_id": AID, "table_id": f"{AID}:0096:00", "filename": "SCN_Book PB27.pdf", "page": 96,
               "grid_json": p96, "title_block": TITLE, "legends": [], "exhibits": [],
               "continuation_of": f"{AID}:0095:00" if link else None}]
    return pages, tables


@pytest.fixture
def corpus():
    c = Corpus(*rows())
    store.set_corpus(c)
    return c


# ----------------------------------------------------------------- numbers
@pytest.mark.parametrize("tok,val", [("13,409.970", Decimal("13409.970")), ("(1,234.5)", Decimal("-1234.5")),
                                     ("-", None), ("n/a", None), ("2,041.582\u2020", Decimal("2041.582")),
                                     ("FY 2013", None), ("12.5%", Decimal("12.5"))])
def test_parse(tok, val):
    assert N.parse(tok) == val


def test_places_and_scales():
    assert N.places("13,409.970") == 3
    assert N.scale_of("Total Cost ($ M)")[1] == "M"
    assert N.scale_of("TY $K")[1] == "K"
    assert N.scale_of("Qty (Each)") is None
    assert N.to_millions(Decimal(1500), "K") == Decimal("1.5")


def test_variants_match_prose():
    pats = N.variants(Decimal("13409.97"))
    assert any(p.search("estimate is $13,409.970 million") for p in pats)
    assert not any(p.search("value 113,409.97") for p in pats)


def test_variants_billions_three_places():
    """MSAR prose prints $12.936 billion and $13.529 billion (wrapped across a line)."""
    hit = lambda v, s: any(p.search(s) for p in N.variants(Decimal(v)))
    assert hit("13529", "from $12.936\nbillion to $13.529 billion.")
    assert hit("12936", "from $12.936\nbillion to $13.529 billion.")
    assert hit("13529", "about $13.53 billion")             # rounded print, as before
    assert hit("13500", "$13.5 billion")                    # exact one place
    assert not hit("13529", "$13.5 billion")                # inexact one place
    assert not hit("13529", "$113.529 billion")             # not inside a larger number
    assert not hit("13409.97", "$13.410 billion")           # inexact three places


# -------------------------------------------------------------------- grid
def test_headers_units_and_count_columns():
    t = grid.build("x", AID, "f", 95, P95, TITLE)
    assert t.header_rows == 3
    total = t.numeric(11, 3)
    assert total.row_header == "Total Ship Estimate" and total.value == Decimal("13409.970")
    assert total.scale == "M" and "Total Cost ($ M)" in total.col_header
    assert t.numeric(3, 1).scale is None  # Qty (Each) is a count, not $M


# ----------------------------------------------------------------- tie-outs
def test_p5c_ties_to_the_cent(corpus):
    res = corpus.tieouts(f"{AID}:0095:00")
    by = {r["rule"]: r for r in res}
    assert by["total_equals_sum_of_rows"]["passed"] and by["total_equals_sum_of_rows"]["computed"] == "13409.970"
    assert by["total_less_prior_funding_equals_net"]["passed"]
    assert by["total_less_prior_funding_equals_net"]["computed"] == "490.952"


def test_a_wrong_cell_fails():
    bad = [r[:] for r in P95]
    bad[4][3] = "8,463.157"  # one unit off in the last place is caught
    bad[5][3] = "432.066"
    c = Corpus(*rows(p95=bad))
    r = next(x for x in c.tieouts(f"{AID}:0095:00") if x["rule"] == "total_equals_sum_of_rows")
    assert not r["passed"] and r["difference"] == "-0.002"


def test_subtotals_roll_up():
    g = [["Item", "Cost ($ M)"], ["A", "1.0"], ["B", "2.0"], ["P-35 Items Subtotal", "3.0"],
         ["C", "4.0"], ["D", "5.0"], ["Major Items Subtotal", "9.0"], ["Total Electronics", "12.0"]]
    res = tieout.check_totals(grid.build("t", AID, "f", 1, g))
    assert [r["passed"] for r in res] == [True, True, True]
    assert res[-1]["computed"] == "12.0"  # subtotals, not subtotals plus their items


def test_a_cost_element_named_total_is_read_as_an_item():
    # SCN PB27 p.357 (LHA 3041 P-8a): "Total Ship Test Program" is a cost element
    # inside Other Cost Elements. Read as a total it failed, the 4 of 818 failures.
    g = [["Item", "Cost ($ M)"], ["A", "136.028"], ["P-35 Items Subtotal", "136.028"],
         ["B", "10.485"], ["Major Items Subtotal", "10.485"], ["Aviation Support", "8.202"],
         ["Miscellaneous Ordnance", "2.964"], ["Total Ship Test Program", "11.063"],
         ["Other Cost Elements Subtotal", "22.229"], ["Total Ordnance", "168.742"]]
    res = tieout.check_totals(grid.build("t", AID, "f", 1, g))
    assert all(r["passed"] for r in res)
    assert "Total Ship Test Program" not in {r["row"] for r in res}
    assert res[-1]["row"] == "Total Ordnance" and res[-1]["computed"] == "168.742"


def test_a_real_total_followed_by_a_subtotal_is_kept():
    # Two exhibits joined over pages: the first exhibit's total ties, so it stays a total.
    g = [["Item", "Cost ($ M)"], ["A", "1.0"], ["P-35 Items Subtotal", "1.0"], ["B", "2.0"],
         ["Major Items Subtotal", "2.0"], ["Total Electronics", "3.0"], ["C", "4.0"],
         ["P-35 Items Subtotal", "4.0"], ["D", "5.0"], ["Major Items Subtotal", "5.0"],
         ["Total Ordnance", "9.0"]]
    res = tieout.check_totals(grid.build("t", AID, "f", 1, g))
    assert "Total Electronics" in {r["row"] for r in res} and all(r["passed"] for r in res)


def test_a_wrong_total_is_not_hidden_by_the_item_reading():
    # Reading a failing total as an item must not just move the failure elsewhere.
    g = [["Item", "Cost ($ M)"], ["A", "1.0"], ["B", "2.0"], ["Total Widgets", "4.0"],
         ["Subtotal", "8.0"], ["Total", "8.0"]]
    res = tieout.check_totals(grid.build("t", AID, "f", 1, g))
    assert [r["row"] for r in res if not r["passed"]] == ["Total Widgets"]


def test_continuation_inferred_and_flagged():
    c = Corpus(*rows(link=False))
    t = c.tables[f"{AID}:0096:00"]
    assert t.continuation_of == f"{AID}:0095:00" and t.link_inferred


# ---------------------------------------------------- structure and search
def test_structure_labels():
    lab = structure.label_page("budget_justification", P5C_TEXT)
    assert lab["exhibit"] == "P-5c" and lab["line_item"] == "2001"
    assert structure.doc_kind("SCN_Book PB27.pdf") == "budget_justification"
    assert structure.doc_kind("CVN 78 MSAR Dec 2023.pdf") == "selected_acquisition_report"


def test_numeric_tokens_normalise():
    assert search.tokens("$13,409.970") == search.tokens("13409.97")


def test_table_is_one_chunk(corpus):
    t = [c for c in corpus.chunks.values() if c.kind == "table" and c.table_id == f"{AID}:0095:00"]
    assert len(t) == 1 and "13,409.970" in t[0].text and "Unit: $ M" in t[0].text


# ------------------------------------------------------------------ service
def test_compare_figures(corpus):
    r = service.compare_figures(corpus, [{"label": "PB27", "value_musd": "13409.97"},
                                         {"label": "CLB", "value_musd": "12936"},
                                         {"label": "step", "value_musd": "12698"}])
    f = {x["label"]: x for x in r["figures"]}
    assert f["PB27"]["authoritative"] and f["PB27"]["found"]
    assert f["CLB"]["found"] and not f["CLB"]["authoritative"]
    assert not f["step"]["found"] and r["summary"]["not_found"] == ["step"]


def test_line_item_and_table(corpus):
    li = service.find_line_item(corpus, "2001", "P-5c")
    assert li["sections"][0]["table_chains"] == [f"{AID}:0095:00"]
    gt = service.get_table(corpus, f"{AID}:0095:00")
    assert gt["tieout_status"] == "pass" and gt["pages"] == [95, 96]


@pytest.mark.parametrize("text,cycle", [
    ("SCN_Book PB27.pdf", "PB2027"), ("SCN Book PB 2024.pdf", "PB2024"),
    ("the PB 2024 SCN book", "PB2024"), ("FY2024", "PB2024"), ("pb24", "PB2024"),
    ("CVN_78_MSAR_FY2027_PBv2.pdf", "PB2027"), ("RS20643 CRS.pdf", ""), ("PB2024x9", "PB2024"),
    # The real SCN file names, with the cycle fused to the word before it.
    ("SCN_BookPB2024.pdf", "PB2024"), ("SCN_Bookpb2006.pdf", "PB2006"), ("SCN_BOOKpb2014.pdf", "PB2014"),
])
def test_budget_cycle_joins_the_spellings(text, cycle):
    assert service.budget_cycle(text) == cycle


def test_line_item_by_budget_cycle(corpus):
    li = service.find_line_item(corpus, "2001", "P-5c", "PB 2027")
    assert li["sections"] and all(s["budget_cycle"] == "PB2027" for s in li["sections"])
    other = service.find_line_item(corpus, "2001", "P-5c", "PB2024")
    assert other["sections"] == [] and "not loaded" in other["note"]
    assert other["loaded_cycles"] == ["PB2027"]
    with pytest.raises(service.DocsError):
        service.find_line_item(corpus, "2001", "P-5c", "next year")


def test_cycle_falls_back_to_the_exhibit_headers():
    pages, tables = rows()
    for r in pages + tables:
        if r["artifact_id"] == AID:
            r["filename"] = "carrier_book.pdf"
    c = Corpus(pages, tables)
    assert service.doc_cycle(c.docs[AID]) == "PB2027"
    li = service.find_line_item(c, "2001", "P-5c", "PB2027")
    assert li["sections"] and li["loaded_cycles"] == ["PB2027"]


def test_ship_cost_cells_carry_hull_and_share(corpus):
    cells = service.get_table(corpus, f"{AID}:0095:00")["tables"][0]["numeric_cells"]
    by_row = {c["row_header"]: c for c in cells if c["col_header"].endswith("Total Cost ($ M)")}
    assert by_row["Propulsion Equipment"]["hull"] == "CVN-79"
    assert by_row["Propulsion Equipment"]["ship_fy"] == "2013"
    assert by_row["Basic Construction/Conversion"]["share_of_total_ship_estimate_pct"] == "63.11"
    assert by_row["Propulsion Equipment"]["share_of_total_ship_estimate_pct"] == "15.22"
    assert "share_of_total_ship_estimate_pct" not in by_row["Total Ship Estimate"]


def test_service_rejects_bad_input(corpus):
    with pytest.raises(service.DocsError):
        service.find_figure(corpus, "abc")
    with pytest.raises(service.DocsError):
        service.find_figure(corpus, "100", "50")
    with pytest.raises(service.DocsError):
        service.read_page(corpus, "0" * 16, 1)
    with pytest.raises(service.DocsError):
        service.find_line_item(corpus, "20x1")


def test_volume_paths():
    ok = "/Volumes/main/aircarrier/artifacts/a.pdf"
    assert volume.check_path(ok) == ok
    for bad in ("/etc/passwd", "/Volumes/other/s/v/a.pdf", ok.replace("a.pdf", "a.csv"),
                "/Volumes/main/aircarrier/artifacts/../../x/a.pdf"):
        with pytest.raises(volume.VolumeError):
            volume.check_path(bad)


def test_extract_limits():
    with pytest.raises(extract.ExtractError):
        extract.extract(b"not a pdf", "x.pdf")
    assert extract.parse_pages("1-3,5", 10) == [1, 2, 3, 5]
    with pytest.raises(extract.ExtractError):
        extract.parse_pages("1-100", 500)


# --------------------------------------------------------------------- MCP
def test_mcp_tools_registered_and_callable(corpus):
    from fastmcp import Client

    from mcp_aircarrier_docs.app import mcp

    async def go():
        async with Client(mcp) as cl:
            names = {t.name for t in await cl.list_tools()}
            r = await cl.call_tool("docs_get_table", {"table_id": f"{AID}:0095:00"})
            e = await cl.call_tool("docs_get_table", {"table_id": "bad"}, raise_on_error=False)
            return names, r.structured_content, e.is_error

    names, gt, err = asyncio.run(go())
    assert len(names) == 11 and "docs_compare_figures" in names
    assert gt["tieout_status"] == "pass" and err


TRAPS = [("Large Aperture Bow", "LAB array is a submarine bow sonar. Carriers do not carry one"),
         ("CVN-80", "Enterprise"), ("SSBN", "ballistic missile submarine")]


def test_premise_flags_name_the_trap_and_why():
    """Eval Q8: agents spent up to 255k tokens searching for a submarine sonar on a carrier."""
    f = service.premise_flags("How much did CVN 79 pay for its large aperture bow array?", TRAPS)
    assert f == [{"term": "Large Aperture Bow", "why": TRAPS[0][1]}]
    assert service.premise_flags("CVN-80 cost", TRAPS)[0]["term"] == "CVN-80"


def test_premise_flags_need_word_boundaries():
    assert service.premise_flags("SSBNX program", TRAPS) == []
    assert service.premise_flags("CVN-800", TRAPS) == []
    assert service.premise_flags("Cost Limitation Baseline CVN 79", TRAPS) == []


def test_premise_terms_never_break_search_when_unavailable():
    def boom():
        raise PermissionError("no SELECT on kg_nodes")

    saved = dict(store._premise)
    try:
        store._premise.update(terms=None, loaded=0.0, fixed=False)
        assert store.premise_terms(boom) == []
    finally:
        store._premise.clear()
        store._premise.update(saved)


def test_hull_label_needs_the_carrier_line():
    # 2026-11-20 (B1): the year-to-hull map was applied to every ship cost exhibit, so a
    # DDG-51 or refueling-overhaul column headed "FY 2013" came back labelled CVN-79.
    def part(line):
        return [{"title_block": ["Exhibit P-5c, Ship Cost Analysis: PB 2027 Navy"],
                 "numeric_cells": [{"row_header": "Total Ship Estimate", "col_header": "FY 2020 Total Cost ($ M)",
                                    "value_musd": "1000.0"},
                                   {"row_header": "Plan Costs", "col_header": "FY 2020 Total Cost ($ M)",
                                    "value_musd": "250.0"}]}]
    rcoh, cvn81, unknown = part("2086"), part("2004"), part("")
    service._ship_cost_labels(rcoh, "2086")
    service._ship_cost_labels(cvn81, "2004")
    service._ship_cost_labels(unknown, "")
    assert all("hull" not in c for c in rcoh[0]["numeric_cells"])
    assert rcoh[0]["numeric_cells"][1]["ship_fy"] == "2020"
    assert rcoh[0]["numeric_cells"][1]["share_of_total_ship_estimate_pct"] == "25.00"
    assert cvn81[0]["numeric_cells"][1]["hull"] == "CVN-81"
    assert all("hull" not in c for c in unknown[0]["numeric_cells"])
    assert service._p1_line("P-1 Line Item Number / Title:\n2001 / Carrier Replacement Program") == "2001"


# ------------------------------------------------------------- corpus cache
def _reset_store(monkeypatch, ttl=0):
    monkeypatch.setattr(store.config, "CACHE_TTL_S", ttl)
    store._refreshing.clear()
    store._state.update(corpus=None, loaded=0.0, as_of=None)


def test_a_stale_corpus_is_served_while_it_refreshes(monkeypatch):
    # The reload used to run inside the request after the TTL: the slow mode of the
    # docs known-answer latency. Now the caller gets the copy in hand at once.
    import threading
    _reset_store(monkeypatch)
    calls, gate = [], threading.Event()

    def loader():
        calls.append(1)
        if len(calls) > 1:
            gate.wait(5)
        return rows()

    first = store.corpus(loader)
    store._state["loaded"] = 0.0          # past the TTL
    second = store.corpus(loader)          # returns at once; refresh waits on the gate
    assert second is first and len(calls) == 2
    gate.set()
    for _ in range(100):
        if not store._refreshing.is_set():
            break
        threading.Event().wait(0.02)
    assert not store._refreshing.is_set() and store._state["corpus"] is not first


def test_a_failed_refresh_keeps_the_corpus(monkeypatch):
    _reset_store(monkeypatch)
    first = store.corpus(lambda: rows())
    store._state["loaded"] = 0.0

    def broken():
        raise RuntimeError("warehouse down")

    assert store.corpus(broken, background=False) is first
    assert not store._refreshing.is_set()  # the next stale call tries again


def test_a_p40_money_flow_is_read_as_less_and_plus_lines():
    # SCN PB2006 p.164: Total Obligational Authority is Full Funding TOA plus
    # Advance Procurement, not the sum of every line above it (that doubled it).
    g = [["Item", "FY 2006 ($ M)"], ["End Cost", "24.9"], ["Less Advance Procurement", "0.0"],
         ["Less Escalation", "0.0"], ["Full Funding TOA", "24.9"], ["Plus Advance Procurement", "0.0"],
         ["Total Obligational Authority", "24.9"]]
    res = tieout.check_totals(grid.build("t", AID, "f", 1, g))
    assert [(r["rule"], r["passed"]) for r in res] == [("total_follows_less_and_plus_lines", True)]
    bad = [r[:] for r in g]
    bad[-1][1] = "25.9"                                   # a real error still fails
    assert not tieout.check_totals(grid.build("t", AID, "f", 1, bad))[0]["passed"]


def test_p10_group_rows_are_not_counted_twice():
    # SCN PB2011 p.142: a group row is followed by its items.
    g = [["Item", "FY10 ($ M)"], ["SHIPBUILDER CLASS STANDARD EQUIPMENT (3)", "66.9"],
         ["CRP Propeller (3)", "3.1"], ["LM 2500 (3)", "63.8"], ["OTHER SHIPBUILDING MATERIAL (4)", "13.4"],
         ["GFE - ELECTRONICS (5)", "13.8"], ["EXCOMM Equipment (5)", "13.8"], ["Total AP", "94.1"]]
    [r] = tieout.check_totals(grid.build("t", AID, "f", 1, g))
    assert r["passed"] and r["rule"] == "total_equals_items_without_group_rows"


def test_a_quantity_row_is_not_money_but_economic_order_quantity_is():
    assert tieout.COUNT.search("End Item Qty") and tieout.COUNT.search("PLT in Months")
    assert not tieout.COUNT.search("Economic Order Quantity")
    g = [["Item", "FY 2009 ($ M)"], ["End Item Qty", "1"], ["ERO AP", "6.8"], ["Other AP", "2.0"],
         ["Total Advance Procurement", "8.8"]]
    [r] = tieout.check_totals(grid.build("t", AID, "f", 1, g))
    assert r["passed"] and r["computed"] == "8.8"


# ------------------------------------- round 10 (A9): the nine failing tie-outs, read again
def test_a_number_split_by_a_stray_space_is_read():
    # PB2006 P-40 p.167 prints "5 .2" and "3 3.2"; the First Destination row dropped out.
    from docs_core.numbers import parse

    assert parse("5 .2") == Decimal("5.2") and parse("3 3.2") == Decimal("33.2")
    assert parse("3.3 4.4") is None and parse("3 4") is None  # two values, not one
    g = [["BUDGET ITEM JUSTIFICATION SHEET (P-40) ($M)", "", ""],
         ["", "FY 2011", "TOTAL"],
         ["Full Funding TOA-Outfitting", "162.4", "3,052.1"],
         ["Full Funding TOA-Post Delivery", "195.9", "3,925.2"],
         ["Full Funding TOA-First Destination", "5 .2", "3 3.2"],
         ["Total Obligational Authority", "363.5", "7,010.5"]]
    res = tieout.check_totals(grid.build("t", AID, "f", 167, g))
    assert len(res) == 2 and all(r["passed"] for r in res), res


def test_a_row_collapsed_into_its_label_is_split_back():
    # PB2022 P-5 p.376: a label wrapping at the page foot swallowed $119.746M.
    g = [["Cost Elements ($ M)", "FY 2021", "", "FY 2022", "FY 2022 Total"],
         ["", "Total Cost ($ M)", "", "Total Cost ($ M)", "Total Cost ($ M)"],
         ["4.1) CVN 78 Advanced Weapons Elevator", "71.000", "", "-", "-"],
         ["4.2) Govt responsible - 119.746 119.746 portion of shpbldg", "", "", "", ""],
         ["4.3) CVN 79 properly priced GFE", "-", "", "63.060", "63.060"],
         ["Subtotal: CVN - Carrier Replacement Cost", "71.000", "", "182.806", "182.806"]]
    t = grid.build("t", AID, "f", 376, g)
    assert t.grid[3][0] == "4.2) Govt responsible portion of shpbldg"
    assert t.grid[3][3] == "119.746" and t.grid[3][4] == "119.746"
    res = tieout.check_totals(t)
    assert res and all(r["passed"] for r in res), res


def _p5_page(page, rows, ncols_pad):
    pad = [""] * ncols_pad
    head = [["Exhibit P-5, Cost Analysis: PB 2023 Navy"] + [""] * (3 + ncols_pad),
            ["Resource Summary", "FY 2023 Base"] + pad + ["", ""],
            ["Procurement Quantity (Units in Each)", "-"] + pad + ["", ""],
            ["Cost Elements", "Unit Cost ($ M)"] + pad + ["Qty (Each)", "Total Cost ($ M)"]]
    body = [[lab, "-"] + pad + ["-", v] for lab, v in rows]
    return {"artifact_id": AID, "filename": "SCN_Bookpb2023.pdf", "page": page,
            "table_id": f"{AID}:{page:04d}:00", "grid_json": json.dumps(head + body),
            "title_block": ["Exhibit P-5, Cost Analysis: PB 2023 Navy"]}


def test_a_subtotal_whose_items_start_on_the_page_before_ties_over_both_pages():
    # PB2023 P-5 p.448-449: the extractor split the same columns 26 and 21 ways,
    # so the pages were never linked, and the page above had no unit at all
    # (its Resource Summary block came first), so its rows were never checked.
    from docs_core.corpus import Corpus

    p448 = _p5_page(448, [("3.1) Proper pricing of LCS 27", "21.530"),
                          ("3.2) Combining Gear repairs", "35.750")], 2)
    p449 = _p5_page(449, [("3.3) Crypto Modernization", "4.183"),
                          ("3.6) Shipyard Rate impacts", "6.338"),
                          ("Subtotal: Littoral Combat Ship (LCS) Cost", "67.801")], 0)
    pages = [{"artifact_id": AID, "filename": "SCN_Bookpb2023.pdf", "page": p, "text": "Exhibit P-5"}
             for p in (448, 449)]
    c = Corpus(pages, [p448, p449])
    assert c.tables[f"{AID}:0449:00"].continuation_of == f"{AID}:0448:00"
    res = c.tieouts(f"{AID}:0448:00")
    sub = [r for r in res if r["row"].startswith("Subtotal")]
    assert sub and all(r["passed"] and r["scope"] == "joined_pages" for r in sub), res


def test_rounding_is_reported_apart_and_never_passes():
    # PB2008 P-27 p.122: seven rows each rounded to 0.1 miss the printed total by 0.2.
    g = [["Item ($ in Millions)", "CY FY07"]] + [[f"Item {i}", v] for i, v in enumerate(
        ["10.1", "20.2", "30.3", "15.5", "20.6", "10.0", "10.1"])] + [["Total AP", "116.6"]]
    [r] = tieout.check_totals(grid.build("t", AID, "f", 122, g))
    assert not r["passed"] and r["verdict"] == "within_rounding_bound"
    assert Decimal(r["rounding_bound"]) == Decimal("0.40")
    g[-1] = ["Total AP", "117.9"]  # 1.1 off: more than rounding can explain
    [r] = tieout.check_totals(grid.build("t", AID, "f", 122, g))
    assert r["verdict"] == "fails"


def test_a_failing_total_reports_its_closest_reading():
    # PB2007 P-40 p.66, TOTAL PROGRAM: the money flow is 0.5 off (five years each
    # rounded by 0.1), the plain sum 2,014.1 off. The flow is the residual to explain.
    g = [["P-40 ($M)", "FY 2005", "FY 2006", "TOTAL PROGRAM"],
         ["End Cost", "291.0", "361.4", "2450.2"],
         ["Less Advance Procurement", "30.0", "134.3", "434.3"],
         ["Full Funding TOA", "260.9", "227.0", "2014.1"],
         ["Plus Advance Procurement", "63.6", "61.3", "435.6"],
         ["Total Obligational Authority", "324.6", "288.3", "2450.2"]]
    r = next(x for x in tieout.check_totals(grid.build("t", AID, "f", 66, g))
             if x["column"].endswith("TOTAL PROGRAM"))
    assert r["rule"] == "total_follows_less_and_plus_lines" and r["computed"] == "2449.7"
    assert r["verdict"] == "within_rounding_bound"
