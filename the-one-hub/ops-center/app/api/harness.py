"""The work queue: exceptions, the exception card, apply and reject.

Two layers in one module, kept apart:

  service functions   list_exceptions, exception_card, authority_for, act.
                      Each takes the query callables it runs with, so tests
                      pass fakes and the pages and the JSON API share them.
  router              /api/v1 JSON routes over those functions.

Who each statement runs as:

  q_app   the app service principal. Reads of the agent's own tables.
  q_user  the caller, on their on-behalf-of token. Every authority check,
          every write, and the reads the app principal has no grant on
          (decisions, decision attempts). None when the request carries no
          token; then nothing authority-bearing runs and the reason is shown.

Nothing here computes a figure. Amounts arrive as decimal strings and go out
inside envelopes.figure().
"""
from __future__ import annotations

import json
import uuid
from collections.abc import Callable

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from . import envelopes as E
from . import harness_sql as H
from . import identity, live

QueryFn = Callable[[str, dict], list[dict]]

PAGE_SIZE_MAX = 200


# ------------------------------------------------------------------ plumbing
def runners(request: Request) -> tuple[identity.Identity, QueryFn, QueryFn | None]:
    """(identity, q_app, q_user) for one request."""
    ident = identity.from_request(request)
    client = identity.user_client(ident)

    def q_app(sql: str, params: dict | None = None) -> list[dict]:
        return live.query(sql, params)[1]

    def q_user(sql: str, params: dict | None = None) -> list[dict]:
        return live.query(sql, params, client=client)[1]

    return ident, q_app, (q_user if client else None)


def _arr(value) -> list[str]:
    """Array columns arrive from the Statement Execution API as JSON text."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(v) for v in json.loads(value)]


def _section(fn: Callable[[], list[dict]]) -> dict:
    """Run one optional read. A failure is reported in place, never hidden."""
    try:
        return {"rows": fn(), "error": None}
    except Exception as exc:  # noqa: BLE001 - shown to the reader, not swallowed
        return {"rows": [], "error": str(exc)[:400]}


# ------------------------------------------------------------------ envelopes
def amount_figure(x: dict) -> dict:
    """The exception's dollar amount, as detected by its rule."""
    return E.figure(
        figure_id=f"exception.{x['exception_id']}.dollar_amount",
        label="Exception amount",
        value=x.get("dollar_amount"),
        unit="USD",
        as_of=x.get("detected_at"),
        record_ids=_arr(x.get("subject_ids")),
        rule_id=x.get("rule_id"),
        rule_version=x.get("rule_version"),
        computation=(f"dollar_amount returned by the expression of rule {x.get('rule_id')} "
                     f"version {x.get('rule_version')} for these records, in rule "
                     f"evaluation {x.get('eval_id')}. Stored as detected; not recomputed."),
        source="aircarrier_app_exceptions",
        unknown_reason=_no_amount_reason(x),
    )


def unestablished_amount(x: dict, why: str) -> dict:
    """WORK_QUEUE_V2 T3: the amount of an exception in the System lane (test data,
    superseded, a retired rule version) has no live basis, so it is shown as an
    unknown figure with the reason, never printed to the cent."""
    f = amount_figure({**x, "dollar_amount": None})
    f["state_reason"] = (f"Not established. {why} The rule recorded an amount, but it has "
                         "no live basis and is not counted anywhere.")
    return f


def _no_amount_reason(x: dict) -> str:
    """Why an exception has no amount. A-28: an escalation names its parent
    exception and does not restate the parent's dollars, so they are counted once."""
    if x.get("subject_type") == "exception":
        parents = ", ".join(_arr(x.get("subject_ids"))) or "its parent"
        return (f"Escalation of exception {parents}. The amount stays on that exception "
                "and is not counted again here.")
    return "The rule that raised this exception returns no dollar amount."


def count_figure(n: int, *, label: str, computation: str) -> dict:
    return E.figure(figure_id="count", label=label, value=str(n), unit="COUNT",
                    as_of=None, record_ids=[], computation=computation,
                    source="aircarrier_app_exceptions")


def _exception_view(x: dict) -> dict:
    return {
        "exception_id": x["exception_id"], "area": x.get("area"), "status": x["status"],
        "subject_type": x.get("subject_type"),
        "citation": E.citation(rule_id=x["rule_id"], rule_version=x["rule_version"],
                               record_ids=_arr(x.get("subject_ids"))),
        "amount": amount_figure(x),
        "owner_role": x["owner_role"], "owner_office": x["owner_office"],
        "required_action": x["required_action"],
        "window_closes_at": x.get("window_closes_at"),
        "detected_at": x.get("detected_at"), "eval_id": x.get("eval_id"),
        "last_run_at": x.get("last_run_at"), "last_run_outcome": x.get("last_run_outcome"),
    }


# ------------------------------------------------------------------ service
def list_exceptions(q_app: QueryFn, *, filters: dict, sort: str = "detected_at",
                    descending: bool = True, page: int = 1, page_size: int = 50) -> dict:
    """One server-side page of exceptions. Filtering and sorting happen in SQL."""
    t = H.tables()
    sort = sort if sort in H.EXCEPTION_SORTS else "detected_at"
    page = max(1, int(page))
    page_size = min(max(1, int(page_size)), PAGE_SIZE_MAX)
    where, params = H.exception_where(filters)
    rows = q_app(H.exception_list(t, where, sort, descending, page_size,
                                  (page - 1) * page_size), params)
    total = int(q_app(H.exception_count(t, where), params)[0]["n"])
    # Not "items": in a Jinja template result.items is the dict method.
    return {
        "exceptions": [_exception_view(r) for r in rows],
        "total": count_figure(total, label="Exceptions matching these filters",
                              computation="count of exception rows matching the filters shown"),
        "page": page, "page_size": page_size,
        "has_next": page * page_size < total,
        "filters": {k: filters.get(k) for k in H.EXCEPTION_FILTERS},
        "sort": sort, "descending": descending,
    }


