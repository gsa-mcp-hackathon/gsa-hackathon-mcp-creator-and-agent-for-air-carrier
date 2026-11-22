"""HTTP routes beside /mcp. /health never touches the warehouse."""
from __future__ import annotations

import os

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

import docs_core
from mcp_aircarrier_docs import __version__, store

LANDING = {
    "service": "mcp-aircarrier-docs",
    "description": ("Deterministic reading of the CVN-79 PDF corpus: J-books (SCN P-40, P-5c, P-27, P-8a, P-35, "
                    "P-10), SAR/MSAR, CRS and GAO. Structure maps, whole tables with exact decimal cells and "
                    "units, tie-outs, hybrid search, and a figure finder that says which documents print a "
                    "number. No model in the loop."),
    "tools": ["docs_status", "docs_list_documents", "docs_document_map", "docs_read_page", "docs_get_table",
              "docs_find_line_item", "docs_search", "docs_find_figure", "docs_compare_figures",
              "docs_tieout_document", "docs_parse_pdf"],
    "owner": os.environ.get("APP_OWNER", ""),
    "mcp_endpoint": "/mcp",
    "transport": "streamable-http (stateless)",
}


def register_routes(mcp: FastMCP) -> None:
    @mcp.custom_route("/", methods=["GET"])
    async def root(request: Request) -> JSONResponse:
        return JSONResponse({**LANDING, "status": "running", "version": __version__,
                             "core": docs_core.__version__, "corpus_loaded_at": store.as_of()})

    @mcp.custom_route("/health", methods=["GET"])
    async def health(request: Request) -> JSONResponse:
        return JSONResponse({"status": "healthy", "service": "mcp-aircarrier-docs"})
