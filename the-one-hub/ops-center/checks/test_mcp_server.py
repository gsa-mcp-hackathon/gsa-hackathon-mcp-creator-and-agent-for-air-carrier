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


def test_server_registers_every_tool():
    srv = mcp_server.build()
    names = {t.name for t in asyncio.run(srv.list_tools())}
    assert {"get_table", "list_tables", "check_claim", "search_corpus"} <= names


def test_tie_out_closes_only_to_the_exhibit_rounding():
    # 2026-11-20 (B2): a $970,000 residual on $13,409.970M used to pass under the $1.0M floor.
    from ops.agents.tieout.run import anchor_chain, two_axis_close
    assert not two_axis_close(13409.97, {"a": 13409.0}, {"b": 13409.97}).passed
    assert two_axis_close(1.0, {"a": 0.1, "b": 0.2, "c": 0.7}, {"x": 1.0}).passed   # no float drift
    assert two_axis_close(13409.970, {"a": 13409.9704}, {"b": 13409.970}).passed    # rounding only
    assert anchor_chain([("cap", 11398.0), ("a", 1300.0), ("b", 238.0), ("c", 260.0), ("d", 213.97)],
                        13409.970).passed
    assert not anchor_chain([("cap", 11398.0), ("a", 1300.0)], 12698.5).passed
