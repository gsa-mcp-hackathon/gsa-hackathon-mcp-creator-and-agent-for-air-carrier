# Evaluation addendum, 2026-11-19

This addendum records what happened to each finding in the
[evaluation report](evaluation-report.pdf) (section 12), what a fresh clone now does,
and the confidence intervals for the delegation evaluation. Every claim below can be
re-run with [`scripts/check.sh`](../../scripts/check.sh).

## Findings F1 to F12

| ID | Severity | Finding | Status | What changed, and where |
| --- | --- | --- | --- | --- |
| F1 | High | Unregistered Cost Limitation Baseline conflict ($13.529B in the FY2027 MSAR) | Fixed | Variance E-17 registered as live and key, with both readings: `app/data/variances.json`, `seed/variances.index.yaml`, `etl/build_data.py`, dossier Part E. The Position page links the baseline row to `/variances#E-17`, and E-1 says the baseline is under review. Four regression checks in `checks/test_app.py` fail on the old code. The demo video narration still states "+$473.97M over the adjusted limit" without the qualifier |
| F2 | Medium | Statute cited as 8691 and 8692 | Fixed | 10 U.S.C. 8692 everywhere: `app/main.py`, `app/api/insights.py`, `app/data/cap_history.json`, `etl/build_data.py`, dossier C.4. A check in `checks/test_app.py` fails if any screen cites 8691 for the cap |
| F3 | Medium | Corpus size quoted two ways | Fixed in the README | The README names both corpora: the docs MCP server (33 PDFs, 7,555 pages, 19,917 chunks) and the front center knowledge base (43 catalogued artifacts, 2,765 chunks from 22 indexed documents). The deck and video still quote the second without naming it |
| F4 | Medium | Stale `as_of` on the obligations tool | Fixed before this addendum (org commit 72cb4d6) | `as_of` is derived from the data |
| F5 | Medium | Work register snapshot seven days old | Mitigated | `carrier_work_register_counts` now adds a `freshness_note` with the snapshot date when the newest row is more than two days old, so a model reports the date instead of implying the counts are current (`mcp-aircarrier-ops/src/.../mcp_work_register_totals.py`, test in `tests/test_server.py`). Restarting the dispatcher tick in the workspace is still an operations task |
| F6 | Medium | Creator designed "how much ... by fiscal year" as a count | Fixed before this addendum (72cb4d6) | Semantic check in the review, with a test |
| F7 | Low | All four tool-mode delegation misses are question F4 (P-5c, PB2024) | Open, by choice | Tightening the exhibit tool description would change the tool catalog and its SHA-256, which every logged run is tied to. The fix belongs with a fresh run of all 14 questions, so the comparison stays clean |
| F8 | Low | Two readings of the 2114 obligation | Fixed | `checks/verify.py` prints the award-level total (4,584.484 $M) and the transaction sum (4,578.603 $M, 927 actions) with their basis and the 5.881 $M difference. The README quotes the transaction sum with its basis |
| F9 | Low | README linked a report that did not exist | Fixed before this addendum (72cb4d6) | The report is committed |
| F10 | Info | Tracing check not runnable in the evaluation sandbox | Fixed | `scripts/check.sh one-hub` runs `checks/test_llm_tracing.py` in the project's own uv environment; it passes there and in CI |
| F11 | Info | Golden-set injection item q16 needs a planted record | Open | Needs an agreed planted row in a scratch copy of a source table. q17, the direct injection case, passes |
| F12 | Info | Lint on hand-written projects | Mostly fixed | Docs, analyst and probe are clean under ruff 0.17.5, pinned in `scripts/check.sh`; weather is clean under its own ruff pin. CI enforces both. The changes are behaviour-preserving (regex flag names, import order, unused `noqa`), plus one silent `except: pass` in the analyst investigator that now logs a warning. The One Hub front center is not yet enforced |

## Fresh clone

Before this work, a fresh clone of org commit 72cb4d6 failed in five places:

1. `uv sync` could not resolve `mcp-aircarrier-ops` or `mcp-bakehouse-sales`: the
   Phoenix evaluation packages sat in the dev group, and arize-phoenix 20.7 and later
   needs fastmcp 4 against the server's `fastmcp<3`.
2. Four Creator tests failed: databricks-sdk was only in an optional extra.
3. The ops-center `mcp>=1.2.0` pin resolved to mcp 2.3.0, which removed
   `mcp.server.fastmcp`, so the next redeploy would break.
4. The One Hub pytest command collected 0 tests without pyspark.
5. weather-mcp had two lint errors.

What changed:

- Evaluation packages now go to `eval/requirements.txt` and run with
  `uv run --no-project --with-requirements`, outside the server environment. The
  Creator generates new projects this way too.
- mcp is pinned below 2 where the code needs the 1.x API.
- Long source descriptions are wrapped, so generated projects pass lint.

Three generator tests pin the fix. Each fails on the old code:

- `test_evaluation_dependencies_stay_out_of_the_server_environment`
- `test_generated_pyproject_resolves_with_uv`
- `test_long_source_descriptions_still_generate_a_lint_clean_project`

`scripts/check.sh` from a fresh clone, 2026-11-19:

| Project | Result |
| --- | --- |
| Creator | 247 passed, 1 skipped (bandit not installed) |
| Air Carrier ops | 36 passed |
| Bakehouse (generated) | 21 passed |
| Weather (generated) | 19 passed |
| Air Carrier docs | 27 passed |
| Air Carrier analyst | 31 passed, 8 skipped (deployed data bundle not readable outside the workspace) |
| Probe | 9 passed |
| `mcp_local.py` | 23 passed |
| One Hub | 187 passed, 5 skipped (need a live Spark session); six script suites pass |
| Evidence | No broken relative links; `eval/delegation/RESULTS.md` matches the logged runs |

Total: 600 passed, 14 skipped, 0 failed. CI (`.github/workflows/ci.yml`) runs the same
script per project on Python 3.11 and 3.12.

## Delegation evaluation with confidence intervals

The 224 logged runs are exported from Delta to
[`eval/delegation/runs.csv`](../../eval/delegation/runs.csv), and
[`analyze.py`](../../eval/delegation/analyze.py) re-derives every number with 95%
Wilson score intervals (checked against statsmodels).

| Slice | With the 29 tools | Without tools |
| --- | --- | --- |
| All 14 questions | 80/84, 95.2% (88.4 to 98.1) | 2/28, 7.1% (2.0 to 22.6) |
| Held out (5 questions) | 26/30, 86.7% (70.3 to 94.7) | 2/10, 20.0% (5.7 to 51.0) |
| Strict held out (4 questions, F1 excluded) | 20/24, 83.3% (64.1 to 93.3) | 2/8, 25.0% (7.1 to 59.1) |
| Development (9 questions) | 54/54, 100% (93.4 to 100) | 0/18, 0% (0 to 17.6) |
| Server instructions in the prompt | 28/28, 100% (87.9 to 100) | |

Question F1 is excluded from the strict held-out row because its earlier failures drove
a fix to the tools (0/4 before, 4/4 after). All four remaining misses are question F4
(P-5c, PB2024), finding F7 above. The intervals are wide because the question set is
small; a larger set is the next step for this evaluation.
