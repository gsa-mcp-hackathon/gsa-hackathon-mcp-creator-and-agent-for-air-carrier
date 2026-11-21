"""Impact page: every figure carries a source and a page, and the page shows it.

    PYTHONPATH=app python -m pytest checks/test_impact.py

The quotes themselves were checked against the page text in
users.xiaobing_shang1_civ.aircarrier_pdf_pages on 2026-11-20 (24 of 24 found on
the cited page of the cited artifact). This suite runs offline and checks what
can be checked without the warehouse: the document is complete and internally
consistent, every derived number recomputes, and the rendered page shows every
figure next to its citation.
"""
import json
import pathlib
import re
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

IMPACT = ROOT / "app" / "data" / "curated" / "impact.json"
DOC = json.loads(IMPACT.read_text())
FIGS = {f["id"]: f for f in DOC["figures"]}
REQUIRED = ("id", "group", "label", "value", "unit", "display", "printed", "scale",
            "source", "page", "quote", "grade")


def test_ids_are_unique():
    assert len(FIGS) == len(DOC["figures"])


@pytest.mark.parametrize("fig", DOC["figures"], ids=lambda f: f["id"])
def test_every_figure_has_a_source_page_and_quote(fig):
    missing = [k for k in REQUIRED if fig.get(k) in (None, "")]
    assert not missing, missing
    src = DOC["sources"].get(fig["source"])
    assert src, f"unknown source {fig['source']}"
    assert re.fullmatch(r"[0-9a-f]{16}", src["artifact_id"]) and src["filename"].endswith(".pdf")
    assert isinstance(fig["page"], int) and fig["page"] >= 1
    assert fig["grade"] in ("VERIFIED", "UNDER REVIEW")


@pytest.mark.parametrize("fig", DOC["figures"], ids=lambda f: f["id"])
def test_value_is_the_printed_number(fig):
    # The number must appear in the quote as printed, and the value is that
    # number times the stated scale (0.001 for exhibits printed in $K).
    assert fig["printed"] in fig["quote"]
    assert float(fig["printed"].replace(",", "")) * fig["scale"] == pytest.approx(fig["value"], abs=1e-9)


def test_every_source_is_used():
    assert {f["source"] for f in DOC["figures"]} == set(DOC["sources"])


def test_hulls_reference_real_figures():
    for h in DOC["hulls"]:
        for k in ("first", "last"):
            assert FIGS[h[k]]["group"] == "hull", h
        if h["cap"]:
            assert FIGS[h["cap"]]["group"] == "caps", h
    assert [h["hull"] for h in DOC["hulls"]] == ["CVN-78", "CVN-79", "CVN-80", "CVN-81"]


def test_derived_numbers_recompute():
    d = {x["id"]: x for x in DOC["derived"]}["cvn79_share_of_portfolio"]
    share = FIGS["tse_79_last"]["value"] / (FIGS["gao_portfolio"]["value"] * 1_000_000)
    assert share == pytest.approx(d["value"], rel=1e-4)
    assert d["display"] == f"{share * 100:.2f}%"
    assert all(i in FIGS for i in d["inputs"])


def test_hull_growth_matches_the_figures():
    import main
    doc = main.impact_doc()
    want = {"CVN-78": 2418.063, "CVN-79": 1998.97, "CVN-80": 1460.269, "CVN-81": 3165.239}
    assert {h["hull"]: h["growth"] for h in doc["hulls"]} == pytest.approx(want, abs=1e-6)


def test_page_renders_every_figure_with_its_citation():
    import main
    from fastapi.testclient import TestClient
    c = TestClient(main.app)
    assert ("/impact", "Impact") in main.NAV
    r = c.get("/impact")
    assert r.status_code == 200 and "{{" not in r.text and "{%" not in r.text
    html = r.text.replace("&#39;", "'").replace("&amp;", "&")
    for f in DOC["figures"]:
        assert f["display"] in html, f["id"]
        assert f"{DOC['sources'][f['source']]['title']}, p.{f['page']}" in html, f["id"]
    api = c.get("/api/impact").json()
    assert len(api["figures"]) == len(DOC["figures"])
