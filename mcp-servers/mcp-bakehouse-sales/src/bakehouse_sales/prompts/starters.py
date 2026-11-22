"""Conversation starters for Bakehouse Sales.

Seeded from the questions the server was built to answer, so a new user sees
what it is for without reading the README.
"""

from __future__ import annotations

from fastmcp import FastMCP

PRIMARY_USER = "a sales analyst at the Bakehouse franchise head office who r"
TYPICAL_QUESTIONS = [
    "Which franchises had the highest total revenue between two dates?",
    "What are the top 5 best-selling products by quantity for a given franchise?",
    "How does revenue split by payment method?",
    "What was total revenue per day over a date range?",
    "How many transactions and what average ticket size did a franchise have?",
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
