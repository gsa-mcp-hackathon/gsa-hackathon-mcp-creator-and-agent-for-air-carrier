# mcp-aircarrier-analyst

> **Scorecard:** 12 tools · 39 tests · in the read-server adversarial sweep (421 hostile calls) · probe known answer 411 of 411. Every server's row: [SCORECARD.md](../../SCORECARD.md).

An MCP server that acts as an intelligence analyst for the CVN-79 (USS John F. Kennedy) cost
reconciliation. Version 0.2 adds the case investigator.

## What it does

Given a record that is missing critical data elements (a GL line, an obligation, an invoice, a budget
figure), it works the way an analyst does:

1. **Profile.** Which critical data elements (contract, line of accounting, amount, date, vendor,
   budget line, description) are present, which are missing, why each matters, where each is
   authoritative, and who holds it.
2. **Plan.** Which skills can run on what is present, and which are waiting for a clue.
3. **Chase.** Run every runnable skill. Each one can produce new clues that unlock others, for
   example amount -> FPDS line -> PIID -> keyset verdict -> vendor and accounts -> documents.
4. **Weigh.** Every piece of evidence moves a score per case by a stated weight; softmax gives the
   confidence. Co-occurrence in documents is weighed as lift over the corpus baseline, because the
   corpus is mostly CVN 78 programme reports.
5. **Decide.** The top three cases, with evidence for and against, the clue chain with citations,
   recovered data elements, a collection requirement per missing element, and `human_review`
   with reasons and reviewer questions whenever the answer is weak, close, contested or secondary.

Cases: `CVN-79`, `CVN-78`, `CVN-80/81`, `CLASS_SHARED` (Ford-class common cost), `OTHER_CARRIER`
(Nimitz class, CV-67, CVN-65), `NOT_CARRIER`.

## Beyond CVN-79

Researching one record with missing data elements is the slowest step in audit remediation:
unsupported transactions, abnormal balances and Universe of Transactions gaps all start
there. The investigator's method (profile, plan, chase, weigh, decide, with human review on
weak answers) does not depend on the program. A new program supplies its contracts, File C,
sub-awards and key set; the six cases become that program's hulls or lots.

## Skills and what they read

| Skill | Runs on | Reads |
| --- | --- | --- |
| keyset | PIID | knowledge-graph contract nodes from `seed/keyset.yaml`: prime, excluded, multi-hull, collisions |
| fpds_amount | amount (+date) | FPDS transactions of N00024-15-C-2114 and N00024-09-C-2116 |
| filec_amount | amount | File C rows of N00024-15-C-2114 |
| subaward | vendor, UEI, amount | 2,990 sub-awards under N00024-15-C-2114 |
| tas_profile | TAS / main account | TAS vocabulary and the account lists of CVN-79 awards |
| program_code | DoD program code, PSC | codes seen on CVN-79 awards |
| text_cues | description, any unrecognised field | hull, class and platform vocabulary; negative vocabulary; finds PIIDs, TAS, PEs, BLIs in text |
| budget_lines | BLI, program element | graph links and SCN / SAR / MSAR exhibit tables |
| vendor | CAGE | vendor nodes and the pages that mention them |
| documents | PIID, program element | full text of every PDF: SCN Book PB27, SAR/MSAR, GAO, CRS, NPS, DoN 5200.45A, DCMA MAN 2101-02, SUPSHIP manual |
| budget_exhibit_amount | amount | budget exhibit cells (rounded $M, flagged as coincidence-prone) |
| loa_engine | an exact FPDS match | the line-of-accounting engine (`core/analyst`) |

Not loaded: Navy ERP / GL, PIEE EDA, DFAS, Advana, the internet. Matches in FPDS, File C and
sub-awards are only looked for on the two CVN-79 contracts, so a no-match is not evidence against
CVN-79. Round amounts and multiple matches are kept as candidates, not links.

## Tools

* `analyst_investigate_record`: the case investigator (logs a lead, kind `case`).
* `analyst_profile_record`: what is missing and which skills can run, without reading data.
* `analyst_list_sources`: documents by category, tables, graph coverage, skills, what is not loaded.
* `analyst_search_documents`: phrase search over every PDF page.
* `analyst_trace_entity`: one entity's links in the knowledge graph.
* `analyst_open_questions`, `analyst_investigate_transaction`, `analyst_investigate_window`,
  `analyst_explain_residual`, `analyst_backtest`, `analyst_model_status`: line of accounting on the
  two CVN-79 contracts.
* `analyst_record_outcome`: record a confirmed answer from an authoritative document (transaction,
  residual or case lead). It is a training label, never a claim.

## Rules

Every answer is grade LEAD (D16). Exact PIID only (09-C-2116 is not 16-C-2116). Never sum
`total_dollars_obligated`. Knowledge-graph edges are navigation, never a figure (D27).

## Runtime

* App: `mcp-aircarrier-analyst`, MCP endpoint `/mcp`, health `/health`.
* Resource `sql_warehouse` (CAN_USE) supplies `DATABRICKS_WAREHOUSE_ID`.
* The service principal needs SELECT on the `aircarrier_src_*`, `aircarrier_kg_*`, `aircarrier_pdf_*`,
  `aircarrier_mechanism` tables, and SELECT + MODIFY on `aircarrier_analyst_leads` and
  `aircarrier_analyst_outcomes`.
* Tests: `tests/run_checks.py` runs pytest and a live check on serverless (as a one-off job run).
