"""Security tests for the boundaries this server actually has.

Every check here is deterministic and offline. Nothing probes a real
network destination.
"""

from __future__ import annotations

import pytest

from weather_mcp.app import mcp

FORBIDDEN_PARAM_NAMES = {
    "url",
    "uri",
    "endpoint",
    "sql",
    "query_sql",
    "statement",
    "path",
    "file_path",
    "filepath",
    "command",
}


def tool_schema(tool) -> dict:
    """Read a tool's input schema across FastMCP versions."""
    return getattr(tool, "parameters", None) or getattr(tool, "inputSchema", None) or {}


def hint(tool, name: str):
    """Read an annotation hint across FastMCP versions."""
    annotations = tool.annotations
    if annotations is None:
        return None
    if hasattr(annotations, name):
        return getattr(annotations, name)
    parts = name.split("_")
    legacy = parts[0] + "".join(part.capitalize() for part in parts[1:])
    return getattr(annotations, legacy, None)


async def test_no_tool_accepts_a_url_sql_or_path_argument():
    """These three arguments turn a data tool into an exfiltration primitive.

    If a tool genuinely needs one, add it to `allowed` below with a comment
    saying why, and validate it against an allowlist of exact destinations.
    """
    allowed: set[str] = set()
    offenders: list[str] = []
    for tool in await mcp.list_tools():
        properties = tool_schema(tool).get("properties") or {}
        for param in properties:
            if param.lower() in FORBIDDEN_PARAM_NAMES - allowed:
                offenders.append(f"{tool.name}.{param}")
    assert not offenders, f"unsafe tool arguments: {offenders}"


async def test_read_only_tools_are_annotated_read_only():
    for tool in await mcp.list_tools():
        if hint(tool, "read_only_hint"):
            assert not hint(tool, "destructive_hint"), (
                f"{tool.name} claims read-only and destructive at once"
            )


def test_relative_path_validation_refuses_absolute_and_escaping_paths():
    from weather_mcp.data.rest import _validate_relative_path

    for attempt in (
        "https://evil.example.com/x",
        "//evil.example.com/x",
        "/absolute",
        "../escape",
        "records?x=1",
        "",
    ):
        with pytest.raises(ValueError):
            _validate_relative_path(attempt)
    assert _validate_relative_path("records/123") == "records/123"
