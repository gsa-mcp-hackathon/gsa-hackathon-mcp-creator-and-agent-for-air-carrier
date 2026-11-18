"""Every SQL statement the work queue runs, in one file, as SQL.

Why one file: the authority rule is the part an auditor reads, and it should
be readable as one statement rather than reassembled from Python branches.
authority_check() below IS the rule. The rendering path (is the apply button
enabled, and if not, why) and the write path (apply_block()) run the same
text, so what the button says and what the server does cannot disagree.

Rules the statements follow:
  * Every value is a named parameter marker. Only table names, which come
    from configuration, are formatted into the text.
  * Money leaves the warehouse as STRING. live._cast turns DECIMAL into
    float, which would round dollars; a string is passed through untouched.
  * Timestamps leave as ISO 8601 UTC strings.
  * Authority is decided by current_user() inside the statement, run under
    the caller's on-behalf-of token. No statement takes a role as input.

Table names: {catalog}.{schema}.{prefix}{infix}{name}, where infix is
AIRCARRIER_APP_INFIX (default "app_"). Tests set it to "apptest_" to run the
same statements against scratch copies.
"""
from __future__ import annotations

import os

from . import live
from .sqlsafe import Fragment, compose, ident

INFIX = os.environ.get("AIRCARRIER_APP_INFIX", "app_")

_NAMES = ("exceptions", "rule_register", "rule_register_audit", "proposals",
          "checker_verdicts", "decisions", "determinations", "decision_attempts",
          "agent_runs", "agent_steps", "role_map", "authority",
          "current_rules", "rule_evals",
          "model_runs", "documents", "metrics")


def tables(infix: str | None = None) -> dict[str, str]:
    """Logical name -> fully qualified table name."""
    base = f"{live.CATALOG}.{live.SCHEMA}.{live.PREFIX}{INFIX if infix is None else infix}"
    return {n: ident(base + n) for n in _NAMES}


_ISO = "date_format(to_utc_timestamp({c}, current_timezone()), \"yyyy-MM-dd'T'HH:mm:ss'Z'\")"


def iso(col: str) -> Fragment:
    """SQL expression rendering a TIMESTAMP column as an ISO 8601 UTC string."""
    return Fragment(_ISO.format(c=ident(col)))


# --------------------------------------------------------------- authority
# One row, always. reason_code is a fixed vocabulary the UI maps to nothing
# but a label: the sentence shown to the user is `reason`, written here.
#
# Order matters. The first failing condition is the one reported, so a user
# is told the most basic reason first (the proposal is gone) before the most
# specific (your role does not own this exception).
#
# Parameters:
#   :proposal_id        the proposal being acted on
#   :action             'apply' or 'reject'
#   :confirmed_records  JSON array of the record ids the confirmation showed,
#                       sorted, no spaces; NULL when only rendering the state
#
# Who may act: the caller holds, in role_map, the role that owns the
# exception (exceptions.owner_role, which the rule register set at
# detection), and that role holds `action` on 'proposals' in authority.
# proposals.target_table is NOT consulted: the agent chose it, and nothing
# an agent writes is a basis for authority.
REASON_CODES = ("allowed", "bad_action", "not_found", "blocked", "not_pending",
                "no_lineage", "exception_missing", "exception_closed",
                "lineage_mismatch", "record_set_changed", "not_checked",
                "verdict_not_passing", "no_role", "not_owner", "role_cannot_act")


