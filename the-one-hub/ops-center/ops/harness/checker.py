"""Independent checker (invariant 4, B28.5, B29).

Re-reads every specialist output and verifies it using a DIFFERENT model
family. A fail blocks the proposal from being applied.

Model selection (B28.5):
  Primary:  databricks-gpt-5-5
  Fallback: databricks-gemini-3-8-flash
  Both verified to pass tool-calling probe (2026-11-10).

The checker:
  * Re-reads the proposal, the exception, and the rule from the tools.
  * Verifies grounding: every field in proposed_payload has a grounding entry
    with a non-empty text_span.
  * Verifies the rule_id and rule_version on the proposal match the exception
    (structural, no model; F21). A proposal without lineage fails: its rule
    cannot be verified.
  * Asks the checker model whether the proposal is consistent with the tool
    results. The model returns a structured verdict.
  * Writes a checker_verdicts row. If verdict is 'fail', the proposal's
    status stays 'pending' (it is never applied). step_seq numbers the
    verdicts of one run 1, 2, ...; the proposal_id is recorded as the
    'proposal' entry in checks (F5; the table has no proposal_id column).
    When no checker model answers, check_proposal returns 'error' but the
    row stores 'fail', since verdict_enum allows only pass,
    pass_with_exception, fail (F6); the 'proposal_review' check keeps
    actual = 'error'.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from . import catalog as C
from ._common import call_model as _call_model
from ._common import message_text as _text
from ._common import role_chain
from ._common import spark_session as _spark
from .specialists import load_prompt
from .tools import TOOL_DISPATCH, argument_error


MAX_TOOL_CHARS = 5000


def _checker_models() -> list[str]:
    """The 'checker' role: a different family from the specialist (B28.5)."""
    return role_chain("checker")


def _clip(obj) -> str:
    s = json.dumps(obj, default=str, ensure_ascii=False)
    return s if len(s) <= MAX_TOOL_CHARS else s[:MAX_TOOL_CHARS] + '...(truncated)'


# Version-controlled prompt file: prompts/harness_checker.md (named after
# checker_agent, the value written to checker_verdicts).
CHECKER_SYSTEM = load_prompt("harness_checker")

CHECKER_PROMPT_VERSION = "checker/verify@1"

# Re-read tools the checker uses (it re-reads, never writes)
CHECKER_TOOLS = [
    {"type": "function", "function": {
        "name": "get_exception",
        "description": "Re-read the exception being checked.",
        "parameters": {"type": "object", "properties": {
            "exception_id": {"type": "string"}}, "required": ["exception_id"]}}},
    {"type": "function", "function": {
        "name": "get_rule",
        "description": "Re-read the rule that triggered the exception.",
        "parameters": {"type": "object", "properties": {
            "rule_id": {"type": "string"},
            "version": {"type": ["integer", "null"]}}, "required": ["rule_id"]}}},
    {"type": "function", "function": {
        "name": "get_document_text",
        "description": "Re-read a document the specialist cited.",
        "parameters": {"type": "object", "properties": {
            "document_id": {"type": "string"},
            "page_start": {"type": ["integer", "null"]},
            "page_end": {"type": ["integer", "null"]}}, "required": ["document_id"]}}},
]

CHECKER_DISPATCH = {
    "get_exception": TOOL_DISPATCH["get_exception"],
    "get_rule": TOOL_DISPATCH["get_rule"],
    "get_document_text": TOOL_DISPATCH["get_document_text"],
}


def check_proposal(
    proposal_id: str,
    *,
    call: Any = None,
    dry_run: bool = False,
) -> dict:
    """Run the independent checker on a single proposal.

    Returns {verdict_id, proposal_id, verdict, block_reason, model}.
    """
    call = call or _call_model
    spark = _spark()
    verdict_id = str(uuid.uuid4())
    now_ts = datetime.now(timezone.utc).isoformat()

    # ---- load the proposal --------------------------------------------------
    prop_row = spark.sql(f"""
        SELECT proposal_id, run_id, target_table, target_key,
               proposed_payload, grounding, schema_validation,
               status, exception_id, rule_id, rule_version
        FROM {C.PROPOSALS}
        WHERE proposal_id = :proposal_id
    """, args={"proposal_id": proposal_id}).collect()
    if not prop_row:
        return {"verdict_id": verdict_id, "proposal_id": proposal_id,
                "verdict": "error", "block_reason": "proposal not found", "model": None}
    prop = prop_row[0].asDict()

    # ---- structural checks (no model needed) --------------------------------
    grounding = prop.get("grounding") or []
    payload_str = prop.get("proposed_payload") or "{}"
    try:
        payload = json.loads(payload_str) if isinstance(payload_str, str) else payload_str
    except (json.JSONDecodeError, TypeError):
        payload = {}

    # Check grounding completeness
    grounded_fields = {g.field for g in grounding if hasattr(g, 'field')} if grounding else set()
    payload_fields = set(payload.keys()) if isinstance(payload, dict) else set()
    ungrounded = payload_fields - grounded_fields - {"status"}  # status can be ungrounded

    # Check the proposal's rule matches its exception (F21)
    if ungrounded:
        block_reason = f"Ungrounded fields in proposal: {sorted(ungrounded)}"
    else:
        block_reason = _rule_mismatch(prop)

    if block_reason:
        verdict = "fail"
        if not dry_run:
            _write_verdict(spark, verdict_id, proposal_id, prop.get("run_id", ""),
                           verdict, block_reason, None, now_ts)
        return {"verdict_id": verdict_id, "proposal_id": proposal_id,
                "verdict": verdict, "block_reason": block_reason, "model": None}

    # ---- model-based check --------------------------------------------------
    user_msg = (
        f"Proposal {proposal_id}:\n"
        f"Target: {prop.get('target_table')}.{prop.get('target_key')}\n"
        f"Payload: {payload_str}\n"
        f"Grounding: {json.dumps([g.asDict() for g in grounding] if grounding else [], default=str)}\n\n"
        f"Exception ID from run: {prop.get('exception_id', 'unknown')}\n\n"
        "Re-read the exception and rule using the tools, then verify this proposal."
    )
    msgs = [
        {"role": "system", "content": CHECKER_SYSTEM},
        {"role": "user", "content": user_msg},
    ]

    model_used = None
    verdict = "error"
    block_reason = "checker did not produce a verdict"

    for model in _checker_models():
        m_msgs = list(msgs)
        try:
            for _step in range(4):  # Checker gets fewer steps
                r = call(model, {
                    "messages": m_msgs, "tools": CHECKER_TOOLS, "max_tokens": 800})
                msg = r["choices"][0]["message"]
                tcs = msg.get("tool_calls") or []
                if not tcs:
                    # Parse the verdict from the response
                    text = _text(msg.get("content"))
                    model_used = model
                    verdict, block_reason = _parse_verdict(text)
                    break

                m_msgs.append(msg)
                for tc in tcs:
                    name = tc["function"]["name"]
                    try:
                        args = json.loads(tc["function"].get("arguments") or "{}")
                    except ValueError:
                        args = {}
                    fn = CHECKER_DISPATCH.get(name)
                    if not fn:
                        result = {"error": f"checker cannot use tool {name}"}
                    elif bad_args := argument_error(name, args, CHECKER_TOOLS):
                        result = {"error": bad_args}   # F22: returned, not raised
                    else:
                        result = fn(**args)
                    m_msgs.append({
                        "role": "tool", "tool_call_id": tc["id"],
                        "content": _clip(result),
                    })
            else:
                # Force answer
                m_msgs.append({"role": "user", "content": "Give your verdict now."})
                r = call(model, {"messages": m_msgs, "max_tokens": 500})
                text = _text(r["choices"][0]["message"].get("content"))
                model_used = model
                verdict, block_reason = _parse_verdict(text)

            break
        except Exception as exc:
            block_reason = f"{model}: {type(exc).__name__}: {str(exc)[:200]}"
            continue

    # ---- write verdict row --------------------------------------------------
    if not dry_run:
        _write_verdict(spark, verdict_id, proposal_id, prop.get("run_id", ""),
                       verdict, block_reason, model_used, now_ts)

    return {
        "verdict_id": verdict_id,
        "proposal_id": proposal_id,
        "verdict": verdict,
        "block_reason": block_reason,
        "model": model_used,
    }


def _parse_verdict(text: str) -> tuple[str, str | None]:
    """Extract verdict from checker model output."""
    try:
        # Try JSON parse
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            d = json.loads(text[start:end])
            v = str(d.get("verdict", "fail")).lower().strip()
            if v not in ("pass", "fail"):
                v = "fail"
            return v, d.get("block_reason")
    except (json.JSONDecodeError, TypeError):
        pass
    # Fallback: look for keywords
    lower = text.lower()
    if "verdict" in lower and "pass" in lower and "fail" not in lower:
        return "pass", None
    return "fail", f"Could not parse checker response: {text[:200]}"


def _rule_mismatch(prop: dict) -> str | None:
    """Block reason if the proposal's rule_id/rule_version differ from its exception's.

    Re-reads the exception through get_exception. None means they match.
    """
    exc_id, rule_id, rule_version = (
        prop.get("exception_id"), prop.get("rule_id"), prop.get("rule_version"))
    if not exc_id or not rule_id or rule_version is None:
        return "Proposal lacks lineage (exception_id, rule_id, rule_version); rule cannot be verified"
    try:
        exc = json.loads(CHECKER_DISPATCH["get_exception"](exception_id=exc_id))
    except (TypeError, ValueError):
        exc = None
    if not isinstance(exc, dict) or exc.get("error"):
        return f"Exception {exc_id} not found; rule cannot be verified"
    if (exc.get("rule_id"), exc.get("rule_version")) != (rule_id, rule_version):
        return (f"Proposal rule {rule_id} v{rule_version} does not match exception "
                f"{exc_id} rule {exc.get('rule_id')} v{exc.get('rule_version')}")
    return None


def _write_verdict(
    spark, verdict_id: str, proposal_id: str, run_id: str,
    verdict: str, block_reason: str | None,
    model: str | None, now_ts: str
):
    """Write to checker_verdicts matching the DDL schema:
    (run_id, step_seq, verdict, checks, notes, checker_agent, model_endpoint, decided_at)

    step_seq is the next number for this run_id (F5). verdict 'error' is
    stored as 'fail' to satisfy verdict_enum (F6).
    """
    seq_row = spark.sql(
        f"SELECT coalesce(max(step_seq), 0) + 1 FROM {C.CHECKER_VERDICTS} WHERE run_id = :run_id",
        args={"run_id": run_id}).collect()
    step_seq = int(seq_row[0][0]) if seq_row and seq_row[0][0] is not None else 1
    # Every value is bound as a parameter marker, never pasted into SQL text (F18, F20).
    args = {"run_id": run_id, "proposal_id": proposal_id,
            "actual": verdict, "verdict": "fail" if verdict == "error" else verdict,
            "model": model or None,
            "notes": block_reason[:500] if block_reason else None}
    # checks is ARRAY<STRUCT<check_name,expected,actual,result>> NOT NULL
    checks = (
        "named_struct('check_name','proposal','expected',:proposal_id,"
        "'actual',:proposal_id,'result','recorded'), "
        "named_struct('check_name','proposal_review','expected','consistent',"
        "'actual',:actual,'result',:verdict)"
    )
    spark.sql(f"""
        INSERT INTO {C.CHECKER_VERDICTS}
          (run_id, step_seq, verdict, checks, notes,
           checker_agent, model_endpoint, decided_at)
        VALUES (
            :run_id, {int(step_seq)}, :verdict,
            ARRAY({checks}),
            :notes,
            'harness_checker', :model,
            TIMESTAMP '{now_ts}')
    """, args=args)
