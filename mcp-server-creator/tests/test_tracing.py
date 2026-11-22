"""Every tool call leaves a trace, and no trace carries arguments or results."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from fastmcp import Client

from mcp_server_creator import volume_files
from mcp_server_creator.app import mcp
from mcp_server_creator.config import settings

SECRET_PURPOSE = "zebra-canary-purpose-text"


def _traces(output: str) -> list[dict]:
    return [
        json.loads(line[len("TRACE ") :])
        for line in output.splitlines()
        if line.startswith("TRACE ")
    ]


async def test_a_tool_call_emits_one_trace(capsys):
    async with Client(mcp) as client:
        await client.call_tool("creator_list_library", {})
    traces = _traces(capsys.readouterr().out)
    assert len(traces) == 1
    trace = traces[0]
    assert trace["tool"] == "creator_list_library"
    assert trace["outcome"] == "ok"
    assert isinstance(trace["duration_ms"], int)
    assert set(trace) >= {"ts", "id", "caller", "identity"}


async def test_a_trace_never_contains_arguments(capsys):
    async with Client(mcp) as client:
        await client.call_tool(
            "creator_start_design",
            {
                "purpose": SECRET_PURPOSE,
                "primary_user": "analyst",
                "jobs_to_be_done": ["find expiring awards"],
            },
            raise_on_error=False,
        )
    output = capsys.readouterr().out
    assert _traces(output)
    assert SECRET_PURPOSE not in output


async def test_a_returned_error_is_traced_as_a_tool_error(capsys):
    async with Client(mcp) as client:
        await client.call_tool(
            "creator_generate_project",
            {"design_id": "dsn_00000000"},
            raise_on_error=False,
        )
    (trace,) = _traces(capsys.readouterr().out)
    assert trace["outcome"] == "tool_error"
    assert trace["error"]


async def test_traces_go_to_a_volume_when_configured(monkeypatch, capsys):
    written: dict[str, str] = {}

    class Files:
        def upload(self, path, contents, overwrite=False):
            written[path] = contents.read().decode()

    volume_files.set_client(SimpleNamespace(files=Files()))
    root = "/Volumes/users/someone/mcp_a_creator/traces"
    monkeypatch.setattr(settings, "creator_trace_dir", root)
    try:
        async with Client(mcp) as client:
            await client.call_tool("creator_list_library", {})
    finally:
        volume_files.set_client(None)
    (path,) = written
    assert path.startswith(root + "/") and path.endswith(".json")
    assert json.loads(written[path])["tool"] == "creator_list_library"


@pytest.mark.parametrize("enabled", [False])
async def test_tracing_can_be_turned_off(monkeypatch, capsys, enabled):
    monkeypatch.setattr(settings, "creator_trace_enabled", enabled)
    async with Client(mcp) as client:
        await client.call_tool("creator_list_library", {})
    assert not _traces(capsys.readouterr().out)


def test_stdio_stdout_carries_only_protocol_messages(tmp_path):
    """Over stdio, stdout is the protocol channel. Until 1.0.0rc3 every tool
    call also printed its audit line there, so a client logged a JSON parse
    error with a traceback after each call. The audit line now goes to stderr.
    """
    import os
    import subprocess
    import sys

    requests = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "stdio-test", "version": "0"},
            },
        },
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "creator_list_library", "arguments": {}},
        },
    ]
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in {"DATABRICKS_APP_PORT", "PORT", "MCP_TRANSPORT"}
    }
    server = subprocess.Popen(
        [sys.executable, "-m", "mcp_server_creator.app"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=tmp_path,
        env=env,
    )
    try:
        for request in requests:
            server.stdin.write(json.dumps(request) + "\n")
            server.stdin.flush()
        answers = []
        while not any(a.get("id") == 2 for a in answers):
            line = server.stdout.readline()
            assert line, "the server closed stdout before answering"
            answers.append(json.loads(line))  # every stdout line is JSON
    finally:
        server.stdin.close()
        server.terminate()
        errors = server.stderr.read()
        server.wait(timeout=10)
    assert all(a.get("jsonrpc") == "2.0" for a in answers), answers
    assert '"tool":"creator_list_library"' in errors
    assert "TRACE " in errors
