-- CC-02 v6 (A-28 second half, 2026-11-11): the escalation stops copying the
-- parent's dollars.
--
-- v1-v5 selected e.dollar_amount, so every escalation re-stated the CC-01
-- amount as its own. Summed across the table, the same dollars counted once
-- per escalation (6 rows held $30M for $9M of seed). v6 returns only
-- parent_exception_id. evaluate.py then writes dollar_amount NULL, and the
-- amount stays on the parent exception, which the subject names (v5).
-- Unchanged from v5: statement, params, owner, required_action, area.
--
-- Also records the retirement of v5 (A-30: the register is insert-only, so
-- retirement is an audit 'retire' event, never an UPDATE).
-- Idempotent. Run with ${S} = users.xiaobing_shang1_civ.

INSERT INTO ${S}.aircarrier_app_rule_register
  (rule_id, version, effective_from, effective_to, owner_role, statement_text,
   expression_sql, params, value_lists, status, created_by, created_at,
   owner_office, required_action, area, blocked_reason)
SELECT 'CC-02', 6, current_timestamp(), NULL, v5.owner_role, v5.statement_text,
  'SELECT e.exception_id AS parent_exception_id FROM {EXCEPTIONS} e WHERE e.rule_id = :source_rule AND e.status = :status_filter AND datediff(current_date(), e.detected_at) > CAST(:escalation_days AS INT)',
  v5.params, v5.value_lists, 'active', 'a28_no_inherited_dollars', current_timestamp(),
  v5.owner_office, v5.required_action, v5.area, NULL
FROM ${S}.aircarrier_app_rule_register v5
WHERE v5.rule_id = 'CC-02' AND v5.version = 5
  AND NOT EXISTS (SELECT 1 FROM ${S}.aircarrier_app_rule_register x
                  WHERE x.rule_id = 'CC-02' AND x.version = 6);

INSERT INTO ${S}.aircarrier_app_rule_register_audit
  (audit_id, rule_id, version, event, actor, actor_role, event_at,
   prior_params, new_params, notes)
SELECT uuid(), 'CC-02', 6, 'insert', 'a28_no_inherited_dollars', NULL, current_timestamp(),
  v5.params, v5.params,
  'A-28: escalation no longer selects dollar_amount; the amount stays on the parent CC-01 exception'
FROM ${S}.aircarrier_app_rule_register v5
WHERE v5.rule_id = 'CC-02' AND v5.version = 5
  AND NOT EXISTS (SELECT 1 FROM ${S}.aircarrier_app_rule_register_audit a
                  WHERE a.rule_id = 'CC-02' AND a.version = 6 AND a.event = 'insert');

INSERT INTO ${S}.aircarrier_app_rule_register_audit
  (audit_id, rule_id, version, event, actor, actor_role, event_at,
   prior_params, new_params, notes)
SELECT uuid(), 'CC-02', 5, 'retire', 'a28_no_inherited_dollars', NULL, current_timestamp(),
  v5.params, NULL,
  'A-30: superseded by CC-02 v6 (no inherited dollars); stored status left as is (insert-only register)'
FROM ${S}.aircarrier_app_rule_register v5
WHERE v5.rule_id = 'CC-02' AND v5.version = 5
  AND EXISTS (SELECT 1 FROM ${S}.aircarrier_app_rule_register n
              WHERE n.rule_id = 'CC-02' AND n.version = 6
                AND n.effective_from <= current_timestamp())
  AND NOT EXISTS (SELECT 1 FROM ${S}.aircarrier_app_rule_register_audit a
                  WHERE a.rule_id = 'CC-02' AND a.version = 5 AND a.event = 'retire');
