"""Agent tools for the harness orchestrator (C2).

Seven read tools call UC SQL functions through Spark SQL. The functions are
parameterised, governed, and auditable (deploy/harness_tools.sql). No agent
gets a free SQL tool.

Two write tools run as orchestrator-side Python:
  stage_proposal  — the ONLY write tool in the agent loop (invariant 6).
  run_cost_model_scenario — runs the deterministic EAC model (cost_model.py),
                            writes model_runs and returns a model_run_id.

Every tool function returns a JSON string (or dict for the write tools) so
the orchestrator can pass it directly into the model’s tool-result message.
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from . import catalog as C
from ._common import spark_session as _spark

# ---- helpers ----------------------------------------------------------------

def _call_uc(fn_fqn: str, args: dict[str, Any]) -> str:
    """Call a UC SQL scalar function and return its string result.

    Values travel as named parameter markers, never as SQL text (F18).
    """
    parts, bound = [], {}
    for i, v in enumerate(args.values()):
        if v is None:
            parts.append("NULL")
        else:
            parts.append(f":p{i}")
            bound[f"p{i}"] = v if isinstance(v, int) else str(v)
    sql = f"SELECT {fn_fqn}({', '.join(parts)})"
    row = _spark().sql(sql, args=bound).collect()
    return row[0][0] if row and row[0][0] is not None else '{"error": "not_found"}'


# ---- read tools (delegates to UC SQL functions) -----------------------------

def get_exception(exception_id: str) -> str:
    """Exception row as a JSON string, or the not_found error JSON."""
    return _call_uc(C.TOOL_GET_EXCEPTION, {"p_exception_id": exception_id})


def get_rule(rule_id: str, version: int | None = None) -> str:
    """Rule definition as a JSON string. version None: the active version, else the
    latest version with its status and resolved_as=no_active_version (A-32)."""
    return _call_uc(C.TOOL_GET_RULE, {"p_rule_id": rule_id, "p_version": version})


def get_document_text(document_id: str, page_start: int | None = None,
                      page_end: int | None = None) -> str:
    """Page text of a registered document as a JSON array of {page, text}."""
    return _call_uc(C.TOOL_GET_DOCUMENT_TEXT, {
        "p_document_id": document_id,
        "p_page_start": page_start, "p_page_end": page_end})


def get_cost_capture(wbs: str, clin: str,
                     period_start: str, period_end: str) -> str:
    """Incurred vs recorded cost by WBS/CLIN (returns blocked_no_source until the feeds land)."""
    return _call_uc(C.TOOL_GET_COST_CAPTURE, {
        "p_wbs": wbs, "p_clin": clin,
        "p_period_start": period_start, "p_period_end": period_end})


def get_evm_control_account(control_account_id: str,
                            period_start: str, period_end: str) -> str:
    """EVM data for one control account (returns blocked_no_source until the feeds land)."""
    return _call_uc(C.TOOL_GET_EVM_CONTROL_ACCOUNT, {
        "p_control_account_id": control_account_id,
        "p_period_start": period_start, "p_period_end": period_end})


def get_cap_ledger(as_of: str) -> str:
    """Cost cap ledger as of a date (returns blocked_no_source until the feeds land)."""
    return _call_uc(C.TOOL_GET_CAP_LEDGER, {"p_as_of": as_of})


def get_cip_transactions(cost_element: str | None = None,
                         period_start: str | None = None,
                         period_end: str | None = None) -> str:
    """CIP transactions by cost element (returns blocked_no_source until the feeds land).

    cost_element is optional (None = all), as in the tool schema and the UC
    function; before F22 the signature required it, so a model that left it
    out raised TypeError. period_start and period_end are required.
    """
    if period_start is None or period_end is None:
        raise TypeError("get_cip_transactions requires period_start and period_end")
    return _call_uc(C.TOOL_GET_CIP_TRANSACTIONS, {
        "p_cost_element": cost_element,
        "p_period_start": period_start, "p_period_end": period_end})


# ---- write tools (orchestrator-side only) -----------------------------------

def stage_proposal(
    *,
    run_id: str,
    target_table: str,
    target_key: str,
    proposed_payload: dict,
    grounding: list[dict],
    schema_validation: str | None = None,
    exception_id: str | None = None,
    rule_id: str | None = None,
    rule_version: int | None = None,
    record_ids: list[str] | None = None,
) -> dict:
    """The ONLY write tool in the agent loop (invariant 6).

    Inserts a row into proposals with status='pending'. The apply path is
    server-side only and unreachable from here.

    run_id and the lineage fields (exception_id, rule_id, rule_version,
    record_ids) are injected by the orchestrator from the exception it is
    working, never taken from the model (F3, invariant 6).

    Returns {proposal_id, status} on success.
    """
    records = [str(r) for r in (record_ids or [])]
    record_sql = "ARRAY(" + ", ".join(f":rec{i}" for i in range(len(records))) + ")" \
        if records else "NULL"
    proposal_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    spark = _spark()
    spark.sql(f"""
        INSERT INTO {C.PROPOSALS}
          (proposal_id, run_id, target_table, target_key, proposed_payload,
           grounding, schema_validation, status, created_at,
           exception_id, rule_id, rule_version, record_ids)
        VALUES (
            :proposal_id, :run_id,
            :target_table, :target_key, :proposed_payload,
            from_json(:grounding,
                      'array<struct<field:string,document_id:string,page:int,text_span:string>>'),
            :schema_validation, 'pending', TIMESTAMP '{now}',
            :exception_id, :rule_id, CAST(:rule_version AS INT), {record_sql}
        )
    """, args={
        "proposal_id": proposal_id, "run_id": run_id,
        "target_table": target_table, "target_key": target_key,
        "proposed_payload": json.dumps(proposed_payload),
        "grounding": json.dumps(grounding),
        "schema_validation": schema_validation or None,
        "exception_id": exception_id, "rule_id": rule_id, "rule_version": rule_version,
        **{f"rec{i}": r for i, r in enumerate(records)},
    })
    return {"proposal_id": proposal_id, "status": "pending"}


def run_cost_model_scenario(
    *,
    scenario_params: dict,
    inputs_vintage: dict | str,
    rule_version: int,
    assumptions: list[str] | str,
    rule_id: str | None = None,
    exception_rule_version: int | None = None,
    record_ids: list[str] | None = None,
) -> dict:
    """Execute the deterministic cost model and write a model_runs row.

    The model itself is a SQL/Python computation. The agent interprets the
    result but never produces a figure the run does not contain (invariant 5).

    Stored inputs (F4), in the column types of model_runs:
      * inputs_vintage MAP<STRING,TIMESTAMP>: feed -> vintage. A dict, or a
        JSON object string, of ISO-8601 timestamps; CM-02 reads it. A value
        that is not a feed map, or a timestamp that does not parse, is not
        stored and is listed in warnings.
      * rule_version MAP<STRING,INT>: {rule_id: version} for the exception's
        rule; rule_id and exception_rule_version are injected by the
        orchestrator. Without a rule_id it is NULL. When the model's
        rule_version differs from the exception's, the exception's is stored
        and the difference is listed in warnings.
      * assumptions ARRAY<STRING>: a list, or one string as a one-item list.
      * input_record_ids ARRAY<STRING>: the exception's record ids (injected).

    Returns {model_run_id, outputs, warnings} on success.
    """
    model_run_id = str(uuid.uuid4())
    spark = _spark()

    # The deterministic model (ops/harness/cost_model.py): an estimate-growth
    # range from the published budget submissions today, or the earned value
    # range when contract figures are passed. Unusable params become warnings.
    from . import cost_model
    try:
        result, model_warnings = cost_model.run(scenario_params)
    except Exception as e:  # noqa: BLE001 - the run row is still written, with the reason
        result = {"status": "error", "model_version": cost_model.MODEL_VERSION,
                  "message": f"cost model failed: {type(e).__name__}",
                  "scenario_params": scenario_params}
        model_warnings = [result["message"]]
    outputs = json.dumps(result, default=str)

    # scenario_params is MAP<STRING,STRING>, so convert all values to strings.
    sp_map = {str(k): str(v) for k, v in scenario_params.items()}
    bound = {"model_run_id": model_run_id, "outputs": outputs,
             "model_version": cost_model.MODEL_VERSION}
    for i, (k, v) in enumerate(sp_map.items()):
        bound[f"k{i}"], bound[f"v{i}"] = k, v
    sp_sql = "MAP(" + ", ".join(f":k{i}, :v{i}" for i in range(len(sp_map))) + ")"

    warnings: list[str] = list(model_warnings)
    vintage = _vintage_map(inputs_vintage, warnings)
    for i, (feed, ts) in enumerate(vintage.items()):
        bound[f"f{i}"], bound[f"t{i}"] = feed, ts
    iv_sql = ("MAP(" + ", ".join(f":f{i}, CAST(:t{i} AS TIMESTAMP)" for i in range(len(vintage)))
              + ")") if vintage else "NULL"

    if rule_id:
        version = rule_version if exception_rule_version is None else exception_rule_version
        if exception_rule_version is not None and rule_version != exception_rule_version:
            warnings.append(f"rule_version {rule_version} given; exception's {rule_id} "
                            f"v{exception_rule_version} stored")
        bound["rv_rule"], bound["rv_version"] = rule_id, int(version)
        rv_sql = "MAP(:rv_rule, CAST(:rv_version AS INT))"
    else:
        rv_sql = "NULL"

    items = [assumptions] if isinstance(assumptions, str) else list(assumptions or [])
    items = [str(a) for a in items if a is not None and str(a).strip()]
    as_sql = _array_sql("as", items, bound)
    rec_sql = _array_sql("rec", [str(r) for r in (record_ids or [])], bound)

    now = datetime.now(timezone.utc).isoformat()
    spark.sql(f"""
        INSERT INTO {C.MODEL_RUNS}
          (model_run_id, scenario_params, inputs_vintage, rule_version,
           assumptions, outputs, model_version, created_at, created_by,
           input_record_ids, warnings)
        VALUES (
            :model_run_id, {sp_sql},
            {iv_sql}, {rv_sql},
            {as_sql}, :outputs,
            :model_version, TIMESTAMP '{now}', 'harness-agent',
            {rec_sql}, {_array_sql("w", warnings, bound)}
        )
    """, args=bound)
    return {"model_run_id": model_run_id, "outputs": json.loads(outputs),
            "warnings": warnings}


def _vintage_map(value, warnings: list[str]) -> dict[str, str]:
    """feed -> ISO timestamp text for inputs_vintage; problems go to warnings."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            pass
    if not isinstance(value, dict):
        warnings.append(f"inputs_vintage not stored: expected a feed -> timestamp map, got {value!r}"[:300])
        return {}
    out = {}
    for feed, ts in value.items():
        # Extended ISO-8601 only: fromisoformat also takes forms Spark's CAST
        # rejects (20260930, 2026-W40-1), which would fail the whole INSERT.
        text = str(ts)
        try:
            ok = bool(_ISO_TS.match(text)) and bool(
                datetime.fromisoformat(text.replace("Z", "+00:00")))
        except ValueError:
            ok = False
        if ok:
            out[str(feed)] = text
        else:
            warnings.append(f"inputs_vintage[{feed!r}] not stored: {ts!r} is not an ISO-8601 timestamp"[:300])
    return out