def authority_check(t: dict[str, str]) -> str:
    return f"""
WITH p AS (
  SELECT proposal_id, run_id, status, intake_outcome, block_reason, exception_id,
         rule_id, rule_version, record_ids
  FROM {t['proposals']} WHERE proposal_id = :proposal_id
),
e AS (
  SELECT x.exception_id, x.rule_id, x.rule_version, x.owner_role, x.owner_office, x.status
  FROM {t['exceptions']} x JOIN p ON x.exception_id = p.exception_id
),
v AS (
  SELECT cv.verdict FROM {t['checker_verdicts']} cv JOIN p ON cv.run_id = p.run_id
  WHERE exists(cv.checks, c -> c.check_name = 'proposal' AND c.expected = :proposal_id)
  ORDER BY cv.decided_at DESC NULLS LAST, cv.step_seq DESC LIMIT 1
),
held AS (
  SELECT role, component FROM {t['role_map']}
  WHERE (uc_group = current_user() OR is_account_group_member(uc_group))
    AND effective_from <= current_timestamp()
    AND (effective_to IS NULL OR effective_to > current_timestamp())
),
able AS (
  SELECT min(h.role) AS role, min(h.component) AS component
  FROM held h
  JOIN {t['authority']} a ON a.role = h.role
  JOIN e ON e.owner_role = h.role
  WHERE a.target_table = 'proposals' AND a.action = :action
),
d AS (
  SELECT p.proposal_id, p.status, p.block_reason, p.exception_id,
         e.exception_id AS e_id, e.owner_role, e.owner_office, e.status AS e_status,
         v.verdict, hr.roles, able.role AS role_used, able.component,
    CASE
      WHEN :action NOT IN ('apply', 'reject') THEN 'bad_action'
      WHEN p.proposal_id IS NULL THEN 'not_found'
      WHEN p.status = 'blocked' OR coalesce(p.intake_outcome, '') = 'blocked' THEN 'blocked'
      WHEN p.status <> 'pending' THEN 'not_pending'
      WHEN p.exception_id IS NULL THEN 'no_lineage'
      WHEN e.exception_id IS NULL THEN 'exception_missing'
      WHEN e.status <> 'open' THEN 'exception_closed'
      WHEN NOT (p.rule_id <=> e.rule_id AND p.rule_version <=> e.rule_version)
        THEN 'lineage_mismatch'
      WHEN :confirmed_records IS NOT NULL
       AND to_json(array_sort(coalesce(p.record_ids, array()))) <> :confirmed_records
        THEN 'record_set_changed'
      WHEN :action = 'apply' AND v.verdict IS NULL THEN 'not_checked'
      WHEN :action = 'apply' AND v.verdict NOT IN ('pass', 'pass_with_exception')
        THEN 'verdict_not_passing'
      WHEN size(hr.roles) = 0 THEN 'no_role'
      WHEN NOT array_contains(hr.roles, e.owner_role) THEN 'not_owner'
      WHEN able.role IS NULL THEN 'role_cannot_act'
      ELSE 'allowed'
    END AS reason_code
  FROM (SELECT 1 AS one) base
  LEFT JOIN p ON true
  LEFT JOIN e ON true
  LEFT JOIN v ON true
  CROSS JOIN (SELECT array_sort(collect_set(role)) AS roles FROM held) hr
  CROSS JOIN able
)
SELECT reason_code,
  CASE reason_code
    WHEN 'allowed' THEN concat('You hold ', role_used, ', the role that owns this exception.')
    WHEN 'bad_action' THEN 'The requested action is not apply or reject.'
    WHEN 'not_found' THEN 'No proposal with this id exists.'
    WHEN 'blocked' THEN concat('This proposal is blocked and cannot be applied by anyone: ',
                               coalesce(block_reason, 'no reason was recorded.'))
    WHEN 'not_pending' THEN concat('This proposal is already ', status, '.')
    WHEN 'no_lineage' THEN 'This proposal names no exception, so there is no rule and no owning office to authorize against.'
    WHEN 'exception_missing' THEN 'The exception this proposal cites does not exist.'
    WHEN 'exception_closed' THEN concat('The exception is ', e_status, ', so its proposals can no longer be acted on.')
    WHEN 'lineage_mismatch' THEN 'The rule or rule version on this proposal differs from its exception.'
    WHEN 'record_set_changed' THEN 'The records behind this proposal changed after you reviewed them. Review again.'
    WHEN 'not_checked' THEN 'The checker has not verified this proposal. It cannot be applied until it has a passing verdict.'
    WHEN 'verdict_not_passing' THEN concat('The checker verdict is ', verdict, '. A proposal that did not pass cannot be applied.')
    WHEN 'no_role' THEN concat(current_user(), ' holds no role in the Air Carrier role map.')
    WHEN 'not_owner' THEN concat('This exception is owned by ', owner_role, ' (', owner_office,
                                 '). You hold: ', array_join(roles, ', '), '.')
    WHEN 'role_cannot_act' THEN concat('Your role ', owner_role, ' may not ', :action, ' proposals.')
  END AS reason,
  role_used, component, e_id AS exception_id, owner_role, current_user() AS evaluated_for
FROM d
"""


