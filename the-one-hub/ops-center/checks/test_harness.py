#!/usr/bin/env python3
"""Characterization tests for the harness (ops/harness). Cleanup batch 0.

Written against the code as it stood on 2026-11-10, including behaviour that
docs/cleanup-inventory.md section 9 records as suspect. A test pinned to a
suspect behaviour says CHARACTERIZES Fn. If a later change makes one of those
fail, that change altered behaviour and is not a cleanup.

Spark and the model endpoints are faked. The LIVE tests run the seeded
detection SQL against temp views only (no table is read or written) and are
skipped when there is no active Spark session.

Run:
    PYTHONDONTWRITEBYTECODE=1 python3 checks/test_harness.py      (LIVE skipped)
    in a serverless/notebook session: runpy.run_path(<this file>, run_name="__main__")
    pytest also works: python -m pytest -p no:cacheprovider --assert=plain checks/test_harness.py
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]   # a test, not a serverless entry point
sys.dont_write_bytecode = True
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pyspark.sql import Row, SparkSession

from ops.harness import catalog as C
from ops.harness import (
    checker,
    tools,
)
from ops.harness import evaluate as ev
from ops.harness import orchestrator as orch
from ops.harness import specialists as sp

# ---- fakes ------------------------------------------------------------------

class FakeDF:
    def __init__(self, rows):
        self._rows = list(rows)

    def collect(self):
        return list(self._rows)

    def count(self):
        return len(self._rows)


class FakeSpark:
    """Records every statement; the handler decides what a SELECT returns."""

    def __init__(self, handler=None):
        self.queries: list[str] = []
        self.args: list[dict] = []
        self.handler = handler or (lambda q: [])

    def sql(self, q, args=None):
        self.queries.append(q)
        self.args.append(dict(args or {}))
        return FakeDF(self.handler(q))

    def inserts(self, table):
        return [q for q in self.queries if f"INSERT INTO {table}" in q]

    def inserts_with_args(self, table):
        return [(q, a) for q, a in zip(self.queries, self.args) if f"INSERT INTO {table}" in q]

    # F23: a run's agent_steps are its tool steps, then at most one finding.
    def _is_finding(self, a):
        try:
            out = json.loads(a.get("output_json") or "null")
        except ValueError:
            return False
        return isinstance(out, dict) and out.get("kind") == "finding"

    def tool_steps(self):
        return [(q, a) for q, a in self.inserts_with_args(C.AGENT_STEPS) if not self._is_finding(a)]

    def finding_steps(self):
        return [(q, a) for q, a in self.inserts_with_args(C.AGENT_STEPS) if self._is_finding(a)]


@contextmanager
def patched(*pairs):
    saved = [(o, n, getattr(o, n)) for o, n, _ in pairs]
    try:
        for o, n, v in pairs:
            setattr(o, n, v)
        yield
    finally:
        for o, n, v in saved:
            setattr(o, n, v)


def with_spark(fake):
    def getter():
        return fake
    return patched((tools, "_spark", getter), (orch, "_spark", getter),
                   (checker, "_spark", getter), (ev, "_spark", getter))


class ScriptedModel:
    """Plays back assistant messages; endpoints in fail raise."""

    def __init__(self, script, fail=()):
        self.script = list(script)
        self.fail = set(fail)
        self.calls: list[tuple[str, dict]] = []

    def __call__(self, endpoint, body):
        self.calls.append((endpoint, json.loads(json.dumps(body, default=str))))
        if endpoint in self.fail:
            raise RuntimeError("endpoint down")
        return {"choices": [{"message": self.script.pop(0)}]}


def tc(i, name, args):
    return {"id": f"tc{i}", "type": "function",
            "function": {"name": name, "arguments": json.dumps(args)}}


def tool_msg(*calls):
    return {"role": "assistant", "content": None, "tool_calls": list(calls)}


def final(text="done"):
    return {"role": "assistant", "content": text}


EXC = {"exception_id": "exc-1", "rule_id": "CC-02", "rule_version": 4,
       "subject_type": "reconciliation_item", "subject_ids": ["exc-0"],
       "area": "cost_capture", "owner_office": "PEO Carriers", "owner_role": "PMS379",
       "required_action": "Escalation", "status": "open", "record_ids": ["exc-0"]}


def owner_rows(q, holders=("pm@navy.mil",), actions=("apply", "reject")):
    """role_map / authority answers for the G-e pre-check (A-34); None if q is neither."""
    if q.startswith(f"SELECT uc_group FROM {C.ROLE_MAP}"):
        return [Row(uc_group=h) for h in holders]
    if q.startswith(f"SELECT action FROM {C.AUTHORITY}"):
        return [Row(action=a) for a in actions]
    return None

GROUNDED = {"target_table": "t", "target_key": "k", "proposed_payload": {"a": 1},
            "grounding": [{"field": "a", "document_id": "d", "page": 1, "text_span": "x"}]}


def harness_handler(exc=EXC):
    def h(q):
        if C.TOOL_GET_EXCEPTION + "(" in q:
            return [Row(v=json.dumps(exc) if exc else '{"error": "not_found"}')]
        if C.TOOL_GET_RULE + "(" in q:
            return [Row(v=json.dumps({"rule_id": "CC-02", "version": 4}))]
        if q.startswith(f"SELECT rule_id, version, params FROM {C.CURRENT_RULES}"):
            return [Row(rule_id="CC-02", version=4, params={})]   # pre-check admits (A-34)
        o = owner_rows(q)
        return o if o is not None else []
    return h


def precheck_handler(exc, current, latest=(), parents=(), holders=("pm@navy.mil",),
                     actions=("apply", "reject"), owner_error=False):
    def h(q):
        o = owner_rows(q, holders, actions)
        if o is not None:
            if owner_error:
                raise RuntimeError("PERMISSION_DENIED on role_map")
            return o
        if C.TOOL_GET_EXCEPTION + "(" in q:
            return [Row(v=json.dumps(exc))]
        if q.startswith(f"SELECT rule_id, version, params FROM {C.CURRENT_RULES}"):
            return list(current)
        if q.startswith(f"SELECT version, status, blocked_reason FROM {C.RULE_REGISTER}"):
            return list(latest)
        if q.startswith(f"SELECT exception_id, status FROM {C.EXCEPTIONS}"):
            return list(parents)
        return []
    return h


def sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:16]


# ---- shared helpers (pinned before batch 3 moves them) ----------------------

def test_argument_error():
    """F22: tool arguments are checked against the schema before the call."""
    ae = tools.argument_error
    assert ae("get_rule", {"rule_id": "CC-02"}) is None
    assert ae("get_rule", {"rule_id": "CC-02", "version": None}) is None
    assert ae("get_cip_transactions", {"period_start": "a", "period_end": "b"}) is None
    m = ae("get_cost_capture", {"wbs_id": "w"})
    assert m.startswith("bad arguments for get_cost_capture: missing [") and "unexpected ['wbs_id']" in m
    assert ae("get_rule", {}) == "bad arguments for get_rule: missing ['rule_id']; expected ['rule_id', 'version']"
    assert ae("get_rule", ["CC-02"]) == "arguments for get_rule must be a JSON object"
    assert ae("stage_proposal", dict(GROUNDED, run_id="x", rule_id="y")) is None   # injected keys are dropped, not refused
    assert ae("no_such_tool", {}) is None                                       # unknown tools handled by the caller
    assert ae("get_exception", {"exception_id": "e"}, checker.CHECKER_TOOLS) is None
    assert "missing ['exception_id']" in ae("get_exception", {}, checker.CHECKER_TOOLS)


def test_tool_schemas_match_signatures():
    """F22: a call that passes argument_error must not raise TypeError on binding."""
    import inspect
    for s in tools.TOOL_SCHEMAS + checker.CHECKER_TOOLS:
        f = s["function"]
        sig = inspect.signature(getattr(tools, f["name"])).parameters
        no_default = {n for n, p in sig.items() if p.default is p.empty and n != "run_id"}
        required, props = set(f["parameters"].get("required", [])), set(f["parameters"]["properties"])
        assert props <= set(sig), (f["name"], props - set(sig))
        assert required <= props and no_default <= required, (f["name"], no_default - required)
    fake = FakeSpark(lambda q: [Row(v='{"status": "blocked_no_source"}')])
    with with_spark(fake):   # cost_element omitted: was a TypeError before F22
        out = tools.TOOL_DISPATCH["get_cip_transactions"](period_start="2026-01", period_end="2026-02")
    assert json.loads(out)["status"] == "blocked_no_source" and fake.args[-1] == {"p1": "2026-01", "p2": "2026-02"}


def test_orchestrator_bad_tool_args_returned_to_model():
    """F22 fixed: bad arguments become a tool error; the same model continues."""
    fake = FakeSpark(harness_handler())
    model = ScriptedModel([tool_msg(tc(1, "get_cost_capture", {"wbs_id": "test-wbs-001"})),
                           tool_msg(tc(2, "get_exception", {"exception_id": "exc-1"})), final()])
    with with_spark(fake):
        r = orch.run_exception("exc-1", call=model)
    first = orch._models("agent")[0]
    assert (r["status"], r["error"], r["model"], r["steps"]) == ("completed", None, first, 2), r
    assert {e for e, _ in model.calls} == {first}, "fell through to the fallback model"
    reply = json.loads(model.calls[1][1]["messages"][-1]["content"])
    assert reply["error"].startswith("bad arguments for get_cost_capture")
    assert not any(C.TOOL_GET_COST_CAPTURE + "(" in q for q in fake.queries), "tool was called"
    (_, s1), _ = fake.tool_steps()
    assert "bad arguments" in json.loads(s1["output_json"])["error"]
    [(_, fin)] = fake.finding_steps()
    assert json.loads(fin["output_json"]) == {"kind": "finding", "text": "done", "truncated": False,
                                             "chars": 4}
    [(_, run)] = fake.inserts_with_args(C.AGENT_RUNS)
    assert run["outcome"] == "completed"


def test_checker_bad_tool_args_returned_to_model():
    fake = FakeSpark(proposal_handler({"a": 1}))
    model = ScriptedModel([tool_msg(tc(1, "get_rule", {"id": "CC-02"})), final('{"verdict": "pass"}')])
    with with_spark(fake):
        r = checker.check_proposal("p-1", call=model)
    first = checker._checker_models()[0]
    assert (r["verdict"], r["model"]) == ("pass", first) and {e for e, _ in model.calls} == {first}
    assert "bad arguments for get_rule" in model.calls[1][1]["messages"][-1]["content"]


def test_step_json_single_encoded():
    """agent_steps.output_json holds the tool result as one JSON document."""
    tool_text = json.dumps({"rule_id": "CC-02", "q": "o'b"})
    assert orch._step_json(tool_text) == tool_text                      # JSON text kept as is
    assert json.loads(orch._step_json(tool_text))["rule_id"] == "CC-02"   # parses once to the object
    assert json.loads(orch._step_json({"a": 1})) == {"a": 1}
    assert json.loads(orch._step_json("not json")) == "not json"        # plain text is encoded once
    assert json.loads(orch._step_json('{"error": "not_found"}')) == {"error": "not_found"}
    for big in ("x" * 9000, json.dumps({"t": "\"" * 5000}), {"t": "é\n" * 3000}):
        s = orch._step_json(big)
        d = json.loads(s)
        assert len(s) <= orch.MAX_STEP_JSON and d["truncated"] is True and d["chars"] > orch.MAX_STEP_JSON


def test_orchestrator_step_output_json_is_single_encoded():
    fake = FakeSpark(harness_handler())
    model = ScriptedModel([tool_msg(tc(1, "get_exception", {"exception_id": "exc-1"})),
                           tool_msg(tc(2, "stage_proposal", GROUNDED)), final()])
    with with_spark(fake):
        orch.run_exception("exc-1", call=model)
    (_, a1), (_, a2) = fake.tool_steps()
    assert json.loads(a1["output_json"])["exception_id"] == "exc-1"
    assert json.loads(a2["output_json"])["status"] == "pending"
    # the model's view is unchanged: _clip of the raw result
    assert model.calls[1][1]["messages"][-1]["content"] == orch._clip(json.dumps(EXC))


def test_clip_limits_differ():
    """S1: the two clips are deliberately not the same."""
    big = "x" * 9000
    o, c = orch._clip(big), checker._clip(big)
    assert o == json.dumps(big)[:7000] + '..."(truncated)"'
    assert c == json.dumps(big)[:5000] + "...(truncated)"
    assert orch._clip({"a": 1}) == checker._clip({"a": 1}) == '{"a": 1}'


def test_text_extraction():
    for f in (orch._text, checker._text):
        assert f("hi") == "hi"
        assert f([{"type": "text", "text": "a"}, {"type": "image"}, "junk",
                  {"type": "text", "text": "b"}]) == "ab"
        assert f(None) == "" and f(5) == "5"


def test_model_chains_and_env():
    import os
    keys = tuple(f"AIRCARRIER_{r}_{s}" for r in ("AGENT", "REASONING", "EXTRACTION", "CHECKER")
                 for s in ("MODEL", "FALLBACKS"))
    saved = {k: os.environ.pop(k, None) for k in keys}
    try:
        # Defaults come from seed/models.yaml; no Claude model in any chain.
        assert orch._models() == ["databricks-gpt-5-5", "databricks-gemini-3-8-flash",
                                  "databricks-grok-4-7"]
        assert orch._models("reasoning") == ["databricks-gpt-6-1-sol", "databricks-grok-4-7",
                                             "databricks-gemini-3-8-flash"]
        assert orch._models("extraction") == ["databricks-gpt-6-sol", "databricks-gpt-5-6-sol",
                                              "databricks-gemini-3-8-flash"]
        assert checker._checker_models() == ["databricks-gemini-3-8-flash", "databricks-grok-4-7"]
        assert not any("claude" in m for r in ("agent", "reasoning", "extraction", "checker")
                       for m in orch._models(r))
        # B28.5: the checker leads with a different family from the specialist.
        assert orch._models()[0].split("-")[1] != checker._checker_models()[0].split("-")[1]
        os.environ["AIRCARRIER_AGENT_MODEL"] = "m1"
        os.environ["AIRCARRIER_AGENT_FALLBACKS"] = " m2 , ,m1,m3"
        assert orch._models() == ["m1", "m2", "m3"]
        os.environ["AIRCARRIER_CHECKER_MODEL"] = "c1"
        os.environ["AIRCARRIER_CHECKER_FALLBACKS"] = ""
        assert checker._checker_models() == ["c1"]
    finally:
        for k, v in saved.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v


def test_call_model_request_shape():
    import types
    seen = []

    class FakeClient:
        def __init__(self):
            self.api_client = types.SimpleNamespace(
                do=lambda method, path, body=None: seen.append((method, path, body)) or {"ok": 1})

    fake_sdk = types.ModuleType("databricks.sdk")
    fake_sdk.WorkspaceClient = FakeClient
    saved = sys.modules.get("databricks.sdk")
    sys.modules["databricks.sdk"] = fake_sdk
    try:
        for f in (orch._call_model, checker._call_model):
            assert f("ep-1", {"m": 1}) == {"ok": 1}
    finally:
        if saved is None:
            sys.modules.pop("databricks.sdk", None)
        else:
            sys.modules["databricks.sdk"] = saved
    assert seen == [("POST", "/serving-endpoints/ep-1/invocations", {"m": 1})] * 2


# ---- catalog ----------------------------------------------------------------

def test_catalog_names_pinned():
    vals = {v for k, v in vars(C).items()
            if k.isupper() and not k.startswith("_") and isinstance(v, str)
            and v.startswith(C.STORE_SCHEMA + ".")}
    tails = {v[len(C.STORE_SCHEMA) + 1:] for v in vals}
    assert tails == {
        *("aircarrier_app_" + t for t in (
            "rule_register", "rule_register_audit", "exceptions", "agent_runs",
            "agent_steps", "checker_verdicts", "proposals", "decisions", "documents",
            "model_runs", "rule_evals", "determinations", "metrics", "role_map",
            "authority", "current_rules")),
        *("aircarrier_tool_" + t for t in (
            "get_exception", "get_rule", "get_document_text", "get_cost_capture",
            "get_evm_control_account", "get_cap_ledger", "get_cip_transactions")),
    }, tails


# ---- specialists ------------------------------------------------------------

COMMON = {"get_exception", "get_rule", "get_document_text", "stage_proposal"}
ROSTER = {
    "cost_capture": ("cost_capture_specialist", "specialist/cost_capture@1", "get_cost_capture", "fc5ea5ff16ecc8be"),
    "evm": ("evm_specialist", "specialist/evm@1", "get_evm_control_account", "a8d8e6f663f8c6d3"),
    "cost_cap": ("cost_cap_specialist", "specialist/cost_cap@1", "get_cap_ledger", "f5725b311a1dbfa6"),
    "valuation": ("valuation_specialist", "specialist/valuation@1", "get_cip_transactions", "e5ef8cc41426f082"),
    "cost_model": ("cost_model_specialist", "specialist/cost_model@1", "run_cost_model_scenario", "5ecf41e7382b5112"),
}


def test_roster_allowlists_and_prompts_pinned():
    assert set(sp.SPECIALISTS) == set(ROSTER)
    for area, (name, ver, own_tool, prompt_sha) in ROSTER.items():
        s = sp.get_specialist(area)
        assert (s.name, s.area, s.prompt_version) == (name, area, ver), area
        assert s.tool_allowlist == frozenset(COMMON | {own_tool}), area
        assert sha(s.system_prompt) == prompt_sha, f"{area} prompt text changed"
    assert sha(checker.CHECKER_SYSTEM) == "cb87ffc0e7487af7", "checker prompt text changed"
    assert checker.CHECKER_PROMPT_VERSION == "checker/verify@1"


def test_one_prompt_file_per_agent():
    d = ROOT / "ops" / "harness" / "prompts"
    want = {s.name for s in sp.SPECIALISTS.values()} | {"harness_checker"}
    assert {p.stem for p in d.glob("*.md")} == want
    for name in want:
        assert (d / f"{name}.md").read_text(encoding="utf-8").endswith("\n"), name


def test_unknown_area_raises():
    try:
        sp.get_specialist("nope")
    except KeyError:
        return
    raise AssertionError("expected KeyError")


# ---- tools ------------------------------------------------------------------

def test_tool_registry_shape():
    names = [t["function"]["name"] for t in tools.TOOL_SCHEMAS]
    assert len(names) == 9 and set(names) == set(tools.TOOL_DISPATCH)
    assert {t["function"]["name"] for t in checker.CHECKER_TOOLS} == set(checker.CHECKER_DISPATCH) \
        == {"get_exception", "get_rule", "get_document_text"}


def test_each_read_tool_calls_its_namesake_uc_function():
    calls = {"get_exception": ("e",), "get_rule": ("r", None), "get_document_text": ("d",),
             "get_cost_capture": ("w", "c", "a", "b"), "get_evm_control_account": ("x", "a", "b"),
             "get_cap_ledger": ("a",), "get_cip_transactions": (None, "a", "b")}
    for name, args in calls.items():
        fake = FakeSpark(lambda q: [Row(v="{}")])
        with with_spark(fake):
            getattr(tools, name)(*args)
        [q] = fake.queries
        assert q.startswith(f"SELECT {C.STORE_SCHEMA}.aircarrier_tool_{name}("), (name, q)


def test_call_uc_literals_and_not_found():
    fake = FakeSpark(lambda q: [Row(v=None)])
    with with_spark(fake):
        out = tools.get_rule("R'1", None)
        tools.get_rule("CC-02", 3)
        tools.get_cip_transactions(None, "2026-01", "2026-02")
    assert out == '{"error": "not_found"}'
    assert fake.queries[0] == f"SELECT {C.TOOL_GET_RULE}(:p0, NULL)"
    assert fake.args[0] == {"p0": "R'1"}
    assert fake.queries[1] == f"SELECT {C.TOOL_GET_RULE}(:p0, :p1)"
    assert fake.args[1] == {"p0": "CC-02", "p1": 3}
    assert fake.queries[2].endswith("(NULL, :p1, :p2)")
    assert fake.args[2] == {"p1": "2026-01", "p2": "2026-02"}


def test_stage_proposal_insert_shape():
    """F3 fixed: lineage columns are written from what the orchestrator injects."""
    lineage = {"exception_id": "exc-1", "rule_id": "CC-02", "rule_version": 4,
               "record_ids": ["w1", "w2"]}
    fake = FakeSpark()
    with with_spark(fake):
        r = tools.TOOL_DISPATCH["stage_proposal"](_run_id="run-9", _lineage=lineage, **GROUNDED)
    assert r["status"] == "pending"
    [(q, a)] = fake.inserts_with_args(C.PROPOSALS)
    cols = q.split("VALUES")[0]
    assert (a["run_id"], a["proposal_id"]) == ("run-9", r["proposal_id"]) and "'pending'" in q
    assert "run-9" not in q and r["proposal_id"] not in q
    for present in ("exception_id", "rule_id", "rule_version", "record_ids"):
        assert present in cols, present
    assert (a["exception_id"], a["rule_id"], a["rule_version"]) == ("exc-1", "CC-02", 4)
    assert "ARRAY(:rec0, :rec1)" in q and (a["rec0"], a["rec1"]) == ("w1", "w2")
    # Without injected lineage (direct call) the columns are NULL, not placeholders.
    fake = FakeSpark()
    with with_spark(fake):
        tools.stage_proposal(run_id="r", **GROUNDED)
    [(q, a)] = fake.inserts_with_args(C.PROPOSALS)
    assert a["rule_id"] is None and a["rule_version"] is None and "CAST(:rule_version AS INT), NULL" in q


def test_stage_proposal_ignores_model_supplied_lineage():
    """Invariant 6: the model cannot set run_id or lineage through tool arguments."""
    lineage = {"exception_id": "exc-1", "rule_id": "CC-02", "rule_version": 4, "record_ids": ["w1"]}
    forged = dict(GROUNDED, run_id="evil", exception_id="evil", rule_id="evil",
                  rule_version=99, record_ids=["evil"])
    fake = FakeSpark()
    with with_spark(fake):
        tools.TOOL_DISPATCH["stage_proposal"](_run_id="run-9", _lineage=lineage, **forged)
    [(_, a)] = fake.inserts_with_args(C.PROPOSALS)
    assert "evil" not in json.dumps(a) and 99 not in a.values()
    assert (a["run_id"], a["rule_id"], a["rule_version"], a["rec0"]) == ("run-9", "CC-02", 4, "w1")


def test_run_cost_model_scenario_placeholder():
    """F4 fixed: inputs_vintage, rule_version, assumptions, input_record_ids are stored."""
    lineage = {"exception_id": "exc-1", "rule_id": "CM-02", "rule_version": 1, "record_ids": ["mr-1"]}
    fake = FakeSpark()
    with with_spark(fake):
        r = tools.TOOL_DISPATCH["run_cost_model_scenario"](
            _lineage=lineage, scenario_params={"x": 1},
            inputs_vintage={"IPMDAR": "2026-09-30T00:00:00Z", "CCDR": "2026-06-30"},
            rule_version=1, assumptions=["A1", "A'2"])
    [(q, a)] = fake.inserts_with_args(C.MODEL_RUNS)
    assert r["outputs"]["status"] == "placeholder" and r["warnings"] == []
    assert "'placeholder-v0'" in q and "MAP(:k0, :v0)" in q and (a["k0"], a["v0"]) == ("x", "1")
    assert "MAP(:f0, CAST(:t0 AS TIMESTAMP), :f1, CAST(:t1 AS TIMESTAMP))" in q
    assert (a["f0"], a["t0"], a["f1"], a["t1"]) == ("IPMDAR", "2026-09-30T00:00:00Z", "CCDR", "2026-06-30")
    assert "MAP(:rv_rule, CAST(:rv_version AS INT))" in q and (a["rv_rule"], a["rv_version"]) == ("CM-02", 1)
    assert "ARRAY(:as0, :as1)" in q and (a["as0"], a["as1"]) == ("A1", "A'2") and "A'2" not in q
    assert "ARRAY(:rec0)" in q and a["rec0"] == "mr-1"
    assert "w0" not in a and ":w0" not in q                         # warnings NULL when none


def test_run_cost_model_scenario_bad_inputs_become_warnings():
    """F4: nothing invented. Unusable inputs are left out and listed in warnings."""
    fake = FakeSpark()
    with with_spark(fake):   # direct call: no lineage, legacy string shapes
        r = tools.run_cost_model_scenario(scenario_params={}, inputs_vintage="VINTAGE-Z",
                                          rule_version=7, assumptions="ASSUME-Z")
    [(q, a)] = fake.inserts_with_args(C.MODEL_RUNS)
    assert "inputs_vintage not stored" in r["warnings"][0] and len(r["warnings"]) == 1
    assert "MAP(:f" not in q and ":rv_rule" not in q              # vintage and rule_version NULL
    assert "ARRAY(:as0)" in q and a["as0"] == "ASSUME-Z"          # one string -> one-item list
    assert "ARRAY(:w0)" in q and a["w0"] == r["warnings"][0]
    fake = FakeSpark()
    with with_spark(fake):   # JSON-object string, one bad timestamp, model version differs
        r = tools.TOOL_DISPATCH["run_cost_model_scenario"](
            _lineage={"rule_id": "CM-02", "rule_version": 1, "record_ids": []},
            scenario_params={}, inputs_vintage='{"IPMDAR": "2026-09-30", "GL": "last week", "B": "20260930"}',
            rule_version=3, assumptions=[], rule_id="FORGED")
    [(q, a)] = fake.inserts_with_args(C.MODEL_RUNS)
    assert (a["f0"], a["t0"]) == ("IPMDAR", "2026-09-30") and "f1" not in a
    assert (a["rv_rule"], a["rv_version"]) == ("CM-02", 1) and "FORGED" not in json.dumps(a)
    assert any("'B'" in w for w in r["warnings"])   # basic format: Python parses it, Spark CAST does not
    assert any("'GL'" in w for w in r["warnings"]) and any("rule_version 3 given" in w for w in r["warnings"])
    assert ":as0" not in q and ":rec0" not in q                   # empty lists -> NULL


def test_orchestrator_injects_lineage_into_cost_model():
    fake = FakeSpark(harness_handler({**EXC, "area": "cost_model"}))
    model = ScriptedModel([tool_msg(tc(1, "run_cost_model_scenario", {
        "scenario_params": {}, "inputs_vintage": {"IPMDAR": "2026-09-30"},
        "rule_version": 4, "assumptions": ["a"]})), final()])
    with with_spark(fake):
        r = orch.run_exception("exc-1", call=model)
    assert r["status"] == "completed" and r["error"] is None
    [(_, a)] = fake.inserts_with_args(C.MODEL_RUNS)
    assert (a["rv_rule"], a["rv_version"], a["rec0"]) == ("CC-02", 4, "exc-0")


# ---- orchestrator -----------------------------------------------------------

def test_orchestrator_mock_run_b31_7():
    """B31.7 acceptance + invariant 6. F2 fixed: one agent_runs row, written at the end."""
    fake = FakeSpark(harness_handler())
    model = ScriptedModel([
        tool_msg(tc(1, "get_exception", {"exception_id": "exc-1"})),
        tool_msg(tc(2, "get_rule", {"rule_id": "CC-02", "version": None})),
        tool_msg(tc(3, "stage_proposal", GROUNDED)),
        final()])
    with with_spark(fake):
        r = orch.run_exception("exc-1", call=model)
    assert r["status"] == "completed" and r["error"] is None, r
    assert r["steps"] == 3 and len(r["proposals"]) == 1
    assert r["specialist"] == "cost_capture_specialist"
    assert r["model"] == orch._models("agent")[0]
    offered = {t["function"]["name"] for t in model.calls[0][1]["tools"]}
    assert offered == sp.get_specialist("cost_capture").tool_allowlist
    assert all(r["run_id"] not in json.dumps(b) for _, b in model.calls), "run_id leaked to model"
    [(_, pa)] = fake.inserts_with_args(C.PROPOSALS)
    assert (pa["run_id"], pa["proposal_id"]) == (r["run_id"], r["proposals"][0])
    # F3: proposal lineage is the exception's, as on the agent_steps rows.
    assert (pa["exception_id"], pa["rule_id"], pa["rule_version"], pa["rec0"]) == \
        ("exc-1", "CC-02", 4, "exc-0")
    [(run_q, run_a)] = fake.inserts_with_args(C.AGENT_RUNS)
    assert run_a["run_id"] == r["run_id"] and run_a["outcome"] == "completed"
    assert run_q.count("TIMESTAMP '") == 2   # started_at and ended_at in the one row
    steps = fake.inserts_with_args(C.AGENT_STEPS)
    assert len(steps) == 4   # three tool steps, then the finding (F23)
    assert json.loads(steps[-1][1]["output_json"])["kind"] == "finding"
    assert all("ARRAY(:r0)" in q and a["r0"] == "exc-0" and a["specialist"] == "cost_capture_specialist"
               and a["rule_id"] == "CC-02" and a["rule_version"] == 4 and a["run_id"] == r["run_id"]
               for q, a in steps)
    assert all(f":run_id, {n}, :specialist" in q for n, (q, _) in enumerate(steps, 1))
    assert fake.queries.index(run_q) > max(fake.queries.index(q) for q, _ in steps), \
        "agent_runs row must be written after the steps"


def test_orchestrator_allowlist_refusal():
    fake = FakeSpark(harness_handler())
    model = ScriptedModel([tool_msg(tc(1, "get_cap_ledger", {"as_of": "2026-01-01"})), final()])
    with with_spark(fake):
        r = orch.run_exception("exc-1", call=model)
    assert r["status"] == "completed" and r["steps"] == 1
    last = model.calls[1][1]["messages"][-1]
    assert last["role"] == "tool" and "not in allowlist" in last["content"]
    assert not any(C.TOOL_GET_CAP_LEDGER in q for q in fake.queries)


def test_orchestrator_dry_run():
    """F15 fixed: dry_run writes nothing, not even proposals or model_runs."""
    fake = FakeSpark(harness_handler())
    model = ScriptedModel([
        tool_msg(tc(1, "stage_proposal", GROUNDED)),
        tool_msg(tc(2, "get_rule", {"rule_id": "CC-02", "version": 4})),
        final()])
    with with_spark(fake):
        r = orch.run_exception("exc-1", call=model, dry_run=True)
    assert r["status"] == "completed" and r["steps"] == 2
    assert r["proposals"] == [] and r["dry_run_proposals"] == 1
    assert not [q for q in fake.queries if "INSERT" in q], "dry run wrote"
    tool_reply = json.loads(model.calls[1][1]["messages"][-1]["content"])
    assert tool_reply["status"] == "dry_run" and tool_reply["tool"] == "stage_proposal"
    assert any(C.TOOL_GET_RULE + "(" in q for q in fake.queries), "read tools still run"
    # run_cost_model_scenario (writes model_runs) is skipped too, for a specialist that has it
    spec = sp.get_specialist("cost_model")
    fake = FakeSpark(harness_handler({**EXC, "area": "cost_model"}))
    model = ScriptedModel([tool_msg(tc(1, "run_cost_model_scenario", {
        "scenario_params": {}, "inputs_vintage": "v", "rule_version": 4, "assumptions": "a"})), final()])
    with with_spark(fake):
        r = orch.run_exception("exc-1", call=model, dry_run=True)
    assert "run_cost_model_scenario" in spec.tool_allowlist and r["dry_run_proposals"] == 0
    assert not [q for q in fake.queries if "INSERT" in q]
    # without dry_run the key is absent and the write happens
    fake = FakeSpark(harness_handler())
    with with_spark(fake):
        r = orch.run_exception("exc-1", call=ScriptedModel([tool_msg(tc(1, "stage_proposal", GROUNDED)), final()]))
    assert "dry_run_proposals" not in r and len(fake.inserts(C.PROPOSALS)) == 1


def test_orchestrator_not_found_and_unknown_area():
    fake = FakeSpark(harness_handler(exc=None))
    with with_spark(fake):
        r = orch.run_exception("missing", call=ScriptedModel([]))
    assert r["status"] == "error" and r["error"] == "exception not found"
    assert not fake.inserts(C.AGENT_RUNS)
    fake = FakeSpark(harness_handler(exc={**EXC, "area": "nope"}))
    with with_spark(fake):
        r = orch.run_exception("exc-1", call=ScriptedModel([]))
    assert r["status"] == "error" and "No specialist" in r["error"]


def test_orchestrator_refuses_exception_without_lineage():
    """F7 fixed: no rule_version 1 / ['unknown'] placeholders. Refused before any model call."""
    for broken, name in (({"rule_version": None}, "rule_version"), ({"rule_version": "4"}, "rule_version"),
                         ({"subject_ids": []}, "subject_ids"), ({"subject_ids": None}, "subject_ids"),
                         ({"rule_id": "  "}, "rule_id")):
        fake = FakeSpark(harness_handler({**EXC, **broken}))
        model = ScriptedModel([final()])
        with with_spark(fake):
            r = orch.run_exception("exc-1", call=model)
        assert r["status"] == "error" and name in r["error"], (broken, r)
        assert model.calls == [] and not [q for q in fake.queries if "INSERT" in q], broken
    fake = FakeSpark(harness_handler({k: v for k, v in EXC.items() if k != "rule_version"}))
    with with_spark(fake):
        r = orch.run_exception("exc-1", call=ScriptedModel([final()]))
    assert r["error"] == "exception lacks lineage: rule_version"


def test_orchestrator_binds_exception_id():
    """F1 fixed: the exception id is bound in every orchestrator statement."""
    fake = FakeSpark(harness_handler(exc=None))
    with with_spark(fake):
        orch.run_exception("a'b", call=ScriptedModel([]))
    assert fake.queries[0] == f"SELECT {C.TOOL_GET_EXCEPTION}(:exception_id)"
    assert fake.args[0] == {"exception_id": "a'b"}
    fake = FakeSpark(harness_handler())
    model = ScriptedModel([tool_msg(tc(1, "get_exception", {"exception_id": "exc-1"})), final()])
    with with_spark(fake):
        orch.run_exception("a'b", call=model)
    writes = fake.inserts_with_args(C.AGENT_RUNS) + fake.inserts_with_args(C.AGENT_STEPS)
    # run, tool step, finding (F23)
    assert len(writes) == 3 and all("a'b" not in q and "'{" not in q for q, _ in writes)
    assert [a["exception_id"] for _, a in fake.inserts_with_args(C.AGENT_RUNS)] == ["a'b"]


def test_orchestrator_records_finding_f23():
    """F23: the final answer is stored, cited, last, and only when there is one."""
    # A-33: a finding far longer than MAX_STEP_JSON is stored whole, with its tail.
    long_text = "x" * (orch.MAX_STEP_JSON * 3) + " CONCLUSION: cannot resolve."
    fake = FakeSpark(harness_handler())
    model = ScriptedModel([tool_msg(tc(1, "get_exception", {"exception_id": "exc-1"})),
                           final(long_text)])
    with with_spark(fake):
        r = orch.run_exception("exc-1", call=model)
    steps = fake.inserts_with_args(C.AGENT_STEPS)
    q, a = steps[-1]
    out = json.loads(a["output_json"])
    assert out["kind"] == "finding" and out["truncated"] is False
    assert out["text"] == long_text and out["chars"] == len(long_text)
    assert out["text"].endswith("CONCLUSION: cannot resolve.")
    assert (a["rule_id"], a["rule_version"], a["r0"], a["run_id"]) == ("CC-02", 4, "exc-0", r["run_id"])
    assert f":run_id, {len(steps)}, :specialist" in q and long_text not in q   # bound, not pasted
    assert r["steps"] == 1                                                      # tool steps only
    for script in ([final("")], [final("   ")]):                                # nothing to record
        fake = FakeSpark(harness_handler())
        with with_spark(fake):
            orch.run_exception("exc-1", call=ScriptedModel(script))
        assert fake.finding_steps() == []
    fake = FakeSpark(harness_handler())                                         # dry run writes nothing
    with with_spark(fake):
        orch.run_exception("exc-1", call=ScriptedModel([final("a finding")]), dry_run=True)
    assert fake.inserts_with_args(C.AGENT_STEPS) == []


def test_orchestrator_model_fallback_and_all_down():
    first, second = orch._models("agent")[:2]
    fake = FakeSpark(harness_handler())
    with with_spark(fake):
        r = orch.run_exception("exc-1", call=ScriptedModel([final()], fail={first}))
    assert r["status"] == "completed" and r["model"] == second
    fake = FakeSpark(harness_handler())
    with with_spark(fake):
        r = orch.run_exception("exc-1", call=ScriptedModel([], fail=set(orch._models("agent"))))
    assert r["status"] == "error" and "endpoint down" in r["error"] and r["model"] is None
    _, end_args = fake.inserts_with_args(C.AGENT_RUNS)[-1]
    assert end_args["outcome"].startswith("error: ")   # CHARACTERIZES N5 outcome vocabulary


def test_orchestrator_step_limit_forces_answer():
    fake = FakeSpark(harness_handler())
    script = [tool_msg(tc(i, "get_rule", {"rule_id": "CC-02"})) for i in range(orch.MAX_STEPS)]
    model = ScriptedModel(script + [final()])
    with with_spark(fake):
        r = orch.run_exception("exc-1", call=model)
    assert r["status"] == "completed" and r["steps"] == orch.MAX_STEPS == 8
    last_body = model.calls[-1][1]
    assert "tools" not in last_body
    assert last_body["messages"][-1] == {"role": "user", "content": "Answer now from what you have."}


# ---- checker ----------------------------------------------------------------

LINEAGE = {"exception_id": "exc-1", "rule_id": "CC-02", "rule_version": 4}   # matches EXC


def proposal_handler(payload, grounded_fields=("a",), exists=True, lineage=LINEAGE, exc=EXC):
    row = Row(proposal_id="p-1", run_id="run-1", target_table="t", target_key="k",
              proposed_payload=json.dumps(payload),
              grounding=[Row(field=f, document_id="d", page=1, text_span="x")
                         for f in grounded_fields],
              schema_validation=None, status="pending", **lineage)

    def h(q):
        if f"FROM {C.PROPOSALS}" in q and q.lstrip().startswith("SELECT"):
            return [row] if exists else []
        return harness_handler(exc)(q)
    return h


def test_checker_rule_match_f21():
    """F21 fixed: the proposal's rule_id/rule_version must match its exception. No model call."""
    none = {"exception_id": None, "rule_id": None, "rule_version": None}
    cases = [
        (dict(LINEAGE, rule_version=3), EXC, "does not match exception exc-1 rule CC-02 v4"),
        (dict(LINEAGE, rule_id="CC-01"), EXC, "Proposal rule CC-01 v4 does not match"),
        (none, EXC, "lacks lineage"),
        (dict(LINEAGE, rule_version=None), EXC, "lacks lineage"),
        (LINEAGE, None, "Exception exc-1 not found"),
    ]
    for lineage, exc, reason in cases:
        fake = FakeSpark(proposal_handler({"a": 1}, lineage=lineage, exc=exc))
        model = ScriptedModel([final('{"verdict": "pass"}')])
        with with_spark(fake):
            r = checker.check_proposal("p-1", call=model)
        assert r["verdict"] == "fail" and reason in r["block_reason"], (lineage, r)
        assert model.calls == [] and r["model"] is None
        [(_, a)] = fake.inserts_with_args(C.CHECKER_VERDICTS)
        assert a["verdict"] == "fail" and reason in a["notes"]
    # matching lineage: the exception is re-read with the proposal's exception_id, bound
    fake = FakeSpark(proposal_handler({"a": 1}))
    with with_spark(fake):
        r = checker.check_proposal("p-1", call=ScriptedModel([final('{"verdict": "pass"}')]))
    assert r["verdict"] == "pass"
    assert {"p0": "exc-1"} in fake.args and not any("'exc-1'" in q for q in fake.queries)
    # dry run: same verdict, nothing written
    fake = FakeSpark(proposal_handler({"a": 1}, lineage=none))
    with with_spark(fake):
        r = checker.check_proposal("p-1", call=ScriptedModel([]), dry_run=True)
    assert r["verdict"] == "fail" and not fake.inserts(C.CHECKER_VERDICTS)


