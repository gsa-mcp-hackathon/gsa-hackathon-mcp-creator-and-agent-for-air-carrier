-- Grants for the Databricks App service principal.
--
-- The app runs as its OWN identity, not as you. A server that works
-- locally and returns empty results once deployed has almost always
-- skipped this file.
--
-- Find the service principal's application id under App
-- Authorization on the app's page, then replace the placeholder
-- below and run these in a SQL editor.

-- SET VAR app_sp = '<service-principal-application-id>';

-- exhibit_cells (uc_table)
GRANT USE CATALOG ON CATALOG `users` TO `$app_sp`;
GRANT USE SCHEMA ON SCHEMA `users`.`xiaobing_shang1_civ` TO `$app_sp`;
GRANT SELECT ON TABLE `users`.`xiaobing_shang1_civ`.`aircarrier_pdf_cells` TO `$app_sp`;

-- obligations_2116 (uc_table)
GRANT SELECT ON TABLE `users`.`xiaobing_shang1_civ`.`aircarrier_src_2116_contract_transactions` TO `$app_sp`;

-- obligations_2114 (uc_table), added 2026-11-20 for carrier_search_obligations
GRANT SELECT ON TABLE `users`.`xiaobing_shang1_civ`.`aircarrier_src_2114_contract_transactions` TO `$app_sp`;

-- variances (uc_table), added 2026-11-20 for carrier_search_variances
GRANT SELECT ON TABLE `users`.`xiaobing_shang1_civ`.`aircarrier_variances` TO `$app_sp`;

-- graph_edges (uc_table)
GRANT SELECT ON TABLE `users`.`xiaobing_shang1_civ`.`aircarrier_kg_edges` TO `$app_sp`;

-- work_register (uc_table)
GRANT SELECT ON TABLE `users`.`xiaobing_shang1_civ`.`aircarrier_work` TO `$app_sp`;

-- The SQL warehouse is granted through the bundle resource in
-- databricks.yml (permission: CAN_USE), not with a GRANT here.