# --------------------------------------------------------------- apply / reject
# One statement, one transaction. The attempt row is written whatever the
# outcome, so a refusal is on the record. When allowed, the decision, the
# determination (apply only) and the proposal status change commit together:
# a decision without its status change, or a status change without its
# decision, would leave lineage that does not explain the record.
#
# Idempotency: a request_id this caller already sent returns the outcome
# recorded the first time, and writes nothing. The check is inside the block,
# so two concurrent sends of one request cannot both write.
#
# Parameters: :proposal_id, :action, :confirmed_records, :request_id, :notes
def apply_block(t: dict[str, str]) -> str:
    return f"""
BEGIN ATOMIC
  DECLARE v_prior BIGINT;
  DECLARE v_code STRING;
  DECLARE v_reason STRING;
  DECLARE v_role STRING;
  DECLARE v_component STRING;
  DECLARE v_exception STRING;
  DECLARE v_owner STRING;
  DECLARE v_for STRING;
  DECLARE v_decision STRING DEFAULT uuid();
  DECLARE v_now TIMESTAMP DEFAULT current_timestamp();

  -- A DECLARE default cannot hold a subquery; SET can.
  SET v_prior = (SELECT count(*) FROM {t['decision_attempts']}
                 WHERE request_id = :request_id AND actor = current_user()
                   AND proposal_id = :proposal_id AND action = :action);

  IF v_prior > 0 THEN
    SELECT reason_code, reason, decision_id, role_used, actor AS evaluated_for, true AS replayed
    FROM {t['decision_attempts']}
    WHERE request_id = :request_id AND actor = current_user()
      AND proposal_id = :proposal_id AND action = :action
    ORDER BY attempted_at LIMIT 1;
  ELSE
  SET (v_code, v_reason, v_role, v_component, v_exception, v_owner, v_for) = ({authority_check(t)});

  INSERT INTO {t['decision_attempts']}
    SELECT uuid(), :request_id, :proposal_id, v_exception, current_user(), :action,
           IF(v_code = 'allowed', 'allowed', 'refused'), v_code, v_reason, v_role,
           IF(v_code = 'allowed', v_decision, NULL), v_now;

  IF v_code = 'allowed' THEN
    INSERT INTO {t['decisions']}
      (decision_id, proposal_id, exception_id, actor, actor_role, action,
       decided_at, authority_check_result, notes, actor_kind, authority_basis)
      SELECT v_decision, :proposal_id, v_exception, current_user(), v_role, :action,
             v_now, concat('allowed:', v_role), :notes,
             'human', IF(:action = 'apply', 'human_applied', 'human_rejected');

    IF :action = 'apply' THEN
      INSERT INTO {t['determinations']}
        (determination_id, proposal_id, decision_id, target_table, target_key,
         payload, component, applied_at, applied_by)
        SELECT uuid(), proposal_id, v_decision, target_table, target_key,
               proposed_payload, v_component, v_now, current_user()
        FROM {t['proposals']} WHERE proposal_id = :proposal_id;
    END IF;

    UPDATE {t['proposals']}
      SET status = IF(:action = 'apply', 'applied', 'rejected')
      WHERE proposal_id = :proposal_id AND status = 'pending';
  END IF;

  SELECT v_code AS reason_code, v_reason AS reason,
         IF(v_code = 'allowed', v_decision, NULL) AS decision_id,
         v_role AS role_used, v_for AS evaluated_for, false AS replayed;
  END IF;
END;
"""