def test_checker_ungrounded_fails_without_model():
    fake = FakeSpark(proposal_handler({"a": 1, "b": 2}))
    model = ScriptedModel([])
    with with_spark(fake):
        r = checker.check_proposal("p-1", call=model)
    assert r["verdict"] == "fail" and "['b']" in r["block_reason"] and r["model"] is None
    assert model.calls == []
    [(q, a)] = fake.inserts_with_args(C.CHECKER_VERDICTS)
    assert ":run_id, 1, :verdict" in q and (a["run_id"], a["verdict"], a["model"]) == ("run-1", "fail", None)
    assert fake.args[0] == {"proposal_id": "p-1"} and "'p-1'" not in fake.queries[0]


def test_checker_pass_path():
    """status may be ungrounded. F5 fixed: proposal_id recorded in checks."""
    fake = FakeSpark(proposal_handler({"a": 1, "status": "x"}))
    model = ScriptedModel([
        tool_msg(tc(1, "get_exception", {"exception_id": "exc-1"})),
        tool_msg(tc(2, "stage_proposal", GROUNDED)),
        final('{"verdict": "pass", "block_reason": null, "notes": "ok"}')])
    with with_spark(fake):
        r = checker.check_proposal("p-1", call=model)
    assert r["verdict"] == "pass" and r["block_reason"] is None
    assert r["model"] == checker._checker_models()[0]
    assert "checker cannot use tool" in model.calls[2][1]["messages"][-1]["content"]
    assert not fake.inserts(C.PROPOSALS)
    [(q, a)] = fake.inserts_with_args(C.CHECKER_VERDICTS)
    assert (a["run_id"], a["verdict"], a["model"]) == ("run-1", "pass", checker._checker_models()[0])
    assert a["proposal_id"] == "p-1" and "p-1" not in q and "'harness_checker'" in q
    assert "'check_name','proposal','expected',:proposal_id" in q
    assert "'actual',:actual,'result',:verdict" in q and a["actual"] == "pass"


