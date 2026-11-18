"""HTTP-only routes that sit alongside the /mcp endpoint.

`/health` matters for deployment: Databricks Apps uses an HTTP health check
to decide the app started. Keep it fast and dependency-free, so it answers
even when the warehouse is unreachable.
"""

from __future__ import annotations

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from mcp_aircarrier_ops import __version__
from mcp_aircarrier_ops.data import sources

# What a person sees when they open the app URL in a browser. MCP clients
# use /mcp; this only describes the server and how to connect it.
LANDING: dict = {
    "service": "mcp-aircarrier-ops",
    "name": "Air Carrier Ops",
    "description": "Let an agent answer CVN-79 cost-reconciliation questions "
    "from the Air Carrier lossless stores, returning every "
    "figure with its page or row coordinate, legends, tag and "
    "source, and never promoting a figure on its own.",
    "primary_user": "A cost analyst reconciling the CVN-79 (USS John F. "
    "Kennedy) program cost across budget exhibits and "
    "contract obligation records",
    "tools": [
        "carrier_get_exhibit_cells",
        "carrier_search_exhibit_cells",
        "carrier_search_obligations_2116",
        "carrier_search_graph_edges",
        "carrier_search_work_register",
        "carrier_work_register_counts",
    ],
    "data": [
        f"{sources.STORE_CATALOG}.{sources.STORE_SCHEMA}.{table}"
        for table in (
            sources.EXHIBIT_CELLS_TABLE,
            sources.OBLIGATIONS_2116_TABLE,
            sources.GRAPH_EDGES_TABLE,
            sources.WORK_REGISTER_TABLE,
        )
    ],
    "refuses": [
        "Attribute a budget column to a hull (that is the "
        "Attributor's job and stays DERIVED)",
        "Sum total_dollars_obligated or announced modifications as obligations",
        "Write to, promote, or edit any table",
        "Questions about hulls or programs outside the CVN-78 class corpus",
    ],
    "owner": "xiaobing.shang1.civ@mail.mil",
    "how_to_use": [
        "In Genie Code, open Settings > Connectors > Custom MCP Server.",
        "Choose mcp-aircarrier-ops, then save.",
        "Ask a question in your own words; the agent picks the tool.",
    ],
    "transport": "streamable-http (stateless)",
    "mcp_endpoint": "/mcp",
    "endpoints": {"health": "/health", "version": "/version"},
    "built_by": "MCP A Creator",
}


def register_routes(mcp: FastMCP) -> None:
    """Register custom HTTP routes with the server."""

    @mcp.custom_route("/", methods=["GET"])
    async def root(request: Request) -> JSONResponse:
        return JSONResponse({**LANDING, "status": "running", "version": __version__})

    @mcp.custom_route("/health", methods=["GET"])
    async def health_check(request: Request) -> JSONResponse:
        return JSONResponse({"status": "healthy", "service": "mcp-aircarrier-ops"})

    @mcp.custom_route("/version", methods=["GET"])
    async def version(request: Request) -> JSONResponse:
        return JSONResponse({"version": __version__})
