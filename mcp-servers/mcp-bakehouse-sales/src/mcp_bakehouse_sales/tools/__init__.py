"""Tools submodule: one tool per file.

Each module exposes `register(mcp)`. This file aggregates them into
`register_tools(mcp)`, which app.py calls once at startup.
"""

from __future__ import annotations

from mcp_bakehouse_sales.tools import (
    mcp_describe_sales,
    mcp_sales_totals,
    mcp_sales_trend,
    mcp_top_product_by_transactionid,
)


def register_tools(mcp) -> None:
    """Register all tools with the MCP server."""
    mcp_describe_sales.register(mcp)
    mcp_top_product_by_transactionid.register(mcp)
    mcp_sales_totals.register(mcp)
    mcp_sales_trend.register(mcp)


__all__ = ["register_tools"]
