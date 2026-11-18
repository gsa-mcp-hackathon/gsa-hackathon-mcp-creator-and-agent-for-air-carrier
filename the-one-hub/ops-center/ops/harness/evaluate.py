"""Rule evaluation engine (task 8, invariant 1).

Detection is deterministic SQL, never inference. Each active rule whose
expression_sql is not NULL is executed against the source views, and matching
rows are written to the exceptions table stamped with the rule version in
force at detection time.

The evaluator:
  * Reads only from the current_rules view (active, in the effective window,
    latest version).
  * Substitutes table-name placeholders ({EXCEPTIONS}, {MODEL_RUNS}, etc.)
    and binds named params (:param_name) from the rule's params map.
  * Drops any result row that lacks owner_office or required_action
    (invariant 7: a detection with neither is not written).
  * Writes a rule_evals summary row so the API can report what ran.

Design for on-demand trigger (spec): this module is a pure function. The
entrypoint (ops/entrypoints/eval_job.py) or the POST /rules handler calls
evaluate() after an insert. A threshold change alters the exception
population in the same session with no deploy.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from . import catalog as C
from ._common import spark_session as _spark


# ---- table-name placeholders the expression_sql may contain -----------------
_TABLE_MAP = {
    "{EXCEPTIONS}": C.EXCEPTIONS,
    "{MODEL_RUNS}": C.MODEL_RUNS,
    "{RULE_REGISTER}": C.RULE_REGISTER,
    "{PROPOSALS}": C.PROPOSALS,
    "{DECISIONS}": C.DECISIONS,
    "{DOCUMENTS}": C.DOCUMENTS,
    "{AGENT_RUNS}": C.AGENT_RUNS,
    "{AGENT_STEPS}": C.AGENT_STEPS,
    "{METRICS}": C.METRICS,
    "{DETERMINATIONS}": C.DETERMINATIONS,
}


def _bind(expression_sql: str, params: dict[str, str] | None) -> tuple[str, dict[str, str]]:
    """Substitute table placeholders; return (sql, args) for spark.sql(sql, args=args).

    Named params use :param_name syntax in expression_sql and are bound by
    Spark as parameter markers, so values never become SQL text (F18).
    """
    sql = expression_sql
    for placeholder, fqn in _TABLE_MAP.items():
        sql = sql.replace(placeholder, fqn)
    return sql, {k: str(v) for k, v in (params or {}).items()}


def evaluate(
    *,
    trigger: str = "manual",
    triggered_by: str = "unknown",
    rule_ids: list[str] | None = None,
    dry_run: bool = False,
    params_override: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Run rule evaluation. Returns {eval_id, rules_evaluated: [...]}.

    Args:
        trigger:         Why this evaluation is running (manual | rule_insert | schedule).
        triggered_by:    Who or what triggered it (user email, job id, etc.).
        rule_ids:        If set, evaluate only these rules. Otherwise all active
                         rules with expression_sql.
        dry_run:         When True, no rows are written (A-4). Detection hits are
                         returned in each rule result's 'hits' list.
        params_override: If set, use these params instead of the rule's stored
                         params. Used by preview to test proposed parameter changes.
    """
    spark = _spark()
    eval_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    now_ts = now.isoformat()
    results: list[dict] = []

    # Read active rules with expression_sql
    # Every value below is bound as a parameter marker, never pasted into SQL
    # text (F9, F18). Table names and generated timestamps stay inline.
    where = "expression_sql IS NOT NULL"
    id_args = {f"r{i}": str(r) for i, r in enumerate(rule_ids or [])}
    if id_args:
        where += f" AND rule_id IN ({', '.join(':' + k for k in id_args)})"
    rules = spark.sql(
        f"SELECT * FROM {C.CURRENT_RULES} WHERE {where}", args=id_args
    ).collect()

    # A-29: a derived rule (params.source_rule) runs only while its source
    # rule, and the source's own source, has a version in current_rules.
    # Otherwise it would escalate leftovers of a rule that is not running.
    current: dict[str, dict] | None = None

    for rule in rules:
        rule_id = rule.rule_id
        version = rule.version
        status = "ok"
        error_msg = None
        rows_written = 0
        detected: list[dict] = []  # collected when dry_run (A-4)

        stored = dict(rule.params) if rule.params else None
        gate_params = params_override if params_override is not None else stored
        if gate_params and gate_params.get(SOURCE_RULE_PARAM):
            if current is None:
                current = {r.rule_id: (dict(r.params) if r.params else {}) for r in spark.sql(
                    f"SELECT rule_id, params FROM {C.CURRENT_RULES}").collect()}
            reason = _parent_gate(spark, rule_id, gate_params, current)
            if reason:
                entry = {"rule_id": rule_id, "version": version, "rows": 0,
                         "status": SKIPPED_PARENT_INACTIVE, "error": reason}
                if dry_run:
                    entry["hits"] = []
                results.append(entry)
                continue

        try:
            use_params = (params_override if params_override is not None
                          else stored)
            # A-31: the response window comes from the rule (params.window_days),
            # never from a default. No window_days -> NULL, which gate G-f
            # routes to System. A bad value fails the rule before it runs.
            window_ts = _window_closes(now, use_params)
            bound_sql, bound_args = _bind(
                rule.expression_sql,
                {k: v for k, v in (use_params or {}).items() if k != WINDOW_PARAM} or None)
            hits = spark.sql(bound_sql, args=bound_args).collect()

            # F19: at most one open exception per (rule_id, subject set), across
            # rule versions. A re-run, or a new version of the rule, that finds
            # the same subjects again does not raise a second one.
            open_sets = {
                tuple(sorted(r.subject_ids or [])) for r in spark.sql(
                    f"SELECT subject_ids FROM {C.EXCEPTIONS} "
                    "WHERE rule_id = :rule_id AND status = 'open'",
                    args={"rule_id": rule_id}).collect()
            } if hits else set()

            for hit in hits:
                hit_dict = hit.asDict()
                # Build subject_ids from the result columns
                subject_ids = _extract_subject_ids(hit_dict)
                if not subject_ids:
                    continue

                # Invariant 7: owner_office and required_action are mandatory.
                # They come from the rule row, not the query result.
                owner_office = rule.owner_office
                required_action = rule.required_action
                if not owner_office or not str(owner_office).strip():
                    continue  # drop silently (invariant 7)
                if not required_action or not str(required_action).strip():
                    continue

                subject_key = tuple(sorted(subject_ids))
                if subject_key in open_sets:
                    continue  # already open (F19)
                open_sets.add(subject_key)

                dollar_amount = _extract_dollar(hit_dict)
                subject_type = _subject_type(rule_id, hit_dict)

                if dry_run:
                    detected.append({"subject_ids": subject_ids,
                                     "dollar_amount": dollar_amount,
                                     "subject_type": subject_type,
                                     "window_closes_at": window_ts})
                else:
                    exception_id = str(uuid.uuid4())
                    exc_args = {
                        "exception_id": exception_id, "rule_id": rule_id,
                        "subject_type": subject_type, "dollar_amount": dollar_amount,
                        "owner_role": rule.owner_role,
                        "owner_office": str(owner_office),
                        "required_action": str(required_action),
                        "area": rule.area or "", "eval_id": eval_id,
                    }
                    exc_args.update({f"s{i}": str(s) for i, s in enumerate(subject_ids)})
                    ids_sql = ", ".join(f":s{i}" for i in range(len(subject_ids)))
                    dollar_sql = ("CAST(:dollar_amount AS DECIMAL(20,2))"
                                  if dollar_amount is not None else "NULL")

                    spark.sql(f"""
                        INSERT INTO {C.EXCEPTIONS}
                          (exception_id, rule_id, rule_version, subject_type,
                           subject_ids, detected_at, dollar_amount, owner_role,
                           owner_office, required_action, window_closes_at,
                           status, area, eval_id)
                        VALUES (
                            :exception_id, :rule_id, {int(version)},
                            :subject_type, ARRAY({ids_sql}),
                            TIMESTAMP '{now_ts}',
                            {dollar_sql},
                            :owner_role,
                            :owner_office, :required_action,
                            {f"TIMESTAMP '{window_ts}'" if window_ts else "NULL"}, 'open',
                            :area, :eval_id
                        )
                    """, args=exc_args)
                rows_written += 1

        except Exception as exc:
            status = "error"
            error_msg = str(exc)[:500]

        row_count = len(detected) if dry_run else rows_written
        entry: dict[str, Any] = {
            "rule_id": rule_id, "version": version,
            "rows": row_count, "status": status,
            "error": error_msg,
        }
        if dry_run:
            entry["hits"] = detected
        results.append(entry)

    # Write the rule_evals summary row (skipped in dry_run — A-4)
    if not dry_run:
        ended_ts = datetime.now(timezone.utc).isoformat()
        struct_exprs = []
        eval_args = {"eval_id": eval_id, "trigger": trigger, "triggered_by": triggered_by}
        for i, r in enumerate(results):
            err = "NULL"
            if r.get('error'):
                err, eval_args[f"err{i}"] = f":err{i}", str(r['error'])
            eval_args[f"rid{i}"], eval_args[f"st{i}"] = r['rule_id'], r['status']
            struct_exprs.append(
                f"named_struct('rule_id',:rid{i},'version',{int(r['version'])},"
                f"'rows',CAST({int(r['rows'])} AS BIGINT),'status',:st{i},"
                f"'error',{err})")
        array_sql = "ARRAY(" + ",".join(struct_exprs) + ")" if struct_exprs else "NULL"

        spark.sql(f"""
            INSERT INTO {C.RULE_EVALS}
              (eval_id, trigger, triggered_by, started_at, ended_at, rules_evaluated)
            VALUES (
                :eval_id, :trigger, :triggered_by,
                TIMESTAMP '{now_ts}', TIMESTAMP '{ended_ts}',
                {array_sql}
            )
        """, args=eval_args)

    return {"eval_id": eval_id, "rules_evaluated": results, "dry_run": dry_run}


