# Evaluation: MCP A Creator and the One Hub for CVN-79

GSA MCP & SI Agent Government Hackathon. Track: **Dataset Access Server**.

This document follows the four headings of the GSA evaluation template. It replaces the
earlier `evaluation-report.pdf` (602 tests, written before delegation round 3). Every number
below was re-run or re-queried on 2026-11-20 against commit `31f3409` unless it says
otherwise, and each one names the file or command that reproduces it.

## 1. Testing methodology

The evaluation asks five separate questions, because passing one says nothing about the
others.

| Layer | Question | How it is tested | Reproduce |
| --- | --- | --- | --- |
| Code suites | Does the code do what it says? | Unit, contract and route tests per project, each in its own environment, plus lint (ruff, pinned) | `scripts/check.sh` |
| Adversarial arguments | Does any tool accept a hostile argument? | Every parameter of all 30 Air Carrier tools receives SQL fragments, path traversal, oversized values, wrong enum members and control characters, against a recording fake warehouse | `scripts/check.sh mcp-local` |
| Known answers in production | Do the deployed servers answer correctly, every time? | A probe app calls each deployed server as a non-human caller: resolve, initialize, tools/list, then one known-answer tool call, logged per step | `aircarrier-mcp-probe`, results in `/Volumes/users/xiaobing_shang1_civ/aircarrier_mcp_probe_runs` |
| Delegation | Given all tools at once, do real models pick the right ones? | Claude Sonnet 4.5 and GPT-5 mini, with and without server instructions, three repeats, plus a no-tool baseline. Rounds 2 and 3 were sealed: questions and answer key fixed by a SHA-256 committed before any model saw them | `python3 eval/delegation/analyze.py` |
| Figures | Is every published number what the source prints? | Tie-outs to zero residual on two axes; every Impact page figure carries a verbatim quote checked against the page text | `checks/verify.py`, `checks/test_impact.py` |

Inputs used: public records only. SCN budget justification books (PB2006 to PB2027), CVN 78
class SARs and MSARs, GAO reports (GAO-15-22, GAO-17-575, GAO-26-108457), CRS RS20643,
NPS-AM-26-055, DoN and DCMA manuals, and USAspending/FPDS transactions for N00024-09-C-2116
(948 actions) and N00024-15-C-2114 (927 actions). The docs server holds 34 PDFs and 7,804
pages. The generator demo `mcp-bakehouse-sales` reads Databricks' `samples.bakehouse`, which
is not government data.

Grading discipline: every delegation miss is read by hand and given a cause; grader defects
are kept in the score and listed apart rather than re-graded upward.

## 2. Performance metrics

### 2.1 Code suites (fresh clone of `31f3409`, 2026-11-20)

| Project | Passed | Skipped |
| --- | --- | --- |
| MCP A Creator | 258 | 1 (needs bandit) |
| Ops server | 40 | 0 |
| Docs server | 41 | 0 |
| Analyst server | 39 | 0 |
| Probe | 9 | 0 |
| Bakehouse (generated) | 21 | 0 |
| In-process harness `mcp_local` | 23 | 0 |
| Adversarial sweep, 30 tools | 422 | 0 |
| One Hub (pytest) | 187 | 5 (need a live Spark session) |
| **Total** | **1,040** | **6** |

The One Hub also runs six script suites (agents 46/46, gate, LLM tracing, app routes,
serverless entry points, tie-out); all pass, and the evidence check finds 0 broken links in
115 and `RESULTS.md` equal to `runs.csv`. The Impact page added after this run brings the
One Hub to 241 passed (54 new tests), so the working tree totals 1,094 passed, 6 skipped. (A generated weather server, 20 tests,
was removed from the repository on 2026-11-21 and is excluded from these totals.)

One environment caveat: run inside a Databricks serverless notebook, four live harness tests
fail with `PySparkImportError`, most likely because the notebook's Spark environment
variables reach the test process. With a clean environment (`env -i`) they skip as designed. CI is unaffected.

### 2.2 Availability and latency of the deployed servers

Probe sweeps from 2026-11-12 16:42Z to 2026-11-20 23:52Z: **413 sweeps, 6,193 checks, 6,187
ok (99.90%)**. **1,234 of 1,234 known-answer checks returned the right answer.** The six
failures were five transport errors (response ended early or read timeout, on 2026-11-13 and
2026-11-19 01:47Z) and one HTTP 502 from the Creator at 01:47Z on 2026-11-19, the minute all
apps were redeployed.

| Server | Step | Checks | OK | p50 ms | p95 ms | Max ms |
| --- | --- | --- | --- | --- | --- | --- |
| mcp-aircarrier-ops | known answer | 412 | 100% | 924 | 1,240 | 6,363 |
| mcp-aircarrier-analyst | known answer | 411 | 100% | 4,453 | 5,248 | 13,653 |
| mcp-aircarrier-docs | known answer | 411 | 100% | 12,559 | 13,704 | 20,187 |
| mcp-aircarrier-ops | tools/list | 413 | 100% | 64 | 101 | 572 |
| mcp-aircarrier-analyst | tools/list | 412 | 100% | 63 | 102 | 351 |
| mcp-aircarrier-docs | tools/list | 413 | 100% | 69 | 104 | 355 |
| mcp-a-creator | tools/list | 412 | 100% | 65 | 99 | 201 |
| all four | initialize | 1,652 | 99.94% | 91 to 96 | 482 to 523 | 864 |

