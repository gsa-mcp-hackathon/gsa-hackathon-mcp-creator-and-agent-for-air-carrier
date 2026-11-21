# Findings and fixes

Every defect found by testing, by the [evaluation report](evaluation-report.pdf)
(section 12) and by the delegation evaluation, with what changed and what is still open.
Every claim can be re-run with [`scripts/check.sh`](../../scripts/check.sh).

## Where it stands

`scripts/check.sh` from a clean clone, on Python 3.11 and 3.12 in CI:
**1,151 passed, 6 skipped, 0 failed** (checked 2026-11-21).

| Project | Result |
| --- | --- |
| Creator | 258 passed, 1 skipped (bandit not installed) |
| Air Carrier ops | 40 passed |
| Air Carrier docs | 42 passed |
| Air Carrier analyst | 39 passed |
| Probe | 10 passed |
| Bakehouse (generated) | 21 passed (the generated weather server was removed 2026-11-21) |
| `mcp_local.py` and the adversarial sweep | 23 and 422 passed: 421 hostile calls against all 30 tools, 330 refused, none wrote, none pasted an argument into SQL |
| One Hub | 296 passed, 5 skipped (need a live Spark session); six script suites and lint pass |
| Evidence | No broken relative links; both `RESULTS.md` files match the logged runs; 36 round 4 grader and runner tests pass |

Delegation evaluation, 12 new sealed questions after the fixes: 50 of 72 with the tools
(69.4%), 1 of 24 without. Full account, including the misses that remain:
[eval/delegation/README.md](../../eval/delegation/README.md).

**Still open**

| Item | Why it matters |
| --- | --- |
| Cost model is a placeholder (`ops/harness/tools.run_cost_model_scenario`) | The cost-model specialist cannot produce an EAC range; the largest functional gap in the cost-capture story |
| No run flagged the injected instruction in q16 to the user | The models ignored it (see F11) but did not warn that the record carried one |
| No tool counts obligations by sign, and none exposes transaction-description contamination (P00154) | The two delegation questions still at 0 of 6 (G04, H04) |
| Creator maps "most negative reviews" to a count | Nothing records sentiment, so the honest answer is "not answerable without a sentiment column" |
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
