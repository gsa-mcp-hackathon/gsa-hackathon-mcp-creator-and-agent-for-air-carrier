"""Every tool lists a typed output schema, and a real answer fits it.

FastMCP checks each result against the tool's output schema before it leaves
the server, so a model in output_models.py that is stricter than the code
turns a working tool into an error. This calls every tool through the MCP
client with a fake warehouse that returns the value types Databricks SQL
does (Decimal, date, datetime), and fails if any answer is refused. A
failure body must still reach the client as the tool's own error, not as a
schema error. Run: uv run pytest contract
"""

from __future__ import annotations

import importlib
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from fastmcp import Client

from mcp_aircarrier_ops.app import mcp

TOOL_MODULES = [
    "mcp_get_exhibit_cells",
    "mcp_search_exhibit_cells",
    "mcp_search_graph_edges",
    "mcp_search_obligations",
    "mcp_search_variances",
    "mcp_search_work_register",
    "mcp_work_register_totals",
]
ROW = {
    "table_id": "bb2e90fd1d91a0bc:0095:00",
    "page": 95,
    "row_idx": 0,
    "col_idx": 1,
    "value": Decimal("13409.970"),
    "action_date": date(2020, 3, 10),
    "federal_action_obligation": Decimal("454765071.00"),
    "kind": "gap",
    "state": "open_question",
    "owner_agent": "investigator",
    "records": 3,
    "with_exposure": 1,
    "exposure_usd_m": Decimal("12.5"),
    "last_updated": datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc),
    "text": "CVN 79 detail design and construction",
}
TOTALS = {
    "total": 2,
    "obligation_total": Decimal("454765071.00"),
    "data_as_of": date(2026, 11, 20),
}
CALLS = [
    ("carrier_get_exhibit_cells", {"table_id": ROW["table_id"]}),
    ("carrier_search_exhibit_cells", {"query": "ship estimate"}),
    ("carrier_search_graph_edges", {"query": "CVN-79"}),
    ("carrier_search_obligations", {"contract": "N00024-15-C-2114"}),
    ("carrier_search_obligations", {"contract": "N00024-15-C-2114", "detail": "full"}),
    ("carrier_search_variances", {"query": "cost"}),
    ("carrier_search_work_register", {"query": "CVN"}),
    ("carrier_work_register_counts", {}),
]


def _fake_warehouse(rows: list[dict]):
    def run_query(sql, params=None):
        return [dict(TOTALS)] if "COUNT(*)" in sql else [dict(r) for r in rows]

    return run_query


def _patch(monkeypatch, rows: list[dict]) -> None:
    for name in TOOL_MODULES:
        module = importlib.import_module(f"mcp_aircarrier_ops.tools.{name}")
        monkeypatch.setattr(module, "run_query", _fake_warehouse(rows))


async def _tools():
    async with Client(mcp) as client:
        return await client.list_tools()


async def _call(name: str, arguments: dict):
    async with Client(mcp) as client:
        return await client.call_tool(name, arguments, raise_on_error=False)


async def test_every_tool_lists_named_output_fields():
    tools = await _tools()
    assert len(tools) == len(TOOL_MODULES)
    for tool in tools:
        fields = (tool.outputSchema or {}).get("properties", {})
        assert len(fields) >= 4, f"{tool.name} does not say what it returns"


async def test_the_calls_cover_every_tool():
    assert {name for name, _ in CALLS} == {tool.name for tool in await _tools()}


@pytest.mark.parametrize(
    "name,arguments", CALLS, ids=[f"{n}-{i}" for i, (n, _) in enumerate(CALLS)]
)
async def test_a_real_answer_fits_the_schema(monkeypatch, name, arguments):
    _patch(monkeypatch, [ROW, ROW])
    result = await _call(name, arguments)
    assert not result.is_error, result.content[0].text
    assert result.structured_content


async def test_a_failure_body_keeps_its_own_message(monkeypatch):
    _patch(monkeypatch, [])
    monkeypatch.setitem(TOTALS, "total", 0)
    result = await _call("carrier_get_exhibit_cells", {"table_id": "missing"})
    assert result.is_error
    assert "No record matched" in result.structured_content["error"]
    assert result.structured_content["hint"]
