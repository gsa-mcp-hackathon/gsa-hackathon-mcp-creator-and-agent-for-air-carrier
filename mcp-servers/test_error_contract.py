"""A failure is reported as an error, by every server, with its reason intact.

Round 10 (A3), 2026-11-21: the Creator and the generated servers answered a
failure ({"error": ..., "hint": ...}) as an ordinary result, so a client, a
grader or the probe counted it as a success, while the docs, analyst and hub
servers raised ToolError. error_contract.py, copied byte for byte into every
FastMCP server the Creator builds, now marks such a result isError and keeps
the body. The hub, built on the plain MCP SDK, raises ToolError (_ok in
the-one-hub/ops-center/mcp/mcp_server.py).

Run: python -m pytest -q test_error_contract.py   (needs fastmcp>=3.4,<4)
"""

from __future__ import annotations

import asyncio
import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
CANON = REPO / "mcp-server-creator/src/mcp_server_creator/error_contract.py"
COPIES = [
    ROOT / "mcp-aircarrier-ops/src/mcp_aircarrier_ops/error_contract.py",
    ROOT / "mcp-bakehouse-sales/src/bakehouse_sales/error_contract.py",
]
APPS = [
    REPO / "mcp-server-creator/src/mcp_server_creator/app.py",
    ROOT / "mcp-aircarrier-ops/src/mcp_aircarrier_ops/app.py",
    ROOT / "mcp-bakehouse-sales/src/bakehouse_sales/app.py",
]


@pytest.mark.parametrize("copy", COPIES, ids=lambda p: p.parts[-3])
def test_every_copy_matches_the_creator(copy):
    assert copy.read_bytes() == CANON.read_bytes()


@pytest.mark.parametrize("app", APPS, ids=lambda p: p.parts[-3])
def test_every_fastmcp_server_installs_it(app):
    text = app.read_text()
    assert "mcp.add_middleware(" in text and "ErrorContractMiddleware())" in text
    # 2026-11-23: an unexpected exception's text must not reach a client either.
    assert "mask_error_details=True" in text


def test_the_generator_ships_and_installs_it():
    text = (REPO / "mcp-server-creator/src/mcp_server_creator/generators/project.py").read_text()
    assert '"error_contract.py": ERROR_CONTRACT_MODULE' in text
    assert "mcp.add_middleware(error_contract.ErrorContractMiddleware())" in text
    assert 'name="{{title}}",' in text and "mask_error_details=True" in text


def test_only_a_top_level_error_counts():
    sys.path.insert(0, str(CANON.parent.parent))
    ec = importlib.import_module("mcp_server_creator.error_contract")
    assert ec.is_error_body({"error": "No record matched 'X'.", "hint": "h"})
    assert ec.is_error_body({"status": "failed", "error": "boom"})
    assert not ec.is_error_body({"error": "", "rows": []})
    assert not ec.is_error_body({"checks": [{"error": "nested"}]})
    assert not ec.is_error_body(None)


def _creator():
    src = REPO / "mcp-server-creator/src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    return importlib.import_module("mcp_server_creator.app").mcp


def test_a_creator_failure_reaches_the_client_as_an_error_with_its_hint():
    from fastmcp import Client

    async def go():
        async with Client(_creator()) as c:
            return await c.call_tool(
                "creator_design_tools", {"design_id": "dsn_00000000"}, raise_on_error=False
            )

    res = asyncio.run(go())
    assert res.is_error
    assert "no design named" in res.structured_content["error"]
    assert res.structured_content.get("hint")


def test_a_creator_success_is_not_an_error():
    from fastmcp import Client

    async def go():
        async with Client(_creator()) as c:
            return await c.call_tool("creator_list_library", {}, raise_on_error=False)

    assert not asyncio.run(go()).is_error
