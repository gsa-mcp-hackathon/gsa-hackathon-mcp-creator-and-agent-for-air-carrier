"""Describe NWS Weather API (weather.gov).

Tell me what is in NWS Weather API (weather.gov): the fields, what they mean, the
allowed values, and how fresh it is.

Source: nws (rest_api).
"""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from weather_mcp.data import sources

AS_OF = sources.NWS_AS_OF


def register(mcp: FastMCP) -> None:
    """Register the weather_describe_nws tool with the MCP server."""

    @mcp.tool(
        name="weather_describe_nws",
        annotations={
            "title": "Describe NWS Weather API (weather.gov)",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def weather_describe_nws() -> dict[str, Any]:
        """Tell me what is in NWS Weather API (weather.gov): the fields, what they mean,
        the allowed values, and how fresh it is.

        One record is one HTTP response per NWS API call; each forecast endpoint returns
        a list of forecast periods. The source refreshes live — data is fresh at call
        time and currently reflects the as_of value in the response.

        Returns: The source's grain, update cadence, as-of date, and every field with
        its type, role, description, and allowed values.

        This tool needs no credentials and no query: the dictionary ships with the
        server.
        """
        fields = [
            {
                "name": "GET /points/{latitude}",
                "type": "string",
                "role": "dimension",
                "description": "",
                "example": 'Response: { "properties": { "forecast": "<url>"',
                "allowed_values": None,
            },
            {
                "name": "{longitude}",
                "type": "string",
                "role": "dimension",
                "description": "",
                "example": '"forecastHourly": "<url>"',
                "allowed_values": None,
            },
        ]
        return {
            "source": "nws",
            "kind": sources.NWS_KIND,
            "grain": sources.NWS_GRAIN,
            "update_cadence": sources.NWS_CADENCE,
            "as_of": sources.NWS_AS_OF,
            "field_count": len(fields),
            "fields": fields,
            "note": (
                "Read this before calling the other tools: it gives "
                "the exact column spellings and the allowed values."
            ),
        }
