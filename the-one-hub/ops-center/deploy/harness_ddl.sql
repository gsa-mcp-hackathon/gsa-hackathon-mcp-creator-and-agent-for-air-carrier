-- Harness application tables (B27, C4). One schema, prefix aircarrier_app_.
-- Spec columns kept verbatim. Every table the apply transaction writes carries
-- catalog commits (delta.feature.catalogManaged) so BEGIN ATOMIC can write it.
-- Idempotent: CREATE ... IF NOT EXISTS only. No DROP, no ALTER of existing data.
-- Run with ${S} = users.xiaobing_shang1_civ. Statements are separated by ";\n".

CREATE TABLE IF NOT EXISTS ${S}.aircarrier_app_rule_register (
  rule_id STRING NOT NULL, version INT NOT NULL,
  effective_from TIMESTAMP NOT NULL, effective_to TIMESTAMP,
  owner_role STRING NOT NULL, statement_text STRING NOT NULL,
  expression_sql STRING, params MAP<STRING,STRING>, value_lists MAP<STRING,ARRAY<STRING>>,
  status STRING NOT NULL,            -- active | retired | blocked_no_source | blocked_param_unset
  created_by STRING NOT NULL, created_at TIMESTAMP NOT NULL,
  owner_office STRING, required_action STRING, area STRING, blocked_reason STRING
) TBLPROPERTIES ('delta.feature.catalogManaged'='supported',
                 'comment'='Insert-only rule register. Never UPDATE; insert a new version.');

CREATE TABLE IF NOT EXISTS ${S}.aircarrier_app_rule_register_audit (
  audit_id STRING NOT NULL, rule_id STRING NOT NULL, version INT NOT NULL,
  event STRING NOT NULL,             -- insert | retire
  actor STRING NOT NULL, actor_role STRING, event_at TIMESTAMP NOT NULL,
  prior_params MAP<STRING,STRING>, new_params MAP<STRING,STRING>, notes STRING
) TBLPROPERTIES ('delta.feature.catalogManaged'='supported');

CREATE TABLE IF NOT EXISTS ${S}.aircarrier_app_exceptions (
  exception_id STRING NOT NULL, rule_id STRING NOT NULL, rule_version INT NOT NULL,
  subject_type STRING NOT NULL, subject_ids ARRAY<STRING> NOT NULL,
  detected_at TIMESTAMP NOT NULL, dollar_amount DECIMAL(20,2),
  owner_role STRING NOT NULL, owner_office STRING NOT NULL, required_action STRING NOT NULL,
  window_closes_at TIMESTAMP, status STRING NOT NULL,   -- open | resolved | superseded | void_test_data
                                                        -- void_test_data: raised on seed/test subjects (test-wbs-*), closed
                                                        -- without resolution (2026-11-11, table version 11). All code reads
                                                        -- status <> 'open' as closed.
  area STRING, eval_id STRING NOT NULL
) TBLPROPERTIES ('delta.feature.catalogManaged'='supported');

CREATE TABLE IF NOT EXISTS ${S}.aircarrier_app_rule_evals (
  eval_id STRING NOT NULL, trigger STRING NOT NULL, triggered_by STRING NOT NULL,
  started_at TIMESTAMP NOT NULL, ended_at TIMESTAMP,
  rules_evaluated ARRAY<STRUCT<rule_id:STRING, version:INT, rows:BIGINT, status:STRING, error:STRING>>
) TBLPROPERTIES ('delta.feature.catalogManaged'='supported');

CREATE TABLE IF NOT EXISTS ${S}.aircarrier_app_agent_runs (
  run_id STRING NOT NULL, trigger STRING NOT NULL, triggered_by STRING NOT NULL,
  started_at TIMESTAMP NOT NULL, ended_at TIMESTAMP,
  orchestrator_version STRING NOT NULL, mlflow_trace_id STRING,
  subject_kind STRING, subject_id STRING, specialist STRING,
  outcome STRING                     -- released | blocked_by_checker | error
) TBLPROPERTIES ('delta.feature.catalogManaged'='supported');