FINDING_NOT_CHECKED = ("The checker verifies staged proposals. This finding staged no "
                       "proposal, so no checker has read it.")


def _run_view(run: dict, steps: list[dict]) -> dict:
    """One agent run: its tool steps in order and its finding, if it recorded one."""
    finding, tool_steps = None, []
    for s in steps:
        out = E.step_output(s.get("output_json"))
        cite = E.citation(rule_id=s.get("rule_id"), rule_version=s.get("rule_version"),
                          record_ids=_arr(s.get("record_ids")), run_id=run["run_id"],
                          step_seq=s.get("step_seq"))
        who = E.actor(s.get("actor_kind") or "agent", s.get("agent_name"),
                      detail=s.get("agent_version"),
                      authority_basis=s.get("authority_basis"))
        if isinstance(out, dict) and out.get("kind") == "finding":
            finding = {"text": out.get("text", ""), "truncated": bool(out.get("truncated")),
                       "citation": cite, "actor": who, "model": s.get("model_endpoint"),
                       "verdict": E.verdict(None, not_checked_reason=FINDING_NOT_CHECKED)}
            continue
        status = out.get("status") or ("error" if out.get("error") else "result") \
            if isinstance(out, dict) else "result"
        summary = (out.get("message") or out.get("error") or "") if isinstance(out, dict) else ""
        tool_steps.append({"step_seq": s.get("step_seq"), "status": status,
                           "summary": str(summary)[:300], "citation": cite, "actor": who,
                           "stepped_at": s.get("stepped_at")})
    return {"run_id": run["run_id"], "specialist": run.get("specialist"),
            "started_at": run.get("started_at"), "ended_at": run.get("ended_at"),
            "outcome": run.get("outcome"), "trigger": run.get("trigger"),
            "steps": tool_steps, "finding": finding}


def authority_for(q_user: QueryFn | None, proposal_id: str, action: str) -> dict:
    """The server's answer to: may this caller take this action. For rendering."""
    if q_user is None:
        return E.authority(action, None, missing_reason=identity.obo_missing_reason())
    try:
        rows = q_user(H.authority_check(H.tables()),
                      {"proposal_id": proposal_id, "action": action, "confirmed_records": None})
    except Exception as exc:  # noqa: BLE001
        return E.authority(action, None,
                           missing_reason=f"Authority could not be evaluated: {str(exc)[:300]}")
    return E.authority(action, rows[0] if rows else None)


def _proposal_view(p: dict, q_user: QueryFn | None) -> dict:
    try:
        payload = json.loads(p.get("proposed_payload") or "{}")
    except ValueError:
        payload = {"unparsed": p.get("proposed_payload")}
    grounding = json.loads(p.get("grounding_json") or "null") or []
    return {
        "proposal_id": p["proposal_id"], "run_id": p.get("run_id"), "status": p["status"],
        "intake_outcome": p.get("intake_outcome"), "block_reason": p.get("block_reason"),
        "target": f"{p.get('target_table')}.{p.get('target_key')}",
        "payload": E.typed_payload(payload, grounding=grounding,
                                     proposal_id=p["proposal_id"],
                                     rule_id=p.get("rule_id"),
                                     rule_version=p.get("rule_version")),
        "grounding": grounding, "created_at": p.get("created_at"),
        "citation": E.citation(rule_id=p.get("rule_id"), rule_version=p.get("rule_version"),
                               record_ids=_arr(p.get("record_ids")), run_id=p.get("run_id")),
        "actor": E.actor("agent", "specialist", detail=f"run {p.get('run_id')}"),
        "verdict": E.verdict(p, not_checked_reason="No checker verdict is recorded for this proposal."),
        "authority": {a: authority_for(q_user, p["proposal_id"], a) for a in ("apply", "reject")},
    }


_DECIDED = {"applied": "apply", "rejected": "reject"}


def _mark_unbacked(views: list[dict], decisions: dict) -> None:
    """Flag a proposal whose status says decided with no decision row behind it.

    Only the app's apply path writes a decision, so applied or rejected with no
    matching decision means something else changed the status (gap A-22: the
    agent principal holds MODIFY on proposals). Without the decisions read
    (no user token), the check cannot be made and says so.
    """
    decided = {(d["proposal_id"], d["action"]) for d in decisions["rows"]}
    for p in views:
        want = _DECIDED.get(p["status"])
        if not want:
            p["unbacked"] = None
        elif decisions["error"]:
            p["unbacked"] = (f"Status is {p['status']}. Whether a decision backs it could not be "
                             f"checked: the decisions could not be read.")
        elif (p["proposal_id"], want) not in decided:
            p["unbacked"] = (f"Status is {p['status']}, but no {want} decision is recorded for this "
                             f"proposal. The status was changed outside the decision path. "
                             f"Do not rely on it until it is reconciled.")
        else:
            p["unbacked"] = None