# ---- helpers ----------------------------------------------------------------

WINDOW_PARAM = "window_days"


def _window_closes(now: datetime, params: dict | None) -> str | None:
    """detected_at + params.window_days, as an ISO timestamp; None when unset (A-31)."""
    raw = (params or {}).get(WINDOW_PARAM)
    if raw is None or str(raw).strip() == "":
        return None
    s = str(raw).strip()
    if not s.isdigit() or int(s) <= 0:
        raise ValueError(f"{WINDOW_PARAM} must be a whole number of days above 0, not {raw!r}")
    return (now + timedelta(days=int(s))).isoformat()


SOURCE_RULE_PARAM = "source_rule"
SKIPPED_PARENT_INACTIVE = "skipped_parent_inactive"


def _parent_gate(spark, rule_id: str, params: dict, current: dict[str, dict]) -> str | None:
    """None when every rule up the source_rule chain is current; else why not (A-29)."""
    seen = {rule_id}
    p = params
    while p and p.get(SOURCE_RULE_PARAM):
        parent = str(p[SOURCE_RULE_PARAM])
        if parent in seen:
            return f"source_rule chain loops back to {parent}; not run"
        seen.add(parent)
        if parent not in current:
            latest = spark.sql(
                f"SELECT version, status, blocked_reason FROM {C.RULE_REGISTER} "
                "WHERE rule_id = :rid ORDER BY version DESC LIMIT 1",
                args={"rid": parent}).collect()
            if not latest:
                state = "is not in the rule register"
            else:
                r = latest[0]
                state = f"has no version in effect (latest v{r.version}, {r.status}"
                state += f": {r.blocked_reason})" if r.blocked_reason else ")"
            return (f"source rule {parent} {state}; {rule_id} escalates {parent} "
                    f"exceptions, so it does not run until {parent} does")
        p = current[parent]
    return None


