"""Where SI runs are kept, who may decide on a proposal, and the decision itself.

Two modes, chosen by AIRCARRIER_SI_PERSIST:

  memory (default)  runs, steps, verdicts, proposals, decisions and the activity
                    log live in this process (the last MAX_RUNS runs). Every
                    receipt says so. Nothing is written to Unity Catalog.
  delta             the same rows are also written to the harness tables
                    (agent_runs, agent_steps, checker_verdicts, proposals,
                    decisions) on the CALLER's on-behalf-of token, so
                    current_user() is the person who asked or decided. No new
                    table and no new column is needed: SI rows are told apart
                    by agent_runs.trigger 'si:<page>:<task>' and
                    proposals.intake_outcome 'si_run'.

Authority is the same rule the work queue uses, applied to the role a
proposal goes to instead of an exception's owner: the caller holds that role
in role_map, in effect now, and the role holds the action on 'proposals' in
authority. The role a proposal goes to was set by code (tasks.py), never by a
model. The decision statement re-tests the rule inside the write, so a
stale page cannot decide on a role the caller no longer holds.
"""
from __future__ import annotations

import json
import os
import re
import threading
import uuid
from collections import OrderedDict, deque
from typing import Callable

from ..sqlsafe import Fragment, compose
from .sdk import Run, now_iso

QueryFn = Callable[[str, dict], list[dict]]
MAX_RUNS = int(os.environ.get("AIRCARRIER_SI_MAX_RUNS", "200"))


def mode() -> str:
    return "delta" if os.environ.get("AIRCARRIER_SI_PERSIST", "memory") == "delta" else "memory"


class Store:
    def __init__(self, max_runs: int = MAX_RUNS):
        self.runs: OrderedDict[str, Run] = OrderedDict()
        self.activity: deque[dict] = deque(maxlen=2000)
        self.max_runs = max_runs
        self._lock = threading.Lock()

    def add(self, run: Run) -> None:
        with self._lock:
            self.runs[run.run_id] = run
            while len(self.runs) > self.max_runs:
                self.runs.popitem(last=False)

    def get(self, run_id: str) -> Run | None:
        return self.runs.get(run_id)

    def list(self, limit: int = 50, page: str | None = None) -> list[Run]:
        rs = [r for r in reversed(self.runs.values()) if not page or r.page == page]
        return rs[:limit]

    def log(self, *, actor: str | None, actor_kind: str, action: str, run_id: str | None,
            detail: str, role: str | None = None) -> dict:
        e = {"at": now_iso(), "actor": actor or "unknown", "actor_kind": actor_kind,
             "role": role, "action": action, "run_id": run_id, "detail": detail}
        with self._lock:
            self.activity.appendleft(e)
        return e


STORE = Store()


# ------------------------------------------------------------------- load
# A run lives in this process until the app restarts. With PERSIST=delta it
# was also written to the harness tables, so a run that is no longer in memory
# is rebuilt from those rows. Nothing is recomputed: events, verdicts and each
# proposal (with the figures it was shown with) are read back as written.
# Deciding a loaded run goes through decide() and decision_statement(), which
# re-test the caller's role and the proposal's pending status inside the write.
def _table_to_verdict(v: str) -> str:
    return {t: k for k, t in VERDICT_TO_TABLE.items()}.get(v, v)