def exception_card(q_app: QueryFn, q_user: QueryFn | None, exception_id: str) -> dict | None:
    """Everything the exception card shows, so a user can decide without leaving it."""
    t = H.tables()
    found = q_app(H.exception_one(t), {"exception_id": exception_id})
    if not found:
        return None
    x = found[0]
    rule = _section(lambda: q_app(H.rule_at_version(t), {"rule_id": x["rule_id"],
                                                         "rule_version": x["rule_version"]}))
    runs = _section(lambda: q_app(H.runs_for_exception(t), {"exception_id": exception_id}))
    latest = None
    if runs["rows"]:
        run = runs["rows"][0]
        steps = q_app(H.steps_for_run(t), {"run_id": run["run_id"]})
        latest = _run_view(run, steps)
    proposals = _section(lambda: q_app(H.proposals_for_exception(t), {"exception_id": exception_id}))
    as_user = q_user or (lambda *_: (_ for _ in ()).throw(
        RuntimeError(identity.obo_missing_reason())))
    decisions = _section(lambda: as_user(H.decisions_for_exception(t), {"exception_id": exception_id}))
    attempts = _section(lambda: as_user(H.attempts_for_exception(t), {"exception_id": exception_id}))
    rule_row = rule["rows"][0] if rule["rows"] else None
    views = [_proposal_view(p, q_user) for p in proposals["rows"]]
    _mark_unbacked(views, decisions)
    # The answer line and lane, by the same code as the queue (lanes()).
    current = _section(lambda: q_app(H.lane_current(t), {}))
    if current["error"]:
        lane, answer = None, f"The lane could not be worked out: {current['error']}"
    else:
        lane, answer = exception_lane(x, live_versions(current["rows"]))
    xv = _exception_view(x)
    if lane == "system":
        xv["amount"] = unestablished_amount(x, answer)
    return {
        "lane": lane, "answer": answer,
        "exception": xv,
        "rule": rule_row, "rule_error": rule["error"],
        "latest_run": latest, "run_count": len(runs["rows"]), "runs_error": runs["error"],
        "proposals": views,
        "proposals_error": proposals["error"],
        "decisions": [dict(d, actor_view=E.actor(
                          d.get("actor_kind") or "human", d["actor"],
                          role=d.get("actor_role"),
                          authority_basis=d.get("authority_basis")))
                      for d in decisions["rows"]],
        "decisions_error": decisions["error"],
        "attempts": attempts["rows"], "attempts_error": attempts["error"],
        "obo": q_user is not None,
    }


# ------------------------------------------------------------------ lanes
# WORK_QUEUE_V2 section 4.1. Every item lands in exactly one lane, by code:
#
#   decide   a named role can act on it today: an open, non-test exception on
#            the live version of its rule, or the newest pending SI proposal
#            for its subject whose run the records checker passed. Proposals
#            are decided on their run page (/runs/{run_id}), not here.
#   unblock  a rule that cannot run, one row per root cause (blocked_reason),
#            with the rules it holds and the office that owns them.
#   system   test data, superseded or closed rows, repeat runs, unchecked or
#            failed proposals, rule defects. Shown collapsed; no business action.
TEST_PREFIXES = ("test-",)
PASSING = {"pass", "pass_with_exception"}
CLOSED_REASON = {
    "void_test_data": "Test data. Voided; no action.",
    "superseded": "Superseded by a later version of the same rule; no action.",
}


def _is_test(ids: list[str]) -> bool:
    return any(str(i).lower().startswith(TEST_PREFIXES) for i in ids)


def live_versions(current: list[dict]) -> dict[str, list[int]]:
    """rule_id -> the version in effect, from the current_rules view."""
    out: dict[str, list[int]] = {}
    for r in current:
        out.setdefault(r["rule_id"], []).append(int(r["version"]))
    return {k: sorted(v) for k, v in out.items()}


def unretired_active(rules: list[dict], retired: set[tuple[str, int]]) -> dict[str, list[int]]:
    """rule_id -> active versions with no retire event (a defect when more than one)."""
    out: dict[str, list[int]] = {}
    for r in rules:
        if r["status"] == "active" and (r["rule_id"], int(r["version"])) not in retired:
            out.setdefault(r["rule_id"], []).append(int(r["version"]))
    return {k: sorted(v) for k, v in out.items()}


def exception_lane(x: dict, live: dict[str, list[int]]) -> tuple[str, str]:
    """(lane, the one-line answer) for one exception. Code, not a model."""
    ids = _arr(x.get("subject_ids"))
    if x["status"] != "open":
        return "system", CLOSED_REASON.get(x["status"],
                                           f"Closed ({x['status'].replace('_', ' ')}); no action.")
    if _is_test(ids):
        return "system", "Test data still open. Void it; no business action."
    versions = live.get(x["rule_id"], [])
    if int(x["rule_version"]) not in versions:
        return "system", (f"Raised by {x['rule_id']} v{x['rule_version']}, which is not a live "
                          f"version of the rule. Supersede it; no business action.")
    when = (f"by {x['window_closes_at']}" if x.get("window_closes_at")
            else "(the rule sets no deadline)")
    return "decide", (f"Decide {when}: {x['required_action']}. Owner {x['owner_role']}, "
                      f"{x['owner_office']}.")


def _verdicts(row: dict) -> list[dict]:
    v = row.get("verdicts")
    return (json.loads(v) if isinstance(v, str) else v) or []


def proposal_check(row: dict) -> tuple[bool, str]:
    """Passed when the run's records checker passed and no checker failed it."""
    vs = _verdicts(row)
    if not vs:
        return False, "No checker verdict is recorded for its run."
    if any(v["verdict"] not in PASSING for v in vs):
        return False, "A checker did not pass its run: " + ", ".join(
            f"{v['checker']} {v['verdict']}" for v in vs) + "."
    if not any(v["checker"] == "si:records_checker" for v in vs):
        return False, "The records checker has not read its run."
    return True, "Checked: " + ", ".join(
        f"{v['checker'].removeprefix('si:').replace('_', ' ')} "
        f"{v['verdict'].replace('_', ' ')}" for v in vs) + "."


