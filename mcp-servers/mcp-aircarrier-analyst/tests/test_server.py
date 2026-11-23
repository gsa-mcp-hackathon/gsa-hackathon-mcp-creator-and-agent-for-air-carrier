"""Server tests on a synthetic corpus: no warehouse, no network.

The store is monkeypatched, so every tool runs end to end through FastMCP
exactly as a client would call it.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path

import pytest

from core.analyst import engine, loa
from mcp_aircarrier_analyst import service, store

P = "N0002415C2114"
SCN18 = "017-2018/2022-1611-000"
RD19 = "017-2018/2019-1319-000"
AWARD = (SCN18, RD19)


def tx(key, date, mod, amt, desc=""):
    return engine.Tx(key, P, date, mod, loa.cents(amt), "", desc, AWARD, ("31.0: Equipment",), ())


def corpus():
    t = [tx("k1", "2018-10-15", "P1", "90"), tx("k2", "2018-11-15", "P2", "10"),
         tx("k3", "2019-01-10", "P3", "50"), tx("k4", "2019-04-10", "P4", "30"),
         tx("k5", "2019-04-20", "P4", "5")]
    fc = [engine.FCRow("FY2019Q1", P, SCN18, "31.0", "0001", loa.cents("90")),
          engine.FCRow("FY2019Q1", P, RD19, "25.1", "0002", loa.cents("10")),
          engine.FCRow("FY2019Q2", P, SCN18, "31.0", "0001", loa.cents("70"))]
    return engine.Corpus(t, fc)


# ------------------------------------------------------------ service

def test_open_questions_lists_residual_and_proven():
    q = service.open_questions(corpus(), P, 10)
    assert q["tied_periods"] == ["FY2019Q1"]
    assert [r["period"] for r in q["residual_periods"]] == ["FY2019Q2"]
    assert q["residual_periods"][0]["gap"] == "$20.00"
    assert q["proven_by_arithmetic"] == 1  # P1: >= 80 of 90 must be SCN18
    assert "k1" not in {t["transaction_key"] for t in q["largest_unattributed_transactions"]}


def test_unknown_piid_rejected_exactly():
    with pytest.raises(service.AnalystError):
        service.open_questions(corpus(), "N0002416C2116")


def test_ambiguous_mod_asks_for_key():
    with pytest.raises(service.AnalystError, match="2 transactions"):
        service.resolve_tx(corpus(), P, "P4")
    assert service.resolve_tx(corpus(), P, transaction_key="k5").key == "k5"


def test_investigate_is_lead_with_three_or_fewer_options():
    c = corpus()
    r = service.investigate_transaction(c, c.get("k1"), None)
    assert r["grade"] == "LEAD" and r["kind"] == "tx"
    assert r["options"][0]["loa"]["tas"] == SCN18
    total = sum(r["posterior_all"].values()) + r["none_of_these"]
    assert abs(total - 1) < 1e-3


def test_residual_rejects_unknown_period():
    with pytest.raises(service.AnalystError, match="Available"):
        service.explain_residual(corpus(), P, "FY2030P03")


def test_outcome_validation():
    c = corpus()
    lead = {"kind": "tx", "piid": P, "subject_key": "k3", "period": "FY2019Q2"}
    ok = service.validate_outcome(lead, SCN18, "section_g_accounting_data", "P00003 p.12 line 3", "SUPSHIP NN", c)
    assert ok["truth"] == SCN18
    with pytest.raises(service.AnalystError, match="evidence_type"):
        service.validate_outcome(lead, SCN18, "email", "P00003 p.12 line 3", "SUPSHIP NN", c)
    with pytest.raises(service.AnalystError, match="cannot fund"):
        service.validate_outcome(lead, "017-2010/2014-1611-000", "section_g_accounting_data", "P00003 p.12", "SUPSHIP", c)
    with pytest.raises(service.AnalystError, match="residual"):
        service.validate_outcome({**lead, "kind": "residual"}, "magic", "file_c_submission", "FY2019Q2 row 4", "DFAS", c)


def test_confirmed_outcome_moves_weights_toward_truth():
    c = corpus()
    w0, i0 = service.current_weights(c, [])
    outs = [{"kind": "tx", "subject_key": "k4", "truth": RD19}, {"kind": "tx", "subject_key": "k5", "truth": RD19}]
    w1, i1 = service.current_weights(c, outs)
    assert i1["labels"]["confirmed_tx"] == 2 and i1["n_cases"] == i0["n_cases"] + 2
    t = c.get("k4")
    p0 = engine.investigate_tx(c, t.key, w0)["posterior_all"].get(RD19, 0)
    p1 = engine.investigate_tx(c, t.key, w1)["posterior_all"].get(RD19, 0)
    assert p1 > p0


# ------------------------------------------------------------ through FastMCP

@pytest.fixture
def fake_store(monkeypatch):
    c = corpus()
    leads: dict = {}
    saved: list = []
    monkeypatch.setattr(store, "corpus", lambda: c)
    monkeypatch.setattr(store, "as_of", lambda: "2026-11-09T00:00:00Z")
    monkeypatch.setattr(store, "weights", lambda: service.current_weights(c, saved))

    def log_lead(result, piid, key, period):
        lid = f"lead-{len(leads):016x}"
        leads[lid] = {"lead_id": lid, "kind": result["kind"], "piid": piid, "subject_key": key,
                      "period": period, "status": "open", "options": json.loads(json.dumps(result["options"], default=str))}
        return {"lead_id": lid, "lead_logged": True}

    def save(lid, row, note, by, rank):
        saved.append(row)
        return "out-0000000000000001"

    monkeypatch.setattr(store, "log_lead", log_lead)
    monkeypatch.setattr(store, "get_lead", lambda lid: leads.get(lid))
    monkeypatch.setattr(store, "save_outcome", save)
    return leads, saved


def call(name, args):
    from fastmcp import Client

    from mcp_aircarrier_analyst.app import mcp

    async def go():
        async with Client(mcp) as cl:
            return await cl.call_tool(name, args, raise_on_error=False)
    return asyncio.run(go())


def payload(res):
    return res.structured_content if res.structured_content is not None else json.loads(res.content[0].text)


HINTS = {"readOnlyHint", "destructiveHint", "idempotentHint", "openWorldHint"}


def literal_hints_and_try(tools_py, expected):
    """m8ven scan, 2026-11-23. A scanner reads the decorator, not the running server:
    hints supplied through a shared dict (**READ) were served correctly but reported
    missing. Each decorator must state all four as literals, and each handler must
    hold an explicit try/except."""
    import ast

    with open(tools_py, encoding="utf-8") as f:
        tree = ast.parse(f.read())
    seen = 0
    for fn in ast.walk(tree):
        if not isinstance(fn, ast.FunctionDef):
            continue
        for d in fn.decorator_list:
            if isinstance(d, ast.Call) and getattr(d.func, "attr", "") == "tool":
                ann = next(k.value for k in d.keywords if k.arg == "annotations")
                assert isinstance(ann, ast.Dict), fn.name
                literal = {k.value for k, v in zip(ann.keys, ann.values)
                           if isinstance(k, ast.Constant) and isinstance(v, ast.Constant) and isinstance(v.value, bool)}
                assert HINTS <= literal, (fn.name, sorted(HINTS - literal))
                assert any(isinstance(n, ast.Try) for n in fn.body), fn.name
                seen += 1
    assert seen == expected


def test_tools_listed():
    from fastmcp import Client

    from mcp_aircarrier_analyst.app import mcp

    async def go():
        async with Client(mcp) as cl:
            return {t.name: t for t in await cl.list_tools()}
    tools = asyncio.run(go())
    assert set(tools) == {"analyst_open_questions", "analyst_investigate_transaction", "analyst_investigate_window",
                          "analyst_explain_residual", "analyst_backtest", "analyst_model_status", "analyst_record_outcome",
                          "analyst_investigate_record", "analyst_profile_record", "analyst_list_sources",
                          "analyst_search_documents", "analyst_trace_entity"}
    assert all(t.description and len(t.description) > 80 for t in tools.values())
    assert tools["analyst_record_outcome"].annotations.readOnlyHint is False
    # The four tools that append to the leads table must not claim to be read-only.
    logs_lead = {"analyst_investigate_record", "analyst_investigate_transaction",
                 "analyst_investigate_window", "analyst_explain_residual"}
    for name, t in tools.items():
        a = t.annotations
        assert a.destructiveHint is False, name
        if name in logs_lead or name == "analyst_record_outcome":
            assert a.readOnlyHint is False, name
        else:
            assert a.readOnlyHint is True, name
    literal_hints_and_try(Path(__file__).resolve().parents[1] / "src/mcp_aircarrier_analyst/tools.py", 12)


def test_investigate_then_record_round_trip(fake_store):
    leads, saved = fake_store
    r = payload(call("analyst_investigate_transaction", {"piid": P, "modification_number": "P3"}))
    assert r["grade"] == "LEAD" and r["lead_logged"] and r["lead_id"] in leads
    out = payload(call("analyst_record_outcome", {
        "lead_id": r["lead_id"], "truth": SCN18, "evidence_type": "section_g_accounting_data",
        "evidence_locator": "P3 Section G p.4 ACRN AA", "confirming_office": "SUPSHIP Newport News"}))
    assert out["rank_of_truth"] == 1 and out["model"]["labels"]["confirmed_tx"] == 1
    assert "No claim" in out["note"] and len(saved) == 1


def test_record_outcome_refuses_bad_evidence(fake_store):
    r = payload(call("analyst_investigate_transaction", {"piid": P, "transaction_key": "k3"}))
    bad = call("analyst_record_outcome", {"lead_id": r["lead_id"], "truth": SCN18, "evidence_type": "hunch",
                                          "evidence_locator": "somewhere long", "confirming_office": "me"})
    assert bad.is_error


def test_errors_are_tool_errors(fake_store, monkeypatch):
    res = call("analyst_explain_residual", {"piid": P, "submission_period": "FY2030P03"})
    assert res.is_error and "Available" in res.content[0].text
    res = call("analyst_investigate_transaction", {"piid": "N0002416C2116", "modification_number": "P1"})
    assert res.is_error

    # An unexpected error reaches the client without its text (m8ven scan, 2026-11-23).
    # Before the fix the reply was "Error calling tool '...': <the exception text>".
    def boom(*a, **k):
        raise RuntimeError("SECRET host=example token=abc path=/Volumes/private/x")

    monkeypatch.setattr(service, "open_questions", boom)
    text = (res := call("analyst_open_questions", {"piid": P})).content[0].text
    assert res.is_error and "SECRET" not in text and "/Volumes" not in text
    assert "analyst_open_questions" in text and "RuntimeError" in text


def test_window_residual_backtest_status(fake_store):
    w = payload(call("analyst_investigate_window", {"piid": P, "fiscal_year": 2019, "first_period": 7, "last_period": 9}))
    assert w["options"][0]["tas"] and w["lead_logged"]
    rz = payload(call("analyst_explain_residual", {"piid": P, "submission_period": "FY2019Q2"}))
    assert rz["gap"] == "$20.00" and rz["grade"] == "LEAD"
    b = payload(call("analyst_backtest", {"piid": P}))
    assert b["n_tx_labels"] >= 1 and "period_baseline_top1" in b
    s = payload(call("analyst_model_status", {}))
    assert s["priors"] == engine.PRIOR_WEIGHTS and "section_g_accounting_data" in s["accepted_evidence"]


# ------------------------------------------------------------ vendoring

# The One Hub core this server vendors. In a clone it sits in the same repo, so
# the check runs everywhere (it used to point at one workspace path and skip
# elsewhere). AIRCARRIER_BUNDLE_CORE overrides it, for example with the deployed
# bundle in the workspace.
BUNDLE = Path(os.getenv("AIRCARRIER_BUNDLE_CORE",
                        str(Path(__file__).resolve().parents[3] / "the-one-hub" / "ops-center" / "core")))
VENDORED = ("catalog.py", "analyst/__init__.py", "analyst/loa.py", "analyst/engine.py", "analyst/learn.py",
            "analyst/backtest.py", "analyst/residual.py", "analyst/sources.py")


@pytest.mark.skipif(not BUNDLE.exists(), reason="bundle not readable here")
@pytest.mark.parametrize("rel", VENDORED)
def test_vendored_engine_matches_bundle(rel):
    here = Path(engine.__file__).parents[1] / rel
    h = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    assert h(here) == h(BUNDLE / rel), f"src/core/{rel} drifted from the bundle; recopy it"
