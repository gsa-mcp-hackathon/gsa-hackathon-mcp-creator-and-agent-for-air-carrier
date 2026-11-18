# Air Carrier work queue v2: from a rule-output viewer to a decision queue

Status: design, 2026-11-11. Not built. Extends ORCHESTRATION_V2.md (Part C, /work) and API_SPEC.md section 4 (new gaps A-27 to A-36).
Case studied: exception 5657e0c5-aed8-4c10-8297-34fa23c06fda (CC-02 v4, test-wbs-001, $6,000,000.00, void_test_data).
All counts below were read from the live `users.xiaobing_shang1_civ.aircarrier_app_*` tables on 2026-11-11 unless marked otherwise.

## 1. Purpose

The work queue exists to answer one question for one person:

> What must I decide, by when, and is the evidence good enough for me to sign?

An item belongs on the queue only if a named authority can act on it today, with a figure that traces to source records.
Everything else the system knows (missing feeds, rule defects, test data, agent failures) is real and must be shown, but
it is not a decision, and it must not look like one.

The page fails its purpose in two ways, both of which are worse than an empty page:

* It shows a non-actionable item as actionable, and a financial manager acts on it (or learns to ignore the page).
* It shows nothing, and the reason (four missing feeds) stays invisible to the people who can get them.

## 2. Audience

| Audience | What they need from this page | What they must never see |
| --- | --- | --- |
| PMS 379 / PEO Carriers financial managers (record owners, the deciders) | Items they own, a deadline, a backed figure, a checked proposal, Apply / Reject / Escalate | Test data, unbacked dollars, internal error tokens |
| NAVY_FMO / OUSD(C) FMO (higher authority) | Items escalated to them, with the history of the level below | Items they have no authority over |
| DCFO sponsor (brief 18-21 Nov) | One line: decisions due, backed vs unbacked dollars, top blockers and who owns them | Row-level detail |
| Data owners (DCMA/contractor for IPMDAR, CAPE for CCDR, DFAS for ledger, PMS 379 for CLIN funding) | A specific request: which feed, why, what it unlocks | Rule internals |
| Auditors / CAPE (reviewers) | Who decided what, on which evidence, under which rule version | Nothing hidden; read-only |
| Builder / admin | Rule defects, agent failures, data integrity breaks | (sees everything) |

Today only the builder is served. The case card is readable as a debugging trace and misleading as anything else.

## 3. Diagnosis: what the case card shows, and why it is wrong

Verified facts (live tables, 2026-11-11):