def test_checker_all_models_down():
    """F6 fixed: returns 'error', but the row stores 'fail' (verdict_enum) with actual 'error'."""
    fake = FakeSpark(proposal_handler({"a": 1}))
    with with_spark(fake):
        r = checker.check_proposal("p-1", call=ScriptedModel([], fail=set(checker._checker_models())))
    assert r["verdict"] == "error" and "endpoint down" in r["block_reason"]
    [(_, a)] = fake.inserts_with_args(C.CHECKER_VERDICTS)
    assert (a["verdict"], a["actual"]) == ("fail", "error") and "endpoint down" in a["notes"]
    assert a["verdict"] in ("pass", "pass_with_exception", "fail")


def test_checker_step_seq_numbers_verdicts_per_run():
    """F5 fixed: step_seq is max(step_seq) + 1 for the run, read with run_id bound."""
    base = proposal_handler({"a": 1})
    for existing, expected in ((None, 1), (2, 3)):
        def h(q, existing=existing):
            if "coalesce(max(step_seq), 0) + 1" in q:
                return [] if existing is None else [Row(v=existing + 1)]
            return base(q)
        fake = FakeSpark(h)
        with with_spark(fake):
            checker.check_proposal("p-1", call=ScriptedModel([final('{"verdict": "pass"}')]))
        [(q, _)] = fake.inserts_with_args(C.CHECKER_VERDICTS)
        assert f":run_id, {expected}, :verdict" in q, (existing, q)
        i = next(i for i, s in enumerate(fake.queries) if "max(step_seq)" in s)
        assert fake.args[i] == {"run_id": "run-1"} and "run-1" not in fake.queries[i]


