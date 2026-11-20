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
| F7 | Low | All four tool-mode delegation misses are question F4 (P-5c, PB2024) | First fix failed in round 2 (F4 0 of 6); fixed again 2026-11-20, re-run pending | J-book filenames say PB24; questions say "the PB 2024 book", and keyword search cannot join them. `docs_list_documents` and `docs_find_line_item` now carry a normalized `budget_cycle`, and `docs_find_line_item` filters on it and says when the named book is not loaded (`mcp-aircarrier-docs/src/.../service.py`, tests in `tests/test_docs.py`). The tool catalog changes, so the fix counts only after the round 2 run in [eval/delegation/round2/](../../eval/delegation/round2/README.md), which re-runs all 14 questions plus 12 sealed new ones. **Round 2 result:** F4 went 0 of 6. The cycle reader required a separator before `PB`; the real names (`SCN_BookPB2024.pdf`, `SCN_Bookpb2006.pdf`) have none, so 21 of 22 books got no cycle, and the tests had used invented names with a space. The reader now matches the real names, falls back to the most frequent `PB 20xx` page header, and the tests use the real names |
| F8 | Low | Two readings of the 2114 obligation | Fixed | `checks/verify.py` prints the award-level total (4,584.484 $M) and the transaction sum (4,578.603 $M, 927 actions) with their basis and the 5.881 $M difference. The README quotes the transaction sum with its basis |
| F9 | Low | README linked a report that did not exist | Fixed before this addendum (72cb4d6) | The report is committed |
| F10 | Info | Tracing check not runnable in the evaluation sandbox | Fixed | `scripts/check.sh one-hub` runs `checks/test_llm_tracing.py` in the project's own uv environment; it passes there and in CI |
| F11 | Info | Golden-set injection item q16 needs a planted record | Built, not yet run (2026-11-20) | `mcp-aircarrier-ops/eval/q16_planted_record.sql` copies the four ops tables into a scratch schema and plants gap G99 with an instruction in its `last_error`; `answer_key.py q16` reads the copy, and the dataset carries the real question. The source tables are never written. q17, the direct injection case, passes |
| F12 | Info | Lint on hand-written projects | Fixed (2026-11-20) | Docs, analyst and probe are clean under ruff 0.17.5, pinned in `scripts/check.sh`; weather is clean under its own pin. The One Hub went from 285 findings to 0 and is now enforced in `scripts/check.sh one-hub` and CI. Deliberate broad catches carry their reason on the line; jobs, ETL, tools and checks keep BLE001 off by a per-file rule explained in `pyproject.toml` |

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

Total: 600 passed, 14 skipped, 0 failed.

**Update, 2026-11-20.** After the round of fixes on branch `enhance/mission-and-eval`:
Creator 258 passed, 1 skipped; ops 36; bakehouse 21; weather 20; docs 36; analyst 31 passed,
8 skipped; probe 9; `mcp_local.py` 23 plus the adversarial sweep 400; One Hub 187 passed,
5 skipped, six script suites and lint. Total: 1,021 passed, 14 skipped, 0 failed. The new
tests cover free text in source descriptions (the Creator's `docstring_safe` doubled pairs
of backslashes instead of each one and kept newlines), the deploy approval token, the
budget-cycle filter, and hostile arguments against all 29 tools. CI (`.github/workflows/ci.yml`) runs the same
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

## Round 2: the sealed held-out set (2026-11-20)

Twelve questions, sealed by SHA-256 before the run, on the 29-tool catalog
`1143a3c17536b7bd` (runs `rpt-cde6da6d` and `166621165979`):

| Slice | With the 29 tools | Without tools |
| --- | --- | --- |
| Sealed held out (12 questions) | 31/72, 43.1% (32.3 to 54.6) | 3/24, 12.5% (4.3 to 31.0) |
| F4 after the first F7 fix | 0/6, 0% (0 to 39.0) | 0/2 |
| Every question in the run | 109/156, 69.9% (62.3 to 76.5) | 4/52, 7.7% (3.0 to 18.2) |

Round 1's 83.3% rested on four questions; on twelve new ones the rate is about half.
The gap to no tools stays wide. Every miss was read and assigned a cause in
[eval/delegation/round2/README.md](../../eval/delegation/round2/README.md): 28 of 41
needed a tool or option that did not exist (obligations on the DD&C contract, a sort by
amount, a search of the variance register), 7 were P-5c column reads, 5 were a decoy
pattern that rejected "cannot find", and 1 was an incomplete answer. The fixes are on
branch `fix/round2-findings`: the ops server gains `carrier_search_variances` (30
tools) and a required `contract` and an `order` on `carrier_search_obligations`, and
`docs_get_table` labels P-5c cells with ship fiscal year, hull and share. The official
score is not regraded. A run of the same 12 questions on the fixed tools is a post-fix
re-run, reported apart; a new sealed set,
[round 3](../../eval/delegation/round3/README.md), tests the fixes on questions no model
has seen.

After these fixes `scripts/check.sh` passes from a clean clone with 1,052 tests (ops 40,
docs 41, the adversarial sweep 422) and 14 skipped.

## Round 3: new sealed questions after the fixes (2026-11-20)

Twelve questions written after the round 2 fixes, sealed by SHA-256 before the run, on
the 30-tool catalog `7e0d0a2a69214945` (run `rpt-5153ac3f`):

| Slice | With the 30 tools | Without tools |
| --- | --- | --- |
| Round 3 sealed held out (12 questions) | 50/72, 69.4% (58.0 to 78.9) | 1/24, 4.2% (0.7 to 20.2) |
| Round 2 questions, re-run after the fixes | 45/72, 62.5% (51.0 to 72.8) | 3/24, 12.5% |
| F4 after the second F7 fix | 4/6, 66.7% (30.0 to 90.3) | 0/2 |
| Every question in the run | 174/228, 76.3% (70.4 to 81.4) | 6/76, 7.9% (3.7 to 16.2) |

Three grading defects are kept in the official score and reported apart in
[`hand_grades.csv`](../../eval/delegation/hand_grades.csv): an answer-key error in G07
(the key rounded 13,195.970 to 13,196), a pattern in H06 that cannot match 63.11%, and
the H10 pattern that does not accept "cannot find". Read by hand, round 3 and the round 2
re-run are each 55/72 (76.4%). The real misses left are counting deobligations by sign
(G04), the P00154 contamination that no tool exposes (H04), and figures that live only
in the variance register (G09, part of G08). Both sealed sets were written by the person
who built the tools; an independent author would make a stronger test.

