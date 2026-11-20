"""HTTP-only routes that sit alongside the /mcp endpoint.

`/health` matters for deployment: Databricks Apps uses an HTTP health check
to decide the app started. Keep it fast and dependency-free, so it answers
even when the warehouse is unreachable.
"""

from __future__ import annotations

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from weather_mcp import __version__


def register_routes(mcp: FastMCP) -> None:
    """Register custom HTTP routes with the server."""

    @mcp.custom_route("/", methods=["GET"])
    async def index(request: Request) -> JSONResponse:
        # Opening the app URL in a browser lands here. Without this route the
        # root answered 404 "Not Found", which read as a broken deployment.
        return JSONResponse(
            {
                "service": "weather-mcp",
                "version": __version__,
                "mcp_endpoint": "/mcp",
                "health": "/health",
                "note": "MCP server: connect an MCP client to /mcp.",
            }
        )

    @mcp.custom_route("/health", methods=["GET"])
    async def health_check(request: Request) -> JSONResponse:
        return JSONResponse({"status": "healthy", "service": "weather-mcp"})

    @mcp.custom_route("/version", methods=["GET"])
    async def version(request: Request) -> JSONResponse:
        return JSONResponse({"version": __version__})
