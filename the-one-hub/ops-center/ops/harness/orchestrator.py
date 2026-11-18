"""Harness orchestrator (task 9, C1, C2, invariants 1-5).

Picks open exceptions, selects a specialist by area, runs the tool-calling
loop, and writes agent_runs / agent_steps. The specialist can only read
through its allowlisted tools and write through stage_proposal.

Design:
  * One run per exception. The orchestrator does not batch.
  * The model sees only the specialist's system prompt, the exception data,
    and the tool results from the allowed tools.
  * stage_proposal receives run_id from the orchestrator, not from the model
    (the model never knows the run_id). Invariant 6.
  * The orchestrator writes agent_steps for every tool call so the checker
    can replay the reasoning without re-calling the model.
  * agent_runs gets one row per run, written when the run ends, with both
    started_at and ended_at (F2). A run killed mid-loop leaves agent_steps
    rows whose run_id has no agent_runs row; that is how to spot one.
  * The specialist's final answer is its finding. It is written as the last
    agent_steps row of the run, output_json {"kind": "finding", "text": ...},
    with the same rule and record citation as every other step (F23). Before
    F23 the text was discarded, so a run that staged no proposal left no
    record of what the agent concluded.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from . import catalog as C
from ._common import call_model as _call_model
from ._common import message_text as _text  # noqa: F401  (kept: module API)
from ._common import role_chain
from ._common import spark_session as _spark
from .checker import check_proposal
from .precheck import precheck as _precheck
from .specialists import get_specialist
from .tools import TOOL_SCHEMAS, TOOL_DISPATCH, argument_error


MAX_STEPS = 8

# Tools that write to a table. Under dry_run they are not called (F15); the
# model gets a dry_run result instead, and the run reports what it would have staged.
WRITE_TOOLS = frozenset({"stage_proposal", "run_cost_model_scenario"})
MAX_TOOL_CHARS = 7000


def _clip(obj) -> str:
    s = json.dumps(obj, default=str, ensure_ascii=False)
    return s if len(s) <= MAX_TOOL_CHARS else s[:MAX_TOOL_CHARS] + '..."(truncated)"'


MAX_STEP_JSON = 2000


def _step_json(result) -> str:
    """agent_steps.output_json: the tool result as one JSON document, <= MAX_STEP_JSON chars.

    Read tools return JSON text; it is stored as is, not wrapped in a second
    JSON string. Anything else is json.dumps'd once. An over-long result is
    stored as {"truncated": true, "chars": n, "preview": ...} so the column
    always holds valid JSON. (The model still receives _clip(result).)
    """
    text = None
    if isinstance(result, str):
        try:
            json.loads(result)
            text = result
        except ValueError:
            pass
    if text is None:
        text = json.dumps(result, default=str, ensure_ascii=False)
    if len(text) <= MAX_STEP_JSON:
        return text
    n = MAX_STEP_JSON - 100
    while True:
        out = json.dumps({"truncated": True, "chars": len(text), "preview": text[:n]},
                         ensure_ascii=False)
        if len(out) <= MAX_STEP_JSON:
            return out
        n -= 200


def _models(role: str = "agent") -> list[str]:
    """Model chain for a seed/models.yaml role. The specialist loop calls tools,
    so it runs on the 'agent' role (tool-capable endpoints only)."""
    return role_chain(role)


def _lineage(exception_id: str, exc: dict) -> tuple[dict, list[str]]:
    """(lineage, missing): rule_id, rule_version, record_ids taken from the exception.

    record_ids are the exception's subject_ids. Nothing is defaulted (F7):
    a missing or empty field is reported, not filled with a placeholder.
    """
    rule_id = exc.get("rule_id")
    rule_version = exc.get("rule_version")
    records = [str(s) for s in (exc.get("subject_ids") or []) if s is not None]
    missing = [name for name, ok in (
        ("rule_id", isinstance(rule_id, str) and rule_id.strip() != ""),
        ("rule_version", isinstance(rule_version, int) and not isinstance(rule_version, bool)),
        ("subject_ids", bool(records)),
    ) if not ok]
    return ({"exception_id": exception_id, "rule_id": rule_id,
             "rule_version": rule_version, "record_ids": records}, missing)


# A-33 (2026-11-11): the finding is stored in full. It used to be clipped to
# 1,900 chars to fit MAX_STEP_JSON, and the clipped part was usually the
# conclusion. MAX_STEP_JSON still bounds tool results; it does not apply to
# the finding. output_json is a STRING column with no length limit.
# Display may shorten a finding; storage may not.


def _write_finding(spark, *, run_id: str, step_seq: int, spec, model: str | None,
                   lineage: dict, text: str) -> None:
    """Append the specialist's final answer as a cited agent_steps row (F23).

    output_json is {"kind": "finding", "text": ..., "truncated": false, "chars": n}.
    The text is the full final answer (A-33); truncated is always false for rows
    written by this version and is kept so readers of older rows still work.
    Readers tell a finding from a tool result by the kind field. Values are
    bound as parameter markers, never pasted into SQL text (F18).
    """
    import hashlib
    output = json.dumps({"kind": "finding", "text": text, "truncated": False,
                         "chars": len(text)}, ensure_ascii=False)
    record_ids = lineage["record_ids"]
    args = {"run_id": run_id, "specialist": spec.name, "agent_version": spec.prompt_version,
            "model": model or None, "rule_id": lineage["rule_id"],
            "rule_version": lineage["rule_version"],
            "input_digest": hashlib.sha256(text.encode()).hexdigest()[:16],
            "output_json": output}
    args.update({f"r{i}": s for i, s in enumerate(record_ids)})
    record_sql = ",".join(f":r{i}" for i in range(len(record_ids)))
    spark.sql(f"""
        INSERT INTO {C.AGENT_STEPS}
          (run_id, step_seq, agent_name, agent_version, model_endpoint,
           rule_id, rule_version, record_ids, inputs_digest, output_json,
           tokens, latency_ms, prompt_sha, stepped_at,
           actor_kind, authority_basis)
        VALUES (:run_id, {int(step_seq)}, :specialist, :agent_version, :model,
                :rule_id, :rule_version, ARRAY({record_sql}), :input_digest,
                :output_json, NULL, NULL, NULL, CURRENT_TIMESTAMP(),
                'agent', 'agent_own')
    """, args=args)


# ---- core loop --------------------------------------------------------------

def run_exception(
    exception_id: str,
    *,
    call: Any = None,
    dry_run: bool = False,
    check: bool = True,
    checker_call: Any = None,
    precheck: bool = True,
) -> dict:
    """Process one exception through the specialist loop.

    With check (the default) every proposal the run staged goes through
    checker.check_proposal before this returns, so no caller can stage a
    proposal and skip its verdict (invariant 4). checker_call is the checker's
    model client; it is separate from call because the checker must use a
    different model family. A checker failure on one proposal is recorded in
    verdicts as 'error' and does not lose the run. Dry runs stage nothing, so
    nothing is checked.

    With precheck (the default) the code-only pre-check (A-34, precheck.py)
    runs first. If it does not admit the item, no model is called: the run
    returns status 'precheck_blocked' with the lane and reasons, and (unless
    dry_run) writes one agent_runs row whose outcome is
    'precheck_blocked: <lane>: <reasons>' and no agent_steps. precheck=False
    skips it, for a deliberate run on an item the gate would refuse.

    Returns {run_id, exception_id, specialist, steps, proposals, status, error}.
    With dry_run nothing is written: no agent_runs / agent_steps rows and no
    write tools (WRITE_TOOLS) are called; proposals stays empty and
    dry_run_proposals counts the stage_proposal calls that were skipped.
    """
    call = call or _call_model
    spark = _spark()
    run_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    now_ts = now.isoformat()

    # ---- load exception -----------------------------------------------------
    exc_json = spark.sql(
        f"SELECT {C.TOOL_GET_EXCEPTION}(:exception_id)", args={"exception_id": exception_id}
    ).collect()[0][0]
    exc_data = json.loads(exc_json)
    if exc_data.get("error") == "not_found":
        return {"run_id": run_id, "exception_id": exception_id,
                "status": "error", "error": "exception not found"}

    area = exc_data.get("area", "")
    try:
        spec = get_specialist(area)
    except KeyError as e:
        return {"run_id": run_id, "exception_id": exception_id,
                "status": "error", "error": str(e)}

    # ---- build the tool set from the specialist's allowlist -----------------
    tools = [t for t in TOOL_SCHEMAS if t["function"]["name"] in spec.tool_allowlist]

    # Lineage for every agent_steps row and every staged proposal comes from
    # the exception, never from defaults or the model (F3, F7). An exception
    # without it is refused before any model call or write.
    lineage, missing = _lineage(exception_id, exc_data)
    if missing:
        return {"run_id": run_id, "exception_id": exception_id,
                "status": "error", "error": f"exception lacks lineage: {', '.join(missing)}"}

    # Values shared by the agent_runs and agent_steps inserts. Every value is
    # bound as a parameter marker, never pasted into SQL text (F1, F18).
    run_args = {"run_id": run_id, "exception_id": exception_id, "specialist": spec.name}

    # ---- pre-check: code only, before any model call (A-34) -----------------
    pc = _precheck(spark, exc_data) if precheck else None
    if pc is not None and not pc["admit"]:
        outcome = f"precheck_blocked: {pc['lane']}: " + "; ".join(pc["reasons"])
        if not dry_run:
            ended_ts = datetime.now(timezone.utc).isoformat()
            spark.sql(f"""
                INSERT INTO {C.AGENT_RUNS}
                  (run_id, trigger, triggered_by, started_at, ended_at,
                   orchestrator_version, mlflow_trace_id,
                   subject_kind, subject_id, specialist, outcome)
                VALUES (
                    :run_id, 'harness', 'orchestrator',
                    TIMESTAMP '{now_ts}', TIMESTAMP '{ended_ts}',
                    'orchestrator/1.0', NULL,
                    'exception', :exception_id, :specialist,
                    :outcome)
            """, args={**run_args, "outcome": outcome})
        return {"run_id": run_id, "exception_id": exception_id, "specialist": spec.name,
                "model": None, "steps": 0, "proposals": [],
                **({"dry_run_proposals": 0} if dry_run else {}),
                "status": "precheck_blocked", "lane": pc["lane"], "error": None,
                "precheck": pc, "checked": False, "verdicts": []}

    # ---- tool-calling loop --------------------------------------------------
    user_msg = (
        f"Exception {exception_id}:\n"
        f"{json.dumps(exc_data, indent=2, default=str)}\n\n"
        "Read the exception, look up the rule, inspect any supporting data, "
        "and either stage a proposal to resolve it or explain what is missing."
    )
    msgs = [
        {"role": "system", "content": spec.system_prompt},
        {"role": "user", "content": user_msg},
    ]
    steps: list[dict] = []
    proposals: list[str] = []
    dry_run_proposals = 0
    model_used = None
    error_msg = None
    step_num = 0
    final_text = ""

    for model in _models("agent"):
        m_msgs = list(msgs)
        try:
            for _loop in range(MAX_STEPS):
                r = call(model, {
                    "messages": m_msgs, "tools": tools, "max_tokens": 2000})
                msg = r["choices"][0]["message"]
                tcs = msg.get("tool_calls") or []

                if not tcs:
                    # Final text response — done. It is the finding (F23).
                    model_used = model
                    final_text = _text(msg.get("content"))
                    break

                m_msgs.append(msg)
                for tc in tcs:
                    step_num += 1
                    name = tc["function"]["name"]
                    try:
                        args = json.loads(tc["function"].get("arguments") or "{}")
                    except ValueError:
                        args = {}

                    # Enforce allowlist (invariant 3)
                    if name not in spec.tool_allowlist:
                        result = {"error": f"tool {name} not in allowlist for {spec.name}"}
                    else:
                        fn = TOOL_DISPATCH.get(name)
                        if fn is None:
                            result = {"error": f"unknown tool {name}"}
                        elif bad_args := argument_error(name, args):
                            # F22: returned to the model, not raised
                            result = {"error": bad_args}
                        elif dry_run and name in WRITE_TOOLS:
                            # F15: a dry run writes nothing
                            result = {"status": "dry_run", "tool": name,
                                      "note": "not executed: dry run writes nothing"}
                            dry_run_proposals += name == "stage_proposal"
                        elif name == "stage_proposal":
                            # Inject run_id and lineage (invariant 6, F3)
                            result = fn(_run_id=run_id, _lineage=lineage, **args)
                            proposals.append(result.get("proposal_id", ""))
                        elif name == "run_cost_model_scenario":
                            # Inject the exception's rule and records (F4)
                            result = fn(_lineage=lineage, **args)
                        else:
                            result = fn(**args)

                    result_str = _clip(result)
                    step = {
                        "step": step_num, "tool": name, "args": args,
                        "result_preview": result_str[:500],
                        "ok": not (isinstance(result, (dict, str))
                                   and "error" in str(result)[:50]),
                    }
                    steps.append(step)

                    # Write agent_steps row
                    if not dry_run:
                        import hashlib
                        input_digest = hashlib.sha256(
                            json.dumps(args, sort_keys=True).encode()).hexdigest()[:16]
                        record_ids = lineage["record_ids"]
                        step_args = {
                            "run_id": run_id, "specialist": spec.name,
                            "agent_version": spec.prompt_version, "model": model or None,
                            "rule_id": lineage["rule_id"],
                            "rule_version": lineage["rule_version"],
                            "input_digest": input_digest,
                            "output_json": _step_json(result),
                        }
                        step_args.update({f"r{i}": s for i, s in enumerate(record_ids)})
                        record_sql = ",".join(f":r{i}" for i in range(len(record_ids)))
                        spark.sql(f"""
                            INSERT INTO {C.AGENT_STEPS}
                              (run_id, step_seq, agent_name, agent_version,
                               model_endpoint, rule_id, rule_version,
                               record_ids, inputs_digest, output_json,
                               tokens, latency_ms, prompt_sha, stepped_at,
                               actor_kind, authority_basis)
                            VALUES (
                                :run_id, {int(step_num)}, :specialist,
                                :agent_version,
                                :model, :rule_id,
                                :rule_version,
                                ARRAY({record_sql}),
                                :input_digest, :output_json,
                                NULL, NULL, NULL, CURRENT_TIMESTAMP(),
                                'agent', 'none')
                        """, args=step_args)

                    m_msgs.append({
                        "role": "tool", "tool_call_id": tc["id"],
                        "content": result_str,
                    })

            else:
                # Exhausted MAX_STEPS — force a final answer
                m_msgs.append({"role": "user",
                               "content": "Answer now from what you have."})
                r = call(model, {"messages": m_msgs, "max_tokens": 1500})
                model_used = model
                final_text = _text(r["choices"][0]["message"].get("content"))

            break  # Success — don't try the next model

        except Exception as exc:
            error_msg = f"{model}: {type(exc).__name__}: {str(exc)[:300]}"
            continue

    status = "completed" if model_used else "error"
    if not model_used and error_msg:
        status = "error"
    elif not model_used:
        error_msg = "no model reachable"

    # ---- write the finding as the run's last step (F23) --------------------
    if final_text.strip() and not dry_run:
        step_num += 1
        _write_finding(spark, run_id=run_id, step_seq=step_num, spec=spec,
                       model=model_used, lineage=lineage, text=final_text)

    # ---- write the single agent_runs row (F2) ------------------------------
    if not dry_run:
        ended_ts = datetime.now(timezone.utc).isoformat()
        outcome_msg = status if not error_msg else f"{status}: {error_msg[:200]}"
        spark.sql(f"""
            INSERT INTO {C.AGENT_RUNS}
              (run_id, trigger, triggered_by, started_at, ended_at,
               orchestrator_version, mlflow_trace_id,
               subject_kind, subject_id, specialist, outcome)
            VALUES (
                :run_id, 'harness', 'orchestrator',
                TIMESTAMP '{now_ts}', TIMESTAMP '{ended_ts}',
                'orchestrator/1.0', NULL,
                'exception', :exception_id, :specialist,
                :outcome)
        """, args={**run_args, "outcome": outcome_msg})

    # ---- independent check of every staged proposal (invariant 4) ----------
    verdicts: list[dict] = []
    if check and not dry_run:
        for proposal_id in proposals:
            if not proposal_id:
                verdicts.append({"proposal_id": proposal_id, "verdict": "error",
                                 "block_reason": "stage_proposal returned no proposal_id",
                                 "model": None})
                continue
            try:
                verdicts.append(check_proposal(proposal_id, call=checker_call))
            except Exception as exc:  # one bad check must not lose the run
                verdicts.append({"proposal_id": proposal_id, "verdict": "error",
                                 "block_reason": f"{type(exc).__name__}: {str(exc)[:200]}",
                                 "model": None})

    return {
        "run_id": run_id,
        "exception_id": exception_id,
        "specialist": spec.name,
        "model": model_used,
        "steps": len(steps),
        "proposals": proposals,
        **({"dry_run_proposals": dry_run_proposals} if dry_run else {}),
        "status": status,
        "error": error_msg,
        "checked": bool(check and not dry_run),
        "verdicts": verdicts,
        "precheck": pc,
    }
