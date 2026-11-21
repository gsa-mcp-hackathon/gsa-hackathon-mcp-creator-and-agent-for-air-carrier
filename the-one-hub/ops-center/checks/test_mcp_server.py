"""The ops-center MCP server (mcp/mcp_server.py): every tool answers on the
shipped data, and no tool argument can read outside app/data.

    PYTHONPATH=. python -m pytest checks/test_mcp_server.py
"""
from __future__ import annotations

import asyncio
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mcp"))

import mcp_server


@pytest.fixture
def outside_json(tmp_path):
    secret = tmp_path / "leak.json"
    secret.write_text(json.dumps({"secret": "outside the data folder"}))
    return secret


def test_get_table_cannot_read_outside_the_data_folder(outside_json):
    rel = pathlib.Path(
        *([".."] * len(mcp_server.DATA.resolve().parts)), *outside_json.parts[1:]
    )
    name = str(rel.with_suffix(""))
    result = mcp_server.get_table(name)
    assert "secret" not in json.dumps(result)
    assert result["error"].startswith("no table")


@pytest.mark.parametrize("name", ["../seed/gate", "/etc/passwd", "kb/../../mcp/x"])
def test_get_table_refuses_traversal_names(name):
    assert "error" in mcp_server.get_table(name)


def test_every_listed_table_loads():
    tables = mcp_server.list_tables()["tables"]
    assert tables, "app/data ships no tables"
    for name in tables:
        assert "error" not in mcp_server.get_table(name), name


def test_read_tools_answer_on_the_shipped_data():
    gaps = mcp_server.rank_gaps(limit=3)
    assert isinstance(gaps, dict)
    first = next(iter(mcp_server._json("gaps").get("rows", [])), {})
    gap_id = first.get("id") or first.get("gap_id") or "G1"
    for result in (
        mcp_server.search_mechanisms("contract", limit=3),
        mcp_server.get_keyset(),
        mcp_server.exhibit_hazards(),
        mcp_server.get_gap(gap_id),
        mcp_server.plan_gap(gap_id),
        mcp_server.next_work(limit=3),
        mcp_server.corpus_status(),
        mcp_server.challenge_text("CVN-79 cost is 13,409.970 million."),
    ):
        assert isinstance(result, dict)
        json.dumps(result, default=str)  # every answer is JSON-serialisable


# ------------------------------------------------------------ MCP surface
RISKY = ("$ref", "$defs", "anyOf", "allOf", "oneOf")


@pytest.fixture(scope="module")
def srv():
    return mcp_server.build()


@pytest.fixture(scope="module")
def tools(srv):
    return {t.name: t for t in asyncio.run(srv.list_tools())}


def _call(srv, tool, **args):
    """(ok, answer): the tool's JSON answer, or ok=False with the refusal text
    when a ToolError or a validation error stops it."""
    try:
        result = asyncio.run(srv.call_tool(tool, args))
    except Exception as exc:  # the server's refusal is what is tested
        return False, str(exc)
    content = result[0] if isinstance(result, tuple) else result
    return True, json.loads(content[0].text)


def test_server_is_named_apart_from_the_ops_server(srv, tools):
    # 2026-11-21 (B3): it was "aircarrier-ops", the same name as mcp-aircarrier-ops,
    # with generic tool names that collide in a multi-server client.
    assert srv.name == "mcp-aircarrier-hub"
    assert len(tools) == len(mcp_server.TOOLS) == 16
    assert all(n.startswith("hub_") for n in tools), sorted(tools)


def test_every_tool_is_read_only_and_described(tools):
    for name, t in tools.items():
        a = t.annotations
        assert a and a.readOnlyHint and not a.destructiveHint and a.idempotentHint, name
        assert t.description and len(t.description) > 40, name


