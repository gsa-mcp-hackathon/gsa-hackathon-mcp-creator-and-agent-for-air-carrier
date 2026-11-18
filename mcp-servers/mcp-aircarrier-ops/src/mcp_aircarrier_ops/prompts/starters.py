"""Conversation starters for Air Carrier Ops.

Seeded from the questions the server was built to answer, so a new user sees
what it is for without reading the README.
"""

from __future__ import annotations

from fastmcp import FastMCP

PRIMARY_USER = "A cost analyst reconciling the CVN-79 (USS John F. Kennedy) "
TYPICAL_QUESTIONS = [
    "What does the P-5c exhibit say for this cost category, on which page, "
    "with which legends?",
    "How much has been obligated on contract N00024-09-C-2116, by fiscal year?",
    "Which documents and tables mention this contract number or hull?",
    "Which open gaps and variances are queued, and for which agent?",
    "Is this contract number safe to use for CVN-79, or is it a collision "
    "or exclusion?",
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
            + "\n\nThe allowed filter values are in each tool's schema, and the "
            "mcp://dictionary/sources resource describes every field. Answer my "
            "question using the tools, and cite the as_of date you get back."
        )

    @mcp.prompt()
    def check_freshness() -> str:
        """Ask how current the underlying data is."""
        return (
            "Before I rely on this, tell me the as_of date and the update "
            "cadence of every source behind these tools, and say plainly "
            "what the data cannot answer."
        )