_ISO_TS = re.compile(r"\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2}(\.\d{1,6})?)?)?(Z|[+-]\d{2}:\d{2})?\Z")


def _array_sql(prefix: str, items: list[str], bound: dict) -> str:
    """ARRAY(:prefix0, ...) with the items bound, or NULL for none."""
    if not items:
        return "NULL"
    for i, item in enumerate(items):
        bound[f"{prefix}{i}"] = item
    return "ARRAY(" + ", ".join(f":{prefix}{i}" for i in range(len(items))) + ")"


# ---- tool registry for the orchestrator ------------------------------------

# Maps tool name -> (callable, OpenAI function schema). The orchestrator uses
# this to build the tools array for the model and to dispatch tool calls.

TOOL_SCHEMAS: list[dict] = [
    {"type": "function", "function": {
        "name": "get_exception",
        "description": "Look up an exception by id. Returns rule_id, rule_version, "
                       "subject_type, subject_ids, dollar_amount, owner_office, required_action, "
                       "status, detected_at. When subject_type is 'exception', subject_ids are "
                       "the parent exception_ids this one was raised on (for example a CC-02 "
                       "escalation of a CC-01 item); call get_exception on each to read the "
                       "parent's status and detected_at, which are what the rule tested.",
        "parameters": {"type": "object", "properties": {
            "exception_id": {"type": "string"}}, "required": ["exception_id"]}}},
    {"type": "function", "function": {
        "name": "get_rule",
        "description": "Look up a rule definition. Returns statement_text, expression_sql, "
                       "params, value_lists, status and resolved_as. Pass version=null for the "
                       "current version. If the rule has no active version, you get its latest "
                       "version with its status (for example blocked_no_source) and "
                       "resolved_as=no_active_version: the rule exists but is not running. "
                       "Only error=not_found means the rule is absent from the register. "
                       "For an explicit version, lifecycle='superseded' with superseded_by=N "
                       "means a newer version N is in effect; the stored status of an old "
                       "version is not updated, so read lifecycle, not status.",
        "parameters": {"type": "object", "properties": {
            "rule_id": {"type": "string"},
            "version": {"type": ["integer", "null"]}}, "required": ["rule_id"]}}},
    {"type": "function", "function": {
        "name": "get_document_text",
        "description": "Read page text from a registered document. Returns [{page, text}].",
        "parameters": {"type": "object", "properties": {
            "document_id": {"type": "string"},
            "page_start": {"type": ["integer", "null"]},
            "page_end": {"type": ["integer", "null"]}}, "required": ["document_id"]}}},
    {"type": "function", "function": {
        "name": "get_cost_capture",
        "description": "Contractor incurred vs. recorded cost by WBS and CLIN. Returns "
                       "blocked_no_source if the feeds are not yet ingested.",
        "parameters": {"type": "object", "properties": {
            "wbs": {"type": "string"}, "clin": {"type": "string"},
            "period_start": {"type": "string"}, "period_end": {"type": "string"}},
            "required": ["wbs", "clin", "period_start", "period_end"]}}},
    {"type": "function", "function": {
        "name": "get_evm_control_account",
        "description": "EVM data: CPI, SPI, TCPI, BCWS, ACWP, EAC at control account. "
                       "Returns blocked_no_source if the feeds are not yet ingested.",
        "parameters": {"type": "object", "properties": {
            "control_account_id": {"type": "string"},
            "period_start": {"type": "string"}, "period_end": {"type": "string"}},
            "required": ["control_account_id", "period_start", "period_end"]}}},
    {"type": "function", "function": {
        "name": "get_cap_ledger",
        "description": "Cost cap ledger: amounts toward 10 USC 8692 limitation, exclusions, "
                       "adjustments, headroom. Returns blocked_no_source if not ingested.",
        "parameters": {"type": "object", "properties": {
            "as_of": {"type": "string"}}, "required": ["as_of"]}}},
    {"type": "function", "function": {
        "name": "get_cip_transactions",
        "description": "CIP transactions: accumulation by cost element, GFE/GFM transfers, "
                       "source document linkage. Returns blocked_no_source if not ingested.",
        "parameters": {"type": "object", "properties": {
            "cost_element": {"type": ["string", "null"]},
            "period_start": {"type": "string"}, "period_end": {"type": "string"}},
            "required": ["period_start", "period_end"]}}},
    {"type": "function", "function": {
        "name": "stage_proposal",
        "description": "Stage a proposal with status pending. This is the ONLY write tool. "
                       "Provide grounding: document_id, page, text_span for every field.",
        "parameters": {"type": "object", "properties": {
            "target_table": {"type": "string"}, "target_key": {"type": "string"},
            "proposed_payload": {"type": "object"},
            "grounding": {"type": "array", "items": {"type": "object",
                "properties": {"field": {"type": "string"},
                               "document_id": {"type": "string"},
                               "page": {"type": "integer"},
                               "text_span": {"type": "string"}}}}},
            "required": ["target_table", "target_key", "proposed_payload", "grounding"]}}},
    {"type": "function", "function": {
        "name": "run_cost_model_scenario",
        "description": "Run the deterministic cost model with given scenario parameters. "
                       "Returns a model_run_id. Every figure the agent cites must resolve "
                       "to a model_run_id.",
        "parameters": {"type": "object", "properties": {
            "scenario_params": {"type": "object"},
            "inputs_vintage": {"type": "object",
                               "description": "Feed name -> ISO-8601 vintage timestamp of the "
                                              "data used, e.g. {\"IPMDAR\": \"2026-09-30T00:00:00Z\"}.",
                               "additionalProperties": {"type": "string"}},
            "rule_version": {"type": "integer"},
            "assumptions": {"type": "array", "items": {"type": "string"},
                            "description": "One entry per assumption."}},
            "required": ["scenario_params", "inputs_vintage", "rule_version", "assumptions"]}}},
]