def _proposal_item(row: dict, payload: dict, check_text: str, copies: int) -> dict:
    goes = payload.get("goes_to") or {}
    figs = payload.get("figures") or []
    task = (row.get("trigger") or "::").split(":", 2)[-1]
    return {
        "kind": "proposal", "id": row["proposal_id"], "title": payload.get("title") or row["rule_id"],
        "rule_id": row.get("rule_id"), "role": goes.get("role") or row.get("target_key"),
        "office": goes.get("office"), "addressed_to": payload.get("addressed_to"),
        "proposed": payload.get("proposed"), "figures": figs[:3], "check": check_text,
        "created_at": row.get("created_at"), "subject": row.get("subject_id"), "task": task,
        "href": f"/runs/{row['run_id']}", "run_id": row["run_id"], "copies": copies,
        "answer": (f"Decide on the run page: {payload.get('title')}. Goes to "
                   f"{goes.get('role')}. {check_text}"),
    }


def lanes(q_app: QueryFn, q_user: QueryFn | None = None) -> dict:
    """The whole queue, sorted into decide / unblock / system, with the page's
    answer line. Three reads as the app (plus who holds which role, on the
    caller's token); everything after them is code."""
    t = H.tables()
    held = _section(lambda: [r["role"] for r in q_user(H.held_roles(t), {})]) if q_user \
        else {"rows": [], "error": identity.obo_missing_reason()}
    rules = q_app(H.lane_rules(t), {})
    exceptions = q_app(H.lane_exceptions(t), {})
    proposals = q_app(H.lane_proposals(t), {})
    live_v = live_versions(q_app(H.lane_current(t), {}))
    retired = _section(lambda: q_user(H.lane_retired(t), {})) if q_user \
        else {"rows": [], "error": identity.obo_missing_reason()}
    decide, system = [], {}

    def sys_add(group: str, item: dict) -> None:
        system.setdefault(group, []).append(item)

    for x in exceptions:
        lane, answer = exception_lane(x, live_v)
        item = {"kind": "exception", "id": x["exception_id"],
                "title": f"{x['rule_id']} v{x['rule_version']} on "
                         f"{', '.join(_arr(x.get('subject_ids')))}",
                "role": x["owner_role"], "office": x["owner_office"], "answer": answer,
                "status": x["status"], "created_at": x.get("detected_at"),
                "href": f"/work/exceptions/{x['exception_id']}",
                "amount": amount_figure(x) if lane == "decide" else None}
        if lane == "decide":
            decide.append(item)
        else:
            sys_add("Test, superseded and closed exceptions", item)

    # SI proposals, grouped by what they are about: (task, subject, rule, kind).
    # The newest pending, checked copy is the Decide item; older pending copies
    # are repeats. A pending copy older than one already applied or rejected was
    # answered by that decision, so it goes to System too.
    groups: dict[tuple, list[tuple[dict, dict]]] = {}
    decided_at: dict[tuple, str] = {}
    for row in proposals:
        try:
            payload = json.loads(row.get("proposed_payload") or "{}")
        except ValueError:
            payload = {}
        if row.get("intake_outcome") != "si_run":
            sys_add("Proposals with no exception and no run page", {
                "kind": "proposal", "id": row["proposal_id"],
                "title": f"{row.get('target_table')} proposal from run {str(row.get('run_id'))[:8]}",
                "answer": "Names no exception and was not made by a page run, so no one can "
                          "decide it. Void it.", "status": row["status"],
                "created_at": row.get("created_at"), "href": None})
            continue
        task = (row.get("trigger") or "::").split(":", 2)[-1]
        key = (task, row.get("subject_id"), row.get("rule_id"), row.get("target_table"))
        if row["status"] in ("applied", "rejected"):
            decided_at[key] = max(decided_at.get(key, ""), row.get("created_at") or "")
            continue
        if row["status"] != "pending":
            if row["status"] == "blocked":
                sys_add("Blocked proposals", {
                    "kind": "proposal", "id": row["proposal_id"], "title": payload.get("title"),
                    "answer": row.get("block_reason") or "Blocked.", "status": "blocked",
                    "created_at": row.get("created_at"), "href": f"/runs/{row['run_id']}"})
            continue
        groups.setdefault(key, []).append((row, payload))
    for key, members in groups.items():
        members.sort(key=lambda m: m[0].get("created_at") or "", reverse=True)
        answered = decided_at.get(key)
        if answered:
            for r, p in [m for m in members if (m[0].get("created_at") or "") <= answered]:
                sys_add("Answered by a later decision", {
                    "kind": "proposal", "id": r["proposal_id"], "title": p.get("title"),
                    "answer": "A newer copy of this proposal was already decided; no action.",
                    "status": r["status"], "created_at": r.get("created_at"),
                    "href": f"/runs/{r['run_id']}"})
            members = [m for m in members if (m[0].get("created_at") or "") > answered]
        passed = [(r, p, txt) for r, p in members for ok, txt in [proposal_check(r)] if ok]
        if passed:
            r, p, txt = passed[0]
            # copies counts the older checked repeats only; copies that failed or
            # were never checked are listed under System with their own reason.
            decide.append(_proposal_item(r, p, txt, copies=len(passed) - 1))
            newest = r["proposal_id"]
        else:
            newest = None
        for r, p in members:
            if r["proposal_id"] == newest:
                continue
            ok, txt = proposal_check(r)
            if ok:
                group, answer = "Repeat runs (an older copy of an item in Decide)", (
                    "A newer run proposed the same thing; decide that one.")
            else:
                group, answer = "Proposals that did not pass the checker", txt
            sys_add(group, {"kind": "proposal", "id": r["proposal_id"], "title": p.get("title"),
                            "answer": answer, "status": r["status"],
                            "created_at": r.get("created_at"), "href": f"/runs/{r['run_id']}"})

    # Unblock: the latest version of each rule that cannot run, by root cause.
    latest: dict[str, dict] = {}
    for r in rules:
        if r["rule_id"] not in latest or int(r["version"]) > int(latest[r["rule_id"]]["version"]):
            latest[r["rule_id"]] = r
    causes: dict[tuple, dict] = {}
    for r in sorted(latest.values(), key=lambda r: r["rule_id"]):
        if not str(r["status"]).startswith("blocked") or r["rule_id"] in live_v:
            continue
        k = (r["status"], r.get("blocked_reason") or "No reason recorded.")
        c = causes.setdefault(k, {"status": r["status"], "reason": k[1], "rules": [],
                                  "offices": set()})
        c["rules"].append(r["rule_id"])
        c["offices"].add(r.get("owner_office") or r.get("owner_role"))
    unblock = [{**c, "offices": sorted(o for o in c["offices"] if o),
                "kind_label": "Missing feed" if c["status"] == "blocked_no_source"
                else "Parameter not set"} for c in causes.values()]
    unblock.sort(key=lambda c: (-len(c["rules"]), c["reason"]))

    multi = {} if retired["error"] else unretired_active(
        rules, {(r["rule_id"], int(r["version"])) for r in retired["rows"]})
    for rid, vs in sorted(multi.items()):
        if len(vs) > 1:
            sys_add("Rule defects", {
                "kind": "rule", "id": rid, "title": f"{rid}: {len(vs)} live versions "
                                                    f"(v{', v'.join(map(str, vs))})",
                "answer": f"Only one version should be live. Retire all but v{vs[-1]}.",
                "status": "defect", "created_at": None, "href": f"/rules/{rid}"})

    if retired["error"]:
        sys_add("Rule defects", {
            "kind": "rule", "id": "defect-check", "title": "Rule versions were not checked",
            "answer": "Whether a rule has more than one unretired active version could not be "
                      "read: " + retired["error"][:200], "status": "unchecked",
            "created_at": None, "href": None})

    # A Decide item routed to a role no one holds can be decided by no one.
    # It stays in Decide (the decision is real) and its role gap goes to Unblock.
    vacant: dict[str, int] = {}
    for d in decide:
        if held["error"]:
            d["holder"] = None
        else:
            d["holder"] = d["role"] in held["rows"]
            if not d["holder"]:
                vacant[d["role"]] = vacant.get(d["role"], 0) + 1
    for role, n in sorted(vacant.items()):
        unblock.insert(0, {"status": "role_vacant", "kind_label": "Role with no holder",
                           "reason": f"No one holds {role} in role_map, so its {n} Decide "
                                     f"item{'s' if n != 1 else ''} cannot be decided.",
                           "rules": [], "offices": [role], "items": n})

    decide.sort(key=lambda d: d.get("created_at") or "", reverse=True)
    blocked_rules = sum(len(c["rules"]) for c in unblock)
    n_sys = sum(len(v) for v in system.values())
    n_causes = len(unblock) - len(vacant)
    roles: dict[str, int] = {}
    for d in decide:
        roles[d["role"] or "no role"] = roles.get(d["role"] or "no role", 0) + 1
    who = ", ".join(f"{n} for {r}" for r, n in sorted(roles.items()))
    answer = ((f"{len(decide)} decision{'s' if len(decide) != 1 else ''} waiting ({who}). "
               if decide else "Nothing needs a decision. ") +
              (f"{n_causes} missing feeds or parameters keep " if n_causes != 1
               else "1 missing feed or parameter keeps ") +
              f"{blocked_rules} rule{'s' if blocked_rules != 1 else ''} from running" +
              (f", and {len(vacant)} owner role{'s' if len(vacant) != 1 else ''} "
               f"({', '.join(sorted(vacant))}) {'have' if len(vacant) != 1 else 'has'} no holder. "
               if vacant else ". ") +
              f"{n_sys} system item{'s' if n_sys != 1 else ''} need no business action.")
    if held["error"]:
        answer += " Whether each owner role has a holder could not be checked: " + \
            held["error"][:160]
    return {"answer": answer, "decide": decide, "unblock": unblock, "roles_error": held["error"],
            "system": [{"group": g, "items": sorted(v, key=lambda i: i.get("created_at") or "",
                                                    reverse=True)}
                       for g, v in system.items()],
            "counts": {"decide": len(decide), "unblock": len(unblock),
                       "blocked_rules": blocked_rules, "system": n_sys}}