def test_checker_proposal_not_found():
    fake = FakeSpark(proposal_handler({}, exists=False))
    with with_spark(fake):
        r = checker.check_proposal("p-x", call=ScriptedModel([]))
    assert r["verdict"] == "error" and r["block_reason"] == "proposal not found"
    assert not fake.inserts(C.CHECKER_VERDICTS)


def test_parse_verdict():
    pv = checker._parse_verdict
    assert pv('x {"verdict": "PASS", "block_reason": null} y') == ("pass", None)
    assert pv('{"verdict": "maybe", "block_reason": "r"}') == ("fail", "r")
    assert pv("verdict: pass") == ("pass", None)
    v, why = pv("no idea")
    assert v == "fail" and why.startswith("Could not parse")


# ---- evaluate ---------------------------------------------------------------

def test_bind():
    s, a = ev._bind("SELECT * FROM {EXCEPTIONS} WHERE a = :p AND b = :q", {"p": "x'y", "q": 1})
    assert s == f"SELECT * FROM {C.EXCEPTIONS} WHERE a = :p AND b = :q"
    assert a == {"p": "x'y", "q": "1"}
    # F16 gone with F18: Spark binds whole marker names, so :a no longer corrupts :ab.
    assert ev._bind(":a :ab", {"a": "1"}) == (":a :ab", {"a": "1"})
    assert ev._bind("SELECT 1", None) == ("SELECT 1", {})


