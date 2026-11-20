"""Agent pre-check (A-34, WORK_QUEUE_V2 4.4 step 1). Code only, no model.

Before a specialist run starts, read what three or four queries can show:
the exception's status, whether it is test data, whether its rule version is
the one in force, and whether the rule it escalates (and the parent exception)
is live. If any blocking check fails, the orchestrator does not call a model;
it records the result as the run outcome and names the lane the item belongs
in (System or Unblock).

Checks, in order (the first failing blocking check sets the lane):
  open        status is 'open'                                  -> System
  G-a         no subject_id starts with test-wbs- and status is
              not void_test_data                                -> System
  G-b         rule_version is the version in current_rules      -> System
  G-c         every rule up the source_rule chain is current    -> Unblock
              and, for subject_type 'exception', each parent
              exception exists (else System) and is open        -> System
  G-e         owner_role is set, holds apply on proposals in
              authority, and has a role_map assignment in effect
              (a person or an account group)                    -> System
  G-f         window_closes_at is set                           -> reported only

G-f is reported but does not block yet: no rule sets window_days (A-31), so
blocking on it would stop every run until owners choose windows. G-d (figure
backed) is not checked here yet.

G-e uses the same role_map and authority tables as the app's
authority_check, so an item admitted here has someone who could apply its
proposal. Group membership is not expanded (the job cannot see who is in a
group), so a group assignment counts as an owner. If the tables cannot be
read, G-e fails with that reason rather than admitting the item.
"""
from __future__ import annotations

from typing import Any

from . import catalog as C
from .evaluate import _parent_gate

TEST_SUBJECT_PREFIX = "test-wbs-"


def _check(gate: str, ok: bool, reason: str, lane: str, blocking: bool = True) -> dict:
    return {"gate": gate, "ok": bool(ok), "reason": None if ok else reason,
            "lane": None if ok else lane, "blocking": blocking}


def _owner_check(spark, role) -> dict:
    """G-e: someone holds the owner role now, and the role may apply a proposal."""
    gate = "G-e owner"
    if not role or not str(role).strip():
        return _check(gate, False, "exception has no owner_role", "System")
    try:
        holders = spark.sql(
            f"SELECT uc_group FROM {C.ROLE_MAP} WHERE role = :role "
            "AND effective_from <= current_timestamp() "
            "AND (effective_to IS NULL OR effective_to > current_timestamp())",
            args={"role": str(role)}).collect()
        actions = {r.action for r in spark.sql(
            f"SELECT action FROM {C.AUTHORITY} WHERE role = :role AND target_table = 'proposals'",
            args={"role": str(role)}).collect()}
    except Exception as exc:  # noqa: BLE001 - unreadable is not the same as resolved
        return _check(gate, False, f"could not read role_map/authority: "
                      f"{type(exc).__name__}: {str(exc)[:200]}", "System")
    problems = []
    if "apply" not in actions:
        problems.append(f"role {role} holds no apply on proposals in authority")
    if not holders:
        problems.append(f"no one holds role {role} in role_map now")
    return _check(gate, not problems, "; ".join(problems), "System")


def precheck(spark, exc: dict) -> dict[str, Any]:
    """Return {admit, lane, checks, reasons}. admit False means do not start a model run."""
    status = exc.get("status")
    rule_id = exc.get("rule_id")
    rule_version = exc.get("rule_version")
    subjects = [str(s) for s in (exc.get("subject_ids") or []) if s is not None]
    checks: list[dict] = []

    checks.append(_check("open", status == "open",
                         f"status is {status}, not open", "System"))

    test = [s for s in subjects if s.startswith(TEST_SUBJECT_PREFIX)]
    checks.append(_check(
        "G-a not test", not test and status != "void_test_data",
        (f"test data: subject {', '.join(test)}" if test else "status is void_test_data"),
        "System"))

    current = {r.rule_id: (r.version, dict(r.params) if r.params else {})
               for r in spark.sql(
                   f"SELECT rule_id, version, params FROM {C.CURRENT_RULES}").collect()}
    cur = current.get(rule_id)
    if cur is None:
        b_reason = f"rule {rule_id} has no version in effect"
    else:
        b_reason = f"rule {rule_id} v{rule_version} is not the version in effect (v{cur[0]})"
    checks.append(_check("G-b rule live", cur is not None and cur[0] == rule_version,
                         b_reason, "System"))

    # G-c, part 1: the rule chain. Uses the version in effect's params, which is
    # what evaluate() would run (A-29); falls back to nothing when the rule is absent.
    params = cur[1] if cur else {}
    gate = _parent_gate(spark, rule_id, params, {k: v[1] for k, v in current.items()}) \
        if params.get("source_rule") else None
    checks.append(_check("G-c parent rule live", gate is None, gate or "", "Unblock"))

    # G-c, part 2: the parent exceptions an escalation names (A-28).
    if exc.get("subject_type") == "exception" and subjects:
        marks = ", ".join(f":p{i}" for i in range(len(subjects)))
        found = {r.exception_id: r.status for r in spark.sql(
            f"SELECT exception_id, status FROM {C.EXCEPTIONS} WHERE exception_id IN ({marks})",
            args={f"p{i}": s for i, s in enumerate(subjects)}).collect()}
        absent = [s for s in subjects if s not in found]
        closed = [f"{s} is {found[s]}" for s in subjects if s in found and found[s] != "open"]
        checks.append(_check("G-c parent exception open", not absent and not closed,
                             "parent exception " + "; ".join(
                                 [f"{s} not found" for s in absent] + closed),
                             "System"))

    checks.append(_owner_check(spark, exc.get("owner_role")))

    checks.append(_check("G-f window", bool(exc.get("window_closes_at")),
                         "no window_closes_at (the rule sets no window_days, A-31)",
                         "System", blocking=False))

    failing = [c for c in checks if not c["ok"] and c["blocking"]]
    return {
        "admit": not failing,
        "lane": failing[0]["lane"] if failing else "Decide",
        "checks": checks,
        "reasons": [f"{c['gate']}: {c['reason']}" for c in failing],
    }
