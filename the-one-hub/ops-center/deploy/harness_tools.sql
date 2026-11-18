-- UC SQL functions: the seven agent read tools (task 5, C2).
-- Each returns a JSON STRING so the tool-calling loop can pass it to the model.
-- Parameterized, no free SQL. Record citation comes from the function contract:
-- every return value names the records it read.
-- Run with ${S} = users.xiaobing_shang1_civ. Statements separated by ";\n".

-- ── 1. get_exception ─────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION ${S}.aircarrier_tool_get_exception(
  p_exception_id STRING COMMENT 'The exception_id to look up.'
)
RETURNS STRING
COMMENT 'Returns the full exception row as JSON, including rule_id, rule_version, subject_ids, dollar_amount, owner_office, required_action and status.'
RETURN
  SELECT coalesce((
    SELECT to_json(named_struct(
      'exception_id', exception_id, 'rule_id', rule_id,
      'rule_version', rule_version, 'subject_type', subject_type,
      'subject_ids', subject_ids, 'detected_at', detected_at,
      'dollar_amount', dollar_amount, 'owner_role', owner_role,
      'owner_office', owner_office, 'required_action', required_action,
      'window_closes_at', window_closes_at, 'status', status,
      'area', area, 'eval_id', eval_id,
      'record_ids', subject_ids)
    ) FROM ${S}.aircarrier_app_exceptions
    WHERE exception_id = p_exception_id
    LIMIT 1
  ), '{"error": "not_found"}');

-- ── 2. get_rule ──────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION ${S}.aircarrier_tool_get_rule(
  p_rule_id STRING COMMENT 'Rule identifier, e.g. CC-01.',
  p_version INT COMMENT 'Version number. Pass NULL for the current version (the active one, else the latest with its status).'
)
RETURNS STRING
COMMENT 'Returns the rule definition as JSON: statement_text, expression_sql, params, value_lists, status, resolved_as. version=NULL returns the current active version; if the rule has no active version it returns the latest version with its status (for example blocked_no_source) and resolved_as=no_active_version. not_found means the rule_id (or that version) is not in the register.'
-- A-32 (2026-11-11): version=NULL used to filter status = active, so a rule
-- that exists but is blocked (CC-01 v1, blocked_no_source) came back as
-- not_found, and agents reported it as missing. Now not_found is returned only
-- when the register has no row; a blocked rule is returned with its status.
-- Parameters appear only in WHERE clauses: a SQL UDF may not reference them in
-- a subquery's SELECT list or ORDER BY (UNSUPPORTED_SUBQUERY_EXPRESSION_CATEGORY),
-- so the three cases are three subqueries, tried in order.
RETURN
  SELECT coalesce(
    -- 1. an explicit version. A-30: the register is insert-only, so an old
    -- version keeps its stored status; lifecycle = 'superseded' and
    -- superseded_by say a newer version has taken effect (as current_rules).
    (SELECT to_json(named_struct(
      'rule_id', rule_id, 'version', version,
      'effective_from', effective_from, 'effective_to', effective_to,
      'owner_role', owner_role, 'statement_text', statement_text,
      'expression_sql', expression_sql, 'params', params,
      'value_lists', value_lists, 'status', status,
      'area', area, 'blocked_reason', blocked_reason,
      'resolved_as', 'requested_version',
      'lifecycle', CASE WHEN version < latest_eff THEN 'superseded' ELSE status END,
      'superseded_by', CASE WHEN version < latest_eff THEN latest_eff END))
     FROM (SELECT *, MAX(CASE WHEN effective_from <= current_timestamp() THEN version END)
                       OVER (PARTITION BY rule_id) AS latest_eff
           FROM ${S}.aircarrier_app_rule_register)
     WHERE p_version IS NOT NULL AND rule_id = p_rule_id AND version = p_version
     LIMIT 1),
    -- 2. version NULL: the active, effective version
    (SELECT to_json(named_struct(
      'rule_id', rule_id, 'version', version,
      'effective_from', effective_from, 'effective_to', effective_to,
      'owner_role', owner_role, 'statement_text', statement_text,
      'expression_sql', expression_sql, 'params', params,
      'value_lists', value_lists, 'status', status,
      'area', area, 'blocked_reason', blocked_reason,
      'resolved_as', 'current_active'))
     FROM ${S}.aircarrier_app_rule_register
     WHERE p_version IS NULL AND rule_id = p_rule_id AND status = 'active'
       AND effective_from <= current_timestamp()
       AND (effective_to IS NULL OR effective_to > current_timestamp())
     ORDER BY version DESC
     LIMIT 1),
    -- 3. version NULL, no active version: the latest version with its status
    (SELECT to_json(named_struct(
      'rule_id', rule_id, 'version', version,
      'effective_from', effective_from, 'effective_to', effective_to,
      'owner_role', owner_role, 'statement_text', statement_text,
      'expression_sql', expression_sql, 'params', params,
      'value_lists', value_lists, 'status', status,
      'area', area, 'blocked_reason', blocked_reason,
      'resolved_as', 'no_active_version',
      'note', concat('This rule has no active version. Version ', CAST(version AS STRING),
                     ' is its latest, with status ', status,
                     '. The rule exists; it is not missing.')))
     FROM ${S}.aircarrier_app_rule_register
     WHERE p_version IS NULL AND rule_id = p_rule_id
     ORDER BY version DESC
     LIMIT 1),
    '{"error": "not_found"}');

