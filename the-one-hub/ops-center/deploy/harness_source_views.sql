-- Read-only source views for the harness (invariant 10, C4).
-- The agent principal gets SELECT on these views and nothing else on any
-- source object. Views are the only path from the harness to source data.
-- Prefix aircarrier_srcv_. Run with ${S} = users.xiaobing_shang1_civ.
--
-- Feeds the spec names that DO NOT EXIST in this workspace (C5) have no view:
-- IPMDAR, CCDR, EVM control accounts, CDRL due dates, GL / CIP ledger,
-- DD 250 / DD 1149, progress payment vouchers, GFE/GFM transfers, management
-- reserve, OPN / O&M,N post-delivery accounts, cap adjustment claims.
-- A view is added here in the same change that lands the feed.

CREATE OR REPLACE VIEW ${S}.aircarrier_srcv_fpds_2114_transactions
COMMENT 'Read-only. USAspending/FPDS prime transactions, N00024-15-C-2114 (DD&C).'
AS SELECT * FROM ${S}.aircarrier_src_2114_contract_transactions;

CREATE OR REPLACE VIEW ${S}.aircarrier_srcv_fpds_2116_transactions
COMMENT 'Read-only. USAspending/FPDS prime transactions, N00024-09-C-2116 (construction prep).'
AS SELECT * FROM ${S}.aircarrier_src_2116_contract_transactions;

CREATE OR REPLACE VIEW ${S}.aircarrier_srcv_file_c_2114
COMMENT 'Read-only. USAspending File C federal account funding, 15-C-2114.'
AS SELECT * FROM ${S}.aircarrier_src_2114_federal_account_funding;

CREATE OR REPLACE VIEW ${S}.aircarrier_srcv_subawards_2114
COMMENT 'Read-only. USAspending sub-awards, 15-C-2114.'
AS SELECT * FROM ${S}.aircarrier_src_2114_subawards;

CREATE OR REPLACE VIEW ${S}.aircarrier_srcv_funding_history
COMMENT 'Read-only. Funding history source table.'
AS SELECT * FROM ${S}.aircarrier_src_funding_history;

CREATE OR REPLACE VIEW ${S}.aircarrier_srcv_jb_ship_cost
COMMENT 'Read-only. J-book P-5/P-5c ship cost cells, PB2008-PB2027.'
AS SELECT * FROM ${S}.aircarrier_jb_ship_cost;

CREATE OR REPLACE VIEW ${S}.aircarrier_srcv_jb_funding_tranche
COMMENT 'Read-only. J-book funding tranches with derived TAS.'
AS SELECT * FROM ${S}.aircarrier_jb_funding_tranche;

CREATE OR REPLACE VIEW ${S}.aircarrier_srcv_pdf_pages
COMMENT 'Read-only. Page text of every registered PDF (document_text tool).'
AS SELECT * FROM ${S}.aircarrier_pdf_pages;
