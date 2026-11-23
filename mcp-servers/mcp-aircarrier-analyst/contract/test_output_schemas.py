"""Every analyst_ tool lists a typed output schema, and a real answer fits it.

FastMCP checks each result against the tool's output schema before it leaves
the server, so a model in output_models.py that is stricter than the code
turns a working tool into an error. This calls every tool through the MCP
client on the synthetic corpus and fake sources the unit tests use, and fails
if any answer is refused. Run: PYTHONPATH=src python -m pytest contract
"""
import asyncio
import importlib.util
import json
import sys
from pathlib import Path

import pytest
from fastmcp import Client

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))

from mcp_aircarrier_analyst import library, service, store, warehouse
from mcp_aircarrier_analyst.app import mcp


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, HERE.parent / "tests" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SERVER = _load("test_server")
INVESTIGATOR = _load("test_investigator")
PIID = SERVER.P
RECORD = {"GL Amount": "$454,765,071.00", "Memo": "SCN progress payment CVN 79"}


@pytest.fixture
def sources(monkeypatch):
    """The unit tests' corpus, an in-memory lead log, and fake document sources."""
    corpus = SERVER.corpus()
    leads: dict = {}
    saved: list = []

    def log_lead(result, piid, key, period):
        lead_id = f"lead-{len(leads):016x}"
        leads[lead_id] = {"lead_id": lead_id, "kind": result["kind"], "piid": piid, "subject_key": key,
                          "period": period, "status": "open",
                          "options": json.loads(json.dumps(result["options"], default=str))}
        return {"lead_id": lead_id, "lead_logged": True}

    def save_outcome(lead_id, row, note, recorded_by, rank):
        saved.append(row)
        return "out-0000000000000001"

    monkeypatch.setattr(store, "corpus", lambda: corpus)
    monkeypatch.setattr(store, "as_of", lambda: "2026-11-09T00:00:00Z")
    monkeypatch.setattr(store, "weights", lambda: service.current_weights(corpus, saved))
    monkeypatch.setattr(store, "log_lead", log_lead)
    monkeypatch.setattr(store, "get_lead", lambda lead_id: leads.get(lead_id))
    monkeypatch.setattr(store, "save_outcome", save_outcome)
    monkeypatch.setattr(library, "knowledge", lambda: INVESTIGATOR.K)
    monkeypatch.setattr(library, "SqlSources", lambda: INVESTIGATOR.Fake([INVESTIGATOR.TX]))
    monkeypatch.setattr(warehouse, "run", lambda sql, params=None: [])


def _call(name: str, arguments: dict):
    async def go():
        async with Client(mcp) as client:
            return await client.call_tool(name, arguments, raise_on_error=False)

    return asyncio.run(go())


def _fits(result) -> dict:
    assert not result.is_error, result.content[0].text
    assert result.structured_content
    return result.structured_content


CALLS = [
    ("analyst_investigate_record", {"record": RECORD}),
    ("analyst_investigate_record", {"record": RECORD, "detail": "full"}),
    ("analyst_investigate_record", {"record": {"note": "nothing usable"}}),
    ("analyst_profile_record", {"record": RECORD}),
    ("analyst_list_sources", {}),
    ("analyst_search_documents", {"query": "N00024-15-C-2114"}),
    ("analyst_trace_entity", {"entity": "CVN-79"}),
    ("analyst_open_questions", {"piid": PIID}),
    ("analyst_investigate_transaction", {"piid": PIID, "transaction_key": "k1"}),
    ("analyst_investigate_window", {"piid": PIID, "fiscal_year": 2019, "first_period": 1, "last_period": 3}),
    ("analyst_explain_residual", {"piid": PIID, "submission_period": "FY2019Q1"}),  # ties to the cent
    ("analyst_explain_residual", {"piid": PIID, "submission_period": "FY2019Q2"}),  # does not
    ("analyst_backtest", {"piid": PIID}),
    ("analyst_model_status", {}),
]


def _tools():
    async def go():
        async with Client(mcp) as client:
            return await client.list_tools()

    return asyncio.run(go())


def test_every_tool_lists_named_output_fields():
    tools = _tools()
    assert len(tools) == 12
    for tool in tools:
        fields = (tool.outputSchema or {}).get("properties", {})
        assert len(fields) >= 4, f"{tool.name} does not say what it returns"


def test_the_calls_cover_every_tool():
    called = {name for name, _ in CALLS} | {"analyst_record_outcome"}
    assert called == {tool.name for tool in _tools()}


@pytest.mark.parametrize("name,arguments", CALLS, ids=[f"{n}-{i}" for i, (n, _) in enumerate(CALLS)])
def test_a_real_answer_fits_the_schema(sources, name, arguments):
    _fits(_call(name, arguments))


def test_a_recorded_outcome_fits_the_schema(sources):
    lead = _fits(_call("analyst_investigate_transaction", {"piid": PIID, "transaction_key": "k3"}))
    outcome = _fits(_call("analyst_record_outcome", {
        "lead_id": lead["lead_id"], "truth": SERVER.SCN18, "evidence_type": "section_g_accounting_data",
        "evidence_locator": "P00003 p.12 line 3", "confirming_office": "SUPSHIP Newport News"}))
    assert outcome["truth"] == SERVER.SCN18