# Outcome codes that are about the caller's authority (403) rather than the
# state of the record (409). Kept here so the JSON API and the pages agree.
AUTHORITY_CODES = {"no_role", "not_owner", "role_cannot_act", "not_evaluated"}


def act(q_user: QueryFn | None, *, proposal_id: str, action: str, confirmed_record_ids: list[str],
        notes: str | None, request_id: str | None = None) -> dict:
    """Apply or reject, as the caller, in one transaction. Returns the server's outcome."""
    if action not in ("apply", "reject"):
        raise ValueError("action must be apply or reject")
    if q_user is None:
        return {"reason_code": "not_evaluated", "reason": identity.obo_missing_reason(),
                "decision_id": None, "allowed": False}
    confirmed = json.dumps(sorted(str(r) for r in confirmed_record_ids), separators=(",", ":"))
    rows = q_user(H.apply_block(H.tables()), {
        "proposal_id": proposal_id, "action": action, "confirmed_records": confirmed,
        "request_id": request_id or str(uuid.uuid4()), "notes": notes or None})
    out = dict(rows[0])
    # live._cast leaves BOOLEAN as the API's text, and the string 'false' is truthy.
    out["replayed"] = str(out.get("replayed")).lower() == "true"
    return {**out, "allowed": out["reason_code"] == "allowed"}


