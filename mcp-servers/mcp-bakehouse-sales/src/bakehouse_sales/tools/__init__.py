"""Tools submodule: one tool per file.

Each module exposes `register(mcp)`. This file aggregates them into
`register_tools(mcp)`, which app.py calls once at startup.
"""

from __future__ import annotations

from bakehouse_sales.tools import (
    bakehouse_average_totalprice,
    bakehouse_daily_totalprice,
    bakehouse_describe_sales,
    bakehouse_get_sales,
    bakehouse_top_franchiseid_by_totalprice,
    bakehouse_top_paymentmethod_by_totalprice,
    bakehouse_top_product_by_quantity,
)


def register_tools(mcp) -> None:
    """Register all tools with the MCP server."""
    bakehouse_describe_sales.register(mcp)
    bakehouse_get_sales.register(mcp)
    bakehouse_top_franchiseid_by_totalprice.register(mcp)
    bakehouse_top_product_by_quantity.register(mcp)
    bakehouse_top_paymentmethod_by_totalprice.register(mcp)
    bakehouse_daily_totalprice.register(mcp)
    bakehouse_average_totalprice.register(mcp)


__all__ = ["register_tools"]