# Arguments of stage_proposal that only the orchestrator may set.
_INJECTED = frozenset({"run_id", "exception_id", "rule_id", "rule_version", "record_ids"})


def argument_error(name: str, args: Any, schemas: list[dict] | None = None) -> str | None:
    """Why a model's tool call cannot be dispatched, or None if it can (F22).

    Checks the arguments against the tool's JSON schema (required and known
    properties) before the call, so a bad call is returned to the model as a
    tool error instead of raising inside the loop. Keys only the orchestrator
    sets (_INJECTED) are not reported; the dispatcher drops them.
    """
    spec = next((s["function"] for s in (schemas or TOOL_SCHEMAS)
                 if s["function"]["name"] == name), None)
    if spec is None:
        return None
    if not isinstance(args, dict):
        return f"arguments for {name} must be a JSON object"
    params = spec.get("parameters") or {}
    known = set(params.get("properties") or {})
    missing = sorted(set(params.get("required") or []) - set(args))
    unexpected = sorted(set(args) - known - _INJECTED)
    if not missing and not unexpected:
        return None
    parts = ([f"missing {missing}"] if missing else []) + \
            ([f"unexpected {unexpected}"] if unexpected else [])
    return f"bad arguments for {name}: {'; '.join(parts)}; expected {sorted(known)}"


