-- Grants for the harness agent principal (invariant 10, B27 C4).
-- Principal (B29, decided by the user 2026-11-10: work with the current role
-- and the existing service principals, no admin): the front-center app SP
-- 7e1ec6c0-bbe4-43db-a519-1c1fcd99f9c9 ("app-2vrjmx aircarrier-front-center-dev").
-- The harness orchestrator runs inside that app, so its identity is the agent
-- principal. Authority-bearing calls (apply, reject, POST /rules) do NOT use
-- it: they run on the end user's on-behalf-of token (B28 item 4).
-- Run by the schema owner (xiaobing.shang1.civ@mail.mil). Order matters:
--   1. the GRANTs below and the srcv_ GRANTs in grants_front_center.sql;
--   2. redeploy the app (api/live.py now reads the srcv_ views);
--   3. the REVOKEs at the end. Between 1 and 3 nothing breaks; if 3 runs
--      before 2, live pages fall back to the shipped extracts (D11) until the
--      redeploy, they do not error.
-- USE CATALOG on `users` is not granted here: `account users` already holds it.
--
-- What the agent principal gets, and nothing more:
--   * SELECT on the 8 aircarrier_srcv_* views. No grant of any kind on any
--     aircarrier_src_* base table (the REVOKEs below remove the four it held)
--     or jb_* table. Views run with the view owner's rights, so the base
--     tables need no grant. Because this SP is also the app, it keeps the
--     read-only SELECTs in grants_front_center.sql on the app-derived stores
--     (pdf_tables, pdf_cells, claim, gate, ...). None of those is a source
--     system and none carries MODIFY.
--   * SELECT on the application tables the specialists and checker read.
--   * MODIFY only on five tables: the three lineage tables the orchestrator
--     appends to (agent_runs, agent_steps, checker_verdicts), proposals
--     (stage_proposal) and model_runs (run_cost_model_scenario). Delta has no
--     INSERT-only privilege, so MODIFY also permits UPDATE/DELETE on those five
--     tables; the code path is
--     append-only and checks/no_source_write.py fails the build on any UPDATE,
--     DELETE or MERGE against them outside ops/harness/apply.
--   * NO grant on rule_register, rule_register_audit, exceptions, decisions,
--     determinations, metrics, role_map or authority. Those are written only
--     by the rule evaluation job and the apply path, under other identities.

GRANT USE SCHEMA ON SCHEMA users.xiaobing_shang1_civ TO `7e1ec6c0-bbe4-43db-a519-1c1fcd99f9c9`;

GRANT SELECT ON VIEW users.xiaobing_shang1_civ.aircarrier_srcv_fpds_2114_transactions TO `7e1ec6c0-bbe4-43db-a519-1c1fcd99f9c9`;
GRANT SELECT ON VIEW users.xiaobing_shang1_civ.aircarrier_srcv_fpds_2116_transactions TO `7e1ec6c0-bbe4-43db-a519-1c1fcd99f9c9`;
GRANT SELECT ON VIEW users.xiaobing_shang1_civ.aircarrier_srcv_file_c_2114 TO `7e1ec6c0-bbe4-43db-a519-1c1fcd99f9c9`;
GRANT SELECT ON VIEW users.xiaobing_shang1_civ.aircarrier_srcv_subawards_2114 TO `7e1ec6c0-bbe4-43db-a519-1c1fcd99f9c9`;
GRANT SELECT ON VIEW users.xiaobing_shang1_civ.aircarrier_srcv_funding_history TO `7e1ec6c0-bbe4-43db-a519-1c1fcd99f9c9`;
GRANT SELECT ON VIEW users.xiaobing_shang1_civ.aircarrier_srcv_jb_ship_cost TO `7e1ec6c0-bbe4-43db-a519-1c1fcd99f9c9`;
GRANT SELECT ON VIEW users.xiaobing_shang1_civ.aircarrier_srcv_jb_funding_tranche TO `7e1ec6c0-bbe4-43db-a519-1c1fcd99f9c9`;
GRANT SELECT ON VIEW users.xiaobing_shang1_civ.aircarrier_srcv_pdf_pages TO `7e1ec6c0-bbe4-43db-a519-1c1fcd99f9c9`;

