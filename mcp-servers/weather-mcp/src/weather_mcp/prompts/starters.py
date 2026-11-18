"""Conversation starters for Weather Mcp.

Seeded from the questions the server was built to answer, so a new user sees
what it is for without reading the README.
"""

from __future__ import annotations

from fastmcp import FastMCP

PRIMARY_USER = "anyone who needs current weather or forecast data for a US l"
TYPICAL_QUESTIONS = [
    "What is the current weather at my location?",
    "What is the forecast for a given city or coordinates?",
    "What weather alerts are active in my area?",
]


def register(mcp: FastMCP) -> None:
    """Register the starter prompts with the MCP server."""

    @mcp.prompt()
    def start_here() -> str:
        """What this server answers, and how to begin."""
        listed = "\n".join(
            f"  {index}. {question}"
            for index, question in enumerate(TYPICAL_QUESTIONS, 1)
        )
        return (
            f"I am {PRIMARY_USER}. This server answers questions like:\n"
            + listed
            + "\n\nStart by calling the describe tool so you know the exact "
            "field names and allowed values, then answer my question using "
            "the tools, and cite the as_of date you get back."
        )

    @mcp.prompt()
    def check_freshness() -> str:
        """Ask how current the underlying data is."""
        return (
            "Before I rely on this, tell me the as_of date and the update "
            "cadence of every source behind these tools, and say plainly "
            "what the data cannot answer."
        )