def my_roles(t: dict[str, str]) -> str:
    """The caller's current roles, resolved by Unity Catalog under their token."""
    return f"""
SELECT role, component, uc_group, {iso('effective_from')} AS effective_from,
       {iso('effective_to')} AS effective_to, current_user() AS evaluated_for
FROM {t['role_map']}
WHERE (uc_group = current_user() OR is_account_group_member(uc_group))
  AND effective_from <= current_timestamp()
  AND (effective_to IS NULL OR effective_to > current_timestamp())
ORDER BY role
"""


# --------------------------------------------------------------- reads
EXCEPTION_SORTS = {"detected_at": "detected_at", "window_closes_at": "window_closes_at",
                   "dollar_amount": "dollar_amount", "rule_id": "rule_id"}
EXCEPTION_FILTERS = ("area", "status", "owner_role", "rule_id")


def exception_columns(alias: str = "x") -> Fragment:
    a = ident(alias)
    return Fragment(f"""{a}.exception_id, {a}.rule_id, {a}.rule_version, {a}.subject_type,
  {a}.subject_ids, {iso(a + '.detected_at')} AS detected_at,
  CAST({a}.dollar_amount AS STRING) AS dollar_amount, {a}.owner_role, {a}.owner_office,
  {a}.required_action, {iso(a + '.window_closes_at')} AS window_closes_at,
  {a}.status, {a}.area, {a}.eval_id""")


def exception_where(filters: dict[str, str]) -> tuple[Fragment, dict[str, str]]:
    """WHERE clause over the allowlisted filter columns, with bound values."""
    parts, params = ["1 = 1"], {}
    for name in EXCEPTION_FILTERS:
        value = filters.get(name)
        if value:
            parts.append(f"x.{name} = :f_{name}")
            params[f"f_{name}"] = value
    return Fragment(" AND ".join(parts)), params


def exception_list(t: dict[str, str], where: str, sort: str, descending: bool,
                   limit: int, offset: int) -> str:
    col = EXCEPTION_SORTS[sort]
    direction = "DESC" if descending else "ASC"
    return f"""
SELECT {exception_columns()},
  {iso('r.last_run_at')} AS last_run_at, r.last_run_outcome
FROM {t['exceptions']} x
LEFT JOIN (
  SELECT subject_id, max(ended_at) AS last_run_at,
         max_by(outcome, ended_at) AS last_run_outcome
  FROM {t['agent_runs']}
  WHERE subject_kind = 'exception' AND ended_at IS NOT NULL
  GROUP BY subject_id
) r ON r.subject_id = x.exception_id
WHERE {where}
ORDER BY x.{col} {direction} NULLS LAST, x.exception_id
LIMIT {int(limit)} OFFSET {int(offset)}
"""


def exception_count(t: dict[str, str], where: Fragment) -> str:
    """where is the Fragment exception_where() built; a plain str is refused."""
    return compose("SELECT count(*) AS n FROM {tbl} x WHERE {where}",
                   tbl=t["exceptions"], where=where)


def exception_one(t: dict[str, str]) -> str:
    return compose("SELECT {cols} FROM {tbl} x WHERE x.exception_id = :exception_id",
                   cols=exception_columns(), tbl=t["exceptions"])


def rule_at_version(t: dict[str, str]) -> str:
    return f"""
SELECT rule_id, version, statement_text, to_json(params) AS params_json, status,
       owner_role, owner_office, required_action, area, blocked_reason,
       {iso('effective_from')} AS effective_from, created_by
FROM {t['rule_register']} WHERE rule_id = :rule_id AND version = :rule_version
"""