def status_for(outcome: dict) -> int:
    if outcome["allowed"]:
        return 200
    return 403 if outcome["reason_code"] in AUTHORITY_CODES else 409


# ------------------------------------------------------------------ JSON API
router = APIRouter(prefix="/api/v1", tags=["work queue"])


class ActBody(BaseModel):
    """What a caller sends to apply or reject. Nothing else is accepted.

    extra='forbid' rejects any other field with 422, so a role, an actor or an
    authority claim in a request body is refused before anything runs.
    """
    model_config = ConfigDict(extra="forbid")
    confirmed_record_ids: list[str] = Field(
        description="The record ids the confirmation showed. Must match the proposal's.")
    notes: str | None = Field(default=None, max_length=2000)
    request_id: str | None = Field(default=None, max_length=64)


@router.get("/me")
def me(request: Request):
    """Who the server thinks is calling, and the roles Unity Catalog resolves for them."""
    ident, _q_app, q_user = runners(request)
    roles = _section(lambda: q_user(H.my_roles(H.tables()), {})) if q_user else \
        {"rows": [], "error": identity.obo_missing_reason()}
    return {"email": ident.email, "obo": q_user is not None,
            "roles": roles["rows"], "roles_error": roles["error"]}


@router.get("/exceptions")
def api_exceptions(request: Request, area: str | None = None, status: str | None = None,
                   owner_role: str | None = None, rule_id: str | None = None,
                   sort: str = "detected_at", descending: bool = True,
                   page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=PAGE_SIZE_MAX)):
    _ident, q_app, _q_user = runners(request)
    return list_exceptions(q_app, filters={"area": area, "status": status,
                                           "owner_role": owner_role, "rule_id": rule_id},
                           sort=sort, descending=descending, page=page, page_size=page_size)


@router.get("/exceptions/{exception_id}")
def api_exception(request: Request, exception_id: str):
    _ident, q_app, q_user = runners(request)
    card = exception_card(q_app, q_user, exception_id)
    if card is None:
        raise HTTPException(404, "no exception with this id")
    return card


@router.get("/proposals/{proposal_id}/authority")
def api_authority(request: Request, proposal_id: str, action: str = Query(pattern="^(apply|reject)$")):
    _ident, _q_app, q_user = runners(request)
    return authority_for(q_user, proposal_id, action)


def _act_route(request: Request, proposal_id: str, action: str, body: ActBody):
    _ident, _q_app, q_user = runners(request)
    if action == "reject" and not (body.notes or "").strip():
        raise HTTPException(422, "a reason is required to reject")
    out = act(q_user, proposal_id=proposal_id, action=action,
              confirmed_record_ids=body.confirmed_record_ids, notes=body.notes,
              request_id=body.request_id)
    from fastapi.responses import JSONResponse
    return JSONResponse(out, status_code=status_for(out))


@router.post("/proposals/{proposal_id}/apply")
def api_apply(request: Request, proposal_id: str, body: ActBody):
    return _act_route(request, proposal_id, "apply", body)


@router.post("/proposals/{proposal_id}/reject")
def api_reject(request: Request, proposal_id: str, body: ActBody):
    return _act_route(request, proposal_id, "reject", body)


# ---------------------------------------------------------------- provenance
# A-13: look up the full provenance of any figure rendered on a recent page.
# The data lives in the in-process cache populated by envelopes.figure().

@router.get("/provenance/{provenance_id}")
def api_provenance(provenance_id: str):
    prov = E.get_provenance(provenance_id)
    if prov is None:
        raise HTTPException(404, "Provenance not found. It may have been "
                            "evicted from cache. Reload the page that "
                            "showed this figure, then try again.")
    return prov


@router.get("/provenance/{provenance_id}/records")
def api_provenance_records(provenance_id: str,
                           page: int = Query(1, ge=1),
                           page_size: int = Query(100, ge=1, le=1000)):
    prov = E.get_provenance(provenance_id)
    if prov is None:
        raise HTTPException(404, "Provenance not found. It may have been "
                            "evicted from cache. Reload the page that "
                            "showed this figure, then try again.")
    all_ids = prov.get("record_ids", [])
    start = (page - 1) * page_size
    page_ids = all_ids[start : start + page_size]
    return {
        "provenance_id": provenance_id,
        "record_count": len(all_ids),
        "page": page,
        "page_size": page_size,
        "records": [
            {"record_id": rid, "source_table": prov.get("source"),
             "rule": prov.get("rule")}
            for rid in page_ids
        ],
    }


# --------------------------------------------------------------- rule register

def _rule_view(row: dict) -> dict:
    """Shape a rule_register row for the API."""
    return {
        "rule_id": row["rule_id"], "version": row["version"],
        "status": row.get("status"), "blocked_reason": row.get("blocked_reason"),
        "statement_text": row.get("statement_text"),
        "params": json.loads(row["params"]) if isinstance(row.get("params"), str) else row.get("params"),
        "value_lists": json.loads(row["value_lists"]) if isinstance(row.get("value_lists"), str) else row.get("value_lists"),
        "owner_role": row.get("owner_role"), "owner_office": row.get("owner_office"),
        "required_action": row.get("required_action"), "area": row.get("area"),
        "effective_from": row.get("effective_from"), "effective_to": row.get("effective_to"),
        # A-30: derived state; current_rules rows are current by definition.
        "lifecycle": row.get("lifecycle") or row.get("status"),
        "superseded_by": row.get("superseded_by"),
    }