def _extract_subject_ids(hit: dict) -> list[str]:
    """Pull subject identifiers from a query result row.

    A-28: a derived rule (one that reads other exceptions, such as CC-02) names
    its parent with a parent_exception_id column. That column wins over every
    other, so the new exception's subject is the parent exception, not the
    parent's own subjects (which used to be copied through subject_ids).
    """
    # Rules may return different id columns. Try common patterns.
    for key in ["parent_exception_id", "subject_ids", "exception_id", "model_run_id",
                "proposal_id", "document_id", "transaction_id"]:
        val = hit.get(key)
        if val is not None:
            if isinstance(val, list):
                return [str(v) for v in val if v is not None]
            return [str(val)]
    # Fallback: use all string values that look like identifiers
    ids = [str(v) for v in hit.values() if v is not None and isinstance(v, str) and len(str(v)) < 100]
    return ids[:10] if ids else []


def _extract_dollar(hit: dict) -> str | None:
    """Pull a dollar amount from a query result row, if present."""
    for key in ["dollar_amount", "amount", "total", "value"]:
        val = hit.get(key)
        if val is not None:
            try:
                return str(float(val))
            except (TypeError, ValueError):
                pass
    return None


def _subject_type(rule_id: str, hit: dict) -> str:
    """'exception' when the subject is a parent exception (A-28), else by rule prefix."""
    if hit.get("parent_exception_id") is not None:
        return "exception"
    return _infer_subject_type(rule_id)


