"""Ask two of the MCP servers real questions with no Databricks workspace.

The One Hub server (mcp-aircarrier-hub) answers from the corpus, registers and
deterministic checks shipped in this repository. MCP A Creator designs and
reviews a server from a pasted schema. Both run here over stdio, exactly as an
MCP client would call them. The docs, analyst and ops servers read Unity
Catalog through a SQL warehouse, so they answer only inside a workspace.

Run from the repository root (needs uv):

    uv run --project mcp-server-creator python tools/try_offline.py
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]
HUB = ROOT / "the-one-hub" / "ops-center"
CREATOR = ROOT / "mcp-server-creator"


async def _call(session: ClientSession, tool: str, args: dict) -> dict:
    result = await session.call_tool(tool, args)
    if result.structuredContent:
        return result.structuredContent
    text = " ".join(getattr(c, "text", "") for c in result.content)
    try:
        return json.loads(text)
    except ValueError:
        return {"text": text}


def _server(project: Path, *command: str) -> StdioServerParameters:
    return StdioServerParameters(
        command="uv",
        args=["run", "--quiet", "--project", str(project), *command],
        cwd=str(project),
        env=dict(os.environ),
    )


async def hub() -> None:
    print("== mcp-aircarrier-hub (16 tools), no workspace\n")
    hub_server = _server(HUB, "python", "mcp/mcp_server.py")
    async with stdio_client(hub_server) as (r, w), ClientSession(r, w) as s:
        await s.initialize()
        held = await _call(s, "hub_check_claim", {
            "hull": "CVN-79", "layer": "budget", "element": "Total Ship Estimate",
            "period": "FY2027 PB", "value_musd": "13529", "tag": "VERIFIED",
            "confidence": 0.9,
        })  # fmt: skip
        print("Can I brief CVN-79 at $13,529M?")
        print(f"  decision: {held.get('decision')}  ({held.get('reason', '')[:110]})\n")
        query = {"query": "cost limitation baseline", "k": 3}
        hits = await _call(s, "hub_search_corpus", query)
        print("Where do the sources discuss the cost limitation baseline?")
        for hit in hits.get("hits", [])[:3]:
            print(f"  {hit.get('citation', '')} ({hit.get('grade', '')})")
        gaps = await _call(s, "hub_rank_gaps", {"limit": 3})
        print(f"\nWhich of the {gaps.get('open')} open questions matter most?")
        for gap in gaps.get("rows", [])[:3]:
            print(f"  {gap.get('id')}: {gap.get('title')} ({gap.get('executor')})")


async def creator() -> None:
    print("\n== MCP A Creator (10 tools), a pasted schema, no workspace\n")
    jobs = [
        "How many gallons of water were delivered per state?",
        "How many disasters were declared in each fiscal year?",
        "Show declarations for a given disaster number",
    ]
    creator_server = _server(CREATOR, "mcp-a-creator")
    async with stdio_client(creator_server) as (r, w), ClientSession(r, w) as s:
        await s.initialize()
        started = await _call(s, "creator_start_design", {
            "purpose": "Answer FEMA public assistance questions",
            "primary_user": "Disaster recovery analyst",
            "jobs_to_be_done": jobs,
        })  # fmt: skip
        design_id = started["design_id"]
        await _call(s, "creator_add_data_source", {
            "design_id": design_id, "name": "pa_projects", "kind": "uc_table",
            "modality": "structured", "catalog": "main", "schema_name": "fema",
            "table": "pa_projects", "grain": "one row per project worksheet",
            "schema_text": (
                "disasterNumber BIGINT, declarationDate TIMESTAMP, fiscalYear INT, "
                "state STRING, gallonsDelivered DOUBLE, projectAmount DOUBLE"
            ),
            "try_live_inspection": False,
        })  # fmt: skip
        designed = await _call(s, "creator_design_tools", {"design_id": design_id})
        for tool in designed.get("tools", []):
            print(f"  {tool['name']}: {tool.get('goal', '')[:70]}")
        review = await _call(s, "creator_review_server", {"design_id": design_id})
        print(f"\n  review: {review.get('verdict') or review.get('summary', '')}")


if __name__ == "__main__":
    asyncio.run(hub())
    asyncio.run(creator())
