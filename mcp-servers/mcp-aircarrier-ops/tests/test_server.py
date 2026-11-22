"""Smoke tests: the server imports and every submodule registers.

These run with no credentials and no network, which is what makes them
useful in CI.
"""

from __future__ import annotations

from fastmcp import FastMCP

from mcp_aircarrier_ops.app import mcp
from mcp_aircarrier_ops.config import settings

EXPECTED_TOOLS = {
    "carrier_search_exhibit_cells",
    "carrier_search_graph_edges",
    "carrier_work_register_counts",
    "carrier_search_work_register",
    "carrier_get_exhibit_cells",
    "carrier_search_obligations",
    "carrier_search_variances",
}


def test_server_is_importable():
    assert mcp is not None


def test_server_has_name():
    assert mcp.name == "Air Carrier Ops"


def test_instructions_name_only_things_that_exist():
    """The old instructions sent agents to a 'describe tool' that never existed."""
    text = (mcp.instructions or "") + " "
    assert "describe tool" not in text
    assert "mcp://dictionary/sources" in text


async def test_instruction_tool_names_are_real():
    import re

    names = {t.name for t in await mcp.list_tools()}
    mentioned = set(re.findall(r"carrier_[a-z0-9_]+", mcp.instructions or ""))
    assert mentioned and mentioned <= names, (
        f"unknown tools in instructions: {mentioned - names}"
    )


def test_default_transport_is_stdio():
    """Guard against shipping with a non-stdio default."""
    assert settings.mcp_transport == "stdio"


def test_tools_register_without_error():
    from mcp_aircarrier_ops.tools import register_tools

    register_tools(FastMCP("test"))


def test_prompts_register_without_error():
    from mcp_aircarrier_ops.prompts import register_prompts

    register_prompts(FastMCP("test"))


def test_resources_register_without_error():
    from mcp_aircarrier_ops.resources import register_resources

    register_resources(FastMCP("test"))


def test_routes_register_without_error():
    from mcp_aircarrier_ops.routes import register_routes

    register_routes(FastMCP("test"))


async def test_every_planned_tool_is_discoverable():
    """The tools the specification planned are the tools the server exposes."""
    tools = await mcp.list_tools()
    names = {tool.name for tool in tools}
    missing = EXPECTED_TOOLS - names
    assert not missing, f"tools missing from the server: {sorted(missing)}"


async def test_tool_names_are_unique():
    tools = await mcp.list_tools()
    names = [tool.name for tool in tools]
    assert len(names) == len(set(names))


async def test_no_tool_uses_the_generic_mcp_prefix():
    """'mcp_' says nothing about the domain; agents pick tools by name."""
    tools = await mcp.list_tools()
    generic = [t.name for t in tools if t.name.startswith("mcp_")]
    assert not generic, f"rename these: {generic}"


async def _tool(server, name: str):
    """One tool by name, on FastMCP 2 (shimmed in conftest) and 3 alike."""
    return next(t for t in await server.list_tools() if t.name == name)


async def _schema(name: str) -> dict:
    return (await _tool(mcp, name)).parameters


async def test_work_register_filters_cover_every_kind_and_state():
    """Claims are 12,061 of 12,173 work items.

    A kind enum without them hides most rows.
    """
    for name in ("carrier_search_work_register", "carrier_work_register_counts"):
        schema = await _schema(name)
        text = str(schema)
        for value in (
            "claim",
            "gap",
            "variance",
            "artifact",
            "collect",
            "human_review",
            "open_question",
            "collection_required",
        ):
            assert value in text, f"{name} cannot filter on {value}"


async def test_counts_tool_does_not_report_an_exposure_sum_by_default():
    from mcp_aircarrier_ops.tools import mcp_work_register_totals as counts

    rows = [
        {
            "kind": "claim",
            "state": "human_review",
            "owner_agent": None,
            "records": 5,
            "with_exposure": 0,
            "exposure_usd_m": 0.0,
            "last_updated": "2026-11-10 00:34:35",
        }
    ]
    original = counts.run_query
    counts.run_query = lambda sql, params: rows
    try:
        server = FastMCP("t")
        counts.register(server)
        tool = await _tool(server, "carrier_work_register_counts")
        out = (await tool.run({})).structured_content
    finally:
        counts.run_query = original
    assert out["totals"]["record_count"] == 5
    assert "exposure" not in out and "exposure_note" in out
    assert "freshness_note" in out  # 2026-11-10 is well past two days old