def _infer_subject_type(rule_id: str) -> str:
    """Map rule prefix to a subject type."""
    prefix = rule_id.split("-")[0] if "-" in rule_id else rule_id
    return {
        "CC": "reconciliation_item",
        "EV": "control_account",
        "CAP": "cost_cap_item",
        "AV": "valuation_item",
        "CM": "model_run",
    }.get(prefix, "unknown")


# ---- preview (A-4) ----------------------------------------------------------

def _sum_dollars(hits: list[dict]) -> str | None:
    """Sum dollar_amount across hits. Returns string or None if no amounts."""
    total = 0.0
    any_dollar = False
    for h in hits:
        if h.get("dollar_amount") is not None:
            try:
                total += float(h["dollar_amount"])
                any_dollar = True
            except (TypeError, ValueError):
                pass
    return str(total) if any_dollar else None


def preview_rule(
    rule_id: str,
    base_version: int,
    proposed_params: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Non-writing before/after preview of a rule parameter change.

    Runs the same detection code path as evaluate() in dry_run mode,
    first with current params (before), then with proposed params (after).
    Returns before, after, delta counts and dollar totals, plus the
    added and removed subject sets.
    """
    preview_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    # Before: current params
    before = evaluate(rule_ids=[rule_id], dry_run=True)
    before_hits = before["rules_evaluated"][0].get("hits", []) if before["rules_evaluated"] else []

    # After: proposed params
    after = evaluate(rule_ids=[rule_id], dry_run=True, params_override=proposed_params)
    after_hits = after["rules_evaluated"][0].get("hits", []) if after["rules_evaluated"] else []

    before_keys = {tuple(sorted(h["subject_ids"])) for h in before_hits}
    after_keys = {tuple(sorted(h["subject_ids"])) for h in after_hits}
    added_keys = after_keys - before_keys
    removed_keys = before_keys - after_keys

    return {
        "preview_id": preview_id,
        "rule_id": rule_id,
        "base_version": base_version,
        "evaluated_at": now.isoformat(),
        "before": {"count": len(before_hits), "dollar_total": _sum_dollars(before_hits)},
        "after": {"count": len(after_hits), "dollar_total": _sum_dollars(after_hits)},
        "delta": {"count": len(after_hits) - len(before_hits),
                  "dollar_total_before": _sum_dollars(before_hits),
                  "dollar_total_after": _sum_dollars(after_hits)},
        "added": [list(k) for k in sorted(added_keys)],
        "removed": [list(k) for k in sorted(removed_keys)],
        "added_count": len(added_keys),
        "removed_count": len(removed_keys),
    }
