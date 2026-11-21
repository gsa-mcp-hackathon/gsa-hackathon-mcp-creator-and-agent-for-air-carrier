"""Offline tests for run_round4.py: no model endpoint, no Spark, no MCP servers.

They cover what made the first full round 4 attempt fail or could make the next one
fail: rows held only in memory until the end, no retry on a transient serving error,
no time budget, a non-object tool argument crashing a run, and an unlabelled cut-off.

Run: python -m pytest -q -p no:cacheprovider eval/delegation/round4/test_runner.py
"""
from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent


def _load():
    spec = importlib.util.spec_from_file_location("run_round4_under_test", HERE / "run_round4.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _grader():
    spec = importlib.util.spec_from_file_location("grade_v2_under_test", HERE / "grade.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


QUESTIONS = [
    {"qid": "T1 a", "question": "How many?", "set": "generated", "category": "c",
     "expect": {"numbers": [{"kind": "count", "value": "46"}]}},
    {"qid": "T2 b", "question": "Which month?", "set": "reviewed", "category": "d",
     "expect": {"texts": ["March"]}},
]


class FakeApi:
    """Answers every call; fails the first `fail_first` calls with `error`."""

    def __init__(self, answer="There are 46 actions, in March.", fail_first=0, error="429 Too Many Requests",
                 tool_call=None):
        self.answer, self.fail_first, self.error, self.tool_call = answer, fail_first, error, tool_call
        self.calls = 0

    def do(self, method, path, body=None):
        self.calls += 1
        if self.calls <= self.fail_first:
            raise RuntimeError(self.error)
        if self.tool_call and "tools" in body:
            return {"choices": [{"message": {"content": None, "tool_calls": [self.tool_call]}}], "usage": {}}
        return {"choices": [{"message": {"content": self.answer}}], "usage": {"prompt_tokens": 3, "completion_tokens": 2}}


class FakeW:
    def __init__(self, api):
        self.api_client = api


class FakeLocal:
    def __init__(self):
        self.seen = []

    def call(self, srv, name, **args):
        self.seen.append((srv, name, args))
        return {"ok": True, "result": {"n": 46}}


@pytest.fixture
def rr(monkeypatch, tmp_path):
    mod = _load()
    monkeypatch.setattr(mod.time, "sleep", lambda s: None)
    api = FakeApi()
    sdk = types.ModuleType("databricks.sdk")
    sdk.WorkspaceClient = lambda: FakeW(api)
    monkeypatch.setitem(sys.modules, "databricks", sys.modules.get("databricks") or types.ModuleType("databricks"))
    monkeypatch.setitem(sys.modules, "databricks.sdk", sdk)
    monkeypatch.setattr(mod, "load_questions", lambda path=None: {"questions": QUESTIONS})
    monkeypatch.setattr(mod, "_grader", lambda repo: _grader())
    monkeypatch.setattr(mod, "load_tools", lambda repo: (FakeLocal(), {}, {"docs": ""}, []))
    mod._api, mod._ckdir = api, str(tmp_path)
    return mod


def test_retry_on_transient_error(rr):
    api = FakeApi(fail_first=2)
    r = rr.run_no_tools(FakeW(api), "q", "m")
    assert r["answer"].startswith("There are 46") and r["retries"] == 2 and api.calls == 3


def test_no_retry_on_permanent_error(rr):
    api = FakeApi(fail_first=1, error="400 Bad Request: invalid tools")
    with pytest.raises(RuntimeError, match="400"):
        rr.run_no_tools(FakeW(api), "q", "m")
    assert api.calls == 1


def test_retry_gives_up_after_limit(rr):
    api = FakeApi(fail_first=99)
    with pytest.raises(RuntimeError, match="429"):
        rr.run_no_tools(FakeW(api), "q", "m")
    assert api.calls == rr.RETRIES


def test_non_object_arguments_do_not_crash(rr):
    call = {"id": "c1", "function": {"name": "docs_status", "arguments": "[1, 2]"}}
    api, local = FakeApi(tool_call=call), FakeLocal()
    r = rr.run_agent(FakeW(api), local, {"docs_status": ("docs", None)}, [{}], "q", "m")
    assert local.seen == [] and r["trace"][0]["ok"] is False and len(r["trace"]) == rr.MAX_STEPS
    assert r["answer"] is None and "tool turns" in r["cutoff"]


def test_tool_exception_becomes_tool_error(rr):
    class Boom(FakeLocal):
        def call(self, srv, name, **args):
            raise TypeError("call() got multiple values for argument 'name'")
    call = {"id": "c1", "function": {"name": "docs_status", "arguments": '{"name": "x"}'}}
    r = rr.run_agent(FakeW(FakeApi(tool_call=call)), Boom(), {"docs_status": ("docs", None)}, [{}], "q", "m")
    assert r["trace"][0]["ok"] is False


def test_full_run_writes_checkpoint_and_grades(rr):
    rows = rr.run(None, "/repo", models=["m1", "m2"], repeats=2, workers=3, run_id="t-full", checkpoint_dir=rr._ckdir)
    assert len(rows) == 2 * 2 * 3  # models x questions x (no_tools + 2 reps)
    assert all(r["passed"] for r in rows) and all(r["error"] is None for r in rows)
    lines = Path(rr.checkpoint_path("t-full", rr._ckdir)).read_text().splitlines()
    assert len(lines) == 12 and len({(json.loads(x)["model"], json.loads(x)["mode"], json.loads(x)["qid"]) for x in lines}) == 12


def test_budget_stops_then_resume_finishes_without_duplicates(rr):
    first = rr.run(None, "/repo", models=["m1"], repeats=3, workers=2, run_id="t-res", budget_s=0,
                   checkpoint_dir=rr._ckdir)
    assert first == []  # budget 0: nothing started
    part = rr.run(None, "/repo", models=["m1"], repeats=3, workers=2, run_id="t-res", checkpoint_dir=rr._ckdir,
                  only=["T1"])
    assert len(part) == 4
    calls_before = rr._api.calls
    full = rr.run(None, "/repo", models=["m1"], repeats=3, workers=2, run_id="t-res", checkpoint_dir=rr._ckdir)
    assert len(full) == 8 and rr._api.calls - calls_before == 4  # only T2's 4 runs were made
    keys = [(r["model"], r["mode"], r["qid"]) for r in full]
    assert len(set(keys)) == 8
    assert len({str(r["run_at"]) for r in full}) == 1  # one run, one timestamp


def test_half_written_checkpoint_line_is_ignored(rr, tmp_path):
    p = tmp_path / "x.jsonl"
    p.write_text(json.dumps({"run_at": "2026-11-21T00:00:00+00:00", "model": "m", "mode": "no_tools", "qid": "T1 a"})
                 + "\n{\"run_at\": \"2026")
    rows = rr.read_checkpoint(str(p))
    assert len(rows) == 1 and rows[0]["run_at"].year == 2026


def test_error_row_is_recorded_not_raised(rr):
    rr._api.fail_first, rr._api.error = 10**6, "400 Bad Request"
    rows = rr.run(None, "/repo", models=["m1"], repeats=1, workers=2, run_id="t-err", checkpoint_dir=rr._ckdir)
    assert len(rows) == 4 and all(not r["passed"] and r["error"].startswith("RuntimeError: 400") for r in rows)
