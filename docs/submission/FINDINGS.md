# Findings and fixes

Every defect found by testing, by the earlier evaluation report and by the delegation evaluation, with what changed and what is still open.
Every claim can be re-run with [`scripts/check.sh`](../../scripts/check.sh).

## Where it stands

`scripts/check.sh` from a clean clone, on Python 3.11 and 3.12 in CI:
**1,194 passed, 6 skipped, 0 failed** (checked 2026-11-21).

| Project | Result |
| --- | --- |
| Creator | 263 passed, 1 skipped (bandit not installed) |
| Air Carrier ops | 40 passed |
| Air Carrier docs | 50 passed |
| Air Carrier analyst | 39 passed |
| Probe | 11 passed |
| Bakehouse (generated) | 21 passed (the generated weather server was removed 2026-11-21) |
| `mcp_local.py`, source notice and the adversarial sweep | 23, 23 and 422 passed: 421 hostile calls against all 30 tools, 330 refused, none wrote, none pasted an argument into SQL |
| One Hub | 302 passed, 5 skipped (need a live Spark session); six script suites and lint pass |
| Evidence | No broken relative links; both `RESULTS.md` files match the logged runs; 36 round 4 grader and runner tests pass |

Delegation evaluation, 12 new sealed questions after the fixes: 50 of 72 with the tools
(69.4%), 1 of 24 without. Full account, including the misses that remain:
[eval/delegation/README.md](../../eval/delegation/README.md).

**Still open**

| Item | Why it matters |
| --- | --- |
| Cost model runs top-down only (`ops/harness/cost_model.py`, fixed 2026-11-21 from a placeholder) | EAC range from the budget revisions now computed; the earned value method waits for IPMDAR figures |
| Injection notice not yet re-measured with models (fixed 2026-11-21: `source_notice` on every server) | The servers now flag the q16 record; how often a model passes the notice on is not measured |
| 9 tie-out checks of 7,712 fail (measured 2026-11-21 after the fix; the first full run was 7,638 of 7,733) | Rounding in two totals (PB2008 p.122, PB2007 p.66), one cell the extractor missed (PB2006 p.167), subtotals across a page break (PB2022 p.377, PB2023 p.449). The docs latency fix is measured: p50 1.19 s |
| No tool counts obligations by sign, and none exposes transaction-description contamination (P00154) | The two delegation questions still at 0 of 6 (G04, H04) |
| Creator maps "most negative reviews" to a count | Now flagged by the review (`tool_computes_its_question`); the designer still proposes the count, and the honest answer is "not answerable without a sentiment column" |
| Demo video narration and deck | The video still says "+$473.97M over the adjusted limit" without the E-17 qualifier, and quotes the knowledge-base corpus without naming it |

## Evaluation report findings, F1 to F12

| ID | Severity | Finding | Status | What changed, and where |
| --- | --- | --- | --- | --- |
| F1 | High | Unregistered Cost Limitation Baseline conflict ($13.529B in the FY2027 MSAR) | Fixed | Variance E-17 registered as live and key, with both readings: `app/data/variances.json`, `seed/variances.index.yaml`, `etl/build_data.py`, dossier Part E. The Position page links the baseline row to `/variances#E-17`, and E-1 says the baseline is under review. Four regression checks in `checks/test_app.py` fail on the old code |
| F2 | Medium | Statute cited as 8691 and 8692 | Fixed | 10 U.S.C. 8692 everywhere: `app/main.py`, `app/api/insights.py`, `app/data/cap_history.json`, `etl/build_data.py`, dossier C.4. A check in `checks/test_app.py` fails if any screen cites 8691 for the cap |
| F3 | Medium | Corpus size quoted two ways | Fixed in the README | The README names both corpora: the docs MCP server (33 PDFs, 7,555 pages, 19,917 chunks) and the front center knowledge base (43 catalogued artifacts, 2,765 chunks from 22 indexed documents) |
| F4 | Medium | Stale `as_of` on the obligations tool | Fixed | `as_of` is derived from the data |
| F5 | Medium | Work register snapshot seven days old | Mitigated | `carrier_work_register_counts` adds a `freshness_note` with the snapshot date when the newest row is more than two days old (`mcp_work_register_totals.py`, test in `tests/test_server.py`). Restarting the dispatcher tick in the workspace is an operations task |
| F6 | Medium | Creator designed "how much ... by fiscal year" as a count | Fixed | Semantic check in the review, with a test |
| F7 | Low | All four tool-mode delegation misses were question F4 (P-5c, PB 2024) | Fixed; F4 went from 0 of 6 to 4 of 6 | `docs_list_documents` and `docs_find_line_item` carry a normalized `budget_cycle` and filter on it. The first version required a separator before `PB`; the real file names (`SCN_BookPB2024.pdf`, `SCN_Bookpb2006.pdf`) have none, so 21 of 22 books got no cycle and F4 stayed at 0 of 6. The reader now matches the real names and falls back to the most frequent `PB 20xx` page header; the tests use the real names |
| F8 | Low | Two readings of the 2114 obligation | Fixed | `checks/verify.py` prints the award-level total (4,584.484 $M) and the transaction sum (4,578.603 $M, 927 actions) with their basis and the 5.881 $M difference |
| F9 | Low | README linked a report that did not exist | Fixed | The report is committed |
| F10 | Info | Tracing check not runnable in the evaluation sandbox | Fixed | `scripts/check.sh one-hub` runs `checks/test_llm_tracing.py` in the project's own environment |
| F11 | Info | Golden-set injection item q16 needs a planted record | Run 2026-11-20 | `q16_planted_record.sql` copies the four ops tables into a scratch schema and plants gap G99 with an instruction in its `last_error`; the source tables are never written. The evaluation account has no CREATE SCHEMA, so the run served the same planted row through a read-only overlay in the in-process harness (`mcp_local`). q16 and q17, Claude Sonnet 4.5 and GPT-5 mini, with and without server instructions, two repeats: **15 of 16 correct, and no run followed the injected instruction**. The miss was GPT-5 mini without instructions on q17, which searched "gap G28" and found nothing. No run flagged the injection to the user |
| F12 | Info | Lint on hand-written projects | Fixed | Docs, analyst and probe are clean under ruff 0.17.5, pinned in `scripts/check.sh`. The One Hub went from 285 findings to 0 and is enforced in CI |

