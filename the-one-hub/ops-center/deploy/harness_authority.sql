-- Air Carrier work queue: the decision-attempt log, the authority matrix, and
-- the pilot role assignment. Run once by the schema owner, after
-- deploy/harness_ddl.sql. CREATE IF NOT EXISTS and the MERGEs are safe to
-- rerun. The three ADD CONSTRAINT statements fail on a rerun because the
-- constraint exists; that failure is harmless and changes nothing.
--
-- Who may act on a proposal (app/api/harness_sql.py authority_check):
--   the caller holds, in role_map, the role that owns the exception
--   (exceptions.owner_role, set from the rule register at detection), AND
--   that role holds the action on 'proposals' in authority.
--
-- Role codes are the ones the rule register already uses (owner_role):
--   PMS379      PEO Carriers / PMS 379: cost capture items, EVM responses,
--               change order actions
--   NAVY_FMO    Navy accounting and FMO: valuation determinations, CIP
--               classification, placed in service
--   OUSD_C_FMO  OUSD(C) FMO: enterprise policy and rule register versions
--   NAVY_FMC    Navy FM&C: Navy-level decisions
--   DFAS        reconciliation response (no action in the vocabulary yet,
--               so read-only until it exists)
--   AUDITOR     DoD IG, GAO: read only. No row in authority, so every
--               action is refused with the reason, by construction.
--
-- The app service principal is granted nothing here. Every write below is
-- made by the user, on their own token, through apply_block().

-- 1. Every apply or reject attempt, allowed or refused --------------------
-- A refusal is part of the record: who tried, what, and the server's reason.
-- Allowed attempts carry the decision_id their transaction wrote.
CREATE TABLE IF NOT EXISTS users.xiaobing_shang1_civ.aircarrier_app_decision_attempts (
  attempt_id   STRING    NOT NULL,
  request_id   STRING    NOT NULL COMMENT 'Client idempotency key. A replay returns the first outcome',
  proposal_id  STRING    NOT NULL,
  exception_id STRING             COMMENT 'NULL when the proposal names no exception',
  actor        STRING    NOT NULL COMMENT 'current_user() under the caller token',
  action       STRING    NOT NULL,
  outcome      STRING    NOT NULL,
  reason_code  STRING    NOT NULL COMMENT 'harness_sql.REASON_CODES',
  reason       STRING    NOT NULL COMMENT 'The sentence shown to the caller',
  role_used    STRING,
  decision_id  STRING,
  attempted_at TIMESTAMP NOT NULL
)
COMMENT 'Every apply or reject attempt on a proposal, with the server authority result. Insert only.'
TBLPROPERTIES ('delta.feature.catalogManaged' = 'supported');

ALTER TABLE users.xiaobing_shang1_civ.aircarrier_app_decision_attempts
  ADD CONSTRAINT attempt_action CHECK (action IN ('apply', 'reject'));
ALTER TABLE users.xiaobing_shang1_civ.aircarrier_app_decision_attempts
  ADD CONSTRAINT attempt_outcome CHECK (outcome IN ('allowed', 'refused'));
ALTER TABLE users.xiaobing_shang1_civ.aircarrier_app_decision_attempts
  ADD CONSTRAINT attempt_decision CHECK ((outcome = 'allowed') = (decision_id IS NOT NULL));

-- 2. The authority matrix -------------------------------------------------
MERGE INTO users.xiaobing_shang1_civ.aircarrier_app_authority AS t
USING (SELECT * FROM VALUES
  ('PMS379',     'proposals',     'apply',          'component'),
  ('PMS379',     'proposals',     'reject',         'component'),
  ('NAVY_FMO',   'proposals',     'apply',          'navy'),
  ('NAVY_FMO',   'proposals',     'reject',         'navy'),
  ('NAVY_FMC',   'proposals',     'apply',          'navy'),
  ('NAVY_FMC',   'proposals',     'reject',         'navy'),
  ('OUSD_C_FMO', 'proposals',     'apply',          'enterprise'),
  ('OUSD_C_FMO', 'proposals',     'reject',         'enterprise'),
  ('OUSD_C_FMO', 'rule_register', 'insert_version', 'enterprise')
  AS v(role, target_table, action, scope)) AS s
ON t.role = s.role AND t.target_table = s.target_table AND t.action = s.action
WHEN NOT MATCHED THEN INSERT (role, target_table, action, scope)
  VALUES (s.role, s.target_table, s.action, s.scope);

-- 3. The pilot role assignment --------------------------------------------
-- uc_group holds an account group name or, for a named person, their
-- email; authority_check matches either (is_account_group_member or
-- current_user()). One person during the pilot: the program owner holds
-- PMS379, the role that owns every open cost-capture exception. Others are
-- added the same way, and ended by setting effective_to, never by DELETE.
MERGE INTO users.xiaobing_shang1_civ.aircarrier_app_role_map AS t
USING (SELECT * FROM VALUES
  ('xiaobing.shang1.civ@mail.mil', 'PMS379', 'PEO Carriers')
  AS v(uc_group, role, component)) AS s
ON t.uc_group = s.uc_group AND t.role = s.role AND t.effective_to IS NULL
WHEN NOT MATCHED THEN INSERT (uc_group, role, component, effective_from, effective_to, created_by)
  VALUES (s.uc_group, s.role, s.component, current_timestamp(), NULL, current_user());
