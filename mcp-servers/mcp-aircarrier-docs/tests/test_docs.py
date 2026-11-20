"""Fixture tests: known answers, deliberate failures, input limits. No warehouse, no network."""
import asyncio
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
    ok = "/Volumes/users/xiaobing_shang1_civ/aircarrier_artifacts/a.pdf"
    assert volume.check_path(ok) == ok
    for bad in ("/etc/passwd", "/Volumes/other/s/v/a.pdf", ok.replace("a.pdf", "a.csv"),
                "/Volumes/users/xiaobing_shang1_civ/aircarrier_artifacts/../../x/a.pdf"):
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
