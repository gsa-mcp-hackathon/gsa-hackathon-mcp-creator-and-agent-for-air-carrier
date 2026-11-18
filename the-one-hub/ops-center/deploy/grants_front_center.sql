-- Unity Catalog grants for the front-center app's service principal.
--
-- Run ONCE, by the owner of the schema, after the first deploy that adds the
-- app resources in resources/app.yml. The bundle grants the warehouse and the
-- two serving endpoints; it cannot grant table SELECT, so this file does.
--
-- Read-only by construction: SELECT on twelve tables and nothing else. No
-- MODIFY, no CREATE, no volume access. The list is api/live.py TABLES, and
-- checks/test_app.py fails if the two drift apart.
--
-- Principal: the app SP's application (client) id, from
--   databricks apps get aircarrier-front-center-dev -> service_principal_client_id
-- For dev that is 7e1ec6c0-bbe4-43db-a519-1c1fcd99f9c9. At transfer, replace it
-- and the catalog.schema below.
--
-- Applied 2026-11-10 for dev by the schema owner: USE SCHEMA + the 12 SELECTs.
-- The USE CATALOG line needs MANAGE on catalog users, which the schema owner
-- lacks; it is not needed in dev because `account users` (which includes
-- service principals) already holds USE CATALOG and USE SCHEMA on users.
-- At transfer to a catalog the owner controls, run every line.

GRANT USE CATALOG ON CATALOG users TO `7e1ec6c0-bbe4-43db-a519-1c1fcd99f9c9`;
GRANT USE SCHEMA ON SCHEMA users.xiaobing_shang1_civ TO `7e1ec6c0-bbe4-43db-a519-1c1fcd99f9c9`;

-- 2026-11-10 (B29): source data moved behind the read-only srcv_ views. This
-- SP is also the harness agent principal; see deploy/grants_harness_agent.sql
-- for its harness grants and for the REVOKEs of the four src_ base tables.
GRANT SELECT ON VIEW users.xiaobing_shang1_civ.aircarrier_srcv_fpds_2114_transactions TO `7e1ec6c0-bbe4-43db-a519-1c1fcd99f9c9`;
GRANT SELECT ON VIEW users.xiaobing_shang1_civ.aircarrier_srcv_fpds_2116_transactions TO `7e1ec6c0-bbe4-43db-a519-1c1fcd99f9c9`;
GRANT SELECT ON VIEW users.xiaobing_shang1_civ.aircarrier_srcv_file_c_2114 TO `7e1ec6c0-bbe4-43db-a519-1c1fcd99f9c9`;
GRANT SELECT ON TABLE users.xiaobing_shang1_civ.aircarrier_srcv_file_c_2116 TO `7e1ec6c0-bbe4-43db-a519-1c1fcd99f9c9`;
GRANT SELECT ON VIEW users.xiaobing_shang1_civ.aircarrier_srcv_subawards_2114 TO `7e1ec6c0-bbe4-43db-a519-1c1fcd99f9c9`;
GRANT SELECT ON TABLE users.xiaobing_shang1_civ.aircarrier_pdf_tables TO `7e1ec6c0-bbe4-43db-a519-1c1fcd99f9c9`;
GRANT SELECT ON TABLE users.xiaobing_shang1_civ.aircarrier_pdf_cells TO `7e1ec6c0-bbe4-43db-a519-1c1fcd99f9c9`;
GRANT SELECT ON TABLE users.xiaobing_shang1_civ.aircarrier_claim TO `7e1ec6c0-bbe4-43db-a519-1c1fcd99f9c9`;
GRANT SELECT ON TABLE users.xiaobing_shang1_civ.aircarrier_gate TO `7e1ec6c0-bbe4-43db-a519-1c1fcd99f9c9`;
GRANT SELECT ON TABLE users.xiaobing_shang1_civ.aircarrier_mechanism TO `7e1ec6c0-bbe4-43db-a519-1c1fcd99f9c9`;
GRANT SELECT ON TABLE users.xiaobing_shang1_civ.aircarrier_analyst_leads TO `7e1ec6c0-bbe4-43db-a519-1c1fcd99f9c9`;
GRANT SELECT ON TABLE users.xiaobing_shang1_civ.aircarrier_collection_requirements TO `7e1ec6c0-bbe4-43db-a519-1c1fcd99f9c9`;
GRANT SELECT ON TABLE users.xiaobing_shang1_civ.aircarrier_variances TO `7e1ec6c0-bbe4-43db-a519-1c1fcd99f9c9`;

-- Verify: SHOW GRANTS `7e1ec6c0-bbe4-43db-a519-1c1fcd99f9c9` ON SCHEMA users.xiaobing_shang1_civ;
-- Then GET /api/live on the app: "live": true.
