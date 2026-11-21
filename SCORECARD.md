# Scorecard: every server, one row

One row per MCP server in this repository: what it is for, how it was tested, what the
tests show and what is still missing. Every figure names the file or command behind it.
Updated 2026-11-21.

| Server | Tools | Unit and contract tests | Adversarial sweep | Accuracy evidence | Probe (8 days) | Deployed | Open |
| --- | --- | --- | --- | --- | --- | --- | --- |
| [MCP A Creator](mcp-server-creator/) | 10 | 263 passed, 1 skipped | Fuzzed generated code; injection-safety tests | 15 of 15 generated projects pass their own tests and lint; 58 of 58 files byte-identical from the same specification | `tools/list` 412 of 412 | Yes | No measured time from question to deployed server |
| [Docs](mcp-servers/mcp-aircarrier-docs/) | 11 | 47 passed | In the 421-call sweep | 814 of 818 tie-out checks passed on 34 PDFs (7,804 pages); the 4 were "Total ..." cost elements read as totals, fixed 2026-11-21 (PB2027 locally: 790 of 790) | Known answer 411 of 411, p50 12.6 s | Yes | Redeploy, then re-measure both: the slow latency mode was the corpus reload inside the request, now refreshed in the background |
| [Analyst](mcp-servers/mcp-aircarrier-analyst/) | 12 | 39 passed | In the 421-call sweep | Delegation, shared with docs and ops (below) | Known answer 411 of 411, p50 4.5 s | Yes | No per-server delegation split |
| [Ops](mcp-servers/mcp-aircarrier-ops/) (built by the Creator) | 7 | 40 passed | In the 421-call sweep | Injection cases q16 and q17: 15 of 16 answers correct, none followed the injected instruction; the q16 record now comes back with a `source_notice` (every server, 23 tests); 17-item golden set with independent SQL keys | Known answer 412 of 412, p50 0.9 s | Yes | Golden set not scored as a whole |
| [One Hub](the-one-hub/ops-center/mcp/) (`mcp-aircarrier-hub`) | 16 | 25 server tests (schema portability, read-only, refusals, tie-out, gate, HTTP behind the Apps proxy) within the One Hub's 302 | Its own sweep: 193 hostile arguments, 131 refused, 62 answered, none leaked | `hub_check_claim` routes the held $13,529M baseline to human review; `hub_tie_out` refuses a $970,000 gap | Target added 2026-11-21 (known answer: the held baseline) | Ready (HTTP fixed; one create command) | Create the app, grant the probe `CAN_USE` |
| [Bakehouse](mcp-servers/mcp-bakehouse-sales/) (built by the Creator) | 4 | 21 passed | No | Shows the Creator on a second, non-CVN dataset (`samples.bakehouse`); answer key still has the generated TODOs | Target added 2026-11-21 (needs the probe's `CAN_USE` grant) | Yes | Fill the answer key; not government data, so it is a demonstration, not part of the CVN-79 evidence |

**Delegation across the three read servers** (docs, analyst, ops: 30 tools offered at once),
round 4, 69 sealed questions, three repeats, question-bootstrap 95% intervals
([`eval/delegation/round4/RESULTS.md`](eval/delegation/round4/RESULTS.md)):

| Model | With tools | No tools |
| --- | --- | --- |
| Claude Sonnet 4.5 | 183/207 = 88.4% (81.2 to 94.7) | 10/69 = 14.5% |
| GPT-5 mini | 163/207 = 78.7% (70.0 to 86.5) | 1/69 = 1.4% |

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
| Ask the evidence | Questions in plain words; answers cite the records they rest on | Answers are leads; same input validation as capture | in `test_capture_ask.py` |
| The gate | Decides whether a figure is promoted, held as a lead or sent to review | Deterministic, no model; `hub_check_claim` exposes it | `checks/test_gate.py`, agents suite 46 of 46 |

## How each row is reproduced

| Row | Command |
| --- | --- |
| Tests, every server | `scripts/check.sh` (or `scripts/check.sh <project>`) |
| Adversarial sweep | `scripts/check.sh mcp-local` |
| Probe | [`aircarrier-mcp-probe`](mcp-servers/aircarrier-mcp-probe/); results in [EVALUATION.md](docs/submission/EVALUATION.md) section 2.2 |
| Delegation | `python3 eval/delegation/round4/analyze_round4.py` |
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
