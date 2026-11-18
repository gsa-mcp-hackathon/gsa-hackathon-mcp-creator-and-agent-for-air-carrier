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

-- sales (uc_table)
GRANT USE CATALOG ON CATALOG samples TO `$app_sp`;
GRANT USE SCHEMA ON SCHEMA samples.bakehouse TO `$app_sp`;
GRANT SELECT ON TABLE samples.bakehouse.sales_transactions TO `$app_sp`;

-- The SQL warehouse is granted through the bundle resource in
-- databricks.yml (permission: CAN_USE), not with a GRANT here.