* Exceptions: 6 rows. 2 superseded, 4 void_test_data, 0 open. Their dollar_amount sums to $30,000,000.00. The seed behind them is two test WBS elements ($6,000,000.00 and $3,000,000.00, $9,000,000.00 total). Summing the table overstates the seed by more than 3x.
* The parent of the case exists: CC-01 v1 exception a0316eb8-dc9b-4cbc-a50b-6ef0119a8358, test-wbs-001, $6,000,000.00, detected 2026-09-22 (50 days before 2026-11-11, so CC-02's 45-day test was correctly met). The CC-02 card never names it.
* CC-01 v1 is in aircarrier_app_rule_register with status blocked_no_source. aircarrier_tool_get_rule with version NULL filtered status = 'active' (the same set as aircarrier_app_current_rules: AV-06, CAP-05, CC-02 v4, CM-01 v3, CM-02 v2), so the agent's get_rule(CC-01, NULL) returned not_found. The agent reported the rule as missing. It is blocked, not missing.
* CC-02 has versions 1 to 4 in the register, all with status active. Each new version re-raised the same subject, which produced the superseded rows.
* window_closes_at is NULL on all 6 exceptions.
* The case row was inserted open at 2026-11-11 03:28:02 (Delta version 9) and set to void_test_data at 15:40:34 (version 11). Both agent runs on it (9cb75c3b ended 04:06:38, 16bf9ac3 ended 15:32:56) finished before the void. The agents worked an open item; the waste came from the missing pre-check (D13), not from running after the void.
* agent_runs: 34 rows, 22 distinct run_ids (duplicates persist, see ORCHESTRATION_V2 Part B).
* proposals: 3, all pending, all with exception_id NULL. decisions: 0. metrics: 0.
* Rule register: 22 rule ids. 5 active, 14 blocked_no_source, 3 blocked_param_unset.

Defects on the card, by layer:

| # | Layer | Defect | Effect on the reader |
| --- | --- | --- | --- |
| D1 | Card | Headline is "$6,000,000.00 / Escalation to next authority"; status void_test_data sits in small print | Reader sees a $6M escalation |
| D2 | Card | The figure is printed to the cent although nothing backs it (parent rule blocked, feeds missing) | False precision on a non-figure |
| D3 | Card | "Rule CC-02 v4 / 1 record: test-wbs-001" repeated on every block | Noise; hides the content |
| D4 | Card | Evidence steps show only status tokens (open, active, error not_found, blocked_no_source) | Reader cannot tell what was checked |
| D5 | Card | The finding is truncated ("shortened when stored") and the cut part is the conclusion | The one useful output is lost |
| D6 | Card | "Not checked" because no proposal was staged (A-21) | A cannot-resolve claim goes unverified, and in this case it was partly wrong (D9) |
| D7 | Rule | CC-02 is an exception about an exception and re-asserts the parent's dollar_amount | Double counting; $30M of rows for $9M of seed |
| D8 | Rule | CC-02 subject_ids is the WBS element, not the parent exception_id | The 45-day test cannot be verified from the card |
| D9 | Data | current_rules hides non-active rules; the tool reports them as not_found | Agent misdiagnoses blocked as missing |
| D10 | Rule | Escalation rule sets no window | An escalation with no deadline |
| D11 | Rule | Several versions of one rule active at once | Re-detection on every version |
| D12 | Engine | A derived rule (CC-02) evaluates while its parent rule is blocked_no_source | Derived items exist with no live basis |
| D13 | Agent | The run started with no pre-check of status, parent state or feeds | A full run spent to learn what three reads would show |

## 4. Design

### 4.1 Three lanes

The single list becomes three lanes, each with its own audience and its own verb.

| Lane | Admits | Audience | Verb |
| --- | --- | --- | --- |
| Decide | Items that pass the admission gate (4.2) | Record owner by authority matrix | Apply, reject, escalate |
| Unblock | Missing feeds, access, unset parameters, gaps G1-G28; grouped by root cause, not by rule | Program lead, data owner | Send the drafted request; record the response |
| System | Test data, rule defects, integrity breaks, agent failures | Builder / admin only (hidden from other roles by role_map) | Fix, void, supersede |

An Unblock item is one row per root cause. Today that is one row: "IPMDAR, CCDR, GL recorded cost and CLIN funding authority are not ingested; this blocks CC-01, CC-03, CC-04" (and the EV, AV and CAP rules with the same status), with the owner of each feed and a drafted request.

### 4.2 Admission gate (deterministic, server-side)

Run by code at detection time and again at read time. An item is in Decide only if every check passes. A failure routes it to the named lane and the reason is stored.

| Gate | Check | On failure |
| --- | --- | --- |
| G-a Not test | No subject matches the test pattern (test-wbs-*) and status is not void_test_data | System |
| G-b Rule live | The rule version is the single active version of its rule | System |
| G-c Parent live | For a derived rule, the parent rule is active and the parent exception is open and named in subject_ids | Unblock (parent blocked) or System (parent absent) |
| G-d Figure backed | Every dollar figure has a provenance_id whose records resolve to source rows, and the source layer (A-20) is recorded | Unblock |
| G-e Owner | owner_role resolves in the authority matrix to at least one person | System |
| G-f Window | window_closes_at is set | System |
| G-g Not duplicate | No other open item in Decide counts the same dollars for the same subject | System |

The case card fails G-a, G-c (parent blocked), G-d and G-f. It belongs in System, and its root cause belongs in Unblock.

### 4.3 The card

Top to bottom:

1. **Answer line**, one sentence, generated from the lane and gate result, not by the model. Examples:
   * "No action. Test data, voided 2026-11-11."
   * "Blocked. CC-01 cannot run until IPMDAR and GL recorded cost are ingested. Request drafted to DCMA and DFAS."
   * "Decide by 2026-12-02. Approve a $X reclassification. 3 of 3 sources tie out; checker SUPPORTED."
2. **Status and backing**, before any dollar figure. An unbacked figure renders as "not established" with the reason; it is never printed to the cent.
3. **Decision**, when in Decide: proposal rows (GOES TO / PROPOSED / WHY / RULE) and Apply / Reject / Escalate under the caller's authority.
4. **Evidence**: one line per step, as tool, arguments, one-line result, timestamp (needs A-19). Rule and subject are shown once in the card header, not per step.
5. **Trail** (collapsed): every run, verdict, attempt and decision.

### 4.4 Agent process

1. **Pre-check (code, no model).** Read status, gate result, parent state and feed availability. If the item is not in Decide, do not start a model run. Write the gate result as the run outcome.
2. **Record pack (code).** Pack only the records the task needs: the exception, its parent chain, the rule version and the source rows behind each figure. The model does not choose its own context.
3. **Specialist run.** One specialist, the existing tool allowlist, MAX_STEPS 8.
4. **Fixed outcomes**, stored as structured fields, not free text:
   * `proposal_staged` (proposal ids)
   * `cannot_resolve_blocked` (blocker ids, each a feed, parameter or parent rule)
   * `rule_defect` (rule id, version, defect)
   * `data_defect` (table, key, defect)
   The prose explanation is stored in full; display may shorten it, storage may not.
5. **Check every outcome.** The model checker reviews findings as well as proposals (A-21). A deterministic re-check confirms each blocker claim against the tool results and the register (for example, it would have rejected "CC-01 not found" because the register holds CC-01 v1 as blocked_no_source).
6. **Turn blocked into a request.** A `cannot_resolve_blocked` outcome attaches to the Unblock item for its root cause and drafts (or updates) the collection request to the feed owner. It does not create a new item.
7. **One run row per run.** Write agent_runs once per run_id (fix the duplicates); link every proposal to its exception and to an existing run.

### 4.5 Rule and engine changes

* CC-02 stops raising exceptions. Escalation becomes a field on the parent: `escalation_level` and `escalated_at`, set when the parent passes 45 days open. The parent's owner moves up the authority matrix. Dollars are counted once.
* Until that change ships, CC-02 subject_ids carries the parent exception_id, and dollar_amount is displayed as "inherited from <parent>" and excluded from every total.
* A derived rule does not evaluate while its parent rule is not active.
* Activating a new rule version retires the previous one (one active version per rule id).
* Every rule sets a window; for CC-02 it is the 45 days.
* get_rule returns the register row with its status for any version; not_found means absent from the register.

## 5. What is presented

### 5.1 The work queue page today, under this design

| Lane | Count | Content |
| --- | --- | --- |
| Decide | 0 | "Nothing needs your decision. 0 backed items are open." This is the correct result. |
| Unblock | 1 | Missing feeds IPMDAR, CCDR, GL recorded cost, CLIN funding authority. Blocks the cost capture rules CC-01, CC-03, CC-04, among the 14 blocked_no_source rules. Owners and drafted requests attached. Plus 3 rules waiting on a parameter (blocked_param_unset). |
| System | 4 groups | 4 void test exceptions and 2 superseded (6 rows, $30M of row totals for $9M of seed); CC-02 versions 1-4 all active; current_rules hides blocked rules from the agent; agent_runs duplicates (34 rows / 22 runs) and 3 pending proposals with no exception |

Next to it, a short "what is verified" strip: the promoted claims in the claim ledger that tie out to source (13 as of 2026-11-11, from the project log, not re-queried here).

### 5.2 The sponsor line (DCFO, weekly and at the brief)

> Decisions due this week: N. Backed dollars in decision: $X. Dollars waiting on data: not established until the feeds arrive. Top blocker: IPMDAR / GL recorded cost, owner <office>, requested <date>.

The brief asks for named access. The Unblock lane is the evidence for that ask: each blocked rule, each missing feed and each owner, on one page.

## 6. Acceptance tests

Each test runs against scratch tables (aircarrier_apptest_*) and must pass before release.

| Id | Test | Pass condition |
| --- | --- | --- |
| T1 | Seed a void_test_data exception | It never appears in Decide or Unblock for a non-admin principal |
| T2 | Seed a CC-02 exception whose parent rule is blocked_no_source | Routed to Unblock with reason G-c; no model run started |
| T3 | Render an unbacked figure | Card shows "not established" and no digits for that figure |
| T4 | Sum dollars across Decide | A derived item's inherited dollars are excluded; total equals the sum over distinct parent subjects |
| T5 | Agent finding text over the display limit | Stored in full; the stored length equals the generated length |
| T6 | Agent claims a rule is not found when the register holds it as blocked | Deterministic re-check returns fail and names the register row |
| T7 | Two runs blocked on the same feed | One Unblock item, two linked runs, one drafted request |
| T8 | Activate CC-02 v5 | v4 is retired; existing subjects are not re-raised |
| T9 | Any exception written with window_closes_at NULL | Gate G-f routes it to System |
| T10 | Answer line | Generated by code from lane and gate result; identical across two renders of the same state |

## 7. New gaps (continue API_SPEC section 4)

| Id | Gap | Evidence | Blocks |
| --- | --- | --- | --- |
| A-27 | No admission gate or lane field on exceptions | exceptions DDL | 4.1, 4.2 |
| A-28 | CC-02 re-asserts the parent dollar_amount and names the WBS element, not the parent exception | live exceptions; rule expression_sql | totals, 45-day verification |
| A-29 | Derived rules evaluate while the parent rule is blocked | CC-02 rows exist while CC-01 v1 is blocked_no_source | G-c |
| A-30 | Several active versions per rule id | CC-02 v1-v4 all active in rule_register | re-detection, superseded churn |
| A-31 | window_closes_at NULL on all exceptions | live exceptions (6 of 6) | G-f, deadlines |
| A-32 | get_rule(version NULL) filters status = active and returns not_found for rules that exist but are blocked | deploy/harness_tools.sql get_rule WHERE clause; live get_rule('CC-01', NULL) = not_found while CC-01 v1 is blocked_no_source | agent diagnosis |
| A-33 | Agent finding is truncated in storage | orchestrator._write_finding stored text[:1900] with a truncated flag; case card shows "shortened when stored" | the finding |
| A-34 | No pre-check before a model run | orchestrator.run_exception refuses only on exception not_found, unknown area or missing lineage; it does not read status, parent state or feeds | wasted runs |
| A-35 | No structured outcome taxonomy for findings | finding row output_json is {kind, text, truncated} only | lanes, checker of findings |
| A-36 | No Unblock store linking blockers to rules, runs and collection requests | grep of deploy/*.sql for blocker, unblock, collection_request: no match | Unblock lane, sponsor line |

Status 2026-11-11:

| Id | Status | Where |
| --- | --- | --- |
| A-32 | Live function replaced 2026-11-11 (user confirmed). CREATE OR REPLACE dropped the agent SP's EXECUTE grant (7e1ec6c0); it was restored the same day from the get_rule line of deploy/grants_harness_agent.sql (user confirmed), and SHOW GRANTS now matches the pre-change set. Any future replace of a tool function must re-run its grant line. The first body was rejected by Spark (a UDF parameter may not appear in a subquery's SELECT list or ORDER BY), so the function is now three WHERE-only subqueries. Live checks after the replace: 22 of 22 ids resolve; live output equals the tested body for every id; all 28 explicit versions match the old function apart from the added resolved_as. version NULL now returns the active version, else the latest version with its status, resolved_as (current_active / no_active_version / requested_version) and a note; not_found only when the register has no row. Tool description tells the model what each case means. Verified read-only against the live register by running the new body as a query: 22 of 22 rule ids resolve (none not_found); CC-01 returns v1 blocked_no_source; CAP-01 returns v1 blocked_param_unset; ZZ-99 and CC-01 v7 still not_found; the 5 active rules return the same version as current_rules and as the old function | deploy/harness_tools.sql, ops/harness/tools.py |
| A-33 | Resolved in code, takes effect on the next harness run (no redeploy of the app needed for new rows). The finding is stored whole as {kind, text, truncated: false, chars}. Rows written before this keep their clipped text and still show "(shortened when stored)". test_harness 55 ok / 0 failed / 4 skipped; test_work 56 passed (fresh /tmp copy) | ops/harness/orchestrator.py, checks/test_harness.py |
| A-28 (parent link) | Done. CC-02 v5 inserted live 2026-11-11 (user confirmed): register 28 -> 29 rows, one audit row (actor a28_parent_link), current_rules and get_rule(CC-02, NULL) both return v5, params identical to v4. A dry-run evaluate of CC-02 v5 returned 0 hits (no open CC-01 items) and wrote nothing (exceptions 6 -> 6, rule_evals 7 -> 7). Root cause: evaluate._extract_subject_ids took subject_ids before exception_id, and CC-02 v1-v4 selected both, so the parent's WBS was copied and the parent id dropped. Fix: a parent_exception_id column wins over every other and sets subject_type 'exception' (evaluate.py, mirrored in app/api/harness.py preview); CC-02 v5 in deploy/rule_cc02_v5.sql returns e.exception_id AS parent_exception_id; get_exception's tool description tells the agent to read the parent. Read-only check against exceptions VERSION AS OF 10 (before the void): v5 yields [a0316eb8...] with subject_type exception, v4 yields [test-wbs-001]. Tests: test_harness 57 ok / 0 failed / 4 skipped (2 new), test_work 56 passed, test_app all checks pass. Second half done 2026-11-11 (user asked): CC-02 v6 (deploy/rule_cc02_v6.sql) returns only parent_exception_id, so evaluate writes dollar_amount NULL and the amount is counted once, on the parent. Inserted live: register 29 -> 30, current_rules and get_rule(CC-02, NULL) = v6, v5 retire event written, re-run inserts 0. Pre-void read-only check: v6 yields parent a0316eb8 with no dollar. Dry-run evaluate of v6: 0 hits, nothing written. The card states where the amount is (Escalation of exception <id>; not counted again), in app/api/harness.py; deployed 2026-11-11 in app deployment 01f1ddfcf630122bb67493337ce04623. Existing rows keep their stored amounts (all 6 are closed, so no open total includes them). Note: superseded_by names the version now in effect (CC-02 v1-v5 all read superseded_by 6), not the immediate successor. test_harness 59 ok / 4 skipped, test_work 57 passed, test_app all pass | ops/harness/evaluate.py, app/api/harness.py, ops/harness/tools.py, deploy/rule_cc02_v5.sql, checks/test_harness.py |
| A-30 (CC-02) | Done for CC-02, 2026-11-11 (user asked). The register is insert-only, so there was no UPDATE. Instead: (1) 4 'retire' audit events for CC-02 v1-v4, actor a30_retire (deploy/rule_cc02_retire_v1_v4.sql, idempotent; re-run inserted 0; register still 29 rows); (2) the real state is derived wherever versions are read: get_rule with an explicit version now returns lifecycle and superseded_by (live: CC-02 v4 -> superseded by 5), and the app rule card SQL returns the same two columns. get_rule replaced with its grant re-run in the same step; SP 7e1ec6c0 EXECUTE confirmed. All 29 explicit versions and all NULL-version lookups match the previous function apart from the two new keys. Also fixed: the rule card audit query read a column named at (it is event_at) and always errored. App changes (harness_sql.rule_detail, rule_audit, _rule_view) deployed 2026-11-11 in app deployment 01f1ddfa944b15698bb777068f67cf3f (snapshot identical to source). Not done: CM-01 v1-v2 and CM-02 v1 are also stored active and now read as superseded, but have no retire events; no insert path writes a retire event for the prior version automatically | deploy/rule_cc02_retire_v1_v4.sql, deploy/harness_tools.sql, ops/harness/tools.py, app/api/harness_sql.py, app/api/harness.py, checks |
| A-29 | Done 2026-11-11 (user asked). evaluate() checks every rule with params.source_rule: the source, and its own source in turn, must have a version in current_rules. If not, the rule is not run and gets status skipped_parent_inactive with rows 0 and a reason naming the source's latest version, status and blocked_reason. The skip is recorded in rule_evals, and a loop in the chain is also caught. The same gate turns the app rule preview into a 409 before any SQL runs (app/api/harness.py _parent_gate, mirrored). Live dry run: CM-01 v3 ok, CM-02 v2 ok, CC-02 v6 skipped (CC-01 v1 blocked_no_source: Requires IPMDAR, CCDR, and GL/ledger recorded cost feeds). Exceptions and rule_evals counts did not change. The eval job picks it up on its next run; the preview gate deployed 2026-11-11 in app deployment 01f1ddfdebe31a0fac13f892ff68cc53. test_harness 60 ok / 4 skipped, test_work 58 passed, test_app all pass | ops/harness/evaluate.py, app/api/harness.py, app/api/harness_sql.py, checks |
| A-31 | Mechanism done 2026-11-11 (user asked); no values set yet. A rule param window_days (whole days above 0) gives window_closes_at = detected_at + N in evaluate(), dry-run hits included. It is not passed to the detection SQL (also stripped in the app preview bind). Unset gives NULL, so G-f routes the item to System; a bad value fails the rule before it runs. Live dry run with CM-02 + window_days 30 ran clean and wrote nothing (exceptions 6, rule_evals 7). OPEN: which rules get which window is a policy decision for the rule owners. The one sourced figure is CC-02's 45 escalation days, which would apply to CC-01 items. No current rule has window_days, so new exceptions still get NULL until a version with it is inserted. The 6 existing rows are closed and were not backfilled. test_harness 61 ok / 4 skipped, test_work 58 passed, test_app all pass | ops/harness/evaluate.py, app/api/harness_sql.py, checks/test_harness.py |
| A-34 | Started 2026-11-11 (user asked). ops/harness/precheck.py is code only, no model. It checks: open status; G-a not test (test-wbs-* or void_test_data); G-b the rule version is the one in effect; G-c the parent rule chain is live (the same gate as evaluate, A-29) and, for subject_type exception, the parent exception exists and is open. G-f (window) is reported but not blocking until rules set window_days (A-31). The first failing check sets the lane (System or Unblock). run_exception runs it before any model call. If the item is refused there is no model call and no agent_steps, and one agent_runs row is written with outcome 'precheck_blocked: <lane>: <reasons>' (none on a dry run). precheck=False bypasses it for a deliberate run. harness_job prints a 'Not run (pre-check)' count. Live, read-only: all 6 exceptions are refused, lane System, with the expected reasons. A dry run of run_exception on 5657e0c5 returned precheck_blocked without calling the model, and agent_runs stayed at 35. G-e added 2026-11-11 (user asked): owner_role must be set, hold apply on proposals in authority, and have a role_map row in effect (a person or an account group; group membership is not expanded). It reads the same tables as the app's authority_check. If the tables cannot be read, G-e fails, lane System; it does not admit. Live: PMS379 resolves (1 assignee), so all 6 exceptions pass G-e. NAVY_FMO and OUSD_C_FMO hold apply but have no role_map assignment, so any item from AV-* or CAP-* would be refused today. Not yet: G-d (figure backed), the feed-availability read, and showing the pre-check on the card. test_harness 64 ok / 4 skipped, test_work 58 passed, test_app all pass | ops/harness/precheck.py, ops/harness/orchestrator.py, ops/entrypoints/harness_job.py, checks/test_harness.py |
| A-35, A-36 | Open | |

Live re-run 2026-11-11, run 027b815a on 5657e0c5 (user asked), compared with run 16bf9ac3:

* A-32 confirmed. Step 3 get_rule(CC-01) returned v1 with status blocked_no_source and resolved_as no_active_version (old run: not_found). The finding now says CC-01 "exists in the register but has no active version".
* A-33 confirmed. Finding stored with truncated=false and 3,895 chars, equal to the text length (old run: truncated=true at 1,900).
* New evidence for A-21 and A-28. Two claims in the finding are wrong. (1) It tests the 45 days and the open status against the CC-02 row itself. The rule tests the parent CC-01 row, a0316eb8, which was open at CC-02 detection and 50 days old (detected_at 2026-09-22, voided only at 15:40:34). (2) It therefore accuses evaluation 7976ee53 of not enforcing status_filter and escalation_days, but the evaluation behaved as written. The cause is that subject_ids names the WBS element rather than the parent exception (A-28), so the agent could not find the parent. No checker reads findings (A-21), so the false accusation reached the card unchallenged.

## 8. Build order

1. A-32 and A-33 (small, and they corrupt agent output today).
2. A-27 gate and lanes, read-side only, computed in harness_sql; T1-T3, T9, T10.
3. A-34 pre-check and A-35 outcomes in the orchestrator; extend the checker to findings (A-21); T5, T6.
4. A-36 Unblock store and drafted requests; T7. Produces the sponsor line.
5. A-28 to A-31 rule and engine changes; T4, T8.