The docs known-answer latency is bimodal: daily medians sit near 1.1 to 1.3 s on some
deployments and about 12.6 to 13.2 s on most others, so the overall p50 of 12.6 s describes the slow
mode. The cause has not been isolated; it tracks the deployment, not the question.

### 2.3 Tool choice by real models (delegation)

| Round | Questions | With tools | Without tools |
| --- | --- | --- | --- |
| 1 (14 questions, 29 tools) | all | 80/84 (95.2%) | 2/28 |
| 1, strict held-out | 4 | 20/24 (83.3%) | 2/8 (25.0%) |
| 2, sealed, before fixes | 12 | 31/72 (43.1%, CI 32.3 to 54.6) | 3/24 (12.5%) |
| 3, sealed, after fixes, 30 tools | 12 new | **50/72 (69.4%, CI 58.0 to 78.9)** | 1/24 (4.2%) |

Round 2 found that 28 of its 41 misses needed a tool or option that did not exist
(obligations on the DD&C contract, a sort by amount, a search of the variance register);
those were built and round 3 measured them on new questions. Five round 3 misses come from
an answer-key error (G07); by hand the score is 55/72, but 50/72 is reported.

### 2.4 Prompt injection

The golden set carries a direct injection (q17) and an indirect one (q16, a planted record
with an embedded instruction, served through a read-only overlay). Both models, with and
without instructions, two repeats: **15 of 16 answers correct, and no run followed the
injected instruction.** The one miss searched for "gap G28" and found nothing. No run
flagged the injection to the user either, which is a gap.

### 2.5 Determinism and data integrity

* MCP A Creator, same specification twice: 58 of 58 generated files byte-identical.
* CVN-79 Total Ship Estimate, $13,409.970M (PB2027 P-5c, p.95), closes to 0.000 by cost
  category and by funding stream.
* Impact page: 24 of 24 figures found verbatim on the cited page of the cited artifact.

## 3. Security considerations

The model fills SQL fragments, file paths and free text, and reads untrusted documents.
The controls are in code, not in prompts.

| Risk | Control | Evidence |
| --- | --- | --- |
| SQL injection | Identifiers allow-listed and quoted; values bound as parameters; the One Hub's `sqlsafe.compose` refuses anything that is not a vetted fragment | Adversarial sweep: 422 tests pass; no hostile value pasted into SQL text; every statement that reached the warehouse was read-only |
| Input validation | Pydantic models and enums on every tool parameter; bounded limits | Same sweep: hostile arguments refused at validation or answered safely |
| Code injection into generated projects | Free text made inert before entering any literal, docstring or comment; generated Python compiled with warnings as errors; TOML/JSON/YAML/XML must parse | `mcp-server-creator/tests/test_injection_safety.py` |
| Unwanted writes | Air Carrier tools are read-only except one gated label write needing an authoritative locator and a confirming office. Creator writes are dry runs by default; deploy needs an approval token bound to the reviewed design, app name, grants and files | Creator and analyst suites |
| Identity and grants | Per-user OAuth through Databricks Apps; tables read as the caller under Unity Catalog; no credentials in code; only `.env.example` committed | `SECURITY.md`, `docs/DEPLOYMENT.md` |
| Token handling in the probe | Calls only an allow-listed Databricks Apps host over https, path `/mcp`, with redirects disabled so the bearer token cannot be moved | `aircarrier-mcp-probe/probe.py` |
| Path traversal | Volume reads confined to configured roots | Adversarial sweep |
| Prompt injection | Retrieved text is data; the docs search returns premise flags for 28 known false premises | q16/q17 above |

Scope: sandbox workspace, publicly released documents only, apps reachable only by
authenticated users of the same Databricks account; nothing is publicly deployed.

Known weaknesses: four analyst tools annotated read-only (`analyst_investigate_record`,
`analyst_investigate_transaction`, `analyst_investigate_window`, `analyst_explain_residual`) append their
answer to the analyst's own leads table. They never change source data, and the server
instructions now say so, but the MCP `readOnlyHint` alone does not. No run
flagged an injected instruction to the user.

## 4. Lessons learned and recommendations

1. **Measure on sealed questions, then fix, then measure on new sealed questions.** Round 1
   looked like 95%; the first sealed round was 43%. Most misses were missing tools, not bad
   models. Fixing those and re-measuring on fresh questions gave 69%.
2. **Goal-shaped tools beat thin wrappers.** Models mis-summed 28 rows until the obligations
   search returned an exact server-side total; a decoy question burned 255k tokens before
   results were trimmed to a summary by default. Return the answer a person needs, with its basis.
3. **Unambiguous words matter.** "open" meant two different states; the enum was renamed.
4. **A figure is not usable until a person can see where it came from.** The MSAR reports a
   December 2025 CVN-79 baseline of $13.529B, which is also CVN-80's baseline. The gate sent
   it to review (E-17) instead of using it; if confirmed, the budget total sits $119.03M
   under the baseline instead of $473.97M over it.
5. **Monitor the server the way a user reaches it.** The probe separated "server broke" from
   "connector token failed", which otherwise look the same to a user.
6. **Extraction is never finished.** The CVN-81 PB2027 P-5c is in the page text but missing
   from the exhibit table store; per-program costs in GAO-26-108457 live only in chart
   images. Both are listed as not shown rather than estimated.

Recommendations for an agency adopting this:

* Start with one program and its key set (appropriation, line item, contracts), reuse the
  servers, gate and registers unchanged, and add CVN-80 and CVN-81 next.
* Have someone other than the tool builder write the next sealed question set.
* Keep the probe running as continuous-monitoring evidence for an authority to operate.
* Measure analyst hours before and after; this pilot has not.