def runs_for_exception(t: dict[str, str]) -> str:
    return f"""
SELECT run_id, trigger, triggered_by, {iso('started_at')} AS started_at,
       {iso('ended_at')} AS ended_at, orchestrator_version, specialist, outcome
FROM {t['agent_runs']}
WHERE subject_kind = 'exception' AND subject_id = :exception_id AND ended_at IS NOT NULL
ORDER BY ended_at DESC LIMIT 20
"""


def steps_for_run(t: dict[str, str]) -> str:
    return f"""
SELECT step_seq, agent_name, agent_version, model_endpoint, rule_id, rule_version,
       record_ids, output_json, {iso('stepped_at')} AS stepped_at,
       actor_kind, authority_basis
FROM {t['agent_steps']} WHERE run_id = :run_id ORDER BY step_seq
"""


def proposals_for_exception(t: dict[str, str]) -> str:
    return f"""
WITH lv AS (
  SELECT p.proposal_id, cv.verdict, to_json(cv.checks) AS checks_json, cv.notes,
         cv.checker_agent, cv.model_endpoint, {iso('cv.decided_at')} AS decided_at,
         row_number() OVER (PARTITION BY p.proposal_id
                            ORDER BY cv.decided_at DESC NULLS LAST, cv.step_seq DESC) AS rn
  FROM {t['proposals']} p
  JOIN {t['checker_verdicts']} cv ON cv.run_id = p.run_id
   AND exists(cv.checks, c -> c.check_name = 'proposal' AND c.expected = p.proposal_id)
  WHERE p.exception_id = :exception_id
)
SELECT p.proposal_id, p.run_id, p.target_table, p.target_key, p.proposed_payload,
       to_json(p.grounding) AS grounding_json, p.status, p.block_reason, p.intake_outcome,
       p.rule_id, p.rule_version, p.record_ids, {iso('p.created_at')} AS created_at,
       lv.verdict, lv.checks_json, lv.notes AS verdict_notes, lv.checker_agent,
       lv.model_endpoint AS checker_model, lv.decided_at AS verdict_at
FROM {t['proposals']} p
LEFT JOIN lv ON lv.proposal_id = p.proposal_id AND lv.rn = 1
WHERE p.exception_id = :exception_id
ORDER BY p.created_at DESC
"""


def decisions_for_exception(t: dict[str, str]) -> str:
    return f"""
SELECT decision_id, proposal_id, actor, actor_role, action,
       {iso('decided_at')} AS decided_at, authority_check_result, notes,
       actor_kind, authority_basis
FROM {t['decisions']} WHERE exception_id = :exception_id ORDER BY decided_at DESC
"""


def attempts_for_exception(t: dict[str, str]) -> str:
    return f"""
SELECT attempt_id, request_id, proposal_id, actor, action, outcome, reason_code, reason,
       role_used, decision_id, {iso('attempted_at')} AS attempted_at
FROM {t['decision_attempts']} WHERE exception_id = :exception_id
ORDER BY attempted_at DESC LIMIT 50
"""


# ---- rule register (build step 4) -------------------------------------------

def rule_list(t: dict[str, str]) -> str:
    """Active rules with open-exception counts. Filters via optional params."""
    return f"""
WITH exc_ct AS (
  SELECT rule_id, COUNT(*) AS open_count,
         SUM(COALESCE(dollar_amount, 0)) AS open_dollars
  FROM {t['exceptions']} WHERE status = 'open'
  GROUP BY rule_id
)
SELECT r.rule_id, r.version, r.status, r.blocked_reason,
       r.statement_text, r.params, r.value_lists,
       r.owner_role, r.owner_office, r.required_action, r.area,
       {iso('r.effective_from')} AS effective_from,
       {iso('r.effective_to')} AS effective_to,
       COALESCE(e.open_count, 0) AS open_count,
       COALESCE(e.open_dollars, 0) AS open_dollars
FROM {t['current_rules']} r
LEFT JOIN exc_ct e ON r.rule_id = e.rule_id
WHERE 1=1
  AND (:area IS NULL OR r.area = :area)
  AND (:status IS NULL OR r.status = :status)
  AND (:owner_role IS NULL OR r.owner_role = :owner_role)
ORDER BY r.rule_id
"""


