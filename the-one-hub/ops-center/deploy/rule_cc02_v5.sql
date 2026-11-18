-- CC-02 v5 (A-28, 2026-11-11): the escalation names its CC-01 parent.
--
-- v1-v4 selected e.subject_ids, so evaluate._extract_subject_ids copied the
-- parent's WBS element (test-wbs-001) into the new exception and the parent
-- exception_id was lost. The agent could not find the parent, tested the 45 days
-- against the CC-02 row itself, and wrongly concluded the rule had misfired
-- (run 027b815a). v5 returns the parent as parent_exception_id; evaluate.py now
-- takes that column first and sets subject_type = 'exception'.
--
-- Unchanged from v4: statement, params (source_rule CC-01, status_filter open,
-- escalation_days 45), owner, required_action, area, and dollar_amount (the
-- inherited figure is a separate open item in A-28).
-- Idempotent: inserts nothing if v5 already exists.
-- Run with ${S} = users.xiaobing_shang1_civ. Statements separated by ";\n".

INSERT INTO ${S}.aircarrier_app_rule_register
  (rule_id, version, effective_from, effective_to, owner_role, statement_text,
   expression_sql, params, value_lists, status, created_by, created_at,
   owner_office, required_action, area, blocked_reason)
SELECT 'CC-02', 5, current_timestamp(), NULL, v4.owner_role, v4.statement_text,
  'SELECT e.exception_id AS parent_exception_id, e.dollar_amount FROM {EXCEPTIONS} e WHERE e.rule_id = :source_rule AND e.status = :status_filter AND datediff(current_date(), e.detected_at) > CAST(:escalation_days AS INT)',
  v4.params, v4.value_lists, 'active', 'a28_parent_link', current_timestamp(),
  v4.owner_office, v4.required_action, v4.area, NULL
FROM ${S}.aircarrier_app_rule_register v4
WHERE v4.rule_id = 'CC-02' AND v4.version = 4
  AND NOT EXISTS (SELECT 1 FROM ${S}.aircarrier_app_rule_register x
                  WHERE x.rule_id = 'CC-02' AND x.version = 5);

INSERT INTO ${S}.aircarrier_app_rule_register_audit
  (audit_id, rule_id, version, event, actor, actor_role, event_at,
   prior_params, new_params, notes)
SELECT uuid(), 'CC-02', 5, 'insert', 'a28_parent_link', NULL, current_timestamp(),
  v4.params, v4.params,
  'A-28: subject is the parent CC-01 exception (parent_exception_id), not the WBS subjects of the parent'
FROM ${S}.aircarrier_app_rule_register v4
WHERE v4.rule_id = 'CC-02' AND v4.version = 4
  AND NOT EXISTS (SELECT 1 FROM ${S}.aircarrier_app_rule_register_audit a
                  WHERE a.rule_id = 'CC-02' AND a.version = 5 AND a.event = 'insert');
