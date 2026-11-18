-- A-30 (2026-11-11): record the retirement of CC-02 v1-v4, superseded by v5.
--
-- The rule register is insert-only (table comment: "Never UPDATE; insert a new
-- version"), so v1-v4 keep their stored status. Retirement is recorded as
-- 'retire' events in the audit table (the event the DDL defines), and every
-- reader derives the real state: current_rules, the app rule card (lifecycle,
-- superseded_by) and get_rule (lifecycle, superseded_by).
-- Idempotent: one retire event per version at most.
-- Run with ${S} = users.xiaobing_shang1_civ.

INSERT INTO ${S}.aircarrier_app_rule_register_audit
  (audit_id, rule_id, version, event, actor, actor_role, event_at,
   prior_params, new_params, notes)
SELECT uuid(), r.rule_id, r.version, 'retire', 'a30_retire', NULL, current_timestamp(),
  r.params, NULL,
  'A-30: superseded by CC-02 v5 (parent link, A-28); stored status left as is (insert-only register)'
FROM ${S}.aircarrier_app_rule_register r
WHERE r.rule_id = 'CC-02' AND r.version BETWEEN 1 AND 4
  AND EXISTS (SELECT 1 FROM ${S}.aircarrier_app_rule_register n
              WHERE n.rule_id = 'CC-02' AND n.version = 5
                AND n.effective_from <= current_timestamp())
  AND NOT EXISTS (SELECT 1 FROM ${S}.aircarrier_app_rule_register_audit a
                  WHERE a.rule_id = r.rule_id AND a.version = r.version
                    AND a.event = 'retire');