def rule_row(**kw):
    base = {"rule_id": "CC-02", "version": 4, "area": "cost_capture", "owner_role": "PMS379",
                "owner_office": "PEO Carriers", "required_action": "Escalate",
                "expression_sql": "SELECT e.exception_id, e.dollar_amount FROM {EXCEPTIONS} e WHERE x = :p",
                "params": {"p": "v"}}
    base.update(kw)
    return Row(**base)


def eval_handler(rule, hits=None, boom=False):
    def h(q):
        if q.startswith(f"SELECT * FROM {C.CURRENT_RULES}"):
            return [rule]
        if q.startswith(f"SELECT rule_id, params FROM {C.CURRENT_RULES}"):
            return [rule, Row(rule_id="CC-01", params={})]   # source rule running (A-29)
        if "SELECT e.exception_id" in q:
            if boom:
                raise RuntimeError("bad sql")
            return hits or []
        return []
    return h


def test_evaluate_writes_exception_and_summary():
    fake = FakeSpark(eval_handler(rule_row(), hits=[Row(exception_id="exc-0", dollar_amount=12.5)]))
    with with_spark(fake):
        out = ev.evaluate(trigger="manual", triggered_by="t", rule_ids=["CC-02"])
    assert "rule_id IN (:r0)" in fake.queries[0] and fake.args[0] == {"r0": "CC-02"}
    assert out["rules_evaluated"] == [{"rule_id": "CC-02", "version": 4, "rows": 1,
                                       "status": "ok", "error": None}]
    [(q, a)] = fake.inserts_with_args(C.EXCEPTIONS)
    assert ":rule_id, 4" in q and "ARRAY(:s0)" in q and "CAST(:dollar_amount AS DECIMAL(20,2))" in q
    assert (a["rule_id"], a["s0"], a["dollar_amount"], a["eval_id"]) == ("CC-02", "exc-0", "12.5",
                                                                           out["eval_id"])
    assert a["subject_type"] == "reconciliation_item" and "'open'" in q
    assert (a["owner_role"], a["area"]) == ("PMS379", "cost_capture")
    [(s, sa)] = fake.inserts_with_args(C.RULE_EVALS)
    assert "named_struct('rule_id',:rid0,'version',4" in s and "'status',:st0" in s
    assert (sa["rid0"], sa["st0"], sa["eval_id"], sa["trigger"], sa["triggered_by"]) == \
        ("CC-02", "ok", out["eval_id"], "manual", "t")


def test_evaluate_drops_rows_without_owner_office():
    fake = FakeSpark(eval_handler(rule_row(owner_office="  "), hits=[Row(exception_id="exc-0")]))
    with with_spark(fake):
        out = ev.evaluate()
    assert out["rules_evaluated"][0]["rows"] == 0 and not fake.inserts(C.EXCEPTIONS)


def test_evaluate_rule_error_still_summarised():
    fake = FakeSpark(eval_handler(rule_row(), boom=True))
    with with_spark(fake):
        out = ev.evaluate()
    r = out["rules_evaluated"][0]
    assert r["status"] == "error" and "bad sql" in r["error"]
    assert len(fake.inserts(C.RULE_EVALS)) == 1


def test_evaluate_skips_already_open_exceptions():
    """F19: one open exception per (rule_id, subject set), any version, any order."""
    hits = [Row(subject_ids=["b", "a"]), Row(subject_ids=["a", "b"]),
            Row(subject_ids=["c"]), Row(subject_ids=["d"])]
    base = eval_handler(rule_row(expression_sql="SELECT e.exception_id FROM {EXCEPTIONS} e"),
                        hits=hits)

    def h(q):
        if q.startswith("SELECT subject_ids FROM"):
            return [Row(subject_ids=["c"]), Row(subject_ids=None)]   # 'c' already open
        return base(q)
    fake = FakeSpark(h)
    with with_spark(fake):
        out = ev.evaluate()
    [lookup] = [(q, a) for q, a in zip(fake.queries, fake.args) if q.startswith("SELECT subject_ids")]
    assert f"FROM {C.EXCEPTIONS}" in lookup[0] and "status = 'open'" in lookup[0]
    assert lookup[1] == {"rule_id": "CC-02"}
    ins = fake.inserts_with_args(C.EXCEPTIONS)
    assert out["rules_evaluated"][0]["rows"] == 2 and len(ins) == 2
    assert (ins[0][1]["s0"], ins[0][1]["s1"]) == ("b", "a")   # stored order unchanged
    assert ins[1][1]["s0"] == "d" and "s1" not in ins[1][1]