def test_counts_freshness_note_names_the_snapshot_date():
    """Evaluation finding F5: the counts came back seven days old with no warning."""
    from datetime import datetime

    from mcp_aircarrier_ops.tools.mcp_work_register_totals import freshness_note

    now = datetime(2026, 11, 19, 12, 0)
    note = freshness_note("2026-11-12 15:15:00", now=now)
    assert note and "2026-11-12" in note and "6 days ago" in note
    assert freshness_note("2026-11-18 15:15:00", now=now) is None
    assert freshness_note("not a date", now=now) is None


async def test_obligation_search_defaults_to_summary_fields():
    from mcp_aircarrier_ops.tools import mcp_search_obligations as ob

    seen: list[str] = []

    def fake(sql, params):
        seen.append(sql)
        return (
            [{"total": 1}]
            if "COUNT(*)" in sql
            else [{"award_id_piid": "N0002409C2116"}]
        )

    original = ob.run_query
    ob.run_query = fake
    try:
        server = FastMCP("t")
        ob.register(server)
        tool = await _tool(server, "carrier_search_obligations")
        out = (
            await tool.run({"contract": "N00024-09-C-2116", "query": "cvn"})
        ).structured_content
        full = (
            await tool.run(
                {"contract": "N00024-09-C-2116", "query": "cvn", "detail": "full"}
            )
        ).structured_content
    finally:
        ob.run_query = original
    # Compare only the SELECT list; the WHERE clause searches the same text
    # columns either way.
    summary_sql, full_sql = (s.split(" FROM ", 1)[0] for s in (seen[1], seen[3]))
    assert out["detail"] == "summary" and full["detail"] == "full"
    assert "highly_compensated_officer_1_name" not in summary_sql
    assert "highly_compensated_officer_1_name" in full_sql
    assert summary_sql.count(",") == len(ob.SUMMARY_FIELDS) - 1


async def test_obligation_search_finds_the_base_award_by_filter():
    """An agent asked for 'modification 0' must not guess a keyword (eval Q4)."""
    from mcp_aircarrier_ops.tools import mcp_search_obligations as ob

    seen: list[tuple[str, list]] = []

    def fake(sql, params):
        seen.append((sql, list(params)))
        return [{"total": 1}] if "COUNT(*)" in sql else [{"modification_number": "0"}]

    original = ob.run_query
    ob.run_query = fake
    try:
        server = FastMCP("t")
        ob.register(server)
        tool = await _tool(server, "carrier_search_obligations")
        await tool.run(
            {
                "contract": "N00024-09-C-2116",
                "modification_number": "0",
                "fiscal_year": 2009,
            }
        )
    finally:
        ob.run_query = original
    sql, params = seen[1]
    assert "LIKE" not in sql, "an empty query must not add a text search"
    assert "ORDER BY" in sql
    assert params[:2] == ["0", 2009]


async def test_obligation_search_returns_the_server_side_sum():
    """Fresh eval F1: models counted 28 FY2010 actions right but mis-added them."""
    from mcp_aircarrier_ops.tools import mcp_search_obligations as ob

    seen: list[str] = []

    def fake(sql, params):
        seen.append(sql)
        if "COUNT(*)" in sql:
            return [{"total": 28, "obligation_total": "211984118.00"}]
        return [{"modification_number": "P00001"}]

    original = ob.run_query
    ob.run_query = fake
    try:
        server = FastMCP("t")
        ob.register(server)
        tool = await _tool(server, "carrier_search_obligations")
        out = (
            await tool.run(
                {"contract": "N00024-09-C-2116", "fiscal_year": 2010, "limit": 5}
            )
        ).structured_content
    finally:
        ob.run_query = original
    assert "SUM(CAST(" in seen[0] and "DECIMAL(20,2)" in seen[0]
    assert out["total"] == 28 and out["obligation_total"] == "211984118.00"
    assert out["count"] == 1 and out["has_more"] is True


