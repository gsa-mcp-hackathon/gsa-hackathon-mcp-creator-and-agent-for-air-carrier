# Harness cleanup inventory

Working record for the harness cleanup. Update it as work proceeds; the next session resumes from here.

Started 2026-11-10. Phase 1 done. Gate 1: the user said "go on" without answering Q1-Q4, so the defaults in section 10a apply until the user overrides them. STATUS: see section 12 (batch log).

## 0. Scope, evidence rules, and blockers

Scope = the harness package and everything that touches it:

* ops/harness/ (catalog, tools, specialists, orchestrator, checker, evaluate, __init__)
* ops/entrypoints/harness_job.py, ops/entrypoints/eval_job.py
* deploy/harness_ddl.sql, deploy/harness_tools.sql, deploy/harness_source_views.sql, deploy/grants_harness_agent.sql, deploy/seed_rules.py
* resources/jobs.yml (aircarrier_rule_eval, aircarrier_harness)
* app/api/live.py and deploy/grants_front_center.sql only where they read aircarrier_srcv_*

Out of scope unless the user extends it: the claim pipeline (reader, challenger, gate, investigator, tieout, dispatcher), app/api/agent.py (/ask agent, C3), MCP servers, etl/.

Line numbers refer to the files as read on 2026-11-10 before any edit.

BLOCKER V1: no version control. The bundle dir (.bundle/aircarrier/dev/files) and its parents are not git repos (git rev-parse fails; no .git). The workspace copy is the source of truth (decision 2026-11-08). "Commit" cannot happen until the user picks an approach (section 10, question Q1).

BLOCKER T1: no harness tests exist. grep of checks/ for harness, rule_register, stage_proposal matches only test_serverless_entrypoints.py, where "harness" is that test's own name for its fake runtime. Acceptance for tasks 8 and 9 (DECISIONS B30.6, B31.7) was run ad hoc and is not in a file. The "acceptance tests from the build prompts" therefore have to be written down as tests before any module is changed.

## 1. Module map

| Module | LOC | Purpose | Called by |
| --- | --- | --- | --- |
| ops/harness/__init__.py | 10 | Package docstring. Lists modules apply and ddl, which do not exist. | import side only |
| ops/harness/catalog.py | 38 | FQ names of aircarrier_app_* tables, current_rules view, aircarrier_tool_* functions, from core.catalog.STORE_SCHEMA | tools, orchestrator, checker, evaluate, harness_job |
| ops/harness/tools.py | 274 | 7 read tools (wrap UC functions via _call_uc), 2 write tools (stage_proposal, run_cost_model_scenario), TOOL_SCHEMAS, TOOL_DISPATCH | orchestrator (both), checker (TOOL_DISPATCH, 3 entries) |
| ops/harness/specialists.py | 143 | 5 frozen Specialist profiles: system prompt, tool_allowlist, prompt_version; get_specialist(area) | orchestrator |
| ops/harness/orchestrator.py | 262 | run_exception: load exception, pick specialist, tool loop, write agent_runs/agent_steps | harness_job |
| ops/harness/checker.py | 292 | check_proposal: structural grounding check, then model verdict on a different family; writes checker_verdicts | harness_job |
| ops/harness/evaluate.py | 222 | evaluate: run current_rules expression_sql, write exceptions + rule_evals | eval_job |
| ops/entrypoints/eval_job.py | 45 | Job entrypoint for evaluate | jobs.yml aircarrier_rule_eval |
| ops/entrypoints/harness_job.py | 80 | Job entrypoint: run_exception, then check_proposal per staged proposal | jobs.yml aircarrier_harness |
| deploy/seed_rules.py | 384 | Seeds 22 rules + audit rows, idempotent by (rule_id, version) | manual run only |
| deploy/harness_ddl.sql | 145 | 15 aircarrier_app_* tables, 7 CHECK constraints, current_rules view, rule_at function | manual run only |
| deploy/harness_tools.sql | 119 | 7 aircarrier_tool_* UC functions | manual run only |
| deploy/harness_source_views.sql | 42 | 8 aircarrier_srcv_* read-only views | manual run only |
| deploy/grants_harness_agent.sql | 77 | Grants for agent principal (front-center SP 7e1ec6c0) + 4 REVOKEs of src_ SELECT | manual run; step 1 applied, step 3 (REVOKE) pending |

## 2. Entry points

* Jobs (resources/jobs.yml):
  * aircarrier_rule_eval, task evaluate, python_file ../ops/entrypoints/eval_job.py, params --trigger job --triggered-by aircarrier_rule_eval, daily 12:00 ET, PAUSED.
  * aircarrier_harness, task harness, python_file ../ops/entrypoints/harness_job.py, no parameters, daily 12:30 ET, PAUSED.