def list_rules(q_app: QueryFn, *, filters: dict | None = None) -> dict:
    """Rule register list with open-exception counts."""
    f = filters or {}
    t = H.tables()
    params = {"area": f.get("area"), "status": f.get("status"),
              "owner_role": f.get("owner_role")}
    rules = _section(lambda: q_app(H.rule_list(t), params))
    items = []
    for r in rules["rows"]:
        v = _rule_view(r)
        v["open_count"] = count_figure(
            int(r.get("open_count", 0)),
            label="Open exceptions",
            computation=f"COUNT of open exceptions for rule {r['rule_id']}")
        v["open_dollars"] = E.figure(
            figure_id=f"rule.{r['rule_id']}.open_dollars",
            label="Open exception dollars", unit="USD",
            value=str(r.get("open_dollars", 0)),
            as_of=None, record_ids=[], source="aircarrier_app_exceptions",
            computation=f"SUM dollar_amount of open exceptions for rule {r['rule_id']}")
        items.append(v)
    return {"rules": items, "rules_error": rules["error"]}


def rule_card(q_app: QueryFn, rule_id: str) -> dict | None:
    """One rule: all versions + audit log."""
    t = H.tables()
    versions = _section(lambda: q_app(H.rule_detail(t), {"rule_id": rule_id}))
    if not versions["rows"]:
        return None
    audit = _section(lambda: q_app(H.rule_audit(t), {"rule_id": rule_id}))
    return {
        "rule_id": rule_id,
        "versions": [_rule_view(v) | {"created_by": v.get("created_by"),
                                       "created_at": v.get("created_at"),
                                       "expression_sql": v.get("expression_sql")}
                      for v in versions["rows"]],
        "versions_error": versions["error"],
        "audit": audit["rows"], "audit_error": audit["error"],
    }


@router.get("/rules")
def api_rules(request: Request, area: str | None = None, status: str | None = None,
              owner_role: str | None = None):
    _ident, q_app, _q_user = runners(request)
    return list_rules(q_app, filters={"area": area, "status": status,
                                      "owner_role": owner_role})


@router.get("/rules/{rule_id}")
def api_rule(request: Request, rule_id: str):
    _ident, q_app, _q_user = runners(request)
    card = rule_card(q_app, rule_id)
    if card is None:
        raise HTTPException(404, "no rule with this id")
    return card


# -------------------------------------------------------------------- preview

from collections import OrderedDict as _OD
from datetime import datetime, timedelta, timezone

_PREVIEW_TTL = timedelta(minutes=10)
_PREVIEW_CACHE_MAX = 50
_preview_cache: _OD = _OD()  # preview_id -> {rule_id, params, expires_at, before, after, ...}


def _cache_preview(pid: str, data: dict) -> None:
    _preview_cache[pid] = data
    _preview_cache.move_to_end(pid)
    while len(_preview_cache) > _PREVIEW_CACHE_MAX:
        _preview_cache.popitem(last=False)


def get_preview(preview_id: str) -> dict | None:
    p = _preview_cache.get(preview_id)
    if p and datetime.now(timezone.utc) < p["expires_at"]:
        return p
    return None


def _extract_subjects(hits: list[dict]) -> list[tuple]:
    """Extract sorted subject_ids tuples from detection hits."""
    seen, out = set(), []
    for h in hits:
        ids = []
        # Same order as ops/harness/evaluate._extract_subject_ids (A-28).
        for key in ("parent_exception_id", "subject_ids", "exception_id", "model_run_id",
                    "proposal_id", "document_id", "transaction_id"):
            v = h.get(key)
            if v is not None:
                ids = [str(x) for x in v] if isinstance(v, list) else [str(v)]
                break
        if not ids:
            ids = [str(v) for v in h.values() if v is not None and isinstance(v, str) and len(str(v)) < 100][:10]
        key = tuple(sorted(ids))
        if key not in seen:
            seen.add(key)
            out.append(key)
    return out


def _sum_dollars(hits: list[dict]) -> str | None:
    total, any_d = 0.0, False
    for h in hits:
        for k in ("dollar_amount", "amount", "total", "value"):
            v = h.get(k)
            if v is not None:
                try:
                    total += float(v)
                    any_d = True
                    break
                except (TypeError, ValueError):
                    pass
    return str(total) if any_d else None


def _count_fig(n: int, label: str, rule_id: str) -> dict:
    return count_figure(n, label=label,
                        computation=f"{label} for rule {rule_id} preview")


def _dollar_fig(amount: str | None, label: str, rule_id: str) -> dict:
    return E.figure(figure_id=f"preview.{rule_id}.{label.replace(' ', '_')}",
                    label=label, unit="USD", value=amount or "0",
                    as_of=None, record_ids=[], source="preview",
                    computation=f"{label} for rule {rule_id} preview")


