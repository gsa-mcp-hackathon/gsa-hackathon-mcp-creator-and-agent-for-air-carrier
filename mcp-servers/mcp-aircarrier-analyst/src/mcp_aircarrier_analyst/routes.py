"""HTTP routes beside /mcp. /health never touches the warehouse."""
from __future__ import annotations

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from core.analyst import engine
from mcp_aircarrier_analyst import __version__, investigator

LANDING: dict = {
    "service": "mcp-aircarrier-analyst",
    "description": ("Intelligence analyst for CVN-79 (USS John F. Kennedy) cost reconciliation. Takes a record "
                    "that is missing critical data elements (a GL line, an obligation, an invoice, a budget "
                    "figure), profiles what is missing, then chains clues across the contract keyset and "
                    "knowledge graph, FPDS/USAspending, File C, sub-awards, the SCN budget book and SAR/MSAR "
                    "exhibits, Navy and DoD regulations, GAO/CRS/NPS reports and the mechanism rules. Returns "
                    "the top three cases (CVN-79, other Ford hull, Ford-class shared, other carrier, not a "
                    "carrier) with confidence, cited evidence for and against, recovered data elements, "
                    "collection requirements, and a human-review flag when confidence is low. Also infers "
                    "missing lines of accounting and explains File C vs FPDS residuals on the two CVN-79 "
                    "contracts. Every answer is grade LEAD; learns from confirmed outcomes."),
    "tools": ["analyst_investigate_record", "analyst_profile_record", "analyst_list_sources",
              "analyst_search_documents", "analyst_trace_entity", "analyst_open_questions",
              "analyst_investigate_transaction", "analyst_investigate_window", "analyst_explain_residual",
              "analyst_backtest", "analyst_model_status", "analyst_record_outcome"],
    "cases": investigator.HYPOTHESES,
    "refuses": ["Creating or promoting a claim (D16)", "Fuzzy PIID matching",
                "Summing total_dollars_obligated", "Recording an outcome without an authoritative document"],
    "owner": "xiaobing.shang1.civ@mail.mil",
    "mcp_endpoint": "/mcp",
    "transport": "streamable-http (stateless)",
}


def register_routes(mcp: FastMCP) -> None:
    @mcp.custom_route("/", methods=["GET"])
    async def root(request: Request) -> JSONResponse:
        return JSONResponse({**LANDING, "status": "running", "version": __version__, "engine": engine.ENGINE_VERSION,
                             "investigator": investigator.VERSION})

    @mcp.custom_route("/health", methods=["GET"])
    async def health(request: Request) -> JSONResponse:
        return JSONResponse({"status": "healthy", "service": "mcp-aircarrier-analyst"})
