"""Prompts submodule: reusable conversation starters.

Prompts appear in a client as slash commands. Each module exposes
`register(mcp)`; this file aggregates them into `register_prompts(mcp)`.
"""

from __future__ import annotations

from bakehouse_sales.prompts import starters


def register_prompts(mcp) -> None:
    """Register all prompts with the MCP server."""
    starters.register(mcp)


__all__ = ["register_prompts"]
