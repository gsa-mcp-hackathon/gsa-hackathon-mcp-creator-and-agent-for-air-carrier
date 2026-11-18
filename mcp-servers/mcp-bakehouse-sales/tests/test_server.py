"""Smoke tests: the server imports and every submodule registers.

These run with no credentials and no network, which is what makes them
useful in CI.
"""

from __future__ import annotations

from fastmcp import FastMCP

from mcp_bakehouse_sales.app import mcp
from mcp_bakehouse_sales.config import settings

EXPECTED_TOOLS = {
    "mcp_sales_trend",
    "mcp_sales_totals",
    "mcp_top_product_by_transactionid",
    "mcp_describe_sales",
}


def test_server_is_importable():
    assert mcp is not None


def test_server_has_name():
    assert mcp.name == "Mcp Bakehouse Sales"


def test_default_transport_is_stdio():
    """Guard against shipping with a non-stdio default."""
    assert settings.mcp_transport == "stdio"


def test_tools_register_without_error():
    from mcp_bakehouse_sales.tools import register_tools

    register_tools(FastMCP("test"))


def test_prompts_register_without_error():
    from mcp_bakehouse_sales.prompts import register_prompts

    register_prompts(FastMCP("test"))


def test_resources_register_without_error():
    from mcp_bakehouse_sales.resources import register_resources

    register_resources(FastMCP("test"))


def test_routes_register_without_error():
    from mcp_bakehouse_sales.routes import register_routes

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


async def test_every_tool_documents_itself():
    """A tool with no description cannot be chosen correctly by a model."""
    tools = await mcp.list_tools()
    undocumented = [tool.name for tool in tools if not (tool.description or "").strip()]
    assert not undocumented, f"tools with no description: {undocumented}"