CREATE TABLE IF NOT EXISTS ${S}.aircarrier_app_agent_steps (
  run_id STRING NOT NULL, step_seq INT NOT NULL,
  agent_name STRING NOT NULL, agent_version STRING NOT NULL, model_endpoint STRING,
  rule_id STRING, rule_version INT, record_ids ARRAY<STRING>,
  inputs_digest STRING NOT NULL, output_json STRING, tokens INT, latency_ms BIGINT,
  prompt_sha STRING
) TBLPROPERTIES ('delta.feature.catalogManaged'='supported');

CREATE TABLE IF NOT EXISTS ${S}.aircarrier_app_checker_verdicts (
  run_id STRING NOT NULL, step_seq INT NOT NULL,
  verdict STRING NOT NULL,           -- pass | pass_with_exception | fail
  checks ARRAY<STRUCT<check_name:STRING, expected:STRING, actual:STRING, result:STRING>> NOT NULL,
  notes STRING, checker_agent STRING, model_endpoint STRING, decided_at TIMESTAMP
) TBLPROPERTIES ('delta.feature.catalogManaged'='supported');

CREATE TABLE IF NOT EXISTS ${S}.aircarrier_app_proposals (
  proposal_id STRING NOT NULL, run_id STRING NOT NULL,
  target_table STRING NOT NULL, target_key STRING NOT NULL, proposed_payload STRING NOT NULL,
  grounding ARRAY<STRUCT<field:STRING, document_id:STRING, page:INT, text_span:STRING>>,
  schema_validation STRING, status STRING NOT NULL, block_reason STRING,
  exception_id STRING, rule_id STRING, rule_version INT, record_ids ARRAY<STRING>,
  created_at TIMESTAMP NOT NULL, intake_outcome STRING   -- ready | duplicate | blocked (intake only)
) TBLPROPERTIES ('delta.feature.catalogManaged'='supported');

CREATE TABLE IF NOT EXISTS ${S}.aircarrier_app_decisions (
  decision_id STRING NOT NULL, proposal_id STRING NOT NULL, exception_id STRING,
  actor STRING NOT NULL, actor_role STRING, action STRING NOT NULL,
  decided_at TIMESTAMP NOT NULL, authority_check_result STRING NOT NULL, notes STRING
) TBLPROPERTIES ('delta.feature.catalogManaged'='supported');

CREATE TABLE IF NOT EXISTS ${S}.aircarrier_app_documents (
  document_id STRING NOT NULL, volume_path STRING NOT NULL, doc_type STRING NOT NULL,
  received_at TIMESTAMP NOT NULL, sha256 STRING NOT NULL, registered_by STRING
) TBLPROPERTIES ('delta.feature.catalogManaged'='supported');

CREATE TABLE IF NOT EXISTS ${S}.aircarrier_app_model_runs (
  model_run_id STRING NOT NULL, scenario_params MAP<STRING,STRING>,
  inputs_vintage MAP<STRING,TIMESTAMP>, rule_version MAP<STRING,INT>,
  assumptions ARRAY<STRING>, outputs STRING NOT NULL,
  model_version STRING NOT NULL, created_at TIMESTAMP NOT NULL, created_by STRING NOT NULL,
  input_record_ids ARRAY<STRING>, warnings ARRAY<STRING>
) TBLPROPERTIES ('delta.feature.catalogManaged'='supported');

-- Applied determinations land here, only via the apply procedure.
CREATE TABLE IF NOT EXISTS ${S}.aircarrier_app_determinations (
  determination_id STRING NOT NULL, proposal_id STRING NOT NULL, decision_id STRING NOT NULL,
  target_table STRING NOT NULL, target_key STRING NOT NULL, payload STRING NOT NULL,
  component STRING NOT NULL, applied_at TIMESTAMP NOT NULL, applied_by STRING NOT NULL
) TBLPROPERTIES ('delta.feature.catalogManaged'='supported');

