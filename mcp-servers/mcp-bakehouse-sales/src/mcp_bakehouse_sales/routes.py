"""HTTP-only routes that sit alongside the /mcp endpoint.

`/health` matters for deployment: Databricks Apps uses an HTTP health check
to decide the app started. Keep it fast and dependency-free, so it answers
even when the warehouse is unreachable.
"""

from __future__ import annotations

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from mcp_bakehouse_sales import __version__

# What a person sees when they open the app URL in a browser. MCP clients
# use /mcp; this only describes the server and how to connect it.
LANDING: dict = {
    "service": "mcp-bakehouse-sales",
    "name": "Mcp Bakehouse Sales",
    "description": "Let an agent answer a bakery franchise sales analyst's "
    "questions about point-of-sale transactions: revenue by "
    "franchise, best-selling products, sales by payment "
    "method, and daily sales trends.",
    "primary_user": "a sales analyst at the Bakehouse franchise head office "
    "who reviews franchise performance weekly",
    "tools": [
        "mcp_describe_sales",
        "mcp_top_product_by_transactionid",
        "mcp_sales_totals",
        "mcp_sales_trend",
    ],
    "data": ["samples.bakehouse.sales_transactions"],
    "refuses": [
        "Customer personal details such as names, emails or addresses",
        "Forecasting future sales",
        "Changing or deleting any sales record",
    ],
    "owner": "xiaobing.shang1.civ@mail.mil",
    "how_to_use": [
        "In Genie Code, open Settings > Connectors > Custom MCP Server.",
        "Select mcp-bakehouse-sales and save.",
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
        return JSONResponse({"status": "healthy", "service": "mcp-bakehouse-sales"})

    @mcp.custom_route("/version", methods=["GET"])
    async def version(request: Request) -> JSONResponse:
        return JSONResponse({"version": __version__})
