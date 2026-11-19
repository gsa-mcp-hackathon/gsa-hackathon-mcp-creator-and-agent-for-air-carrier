"""Data dictionary resources.

A client can read these without spending a tool call, which is
the cheapest way to stop a model guessing column semantics.
"""

from __future__ import annotations

import json

from fastmcp import FastMCP

CATALOGUE = {
    "nws": {
        "kind": "rest_api",
        "modality": "semi_structured",
        "title": "NWS Weather API (weather.gov)",
        "grain": (
            "one HTTP response per NWS API call; "
            "each forecast endpoint returns a list of forecast periods"
        ),
        "update_cadence": "live — data is fresh at call time",
        "as_of": "",
        "fields": [
            {
                "name": "GET /points/{latitude}",
                "type": "string",
                "role": "dimension",
                "description": "",
                "allowed_values": None,
            },
            {
                "name": "{longitude}",
                "type": "string",
                "role": "dimension",
                "description": "",
                "allowed_values": None,
            },
        ],
    }
}


def register(mcp: FastMCP) -> None:
    """Register the dictionary resources with the server."""

    @mcp.resource("weather://dictionary/sources")
    def source_catalogue() -> str:
        """Every source behind this server, with its fields."""
        return json.dumps(CATALOGUE, indent=2, default=str)

    @mcp.resource("weather://dictionary/{source}")
    def source_dictionary(source: str) -> str:
        """The field list for one named source."""
        entry = CATALOGUE.get(source)
        if entry is None:
            known = ", ".join(sorted(CATALOGUE))
            return json.dumps(
                {
                    "error": f"unknown source {source!r}",
                    "known_sources": known,
                },
                indent=2,
            )
        return json.dumps(entry, indent=2, default=str)