def load_sql(t: dict[str, str]) -> dict[str, str]:
    from ..harness_sql import iso                  # the one ISO-8601 UTC formatter
    return {
        "run": compose("""SELECT run_id, trigger, triggered_by, {started} AS started_at,
  {ended} AS ended_at, subject_kind, subject_id, specialist, outcome
FROM {tbl} WHERE run_id = :run_id AND trigger LIKE 'si:%'
ORDER BY ended_at DESC NULLS LAST LIMIT 1""",
            started=iso("started_at"), ended=iso("ended_at"), tbl=t["agent_runs"]),
        "steps": compose("""SELECT step_seq, agent_name, model_endpoint, rule_id, output_json, actor_kind,
  {stepped} AS stepped_at
FROM {tbl} WHERE run_id = :run_id ORDER BY step_seq""",
            stepped=iso("stepped_at"), tbl=t["agent_steps"]),
        "verdicts": compose("""SELECT checker_agent, verdict, to_json(checks) AS checks, notes, model_endpoint,
  {decided} AS decided_at
FROM {tbl} WHERE run_id = :run_id ORDER BY step_seq""",
            decided=iso("decided_at"), tbl=t["checker_verdicts"]),
        "proposals": compose("""SELECT proposal_id, status, block_reason, proposed_payload, rule_id
FROM {tbl} WHERE run_id = :run_id AND intake_outcome = 'si_run'
ORDER BY created_at, proposal_id""", tbl=t["proposals"]),
    }


def _json(v, default):
    if v is None or v == "":
        return default
    if isinstance(v, (list, dict)):
        return v
    try:
        return json.loads(v)
    except ValueError:
        return default


def load_run(run_id: str, q: QueryFn, t: dict[str, str]) -> Run | None:
    """Rebuild one SI run from the harness tables, or None if it was never written."""
    from . import sdk, tasks
    sql = load_sql(t)
    rows = q(sql["run"], {"run_id": run_id})
    if not rows:
        return None
    r = rows[0]
    _si, page, task_id = (r["trigger"].split(":", 2) + ["", ""])[:3]
    tpl = tasks.TASKS.get(task_id)
    if tpl is None:
        return None
    run = Run(tpl, r["subject_id"] or "", {}, page=page or "/", asked_by=r.get("triggered_by"))
    run.run_id = r["run_id"]
    run.started_at, run.ended_at = r.get("started_at"), r.get("ended_at")
    outcome = (r.get("outcome") or "").split(":", 1)
    run.status = outcome[0].strip() or "ready"
    run.error = outcome[1].strip() if len(outcome) > 1 else None
    names = {a.key: a.name for a in (sdk.ORCHESTRATOR, sdk.RECORDS_CHECKER, sdk.CANVAS,
                                     tpl.specialist)}
    kinds = {a.key: a.kind for a in (sdk.ORCHESTRATOR, sdk.RECORDS_CHECKER, sdk.CANVAS,
                                     tpl.specialist)}
    for s in q(sql["steps"], {"run_id": run_id}):
        out = _json(s.get("output_json"), {})
        key = out.get("reported_for") or s.get("agent_name") or "orchestrator"
        run.events.append({"seq": int(s["step_seq"]), "at": s.get("stepped_at"),
                           "agent": names.get(key, key), "agent_key": key,
                           "agent_kind": kinds.get(key, "agent"), "kind": out.get("kind", "step"),
                           "text": out.get("text", ""), "rule": s.get("rule_id"),
                           "data": out.get("data") or {},
                           "actor_kind": s.get("actor_kind") or "agent",
                           "by": s.get("model_endpoint") or "code"})
    for v in q(sql["verdicts"], {"run_id": run_id}):
        name = (v.get("checker_agent") or "").removeprefix("si:") or "checker"
        checks = [{"name": c.get("check_name"), "expected": c.get("expected"),
                   "actual": c.get("actual"), "result": c.get("result")}
                  for c in _json(v.get("checks"), [])]
        run.verdicts[name] = sdk.Verdict(checker=name,
                                         result=_table_to_verdict(v["verdict"]),
                                         checks=checks, notes=v.get("notes") or "",
                                         model=v.get("model_endpoint"),
                                         decided_at=v.get("decided_at") or "")
    for p in q(sql["proposals"], {"run_id": run_id}):
        pv = _json(p.get("proposed_payload"), {})
        goes = pv.get("goes_to") or {}
        run.proposals.append(sdk.Proposal(
            key=pv.get("key", ""), kind=pv.get("kind", ""), title=pv.get("title", ""),
            goes_to_role=goes.get("role", ""), goes_to_office=goes.get("office", ""),
            proposed=pv.get("proposed", ""), why=pv.get("why", ""),
            rule=pv.get("rule") or p.get("rule_id") or "",
            marked_blanks=pv.get("marked_blanks") or [], flags=pv.get("flags") or [],
            proposal_id=p["proposal_id"], status=p["status"], block_reason=p.get("block_reason"),
            drafted_by=pv.get("drafted_by", "code"), grounding=pv.get("grounding") or [],
            addressed_to=pv.get("addressed_to"), saved_figures=pv.get("figures") or []))
    if run.status == "ready" and run.proposals and not run.reviewable():
        run.status = "decided"
    run.persisted = {"mode": "delta", "ok": True, "error": None, "at": run.ended_at,
                     "note": "Loaded from the harness tables: this run is no longer held in "
                             "the app's memory. Events, verdicts and proposals are shown as "
                             "they were written."}
    run.loaded_from_tables = True
    return run


