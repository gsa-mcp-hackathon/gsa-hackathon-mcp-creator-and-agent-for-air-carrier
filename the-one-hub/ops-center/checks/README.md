# checks/

The deterministic tie-out suite. No model, ever. If a check needs judgment it
emits a flag and stops.

These five moved here from `../../analysis/` on 2026-11-08. `analysis/` is now
history: it holds only `superseded/`, which carries the rejected iterations and
why they were rejected.

| File | What it checks |
|---|---|
| `verify.py` | P-5c category close and funding-stream close, both to zero residual |
| `recon_v3.py` | contract-level reconciliation across both HII primes |
| `falsify.py` | premise test. The prototype for the Challenger agent |
| `tx.py` | transaction history by fiscal year, largest actions, deobligations |
| `faf.py` | federal account funding by TAS, object class, program activity |

`tx.py` and `faf.py` take the source CSV path as their only argument.

## Agent and engine suites

| File | What it checks | Run with |
|---|---|---|
| `test_agents.py` | agent handlers on recorded cases, including the challenger's three recorded errors | `python checks/test_agents.py` |
| `test_gate.py` | gate routing and the N.7 recorded errors | `python checks/test_gate.py` |
| `test_llm_tracing.py` | every GatewayLLM trace goes to the dedicated audit experiment, not the session's | `python checks/test_llm_tracing.py` |
| `test_analyst.py` | analyst engine on synthetic cases with known answers | `PYTHONPATH=. python -m pytest checks/test_analyst.py` |

`test_analyst.py` is pytest only. Run as a plain script it defines the tests,
runs none, and exits 0, which looks like a pass.

## Deployment checks

Different purpose. These do not check the figures, they check that the thing
runs where it is going to run.

| File | What it checks |
|---|---|
| `test_serverless_entrypoints.py` | every `spark_python_task` in `resources/jobs.yml` imports with no `__file__` bound, which is how serverless executes it |
| `test_app.py` | the app's routes, charts and caching |
| `gates.py` | the four workspace preconditions, against a live profile |

`test_serverless_entrypoints.py` exists because a module-level
`pathlib.Path(__file__)` works in every local run and fails on every
serverless run. It reads the job definitions, so a new entry point is covered
the moment it is added to the bundle, with nothing to remember.

## The one change these need

They carry figures inline. `P5C`, `OBL_2116` and `cat5` are hardcoded, which
separates the number from its provenance at the moment the script is written.
That is the same failure class as the Columbia-class columns.

`ops/agents/tieout/run.py` holds the same checks as functions that take the
figures as arguments, so the values arrive from the claim table with their
lineage attached and a figure cannot be used without its provenance travelling
with it. These scripts stay runnable in the meantime and are the reference
implementation.