-- ── 3. get_document_text ─────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION ${S}.aircarrier_tool_get_document_text(
  p_document_id STRING COMMENT 'The document_id from the documents table.',
  p_page_start INT COMMENT 'First page (1-based). NULL for all pages.',
  p_page_end INT COMMENT 'Last page (inclusive). NULL for a single page or all.'
)
RETURNS STRING
COMMENT 'Returns document page text as a JSON array of {page, text} objects. Joins the documents register to the PDF page store. Returns error if the document is not registered.'
RETURN
  SELECT coalesce(
    to_json(collect_list(named_struct('page', p.page, 'text', p.text))),
    '{"error": "not_found"}')
  FROM ${S}.aircarrier_app_documents d
  JOIN ${S}.aircarrier_srcv_pdf_pages p
    ON p.filename = regexp_extract(d.volume_path, '[^/]+$', 0)
  WHERE d.document_id = p_document_id
    AND (p_page_start IS NULL OR p.page >= p_page_start)
    AND (p_page_end IS NULL OR p.page <= coalesce(p_page_end, p_page_start));

-- ── 4. get_cost_capture ──────────────────────────────────────────────────────
-- BLOCKED: requires IPMDAR, CCDR, GL/ledger recorded cost, and CLIN funding
-- authority feeds, none of which exist in this workspace (C5).
CREATE OR REPLACE FUNCTION ${S}.aircarrier_tool_get_cost_capture(
  p_wbs STRING COMMENT 'WBS element at level 3.',
  p_clin STRING COMMENT 'Contract line item number.',
  p_period_start STRING COMMENT 'Start of period (YYYY-MM).',
  p_period_end STRING COMMENT 'End of period (YYYY-MM).'
)
RETURNS STRING
COMMENT 'Returns cost capture data: contractor incurred vs. recorded cost by WBS/CLIN. BLOCKED: the source feeds (IPMDAR, CCDR, GL ledger) do not exist in this workspace.'
RETURN '{"status": "blocked_no_source", "feed": "IPMDAR, CCDR, GL/ledger recorded cost, CLIN funding authority", "message": "This tool cannot return data until the missing feeds are ingested. The rules that depend on it (CC-01, CC-03, CC-04) are seeded as blocked_no_source."}';

-- ── 5. get_evm_control_account ───────────────────────────────────────────────
-- BLOCKED: requires EVM/CPI/SPI/TCPI data, BCWS baselines, and management
-- reserve data.
CREATE OR REPLACE FUNCTION ${S}.aircarrier_tool_get_evm_control_account(
  p_control_account_id STRING COMMENT 'Control account identifier.',
  p_period_start STRING COMMENT 'Start of period (YYYY-MM).',
  p_period_end STRING COMMENT 'End of period (YYYY-MM).'
)
RETURNS STRING
COMMENT 'Returns EVM data: CPI, SPI, TCPI, BCWS, ACWP, EAC at control account. BLOCKED: the source feeds (EVM/CPI/SPI data, baselines, management reserve) do not exist in this workspace.'
RETURN '{"status": "blocked_no_source", "feed": "EVM performance data, BCWS baselines, management reserve", "message": "This tool cannot return data until the missing feeds are ingested. The rules that depend on it (EV-01 through EV-04) are seeded as blocked_no_source."}';

-- ── 6. get_cap_ledger ────────────────────────────────────────────────────────
-- BLOCKED: requires GL/CIP transactions, SCN end cost accounts, and post-
-- delivery (OPN, O&M,N) account data.
CREATE OR REPLACE FUNCTION ${S}.aircarrier_tool_get_cap_ledger(
  p_as_of STRING COMMENT 'Point-in-time date (YYYY-MM-DD).'
)
RETURNS STRING
COMMENT 'Returns the cost cap ledger: amounts counted toward 10 USC 8692 limitation, exclusions, adjustments, and headroom. BLOCKED: the source feeds (GL/CIP, SCN end cost, post-delivery accounts) do not exist in this workspace.'
RETURN '{"status": "blocked_no_source", "feed": "GL/CIP transactions, SCN end cost, OPN/O&M,N post-delivery accounts", "message": "This tool cannot return data until the missing feeds are ingested. The rules that depend on it (CAP-01 through CAP-04) are seeded as blocked_no_source."}';

-- ── 7. get_cip_transactions ──────────────────────────────────────────────────
-- BLOCKED: requires CIP transaction ledger, GFE/GFM transfer records, and
-- DD 250 acceptance documentation.
CREATE OR REPLACE FUNCTION ${S}.aircarrier_tool_get_cip_transactions(
  p_cost_element STRING COMMENT 'Cost element code or NULL for all.',
  p_period_start STRING COMMENT 'Start of period (YYYY-MM).',
  p_period_end STRING COMMENT 'End of period (YYYY-MM).'
)
RETURNS STRING
COMMENT 'Returns CIP transactions: accumulation by cost element, GFE/GFM transfers, source document linkage. BLOCKED: the source feeds (CIP ledger, GFE/GFM transfers, DD 250) do not exist in this workspace.'
RETURN '{"status": "blocked_no_source", "feed": "CIP transaction ledger, GFE/GFM transfers, DD 250 records", "message": "This tool cannot return data until the missing feeds are ingested. The rules that depend on it (AV-01 through AV-05) are seeded as blocked_no_source."}';