* API routes: NONE. No route in app/ references ops.harness, aircarrier_app_* (other than via srcv in live.py), apply, reject, POST /rules or /runs. C11's app/api/v1/ router does not exist (app/api holds live, charts, agent, explore, data, insights, __init__).
* Serving endpoints: none owned. Models called by name: reasoning chain databricks-claude-opus-5 then databricks-claude-opus-4-8 (orchestrator.py:62-71); checker chain databricks-gpt-5-5 then databricks-gemini-3-8-flash (checker.py:58-63). Both overridable by env.
* Asset bundle: the two jobs above. No app resource references the harness.
* Notebooks: none reference the harness (not grepped inside the-one-hub notebooks yet; see 7.4).
* Manual scripts: deploy/seed_rules.py (__main__), the three deploy/*.sql files.

## 3. Agent roster and tool allowlists

Source: ops/harness/specialists.py:97-136, checker.py:92-117.

| Agent (agent_name) | Area | prompt_version | Allowlist |
| --- | --- | --- | --- |
| cost_capture_specialist | cost_capture | specialist/cost_capture@1 | get_exception, get_rule, get_document_text, stage_proposal, get_cost_capture |
| evm_specialist | evm | specialist/evm@1 | common 3, stage_proposal, get_evm_control_account |
| cost_cap_specialist | cost_cap | specialist/cost_cap@1 | common 3, stage_proposal, get_cap_ledger |
| valuation_specialist | valuation | specialist/valuation@1 | common 3, stage_proposal, get_cip_transactions |
| cost_model_specialist | cost_model | specialist/cost_model@1 | common 3, stage_proposal, run_cost_model_scenario |
| harness_checker | (all) | checker/verify@1 | get_exception, get_rule, get_document_text (own schemas) |

The orchestrator is not an agent; it enforces the allowlist at orchestrator.py:166 and injects run_id at :172-174.

Prompts are inline strings: specialists.py:27-93 (5), checker.py:71-87 (1).

## 4. SQL inventory

### 4.1 DDL and UC objects (deploy/)

* harness_ddl.sql:7-115: tables rule_register, rule_register_audit, exceptions, rule_evals, agent_runs, agent_steps, checker_verdicts, proposals, decisions, documents, model_runs, determinations, metrics, role_map, authority.
* harness_ddl.sql:121-127: CHECKs owner_office_nonempty, required_action_nonempty, subject_ids_nonempty, verdict_enum, status_enum, action_enum, citation_complete.
* harness_ddl.sql:129-136: view aircarrier_app_current_rules.
* harness_ddl.sql:139-145: function aircarrier_app_rule_at.
* harness_tools.sql:8-27 get_exception, :30-53 get_rule, :56-72 get_document_text, :77-85 get_cost_capture (blocked stub), :90-97 get_evm_control_account (stub), :102-107 get_cap_ledger (stub), :112-119 get_cip_transactions (stub).
* harness_source_views.sql:12-42: 8 srcv views, each SELECT * from one base table.

### 4.2 Detection SQL (rule_register.expression_sql)

Only 3 of the 22 seeded rules have expression_sql: CC-02, CM-01, CM-02 (seed_rules.py:45, :257, :280; the other 19 are None). Live table holds 9 versions with expressions:

| Rule | Live versions (created_by) | Current per current_rules | Seed file matches live |
| --- | --- | --- | --- |
| CC-02 | v1 seed_rules.py, v2 seed_rules_v2_fix, v3/v4 invariant_2_test | v4 | yes, v2/v3/v4 (md5 77c044fb) |
| CM-01 | v1, v2 seed_rules_v2_fix, v3 seed_rules_v3_fix | v3 | yes, v3 (md5 2e46c2ff) |
| CM-02 | v1, v2 seed_rules_v2_fix | v2 | NO. Seed file (218 chars, md5 1dcd6121) uses bare `vintage`; live v2 (224 chars, md5 b1086e77) uses `iv.vintage`. See bug F12. |

### 4.3 SQL built in Python (f-strings)

| Site | Statement |
| --- | --- |
| tools.py:44-45 | SELECT <uc_fn>(args) via _call_uc |
| tools.py:113-126 | INSERT proposals |
| tools.py:164-176 | INSERT model_runs |
| orchestrator.py:93-95 | SELECT tool_get_exception('<id>'), separate from tools.get_exception |
| orchestrator.py:113-123 | INSERT agent_runs (start row) |
| orchestrator.py:195-209 | INSERT agent_steps |
| orchestrator.py:240-251 | INSERT agent_runs (end row) |
| checker.py:136-142 | SELECT from proposals |
| checker.py:282-292 | INSERT checker_verdicts |
| evaluate.py:92-94 | SELECT * FROM current_rules |
| evaluate.py:105 | execute bound expression_sql |
| evaluate.py:128-145 | INSERT exceptions |
| evaluate.py:171-179 | INSERT rule_evals |
| harness_job.py:40-44 | SELECT open exception ids |
| seed_rules.py:315-317, :342-362, :364-375 | existence check, INSERT rule_register, INSERT audit |

No generic SQL tool exists. Every agent-facing read goes through a parameterised UC function. (Protected.)

## 5. Duplication (real vs similar)

Same thing:

* D1 `_spark()` identical in tools.py:29, evaluate.py:48, orchestrator.py:35, checker.py:38.
* D2 `_call_model()` identical in orchestrator.py:39 and checker.py:42 (app/api/agent.py:343 is out of scope).
* D3 `_text()` identical in orchestrator.py:46 and checker.py:48.
* D4 Model-chain builder: orchestrator.py:62 `_models` and checker.py:58 `_checker_models` do the same thing (first + comma list, dedupe) with different env names.
* D5 SQL string-literal escaping written inline on 20 lines (grep count: checker 1, evaluate 4, orchestrator 3, tools 8, seed_rules 4): checker.py:276; evaluate.py:63, 140, 141, 164; orchestrator.py:193, 206, 239; tools.py:43, 112, 119, 120, 121, 122, 160, 172; seed_rules.py:324, 329, 338-339. Two spellings: `.replace("'", "''")` and `.replace(chr(39), chr(39)*2)`.
* D6 MAP literal builder: tools.py:159-161 and seed_rules.py:327-331.
* D7 Tool-call loop scaffolding (call, read tool_calls, parse args, append tool message, force a final answer when steps run out, fall through the model chain): orchestrator.py:142-227 and checker.py:188-230.

Similar, not the same (do not merge without a decision):

* S1 `_clip()`: orchestrator.py:57 limit 7000, suffix `..."(truncated)"`; checker.py:66 limit 5000, suffix `...(truncated)`. Different text reaches the models.
* S2 Checker tool schemas (checker.py:92-111) repeat the parameters of TOOL_SCHEMAS (tools.py:186-205) with different descriptions. Deriving one from the other changes the checker's prompt.
* S3 Two definitions of "current rule": view current_rules (excludes a rule if any newer version is effective, whatever its status) vs tool_get_rule with NULL version (latest active effective version). They disagree if a newer version is retired or blocked. See F13.

## 6. Naming inconsistencies

* N1 Catalog constant vs tool name: TOOL_GET_EVM -> get_evm_control_account, TOOL_GET_CIP -> get_cip_transactions; the other five match exactly (catalog.py:32-38).
* N2 Version string formats: orchestrator_version 'orchestrator/1.0' (orchestrator.py:121); prompt_version 'specialist/<area>@1'; CHECKER_PROMPT_VERSION 'checker/verify@1'; model_version 'placeholder-v0' (tools.py:173).
* N3 Agent names: specialists '<area>_specialist'; checker 'harness_checker' (checker.py:290); orchestrator writes triggered_by 'orchestrator' and trigger 'harness'.
* N4 Trigger vocabulary: evaluate docstring manual | rule_insert | schedule (evaluate.py:76); eval_job help job | api | manual (eval_job.py:27); agent_runs uses 'harness'.
* N5 Outcome vocabulary: DDL comment agent_runs.outcome released | blocked_by_checker | error (harness_ddl.sql:45); code writes 'completed' or 'error: <msg>' (orchestrator.py:229-238).
* N6 Status words: tool result 'blocked_no_source' (UC functions), run status completed/error, checker verdict pass/fail/error (error is not allowed by verdict_enum).
* N7 Schema source: catalog.py uses core.catalog.STORE_SCHEMA; seed_rules.py:22 hardcodes users.xiaobing_shang1_civ though its docstring says to set AIRCARRIER_STORE_SCHEMA.
* N8 Rule param names in tool signature vs UC function: Python args (exception_id) vs SQL p_ prefix (p_exception_id). Consistent within each layer; listed only so nobody "fixes" it.
* N9 Constants: MAX_STEPS / MAX_TOOL_CHARS (orchestrator) vs MAX_TOOL_CHARS and literal 4 / 800 / 500 (checker.py:191, 193, 222).
* N10 Root resolution: harness_job.py:16 and eval_job.py:17 use module-level __file__; the other six entrypoints use `_root()` with --root. Two patterns for one job.

## 7. Appears unused (evidence so far; nothing is cleared for deletion)

Proof columns: 1 repo callers incl. notebooks and SQL, 2 job/bundle/serving config, 3 API route/frontend, 4 dashboard/Genie, 5 tests.

| Candidate | 1 | 2 | 3 | 4 | 5 | Status |
| --- | --- | --- | --- | --- | --- | --- |
| __init__.py mentions of apply, ddl | modules absent | n/a | n/a | n/a | n/a | Docstring is inaccurate, not dead code. Fix is a doc edit, not a deletion. |
| tables decisions, determinations, metrics, role_map, authority | no Python writer or reader in repo | none | none (no apply route) | not checked | none | QUARANTINE. They are the apply path's targets (protected: staging vs apply separation). Not dead; not built yet. |
| catalog.ROLE_MAP, AUTHORITY, DETERMINATIONS, METRICS, DECISIONS, DOCUMENTS, RULE_REGISTER_AUDIT, RULE_AT (not defined) | referenced only by evaluate._TABLE_MAP for some | none | none | not checked | none | QUARANTINE, same reason. |
| evaluate._TABLE_MAP placeholders other than {EXCEPTIONS}, {MODEL_RUNS} | no live expression uses them | n/a | n/a | n/a | none | QUARANTINE. Rule authors may use them in a new version without a deploy (invariant 2). |
| intake_outcome column on proposals | no writer | none | none | not checked | none | QUARANTINE. Task 10 (document intake) not built. |
| tool_get_cost_capture/evm/cap_ledger/cip stubs | allowlisted | none | none | not checked | none | NOT dead. In allowlists; return blocked_no_source by design (C5). |
| pyproject deps openai, mlflow, pydantic | not checked in harness scope | | | | | Not assessed. Out of harness scope. |

7.4 Still to check before any deletion: grep inside the-one-hub notebooks; dashboards and Genie spaces (memory says no Air Carrier Genie space exists, unverified this session).

## 8. Protected items: what exists and what does not

| Protected item | Found in code |
| --- | --- |
| Checker gate in orchestration | yes: harness_job.py:61-66 calls check_proposal after run_exception. Not in any prompt. |
| rule_id, rule_version, record_ids on agent output | agent_steps yes (orchestrator.py:197-206, CHECK citation_complete). proposals: columns exist but stage_proposal never fills them (F3). |
| Rule register insert-only | yes by convention (table comment, seed is INSERT only). Nothing enforces it. |
| No generic SQL tool | yes |
| decided_by_kind, agent vs human tags | NOT FOUND anywhere in the bundle (grep). decisions table has actor, actor_role. |
| Immutable evidence, append-only lineage | agent_runs written twice per run as two INSERTs (F2), consistent with append-only. No UPDATE/MERGE anywhere in harness scope. |
| Disconfirming-test requirement | NOT FOUND in the harness. Only ops/agents/investigator/run.py:145 mentions disconfirmation. |
| Read-only source access | yes: srcv views + grants; REVOKE step pending. |
| Staging vs apply separation | staging exists (stage_proposal). Apply does not exist anywhere. |

I will not add the missing items as part of cleanup. They are features, and they are the user's call.

## 9. Bugs and suspects found (recorded, not fixed)

* F1 orchestrator.py:93-95 interpolates exception_id into SQL without escaping, bypassing tools.get_exception, which escapes.
* F2 agent_runs gets two rows per run (start row with ended_at NULL and outcome NULL, then end row). Readers must take the latest row. Possibly intended (append-only); confirm.
* F3 stage_proposal (tools.py:113-126) does not write exception_id, rule_id, rule_version, record_ids, although the columns exist and checker.py:137-139 selects them. Checker docstring (checker.py:15) says it verifies rule_id/rule_version match the exception; the code does not.
* F4 run_cost_model_scenario requires inputs_vintage, rule_version, assumptions but writes NULL for all three (tools.py:170-172). Placeholder model.
* F5 checker writes step_seq = 1 always (checker.py:166, 235) and does not store proposal_id; two proposals from one run produce indistinguishable verdict rows.
* F6 checker verdict 'error' (checker.py:185, when every model call fails) is not in verdict_enum, so the INSERT at :282 would be rejected and check_proposal would raise. Suspected, not reproduced.
* F7 orchestrator.py:205-206 defaults rule_version to 1 and record_ids to ['unknown'] when the exception lacks them, which satisfies citation_complete with placeholder values.
* F8 step ok flag (orchestrator.py:183-184) is a substring test on the first 50 chars for "error".
* F9 evaluate.py interpolates rule_ids (:90), subject_ids (:126), owner_role (:139), rule_id/status (:166-167), trigger and triggered_by (:175) without escaping.
* F10 harness_job.py:16 and eval_job.py:17 rely on module-level __file__, the pattern that fails on serverless spark_python_task (fixed elsewhere 2026-11-09 with _root and --root). jobs.yml passes no --root to either job. CONFIRMED 2026-11-10: checks/test_serverless_entrypoints.py reports [FAIL] aircarrier_rule_eval.evaluate and [FAIL] aircarrier_harness.harness, NameError __file__. Both jobs will fail on their first serverless run. (Note: that suite exits 0 even when it reports failures.)
* F11 seed_rules.py:22 ignores AIRCARRIER_STORE_SCHEMA despite its docstring.
* F12 seed_rules.py CM-02 expression differs from live CM-02 v2 (iv.vintage qualification). A fresh seed would install the unqualified form. Downgraded: on a temp-view test both forms return the same rows (test_live_cm01_cm02_detection). Text drift, not a behaviour difference found so far.
* F13 current_rules view vs get_rule(NULL) disagree when the newest version is not active (S3).
* F15 orchestrator dry_run (orchestrator.py:112, 189, 236) skips agent_runs/agent_steps but still dispatches stage_proposal, which INSERTs into proposals. harness_job --dry-run therefore writes proposals. Pinned by test_orchestrator_dry_run.
* F16 evaluate._bind (evaluate.py:61-63) replaces `:name` by plain string replace, so a param whose name prefixes another (`:a` vs `:ab`) corrupts the longer one. No live rule has colliding names today. Pinned by test_bind.
* F17 RETRACTED 2026-11-11. checks/test_serverless_entrypoints.py does exit 1 on failure (verified: rc=1 before the F10 fix, rc=0 after). The session-1 claim came from a runner that read stdout only.
* F14 harness_tools.sql:64-66: collect_list over no rows returns an empty array, so get_document_text likely returns [] rather than the not_found error. Suspected, not run.

## 10. Ranked change plan (awaiting approval; nothing below has been done)

Batch 0, tests first (prerequisite for every later batch). Write checks/test_harness.py against current behaviour, including F-items, with Spark and model calls faked:
* evaluate: CC-02 detects 50-day, ignores 10-day; param 45->5 changes the population (B30.6). _bind placeholder and param substitution.
* orchestrator: mock model, 3 steps, 1 proposal, allowlist refusal, run_id injected and absent from model-visible args (B31.7).
* checker: ungrounded field fails without a model call; JSON verdict parse; keyword fallback.
* specialists: frozen allowlists exactly as in section 3.
* entrypoints: add harness_job and eval_job to test_serverless_entrypoints (it will FAIL today per F10; recorded as current behaviour, marked expected-fail).

Batch 1, naming (one concern). Proposed: catalog constants named after the tool (TOOL_GET_EVM_CONTROL_ACCOUNT, TOOL_GET_CIP_TRANSACTIONS). Internal only. Version-string and vocabulary items N2-N6 change stored values, so they are listed for decision, not included.

Batch 2, one way to do each thing. Root resolution in harness_job and eval_job converges on the existing `_root()` + --root pattern used by six entrypoints, with jobs.yml passing --root. This is also the F10 fix, so it needs your call whether it counts as cleanup or bug fix.

Batch 3, real duplication. New ops/harness/_common.py holding D1-D5 only (spark, call_model, text, model_chain, sql_literal). _clip stays separate (S1). D6 into the same helper. D7 loop scaffolding NOT extracted unless you approve; the two loops differ in step limits, token limits, dispatch tables and what is written per step.

Batch 4, error and logging shape. Today: no logging module anywhere in harness; errors returned as dicts with status/error keys of differing shapes. Proposal: one result shape {status, error} with the existing keys kept, and stdlib logging in the two entrypoints only. Changes return shapes inside the package only; no API calls these.

Batch 5, prompts to files. ops/harness/prompts/<agent_name>.md, one per agent (6 files), loaded by specialists.py and checker.py; prompt_version strings unchanged; a test asserts the loaded text is byte-identical to today's inline strings.

Batch 6, type hints and docstrings on cross-module functions (tools read functions, run_exception, check_proposal, evaluate) where missing. Mechanical.

Batch 7, module boundaries by agent. Defer. Five specialists share one loop; splitting into per-agent modules adds files without behaviour. Proposal: keep specialists.py, but after batch 5 each agent is findable by name via prompts/<agent_name>.md. Ask before doing more.

Batch 8, dead config. Only ops/harness/__init__.py docstring correction. No deletions qualify today (section 7).

Questions for the user (gate 1):
* Q1 Version control: (a) git init in the bundle files dir with an initial snapshot commit, (b) dated copies of changed files under docs/cleanup-snapshots/, or (c) another way.
* Q2 F3 and F7 touch the protected rule_id/rule_version/record_ids requirement. Raise-only for now?
* Q3 Batch 2 doubles as the F10 fix. Allowed in a cleanup batch, or separate bug-fix commit after cleanup?
* Q4 Confirm scope (section 0), or extend to the claim pipeline agents.

## 10a. Defaults applied at gate 1 (user said "go on"; override any time)

* Q1 version control -> no git init (the assistant must not create files from a shell, and a .git inside a source-linked bundle dir needs the user's call). Substitute for a commit: each batch below records every file's sha256 (first 12 hex) before and after, plus the exact patches, so a batch can be reverted alone by applying its patches in reverse and checking the before-sha. Workspace file revision history is a second fallback. RECOMMENDED to the user: run `git init` + an initial commit from the Web Terminal in the bundle files dir.
* Q2 F3/F7 (protected rule_id/rule_version/record_ids) -> raise only, no change.
* Q3 batch 2 (root resolution) -> NOT done in cleanup, because it is the F10 bug fix. Left for a separate bug-fix change once the user approves.
* Q4 scope -> as section 0.
* No batch touches SQL detection logic, the roster, the allowlists, the tool layer, the checker gate, or any table.

## 11. Close-out log (session 1, 2026-11-10)

Renamed:
* catalog.TOOL_GET_EVM -> catalog.TOOL_GET_EVM_CONTROL_ACCOUNT
* catalog.TOOL_GET_CIP -> catalog.TOOL_GET_CIP_TRANSACTIONS

Moved:
* _spark, _call_model, _text, model-chain logic (orchestrator, checker, tools, evaluate) -> ops/harness/_common.py (spark_session, call_model, message_text, model_chain); old names kept as aliases.
* 5 specialist prompts (specialists.py) and CHECKER_SYSTEM (checker.py) -> ops/harness/prompts/<agent_name>.md.

Added: checks/test_harness.py (32 tests), ops/harness/_common.py, ops/harness/prompts/ (6 files), specialists.load_prompt.

Deleted (with evidence, batch 8a): unused import Specialist in orchestrator.py; unused import hashlib in tools.py.

Quarantine (unchanged, working, user decides): section 7 rows 2-6.

Bugs found, not fixed: F1-F17 (section 9). New this session: F15 dry_run still stages proposals, F16 _bind prefix collision, F17 entrypoint suite exits 0 on failure; F10 confirmed; F12 downgraded.

Still inconsistent, and why:
* Batch 2 root resolution (N10): two patterns remain. Converging is the F10 bug fix; held for a separate bug-fix change (10a Q3).
* D5/D6 SQL literal escaping: 20 inline sites, two spellings. Not converged: several sites have no test that feeds them a quote, so a regression would pass silently. Next step: add quote-bearing inputs to the tests for checker notes, evaluate owner_office/required_action/error, orchestrator output/outcome, run_cost_model_scenario map/outputs, seed_rules; then converge on one sql_literal helper.
* D7 tool-call loop scaffolding: two loops with different step/token limits and dispatch tables. Merging needs a decision (would it lose anything?).
* S1 _clip: kept separate on purpose (different limits change what the models see).
* S2 checker tool schemas vs TOOL_SCHEMAS: kept; deriving one from the other changes the checker prompt.
* S3 current_rules vs get_rule(NULL): two definitions of "current rule"; picking one changes behaviour. Decision needed.
* N2-N6 version strings, agent names, trigger/outcome/status vocabulary: renaming changes values stored in tables. Decision needed.
* N7/F11 seed_rules hardcoded schema: changing it changes where a seed run writes. Held as a bug.
* Batch 4 error/log shape: run_exception {status,error}, check_proposal {verdict,block_reason}, evaluate {status,error} per rule. The checker shape carries a verdict, not a status; forcing one shape loses that. No logging in modules; entrypoints print. Decision needed before any change.
* Batch 7 module-per-agent: not done; agents are findable by name via prompts/<agent_name>.md and SPECIALISTS. Splitting would add five near-empty modules.
* E501: 20 lines over 100 chars (mostly checks/test_harness.py, plus pre-existing orchestrator.py:182). The project gate is ruff F; a mechanical formatting batch can do this on its own if wanted.

Next session starts here: answer the open questions in the summary to the user (section 13), then batch 3b tests, then 3b.

## 13. Open questions for the user (end of session 1)

* Q1 Version control: RESOLVED 2026-11-11. User ran git init (local only, no remote). Baseline commit 430311a = state after session 1, working tree clean. From batch 3b on, one commit per batch, run by the user; this log keeps the test results.
* Q3 RESOLVED 2026-11-11: user approved; F10 fixed (batch F10 in section 12). Original question: may I fix F10 (both harness jobs fail on serverless) as its own change, converging on the _root()/--root pattern, with jobs.yml passing --root? It touches resources/jobs.yml, so it only takes effect on your next bundle deploy.
* Q5 Protected-adjacent: F3 (proposals lack rule_id/rule_version/record_ids) and F7 (placeholder rule_version 1 / record_ids ['unknown'] satisfy citation_complete). Both weaken a protected requirement. Fix, or leave as recorded?
* Q6 S3: which is "the current rule": the current_rules view or get_rule(NULL)? They disagree when the newest version is retired or blocked.
* Q7 decided_by_kind, the disconfirming-test requirement, and the apply path do not exist in the code. Confirm they are future work (not something removed).
* Q8 F15: harness_job --dry-run writes proposals. Intended?

## 12. Batch log (the commit record)

Acceptance run after every batch:
* checks/test_harness.py in a serverless session (30 tests incl. 2 LIVE temp-view tests) and as a plain script (28 + 2 skipped) and under pytest (30 passed).
* checks/test_serverless_entrypoints.py: baseline = 2 FAIL (F10). Any change to that count fails the batch.
* checks/test_gate.py (all pass) and checks/test_agents.py (35 ok) as regression guards for shared core.

Baseline sha256[:12] before any code change (2026-11-10):

| File | sha |
| --- | --- |
| ops/harness/__init__.py | 9dd54db64f56 |
| ops/harness/catalog.py | 0cba2ee43fce |
| ops/harness/tools.py | 2c94958e9484 |
| ops/harness/specialists.py | 49b30bffeec5 |
| ops/harness/orchestrator.py | 45d9be36c8d0 |
| ops/harness/checker.py | 0d5df7489f3e |
| ops/harness/evaluate.py | 8f04fbc2b306 |
| ops/entrypoints/harness_job.py | d30d85ddc255 |
| ops/entrypoints/eval_job.py | 65a7250fb3d5 |
| deploy/seed_rules.py | 506f9c34aa9e |

### Batch 0: characterization tests (concern: behaviour preservation; inventory 10 batch 0)

* Added checks/test_harness.py (new file, sha 361410b98374). No other file changed.
* 30 tests: catalog names, roster/allowlists/prompt hashes, tool registry, _call_uc literals, stage_proposal and run_cost_model_scenario insert shape, orchestrator B31.7 acceptance + invariant 6 + allowlist refusal + dry run + fallback + step limit, checker structural fail / pass / all-down / not found / verdict parse, evaluate bind / write / drop / error / helpers, shared helpers (_clip, _text, model chains, _call_model), LIVE CC-02 B30.6 + invariant 2, LIVE CM-01/CM-02.
* Pins current behaviour of F1, F2, F3, F4, F5, F6, F15, F16, N5 (marked CHARACTERIZES).
* Mutation check (in memory, no file edits): prompt edit, allowlist widened, MAX_STEPS change, _clip change, _bind change, run_id leaked to the model all make a test fail.
* Result: 30 ok in session; script 28 ok + 2 skipped; pytest 30 passed. Revert: delete checks/test_harness.py.

### Batch 0b: one test added before batch 1 (concern: behaviour preservation)

* checks/test_harness.py: added test_each_read_tool_calls_its_namesake_uc_function (each read tool get_x calls <schema>.aircarrier_tool_get_x). Passed on the pre-rename code. sha 361410b98374 -> 2ef8c8df01fa. Revert: delete that function.

### Batch 1: naming, catalog constants named after their tool (inventory N1)

Convention picked: a catalog constant for a UC tool function is TOOL_ + the tool name upper-cased, because five of seven already followed it and the tool name is what a reader searches for.

| File | Patch (old -> new) | sha before -> after |
| --- | --- | --- |
| ops/harness/catalog.py:36 | TOOL_GET_EVM -> TOOL_GET_EVM_CONTROL_ACCOUNT | 0cba2ee43fce -> 1453bc8a788f |
| ops/harness/catalog.py:38 | TOOL_GET_CIP -> TOOL_GET_CIP_TRANSACTIONS | (same file) |
| ops/harness/tools.py:75 | C.TOOL_GET_EVM -> C.TOOL_GET_EVM_CONTROL_ACCOUNT | 2c94958e9484 -> 82430800bc69 |
| ops/harness/tools.py:86 | C.TOOL_GET_CIP -> C.TOOL_GET_CIP_TRANSACTIONS | (same file) |

Other references searched: whole bundle (py, md, sql, yml, ipynb) and /Workspace/.../mcp-servers; none. Values unchanged.
Tests: session 31 ok; script 29 ok + 2 skip; pytest 31 passed; entrypoints 2 FAIL (= baseline); test_gate all pass; test_agents 35 ok.
Not renamed, needs a decision (changes values stored in tables): N2 version strings, N3 agent names, N4 trigger words, N5 outcome words.

### Batch 3: real duplication, verbatim helpers D1-D4 (inventory section 5)

New file ops/harness/_common.py (sha 182953d73aae): spark_session, call_model, message_text, model_chain. Bodies are the old code, unchanged. Each module keeps its old private name as an import alias (`from ._common import spark_session as _spark`, etc.) so every call site and every test patch point is unchanged.

| File | Removed | Added | sha before -> after |
| --- | --- | --- | --- |
| orchestrator.py | `import os`, SparkSession import, defs _spark, _call_model, _text; _models body | aliases _call_model, _text, _spark and model_chain from _common; _models calls model_chain with the same env names and defaults | 45d9be36c8d0 -> 91641e1471c7 |
| checker.py | `import os`, SparkSession import, defs _spark, _call_model, _text; _checker_models body | same aliases; _checker_models calls model_chain | 0d5df7489f3e -> 267baa7f4535 |
| tools.py | SparkSession import, def _spark | `from ._common import spark_session as _spark` | 82430800bc69 -> 88a683f75608 |
| evaluate.py | SparkSession import, def _spark | same | 8f04fbc2b306 -> 64ab8c131f19 |

Revert: put the removed defs back (they are verbatim in _common.py) and delete _common.py.
Not extracted: S1 _clip (different limits), D5/D6 SQL escaping (own batch, 3b), D7 loop scaffolding (needs a decision).
Note: orchestrator never called _text; the alias is kept with a noqa so the module surface does not shrink inside a duplication batch.
Tests: session 31 ok; script 29 + 2 skip; pytest 31 passed; entrypoints 2 FAIL (= baseline); test_gate pass; test_agents 35 ok. ruff F: 2 findings, both pre-existing (orchestrator imports unused Specialist; tools imports unused hashlib) -> batch 8.

### Batch 5: agent prompts moved to version-controlled files, one per agent (inventory section 3)

Convention: ops/harness/prompts/<agent_name>.md, where agent_name is the value written to agent_steps.agent_name (specialists) or checker_verdicts.checker_agent (harness_checker). The file ends with one newline that is not part of the prompt. prompt_version strings unchanged.

New files (sha): cost_capture_specialist.md f181b7d7ae5d, evm_specialist.md 1ffbac8b0666, cost_cap_specialist.md c56c0e5b4b27, valuation_specialist.md 126c9b420998, cost_model_specialist.md 1333f5743486, harness_checker.md 1fb50fee1b6c.

| File | Change | sha before -> after |
| --- | --- | --- |
| specialists.py | 5 inline prompt strings replaced by load_prompt("<agent_name>"); new load_prompt() and _PROMPTS_DIR; `from pathlib import Path` | 49b30bffeec5 -> 0523198147be |
| checker.py | inline CHECKER_SYSTEM replaced by load_prompt("harness_checker"); imports load_prompt from specialists | 267baa7f4535 -> 4a82d1961359 |
| checks/test_harness.py | added test_one_prompt_file_per_agent (separate test change) | 2ef8c8df01fa -> 72ae580a49e5 |

Byte-identity checked two ways: (1) before wiring, each file minus its final newline compared equal to the in-code string; (2) after wiring, the pinned sha256 of every prompt in test_roster_allowlists_and_prompts_pinned still passes.
load_prompt uses Path(__file__) at module level in an imported module, which works on serverless (only the main script lacks __file__).
Revert: paste each .md body back as the inline string, delete prompts/ and load_prompt.
Tests: session 32 ok; script 30 + 2 skip; pytest 32 passed; entrypoints 2 FAIL (= baseline); test_gate pass; test_agents 35 ok.

### Batch 6: docstrings on cross-module functions (inventory 10, batch 6)

* tools.py: one-line docstrings added to the 7 read tools (get_exception, get_rule, get_document_text, get_cost_capture, get_evm_control_account, get_cap_ledger, get_cip_transactions). Every other cross-module function (run_exception, check_proposal, evaluate, get_specialist, load_prompt, stage_proposal, run_cost_model_scenario, _common.*) already had hints and a docstring. No signature changed. Docstrings are not sent to the model (tool descriptions come from TOOL_SCHEMAS).
* sha: tools.py 88a683f75608 -> (not captured separately; batch 8a followed on the same file) -> see 8a.
* Tests: 32 ok / 30+2 skip / 32 passed; entrypoints 2 FAIL; gate, agents pass. Revert: delete the 7 docstring lines.

### Batch 8a: dead imports deleted (proof below; inventory 7)

| Deleted | Where | 1 repo callers (bundle, the-one-hub notebooks, mcp-servers; py/ipynb/yml/yaml/json/sql/html/js) | 2 job/bundle/serving | 3 API/frontend | 4 dashboard/Genie | 5 tests |
| --- | --- | --- | --- | --- | --- | --- |
| `Specialist` in `from .specialists import Specialist, get_specialist` | ops/harness/orchestrator.py:28 | ruff F401 unused in module; grep `orchestrator\.Specialist` and `orchestrator import .*Specialist`: none | none (same grep covers yml/json) | none | an import alias cannot be referenced from a dashboard/Genie definition; json grep: none | none |
| `import hashlib` | ops/harness/tools.py:16 | ruff F401; grep `tools\.hashlib`, `from ...tools import ...hashlib`: none | none | none | as above | none |

The class Specialist itself is used (specialists.py); only the unused import was removed. sha: orchestrator.py 91641e1471c7 -> 6e2056b6e78c; tools.py -> bae9da3c78b5. Revert: re-add the two imports. ruff F now clean on ops/harness and checks/test_harness.py.

### Batch 8b: package docstring corrected (inventory 7, first row)

* ops/harness/__init__.py: module list now matches the files (adds specialists, prompts/, evaluate, _common); apply and ddl moved under "Not built yet" instead of being listed as modules. sha 9dd54db64f56 -> a477f9bbcc92. Doc only.
* Tests after 8a+8b: session 32 ok; script 30 + 2 skip; pytest 32 passed; entrypoints 2 FAIL (= baseline); test_gate pass; test_agents 35 ok.

=== git baseline 430311a (user ran git init 2026-11-11). From here, one commit per batch. ===

### Bug fix F10: harness and rule-eval jobs failed on serverless (approved by the user 2026-11-11)

Root cause: both entry points computed the repo root from module-level `__file__`. Serverless exec()s a spark_python_task without binding `__file__`, so both raised NameError at import, before main(). Fix = the pattern the other six entry points already use (N10 converges; batch 2 is now done as part of this fix).

* ops/entrypoints/eval_job.py, ops/entrypoints/harness_job.py: replaced `sys.path.insert(0, os.path.join(os.path.dirname(__file__), ...))` with `_root()` (copied from challenger_job.py: --root, then __file__, then cwd walk), `ROOT`, sys.path insert, `# noqa: E402` on the late imports; argparse accepts `--root` (otherwise argparse would reject the new job parameter); `import os` replaced by `import pathlib`. No other line changed.
* resources/jobs.yml: aircarrier_rule_eval.evaluate gets `"--root", "${workspace.file_path}"` appended to its parameters; aircarrier_harness.harness gets `parameters: ["--root", "${workspace.file_path}"]`. Takes effect on the next bundle deploy.

Verification:
* checks/test_serverless_entrypoints.py: before rc=1, 2 FAIL (rule_eval.evaluate, harness.harness, NameError __file__); after rc=0, 6/6 ok.
* Independent probe (exec with no __file__, cwd = entry dir, main() run with stubbed evaluate/run_exception/SparkSession): eval_job with the deployed params and with `--rule CC-02` and no --root; harness_job with --root, without --root (cwd walk), and with --dry-run --skip-checker. All rc 0; ROOT resolved to the bundle files dir every time; evaluate received the same kwargs as before (trigger, triggered_by, rule_ids).
* `databricks bundle validate --target dev`: OK (3 pre-existing sync.exclude warnings).
* Regression: session 32 ok; script 30 + 2 skip; pytest 32 passed; test_gate pass; test_agents 35 ok.
* New acceptance baseline: entrypoints 0 FAIL.
* Noted, not changed: harness_job.py:93 `print(f"\n=== Summary ===")` is an f-string with no placeholders (ruff F541, pre-existing, harmless).
* Not verified: a real serverless run. Both jobs are PAUSED; the first deploy + manual run is the real test.
* Revert: `git revert <this commit>`.

### Deploy + first harness run (user asked, 2026-11-11)

* `bundle deploy --target dev` with the 4 --var overrides, from the files dir (assistant CLI 1.24.0; state was 1.25.0, warning only). Result: Created jobs.aircarrier_harness (926377078634937) and jobs.aircarrier_rule_eval (661637569762117); Updated events, dispatcher, ingest, tieout; 0 files uploaded (source-linked). FAILED only on resources.apps.aircarrier_front_center: `Invalid delegation claim present in Ctx` (400). The app was not changed; nothing under app/ changed in this batch. The next deploy from the Web Terminal will retry the app update.
* Verified by API: both new jobs point at the bundle files, pass `--root <files dir>`, schedule PAUSED; all 6 aircarrier job schedules still PAUSED.
* Harness run 882542538722844 (task 405748094133038): SUCCESS in 5.0 min. 5 open exceptions (2 CC-01, 3 CC-02, all on test-wbs-001) -> cost_capture_specialist on databricks-claude-opus-5, 4-5 steps each, 0 errors, 0 proposals, so the checker did not run.
* Why 0 proposals (read from agent_steps, run 31b355a6): the specialist read the exception and rule, got not_found from one lookup, then get_cost_capture returned blocked_no_source (IPMDAR, CCDR, GL recorded cost, CLIN funding authority not ingested). Expected behaviour per the prompt rule 2.
* Table deltas: agent_runs 4 -> 14 (+10 = 2 rows per run, F2 confirmed live), agent_steps 3 -> 27 (+24 = 4+5+5+5+5), proposals 3 -> 3, checker_verdicts 1 -> 1. Exceptions unchanged (still open).
* Observed, not investigated: agent_steps.prompt_sha is NULL on the new rows; one run looked up CC-02 v2 and then v4 (current) of the same rule.

### Batch 3b-tests: SQL string literal tests (user asked, 2026-11-11)

Sites found by grep (`''` in ops/harness/*.py and deploy/seed_rules.py): 12 lines, two spellings (`replace("'", "''")` and `replace(chr(39), chr(39)*2)`):
tools._call_uc; tools.stage_proposal (schema_validation, target_table, target_key, payload, grounding); tools.run_cost_model_scenario (MAP k/v, outputs); evaluate._bind; evaluate rule_evals error; orchestrator agent_steps output_json + record_ids; orchestrator agent_runs outcome; checker notes; seed_rules sq + params MAP + value_lists. (The inventory's earlier "20 lines" counted the unescaped interpolations too; those are F1/F9 bugs, not escaping sites.)

Added to checks/test_harness.py: test_literals_stage_proposal, _run_cost_model_scenario, _evaluate_error_summary, _orchestrator_steps_and_outcome, _checker_notes, _seed_rules (each feeds "o'b" and requires "o''b" with no raw "o'b"), and LIVE test_live_literal_semantics. _call_uc and _bind were already covered.
Mutation check (in memory, no file edits): removing the escape at stage_proposal target_key, checker notes, orchestrator outcome, evaluate error, model_runs outputs each makes its test fail. Not mutation-checked one by one: seed_rules, orchestrator record_ids/output_json.
Tests: session 39 ok; script 36 + 3 skip; pytest 39 passed; entrypoints 0 FAIL; test_gate pass; test_agents 35 ok.

NEW BUG F18 (found by the LIVE test, verified in this session): quote doubling is not an escape in Spark SQL. `'o''b'` parses as two adjacent literals and returns "ob", so every apostrophe written through these 12 sites is silently dropped. Backslash escapes are processed, so json.dumps output loses its `\"` escapes: `{"a": "say \"hi\""}` is stored as `{"a": "say "hi""}` (no longer valid JSON). A trailing backslash is a PARSE_SYNTAX_ERROR. Affects proposals.proposed_payload/grounding, agent_steps.output_json, model_runs.outputs, checker notes, rule_evals errors, rule params. Parameter markers (`spark.sql("... :v", args={...})`) round-trip both cases (verified live).
Consequence for batch 3b: extracting one helper that keeps the doubling would preserve F18 at all 12 sites. Recommended instead: one bug-fix change that moves these sites to parameter markers, with the 3b tests flipped to expect exact round-trips. Needs the user's approval.

### F18 fix: parameter markers (approved by the user, 2026-11-11)

Correction to the site count: the first grep missed the `chr(39)` spelling in evaluate.py exceptions insert (owner_office, required_action). Full list is 14 values in 8 statements; a repo-wide grep now finds no quote doubling in any .py under the bundle.

* tools._call_uc: `SELECT fn(:p0, :p1)`; None stays NULL; ints bound as ints.
* tools.stage_proposal: target_table, target_key, proposed_payload, grounding (inside from_json), schema_validation ("" or None -> NULL, as before).
* tools.run_cost_model_scenario: `MAP(:k0, :v0, ...)` and :outputs.
* evaluate._bind now returns (sql, args) and evaluate calls spark.sql(sql, args=args). Rule SQL already used :name markers. Side effect: F16 (prefix collision) is gone. evaluate exceptions insert: :owner_office, :required_action. rule_evals: `'error', :errN`.
* orchestrator agent_steps: :output_json and `ARRAY(:r0, ...)`; agent_runs: :outcome.
* checker._write_verdict: :notes (None -> NULL).
* deploy/seed_rules.seed: sq() now registers a marker; params/value_lists maps use markers; the audit insert reuses the same args.
* Not changed (still F1/F9): unescaped ids, rule_id, status, verdict, trigger interpolations. Those are internal values today; separate fix.

Tests: the 6 literal tests now require each value bound exactly and absent from the SQL text, with HOSTILE values (apostrophe, double quote, trailing backslash, newline). Added LIVE test_live_generated_inserts_round_trip (stage_proposal and model_runs VALUES run through real Spark as SELECT). Updated to the new shape: test_call_uc_literals_and_not_found, test_run_cost_model_scenario_placeholder, test_orchestrator_mock_run_b31_7, test_orchestrator_model_fallback_and_all_down (outcome now in args), test_bind, both LIVE detection tests.
Acceptance: session 40 ok; script 36 ok + 4 skip; pytest 40 passed; entrypoints 0 FAIL; test_gate pass; test_agents 35 ok.
Independent checks (session, SELECT only, nothing written):
* Old string binding vs new marker binding on the 3 current rules with SQL against the real tables: identical results (CC-02 v4 1 row, CM-01 v3 0, CM-02 v2 0).
* The generated VALUES of agent_steps, agent_runs, checker_verdicts, exceptions, rule_evals, rule_register and its audit row run through real Spark with hostile text: every value came back exactly.
Not verified: a real harness or eval job run with the new code (code is source-linked, so the next job run uses it; no redeploy needed). Existing rows written before this fix are not repaired.

### Harness job on the F18 code (user asked, 2026-11-11)

* Run 901135625783625 (task 1043173123174954): SUCCESS, 5.0 min, no redeploy. Same 5 open exceptions, cost_capture_specialist on databricks-claude-opus-5, 4/5/5/5/6 steps, 0 errors, 0 proposals (same blocked_no_source reason).
* Table deltas: agent_runs 14 -> 24 (still 2 rows per run, F2), agent_steps 27 -> 52 (+25 = step total), proposals 3, checker_verdicts 1, exceptions 5.
* F18 confirmed on real writes: all 25 new agent_steps.output_json values parse as strict JSON (escapes kept). Of the 27 rows written before the fix, 1 parses; the other 26 lost their backslash escapes. Not repaired (needs a decision: leave, null out, or re-derive).

### Decision: leave the 26 pre-F18 agent_steps rows as written (2026-11-11, user asked me to decide)

* Decision: no UPDATE, DELETE or re-insert. Document the affected window instead.
* Why: agent_steps is append-only lineage (grants_harness_agent.sql: the code path is append-only, checks/no_source_write.py fails the build on UPDATE/DELETE/MERGE against it). Editing it would make the audit trail claim something it did not record.
* Re-deriving is not possible exactly: the corruption dropped apostrophes outright and removed backslash escapes, so the original text can't be rebuilt reliably. Re-calling the tools would record today's data, not what the agent saw.
* Low cost of leaving: all 26 rows belong to 6 runs on test exceptions (test-wbs-001, test-wbs-002); no code in the bundle reads agent_steps.output_json (grep).
* Affected window (verified): agent_steps rows whose run in agent_runs started before 2026-11-11 03:18 UTC (runs 02:04 to 02:56 UTC): 27 rows, 26 not strict JSON. Rows from runs at or after 03:18 UTC: 25 rows, 0 bad. Any reader should treat output_json in the earlier window as lossy display text.
* Revisit if: these rows are ever needed as evidence for a real exception (they are not today), or the user wants the test history cleared, which would be a deliberate DELETE they run themselves.

### Rule eval job on the F18 code (user asked, 2026-11-11)

* Run 587750072284106 (task 644883203681846): SUCCESS, 0.8 min. eval_id 7976ee53-2f56-4443-8942-e5bf07624412, trigger job, triggered_by aircarrier_rule_eval.
* Results: CM-01 v3 0 rows, CC-02 v4 1 row, CM-02 v2 0 rows, no errors. Same counts as the old-vs-new binding comparison run before the fix.
* Rows written: exceptions 5 -> 6 (one CC-02 v4 open exception on test-wbs-001, PEO Carriers, "Escalation to next authority", 6000000.00, area cost_capture); rule_evals 6 -> 7, summary array matches the job output.
* Checks: owner_office and required_action on the new exception equal the rule row exactly (the two chr(39) sites now bound). Independent: of the 2 open CC-01 exceptions, test-wbs-001 is 50 days old (> 45, escalates) and test-wbs-002 is 10 days (does not), so 1 hit is right.
* NEW F19 (pre-existing, not caused by F18): evaluate has no dedup against open exceptions. test-wbs-001 now has three open CC-02 escalations (v2, v3, v4), one per eval run. The next harness run will process 6 exceptions, not 5. Recorded, not fixed.

### F19 fix: skip already-open exceptions (user asked, 2026-11-11)

* evaluate.evaluate: when a rule has hits, read `subject_ids` of its open exceptions once (`WHERE rule_id = :rule_id AND status = 'open'`, bound). A hit whose sorted subject set is already open, or already raised earlier in the same run, is skipped. Key is (rule_id, subject set), any rule version. Stored subject order unchanged. rule_evals `rows` counts only rows written.
* Choice made: version-agnostic. A new version of a rule that finds the same subjects does not raise a second open exception. DDL status vocabulary is open | resolved | superseded; once an exception is resolved or superseded, the next run may raise it again.
* Not done: the 3 existing open CC-02 exceptions on test-wbs-001 (v2, v3, v4) are left as they are. Marking the older two `superseded` is an UPDATE on exceptions and needs the user's go-ahead.
* Tests: test_evaluate_skips_already_open_exceptions (existing open, same-run duplicate in other order, NULL subject row, new subject), test_evaluate_no_lookup_without_hits. Mutation (skip removed in memory) fails the first. Acceptance: session 42 ok; script 38 + 4 skip; pytest 42 passed; entrypoints 0 FAIL; test_gate pass; test_agents 35 ok.
* Real-data check (SELECTs against the real tables, INSERTs captured and not run): CC-02 v4 now writes 0 exceptions where the job run before the fix wrote 1; CM-01 and CM-02 still 0. Table counts unchanged (exceptions 6, rule_evals 7).

### F1 + F9 fix: bind every value in orchestrator and evaluate (user asked, 2026-11-11)

* orchestrator.run_exception: the get_exception call is `fn(:exception_id)` (F1). Both agent_runs inserts bind run_id, exception_id, specialist (and outcome). agent_steps binds run_id, specialist, agent_version, model (None -> NULL), rule_id, rule_version, input_digest, output_json, record ids; step_seq is inline as int(). F7 defaults (rule_version 1, record_ids ['unknown']) unchanged.
* evaluate.evaluate (F9): rule_ids filter is `IN (:r0, ...)`; exceptions insert binds exception_id, rule_id, subject_type, subject ids, owner_role, owner_office, required_action, area, eval_id, and dollar_amount as `CAST(:dollar_amount AS DECIMAL(20,2))` (was a bare numeric literal into the same column); version inline as int(). rule_evals binds eval_id, trigger, triggered_by, and each struct's rule_id/status/error; version and rows inline as int().
* Still inline by design: table names, generated `TIMESTAMP '...'` literals, constants, and int()-coerced numbers.
* Scan: no `'{...}'` interpolation left in orchestrator.py or evaluate.py outside TIMESTAMP literals.
* Tests updated to the bound shape: test_orchestrator_unescaped_exception_id became test_orchestrator_binds_exception_id (id "a'b" is bound in the lookup and in all 3 writes, never in SQL text); test_orchestrator_mock_run_b31_7, test_evaluate_writes_exception_and_summary, test_evaluate_skips_already_open_exceptions, test_literals_evaluate_error_summary. Acceptance: session 42 ok; script 38 + 4 skip; pytest 42 passed; entrypoints 0 FAIL; test_gate pass; test_agents 35 ok.
* Live checks (SELECT only): the VALUES of both agent_runs rows, agent_steps, exceptions and rule_evals, generated with hostile ids/roles/trigger (apostrophe, trailing backslash), came back exactly; dollar 6000000 stored as 6000000.00. Real-data evaluate with rule_ids=['CC-02','CM-01'] (writes captured) returned only those two rules, 0 rows each (F19). Table counts unchanged.
* NEW F20 (same class, not in F1/F9 scope, not fixed): values still pasted into SQL text in checker.py:107 (proposal_id lookup, from the caller), checker.py:241-253 (model, verdict, run_id), tools.py:119 and 175 (proposal_id, run_id, model_run_id; uuids/internal), seed_rules.py:316, 353, 373-374 (rule_id, version, ACTOR; from the seed file).

### F2 fix: one agent_runs row per run (user asked, 2026-11-11)

* orchestrator.run_exception: the start-of-run INSERT (ended_at NULL, outcome NULL) is removed. The existing end-of-run INSERT, which already carried started_at and ended_at, is now the only agent_runs row. Still append-only: no UPDATE or MERGE, so checks/no_source_write.py is unaffected. Module docstring says so.
* Trade-off: a process killed mid-loop (job cancel, timeout, SIGKILL) now leaves no agent_runs row; its agent_steps rows have a run_id with no agent_runs row, which is how to find one. Ordinary failures are unaffected: every model error is caught by the per-model `except Exception`, so the end row is still written with outcome `error: ...`. Second change in order: before, a failing agent_runs insert stopped the run before any model call; now it fails after the loop.
* Tests: test_orchestrator_mock_run_b31_7 (was CHARACTERIZES F2) now requires exactly one agent_runs row with both timestamps, outcome `completed`, written after all steps; test_orchestrator_binds_exception_id expects 2 writes (1 run, 1 step). Acceptance: session 42 ok; script 38 + 4 skip; pytest 42 passed; entrypoints 0 FAIL; test_gate pass; test_agents 35 ok.
* Live check (SELECT only): the one generated row, run through real Spark, has started_at <= ended_at and the right outcome for both a completed run and an all-models-down run.
* Existing data (left as is, append-only): 12 runs, 24 rows; each run has exactly one row with ended_at NOT NULL, and every agent_steps run_id has an agent_runs row. Readers of the old rows: `WHERE ended_at IS NOT NULL` gives one row per run for all history.

### F20 fix: bind the remaining values in checker, tools, seed_rules (user asked, 2026-11-11)

* checker.check_proposal: proposal lookup is `WHERE proposal_id = :proposal_id`. checker._write_verdict binds run_id, verdict (column and both struct fields), model (None -> NULL), notes; step_seq inline as int().
* tools.stage_proposal binds proposal_id and run_id; tools.run_cost_model_scenario binds model_run_id.
* deploy/seed_rules.seed: existence check binds rule_id (version inline as int()); register and audit inserts bind rule_id, actor, audit_id (shared args dict, so both rows carry the same values).
* Scan: no `'{...}'` value interpolation left in orchestrator, evaluate, checker, tools or seed_rules SQL. The one remaining match (tools.py:41) is the not_found JSON string returned to Python, not SQL.
* Unchanged behaviour noted: F5 (checker step_seq 1, no proposal_id in the verdict row) and F6 (verdict 'error' outside verdict_enum) still hold; tests still pin them.
* Tests updated to the bound shape: test_stage_proposal_insert_shape, test_orchestrator_mock_run_b31_7, test_checker_ungrounded_fails_without_model (also checks the bound proposal lookup), test_checker_pass_path, test_checker_all_models_down, test_literals_checker_notes. Acceptance: session 42 ok; script 38 + 4 skip; pytest 42 passed; entrypoints 0 FAIL; test_gate pass; test_agents 35 ok.
* Live checks (SELECT only, nothing written): generated VALUES for checker_verdicts, proposals, model_runs, rule_register and its audit row, with hostile run_id / model / rule_id (apostrophe, trailing backslash), came back exactly. The bound proposal lookup against the real proposals table finds a real id (1 row) and returns 0 rows for `x' OR '1'='1`. Table counts unchanged (proposals 3, checker_verdicts 1, model_runs 1, rule_register 28).

### F3 + F7 fix: proposal lineage from the exception, no placeholders (user asked, 2026-11-11; answers Q5 as "fix")

* orchestrator._lineage(exception_id, exc) builds {exception_id, rule_id, rule_version, record_ids} from the exception (record_ids = its subject_ids) and lists what is missing. No defaults (F7): rule_id must be a non-blank string, rule_version an int (not bool, not "4"), subject_ids non-empty.
* run_exception refuses an exception with missing lineage, after the specialist lookup and before any model call or write, returning status error, `exception lacks lineage: <fields>` (same no-write pattern as not_found). agent_steps rows use the same lineage, so the old `rule_version 1` / `['unknown']` placeholders are gone.
* stage_proposal takes exception_id, rule_id, rule_version, record_ids (keyword, default None) and writes them to the existing proposals columns (F3), bound; record_ids `ARRAY(:rec0, ...)` or NULL; rule_version `CAST(:rule_version AS INT)`. The orchestrator injects them through TOOL_DISPATCH (`_lineage`), like run_id. The dispatcher drops any model-supplied run_id / exception_id / rule_id / rule_version / record_ids (invariant 6). The model-facing tool schema is unchanged.
* Tests: test_stage_proposal_insert_shape (was CHARACTERIZES F3) now requires the four columns and bound values, and NULLs (not placeholders) on a direct call without lineage; new test_stage_proposal_ignores_model_supplied_lineage; new test_orchestrator_refuses_exception_without_lineage (5 broken shapes plus a missing key: error, 0 model calls, 0 writes); test_orchestrator_mock_run_b31_7 checks the proposal carries exc-1 / CC-02 / 4 / exc-0. Acceptance: session 44 ok; script 40 + 4 skip; pytest 44 passed; entrypoints 0 FAIL; test_gate pass; test_agents 35 ok.
* Real-data checks (read-only): all 6 open exceptions, read through the real get_exception UC function, produce complete lineage (CC-02 v2/v3/v3/v4, CC-01 v1 x2), so the next harness run is not refused. Generated proposal VALUES run through real Spark give string / string / int / array<string>, matching the proposals column types; the no-lineage call gives NULLs.
* Existing data: the 3 proposals written before the fix keep NULL lineage (not repaired).
* NEW F21 (not fixed): checker.py docstring line 15 says the checker verifies the proposal's rule_id/rule_version match the exception; no code does that. It is now possible since proposals carry lineage.

### F21 fix: checker verifies the proposal's rule matches its exception (user asked, 2026-11-11)

* checker._rule_mismatch(prop): re-reads the exception through get_exception (bound, via CHECKER_DISPATCH) and returns a block reason when the proposal's (rule_id, rule_version) differ from the exception's, when the proposal has no lineage, or when the exception is not found; None when they match.
* check_proposal runs it as a structural check after the grounding check and before the model, with the same fail path: verdict fail, model None, verdict row written unless dry_run, notes = reason. Grounding failures still take priority. Docstring updated (a proposal without lineage fails).
* Behaviour change to know: proposals without lineage (the 3 written before F3) now fail if re-checked. New proposals carry lineage (F3), so the normal harness path is unaffected.
* Tests: proposal_handler now defaults to lineage matching EXC (exc-1 / CC-02 / 4); new test_checker_rule_match_f21 (wrong version, wrong rule, no lineage, partial lineage, exception not found: fail with 0 model calls and the reason in notes; matching lineage passes and re-reads exc-1 as a bound value; dry run writes nothing). Mutation (_rule_mismatch always None) is caught. Acceptance: session 45 ok; script 41 + 4 skip; pytest 45 passed; entrypoints 0 FAIL; test_gate pass; test_agents 35 ok.
* Real-data checks (read-only, real get_exception): an open exception's own lineage matches; version +1 is reported as a mismatch; id `x' OR '1'='1` is not found. Dry-run check of the 3 existing proposals: all fail on missing lineage, nothing written (checker_verdicts still 1).

### F5 + F6 fix: checker verdict rows (user asked, 2026-11-11; code only, no schema or constraint change)

* Options offered (add a proposal_id column / add 'error' to verdict_enum) were not answered, so I chose the code-only path: no ALTER on the live table. Adding a real proposal_id column remains possible later (additive DDL, needs approval).
* F5: _write_verdict computes step_seq as `coalesce(max(step_seq), 0) + 1` for the run_id (bound), so verdicts in one run are 1, 2, ... (read-then-write; harness_job checks proposals one at a time). The proposal_id is recorded as a `proposal` entry in checks (expected = actual = proposal_id, result 'recorded'), ahead of the existing `proposal_review` entry. The step_seq parameter was removed from _write_verdict (both callers updated).
* F6 (confirmed: the live table has `delta.constraints.verdict_enum = verdict IN ('pass','pass_with_exception','fail')`, so the old 'error' INSERT would have been rejected): when no checker model answers, check_proposal still returns verdict 'error', but the row stores 'fail' (blocks the proposal), proposal_review actual = 'error', notes = the model error.
* Tests: test_checker_pass_path (was CHARACTERIZES F5) requires the bound proposal entry; test_checker_all_models_down (was CHARACTERIZES F6) requires stored 'fail' / actual 'error'; new test_checker_step_seq_numbers_verdicts_per_run (no prior verdict -> 1, prior max 2 -> 3, run_id bound). Acceptance: session 46 ok; script 42 + 4 skip; pytest 46 passed; entrypoints 0 FAIL; test_gate pass; test_agents 35 ok.
* Live checks (reads real, INSERTs captured, nothing written): for the run that already has a verdict, the next step_seq is 2; a new run gets 1. Generated rows pass the verdict_enum expression (pass; error -> fail), proposal id with an apostrophe round-trips, and the checks array type equals the column type. checker_verdicts still 1 row.
* Reading proposal_id from verdicts: `filter(checks, c -> c.check_name = 'proposal')[0].actual`. The 1 existing row has no proposal entry.

### Harness run on F2/F3/F5/F6/F7/F20/F21 code (user asked, 2026-11-11)

* Run [817942932752909] of job 926377078634937 (task run 16017220589240): SUCCESS, 5.7 min. 6 open exceptions (the 5 earlier plus CC-02 v4 on test-wbs-001), 6 completed, 0 errors, 0 proposals.
* Table deltas: agent_runs 24 -> 30 (+6, exactly 1 row per run, F2 confirmed live; started_at <= ended_at, outcome completed, subject_id = the exception); agent_steps 52 -> 80 (+28 = 4+4+6+5+5+4); exceptions 6, proposals 3, checker_verdicts 1, model_runs 1 unchanged.
* Lineage (F7) live: all 28 new steps carry the exception's own rule_id, rule_version and subject_ids; 0 'unknown' placeholders. step_seq contiguous 1..n per run. All 28 output_json parse as JSON.
* Still 0 proposals: 9 of 28 steps returned blocked_no_source (data feeds not live), so the F3 proposal lineage and the F5/F6/F21 checker paths were not exercised live; they rest on the unit tests and the captured-insert checks above.
* Observation (pre-existing, not changed): agent_steps.output_json for read tools is a JSON string whose content is JSON (the tool returns a JSON string and orchestrator._clip json.dumps it again), so readers need to parse twice.

### F15 fix: dry run writes nothing (user asked, 2026-11-11; answers Q8 as "not intended")

* orchestrator.WRITE_TOOLS = {stage_proposal, run_cost_model_scenario}. With dry_run these are not called; the model gets `{"status": "dry_run", "tool": <name>, "note": "not executed: dry run writes nothing"}` and carries on. Read tools still run. The result dict gains `dry_run_proposals` (count of skipped stage_proposal calls) only when dry_run; `proposals` stays empty, so harness_job does not call the checker on proposals that do not exist.
* Scope note: run_cost_model_scenario (writes model_runs) is included because it is the same bug; F15 named only proposals.
* harness_job summary prints `Proposals not staged (dry run): N` under --dry-run (output only).
* Tests: test_orchestrator_dry_run (was CHARACTERIZES F15) now requires 0 INSERTs of any kind, the dry_run reply to the model, read tools still called, the same for run_cost_model_scenario on the cost_model specialist, and the write still happening without dry_run. Mutation (WRITE_TOOLS empty) is caught. Acceptance: session 46 ok; script 42 + 4 skip; pytest 46 passed; entrypoints 0 FAIL; test_gate pass; test_agents 35 ok.
* Real-read check (real get_exception on an open exception, INSERTs captured): dry run with a scripted stage_proposal completed, proposals [], dry_run_proposals 1, 0 INSERTs. Table counts unchanged (agent_runs 30, agent_steps 80, proposals 3, model_runs 1).

### agent_steps.output_json single-encoded (user asked, 2026-11-11)

* orchestrator._step_json(result) builds output_json: a read tool's JSON text is stored as is; any other value is json.dumps'd once; anything over MAX_STEP_JSON (2000, the old cap) is stored as `{"truncated": true, "chars": n, "preview": ...}`, so the column always holds valid JSON (the old `result_str[:2000]` could cut JSON mid-token). No row so far was near the cap (max 638 chars).
* Unchanged on purpose: what the model receives (`_clip(result)`, still double-encoded for read tools) and the step result_preview. Changing the model's input is a separate decision.
* Tests: new test_step_json_single_encoded (JSON text kept, dict/plain text encoded once, three over-long shapes give valid JSON <= 2000 with truncated true) and test_orchestrator_step_output_json_is_single_encoded (get_exception and stage_proposal steps parse once to objects; model content unchanged). Acceptance: session 48 ok; script 44 + 4 skip; pytest 48 passed; entrypoints 0 FAIL; test_gate pass; test_agents 35 ok.
* Real-read check (INSERTs captured): get_exception and get_rule steps for a real open exception parse to OBJECTs (`output_json:rule_id` = CC-02, status open / active); a real get_cost_capture blocked_no_source result is stored byte-for-byte. Counts unchanged (agent_runs 30, agent_steps 80).
* History (80 rows, left as is): 79 are a JSON string wrapping JSON. Reader for all rows: `CASE WHEN output_json LIKE '"%' THEN try_parse_json(parse_json(output_json)::string) ELSE try_parse_json(output_json) END`; it returns NULL for exactly the 26 pre-F18 lossy rows.
* NEW F22 (not fixed): a tool called with wrong arguments raises TypeError inside the model loop, which abandons that model attempt and falls through to the next model, instead of returning a tool error to the model. Seen in the real-read check with a scripted bad argument: outcome `completed: databricks-claude-opus-5: TypeError: get_cost_capture() got an unexpected keyword argument ...`.

### F22 fix: bad tool arguments go back to the model (user asked, 2026-11-11)

* tools.argument_error(name, args, schemas=TOOL_SCHEMAS) checks a model's arguments against the tool's JSON schema before the call: non-object arguments, missing required, unknown keys (orchestrator-injected keys are ignored, since the dispatcher drops them). Returns a message such as `bad arguments for get_rule: missing ['rule_id']; expected ['rule_id', 'version']`, or None.
* orchestrator and checker loops call it before dispatch; on a bad call the tool result is `{"error": <message>}`, the step is recorded (ok false), and the same model continues. Before, the TypeError abandoned the model attempt and fell through to the fallback model, and the run outcome carried the error text. Runtime errors inside a tool still behave as before.
* Found while checking schemas against signatures: get_cip_transactions required cost_element in Python, while its schema and UC function treat it as optional (NULL = all), so a model that left it out raised TypeError. It now defaults to None; period_start/period_end are still required (explicit check), and the positional call order is unchanged.
* Tests: new test_argument_error, test_tool_schemas_match_signatures (every schema property is a parameter; every parameter without a default is schema-required; cost_element can be omitted), test_orchestrator_bad_tool_args_returned_to_model (one model only, tool not called, error stored in the step, outcome `completed`), test_checker_bad_tool_args_returned_to_model. Mutation (argument_error always None) is caught in both loops. Acceptance: session 52 ok; script 48 + 4 skip; pytest 52 passed; entrypoints 0 FAIL; test_gate pass; test_agents 35 ok.
* Real-read check (INSERTs captured): the F22 scenario on a real open exception now completes on databricks-claude-opus-5 with error None and outcome `completed`; the bad call's step holds the bad-arguments error. A real get_cip_transactions call without cost_element returns blocked_no_source. Counts unchanged (agent_runs 30, agent_steps 80).

### Q9 resolved: older CC-02 exceptions marked superseded (user asked, 2026-11-11; data change, not code)

* One UPDATE on aircarrier_app_exceptions, values bound: `SET status = 'superseded' WHERE exception_id IN (60d8a71c-... CC-02 v2, 6c859295-... CC-02 v3) AND rule_id = 'CC-02' AND status = 'open' AND array_contains(subject_ids, 'test-wbs-001')`. 2 rows affected. Table version 9 -> 10 (pre-change state: `VERSION AS OF 9`).
* Table allows it: no delta.appendOnly property and no status constraint; 'superseded' is a documented status in harness_ddl.sql (`open | resolved | superseded`).
* Verified by diffing version 9 against 10: only those 2 rows changed, only the status column, open -> superseded; row count 6 both versions.
* Left open: CC-02 v4 on test-wbs-001 (the current one), CC-02 v3 on test-wbs-002 (different subject, still the only CC-02 for it), CC-01 v1 on test-wbs-001 and test-wbs-002. Open exceptions now 4, so the next harness run processes 4.
* Not recorded anywhere else: there is no exception audit table; the Delta history (version 10, UPDATE) is the only record of who changed it and when.

### F4 fix: model run inputs stored (user asked, 2026-11-11)

* Cause: the tool schema took inputs_vintage and assumptions as strings, but the model_runs columns are MAP<STRING,TIMESTAMP>, MAP<STRING,INT> and ARRAY<STRING>, so the code wrote NULL. CM-02 (stale inputs) reads inputs_vintage, so it could never fire.
* run_cost_model_scenario now stores, in the column types:
  * inputs_vintage: feed -> timestamp, from a dict or a JSON-object string. Only extended ISO-8601 is accepted (Python's fromisoformat also takes 20260930 and 2026-W40-1, which Spark's CAST rejects and which would fail the INSERT). Anything else is left out and listed in warnings.
  * rule_version: {rule_id: version} of the exception's rule, injected by the orchestrator (same lineage as F3). If the model's rule_version differs, the exception's is stored and a warning says so. A model-supplied rule_id is dropped. Without lineage (direct call) it is NULL.
  * assumptions: a list, or one string as a one-item list.
  * input_record_ids (was always NULL): the exception's record_ids. warnings (was always NULL): the list above, or NULL.
  * Every value bound. The result now also returns warnings.
* Tool schema (model-facing): inputs_vintage is now an object of feed -> ISO timestamp, assumptions an array of strings; rule_version unchanged. The prompt files are unchanged (no SHA16 changes).
* Tests: test_run_cost_model_scenario_placeholder (was CHARACTERIZES F4) now requires all five columns; new test_run_cost_model_scenario_bad_inputs_become_warnings (legacy strings, bad and basic-format timestamps, version mismatch, forged rule_id, empty lists -> NULL) and test_orchestrator_injects_lineage_into_cost_model. Acceptance: session 54 ok; script 50 + 4 skip; pytest 54 passed; entrypoints 0 FAIL; test_gate pass; test_agents 35 ok.
* Live check on a scratch copy of model_runs (created and dropped): the real INSERT stores {IPMDAR: 2026-01-15, CCDR: 2026-11-01}, {CM-02: 1}, [learning curve 0.95, o'b], [mr-1], warnings NULL; the legacy-string call stores NULL vintage plus the warning. CM-02's own expression run on the scratch table flags exactly the IPMDAR feed (over 60 days). Every format the code accepts was CAST in Spark without error. Real model_runs unchanged (1 row).
* Existing model_runs row (1, NULL inputs) left as is.
