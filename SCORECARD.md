# Scorecard: every server, one row

One row per MCP server in this repository: what it is for, how it was tested, what the
tests show and what is still missing. Every figure names the file or command behind it.
Updated 2026-11-22.

| Server | Tools | Unit and contract tests | Adversarial sweep | Accuracy evidence | Probe (8 days) | Deployed | Open |
| --- | --- | --- | --- | --- | --- | --- | --- |
| [MCP A Creator](mcp-server-creator/) | 10 | 693 passed (291 plus a 402-case hostile-input sweep) | 400 hostile calls with writing on: nothing escaped, nothing written outside its root, no workspace reached ([summary](mcp-server-creator/tests/adversarial_summary.json)); injection-safety tests | 15 of 15 generated projects pass their own tests and lint; byte-identical across processes (tested with two hash seeds); every project carries a provenance lock and a drift check; bakehouse rebuilt through its tools in 0.38 s | `tools/list` 412 of 412 | Yes | No model-driven build evaluation yet; time to server measured only on the bakehouse rebuild |
| [Docs](mcp-servers/mcp-aircarrier-docs/) | 11 | 55 passed | In the read-server sweep (421 hostile calls) | Deployed store after round 10, 34 PDFs: 7,743 of 7,746, the 3 left within the rounding bound, none failing outside it ([evidence](docs/submission/evidence/tieout_store_2026-11-22.json)); before round 10: 7,703 of 7,712 | Known answer 411 of 411 to 2026-11-20 at p50 12.6 s; after the cache fix 24 of 24 at p50 1.18 s, and a 234-call run across a cache expiry: p50 1.18 s, p95 1.34 s, max 2.34 s ([latency](docs/submission/evidence/latency_2026-11-22.json)) | Yes | Probe window since the fix is 6 hours |
| [Analyst](mcp-servers/mcp-aircarrier-analyst/) | 12 | 39 passed | In the read-server sweep (421 hostile calls) | Delegation, shared with docs and ops: runs that start on analyst, 11 of 12 (Claude), too few to read as a rate ([split](docs/submission/evidence/delegation_by_server_r4.json)) | Known answer 411 of 411, p50 4.5 s | Yes | Few delegation runs start on analyst |
| [Ops](mcp-servers/mcp-aircarrier-ops/) (built by the Creator, then edited by hand) | 7 | 40 passed | In the read-server sweep (421 hostile calls) | Injection cases q16 and q17: 15 of 16 answers correct, none followed the injected instruction; the q16 record now comes back with a `source_notice`; failures reach the client as `isError`; 17-item golden set with independent SQL keys | Known answer 412 of 412, p50 0.9 s | Yes | Golden set not scored as a whole; share of files still Creator output not measured |
| [One Hub](the-one-hub/ops-center/mcp/) (`mcp-aircarrier-hub`) | 16 | 33 server tests (output schemas, schema portability, read-only, refusals, tie-out, gate with per-hull totals, HTTP behind the Apps proxy) within the One Hub's 320 | Its own sweep: 193 hostile arguments, 131 refused, 62 answered, none leaked | `hub_check_claim` routes the held $13,529M baseline to review, refuses an unsourced VERIFIED tag and a hull with no total; `hub_tie_out` refuses a $970,000 gap | Known answer 23 of 23 to 2026-11-22 04:25 UTC, p50 54 ms; round 10 gate deployed 2026-11-22 | Yes, from 2026-11-21 | A longer probe window |
| [Bakehouse](mcp-servers/mcp-bakehouse-sales/) (rebuilt by the Creator on 2026-11-21) | 7 | 21 passed | No | Second, non-CVN dataset (`samples.bakehouse`); every recorded question has a tool; review "Sound design", 4.6 of 5; provenance lock | Not a target since its app was deleted | No: its slot runs the hub since 2026-11-21 (workspace capped at 100 apps); redeploys from its folder | Golden answers to compute in the workspace; not government data, so a demonstration, not CVN-79 evidence |

**Delegation across the three read servers** (docs, analyst, ops: 30 tools offered at once),
round 4, 69 sealed questions, three repeats, question-bootstrap 95% intervals
([`eval/delegation/round4/RESULTS.md`](eval/delegation/round4/RESULTS.md)):

| Model | With tools | No tools |
| --- | --- | --- |
| Claude Sonnet 4.5 | 183/207 = 88.4% (81.2 to 94.7) | 10/69 = 14.5% |
| GPT-5 mini | 163/207 = 78.7% (70.0 to 86.5) | 1/69 = 1.4% |

Round 5, ten sealed questions from an external evaluator who is not a member of the project
development team and took no part in building the servers or preparing the model responses;
same runner and grader
([`eval/delegation/round5/RESULTS.md`](eval/delegation/round5/RESULTS.md)):