def rule_catalog(t: dict[str, str]) -> str:
    """Every rule in the register at its latest stored version (the /rules page).

    rule_list reads current_rules, the rules in effect now, so it leaves out
    the blocked ones. The catalog is the whole specification: a blocked rule
    has no version in effect but is still a rule. current_version is the
    version in effect, or NULL when none is. No parameters.
    """
    return f"""
SELECT r.rule_id, r.version, r.version_count, r.status, r.blocked_reason,
       r.statement_text, r.params, r.owner_role, r.owner_office,
       r.required_action, r.area, c.version AS current_version
FROM (SELECT *, COUNT(*) OVER (PARTITION BY rule_id) AS version_count,
             ROW_NUMBER() OVER (PARTITION BY rule_id ORDER BY version DESC) AS rn
      FROM {t['rule_register']}) r
LEFT JOIN {t['current_rules']} c ON c.rule_id = r.rule_id
WHERE r.rn = 1
ORDER BY r.rule_id
"""


def rule_detail(t: dict[str, str]) -> str:
    """All versions of a single rule.

    A-30: the register is insert-only, so an old version keeps status 'active'
    after a newer version takes effect. lifecycle derives the real state the
    same way current_rules does: a version is 'superseded' once a newer version
    is effective, whatever its stored status; superseded_by names that version.
    """
    return f"""
SELECT rule_id, version, status, blocked_reason,
       CASE WHEN version < latest_eff THEN 'superseded' ELSE status END AS lifecycle,
       CASE WHEN version < latest_eff THEN latest_eff END AS superseded_by,
       statement_text, expression_sql, params, value_lists,
       owner_role, owner_office, required_action, area,
       {iso('effective_from')} AS effective_from,
       {iso('effective_to')} AS effective_to,
       created_by, {iso('created_at')} AS created_at
FROM (SELECT *, MAX(CASE WHEN effective_from <= current_timestamp() THEN version END)
                  OVER (PARTITION BY rule_id) AS latest_eff
      FROM {t['rule_register']}) WHERE rule_id = :rule_id
ORDER BY version DESC
"""


def current_rule_params(t: dict[str, str]) -> str:
    """Every current rule's params, for the derived-rule gate (A-29)."""
    return compose("SELECT rule_id, params FROM {tbl}", tbl=t["current_rules"])


def latest_rule_state(t: dict[str, str]) -> str:
    """Latest stored version of a rule, for the A-29 gate message."""
    return f"""
SELECT version, status, blocked_reason FROM {t['rule_register']}
WHERE rule_id = :rule_id ORDER BY version DESC LIMIT 1
"""


def rule_for_preview(t: dict[str, str]) -> str:
    """Read expression_sql, params, and version for preview."""
    return f"""
SELECT rule_id, version, expression_sql, params, value_lists,
       owner_role, owner_office, required_action, area
FROM {t['current_rules']} WHERE rule_id = :rule_id
"""


# Table-name placeholders that expression_sql may contain, resolved to the
# app's fully qualified names. Mirrors ops/harness/evaluate._TABLE_MAP so the
# preview and the backend evaluate cannot disagree on which tables a rule reads.
_EXPR_PLACEHOLDERS = {
    "{EXCEPTIONS}": "exceptions",
    "{MODEL_RUNS}": "model_runs",
    "{RULE_REGISTER}": "rule_register",
    "{PROPOSALS}": "proposals",
    "{DECISIONS}": "decisions",
    "{DOCUMENTS}": "documents",
    "{AGENT_RUNS}": "agent_runs",
    "{AGENT_STEPS}": "agent_steps",
    "{METRICS}": "metrics",
    "{DETERMINATIONS}": "determinations",
}