async def test_obligation_as_of_comes_from_the_data_not_a_constant():
    """Eval F4: as_of said 2026-06-10 while the latest action was 2026-07-20."""
    from mcp_aircarrier_ops.tools import mcp_search_obligations as ob

    seen: list[str] = []

    def fake(sql, params):
        seen.append(sql)
        if "COUNT(*)" in sql:
            return [
                {"total": 1, "obligation_total": "1.00", "data_as_of": "2026-07-20"}
            ]
        return [{"modification_number": "0"}]

    async def run(fake_fn):
        original = ob.run_query
        ob.run_query = fake_fn
        try:
            server = FastMCP("t")
            ob.register(server)
            tool = await _tool(server, "carrier_search_obligations")
            return (
                await tool.run(
                    {"contract": "N00024-09-C-2116", "fiscal_year": 2010, "limit": 1}
                )
            ).structured_content
        finally:
            ob.run_query = original

    out = await run(fake)
    assert out["as_of"] == "2026-07-20"
    # MAX runs over the whole table (subquery), not only the filtered rows.
    assert "(SELECT CAST(MAX(" in seen[0] and "AS data_as_of" in seen[0]

    # A warehouse that returns no date falls back to the registered constant.
    out = await run(lambda sql, params: [{"total": 0}] if "COUNT(*)" in sql else [])
    assert out["as_of"] == ob.AS_OF


async def test_get_exhibit_cells_returns_the_whole_table_in_order():
    """A table id holds 2 to ~1,600 cells; LIMIT 1 used to return one arbitrary cell."""
    from mcp_aircarrier_ops.tools import mcp_get_exhibit_cells as gx

    seen: list[tuple[str, list]] = []

    def fake(sql, params):
        seen.append((sql, list(params)))
        if "COUNT(*)" in sql:
            return [{"total": 3}]
        return [{"row_idx": 0, "col_idx": 0}, {"row_idx": 0, "col_idx": 1}]

    original = gx.run_query
    gx.run_query = fake
    try:
        server = FastMCP("t")
        gx.register(server)
        tool = await _tool(server, "carrier_get_exhibit_cells")
        out = (await tool.run({"table_id": "t1", "limit": 2})).structured_content
    finally:
        gx.run_query = original
    sql, params = seen[1]
    assert "ORDER BY" in sql and "LIMIT 1" not in sql and params == ["t1", 2, 0]
    assert out["total"] == 3 and out["count"] == 2 and out["next_offset"] == 2
    assert "describe tool" not in str(out)


def test_store_schema_parses_and_rejects_bad_values():
    import pytest

    from mcp_aircarrier_ops.data.sources import store_location

    assert store_location("main.carrier_v2") == ("main", "carrier_v2")
    assert store_location("  ") == ("main", "aircarrier")
    for bad in ("main", "a.b.c", "main.x; DROP TABLE t", "main.`x`", "1a.b"):
        with pytest.raises(ValueError, match="AIRCARRIER_STORE_SCHEMA"):
            store_location(bad)