def test_evaluate_no_lookup_without_hits():
    fake = FakeSpark(eval_handler(rule_row(), hits=[]))
    with with_spark(fake):
        ev.evaluate()
    assert not [q for q in fake.queries if q.startswith("SELECT subject_ids")]


def test_evaluate_derived_rule_names_parent_a28():
    """A-28: a CC-02 hit names its CC-01 parent exception, not the parent's WBS subjects."""
    rule = rule_row(version=5, expression_sql=(
        "SELECT e.exception_id AS parent_exception_id, e.dollar_amount FROM {EXCEPTIONS} e "
        "WHERE e.rule_id = :source_rule"), params={"source_rule": "CC-01"})
    fake = FakeSpark(eval_handler(rule, hits=[Row(parent_exception_id="exc-parent",
                                                  dollar_amount=6000000.0)]))
    with with_spark(fake):
        out = ev.evaluate()
    [(q, a)] = fake.inserts_with_args(C.EXCEPTIONS)
    assert out["rules_evaluated"][0]["rows"] == 1
    assert a["s0"] == "exc-parent" and "s1" not in a and "ARRAY(:s0)" in q
    assert a["subject_type"] == "exception"
    # a dry run reports the same subject (A-4 preview path)
    fake = FakeSpark(eval_handler(rule, hits=[Row(parent_exception_id="exc-parent")]))
    with with_spark(fake):
        out = ev.evaluate(dry_run=True)
    assert out["rules_evaluated"][0]["hits"] == [
        {"subject_ids": ["exc-parent"], "dollar_amount": None, "subject_type": "exception",
         "window_closes_at": None}]


def test_cc02_v5_deploy_sql_a28():
    """The v5 expression returns parent_exception_id and no subject_ids column."""
    sql = (ROOT / "deploy" / "rule_cc02_v5.sql").read_text()
    expr = sql.split("'SELECT ", 1)[1].split("',", 1)[0]
    assert expr.startswith("e.exception_id AS parent_exception_id")
    assert "subject_ids" not in expr and "{EXCEPTIONS}" in expr
    assert ":source_rule" in expr and ":status_filter" in expr and ":escalation_days" in expr
    assert "x.version = 5" in sql and "a.version = 5" in sql   # idempotent


def test_cc02_v6_no_inherited_dollars_a28():
    """v6 returns only the parent id; evaluate writes dollar_amount NULL."""
    sql = (ROOT / "deploy" / "rule_cc02_v6.sql").read_text()
    expr = sql.split("'SELECT ", 1)[1].split("',", 1)[0]
    assert expr.startswith("e.exception_id AS parent_exception_id FROM {EXCEPTIONS} e WHERE")
    assert "dollar" not in expr and "subject_ids" not in expr
    code = "\n".join(l for l in sql.splitlines() if not l.lstrip().startswith("--"))
    assert "UPDATE" not in code.upper() and "x.version = 6" in code
    assert "'CC-02', 5, 'retire'" in code and "a.event = 'retire'" in code
    rule = rule_row(version=6, expression_sql="SELECT e.exception_id AS parent_exception_id "
                                                "FROM {EXCEPTIONS} e WHERE x = :p")
    fake = FakeSpark(eval_handler(rule, hits=[Row(parent_exception_id="exc-parent")]))
    with with_spark(fake):
        ev.evaluate()
    [(q, a)] = fake.inserts_with_args(C.EXCEPTIONS)
    assert a["dollar_amount"] is None and "CAST(:dollar_amount" not in q and "NULL," in q
    assert (a["s0"], a["subject_type"]) == ("exc-parent", "exception")


def _gate_handler(rule, current, latest, hits):
    def h(q):
        if q.startswith(f"SELECT * FROM {C.CURRENT_RULES}"):
            return [rule]
        if q.startswith(f"SELECT rule_id, params FROM {C.CURRENT_RULES}"):
            return current
        if q.startswith(f"SELECT version, status, blocked_reason FROM {C.RULE_REGISTER}"):
            return latest
        if "SELECT e.exception_id" in q:
            return hits
        return []
    return h


def test_derived_rule_skipped_while_source_inactive_a29():
    """A-29: CC-02 does not run, write or detect while CC-01 is not current."""
    rule = rule_row(version=6, params={"source_rule": "CC-01", "status_filter": "open"})
    cur = [Row(rule_id="CC-02", params={"source_rule": "CC-01"})]
    latest = [Row(version=1, status="blocked_no_source", blocked_reason="no ledger feed")]
    for dry in (False, True):
        fake = FakeSpark(_gate_handler(rule, cur, latest, [Row(parent_exception_id="p")]))
        with with_spark(fake):
            out = ev.evaluate(rule_ids=["CC-02"], dry_run=dry)
        [r] = out["rules_evaluated"]
        assert (r["status"], r["rows"]) == ("skipped_parent_inactive", 0)
        assert "source rule CC-01 has no version in effect (latest v1, blocked_no_source: no ledger feed)" in r["error"]
        assert not any("SELECT e.exception_id" in q for q in fake.queries)   # never ran
        assert fake.inserts_with_args(C.EXCEPTIONS) == []
        if dry:
            assert r["hits"] == [] and fake.inserts_with_args(C.RULE_EVALS) == []
        else:
            [(_s, sa)] = fake.inserts_with_args(C.RULE_EVALS)        # the skip is recorded
            assert "skipped_parent_inactive" in sa.values()
    # source current: runs as before
    cur2 = cur + [Row(rule_id="CC-01", params={"t": "1"})]
    fake = FakeSpark(_gate_handler(rule, cur2, latest, [Row(parent_exception_id="p")]))
    with with_spark(fake):
        [r] = ev.evaluate(rule_ids=["CC-02"])["rules_evaluated"]
    assert (r["status"], r["rows"]) == ("ok", 1)
    # source absent from the register, and a loop
    fake = FakeSpark(_gate_handler(rule, cur, [], []))
    with with_spark(fake):
        [r] = ev.evaluate(rule_ids=["CC-02"])["rules_evaluated"]
    assert "CC-01 is not in the rule register" in r["error"]
    loop = cur + [Row(rule_id="CC-01", params={"source_rule": "CC-02"})]
    fake = FakeSpark(_gate_handler(rule, loop, latest, []))
    with with_spark(fake):
        [r] = ev.evaluate(rule_ids=["CC-02"])["rules_evaluated"]
    assert r["status"] == "skipped_parent_inactive" and "loops back to CC-02" in r["error"]


def test_window_from_rule_window_days_a31():
    """A-31: window_closes_at = detected_at + params.window_days; unset stays NULL."""
    import re as _re
    from datetime import datetime as _dt
    rule = rule_row(params={"p": "v", "window_days": "45"})
    fake = FakeSpark(eval_handler(rule, hits=[Row(exception_id="exc-0", dollar_amount=1.0)]))
    with with_spark(fake):
        ev.evaluate()
    [(q, _args)] = fake.inserts_with_args(C.EXCEPTIONS)
    det, win = _re.findall(r"TIMESTAMP '([^']+)'", q)
    assert (_dt.fromisoformat(win) - _dt.fromisoformat(det)).days == 45
    detect_q = [x for x, xa in zip(fake.queries, fake.args) if "SELECT e.exception_id" in x]
    assert detect_q and all("window_days" not in (xa or {}) for x, xa in zip(fake.queries, fake.args)
                            if "SELECT e.exception_id" in x)   # not a detection param
    # unset -> NULL, as before
    fake = FakeSpark(eval_handler(rule_row(), hits=[Row(exception_id="exc-0", dollar_amount=1.0)]))
    with with_spark(fake):
        ev.evaluate()
    [(q, _a)] = fake.inserts_with_args(C.EXCEPTIONS)
    assert len(_re.findall(r"TIMESTAMP '", q)) == 1 and "NULL, 'open'" in q
    # dry run reports it
    fake = FakeSpark(eval_handler(rule, hits=[Row(exception_id="exc-0")]))
    with with_spark(fake):
        [r] = ev.evaluate(dry_run=True)["rules_evaluated"]
    assert r["hits"][0]["window_closes_at"]
    # a bad value fails the rule and writes nothing
    for bad in ("0", "-3", "45.5", "soon"):
        fake = FakeSpark(eval_handler(rule_row(params={"window_days": bad}),
                                      hits=[Row(exception_id="exc-0")]))
        with with_spark(fake):
            [r] = ev.evaluate()["rules_evaluated"]
        assert r["status"] == "error" and "window_days" in r["error"]
        assert fake.inserts_with_args(C.EXCEPTIONS) == []


