# Air Carrier orchestration v2: lessons from the CORAS CFO Mission Module demo

Status: design, 2026-11-11. Evidence: `/Volumes/users/xiaobing_shang1_civ/aircarrier_artifacts/_video_cfo_mission_module/`
(107 frames, frame_descriptions.json, frame_timeline.json, section_synthesis.json, narration_transcript.txt).
Frame text was read by a vision model; numbers in the demo are notional and some OCR is unreliable
(sidebar badge counts change from frame to frame; the new BX-01 value read as "1" is uncertain).

## Part A. What the demo is built from (reverse-engineered)

### A1. Four layers

| Layer | What the demo shows | Evidence (verbatim) |
| --- | --- | --- |
| Records | 9 "CFO lists". The demo never lists all 9. The lists named on screen are Audit Findings, Corrective Action Plans, Organization Milestones, Congressional Budget Actions, Appropriation Status, Financial Cases, Compliance Checks and Thresholds and AI Action Runs; Taskers appears as a proposal target. Every figure is computed from the lists. | "Records: read from 9 of 9 CFO lists at 13:59:57." / "As of 05 OCT 26; computed from the records below." |
| Rules | A rule register, stored as data and owned by people. Each rule has a family, an ID, plain text and one parameter. Families: CP (plan standard), RK (risk and allocation), BX (budget execution), CG/CC (Congress), EC (evidence discipline), IC (controls), WC (working capital), SY (systems). | "These are your business rules, not software code." Toast: "Rule updated. Every result has been recomputed. Saved to the CORAS list." |
| SI team | One orchestrator ("Gary") plus one specialist per task plus a Records Checker. | "Gary, our orchestrator, hands this to the congressional affairs analyst, then the records checker reads the answer against the same records. Each agent has one job." |
| Decision | A review-and-decide modal, authority by acting role and record owner, and a receipt for every write. | "The SI team proposes. You choose what is applied, acting as Comptroller / CFO." / "The Army owns this plan and applies changes to it." |

### A2. The agent roster

| Agent | Kind | Evidenced job | Runs |
| --- | --- | --- | --- |
| Gary | ORCHESTRATOR | "Reads the request, picks the specialist, packs only the records the task needs and returns proposals" | all |
| Congressional Affairs Analyst | SPECIALIST | marks, CR holds, reports owed (CG-01..03) | RUN-001 |
| Budget Execution Analyst | SPECIALIST | benchmark gaps, reprogramming threshold (BX-01, BX-02) | RUN-002, RUN-003 |
| Action Plan Reviewer | SPECIALIST | tests a plan against CP-01..05 and drafts the smallest changes | RUN-004 |
| Audit Findings Analyst | SPECIALIST | reads a document and proposes records | RUN-005 |
| Records Checker | CHECKER | "Checked each amount and date against ..." (EC-02) | every run |
| Other roster cards | SPECIALIST | findings across Components, risk trade-offs, milestone tracker. Their guardrails read "Never close..." and "Never issues a tasker or brief." | none shown |

Each specialist card carries rule-book chips (for example "Action Plan Standard" and "Evidence and Citation Discipline"). Each answer is stamped "Answered as CFO <Specialist> on bedrock/charlie with 2 skills sent", so the system tracks the prompt, the model and the skills behind every answer.

### A3. The run pipeline (the same 6 stages every time)

1. Trigger. Runs start from the page, not from a blank chat. A row has "Explain" or "Screen and draft", a card has "Show me", a page has "Read the marks..." or "sweep the balances", and the ask bar offers 5 suggested chips.
2. Route and pack. Gary picks one specialist and packs the minimum record set: "Routed to the Budget Execution Analyst with 15 appropriation lines" or "with the plan, its 2 milestones and 1 dependency."
3. Specialist steps. Each step is one line with a rule chip, for example "Tested the amount against the threshold: $58M against $15M. BX-02."
4. Two checks:
   * Model checker: "CFO Records Checker ... SUPPORTED. Every stated fact matches a record." It can also return "SUPPORTED WITH NOTES."
   * Deterministic re-check: "Record check by the canvas. Pass. Five conditions re-tested; results match. No date was invented: proposed dates are spaced evenly..."
