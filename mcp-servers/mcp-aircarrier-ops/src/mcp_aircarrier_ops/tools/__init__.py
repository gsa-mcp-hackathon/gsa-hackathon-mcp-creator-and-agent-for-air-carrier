"""Tools submodule: one tool per file.

Each module exposes `register(mcp)`. This file aggregates them into
`register_tools(mcp)`, which app.py calls once at startup.
"""

from __future__ import annotations

from mcp_aircarrier_ops.tools import (
    mcp_get_exhibit_cells,
    mcp_search_exhibit_cells,
    mcp_search_graph_edges,
    mcp_search_obligations_2116,
    mcp_search_work_register,
    mcp_work_register_totals,
)


def register_tools(mcp) -> None:
    """Register all tools with the MCP server."""
    mcp_get_exhibit_cells.register(mcp)
    mcp_search_exhibit_cells.register(mcp)
    mcp_search_obligations_2116.register(mcp)
    mcp_search_graph_edges.register(mcp)
    mcp_search_work_register.register(mcp)
    mcp_work_register_totals.register(mcp)


__all__ = ["register_tools"]