def test_precheck_blocks_without_model_a34():
    """A-34: a refused item gets no model call, no steps, one outcome row."""
    cur = [Row(rule_id="CC-02", version=6, params={"source_rule": "CC-01"})]
    latest = [Row(version=1, status="blocked_no_source", blocked_reason="no feeds")]
    case = dict(EXC, exception_id="5657", rule_version=4, status="void_test_data",
                subject_ids=["test-wbs-001"], subject_type="reconciliation_item")
    model = ScriptedModel([])
    fake = FakeSpark(precheck_handler(case, cur, latest))
    with with_spark(fake):
        out = orch.run_exception("5657", call=model)
    assert out["status"] == "precheck_blocked" and out["lane"] == "System"
    assert model.calls == [] and fake.inserts(C.AGENT_STEPS) == [] and out["steps"] == 0
    [(_q, a)] = fake.inserts_with_args(C.AGENT_RUNS)
    assert a["outcome"].startswith("precheck_blocked: System: open: status is void_test_data")
    for part in ("G-a not test: test data: subject test-wbs-001",
                 "G-b rule live: rule CC-02 v4 is not the version in effect (v6)",
                 "G-c parent rule live: source rule CC-01 has no version in effect"):
        assert part in a["outcome"]
    # dry run: same answer, nothing written
    fake = FakeSpark(precheck_handler(case, cur, latest))
    with with_spark(fake):
        out = orch.run_exception("5657", call=model, dry_run=True)
    assert out["status"] == "precheck_blocked" and fake.inserts(C.AGENT_RUNS) == []
    # open, current version, but parent rule blocked -> Unblock
    live = dict(EXC, rule_version=6, subject_type="exception", subject_ids=["p1"])
    fake = FakeSpark(precheck_handler(live, cur, latest, [Row(exception_id="p1", status="open")]))
    with with_spark(fake):
        out = orch.run_exception("exc-1", call=model)
    assert (out["status"], out["lane"]) == ("precheck_blocked", "Unblock")
    assert out["precheck"]["reasons"] == [
        ("G-c parent rule live: source rule CC-01 has no version in effect (latest v1, "
        "blocked_no_source: no feeds); CC-02 escalates CC-01 exceptions, so it does not "
        "run until CC-01 does")]
    # parent rule live, parent exception closed or missing -> System
    cur2 = cur + [Row(rule_id="CC-01", version=1, params={})]
    for parents, text in (([Row(exception_id="p1", status="void_test_data")], "p1 is void_test_data"),
                          ([], "p1 not found")):
        fake = FakeSpark(precheck_handler(live, cur2, latest, parents))
        with with_spark(fake):
            out = orch.run_exception("exc-1", call=model)
        assert out["lane"] == "System" and text in out["precheck"]["reasons"][0]
    assert model.calls == []


def test_precheck_owner_g_e_a34():
    """G-e: owner_role set, holds apply in authority, assigned in role_map now."""
    cur = [Row(rule_id="CC-02", version=4, params={})]
    model = ScriptedModel([])
    cases = [
        (dict(EXC, owner_role=None), {}, "G-e owner: exception has no owner_role"),
        (EXC, {"holders": ()}, "G-e owner: no one holds role PMS379 in role_map now"),
        (dict(EXC, owner_role="AUDITOR"), {"actions": ()},
         "G-e owner: role AUDITOR holds no apply on proposals in authority"),
        (dict(EXC, owner_role="DFAS"), {"actions": ("reject",), "holders": ()},
         ("G-e owner: role DFAS holds no apply on proposals in authority; "
         "no one holds role DFAS in role_map now")),
        (EXC, {"owner_error": True},
         "G-e owner: could not read role_map/authority: RuntimeError: PERMISSION_DENIED"),
    ]
    for exc, kw, want in cases:
        fake = FakeSpark(precheck_handler(exc, cur, **kw))
        with with_spark(fake):
            out = orch.run_exception("exc-1", call=model)
        assert (out["status"], out["lane"]) == ("precheck_blocked", "System"), want
        assert out["precheck"]["reasons"][0].startswith(want), out["precheck"]["reasons"]
        if kw.get("holders") is not None or kw.get("actions") is not None:
            role_q = [a for q, a in zip(fake.queries, fake.args) if "FROM " + C.ROLE_MAP in q]
            assert role_q and role_q[0] == {"role": exc["owner_role"]}   # bound, not pasted
    assert model.calls == []
    # a group assignment counts as an owner
    fake = FakeSpark(precheck_handler(EXC, cur, holders=("pms379-fm-group",)))
    with with_spark(fake):
        pc = orch._precheck(fake, EXC)
    assert pc["admit"] and next(c for c in pc["checks"] if c["gate"] == "G-e owner")["ok"]


def test_precheck_admits_and_can_be_bypassed_a34():
    """An item that passes runs as before; G-f is reported, not blocking; precheck=False skips."""
    model = ScriptedModel([final("nothing to do")])
    fake = FakeSpark(harness_handler())
    with with_spark(fake):
        out = orch.run_exception("exc-1", call=model)
    assert out["status"] == "completed" and len(model.calls) == 1
    assert out["precheck"]["admit"] and out["precheck"]["lane"] == "Decide"
    [g] = [c for c in out["precheck"]["checks"] if c["gate"] == "G-f window"]
    assert not g["ok"] and g["blocking"] is False
    case = dict(EXC, status="void_test_data")
    model = ScriptedModel([final("looked anyway")])
    fake = FakeSpark(precheck_handler(case, []))
    with with_spark(fake):
        out = orch.run_exception("exc-1", call=model, precheck=False)
    assert out["status"] == "completed" and out["precheck"] is None and len(model.calls) == 1
    assert not any("SELECT rule_id, version, params" in q for q in fake.queries)


def test_cc02_retire_sql_a30():
    """Retirement is an audit insert, never an UPDATE of the insert-only register."""
    sql = (ROOT / "deploy" / "rule_cc02_retire_v1_v4.sql").read_text()
    code = "\n".join(l for l in sql.splitlines() if not l.lstrip().startswith("--"))
    assert "UPDATE" not in code.upper() and "DELETE" not in code.upper()
    assert "INSERT INTO ${S}.aircarrier_app_rule_register_audit" in code
    assert "'retire'" in code and "BETWEEN 1 AND 4" in code
    assert "n.version = 5" in code and "a.event = 'retire'" in code   # needs v5; idempotent


def test_evaluate_helpers():
    # A-28: parent_exception_id wins over subject_ids and exception_id
    assert ev._extract_subject_ids({"parent_exception_id": "p1", "subject_ids": ["w1"],
                                    "exception_id": "e1"}) == ["p1"]
    assert ev._extract_subject_ids({"subject_ids": ["w1"], "exception_id": "e1"}) == ["w1"]
    assert ev._subject_type("CC-02", {"parent_exception_id": "p1"}) == "exception"
    assert ev._subject_type("CC-02", {"exception_id": "e1"}) == "reconciliation_item"
    assert ev._extract_subject_ids({"model_run_id": "m1", "x": "y"}) == ["m1"]
    assert ev._extract_subject_ids({"subject_ids": ["a", None, "b"]}) == ["a", "b"]
    assert ev._extract_subject_ids({"foo": "bar", "n": 3}) == ["bar"]
    assert ev._extract_dollar({"amount": "5"}) == "5.0" and ev._extract_dollar({}) is None
    assert [ev._infer_subject_type(r) for r in ("CC-02", "EV-01", "CAP-01", "AV-06", "CM-01", "ZZ")] \
        == ["reconciliation_item", "control_account", "cost_cap_item", "valuation_item",
            "model_run", "unknown"]


# ---- SQL string literals (batch 3b tests, flipped by the F18 fix) ----------
# Each test feeds hostile text through one write path and checks the value is
# bound as a parameter marker, exactly as given, and never appears in the SQL
# text. The LIVE tests run the generated VALUES through real Spark.

Q = "o'b"
HOSTILE = {"apos": Q, "dq": 'say "hi"', "bs": "C:\\x\\", "nl": "a\nb"}


def _bound(q, args):
    assert Q not in q and "o''b" not in q, q
    return args


def test_literals_stage_proposal():
    fake = FakeSpark()
    with with_spark(fake):
        tools.stage_proposal(run_id="r", target_table=Q, target_key=Q,
                             proposed_payload=HOSTILE,
                             grounding=[{"field": "n", "document_id": Q, "page": 1,
                                         "text_span": Q}],
                             schema_validation=Q)
    [(q, a)] = fake.inserts_with_args(C.PROPOSALS)
    a = _bound(q, a)
    assert a["target_table"] == a["target_key"] == a["schema_validation"] == Q
    assert json.loads(a["proposed_payload"]) == HOSTILE
    assert json.loads(a["grounding"])[0]["document_id"] == Q


def test_literals_run_cost_model_scenario():
    fake = FakeSpark()
    with with_spark(fake):
        tools.run_cost_model_scenario(scenario_params={Q: Q}, inputs_vintage="v",
                                      rule_version=1, assumptions="a")
    [(q, a)] = fake.inserts_with_args(C.MODEL_RUNS)
    a = _bound(q, a)
    assert "MAP(:k0, :v0)" in q and a["k0"] == a["v0"] == Q
    assert json.loads(a["outputs"])["scenario_params"] == {Q: Q}


def test_literals_evaluate_error_summary():
    def h(q):
        if q.startswith(f"SELECT * FROM {C.CURRENT_RULES}"):
            return [rule_row(owner_office=Q, required_action=Q)]
        if "SELECT e.exception_id" in q:
            return [Row(exception_id="exc-0")]
        return []

    def boom(q):
        if "SELECT e.exception_id" in q:
            raise RuntimeError(f"near {Q}")
        return h(q)
    fake = FakeSpark(h)
    with with_spark(fake):
        ev.evaluate()
    [(q, a)] = fake.inserts_with_args(C.EXCEPTIONS)
    a = _bound(q, a)
    assert (a["owner_office"], a["required_action"]) == (Q, Q)
    fake = FakeSpark(boom)
    with with_spark(fake):
        ev.evaluate()
    [(s, a)] = fake.inserts_with_args(C.RULE_EVALS)
    assert "'error',:err0)" in s and _bound(s, a)["err0"] == f"near {Q}"


def test_literals_orchestrator_steps_and_outcome():
    exc = dict(EXC, subject_ids=[Q])
    fake = FakeSpark(harness_handler(exc))
    model = ScriptedModel([tool_msg(tc(1, "get_exception", {"exception_id": "exc-1"})),
                           final()])
    with with_spark(fake):
        orch.run_exception("exc-1", call=model)
    [(step, a)] = fake.tool_steps()
    a = _bound(step, a)
    assert "ARRAY(:r0)" in step and a["r0"] == Q and Q in a["output_json"]

    def down(endpoint, body):
        raise RuntimeError(f"{Q} down")
    fake2 = FakeSpark(harness_handler())
    with with_spark(fake2):
        r = orch.run_exception("exc-1", call=down)
    assert r["status"] == "error"
    q, a = fake2.inserts_with_args(C.AGENT_RUNS)[-1]
    assert f"{Q} down" in _bound(q, a)["outcome"]