def preview_rule(q_app: QueryFn, rule_id: str, base_version: int,
                 proposed_params: dict | None = None) -> dict:
    """Non-writing before/after preview. Returns spec-shaped response or raises."""
    t = H.tables()
    rows = q_app(H.rule_for_preview(t), {"rule_id": rule_id})
    if not rows:
        raise HTTPException(404, "no active rule with this id")
    rule = rows[0]
    current_version = rule.get("version")
    if current_version != base_version:
        raise HTTPException(409, f"stale: current version is {current_version}, "
                            f"not {base_version}")
    expr = rule.get("expression_sql")
    if not expr:
        raise HTTPException(409, "rule has no expression_sql; preview cannot run")

    current_params = json.loads(rule["params"]) if isinstance(rule.get("params"), str) else (rule.get("params") or {})
    gate = _parent_gate(q_app, t, rule_id,
                        proposed_params if proposed_params is not None else current_params)
    if gate:
        raise HTTPException(409, gate)

    # Run detection with current params → before
    sql_before, args_before = H.bind_expression(expr, t, current_params)
    before_hits = q_app(sql_before, args_before)

    # Run detection with proposed params → after
    use_params = proposed_params if proposed_params is not None else current_params
    sql_after, args_after = H.bind_expression(expr, t, use_params)
    after_hits = q_app(sql_after, args_after)

    before_keys = set(_extract_subjects(before_hits))
    after_keys = set(_extract_subjects(after_hits))
    added = sorted(after_keys - before_keys)
    removed = sorted(before_keys - after_keys)

    now = datetime.now(timezone.utc)
    preview_id = str(uuid.uuid4())

    result = {
        "preview_id": preview_id,
        "rule_id": rule_id,
        "base_version": base_version,
        "evaluated_at": now.isoformat(),
        "before": {
            "count": _count_fig(len(before_keys), "Before count", rule_id),
            "dollar_total": _dollar_fig(_sum_dollars(before_hits), "Before dollars", rule_id),
        },
        "after": {
            "count": _count_fig(len(after_keys), "After count", rule_id),
            "dollar_total": _dollar_fig(_sum_dollars(after_hits), "After dollars", rule_id),
        },
        "delta": {
            "count": _count_fig(len(after_keys) - len(before_keys), "Delta count", rule_id),
            "dollar_total": _dollar_fig(
                str((float(_sum_dollars(after_hits) or 0)) - (float(_sum_dollars(before_hits) or 0))),
                "Delta dollars", rule_id),
        },
        "added_href": f"/api/v1/rules/{rule_id}/preview/{preview_id}/added",
        "removed_href": f"/api/v1/rules/{rule_id}/preview/{preview_id}/removed",
        "added_count": len(added),
        "removed_count": len(removed),
        "expires_at": (now + _PREVIEW_TTL).isoformat(),
    }

    # Cache for POST /versions validation and added/removed endpoints
    _cache_preview(preview_id, {
        **result,
        "params": use_params,
        "added": [list(k) for k in added],
        "removed": [list(k) for k in removed],
        "expires_at": now + _PREVIEW_TTL,
    })

    return result


def _params_of(row: dict) -> dict:
    p = row.get("params")
    return json.loads(p) if isinstance(p, str) else (p or {})


def _parent_gate(q_app: QueryFn, t: dict, rule_id: str, params: dict) -> str | None:
    """Same rule as ops/harness/evaluate._parent_gate (A-29): a derived rule
    (params.source_rule) runs only while its source chain is current."""
    if not (params or {}).get("source_rule"):
        return None
    current = {r["rule_id"]: _params_of(r) for r in q_app(H.current_rule_params(t), {})}
    seen, p = {rule_id}, params
    while p and p.get("source_rule"):
        parent = str(p["source_rule"])
        if parent in seen:
            return f"source_rule chain loops back to {parent}; not run"
        seen.add(parent)
        if parent not in current:
            latest = q_app(H.latest_rule_state(t), {"rule_id": parent})
            if not latest:
                state = "is not in the rule register"
            else:
                r = latest[0]
                state = f"has no version in effect (latest v{r.get('version')}, {r.get('status')}"
                state += f": {r['blocked_reason']})" if r.get("blocked_reason") else ")"
            return (f"source rule {parent} {state}; {rule_id} escalates {parent} "
                    f"exceptions, so it does not run until {parent} does")
        p = current[parent]
    return None


class PreviewBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    base_version: int = Field(description="The version the caller sees as current.")
    params: dict | None = Field(default=None, description="Proposed params override.")
    value_lists: dict | None = Field(default=None, description="Proposed value_lists override.")


@router.post("/rules/{rule_id}/preview")
def api_preview(request: Request, rule_id: str, body: PreviewBody):
    _ident, q_app, _q_user = runners(request)
    return preview_rule(q_app, rule_id, body.base_version, body.params)


@router.get("/rules/{rule_id}/preview/{preview_id}/added")
def api_preview_added(rule_id: str, preview_id: str,
                     page: int = Query(1, ge=1),
                     page_size: int = Query(100, ge=1, le=1000)):
    p = get_preview(preview_id)
    if p is None:
        raise HTTPException(404, "Preview not found or expired. Run a new preview.")
    all_items = p.get("added", [])
    start = (page - 1) * page_size
    return {"preview_id": preview_id, "rule_id": rule_id,
            "total": len(all_items), "page": page, "page_size": page_size,
            "items": all_items[start:start + page_size]}


@router.get("/rules/{rule_id}/preview/{preview_id}/removed")
def api_preview_removed(rule_id: str, preview_id: str,
                       page: int = Query(1, ge=1),
                       page_size: int = Query(100, ge=1, le=1000)):
    p = get_preview(preview_id)
    if p is None:
        raise HTTPException(404, "Preview not found or expired. Run a new preview.")
    all_items = p.get("removed", [])
    start = (page - 1) * page_size
    return {"preview_id": preview_id, "rule_id": rule_id,
            "total": len(all_items), "page": page, "page_size": page_size,
            "items": all_items[start:start + page_size]}