def decisions_sql(t: dict[str, str]) -> str:
    """Decisions on a run's proposals. Read on the CALLER's token: the app
    principal has no grant on the decisions table."""
    from ..harness_sql import iso
    return f"""SELECT decision_id, proposal_id, actor, actor_role, action, notes, authority_basis,
  {iso('decided_at')} AS decided_at
FROM {t['decisions']}
WHERE array_contains(from_json(:proposal_ids, 'array<string>'), proposal_id)
ORDER BY decided_at, decision_id"""


def load_decisions(run: Run, q_user: QueryFn | None, t: dict[str, str]) -> str | None:
    """Fill run.decisions for a run loaded from the tables, shaped as decide()
    records them. Returns why they could not be read, or None."""
    if not run.proposals:
        return None
    if q_user is None:
        return "Recorded decisions are read on your token, and this request has none."
    by_id = {p.proposal_id: p for p in run.proposals}
    try:
        rows = q_user(decisions_sql(t), {"proposal_ids": json.dumps(sorted(by_id))})
    except Exception as exc:  # noqa: BLE001 - shown on the page, not swallowed
        return f"Recorded decisions could not be read: {str(exc)[:240]}"
    run.decisions = [{
        "decision_id": d["decision_id"], "proposal_id": d["proposal_id"],
        "title": by_id[d["proposal_id"]].title if d["proposal_id"] in by_id else d["proposal_id"],
        "action": d["action"], "actor": d["actor"], "role": d.get("actor_role"),
        "office": by_id[d["proposal_id"]].goes_to_office if d["proposal_id"] in by_id else None,
        "at": d.get("decided_at"), "notes": d.get("notes"), "basis": d.get("authority_basis"),
        "persisted": "read from the decisions table"} for d in rows]
    return None


def get_run(run_id: str, q: QueryFn | None, t: dict[str, str], store: Store = STORE) -> Run | None:
    """A run started in this process comes from memory. Any other run is read
    from the harness tables on every call, so a decision recorded elsewhere (another
    app process, a notebook on the same person's token) shows at once instead of
    a stale 'pending'. It is also put in memory so the run log lists it."""
    run = store.get(run_id)
    if run is not None and not getattr(run, "loaded_from_tables", False):
        return run
    if q is None:
        return run
    run = load_run(run_id, q, t)
    if run is not None:
        store.add(run)
    return run