def test_store_schema_env_moves_every_table():
    """A fresh interpreter with the variable set must point every tool elsewhere."""
    import os
    import pathlib
    import subprocess
    import sys

    src = pathlib.Path(__file__).resolve().parents[1] / "src"
    code = (
        "from mcp_aircarrier_ops.tools import mcp_get_exhibit_cells as a, "
        "mcp_search_exhibit_cells as b, mcp_search_obligations as c, "
        "mcp_search_graph_edges as d, mcp_search_work_register as e, "
        "mcp_work_register_totals as f, mcp_search_variances as g\n"
        "from mcp_aircarrier_ops.routes import LANDING\n"
        "print('|'.join([m.TABLE for m in (a, b, c, d, e, f, g)] + [c.TABLE_2114]))\n"
        "print('|'.join(LANDING['data']))\n"
    )
    env = dict(
        os.environ, AIRCARRIER_STORE_SCHEMA="other_cat.other_sch", PYTHONPATH=str(src)
    )
    out = subprocess.run(
        [sys.executable, "-c", code],
        env=env,
        cwd=src,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    tables, landing = out.strip().splitlines()
    assert all(t.startswith("`other_cat`.`other_sch`.") for t in tables.split("|"))
    assert all(t.startswith("other_cat.other_sch.") for t in landing.split("|"))
    assert "aircarrier_" not in out or "main.aircarrier" not in out


def test_open_state_means_not_closed_or_promoted():
    """Eval Q6: 'how many open gaps' was answered with open_question only.

    That gave 21, not 58.
    """
    from mcp_aircarrier_ops.models import StateValue, state_clause

    assert state_clause("`state`", StateValue.OPEN) == (
        "`state` NOT IN (?, ?)",
        ["closed", "promoted"],
    )
    assert state_clause("`state`", StateValue.ANY) == ("", [])
    assert state_clause("`state`", StateValue.HUMAN_REVIEW) == (
        "`state` = ?",
        ["human_review"],
    )


def test_exhibit_search_clips_long_cells():
    from mcp_aircarrier_ops.tools.mcp_search_exhibit_cells import MAX_VALUE_CHARS, _clip

    row = _clip({"value": "x" * (MAX_VALUE_CHARS + 50)})
    assert len(row["value"]) == MAX_VALUE_CHARS and row["value_truncated"]
    assert row["value_chars"] == MAX_VALUE_CHARS + 50
    assert _clip({"value": "short"}) == {"value": "short"}
    long_header = _clip({"value": "1", "row_header": "h" * 5084})
    assert long_header["value"] == "1" and long_header["row_header_chars"] == 5084
    assert len(long_header["row_header"]) == MAX_VALUE_CHARS


async def test_every_tool_documents_itself():
    """A tool with no description cannot be chosen correctly by a model."""
    tools = await mcp.list_tools()
    undocumented = [tool.name for tool in tools if not (tool.description or "").strip()]
    assert not undocumented, f"tools with no description: {undocumented}"


async def _obligations(arguments: dict) -> tuple[dict, list[tuple[str, list]]]:
    from mcp_aircarrier_ops.tools import mcp_search_obligations as ob

    seen: list[tuple[str, list]] = []

    def fake(sql, params):
        seen.append((sql, list(params)))
        if "COUNT(*)" in sql:
            return [
                {"total": 1, "obligation_total": "1.00", "data_as_of": "2026-07-20"}
            ]
        return [{"modification_number": "P00116"}]

    original = ob.run_query
    ob.run_query = fake
    try:
        server = FastMCP("t")
        ob.register(server)
        tool = await _tool(server, "carrier_search_obligations")
        out = (await tool.run(arguments)).structured_content
    finally:
        ob.run_query = original
    return out, seen


async def test_obligations_reach_the_dd_and_c_contract():
    """Round 2 H02, H04, H09: three questions on N00024-15-C-2114 had no tool."""
    out, seen = await _obligations(
        {"contract": "N00024-15-C-2114", "fiscal_year": 2018}
    )
    assert out["contract"] == "N00024-15-C-2114"
    assert all("aircarrier_src_2114_contract_transactions" in sql for sql, _ in seen)
    assert not any("aircarrier_src_2116" in sql for sql, _ in seen)


async def test_largest_first_puts_the_largest_action_on_top():
    """Round 2 H03: models paged through actions by date and named the wrong one."""
    out, seen = await _obligations(
        {"contract": "N00024-09-C-2116", "order": "largest_first", "limit": 1}
    )
    rows_sql = seen[1][0]
    assert "ORDER BY CAST(" in rows_sql and "DECIMAL(20,2)) DESC" in rows_sql
    assert out["order"] == "largest_first"
    _, by_date = await _obligations({"contract": "N00024-09-C-2116"})
    assert "DESC" not in by_date[1][0]


async def test_the_contract_is_required_and_closed():
    from mcp_aircarrier_ops.app import mcp as app

    tool = await _tool(app, "carrier_search_obligations")
    schema = tool.parameters
    assert "contract" in schema.get("required", [])
    text = str(schema)
    assert "N00024-09-C-2116" in text and "N00024-15-C-2114" in text


async def test_variances_are_searchable_by_text():
    """Round 2 H08: the FPDS-NG figure lived only in variance E-16."""
    from mcp_aircarrier_ops.tools import mcp_search_variances as va

    seen: list[tuple[str, list]] = []

    def fake(sql, params):
        seen.append((sql, list(params)))
        if "COUNT(*)" in sql:
            return [{"total": 1}]
        return [
            {"id": "E-16", "title": "FPDS-NG and USAspending differ by $583,963.00"}
        ]

    original = va.run_query
    va.run_query = fake
    try:
        server = FastMCP("t")
        va.register(server)
        tool = await _tool(server, "carrier_search_variances")
        out = (
            await tool.run({"query": "FPDS", "status": "resolved"})
        ).structured_content
    finally:
        va.run_query = original
    sql, params = seen[1]
    assert "aircarrier_variances" in sql and "LIKE ?" in sql
    assert params[0] == "resolved" and "%fpds%" in params
    assert out["items"][0]["id"] == "E-16" and out["total"] == 1
