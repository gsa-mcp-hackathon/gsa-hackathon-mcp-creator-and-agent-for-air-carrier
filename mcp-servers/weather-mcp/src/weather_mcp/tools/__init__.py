"""Tools submodule: one tool per file.

Each module exposes `register(mcp)`. This file aggregates them into
`register_tools(mcp)`, which app.py calls once at startup.
"""

from __future__ import annotations

from weather_mcp.tools import (
    weather_describe_nws,
)


def register_tools(mcp) -> None:
    """Register all tools with the MCP server."""
    weather_describe_nws.register(mcp)


__all__ = ["register_tools"]
