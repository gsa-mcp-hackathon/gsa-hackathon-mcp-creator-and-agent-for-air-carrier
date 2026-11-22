"""Ask the evidence as an MCP host (round 10, A7).

Until 2026-11-21 the front center's agents read the stores through in-app
tools and called no MCP server. With AIRCARRIER_ASK_VIA_MCP=1 the /ask agent
lists the deployed servers' tools, offers them to the model and sends each
call to the server that owns it. These tests run the host against a fake
JSON-RPC transport, with no workspace.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from api import agent, mcp_host

URLS = {"mcp-aircarrier-docs": "https://mcp-aircarrier-docs-1.aws.databricksapps.com",
        "mcp-aircarrier-ops": "https://mcp-aircarrier-ops-1.aws.databricksapps.com",
        "mcp-aircarrier-hub": "https://mcp-aircarrier-hub-1.aws.databricksapps.com"}
TOOLS = {"mcp-aircarrier-docs": ["docs_search", "docs_get_table"],
         "mcp-aircarrier-ops": ["carrier_search_obligations"],
         "mcp-aircarrier-hub": ["hub_check_claim"]}


class FakeServers:
    def __init__(self, down=()):
        self.down, self.calls, self.headers_seen = set(down), [], []

    def resolve(self, app):
        return URLS[app]

    def post(self, url, headers, body):
        self.headers_seen.append(headers.get("Authorization"))
        app = next(a for a, u in URLS.items() if url.startswith(u))
        if app in self.down:
            return 503, "unavailable"
        m, i = body["method"], body["id"]
        if m == "initialize":
            result = {"protocolVersion": mcp_host.PROTOCOL}
        elif m == "tools/list":
            result = {"tools": [{"name": n, "description": f"{n} on {app}",
                                 "inputSchema": {"type": "object", "properties": {}}}
                                for n in TOOLS[app]]}
        else:
            self.calls.append((app, body["params"]["name"], body["params"]["arguments"]))
            if body["params"]["name"] == "docs_get_table":
                result = {"isError": True, "content": [{"type": "text", "text": "no table 'x'"}]}
            else:
                result = {"content": [{"type": "text", "text": "{}"}],
                          "structuredContent": {"hits": [{"file": "SCN PB27", "page": 95}]}}
        return 200, "event: message\ndata: " + json.dumps({"jsonrpc": "2.0", "id": i, "result": result})


def host(servers):
    return mcp_host.McpHost(servers.resolve, lambda: {"Authorization": "Bearer t"}, servers.post,
                            apps=list(URLS)).connect()


def test_the_host_lists_every_server_and_routes_each_tool_to_its_owner():
    s = FakeServers()
    h = host(s)
    assert {t["name"] for t in h.tools} == {n for ns in TOOLS.values() for n in ns}
    body, extra = h.call("docs_search", {"query": "Total Ship Estimate"})
    assert extra["server"] == "mcp-aircarrier-docs" and body["hits"][0]["page"] == 95
    assert s.calls == [("mcp-aircarrier-docs", "docs_search", {"query": "Total Ship Estimate"})]


def test_a_tool_error_comes_back_as_an_error():
    body, extra = host(FakeServers()).call("docs_get_table", {"table_id": "x"})
    assert body == {"error": "no table 'x'"} and extra["server"] == "mcp-aircarrier-docs"


def test_a_server_that_is_down_is_recorded_and_the_rest_still_work():
    h = host(FakeServers(down={"mcp-aircarrier-ops"}))
    assert "mcp-aircarrier-ops" in h.unreachable
    assert "carrier_search_obligations" not in h.owner and "hub_check_claim" in h.owner


@pytest.mark.parametrize("url", ["http://mcp-x.aws.databricksapps.com", "https://evil.example.com",
                                 "https://mcp-x.aws.databricksapps.com:8443",
                                 "https://u:p@mcp-x.aws.databricksapps.com"])
def test_the_token_goes_only_to_a_databricks_apps_host(url):
    with pytest.raises(mcp_host.UnsafeURL):
        mcp_host.safe_mcp_url(url)
    assert mcp_host.safe_mcp_url(URLS["mcp-aircarrier-hub"]).endswith(".databricksapps.com/mcp")


def _model(script):
    """A fake model: each call returns the next scripted message."""
    steps = iter(script)

    def call(model, body):
        call.tools = [t["function"]["name"] for t in body.get("tools") or []] or call.tools
        return {"choices": [{"message": next(steps)}]}
    call.tools = []
    return call


def test_ask_uses_the_mcp_servers_tools_and_says_which_server_answered(monkeypatch):
    monkeypatch.setattr(agent, "models", lambda: ["m"])
    s = FakeServers()
    call = _model([
        {"role": "assistant", "content": None, "tool_calls": [
            {"id": "1", "function": {"name": "docs_search",
                                     "arguments": json.dumps({"query": "TSE"})}}]},
        {"role": "assistant", "content": "The total is printed on p.95 [SCN PB27 p.95]."}])
    out = agent.ask("What is the Total Ship Estimate?", call=call, host=host(s))
    assert out["transport"]["kind"] == "mcp" and out["transport"]["tools"] == 4
    assert set(call.tools) == {"docs_search", "docs_get_table", "carrier_search_obligations",
                               "hub_check_claim"}
    assert out["trace"][0]["server"] == "mcp-aircarrier-docs"
    assert any(c["label"] == "mcp-aircarrier-docs docs_search" for c in out["citations"])


def test_ask_falls_back_to_its_own_tools_when_no_server_answers(monkeypatch):
    monkeypatch.setattr(agent, "models", lambda: ["m"])
    call = _model([{"role": "assistant", "content": "No data."}])
    down = FakeServers(down=set(URLS))
    out = agent.ask("anything", call=call, host=host(down))
    assert out["transport"]["kind"] == "in-app"
    assert "unreachable" in out["transport"]["note"]
    assert "search_documents" in call.tools


def test_without_the_setting_ask_is_unchanged(monkeypatch):
    monkeypatch.delenv("AIRCARRIER_ASK_VIA_MCP", raising=False)
    monkeypatch.setattr(agent, "models", lambda: ["m"])
    call = _model([{"role": "assistant", "content": "ok"}])
    out = agent.ask("anything", call=call)
    assert out["transport"] == {"kind": "in-app", "note": None}