# ---------------------------------------------------------------- authority
def authority_sql(t: dict[str, str]) -> str:
    return f"""
WITH held AS (
  SELECT role, component FROM {t['role_map']}
  WHERE (uc_group = current_user() OR is_account_group_member(uc_group))
    AND effective_from <= current_timestamp()
    AND (effective_to IS NULL OR effective_to > current_timestamp())
)
SELECT current_user() AS evaluated_for,
  to_json((SELECT array_sort(collect_set(role)) FROM held)) AS roles,
  (SELECT count(*) FROM {t['authority']} a
    WHERE a.role = :owner_role AND a.target_table = 'proposals' AND a.action = :action)
    AS role_can_act,
  (SELECT count(*) FROM {t['role_map']}
    WHERE role = :owner_role AND effective_from <= current_timestamp()
      AND (effective_to IS NULL OR effective_to > current_timestamp())) AS holders,
  (SELECT min(component) FROM held WHERE role = :owner_role) AS component
"""


def _arr(v) -> list[str]:
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x) for x in v]
    return [str(x) for x in (json.loads(v) or [])]


def authority_decision(row: dict | None, *, owner_role: str, office: str, action: str) -> dict:
    """Pure. The server's answer to: may this caller take this action, and if
    not, the sentence that says why and who can."""
    if action not in ("apply", "reject"):
        return {"allowed": False, "reason_code": "bad_action",
                "reason": "The action is not apply or reject.", "handoff": None}
    if row is None:
        return {"allowed": False, "reason_code": "no_identity",
                "reason": "The request carries no user token, so no authority can be checked.",
                "handoff": None}
    roles, who = _arr(row.get("roles")), row.get("evaluated_for")
    holders = int(row.get("holders") or 0)
    handoff = ({"role": owner_role, "office": office,
                "text": f"Continue as {office}",
                "note": "It waits for that office in its queue."} if holders else
               {"role": owner_role, "office": office, "text": None,
                "note": f"No one holds {owner_role} in the role map yet, so this cannot be "
                        "applied until that office names a holder."})
    if not roles:
        return {"allowed": False, "reason_code": "no_role", "evaluated_for": who,
                "reason": f"{who} holds no role in the Air Carrier role map.", "handoff": handoff}
    if owner_role not in roles:
        return {"allowed": False, "reason_code": "not_owner", "evaluated_for": who,
                "reason": f"{office} ({owner_role}) owns this, and only that role can "
                          f"{action} it. You hold: {', '.join(roles)}.", "handoff": handoff}
    if int(row.get("role_can_act") or 0) == 0:
        return {"allowed": False, "reason_code": "role_cannot_act", "evaluated_for": who,
                "reason": f"The role {owner_role} may not {action} proposals.", "handoff": None}
    return {"allowed": True, "reason_code": "allowed", "evaluated_for": who,
            "role": owner_role, "component": row.get("component"),
            "reason": f"You hold {owner_role}, the role this goes to.", "handoff": None}


def check_authority(q_user: QueryFn | None, t: dict[str, str], owner_role: str, office: str,
                    action: str) -> dict:
    if q_user is None:
        return authority_decision(None, owner_role=owner_role, office=office, action=action)
    rows = q_user(authority_sql(t), {"owner_role": owner_role, "action": action})
    return authority_decision(rows[0] if rows else None, owner_role=owner_role, office=office,
                              action=action)


# ------------------------------------------------------------- delta writes
_CHECKS_T = Fragment("array<struct<check_name:string,expected:string,actual:string,result:string>>")
_GROUND_T = Fragment("array<struct<field:string,document_id:string,page:int,text_span:string>>")


# The SI rule book (tasks.RULEBOOK) is versioned as a whole. agent_steps requires
# every agent step to cite rule_id AND rule_version (CHECK citation_complete).
SI_RULEBOOK_VERSION = 1

# checker_verdicts.verdict_enum is ('pass','pass_with_exception','fail').
# error and not_run are not verdicts: no row is written; the step row says so.
VERDICT_TO_TABLE = {"pass": "pass", "pass_with_notes": "pass_with_exception", "fail": "fail"}

_STEP_T = Fragment("array<struct<seq:int,agent:string,model:string,rule:string,rule_version:int,"
                   "digest:string,output:string,at:string,actor_kind:string,basis:string>>")