| Model | With tools | No tools |
| --- | --- | --- |
| Claude Sonnet 4.5 | 25/30 = 83.3% (66.4 to 92.7) | 1/10 |
| GPT-5 mini | 19/30 = 63.3% (45.5 to 78.1); 21/30 read by hand | 1/10 |

Exhibit questions: 30 of 30 runs right for both models. The misses are a source the servers
do not hold (DoD contract announcements), the eight-turn tool limit, and two published
grader defects.

By area for Claude: obligations 96.7% (mostly ops), document reading 93.3% (docs), printed
exhibit figures 71.8% (docs and ops; the weakest area, concentrated in older books printed
in thousands).

## The front center: agent workflows and controls

The servers above are the tools. The front center (`the-one-hub/ops-center/app/`) is where
people use them, and where agent output meets human authority.

| Part | What it does | Control | Tests |
| --- | --- | --- | --- |
| Four specialist agent workflows, started from a page | Obligation Reconciler (a contract's obligations against its FPDS actions), Account Analyst (a File C period against the transactions), Gap Investigator (the request a named office can close), Brief Composer (what the brief can stand on) | Six stages (`app/api/si/sdk.py`): a page names one task and subject, an unknown pair is refused, code packs the evidence and computes every figure in exact decimals, one model explains it, code then grounds every number against the packed facts and a second model from a different family checks the answer, and only then can a person decide | `checks/test_si.py` 24 |
| Decisions under the user's own identity | Apply or reject a proposal, or an exception in the Work queue | Authority is decided inside Unity Catalog by a statement run with the signed-in user's on-behalf-of token: `current_user()` and `is_account_group_member()` against a dated role map. No role travels in a request or a cookie. A refusal names its reason (not the owning role, checker not passed, records changed since review) | `checks/test_work.py` 78, `checks/test_harness.py` 68 |
| Work queue lanes | Every item lands in one lane by code: decide (a named role can act today), unblock (a rule that cannot run, by root cause), system (test data, superseded rows) | No business action from the system lane | in `test_work.py` |
| Run log | Every agent run and every human action, newest first | Append-only; each row names the person or the agent | in `test_si.py`, `test_work.py` |
| User input capture (Answer a question) | Anyone can record an answer to an open gap with its source and up to three files | Enters as a lead, never a figure; attributed to the signed-in user, refused when no user reaches the deployed app; typed and size-capped input, same-origin posts only | `checks/test_capture_ask.py` 32 |
| Ask the evidence | Questions in plain words; answers cite the records they rest on. With `AIRCARRIER_ASK_VIA_MCP=1` it is an MCP host: it calls the docs, ops and One Hub servers' 34 tools and shows the server behind each step | Answers are leads; same input validation as capture; the bearer token goes only to a Databricks Apps host at `/mcp`; with no server reachable it uses its in-app tools and says so | in `test_capture_ask.py`; `checks/test_mcp_host.py` 10 |
| The gate | Decides whether a figure is promoted, held as a lead or sent to review | Deterministic, no model; `hub_check_claim` exposes it | `checks/test_gate.py`, agents suite 46 of 46 |

## How each row is reproduced

| Row | Command |
| --- | --- |
| Tests, every server | `scripts/check.sh` (or `scripts/check.sh <project>`) |
| Adversarial sweep | `scripts/check.sh mcp-local` |
| Probe | [`aircarrier-mcp-probe`](mcp-servers/aircarrier-mcp-probe/); results in [EVALUATION.md](docs/submission/EVALUATION.md) section 2.2 |
| Delegation | `python3 eval/delegation/round4/analyze_round4.py`; round 5 keys and seal: `scripts/check.sh evidence` |
| Creator determinism and end to end | [EVALUATION.md](docs/submission/EVALUATION.md) section 2.5 |

## Mission user and what the server changes for them

| Server | User | What changes |
| --- | --- | --- |
| MCP A Creator | Any office with a Unity Catalog table and a question | A governed, tested MCP server without a developer; ops and bakehouse are two builds on different data |
| Docs | Budget analysts, cost estimators, GAO and congressional staff | Exhibits read to the page and tied out, instead of retyped into spreadsheets |
| Analyst | Reconciliation and audit teams | Incomplete cost records investigated and ranked as leads, with one gated, attributed write |
| Ops | Cost analysts | Exhibit cells, obligations, the variance register and the work register through paged, read-only tools |
| One Hub | Comptrollers, audit liaisons | A figure is checked against policy and the gate before it reaches a brief; unknowns become owned requests |
| Bakehouse | Demonstration | The Creator's output on a dataset unrelated to CVN-79 |