-- Metrics recomputed inside the apply transaction (invariant 9).
CREATE TABLE IF NOT EXISTS ${S}.aircarrier_app_metrics (
  metric_id STRING NOT NULL, computed_at TIMESTAMP NOT NULL, value DECIMAL(20,6),
  numerator BIGINT, denominator BIGINT, record_ids ARRAY<STRING>,
  trigger_decision_id STRING, definition_sql STRING
) TBLPROPERTIES ('delta.feature.catalogManaged'='supported');

-- Authority is data: UC group -> role, role -> what it may apply. Read by the
-- apply procedure with is_account_group_member(), never from a request field.
CREATE TABLE IF NOT EXISTS ${S}.aircarrier_app_role_map (
  uc_group STRING NOT NULL, role STRING NOT NULL, component STRING NOT NULL,
  effective_from TIMESTAMP NOT NULL, effective_to TIMESTAMP, created_by STRING NOT NULL
) TBLPROPERTIES ('delta.feature.catalogManaged'='supported');

CREATE TABLE IF NOT EXISTS ${S}.aircarrier_app_authority (
  role STRING NOT NULL, target_table STRING NOT NULL, action STRING NOT NULL,
  scope STRING NOT NULL               -- enterprise | navy | component | none
) TBLPROPERTIES ('delta.feature.catalogManaged'='supported');

-- CHECK constraints: CREATE TABLE accepts only PK/FK inline, so they are added
-- here. The runner treats CONSTRAINT_ALREADY_EXISTS as success (idempotent).
-- Invariant 7 is enforced by the table itself: a detection with no owner office
-- or required action cannot be written by any path.
ALTER TABLE ${S}.aircarrier_app_exceptions ADD CONSTRAINT owner_office_nonempty CHECK (length(trim(owner_office)) > 0);
ALTER TABLE ${S}.aircarrier_app_exceptions ADD CONSTRAINT required_action_nonempty CHECK (length(trim(required_action)) > 0);
ALTER TABLE ${S}.aircarrier_app_exceptions ADD CONSTRAINT subject_ids_nonempty CHECK (size(subject_ids) > 0);
ALTER TABLE ${S}.aircarrier_app_checker_verdicts ADD CONSTRAINT verdict_enum CHECK (verdict IN ('pass','pass_with_exception','fail'));
ALTER TABLE ${S}.aircarrier_app_proposals ADD CONSTRAINT status_enum CHECK (status IN ('pending','applied','rejected','blocked'));
ALTER TABLE ${S}.aircarrier_app_decisions ADD CONSTRAINT action_enum CHECK (action IN ('apply','reject'));
ALTER TABLE ${S}.aircarrier_app_agent_steps ADD CONSTRAINT citation_complete CHECK (agent_name = 'orchestrator' OR (rule_id IS NOT NULL AND rule_version IS NOT NULL AND size(record_ids) > 0));

CREATE OR REPLACE VIEW ${S}.aircarrier_app_current_rules AS
SELECT r.* FROM ${S}.aircarrier_app_rule_register r
WHERE r.status = 'active'
  AND r.effective_from <= current_timestamp()
  AND (r.effective_to IS NULL OR r.effective_to > current_timestamp())
  AND NOT EXISTS (SELECT 1 FROM ${S}.aircarrier_app_rule_register n
                  WHERE n.rule_id = r.rule_id AND n.version > r.version
                    AND n.effective_from <= current_timestamp());

-- Rule as it stood at any instant (acceptance test 10).
CREATE OR REPLACE FUNCTION ${S}.aircarrier_app_rule_at(p_rule_id STRING, p_at TIMESTAMP)
RETURNS TABLE (rule_id STRING, version INT, params MAP<STRING,STRING>, expression_sql STRING, status STRING)
RETURN SELECT rule_id, version, params, expression_sql, status
  FROM ${S}.aircarrier_app_rule_register
  WHERE rule_id = p_rule_id AND effective_from <= p_at
    AND (effective_to IS NULL OR effective_to > p_at)
  ORDER BY version DESC LIMIT 1;