def bind_expression(expression_sql: str, t: dict[str, str],
                    params: dict[str, str] | None) -> tuple[str, dict[str, str]]:
    """Same substitution as evaluate._bind but using the app's table dict.

    Returns (sql, args) where args are the named params for live.query().
    """
    sql = expression_sql
    for placeholder, logical in _EXPR_PLACEHOLDERS.items():
        if logical in t:
            sql = sql.replace(placeholder, t[logical])
    # window_days sets the exception deadline; it is not a detection param
    # (A-31, same as ops/harness/evaluate).
    return sql, {k: str(v) for k, v in (params or {}).items() if k != "window_days"}


# ------------------------------------------------------------------ lanes
# The three-lane queue reads everything it sorts in three statements; the
# sorting (Decide / Unblock / System) is code in harness.lanes(), not SQL, so
# one function holds every admission rule.
def lane_exceptions(t: dict[str, str]) -> str:
    return compose("SELECT {cols} FROM {tbl} x", cols=exception_columns(), tbl=t["exceptions"])


def lane_proposals(t: dict[str, str]) -> str:
    """Every proposal, with its run (agent_runs holds duplicate rows per run_id,
    so it is collapsed first) and every checker verdict on that run."""
    return f"""
SELECT p.proposal_id, p.run_id, p.status, p.block_reason, p.rule_id, p.target_table,
  p.target_key, p.intake_outcome, p.exception_id, p.proposed_payload,
  {iso('p.created_at')} AS created_at, r.trigger, r.subject_id, v.verdicts
FROM {t['proposals']} p
LEFT JOIN (
  SELECT run_id, max(trigger) AS trigger, max(subject_id) AS subject_id
  FROM {t['agent_runs']} GROUP BY run_id
) r ON r.run_id = p.run_id
LEFT JOIN (
  SELECT run_id, to_json(collect_list(named_struct('checker', checker_agent,
                                                   'verdict', verdict))) AS verdicts
  FROM {t['checker_verdicts']} GROUP BY run_id
) v ON v.run_id = p.run_id
"""


def held_roles(t: dict[str, str]) -> str:
    """Roles that someone holds now. Run on the caller's token: the app
    principal has no grant on role_map."""
    return f"""
SELECT DISTINCT role FROM {t['role_map']}
WHERE effective_from <= current_timestamp()
  AND (effective_to IS NULL OR effective_to > current_timestamp())
"""


def lane_rules(t: dict[str, str]) -> str:
    return f"""
SELECT r.rule_id, r.version, r.status, r.blocked_reason, r.owner_role, r.owner_office,
  r.area, r.statement_text
FROM {t['rule_register']} r
"""


def lane_current(t: dict[str, str]) -> str:
    """The version of each rule in effect now: the current_rules view, the same
    one every other reader uses. The app principal holds SELECT on it."""
    return compose("SELECT rule_id, version FROM {tbl}", tbl=t["current_rules"])


def lane_retired(t: dict[str, str]) -> str:
    """Versions retired by an audit event (A-30). Optional: the app principal
    has no grant on rule_register_audit, so this runs on the caller's token and
    the rule-defect check is skipped, with the reason, when it cannot."""
    return compose("SELECT rule_id, version FROM {tbl} WHERE event = 'retire'",
                   tbl=t["rule_register_audit"])


def rule_audit(t: dict[str, str]) -> str:
    """Audit log for a rule."""
    return f"""
SELECT version, actor, event, prior_params, new_params, notes,
       {iso('event_at')} AS at
FROM {t['rule_register_audit']} WHERE rule_id = :rule_id
ORDER BY event_at DESC
"""