def test_schemas_stay_portable_across_models(tools):
    # The Creator's rule: no $ref, no nullable unions, no object parameters, a
    # small listing. Gemini through an AI gateway drops what it cannot read.
    total = 0
    for name, t in tools.items():
        text = json.dumps(t.inputSchema, separators=(",", ":"))
        total += len(text)
        assert not [k for k in RISKY if k in text], name
        for pname, prop in t.inputSchema.get("properties", {}).items():
            assert prop.get("type") in ("string", "integer", "number", "boolean", "array"), (name, pname)
            if prop.get("type") == "array":
                assert prop["items"].get("type") == "string", (name, pname)
    assert total < 14_000, total


@pytest.mark.parametrize("name,args", [
    ("hub_get_table", {"name": "../seed/gate"}),
    ("hub_get_table", {"name": "/etc/passwd"}),
    ("hub_get_table", {"name": "no_such_table"}),
    ("hub_get_gap", {"gap_id": "G999"}),
    ("hub_get_gap", {"gap_id": "X1; drop"}),
    ("hub_get_keyset", {"section": "bogus"}),
    ("hub_check_claim", {"hull": "CVN-79", "layer": "budget", "element": "x", "period": "p",
                         "value_musd": "13,529"}),
    ("hub_tie_out", {"total": "1", "axis_a_labels": ["a", "b"], "axis_a_amounts": ["1"],
                     "axis_b_labels": ["x"], "axis_b_amounts": ["1"]}),
    ("hub_tie_out", {"total": "1", "axis_a_labels": ["a", "a"], "axis_a_amounts": ["0.5", "0.5"],
                     "axis_b_labels": ["x"], "axis_b_amounts": ["1"]}),
    ("hub_collection_requirement", {"lead": "get the notification"}),
    ("hub_rank_gaps", {"limit": 0}),
])
def test_bad_arguments_are_refused_with_a_reason(srv, name, args):
    ok, why = _call(srv, name, **args)
    assert not ok and why, (name, args)


def test_tie_out_tool_closes_exactly_and_refuses_a_970k_gap(srv):
    a = {"axis_a_labels": ["Plan Costs", "Basic Construction", "Other"],
         "axis_a_amounts": ["0.1", "0.2", "13409.670"],
         "axis_b_labels": ["SCN"], "axis_b_amounts": ["13409.970"]}
    ok, out = _call(srv, "hub_tie_out", total="13409.970", **a)
    assert ok and out["passed"] is True, out
    ok, out = _call(srv, "hub_tie_out", total="13409.970", **(a | {"axis_b_amounts": ["13409.000"]}))
    assert ok and out["passed"] is False, out


def test_check_claim_tool_routes_the_held_baseline_and_never_promotes(srv):
    # E-17: the $13,529M baseline printed in the FY2027 MSAR is held for review.
    ok, out = _call(srv, "hub_check_claim", hull="CVN-79", layer="budget",
                    element="Total Ship Estimate", period="FY2027 PB", value_musd="13529",
                    tag="VERIFIED", confidence=0.9)
    assert ok and out["decision"] != "promote" and out["reason"], out


def test_tie_out_closes_only_to_the_exhibit_rounding():
    # 2026-11-20 (B2): a $970,000 residual on $13,409.970M used to pass under the $1.0M floor.
    from ops.agents.tieout.run import anchor_chain, two_axis_close
    assert not two_axis_close(13409.97, {"a": 13409.0}, {"b": 13409.97}).passed
    assert two_axis_close(1.0, {"a": 0.1, "b": 0.2, "c": 0.7}, {"x": 1.0}).passed   # no float drift
    assert two_axis_close(13409.970, {"a": 13409.9704}, {"b": 13409.970}).passed    # rounding only
    assert anchor_chain([("cap", 11398.0), ("a", 1300.0), ("b", 238.0), ("c", 260.0), ("d", 213.97)],
                        13409.970).passed
    assert not anchor_chain([("cap", 11398.0), ("a", 1300.0)], 12698.5).passed