5. Proposals. Each proposal is a row with GOES TO, PROPOSED, WHY and RULE. Where the record is silent the draft keeps a marked blank and names who fills it (EC-03). "FLAGS FOR A PERSON" carries a severity.
6. Decide and write. Rows are ticked, authority is checked server-side, and a refusal names the owner ("Continue as Army financial manager"). The receipt reads "2 of 2 proposals applied by Army financial manager". After a write, the headline recomputes (78% -> 87%).

Around every run:
* EC-01: "Nothing is saved until a person applies it."
* The run log records RUN, TIME, TASK, ASKED BY, AGENTS, SI ANSWER and PROPOSALS ("11 of 11 applied").
* The activity log records every person's action and every SI action.
* Every run is kept in the "AI Action Runs" list.

### A4. The design moves that matter

* Every page leads with one question, and the headline is a date-bound outcome, not a count: "78% of material dollars have a plan that can still finish in time for the FY 2028 opinion."
* AI is placed on the row where the problem is, and its scope is already bound (one record, one rule).
* A specialist does one job and a run uses one specialist, which makes failures easy to localise.
* Records are packed by code, not chosen by the model.
* Two checkers with different methods. The model checker compares the answer with the records; the canvas re-computes from the records. They can disagree, and both verdicts are shown.
* Rules are data with one parameter each. A change recomputes everything and is logged, and the page shows the consequence ("three more lines now need an explanation").
* Authority is a property of the record owner, not of the AI. The refusal is a designed state, not an error.
* Document intake is "review exceptions instead of typing." Three outcomes are shown per row: ready / already in the list / value the list doesn't allow (stopped).
* The "How it works" coach marks and the per-page Help turn the screen into training.

## Part B. Where Air Carrier stands (verified 2026-11-11)