def _step_rows(run: Run) -> list[dict]:
    """One row per event, shaped to satisfy citation_complete. An agent event
    with no rule (a fallback note, a model step whose rule was dropped) is kept
    as an orchestrator row that names the agent it reports for: nothing is
    dropped, and no rule is attached that the agent did not cite."""
    digest = run.pack.provenance_id if run.pack else f"subject:{run.subject}"
    rows = []
    for e in run.events:
        cited = bool(e["rule"])
        own = e["agent_key"] == "orchestrator" or cited
        out = {"kind": e["kind"], "text": e["text"], "data": e["data"]}
        if not own:
            out.update(reported_for=e["agent_key"], uncited=True)
        rows.append({"seq": int(e["seq"]),
                     "agent": e["agent_key"] if own else "orchestrator",
                     "model": None if e["by"] in ("code", "none") else e["by"],
                     "rule": e["rule"] if cited else None,
                     "rule_version": SI_RULEBOOK_VERSION if cited else None,
                     "digest": digest,
                     "output": json.dumps(out, default=str, ensure_ascii=False),
                     "at": e["at"], "actor_kind": e["actor_kind"],
                     "basis": "agent_own" if e["actor_kind"] == "agent" else "none"})
    return rows


def run_statements(run: Run, t: dict[str, str]) -> list[tuple[str, dict]]:
    """The statements that keep one run: who asked, which agents worked it, each
    step and its rule, both verdicts, and the proposals. Pure; tests read them.
    persist_run sends them as one transaction (run_transaction)."""
    spec = run.tpl.specialist
    out = [(compose("""INSERT INTO {tbl}
  (run_id, trigger, triggered_by, started_at, ended_at, orchestrator_version,
   mlflow_trace_id, subject_kind, subject_id, specialist, outcome)
VALUES (:run_id, :trigger, current_user(), to_timestamp(:started_at), to_timestamp(:ended_at),
        'si/1.0', NULL, :subject_kind, :subject_id, :specialist, :outcome)""",
                     tbl=t["agent_runs"]),
            {"run_id": run.run_id, "trigger": f"si:{run.page}:{run.task_id}",
             "started_at": run.started_at, "ended_at": run.ended_at or now_iso(),
             "subject_kind": run.tpl.subject_kind, "subject_id": run.subject,
             "specialist": spec.key, "outcome": run.status if not run.error
             else f"{run.status}: {run.error}"[:500]})]
    if run.events:
        out.append((compose("""INSERT INTO {tbl}
  (run_id, step_seq, agent_name, agent_version, model_endpoint, rule_id, rule_version,
   record_ids, inputs_digest, output_json, tokens, latency_ms, prompt_sha, stepped_at,
   actor_kind, authority_basis)
SELECT :run_id, s.seq, s.agent, 'si/1.0', s.model, s.rule, s.rule_version,
       ARRAY(s.digest), s.digest, s.output, NULL, NULL, NULL, to_timestamp(s.at),
       s.actor_kind, s.basis
FROM (SELECT inline(from_json(:steps, '{step_t}'))) AS s""",
                            tbl=t["agent_steps"], step_t=_STEP_T),
                    {"run_id": run.run_id,
                     "steps": json.dumps(_step_rows(run), ensure_ascii=False)}))
    for n, (name, v) in enumerate(run.verdicts.items()):
        if v.result not in VERDICT_TO_TABLE:
            continue
        seq = next((e["seq"] for e in run.events if e["kind"] == "verdict"
                    and e["agent_key"] == name), 0)
        out.append((compose("""INSERT INTO {tbl}
  (run_id, step_seq, verdict, checks, notes, checker_agent, model_endpoint, decided_at)
VALUES (:run_id, CAST(:seq AS INT), :verdict, from_json(:checks, '{checks_t}'), :notes,
        :checker, :model,
        to_timestamp(:at))""", tbl=t["checker_verdicts"], checks_t=_CHECKS_T),
                    {"run_id": run.run_id, "seq": seq, "verdict": VERDICT_TO_TABLE[v.result],
                     "checks": json.dumps([{"check_name": c["name"], "expected": c["expected"],
                                            "actual": c["actual"], "result": c["result"]}
                                           for c in v.checks]),
                     "notes": v.notes[:12000], "checker": f"si:{name}", "model": v.model,
                     "at": v.decided_at}))
    for p in run.proposals:
        out.append((compose("""INSERT INTO {tbl}
  (proposal_id, run_id, target_table, target_key, proposed_payload, grounding,
   schema_validation, status, block_reason, exception_id, rule_id, rule_version, record_ids,
   created_at, intake_outcome)
VALUES (:proposal_id, :run_id, :target_table, :target_key, :payload, CAST(NULL AS {ground_t}),
        'si/1.0', :status, :block_reason, NULL, :rule_id, NULL,
        from_json(:record_ids, 'array<string>'), current_timestamp(), 'si_run')""",
                            tbl=t["proposals"], ground_t=_GROUND_T),
                    {"proposal_id": p.proposal_id, "run_id": run.run_id,
                     "target_table": f"si:{p.kind}", "target_key": p.goes_to_role,
                     "payload": json.dumps(p.view(run.pack.facts if run.pack else {}),
                                           default=str, ensure_ascii=False),
                     "status": p.status, "block_reason": p.block_reason, "rule_id": p.rule,
                     "record_ids": json.dumps([run.pack.provenance_id] if run.pack else [])}))
    return out