GRANT SELECT ON VIEW  users.xiaobing_shang1_civ.aircarrier_app_current_rules TO `7e1ec6c0-bbe4-43db-a519-1c1fcd99f9c9`;
GRANT SELECT ON TABLE users.xiaobing_shang1_civ.aircarrier_app_rule_register TO `7e1ec6c0-bbe4-43db-a519-1c1fcd99f9c9`;
GRANT SELECT ON TABLE users.xiaobing_shang1_civ.aircarrier_app_exceptions TO `7e1ec6c0-bbe4-43db-a519-1c1fcd99f9c9`;
GRANT SELECT ON TABLE users.xiaobing_shang1_civ.aircarrier_app_documents TO `7e1ec6c0-bbe4-43db-a519-1c1fcd99f9c9`;
GRANT SELECT ON TABLE users.xiaobing_shang1_civ.aircarrier_app_model_runs TO `7e1ec6c0-bbe4-43db-a519-1c1fcd99f9c9`;
GRANT EXECUTE ON FUNCTION users.xiaobing_shang1_civ.aircarrier_app_rule_at TO `7e1ec6c0-bbe4-43db-a519-1c1fcd99f9c9`;

GRANT SELECT, MODIFY ON TABLE users.xiaobing_shang1_civ.aircarrier_app_agent_runs TO `7e1ec6c0-bbe4-43db-a519-1c1fcd99f9c9`;
GRANT SELECT, MODIFY ON TABLE users.xiaobing_shang1_civ.aircarrier_app_agent_steps TO `7e1ec6c0-bbe4-43db-a519-1c1fcd99f9c9`;
GRANT SELECT, MODIFY ON TABLE users.xiaobing_shang1_civ.aircarrier_app_checker_verdicts TO `7e1ec6c0-bbe4-43db-a519-1c1fcd99f9c9`;
GRANT SELECT, MODIFY ON TABLE users.xiaobing_shang1_civ.aircarrier_app_proposals TO `7e1ec6c0-bbe4-43db-a519-1c1fcd99f9c9`;
GRANT SELECT, MODIFY ON TABLE users.xiaobing_shang1_civ.aircarrier_app_model_runs TO `7e1ec6c0-bbe4-43db-a519-1c1fcd99f9c9`;

-- The seven read tools (task 5). Each is a UC SQL function returning JSON.
GRANT EXECUTE ON FUNCTION users.xiaobing_shang1_civ.aircarrier_tool_get_exception TO `7e1ec6c0-bbe4-43db-a519-1c1fcd99f9c9`;
GRANT EXECUTE ON FUNCTION users.xiaobing_shang1_civ.aircarrier_tool_get_rule TO `7e1ec6c0-bbe4-43db-a519-1c1fcd99f9c9`;
GRANT EXECUTE ON FUNCTION users.xiaobing_shang1_civ.aircarrier_tool_get_document_text TO `7e1ec6c0-bbe4-43db-a519-1c1fcd99f9c9`;
GRANT EXECUTE ON FUNCTION users.xiaobing_shang1_civ.aircarrier_tool_get_cost_capture TO `7e1ec6c0-bbe4-43db-a519-1c1fcd99f9c9`;
GRANT EXECUTE ON FUNCTION users.xiaobing_shang1_civ.aircarrier_tool_get_evm_control_account TO `7e1ec6c0-bbe4-43db-a519-1c1fcd99f9c9`;
GRANT EXECUTE ON FUNCTION users.xiaobing_shang1_civ.aircarrier_tool_get_cap_ledger TO `7e1ec6c0-bbe4-43db-a519-1c1fcd99f9c9`;
GRANT EXECUTE ON FUNCTION users.xiaobing_shang1_civ.aircarrier_tool_get_cip_transactions TO `7e1ec6c0-bbe4-43db-a519-1c1fcd99f9c9`;

-- Step 3: the agent principal keeps no grant on any source base table.
REVOKE SELECT ON TABLE users.xiaobing_shang1_civ.aircarrier_src_2114_contract_transactions FROM `7e1ec6c0-bbe4-43db-a519-1c1fcd99f9c9`;
REVOKE SELECT ON TABLE users.xiaobing_shang1_civ.aircarrier_src_2116_contract_transactions FROM `7e1ec6c0-bbe4-43db-a519-1c1fcd99f9c9`;
REVOKE SELECT ON TABLE users.xiaobing_shang1_civ.aircarrier_src_2114_federal_account_funding FROM `7e1ec6c0-bbe4-43db-a519-1c1fcd99f9c9`;
REVOKE SELECT ON TABLE users.xiaobing_shang1_civ.aircarrier_src_2114_subawards FROM `7e1ec6c0-bbe4-43db-a519-1c1fcd99f9c9`;

-- Verification after applying (expected: no row with MODIFY on any srcv_/src_/jb_/pdf_ object):
--   SHOW GRANTS `7e1ec6c0-bbe4-43db-a519-1c1fcd99f9c9` ON SCHEMA users.xiaobing_shang1_civ;
--   checks/no_source_write.py --principal 7e1ec6c0-bbe4-43db-a519-1c1fcd99f9c9
