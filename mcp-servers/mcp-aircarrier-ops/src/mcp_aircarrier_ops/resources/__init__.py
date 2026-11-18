"""Resources: data a client reads without a tool call.

Each module exposes `register(mcp)`; this file aggregates them into
`register_resources(mcp)`.
"""

from __future__ import annotations

from mcp_aircarrier_ops.resources import dictionary


def register_resources(mcp) -> None:
    """Register all resources with the MCP server."""
    dictionary.register(mcp)


__all__ = ["register_resources"]