# Dispatch map: tool name -> callable
TOOL_DISPATCH: dict[str, Any] = {
    "get_exception": lambda **kw: get_exception(**kw),
    "get_rule": lambda **kw: get_rule(**kw),
    "get_document_text": lambda **kw: get_document_text(**kw),
    "get_cost_capture": lambda **kw: get_cost_capture(**kw),
    "get_evm_control_account": lambda **kw: get_evm_control_account(**kw),
    "get_cap_ledger": lambda **kw: get_cap_ledger(**kw),
    "get_cip_transactions": lambda **kw: get_cip_transactions(**kw),
    # Write tools receive run_id from the orchestrator, not from the model.
    # run_id and lineage come from the orchestrator; any model-supplied value
    # for those names is dropped (invariant 6, F3).
    "stage_proposal": lambda *, _run_id, _lineage=None, **kw: stage_proposal(
        run_id=_run_id, **(_lineage or {}),
        **{k: v for k, v in kw.items() if k not in _INJECTED}),
    # Lineage from the orchestrator: the exception's rule and records (F4).
    # The model's own rule_version is kept as an argument and compared.
    "run_cost_model_scenario": lambda *, _lineage=None, **kw: run_cost_model_scenario(
        **{k: v for k, v in kw.items()
           if k not in ("rule_id", "exception_rule_version", "record_ids")},
        rule_id=(_lineage or {}).get("rule_id"),
        exception_rule_version=(_lineage or {}).get("rule_version"),
        record_ids=(_lineage or {}).get("record_ids")),
}