def test_literals_checker_notes():
    fake = FakeSpark(proposal_handler({"a": 1, Q: 2}))
    with with_spark(fake):
        checker.check_proposal("p-1", call=ScriptedModel([]))
    [(q, a)] = fake.inserts_with_args(C.CHECKER_VERDICTS)
    assert Q in _bound(q, a)["notes"]
    fake = FakeSpark(proposal_handler({"a": 1}))
    with with_spark(fake):
        checker.check_proposal("p-1", call=ScriptedModel([final('{"verdict": "pass"}')]))
    [(q, a)] = fake.inserts_with_args(C.CHECKER_VERDICTS)
    assert a["notes"] is None and ":notes" in q


def test_literals_seed_rules():
    spec = importlib.util.spec_from_file_location("seed_rules", ROOT / "deploy" / "seed_rules.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    rule = json.loads(json.dumps(mod.RULES[0]))
    rule.update(statement_text=Q, params={Q: Q}, value_lists={Q: [Q]},
                expression_sql="SELECT 1 FROM {EXCEPTIONS} WHERE x = :p")
    mod.RULES = [rule]
    fake = FakeSpark()
    mod.seed(fake)
    # The audit table name starts with TABLE, so match the exact table only.
    [(q, a)] = [(s, x) for s, x in zip(fake.queries, fake.args)
                if f"INSERT INTO {mod.TABLE}\n" in s]
    a = _bound(q, a)
    assert sum(v == Q for v in a.values()) == 5   # statement_text, params k+v, value_lists k+v
    assert a[next(k for k, v in a.items() if v == rule["expression_sql"])] == rule["expression_sql"]
    [(qa, aa)] = fake.inserts_with_args(mod.AUDIT)
    assert aa == a and Q not in qa


def _live_values(spark, q, args):
    """Run the VALUES tuple of a generated INSERT as a SELECT: nothing is written."""
    return spark.sql("SELECT * FROM VALUES " + q.split("VALUES", 1)[1].strip(), args=args).first()


def test_live_generated_inserts_round_trip():
    """F18 fixed: values written by the real code paths come back byte for byte."""
    spark = _live()
    if spark is None:
        return "skip"
    fake = FakeSpark()
    with with_spark(fake):
        tools.stage_proposal(run_id="r", target_table=Q, target_key=Q, proposed_payload=HOSTILE,
                             grounding=[{"field": "n", "document_id": Q, "page": 1,
                                         "text_span": HOSTILE["bs"]}],
                             schema_validation=None)
        tools.run_cost_model_scenario(scenario_params=HOSTILE, inputs_vintage="v",
                                      rule_version=1, assumptions="a")
    row = _live_values(spark, *fake.inserts_with_args(C.PROPOSALS)[0])
    assert row[2] == Q and row[3] == Q and json.loads(row[4]) == HOSTILE
    assert row[5][0]["text_span"] == HOSTILE["bs"] and row[6] is None
    row = _live_values(spark, *fake.inserts_with_args(C.MODEL_RUNS)[0])
    assert row[1] == HOSTILE and json.loads(row[5])["scenario_params"] == HOSTILE


def test_live_literal_semantics():
    """Why the sites use parameter markers (F18). Doubling is not an escape in
    Spark SQL: 'o''b' is two adjacent literals, concatenated to "ob". Backslash
    escapes are processed, so json.dumps output with \\" or \\n changes on the way in."""
    spark = _live()
    if spark is None:
        return "skip"
    lit = "'" + Q.replace("'", "''") + "'"
    assert spark.sql(f"SELECT {lit} AS v").first().v == "ob"
    js = json.dumps({"a": 'say "hi"'})
    got = spark.sql("SELECT '" + js.replace("'", "''") + "' AS v").first().v
    assert got == '{"a": "say "hi""}' and got != js
    # The parameterised form round-trips both (the candidate fix, not applied).
    assert spark.sql("SELECT :v AS v", args={"v": Q}).first().v == Q
    assert spark.sql("SELECT :v AS v", args={"v": js}).first().v == js


# ---- LIVE: seeded detection SQL on temp views (no table reads or writes) ----

def _seed():
    spec = importlib.util.spec_from_file_location("seed_rules", ROOT / "deploy" / "seed_rules.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return {r["rule_id"]: r for r in mod.RULES}


def _live():
    spark = SparkSession.getActiveSession()
    # Run as a script, the caller returns "skip" and the runner reports it.
    # Under pytest a returned value counts as a pass, so skip explicitly.
    if spark is None and "pytest" in sys.modules:
        import pytest
        pytest.skip("needs a live Spark session (Databricks)")
    return spark


def test_live_cc02_detection_and_invariant_2():
    """B30.6: 50-day open CC-01 exception escalates, 10-day does not; 45->5 catches both."""
    spark = _live()
    if spark is None:
        return "skip"
    spark.sql("""CREATE OR REPLACE TEMP VIEW harness_test_exceptions AS SELECT * FROM VALUES
      ('old', 'CC-01', 1, array('s1'), CAST(10.00 AS DECIMAL(20,2)), 'PEO', 'open', current_timestamp() - INTERVAL 50 DAYS),
      ('new', 'CC-01', 1, array('s2'), CAST(NULL AS DECIMAL(20,2)), 'PEO', 'open', current_timestamp() - INTERVAL 10 DAYS)
      AS t(exception_id, rule_id, rule_version, subject_ids, dollar_amount, owner_office, status, detected_at)""")
    rule = _seed()["CC-02"]

    def hits(days):
        params = {**rule["params"], "escalation_days": days}
        sql, args = ev._bind(rule["expression_sql"], params)
        sql = sql.replace(C.EXCEPTIONS, "harness_test_exceptions")
        return sorted(r.exception_id for r in spark.sql(sql, args=args).collect())
    assert hits("45") == ["old"]
    assert hits("5") == ["new", "old"]


def test_live_cm01_cm02_detection():
    spark = _live()
    if spark is None:
        return "skip"
    spark.sql("""CREATE OR REPLACE TEMP VIEW harness_test_model_runs AS SELECT * FROM VALUES
      ('m1', map('k','v'), '{"eac": 100}', TIMESTAMP'2026-01-01 00:00:00', map('fpds', TIMESTAMP'2025-12-20 00:00:00')),
      ('m2', map('k','v'), '{"eac": 103}', TIMESTAMP'2026-04-01 00:00:00', map('fpds', TIMESTAMP'2025-12-20 00:00:00'))
      AS t(model_run_id, scenario_params, outputs, created_at, inputs_vintage)""")
    seed = _seed()

    def hits(rid, **override):
        r = seed[rid]
        sql, args = ev._bind(r["expression_sql"], {**r["params"], **override})
        sql = sql.replace(C.MODEL_RUNS, "harness_test_model_runs")
        return [x.model_run_id for x in spark.sql(sql, args=args).collect()]
    assert hits("CM-01") == ["m2"]                     # +3% > 2%
    assert hits("CM-01", growth_pct="0.05") == []
    assert hits("CM-02") == ["m2"]                     # 102 days > 60; m1 is 12 days
    assert hits("CM-02", staleness_days="200") == []



# ---- checker wired into run_exception (invariant 4, 2026-11-11) -------------

class _CheckRecorder:
    def __init__(self, raise_exc=None):
        self.calls = []
        self.raise_exc = raise_exc

    def __call__(self, proposal_id, *, call=None, dry_run=False):
        self.calls.append((proposal_id, call, dry_run))
        if self.raise_exc:
            raise self.raise_exc
        return {"verdict_id": "v-1", "proposal_id": proposal_id,
                "verdict": "pass", "block_reason": None, "model": "m"}


def _staging_run(recorder, **kw):
    fake = FakeSpark(harness_handler())
    model = ScriptedModel([tool_msg(tc(1, "stage_proposal", GROUNDED)), final()])
    with with_spark(fake), patched((orch, "check_proposal", recorder)):
        r = orch.run_exception("exc-1", call=model, **kw)
    return r, fake


def test_run_exception_checks_every_staged_proposal():
    rec = _CheckRecorder()
    marker = object()
    r, fake = _staging_run(rec, checker_call=marker)
    assert r["status"] == "completed" and len(r["proposals"]) == 1, r
    assert rec.calls == [(r["proposals"][0], marker, False)], rec.calls
    assert r["checked"] is True and [v["verdict"] for v in r["verdicts"]] == ["pass"]
    assert len(fake.inserts_with_args(C.AGENT_RUNS)) == 1


def test_run_exception_check_false_skips_checker():
    rec = _CheckRecorder()
    r, _ = _staging_run(rec, check=False)
    assert rec.calls == [] and r["checked"] is False and r["verdicts"] == []
    assert len(r["proposals"]) == 1


def test_run_exception_dry_run_checks_nothing():
    rec = _CheckRecorder()
    r, _ = _staging_run(rec, dry_run=True)
    assert rec.calls == [] and r["checked"] is False and r["verdicts"] == []


def test_run_exception_checker_error_keeps_run():
    rec = _CheckRecorder(raise_exc=RuntimeError("checker down"))
    r, fake = _staging_run(rec)
    assert r["status"] == "completed", r
    [v] = r["verdicts"]
    assert v["verdict"] == "error" and "checker down" in v["block_reason"]
    assert len(fake.inserts_with_args(C.AGENT_RUNS)) == 1

# ---- runner -----------------------------------------------------------------

def run_all() -> int:
    failed = skipped = passed = 0
    for name, fn in sorted(globals().items()):
        if not (name.startswith("test_") and callable(fn)):
            continue
        try:
            res = fn()
        except Exception as exc:
            failed += 1
            print(f"  [FAIL] {name}: {type(exc).__name__}: {exc}")
            continue
        if res == "skip":
            skipped += 1
            print(f"  [skip] {name} (no Spark session)")
        else:
            passed += 1
            print(f"  [ok  ] {name}")
    print(f"\n{passed} ok, {failed} failed, {skipped} skipped")
    return failed


if __name__ == "__main__":
    sys.exit(1 if run_all() else 0)