def decision_statement(t: dict[str, str]) -> str:
    """One transaction. The decision row is written only if the caller holds the
    role now (re-tested here, not trusted from the page), and the proposal moves
    only if that decision row exists and the proposal is still pending."""
    return f"""
BEGIN ATOMIC
  INSERT INTO {t['decisions']}
    (decision_id, proposal_id, exception_id, actor, actor_role, action, decided_at,
     authority_check_result, notes, actor_kind, authority_basis)
  SELECT :decision_id, :proposal_id, NULL, current_user(), :owner_role, :action,
         current_timestamp(), 'allowed', :notes, 'human', :basis
  WHERE EXISTS (
    SELECT 1 FROM {t['role_map']} r JOIN {t['authority']} a ON a.role = r.role
    WHERE r.role = :owner_role
      AND (r.uc_group = current_user() OR is_account_group_member(r.uc_group))
      AND r.effective_from <= current_timestamp()
      AND (r.effective_to IS NULL OR r.effective_to > current_timestamp())
      AND a.target_table = 'proposals' AND a.action = :action);
  UPDATE {t['proposals']} SET status = :new_status
  WHERE proposal_id = :proposal_id AND status = 'pending'
    AND EXISTS (SELECT 1 FROM {t['decisions']} d WHERE d.decision_id = :decision_id);
END"""


def persist_run(run: Run, q_user: QueryFn | None, t: dict[str, str]) -> None:
    run.persisted = {"mode": mode(), "ok": None, "error": None, "at": None}
    if mode() != "delta":
        run.persisted.update(ok=True, note="Kept in this app process. Durable write is off "
                                           "(AIRCARRIER_SI_PERSIST=memory).")
        return
    if q_user is None:
        run.persisted.update(ok=False, error="No user token, so the run was not written.")
        return
    sql, params = run_transaction(run_statements(run, t))
    q_user(sql, params)
    run.persisted.update(ok=True, at=now_iso(),
                         note="Written to the harness tables in one transaction.")


def run_transaction(stmts: list[tuple[str, dict]]) -> tuple[str, dict]:
    """All of a run's statements as one BEGIN ATOMIC block, so a failed insert
    leaves no partial run. Each statement's parameters get a unique prefix."""
    body, params = [], {}
    for n, (sql, p) in enumerate(stmts):
        def sub(m, n=n):
            return f":s{n}_{m.group(1)}"
        body.append(re.sub(r"(?<![:\w]):(\w+)", sub, sql).strip())
        params.update({f"s{n}_{k}": v for k, v in p.items()})
    return "BEGIN ATOMIC\n" + ";\n".join(body) + ";\nEND", params