| Demo element | Air Carrier today | Gap |
| --- | --- | --- |
| Records + provenance line | aircarrier_src_*, pdf store, KG, claim ledger; Figure envelopes carry provenance_id (A-13) | No "read N of N sources at T" line on each page |
| Rule register | aircarrier_app_rule_register, current_rules (5 rows), GET /rules, POST /rules/{id}/preview | POST /rules/{id}/versions is not built, and nothing recomputes the pages after a rule change |
| Orchestrator | ops/harness/orchestrator.run_exception: one run per exception, specialist chosen by `area`, tool allowlist, MAX_STEPS 8 | No page/trigger router, no record packer (the model gathers its own context through tools) |
| Specialists | cost_capture, evm, cost_cap, valuation, cost_model (prompts/*.md) | None is mapped to the questions the sponsor's pages ask (reconcile, attribute, close gap, read document) |
| Checker | checker.check_proposal (model) | FIXED 2026-11-11: run_exception now checks every staged proposal (check=True default; harness_job passes check=not --skip-checker). Before this, only harness_job called it. Live audit: 30 agent_runs rows but 18 distinct run_ids (duplicate run rows); 17 runs staged no proposal; the 1 run with a proposal has its verdict; 2 proposals carry run_ids with no agent_runs row |
| Canvas re-check | none | Deterministic recompute layer is missing |
| Decide + authority | /work, confirm, apply/reject, authority matrix, OBO identity | Live decisions = 0; there is no multi-row "Review N proposals" modal |
| Run log / activity log | agent_runs/agent_steps with stepped_at, actor_kind, authority_basis | No page showing them |
| Document intake | reader.prose, prose/0.2 verbatim check, claim ledger | No "propose records -> tick -> write with source attached" flow in the app |

## Part C. Front end, page by page (audience -> what they care about -> AI workflow)

Audiences: the DCFO (SES sponsor, brief 18-21 Nov), PMS 379 / PEO Carriers financial managers (record owners), NAVSEA 01 and DFAS (data providers), CAPE and auditors (reviewers).

| Page | Audience | The one question | Headline (date-bound) | In-row AI triggers -> task template | Human actions |
| --- | --- | --- | --- | --- | --- |
| / Kennedy picture | DCFO | Can we stand behind the CVN-79 number at the brief, and what access do we need? | "X% of reported CVN-79 cost ties to a recorded obligation as of <date>; N variances need a named office; brief in D days" | Question cards: "Does reported cost tie to obligations?", "Which gaps block the brief?", "What access do we ask for?" -> brief_readiness | Assign owner, send collection request to PMS 379 |
| /variances | PMS 379 analyst | Why do two sources disagree, and who must explain? | "N variances, $X unexplained; M with a known cause" | Row: "Reconcile this contract" -> reconcile_obligations; "Explain this variance" -> explain_variance | Apply cause note; issue a collection request |
| /position, /cost, /execution | DCFO, PMS 379 | Where is the money against the J-book and FPDS? | "Obligated $X of $Y appropriated through FY..; File C ties for k of n periods" | Row: "Why doesn't FY2021P03 tie?" -> explain_residual (analyst engine) | Accept/reject attribution |
| /gaps | Analyst, DCFO | Which open gap blocks which brief claim, and who can close it? | "N gaps; K block the brief; oldest D days" | Row: "Work this gap" -> investigate_gap (3 options + collection requirement) | Adopt a proposed gap; draft a request to the named office |
| /work | Record owners | What is waiting on me? | "N proposals waiting on you, oldest D days" | Review modal for each run | Apply / reject under OBO authority |
| /knowledge, /sources | Analyst, auditor | Where does this number come from? | "N documents, M pages, tie-outs passed k/n" | "Bring in a document" -> read_document (propose claims, verbatim check, tick to write) | Tick rows; correct a value; attach the source |
| /rules (new) | Program lead | What do our rules say, and what changes if I tighten one? | "N rules; last change by <role> on <date>" | Edit -> preview (already built) -> "3 more variances would open" | Save a version (authority-checked) |
| /runs (new) | Auditor, CAPE | Who asked, which agents worked, what was applied? | "N runs; K applied; checker disagreements D" | none (read only) | Export |

Interaction rules for every page:
1. The headline answers the page's question with a date, recomputes after a write, and shows a short "moved from 78 to 87" delta.
2. Every figure is a Figure envelope with a provenance link.
3. Every AI button names its scope ("Reconcile N00024-09-C-2116"), not "Ask AI".
4. Run cards stream the steps, show both verdicts, and offer "Review N proposals".
5. A refusal names the owning office and offers a hand-off.
6. A marked blank is a first-class object: it shows who must fill it and becomes a collection request.

## Part D. Backend orchestration v2 (derived from Part C)

```
page trigger (page, trigger, record ids)
  -> Router (deterministic table; refuses unknown pairs)
  -> TaskTemplate {specialist, rules, packer, canvas_check, proposal_types, goes_to}
  -> Packer (SQL, records + record_ids + provenance_id)        -- code chooses the evidence
  -> Specialist loop (existing run_exception tool loop, packed context, MAX_STEPS)
  -> Model checker (existing check_proposal)  ||  Canvas check (pure recompute)
  -> Proposals (typed, GOES TO, WHY, RULE, marked blanks, flags)
  -> Review modal -> authority_check -> apply_block (existing) -> receipt + recompute
  -> agent_runs/steps/verdicts/decisions (existing tables + asked_by, page, task_id, verdict_canvas)
```

Task templates, first wave:

| task_id | Specialist | Packer | Canvas check | Proposals -> GOES TO |
| --- | --- | --- | --- | --- |
| reconcile_obligations | Obligation Reconciler | FPDS rows per contract (federal_action_obligation as Decimal) | sum + row count + contract label | variance_note -> PMS379 |
| explain_residual | Account Analyst (core/analyst engine) | File C period + tx window | File C vs tx arithmetic for the window | attribution lead -> NAVY_FMO |
| investigate_gap | Gap Investigator | gap + linked KG edges + leads | every citation resolves to a KG edge/page | collection_request -> named office |
| read_document | Document Reader (prose/0.2) | pdf pages/tables of one artifact | verbatim passage + value domain check | claim rows -> claim ledger |
| brief_readiness | Brief Composer (briefer stub) | zone-V claims + open gaps | every sentence cites a claim_id | brief draft -> DCFO (never sent) |
| rule_change_impact | none (no model) | evaluate(dry_run) before/after | the preview itself | rule version -> rule owner |

Changes to existing code:
1. Add `ops/harness/router.py` (task registry + route) and `packers.py`. run_exception receives the packed records in its first message.
2. After the loop, run_exception calls checker.check_proposal for every staged proposal and the template's canvas_check. It writes both verdicts. The verdicts table already has run_id + step_seq.
3. Add columns to agent_runs: asked_by, page, task_id, packed_provenance_id, verdict_model, verdict_canvas. Add marked_blanks and flags (JSON) to proposals.
4. The proposal is blocked from the review modal unless verdict_canvas = PASS. A model-only SUPPORTED is not enough.
5. POST /rules/{id}/versions: authority-checked, then re-run evaluate() and recompute the headline Figures.
6. Add GET /api/v1/runs and /runs/{id}, a run log page, and an export.

## Part E. Tests run on 2026-11-11 (prototype, live tables)

The router + reconcile_obligations template + canvas check ran against the live tables:

| Test | Result |
| --- | --- |
| route /variances "Reconcile this contract" for 09-C-2116 packs 948 records | PASS |
| claim $4,519,300,323.83 / 948 rows for 2116 | PASS |
| 1-cent tamper ($...323.84) | FAIL as expected |
| E-16 mislabel (2116 sum labelled as DD&C 15-C-2114) | FAIL as expected; recomputed $4,578,603,345.77 |
| claim $4,578,603,345.77 / 927 rows for 2114 | PASS |
| unknown trigger ("Move funds") | refused |

Next tests to write: the checker call in run_exception (expect no run without a verdict), the authority refusal path in the review modal, and that a rule version recompute matches preview_rule.

## Part F. What was built (2026-11-11, not deployed)

| Demo move | Built as | Where |
| --- | --- | --- |
| Button names its scope, no blank chat | `si.trigger` buttons; per-page strip from `SI_TRIGGERS`; unknown task/subject/page refused (422) | `templates/_si.html`, `main.py` |
| Route, pack, specialist, two checkers | `sdk.execute`: route, pack (code picks records, Facts in Decimal), code steps + code draft, model rewrites only why/proposed, canvas re-check, Records Checker on a different model, gate | `api/si/sdk.py` |
| Canvas "Pass. N conditions re-tested" | per task: integer-cent recompute, FY series sum, row ids, role check; grounding of every number and ISO date in every sentence; model text with an invented number reverts to the code draft | `api/si/tasks.py`, `sdk._canvas` |
| Run card with agent chips and streaming steps | run panel polls `?after=N` (SSE endpoint also present); each step shows agent, rule chip, code vs model | `static/js/si.js` |
| Review modal APPLY / GOES TO / PROPOSED / WHY / RULE | `<dialog>`; per-proposal server authority before the click; refusal in place naming the owning office and whether anyone holds the role | `_si.html`, `si.js`, `/api/v1/si/runs/{id}/authority` |
| Receipt with role and run number | `store.decide`; delta mode re-tests authority inside `BEGIN ATOMIC` on the caller's OBO token | `api/si/store.py` |
| Comptroller picture, recompute after a write | `/mission`: headline, 5 KPIs, waiting-on-decision by role, contract bars (click/shift-click FY range, server sums), File C tie strip, gaps, runs; reloads `?fresh=1` after a decision | `api/si/picture.py`, `templates/mission.html` |
| Run log and activity log, export | `/runs`, `/runs/{id}`, JSON exports | `templates/runs.html` |

Tasks: `reconcile_obligations`, `explain_residual`, `investigate_gap`, `brief_readiness`. Rule book ids OB-01..03, TO-01..02, GP-01, BR-01..02, EC-01..03 (restated project rules, not the UC rule register). `read_document` and `rule_change_impact` are designed, not built.

Persistence: `AIRCARRIER_SI_PERSIST=memory` (default, nothing written to UC) or `delta` (writes agent_runs / agent_steps / checker_verdicts / proposals / decisions on the caller's token; no new table or column). Write statements syntax-checked with EXPLAIN only; no row written (agent_runs still 35).

Verified 2026-11-11: live 2116 $4,519,300,323.83 / 948 and 2114 $4,578,603,345.77 / 927; E-16 relabel proposal; FY2021P03 residual $770,407,268.00 (File C $973,836,673.00 vs 3-month window $203,429,405.00); 4 of 8 periods tie; FY2019 2114 range $648,638,113.75 / 80 matches SQL; real-model run (opus-5 fell back to opus-4-8 on token budget; budget raised to 6000) where the Records Checker caught an unpacked date, now a Fact; authority: PMS379 allowed, OUSD_C_FMO and NAVY_FMO refused with no holder; `checks/test_si.py` 13 of 14 passed, the one failure was a test fixture bug since fixed (re-run not yet done).

Closed 2026-11-11: one model family on both roles after a fallback (the SI checker now drops the family that answered; models are GPT/Gemini/Grok, see docs/MODELS.md). Open: `delta` mode never exercised against real writes; si.js checked for syntax only (node --check), not in a browser.