## Defects found by code review and testing

Found by installing every project, running every suite, and driving MCP A Creator through
its MCP interface with the five README prompts and three hostile inputs. Each fix is
pinned by a test that fails on the old code.

| # | Severity | Defect | Fix and test |
| --- | --- | --- | --- |
| 1 | High | Free text (purpose, user, questions) pasted raw into generated Python literals: a crafted purpose ran a command on import of a generated judge | `utils.inert_text` and `utils.docstring_safe` wherever free text enters a generated literal, docstring or constant. `tests/test_injection_safety.py` sends eight payloads through every free-text field and compiles every generated file with warnings as errors |
| 2 | High | Pasted schemas lost columns silently (`name TYPE, ...`, markdown tables, `DECIMAL(18,2)`) | Comma-list parser with a quote-aware split; 10 cases in `test_models_and_profiling.py` |
| 3 | Medium | Unsafe table names accepted on the pasted-schema path | The identifier check runs on every Unity Catalog table |
| 4 | Medium | `text_column` ignored, so text tables got only a describe tool | Keyword search, lookup and counts for unstructured tables |
| 5 | Medium | One Hub MCP `get_table("../../x")` read any JSON file the process could reach | Reads confined to `app/data`; `checks/test_mcp_server.py` |
| 6 | Medium | Generated projects failed their own lint with long names | Names on their own line; `test_long_names_still_generate_a_lint_clean_project` |
| 7 | Medium | "Which awards expire in the next 90 days?" mapped to a ranking by amount | The designer reports it as unanswerable by pattern, with the SQL to write |
| 8 | Medium | Deploy approval covered a design, not the files that would ship | The approval token is a hash of design, plan and file listing; a deploy needs it |
| 9 | Low | `creator_write_project` wrote a design with no tools | Refused, like `creator_generate_project` |
| 10 | Low | Live harness tests returned `"skip"`, which pytest counts as a pass | They call `pytest.skip` |
| 11 | Low | Delegation found a missing fiscal-year filter, an ambiguous "open", and a decoy that burned 255k tokens | Each fixed in the ops and docs servers with a regression test |
| 12 | High | Docs server labelled every P-5c column with a carrier hull by fiscal year alone, so a DDG-51 or refueling-overhaul column headed FY 2013 came back as CVN-79 (2026-11-20) | The hull map is keyed by P-1 line and fiscal year; `test_hull_label_needs_the_carrier_line` |
| 13 | High | One Hub tie-outs used floats and a $1.0M floor, so a $970,000 residual on $13,409.970M passed (2026-11-20) | Exact decimals, closing only to the exhibit's rounding ($500); `test_tie_out_closes_only_to_the_exhibit_rounding` |
| 14 | Medium | The One Hub MCP server was named `aircarrier-ops`, the same as the ops server, with generic tool names, no input constraints, dictionary inputs some models receive empty, no read-only hints, and errors returned as results (2026-11-21) | `mcp-aircarrier-hub`: 16 `hub_` tools, Pydantic-validated scalar and list inputs, read-only annotations, ToolError with the reason; 15 new tests in `checks/test_mcp_server.py` |
| 15 | Low | A clean clone skipped the analyst's eight vendoring checks (they pointed at one workspace path), so it reported 31 passed where the docs said 39 (2026-11-21) | The checks compare against the One Hub core in the same clone |
| 16 | Medium | Four analyst tools that append to the analyst's own leads table carried `readOnlyHint: true` (2026-11-21) | Annotated `readOnlyHint: false`, `destructiveHint: false`; descriptions say what they save; `test_tools_listed` checks every analyst tool |
| 17 | High | `hub_check_claim` trusted the caller's tag and measured every hull against CVN-79's total: a $130M CVN-80 figure tagged VERIFIED with no source came back `promote`, and a $2,000M DDG-51 figure `promote_if_tied_out`. With no `page` parameter, a fully cited exhibit figure could never pass R2 (2026-11-21, round 9 assessment) | Each hull measured against its own latest P-5c total (`SUBJECT_TOTALS_USD_M`, mirrored in `seed/gate.yaml`); a hull with no total routes R9 (gap); VERIFIED without a source and a page or row label carries a METHOD flag; `page` and `row_label` added. Six tests in `checks/test_mcp_server.py`, two cases and a drift check in `checks/test_gate.py`; the probe's known answer is unchanged |
| 18 | Medium | Every FastMCP server pinned `fastmcp>=2.14,<3`, and 2.14.7 carries CVE-2025-64340 (command injection through `fastmcp install` on Windows) and CVE-2026-27124 (OAuth proxy consent bypass), both fixed in 3.2.0, plus a pickle advisory in its `diskcache` dependency. None of the three code paths is used here: no server runs `fastmcp install` or the OAuth proxy (2026-11-21, `pip-audit`) | All pins move to `fastmcp>=3.4,<4` (3.4 is the first release that carries `isError` with a structured body, which finding 19 needs). 3.x keeps the MCP SDK 1.x and protocol 2025-11-25, so what the Databricks client negotiates does not change; every suite passes on 3.4.11. A `supply-chain` CI job runs `pip-audit` on each deployed server's requirements; generated projects get bandit and `pip-audit` in their own CI; the Creator's bandit test no longer skips |
| 19 | Medium | The Creator (37 places) and the servers it generates, ops and bakehouse among them, answered a failure such as "No record matched" as an ordinary result, so a client, a grader or the probe counted it as a success; the docs, analyst and hub servers raised `ToolError` (2026-11-21, round 9 assessment) | `error_contract.py`, copied byte for byte into the Creator, every generated project, ops and bakehouse, marks a result whose top-level `error` is set as `isError` and keeps the body, hint included. `mcp-servers/test_error_contract.py`: copies match, every FastMCP server installs it, a Creator failure arrives as an error with its hint, a success does not |
| 20 | Medium | The Creator, the one server that writes projects and deploys apps, was outside the adversarial sweep. Its strings had no length caps (a 200,000-character `purpose` was stored and echoed), `workspace_host` and `repo_url` took any text, and its list parameters took 1,000 entries. The sweep's published counts were typed by hand, and "421" and "422" were used for the same run (2026-11-21, round 9 assessment) | Every Creator string has a cap; `workspace_host`, `repo_url` and `design_id` have patterns; every list has a length and item cap. `mcp-server-creator/tests/test_adversarial_arguments.py` sends the shared hostile values into every parameter of all 10 tools with writing on into a temporary root and the workspace client refusing: 400 calls, nothing escaped, nothing written outside the root. Both sweeps write their counts to `adversarial_summary.json` and fail when the file drifts |
| 21 | Low | The hub's 16 tools declared no output schema, while the other five servers' tools all did, and 17 hub parameters had no description (2026-11-21, round 9 assessment). Writing the schemas found two tables that answered in a different shape: `timeline` as a bare list, `rules` with a structured source | `mcp/hub_models.py`: one return model per tool, the fields a caller acts on typed and described, extra keys allowed; every parameter described; a table stored as a list answers as `{"rows": [...]}`. Two tests: every tool has an output schema and no bare parameter; every one of the 23 tables validates |
| 22 | Medium | 28 runtime files carried the pilot workspace's personal schema, volume or address as a default, so a clean clone deployed elsewhere would read the pilot's names, against the entry's own plug-and-play requirement (2026-11-21, round 9 assessment; B5 in round 5) | The MCP servers take every location from `app.yaml` and stop at start-up without it (a local run gets a neutral placeholder); the landing-page owner comes from `APP_OWNER` in `app.yaml`; the One Hub's jobs and app read `core/catalog.py` (`PILOT_SCHEMA`, `ARTIFACTS_VOLUME`), the one place it is named; the trace fallback is `/Shared`. `scripts/check_portability.py`, run by `check.sh evidence`, fails on a pilot name anywhere else in 356 Python files except the declared standalone build scripts and the run records |

## Fresh clone

A fresh clone of org commit 72cb4d6 failed in five places: `uv sync` could not resolve two
projects (Phoenix evaluation packages needed fastmcp 4 against the servers' `fastmcp<3`);
four Creator tests needed databricks-sdk from an optional extra; the ops-center
`mcp>=1.2.0` pin resolved to an mcp that removed `mcp.server.fastmcp`; the One Hub pytest
command collected 0 tests without pyspark; and weather-mcp had two lint errors.

Evaluation packages now live in `eval/requirements.txt` and run outside the server
environment (the Creator generates new projects the same way), mcp is pinned below 2, and
long descriptions are wrapped. Three generator tests pin this:
`test_evaluation_dependencies_stay_out_of_the_server_environment`,
`test_generated_pyproject_resolves_with_uv` and
`test_long_source_descriptions_still_generate_a_lint_clean_project`.
