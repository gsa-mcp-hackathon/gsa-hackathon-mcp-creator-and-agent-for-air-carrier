"""Offline tests for the probe (no network). Run: python -m pytest -q test_probe.py"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import probe as P

DOCS_OK = {"value_musd": "13529", "n_text_hits": 2, "text_hits": [
    {"filename": "CVN_78_MSAR_FY2027_PBv2.pdf", "page": 8, "printed": "$13.529 billion"}]}


def sse(obj):
    return "event: message\ndata: " + json.dumps(obj) + "\n\n"


def server(tools=11, answer=DOCS_OK, status=200, fail_on=None, as_sse=True, tool_error=False):
    calls = []

    def post(url, headers, body):
        calls.append((url, body["method"], headers.get("Authorization")))
        if body["method"] == fail_on:
            return 401, ""
        if body["method"] == "initialize":
            res = {"protocolVersion": P.PROTOCOL, "capabilities": {}}
        elif body["method"] == "tools/list":
            res = {"tools": [{"name": f"t{i}"} for i in range(tools)]}
        elif tool_error:
            res = {"isError": True, "content": [{"type": "text", "text": "boom"}]}
        else:
            res = {"content": [{"type": "text", "text": json.dumps(answer)}], "structuredContent": answer}
        msg = {"jsonrpc": "2.0", "id": body["id"], "result": res}
        return status, (sse(msg) if as_sse else json.dumps(msg))
    return post, calls


def sweep(post, resolve=lambda a: (f"https://{a}-7474654188777746.aws.databricksapps.com", "dep-1")):
    return P.Sweep(resolve, lambda: {"Authorization": "Bearer SECRET"}, post)


DOCS = P.TARGETS[0]


def test_green_docs_sweep_records_four_steps_and_no_secret():
    post, calls = server()
    s = sweep(post)
    assert s.target(DOCS) is True
    assert [r["step"] for r in s.rows] == ["resolve", "initialize", "tools_list", "known_answer"]
    assert all(r["ok"] for r in s.rows) and s.rows[-1]["detail"] == "docs_find_figure ok"
    assert [c[1] for c in calls] == ["initialize", "tools/list", "tools/call"]
    assert calls[0][0] == "https://mcp-aircarrier-docs-7474654188777746.aws.databricksapps.com/mcp"
    assert "SECRET" not in json.dumps(s.rows)                    # token never stored


def test_docs_known_answer_catches_the_old_bug():
    old = {"value_musd": "13529", "n_text_hits": 0, "text_hits": [], "found": False}
    post, _ = server(answer=old)
    s = sweep(post)
    assert s.target(DOCS) is False
    assert s.rows[-1]["step"] == "known_answer" and "found nothing" in s.rows[-1]["detail"]
    wrong_page = dict(DOCS_OK, text_hits=[{"filename": "CVN 78 MSAR Dec 2023.pdf", "page": 7}])
    post, _ = server(answer=wrong_page)
    s = sweep(post)
    assert s.target(DOCS) is False and "p. 8" in s.rows[-1]["detail"]


def test_failure_stops_the_target_and_says_where():
    post, calls = server(fail_on="initialize")
    s = sweep(post)
    assert s.target(DOCS) is False
    assert [(r["step"], r["ok"], r["http_status"]) for r in s.rows] == [
        ("resolve", True, None), ("initialize", False, 401)]
    assert len(calls) == 1


def test_too_few_tools_tool_error_and_plain_json():
    post, _ = server(tools=3, as_sse=False)
    s = sweep(post)
    assert s.target(DOCS) is False and s.rows[-1]["detail"] == "3 tools, expected at least 11"
    post, _ = server(tool_error=True)
    s = sweep(post)
    assert s.target(DOCS) is False and "tool error: boom" in s.rows[-1]["detail"]


def test_resolve_and_transport_errors_are_rows_not_crashes():
    def bad_resolve(a):
        raise PermissionError("no access")
    post, _ = server()
    s = sweep(post, bad_resolve)
    assert s.target(DOCS) is False and s.rows == [s.rows[0]] and s.rows[0]["step"] == "resolve"
    s = sweep(post, lambda a: ("https://x", None))
    assert s.target(DOCS) is False and "no active deployment" in s.rows[0]["detail"]

    def down(url, headers, body):
        raise ConnectionError("reset")
    s = sweep(down)
    assert s.target(DOCS) is False and s.rows[-1]["step"] == "transport"


def test_run_summarizes_failing_targets_and_creator_lists_only():
    post, calls = server(tools=16, answer={"engine": "analyst/0.1", "totals": {"record_count": 5},
                                           "source": "sales", "fields": [{"name": "transactionID"}],
                                           "decision": "human_review", **DOCS_OK})
    out = sweep(post).run()
    assert out["ok"] and out["failing"] == [] and out["targets"] == 6
    creator = [c for c in calls if "mcp-a-creator" in c[0]]
    assert [c[1] for c in creator] == ["initialize", "tools/list"]       # never calls a creator tool


def test_hub_known_answer_holds_the_unconfirmed_baseline():
    assert P._hub({"decision": "human_review"}) is None
    assert P._hub({"decision": "promote"})
    assert P._hub({})


def test_bakehouse_known_answer_needs_the_sales_dictionary():
    assert P._bakehouse({"source": "sales", "fields": [{"name": "transactionID"}]}) is None
    assert P._bakehouse({"source": "sales", "fields": []})
    assert P._bakehouse({})


def test_safe_mcp_url_allows_only_apps_hosts():
    ok = "https://mcp-aircarrier-docs-7474654188777746.aws.databricksapps.com/mcp"
    assert P.safe_mcp_url(ok) == ok
    assert P.safe_mcp_url("https://A-1.AWS.DatabricksApps.com:443/mcp") == "https://a-1.aws.databricksapps.com/mcp"
    for bad in ["http://a-1.aws.databricksapps.com/mcp",            # not https
                "https://evil.com/mcp",                              # foreign host
                "https://a.databricksapps.com.evil.com/mcp",         # suffix trick
                "https://evildatabricksapps.com/mcp",                # no dot boundary
                "https://databricksapps.com/mcp",                    # bare suffix
                "https://u:p@a-1.aws.databricksapps.com/mcp",        # credentials
                "https://a.databricksapps.com@evil.com/mcp",         # userinfo trick
                "https://a-1.aws.databricksapps.com:8443/mcp",       # non-default port
                "https://a-1.aws.databricksapps.com/other",          # wrong path
                "https://a-1.aws.databricksapps.com/mcp?x=1",        # query
                "https://169.254.169.254/mcp", "https://localhost/mcp", "", None]:
        try:
            P.safe_mcp_url(bad)
        except P.UnsafeURL:
            continue
        raise AssertionError(f"not refused: {bad}")


def test_foreign_url_is_refused_before_any_token_is_sent():
    post, calls = server()
    s = sweep(post, lambda a: ("https://evil.example.com", "dep-1"))
    assert s.target(DOCS) is False and calls == []
    assert s.rows[-1]["step"] == "resolve" and "refused URL" in s.rows[-1]["detail"]


def test_rows_have_exactly_the_documented_columns_and_clip_detail():
    post, _ = server(fail_on="tools/list")
    s = sweep(post)
    s.target(DOCS)
    assert all(list(r) == P.COLUMNS for r in s.rows)
    json.loads(json.dumps(s.rows))                                      # JSON-lines safe
    s._row("x", "resolve", False, detail="y" * 1000)
    assert len(s.rows[-1]["detail"]) == P.DETAIL_MAX
