"""Coordinates and freshness metadata for every data source.

Generated from the server specification. Edit here rather than in the tools,
so a table move or a refresh change is a one-line edit.
"""

from __future__ import annotations

# --- nws: NWS Weather API (weather.gov)
NWS_KIND = "rest_api"
NWS_GRAIN = "one HTTP response per NWS API call; each forecast endpoint returns a list of forecast periods"
NWS_CADENCE = "live — data is fresh at call time"
NWS_AS_OF = ""
NWS_COLUMNS = ("GET /points/{latitude}", "{longitude}")