# ------------------------------------------------------------------ decide
def decide(run: Run, proposal_ids: list[str], action: str, notes: str | None,
           q_user: QueryFn | None, t: dict[str, str], store: Store = STORE) -> dict:
    """Apply or reject the ticked proposals of one run. Returns the receipt."""
    if action not in ("apply", "reject"):
        raise ValueError("action must be apply or reject")
    if action == "reject" and not (notes or "").strip():
        raise ValueError("a reason is required to reject")
    by_id = {p.proposal_id: p for p in run.proposals}
    unknown = [pid for pid in proposal_ids if pid not in by_id]
    if unknown:
        raise ValueError(f"not proposals of this run: {', '.join(unknown)}")
    auth_cache: dict[str, dict] = {}
    done, refused = [], []
    for pid in dict.fromkeys(proposal_ids):
        p = by_id[pid]
        if p.status != "pending":
            refused.append({"proposal_id": pid, "title": p.title, "reason_code": p.status,
                            "reason": p.block_reason or f"This proposal is already {p.status}.",
                            "handoff": None})
            continue
        a = auth_cache.get(p.goes_to_role)
        if a is None:
            a = auth_cache[p.goes_to_role] = check_authority(q_user, t, p.goes_to_role,
                                                             p.goes_to_office, action)
        if not a["allowed"]:
            refused.append({"proposal_id": pid, "title": p.title, **{k: a.get(k) for k in (
                "reason_code", "reason", "handoff")}})
            store.log(actor=a.get("evaluated_for"), actor_kind="human", action=f"{action}_refused",
                      run_id=run.run_id, detail=f"{p.title}: {a['reason']}")
            continue
        d = {"decision_id": str(uuid.uuid4()), "proposal_id": pid, "title": p.title,
             "action": action, "actor": a.get("evaluated_for"), "role": p.goes_to_role,
             "office": p.goes_to_office, "at": now_iso(), "notes": notes,
             "basis": "human_applied" if action == "apply" else "human_rejected",
             "persisted": mode()}
        if mode() == "delta":
            try:
                q_user(decision_statement(t), {
                    "decision_id": d["decision_id"], "proposal_id": pid,
                    "owner_role": p.goes_to_role, "action": action, "notes": notes,
                    "basis": d["basis"],
                    "new_status": "applied" if action == "apply" else "rejected"})
            except Exception as exc:  # noqa: BLE001 - rolled back; said in the receipt
                refused.append({"proposal_id": pid, "title": p.title, "reason_code": "write_failed",
                                "reason": "Nothing was recorded; the transaction rolled back. "
                                          + str(exc)[:240], "handoff": None})
                continue
        p.status = "applied" if action == "apply" else "rejected"
        run.decisions.append(d)
        done.append(d)
        store.log(actor=d["actor"], actor_kind="human", role=d["role"], action=action,
                  run_id=run.run_id, detail=p.title)
    if not run.reviewable() and run.status == "ready":
        run.status = "decided"
    n = len(dict.fromkeys(proposal_ids))
    verb = "applied" if action == "apply" else "rejected"
    who = done[0]["actor"] if done else None
    roles = sorted({d["role"] for d in done})
    text = (f"{len(done)} of {n} proposals {verb}" +
            (f" by {who} as {', '.join(roles)}" if done else "") + ".")
    where = ("Recorded in the harness tables on your token." if mode() == "delta" else
             "Recorded in this app session only; durable write is off "
             "(AIRCARRIER_SI_PERSIST=memory).")
    return {"run_id": run.run_id, "action": action, "done": done, "refused": refused,
            "text": text, "where": where, "mode": mode(), "run_status": run.status}
