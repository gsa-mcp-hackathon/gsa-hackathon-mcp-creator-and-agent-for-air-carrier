# Air Carrier harness HTTP API: specification of the missing surface

Status: revised 2026-11-11 after the first build. The work queue slice is
built and verified (section 6): exception list, exception card, apply and
reject through confirmation and refusal, on FastAPI and Jinja with no client
framework. The rest of section 3 is the contract for the screens still to
build. Section 4 carries the status of every gap.

Scope decisions (program owner, 2026-11-11):

* The stack stays FastAPI + Jinja2 + server-side SVG, the existing app.css
  tokens, no build step. "Frontend" and "backend" here are layers of one
  app, both built in this repo.
* There is no notional-data label. The whole product is a cross-check: every
  figure is a claim checked against evidence across layers L0 Reported to
  L5 Evidence. Provenance names the layer when the source records one.

Evidence base at the time of the first draft (read from code on 2026-11-11,
not from intent). Items marked resolved in section 4 have since changed:

* app/main.py exposes 33 routes. None of them is a harness route.
* ops/harness has the evaluator, orchestrator, checker and tools as Python
  modules run by jobs. It has no HTTP layer, and ops/harness/__init__.py says
  the apply module is "Not built yet".
* Tables: aircarrier_app_* in users.xiaobing_shang1_civ (deploy/harness_ddl.sql).
* App aircarrier-front-center-dev has no user_api_scopes. Effective scopes are
  iam.access-control:read and iam.current-user:read only. B28.4 (add OBO with
  the sql scope) is decided but not applied.
* aircarrier_app_role_map and aircarrier_app_authority have 0 rows.

---

## 1. Conventions (apply to every endpoint)

### 1.1 Base path, format, versioning

* Base path `/api/v1`. JSON in and out, UTF-8.
* Dollar values travel as decimal strings (`"4519300323.83"`), never as JSON
  numbers, so no float rounding happens on either side.
* Timestamps are ISO 8601 UTC with a `Z` suffix.
* Breaking changes go to `/api/v2`. Additive fields are allowed in v1.

### 1.2 Identity and authority

* Every request is served under the caller's on-behalf-of token
  (`x-forwarded-access-token`). Reads run as the user, so UC row filters and
  grants apply to the user, not to the app SP.
* `X-Forwarded-Email` is informational. It is never the basis of a decision.
* Roles resolve on the server from aircarrier_app_role_map, checked with
  `current_user()` / `is_account_group_member()` under the OBO token (B29.3).
* No request body field carries a role, a component or an authority claim. A
  request that includes `role`, `actor_role` or `authority` in its body is
  rejected with 400 `forbidden_field`.
* The demonstration role switcher in the UI is render-only. It is never sent
  to the server. The server ignores any header or parameter that names a role.

### 1.3 Writes

* Every POST takes an `Idempotency-Key` header (UUID). A replay with the same
  key returns the original response and writes nothing.
* Every authority-bearing POST re-checks authority on the server inside the
  same transaction as the write (BEGIN ATOMIC is verified on serverless).
* Every authority-bearing POST takes `expected_state` (status or version) and
  returns 409 `stale` if the record changed since the user saw it.
* Every authority-bearing POST takes `confirmed_record_ids`, the record ids the
  confirmation dialog showed. The server returns 409 `record_set_changed` if
  they differ from the record ids it is about to act on.

### 1.4 Lists

Every list endpoint is server-paginated, server-filtered and server-sorted.

* Query: `page_size` (default 50, max 500), `page_token`, `sort` (field name,
  `-` prefix for descending; allowed fields listed per endpoint), and the
  filters named per endpoint.
* Response: `{ "items": [...], "next_page_token": string|null,
  "total": Count }`. `total` is a Count envelope (1.6), never a bare integer,
  because the UI shows it.

### 1.5 Errors

`{ "error": { "code": string, "message": string, "detail": object|null } }`.
Codes: `not_found`, `forbidden_field`, `not_authorized` (403, with a
human-readable `message` the UI renders verbatim as the refusal reason),
`stale`, `record_set_changed`, `blocked` (proposal is blocked and can never be
applied), `no_source` (the figure has no source feed), `validation`.

### 1.6 Shared envelopes

These envelopes are the contract the shared UI components render. A response
that carries a figure without the Figure envelope is a backend defect.

**Figure** (every financial or computed value)

```json
{
  "figure_id": "cap.headroom",
  "label": "Cost cap headroom",
  "state": "known | unknown | no_source | blocked_param_unset",
  "state_reason": "string or null; required when state is not known",
  "value": "decimal string or null; null unless state is known",
  "unit": "USD | USD_M | USD_K | PERCENT | COUNT | MONTHS | DAYS | RATIO",
  "display": "$1,234.6M",
  "range": { "low": "decimal", "high": "decimal", "display": "$12.9B to $13.6B" },
  "as_of": "2026-11-10T17:00:00Z",
  "stale_after": "2026-11-11T17:00:00Z",
  "provenance": {
    "record_ids": ["..."],
    "record_count": 948,
    "records_href": "/api/v1/provenance/{provenance_id}/records",
    "rule": { "rule_id": "CAP-02", "rule_version": 3 },
    "computation": {
      "definition_id": "metric.cap_headroom/v1",
      "text": "Statutory limitation less sum of applied cap charges",
      "definition_sql": "optional",
      "inputs": [ { "label": "...", "figure": "Figure (recursive, depth-limited)" } ]
    },
    "model_run_id": "optional",
    "provenance_id": "stable id for GET /provenance/{id}"
  }
}
```

Rules for the Figure envelope:

* The server formats `display`. The UI does no scaling (no division into
  millions), because scaling is arithmetic on dollars.
* `range` is present for estimate-type figures (EAC). A single-value EAC is a
  defect.
* `stale_after` is the end of the figure's as-of window. The UI marks the
  figure stale when the current time is past it. The server sets it per
  figure_id from a policy table (see gap A-12).
* `state` other than `known` means `value`, `display` and `range` are null.
  Zero is never a stand-in for unknown.
* `record_ids` may be truncated for large populations. `record_count` is then
  authoritative and `records_href` pages the full list.
* Counts the UI shows (exception counts, totals) use the same envelope with
  `unit: COUNT`, so every count opens its own provenance.

**Citation** (every agent output)

```json
{ "rule_id": "CC-02", "rule_version": 3, "record_ids": ["..."], "run_id": "...", "step_seq": 4 }
```

**Verdict** (the checker's result on an agent output)

```json
{
  "state": "pass | pass_with_exception | fail | error | pending | not_checked",
  "checks": [ { "check_name": "...", "expected": "...", "actual": "...", "result": "..." } ],
  "notes": "string or null",
  "checker_agent": "harness_checker",
  "model_endpoint": "databricks-gpt-5-5",
  "decided_at": "..."
}
```

`pending` and `not_checked` are explicit states, so the UI never has to infer
a missing verdict. `error` must be a real state (see gap A-3).

**Authority** (on every resource with an action)

```json
{
  "action": "apply | reject | promote | answer | insert_rule_version | respond",
  "allowed": false,
  "reason": "Navy accounting and FMO applies placed-in-service determinations. You hold: Auditor (read-only).",
  "evaluated_for": "user@mail.mil",
  "evaluated_at": "...",
  "basis": { "role": "auditor", "rule": "aircarrier_app_authority row id" }
}
```

The server computes `allowed` and `reason` under the OBO token. This is for
rendering only. The POST re-checks and may still refuse.

**Actor** (on every step and decision)

```json
{
  "kind": "agent | human | system",
  "id": "cost_capture_specialist@v0.3 | user@mail.mil | rule_eval_job",
  "display": "...",
  "authority_basis": "agent_own | human_applied | human_rejected | rule | none"
}
```

`authority_basis: agent_own` marks steps the agent decided on its own
authority (for example a checker block, an intake outcome of duplicate or
blocked, or an analyst rebase). This is the field the agent-decision filter
selects on.

**Confidence band**: `speculative | possible | probable | strong |
established`. Responses carry the band only. If the engine has a numeric
score, the API does not return it.

---

## 2. Endpoint list

Priority P0 is required for build steps 1 to 3 (shared components, shell,
exception list, exception card through apply and refusal). Backing column:
DATA = table exists with rows; TABLE = table exists, empty or partial;
NONE = no store exists yet.

| # | Method and path | P | Backing | Notes |
| --- | --- | --- | --- | --- |
| 1 | GET /me | P0 | role_map (0 rows) | Identity and resolved roles |
| 2 | GET /authority | P0 | authority (0 rows) | Batch authority check |
| 3 | GET /exceptions | P0 | exceptions DATA | List |
| 4 | GET /exceptions/{id} | P0 | exceptions, agent_steps, checker_verdicts, proposals DATA | The exception card |
| 5 | GET /proposals | P0 | proposals DATA | List |
| 6 | GET /proposals/{id} | P0 | proposals DATA | Detail |
| 7 | POST /proposals/{id}/apply | P0 | decisions, determinations TABLE | Apply module not built |
| 8 | POST /proposals/{id}/reject | P0 | decisions TABLE | Apply module not built |
| 9 | POST /runs | P0 | agent_runs DATA | Today runs only in a job |
| 10 | GET /runs, GET /runs/{id} | P0 | agent_runs, agent_steps DATA | Live status missing (A-5) |
| 11 | GET /provenance/{id}, GET /provenance/{id}/records | P0 | NONE | Backs the provenance panel |
| 12 | GET /rules, GET /rules/{rule_id} | P1 | rule_register, audit DATA | |
| 13 | POST /rules/{rule_id}/preview | P1 | evaluator, no dry run (A-4) | Before and after counts |
| 14 | POST /rules/{rule_id}/versions | P1 | rule_register DATA | Authority-checked insert |
| 15 | GET /overview/counts, /overview/figures, /overview/decisions-waiting | P1 | metrics TABLE (0 rows) | |
| 16 | GET /documents, /documents/{id}, /documents/{id}/pages/{n}, /documents/{id}/file | P1 | documents TABLE | |
| 17 | GET /intake | P1 | proposals.intake_outcome | |
| 18 | POST /scenarios, GET /scenarios, GET /scenarios/{model_run_id} | P2 | model_runs DATA | |
| 19 | Domain reads (section 3.9) | P2 | source feeds no_source | |
| 20 | GET /investigations, GET /investigations/{id} | P2 | NONE | |
| 21 | POST /investigations/{id}/answer | P2 | NONE | |
| 22 | GET /candidate-rules, /candidate-rules/{id}, POST promote, POST reject | P2 | NONE | |
| 23 | GET /decisions | P2 | decisions TABLE | Agent-decision filter |
| 24 | GET /lineage/decision/{id}, GET /export/decision/{id}, POST /exports | P2 | all lineage tables | |
| 25 | GET /reference/{kind} | P1 | various | Cacheable reference data |

---

## 3. Endpoint detail

### 3.1 Identity and authority (P0)

**GET /me**

```json
{
  "email": "user@mail.mil",
  "display_name": "...",
  "roles": [ { "role": "navy_accounting_fmo", "component": "navy", "source": "uc_group:... | email" } ],
  "obo": true
}
```

* `obo: false` means the request was not served under a user token. The UI
  then shows a blocking banner and renders every action disabled with that
  reason.

**GET /authority?action=apply&subject=proposal:{id}&subject=proposal:{id2}**

Returns `{ "items": [Authority] }`, one per subject. The exception card and
lists call this in a batch, so authority state renders without one call per
row. The same Authority objects are also embedded in detail responses.

Role to action matrix. Role codes are the ones the rule register already
writes into exceptions.owner_role. Seeded by deploy/harness_authority.sql.

| Role code | Office | Applies |
| --- | --- | --- |
| OUSD_C_FMO | OUSD(C) FMO | rule register versions, enterprise policy; not component records |
| NAVY_FMC | Navy FM&C | Navy-level decisions |
| PMS379 | PEO Carriers / PMS 379 | cost capture items, EVM responses, change order actions, taskers |
| NAVY_FMO | Navy accounting and FMO | valuation determinations, CIP classification, placed in service |
| DFAS | DFAS | reconciliation response only (no action in the vocabulary yet) |
| AUDITOR | DoD IG, GAO | nothing; full read and lineage export |

The rule as built (app/api/harness_sql.py authority_check): a caller may act
on a proposal when they hold, in role_map, the role that owns its exception,
and that role holds the action on `proposals` in authority. The agent-chosen
proposals.target_table is never consulted.

### 3.2 Exceptions (P0)

**GET /exceptions**

* Filters: `area` (cost_capture, evm, cost_cap, valuation, cost_model),
  `owner_office`, `owner_role`, `status` (open, resolved, superseded),
  `rule_id`, `window_closes_before`, `verdict_state`, `has_pending_proposal`.
* Sort: `window_closes_at`, `detected_at`, `dollar_amount`, `rule_id`.
* Item:

```json
{
  "exception_id": "...",
  "area": "cost_capture",
  "status": "open",
  "citation": "Citation",
  "rule_statement": "short text",
  "dollar_amount": "Figure",
  "owner_office": "...", "owner_role": "...",
  "required_action": "...",
  "window_closes_at": "... or null",
  "detected_at": "...",
  "latest_verdict": "Verdict",
  "pending_proposal_count": "Figure (COUNT)"
}
```

**GET /exceptions/{id}**: everything the card shows, with no second call.

```json
{
  "exception": "list item fields above",
  "rule": { "rule_id": "...", "version": 3, "statement_text": "...", "params": {}, "effective_from": "..." },
  "subjects": [ { "record_id": "...", "subject_type": "...", "label": "...", "href": "..." } ],
  "finding": {
    "run_id": "...", "step_seq": 4, "actor": "Actor",
    "summary": "agent's finding text",
    "citation": "Citation",
    "verdict": "Verdict",
    "figures": [ "Figure" ]
  },
  "proposals": [ {
    "proposal_id": "...", "status": "pending | applied | rejected | blocked",
    "target_table": "...", "target_key": "...",
    "payload_display": [ { "field": "...", "value": "...", "figure": "Figure or null" } ],
    "block_reason": "... or null",
    "citation": "Citation", "verdict": "Verdict",
    "authority": { "apply": "Authority", "reject": "Authority" }
  } ],
  "decisions": [ { "decision_id": "...", "actor": "Actor", "action": "apply|reject", "decided_at": "...", "notes": "..." } ],
  "runs": [ { "run_id": "...", "status": "...", "started_at": "..." } ],
  "authority": { "run_agent": "Authority" }
}
```

`finding` is null if no agent has run. The UI then says so. The server does
not synthesize a finding.

### 3.3 Proposals, apply and reject (P0)

**GET /proposals**: filters `exception_id`, `document_id`, `status`,
`intake_outcome`, `target_table`, `rule_id`. Items as in 3.2.

**POST /proposals/{id}/apply**

Request:

```json
{ "expected_state": "pending", "confirmed_record_ids": ["..."], "notes": "optional" }
```

Server, in one transaction under the OBO token:

1. Load the proposal. If `status = blocked` or `intake_outcome = blocked`,
   return 409 `blocked` with `block_reason`. No role can apply a blocked
   proposal.
2. Check `expected_state` and `confirmed_record_ids` (1.3).
3. Check that the latest checker verdict is `pass` or `pass_with_exception`.
   Otherwise return 409 `verdict_not_passing`.
4. Resolve authority from role_map and authority. If refused, write a
   decisions row with `authority_check_result = refused:<reason>` (refusals are
   part of the record) and return 403 `not_authorized` with the reason.
5. Write decisions (action apply), determinations, update proposal status,
   recompute affected metrics (aircarrier_app_metrics, invariant 9) and return:

```json
{ "decision_id": "...", "determination_id": "...", "authority_check_result": "allowed:<basis>",
  "recomputed_figures": [ "Figure" ] }
```

Open question for the backend owner: should a refused attempt write a
decisions row? The action_enum CHECK allows only apply and reject, so the
refusal would need its own action value or a separate attempts table.

**POST /proposals/{id}/reject**: `{ "expected_state": "pending",
"confirmed_record_ids": [...], "reason": "required, non-empty" }`. The same
authority path. Returns `{ decision_id }`.

### 3.4 Runs (P0)

**POST /runs**: `{ "subject_kind": "exception | document | investigation",
"subject_id": "..." }`. Authority-checked (`run_agent`). Returns 202
`{ run_id, status: "queued", status_href }`. The run executes as the agent
principal (app SP), never under the user token. `triggered_by` records the
user.

**GET /runs**: filters `status`, `subject_kind`, `subject_id`,
`triggered_by`, `started_after`.

**GET /runs/{id}**

```json
{
  "run_id": "...",
  "status": "queued | running | succeeded | blocked_by_checker | failed",
  "subject_kind": "...", "subject_id": "...",
  "specialist": "...", "orchestrator_version": "...",
  "triggered_by": "Actor",
  "started_at": "...", "ended_at": "... or null",
  "progress": { "current_step": 3, "current_step_label": "get_cost_capture" },
  "failure": { "step_seq": 3, "step_label": "...", "error_code": "...", "message": "..." },
  "steps": [ {
    "step_seq": 1, "at": "...", "actor": "Actor", "agent_version": "...",
    "model_endpoint": "...", "tool": "... or null",
    "citation": "Citation", "output_summary": "...",
    "verdict": "Verdict or null", "latency_ms": 1200
  } ],
  "mlflow_trace_id": "..."
}
```

The UI polls this every 2 to 5 seconds with backoff, and stops at a terminal
status. A `Retry-After` header is honored if present.

### 3.5 Provenance (P0)

**GET /provenance/{provenance_id}**: the full provenance block of a Figure,
with `computation.inputs` expanded one level.

**GET /provenance/{provenance_id}/records**: paginated list of the records
behind the figure: `{ record_id, record_type, label, source_table,
source_locator, as_of, href }`.

### 3.6 Rule register (P1)

**GET /rules**: filters `area`, `status`, `owner_role`. Item: rule_id,
current version, status, blocked_reason, statement_text, params,
value_lists, owner_office, required_action, effective_from, the current
open-exception count (Figure, COUNT), and Authority for
`insert_rule_version`. Cacheable: `ETag`, `Cache-Control: max-age=60`.

**GET /rules/{rule_id}**: the rule, all versions, and the audit log
(`rule_register_audit`: actor, event, prior_params, new_params, at, notes).
The edit log renders on the same page from this response.

**POST /rules/{rule_id}/preview**: no writes of any kind.

Request: `{ "base_version": 3, "params": { ... }, "value_lists": { ... } }`.

Response:

```json
{
  "preview_id": "...",
  "base_version": 3,
  "evaluated_at": "...",
  "before": { "count": "Figure (COUNT)", "dollar_total": "Figure" },
  "after": { "count": "Figure (COUNT)", "dollar_total": "Figure" },
  "delta": { "count": "Figure (COUNT)", "dollar_total": "Figure" },
  "added_href": "/api/v1/rules/{rule_id}/preview/{preview_id}/added",
  "removed_href": "/api/v1/rules/{rule_id}/preview/{preview_id}/removed",
  "expires_at": "..."
}
```

The server computes `before`, `after` and `delta`. Preview must run the same
code path as ops/harness/evaluate.py in a non-writing mode, so the preview and
the real evaluation cannot disagree (gap A-4).

**POST /rules/{rule_id}/versions**: `{ "base_version": 3, "preview_id":
"...", "params": {...}, "value_lists": {...}, "notes": "required" }`.
Authority-checked. Returns 409 `stale` if base_version is no longer current,
and 409 `preview_mismatch` if params differ from the preview or the preview
expired. Inserts a rule_register row and an audit row in one transaction, then
triggers evaluate(trigger="rule_insert"). Returns `{ rule_id, version, eval_id }`.

### 3.7 Overview (P1)

The overview is split so counts render first.

* **GET /overview/counts** (target p95 under 300 ms): open exceptions per
  area (Figure COUNT each, with a `href` to the filtered list), proposals
  waiting, runs in flight, investigations waiting for a person.
* **GET /overview/figures**: cap headroom; EAC range (Figure with `range`);
  CIP balance; KSD coverage (Figure PERCENT, computed server-side with
  numerator and denominator in provenance); acceptance and delivery milestones
  `[ { milestone, planned, forecast, actual, status } ]`.
* **GET /overview/decisions-waiting**: paginated items naming who must act:
  `{ subject, subject_href, required_action, owner_office, owner_role,
  waiting_since, window_closes_at, dollar_amount: Figure }`.

### 3.8 Documents and intake (P1)

* **GET /documents**: filters `doc_type`, `received_after`, `has_blocked`.
* **GET /documents/{id}**: metadata, page count, sha256, and proposals
  derived from it grouped by intake_outcome.
* **GET /documents/{id}/pages/{n}**: page text plus `spans`:
  `[ { proposal_id, field, char_start, char_end, bbox: [x0,y0,x1,y1] } ]`, so
  the viewer highlights the cited span without searching text client-side
  (gap A-9).
* **GET /documents/{id}/file**: streams the PDF from the volume under the OBO
  token.
* **GET /intake**: proposals with an intake outcome. Each item has
  `intake_outcome` (ready, duplicate, blocked), `duplicate_of` (record id and
  href, required when duplicate), `block_reason` (required when blocked) and
  Authority for apply. Apply goes through 3.3, which refuses blocked.

### 3.9 Domain reads (P2)

All return Figure envelopes. Today every source lookup behind them returns
`blocked_no_source`, so each must return `state: no_source` with a reason
until a feed exists.

* Reconciliation: **GET /reconciliation/ladders**, **GET
  /reconciliation/ladders/{id}**. Rungs ordered top to bottom (financial
  statement line down to source document): `{ rung, label, left: Figure,
  right: Figure, difference: Figure, ties: bool, tolerance: Figure }`, plus
  `findings: [ { kind: "ties_above_fails_below", upper_rung, lower_rung,
  text } ]`. The server detects the tie-above-fail-below case.
* EVM: **GET /evm/control-accounts** (CPI, SPI, CV, SV, VAC as Figures),
  **GET /evm/breaches**, **GET /evm/baseline-flags**, **GET
  /evm/schedule-exposure** (`slip_days: Figure, exposure: Figure,
  assumption: { text, rate: Figure, source }`).
* Cost cap: **GET /cap/position** (limitation, amounts, headroom), **GET
  /cap/adjustments** (each with `authority_reference` or `null` plus
  `has_documented_authority`), **GET /cap/projection?scenario=** (headroom
  series and `breach_date` per scenario), **GET /cap/post-delivery-migration**.
* CIP: **GET /cip/accumulation**, **GET /cip/classification-exceptions**,
  **GET /cip/placed-in-service** (per acceptance event, with determination
  status), **GET /cip/ksd-package** (each required document: present, absent
  as a finding, with the dollar amount it supports).

### 3.10 Scenarios (P2)

* **POST /scenarios**: `{ "assumption_set_id": "...", "overrides": { ... } }`.
  Returns 202 `{ model_run_id, status_href }`.
* **GET /scenarios/{model_run_id}**: `{ model_run_id, status, eac: Figure
  (range required), drivers: [ { name, contribution: Figure } ],
  inputs_vintage: { feed: timestamp }, rule_version: { rule_id: version },
  assumptions: [ ... ], input_record_ids, warnings, created_by: Actor,
  created_at }`. These map to aircarrier_app_model_runs columns.
* **GET /scenarios**, **GET /reference/assumption-sets**.

### 3.11 Investigations (P2, no store exists)

**GET /investigations**: filters `status` (running, waiting_for_human,
concluded, abandoned), `subject_id`, `leading_band`.

**GET /investigations/{id}**

```json
{
  "investigation_id": "...", "subject": { "kind": "reconciliation", "id": "...", "href": "..." },
  "status": "waiting_for_human",
  "residual": "Figure",
  "hypotheses": [ {
    "hypothesis_id": "...", "rank": 1, "band": "probable",
    "state": "live | leading | abandoned | confirmed",
    "abandoned_reason": "required when abandoned", "abandoned_at": "...",
    "mechanism": { "mechanism_id": "...", "text": "..." },
    "supporting": [ "Evidence" ], "disconfirming": [ "Evidence" ],
    "tests": [ { "test_id": "...", "description": "...", "run_at": "...", "result": "supports|disconfirms|inconclusive", "evidence_ids": ["..."] } ],
    "band_history": [ { "at": "...", "band": "possible", "moved_by": ["evidence_id"] } ]
  } ],
  "evidence": [ {
    "evidence_id": "...", "kind": "record | document | absence | test_result",
    "record_ids": ["..."], "text": "...",
    "absence": { "predicted": "what should exist", "searched": ["where"], "searched_at": "..." }
  } ],
  "timeline": [ { "at": "...", "pass": 2, "event": "rebase | test | band_change | abandon | ask | answer",
                  "from_hypothesis": "...", "to_hypothesis": "...", "evidence_ids": ["..."], "actor": "Actor" } ],
  "stop": "Stop or null",
  "citation": "Citation", "verdict": "Verdict"
}
```

The Stop object (present when status is waiting_for_human):

```json
{
  "question_id": "...",
  "reason": "low_confidence | high_cost",
  "question": "...",
  "live_hypotheses": ["hypothesis_id"],
  "tried": ["test_id"],
  "would_separate": [ { "text": "...", "cost": "Figure or null" } ],
  "options": [ { "option_id": "...", "label": "...", "consequence": "..." } ],
  "authority": "Authority (action answer)"
}
```

Abandoned hypotheses are never filtered out of this response.

**POST /investigations/{id}/answer**: `{ "question_id": "...",
"option_id": "...", "notes": "optional", "expected_state":
"waiting_for_human" }`. Authority-checked. Returns 202 `{ run_id }` for the
resumed pass.

### 3.12 Candidate rules (P2, no store exists)

* **GET /candidate-rules**: filters `status` (proposed, promoted, rejected).
  Rejected items are always returned when requested, with `reject_reason`,
  `rejected_by: Actor` and `rejected_at`.
* **GET /candidate-rules/{id}**: statement, proposed expression and params,
  `supporting_investigations` (ids and hrefs), `estimated_population`
  (count and dollar Figures from the same preview path as 3.6), citation,
  verdict.
* **POST /candidate-rules/{id}/promote**: `{ "expected_state": "proposed",
  "preview_id": "...", "reason": "required" }`. Inserts rule version 1 through
  the same path as POST /rules/{id}/versions, so it carries the same authority
  check.
* **POST /candidate-rules/{id}/reject**: `{ "expected_state": "proposed",
  "reason": "required" }`.

### 3.13 Decisions, lineage and export (P2)

* **GET /decisions**: filters `actor_kind` (agent, human, system),
  `authority_basis` (agent_own selects only what the agent decided on its own
  authority), `subject_kind`, `subject_id`, `actor_id`, `from`, `to`,
  `action`. Items carry Actor, Citation and Verdict.
* **GET /runs/{id}/steps** takes the same `actor_kind` and `authority_basis`
  filters.
* **GET /lineage/decision/{id}**: one ordered chain `[ { at, kind:
  "detection | agent_step | checker_verdict | proposal | decision |
  determination | metric_recompute", actor: Actor, citation, verdict, records,
  rule: { rule_id, version, statement_text_at_that_version } } ]`. The rule text
  comes from aircarrier_app_rule_at at the event time, not from the current
  version.
* **GET /export/decision/{id}?format=json|csv**: the same chain as a file,
  with a manifest `{ exported_at, exported_by, sha256 }`.
* **POST /exports**: `{ "scope": { from, to, subject_kind, actor_kind },
  "format": "json|csv" }`. Returns 202 `{ export_id }`. GET /exports/{id}
  gives status and a download link. A full export never streams through a
  list endpoint.

### 3.14 Reference data (P1, cacheable)

**GET /reference/{kind}** for kind in `areas`, `offices`, `roles`,
`confidence-bands`, `figure-policies` (figure_id to as-of window). `ETag`
with `Cache-Control: max-age=300`. Financial figures are never served from
this path.

---

## 4. Backend gaps found in the code (numbered for tracking)

Each gap blocks one or more endpoints above. None is worked around in the UI.

| Id | Gap | Evidence | Blocks |
| --- | --- | --- | --- |
| A-1 | No HTTP layer for the harness | grep of all route decorators | everything |
| A-2 | Apply module not built | ops/harness/__init__.py | 3.3 |
| A-3 | Checker stores `error` as `fail` | checker._write_verdict, verdict_enum CHECK | Verdict.state |
| A-4 | evaluate() always INSERTs; no non-writing mode | evaluate.py lines 150 and 196 | rule preview, candidate population | **Resolved** |
| A-5 | agent_runs row is written only at run end (F2) | orchestrator | live run status, failure step |
| A-6 | agent_steps has no timestamp column | harness_ddl.sql | lineage ordering by time, step `at` | **Resolved** |
| A-7 | checker_verdicts has no proposal_id column; the link sits in the `checks` array, and its step_seq is numbered separately from agent_steps | checker._write_verdict | Verdict on a specific proposal or step |
| A-8 | No actor kind or authority basis on steps or decisions | DDL | agent-decision filter | **Resolved** |
| A-9 | Proposal grounding has page and text_span only, no offsets or bbox | proposals.grounding | span highlight |
| A-10 | aircarrier_app_metrics is empty; cost capture, EVM, cap and CIP tools return blocked_no_source | SQL count; harness_tools.sql | overview and domain figures |
| A-11 | No investigation, hypothesis, evidence, stop or candidate-rule store | grep of ops, core, deploy | 3.11, 3.12 |
| A-12 | No as-of window policy per figure | DDL | Figure.stale_after |
| A-13 | No provenance store or id for computed figures | DDL | 3.5 | **Resolved** |
| A-14 | role_map and authority are empty | SQL count | every Authority |
| A-15 | App has no user_api_scopes (sql) | Apps API GET | OBO; every authority-bearing call |
| A-16 | decisions.action_enum allows only apply and reject | harness_ddl.sql | recording refusals, answers, promotions |
| A-17 | Proposal payload is an opaque JSON string, with no per-field display or figure typing | proposals.proposed_payload | rendering payload values through Figure | **Resolved** |

Found in the 2026-11-11 build audit:

| Id | Gap | Evidence | Blocks |
| --- | --- | --- | --- |
| A-18 | The orchestrator discarded the specialist's final answer, so a run that staged no proposal left no record of its conclusion | orchestrator: `if not tcs: break` kept no text; the forced-answer reply was dropped | the agent finding on the card |
| A-19 | agent_steps stores a tool's result but not which tool was called or with what arguments (only inputs_digest) | harness_ddl.sql, orchestrator step insert | step lineage that names the tool |
| A-20 | The rule register has no evidence-layer column, so no figure can say which of L0 to L5 it comes from | rule_register DDL | Figure.provenance.layer |
| A-21 | The checker verifies staged proposals only; an agent finding is never checked | checker.check_proposal is the only entry point | a verdict on findings |
| A-22 | Authority is enforced in the app's statement, not by the tables, so any principal with MODIFY can write around it. Grants on 2026-11-11: the schema owner holds ALL PRIVILEGES on the schema. The app's own service principal 7e1ec6c0-... (app-2vrjmx aircarrier-front-center-dev), which grants_harness_agent.sql also uses as the agent principal, holds SELECT, MODIFY on proposals, agent_runs, agent_steps and checker_verdicts, SELECT on exceptions and rule_register, and nothing on decisions, determinations, decision_attempts, role_map or authority. So the app identity cannot write a decision, but MODIFY includes UPDATE, and it could set a proposal's status to applied with no decision behind it. Fix: stage through an INSERT-only path (a view or procedure the SP can call, with MODIFY revoked), and have the card flag any proposal whose status is applied or rejected without a matching decision row | SHOW GRANTS on aircarrier_app_proposals, decisions, determinations, decision_attempts | multi-user write safety; agent cannot self-approve |
| A-23 | AV-06 v1 names owner_role NAVY_FMO with owner_office "Navy FM&C", two different offices | live rule register row | the owner shown on valuation exceptions |
| A-24 | agent_runs.outcome holds "completed" (17 rows), "error: ..." (1) or NULL (12), not the released, blocked_by_checker or error that harness_ddl.sql documents | live agent_runs, 2026-11-11 | run outcome filters |
| A-25 | deploy/grants_harness_agent.sql cites checks/no_source_write.py, which does not exist | file listing | the grant's stated check |
| A-26 | live._cast turns DECIMAL into float and leaves BOOLEAN as text | app/api/live.py | exact money, flags (worked around in harness_sql by casting money to STRING, and in harness.act for booleans) |

Status after the 2026-11-11 build:

| Id | Status | Where |
| --- | --- | --- |
| A-1 | Resolved for the work queue: /api/v1/me, /exceptions, /exceptions/{id}, /proposals/{id}/authority, /proposals/{id}/apply, /proposals/{id}/reject | app/api/harness.py |
| A-2 | Resolved. Apply and reject are one BEGIN ATOMIC statement run under the caller's token, with the authority check inside it | app/api/harness_sql.py apply_block |
| A-3 | Read-side resolved: Verdict.state is `error` when the proposal_review check records error | app/api/envelopes.verdict |
| A-7 | Read-side resolved: verdicts join to proposals through checks[check_name='proposal'].expected | harness_sql.proposals_for_exception |
| A-14 | Rows written to deploy/harness_authority.sql; not yet run against the app tables, pending the owner's confirmation | deploy/harness_authority.sql |
| A-15 | Config written: `user_api_scopes: [sql]` added to resources/app.yml. Takes effect on next `bundle deploy` + app restart | resources/app.yml |
| A-16 | Resolved by a separate table: aircarrier_app_decision_attempts holds every attempt, allowed or refused, with the server's reason; decisions holds only what was decided | deploy/harness_authority.sql |
| A-18 | Resolved (F23): the final answer is written as the run's last agent_steps row, {"kind": "finding"}, with the run's citation | ops/harness/orchestrator.py, checks/test_harness.py |
| A-22 | Detection only: the card flags applied or rejected with no matching decision. The grant change is open | app/api/harness.py _mark_unbacked |
| A-26 | Worked around in the work queue; live.py unchanged for the explorer | app/api/harness_sql.py |
| A-6 | Resolved. ALTER TABLE ADD COLUMN stepped_at TIMESTAMP on live and scratch tables. Backfilled 80 existing rows by interpolating run started_at to ended_at. Orchestrator INSERTs now write CURRENT_TIMESTAMP(). Read query selects stepped_at. Template shows <time> element per step. 37/37 offline tests | ops/harness/orchestrator.py, app/api/harness_sql.py, app/api/harness.py, app/templates/exception.html |
| A-13 | Resolved. Hash-based deterministic provenance_id (SHA-256, 16 hex chars) derived from figure inputs. In-process LRU cache (500 entries). Two endpoints: GET /provenance/{id} and GET /provenance/{id}/records (paginated). records_href in Figure envelope. Template links provenance_id to records. 35/35 offline tests | app/api/envelopes.py, app/api/harness.py, app/templates/_ui.html |
| A-17 | Resolved. Convention-based typing in envelopes.py: field name pattern (dollar keywords) + decimal parse → Figure envelope with grounding provenance. Non-dollar fields pass through as text. Templates dispatch on typed=='figure' for ui.figure(). 26/26 offline tests | app/api/envelopes.py, app/api/harness.py, app/templates/exception.html, app/templates/confirm.html |
| A-8 | Resolved. ALTER TABLE ADD COLUMNS (actor_kind STRING, authority_basis STRING) on agent_steps and decisions (live + scratch). Backfilled 80 agent_steps rows (agent/none). Orchestrator writes agent/none for tool steps, agent/agent_own for findings. apply_block writes human/human_applied or human_rejected. Read queries select both columns. E.actor() envelope carries authority_basis. Template renders authority_basis as badge + data-authority attribute. 42/42 offline tests | ops/harness/orchestrator.py, app/api/harness_sql.py, app/api/harness.py, app/api/envelopes.py, app/templates/_ui.html |
| A-4 | Resolved. Backend: evaluate() dry_run + params_override, preview_rule(). App: bind_expression() mirrors evaluate._bind() for SQL warehouse. GET /rules (with open-exception Figures), GET /rules/{rule_id} (all versions + audit), POST /rules/{rule_id}/preview (before/after/delta as Figures, 409 stale, 404 unknown, expression_sql execution via bind_expression), GET .../preview/{id}/added and /removed (paginated, LRU cache 50 entries, 10min TTL). 56/56 offline tests | ops/harness/evaluate.py, app/api/harness_sql.py, app/api/harness.py |
| others | Open | |

## 5. Build order, matched to the UI build order

1. A-15 and A-14 (configuration and seed rows; no code). A-14 written.
2. Done: A-1 work-queue skeleton, A-2 apply and reject, A-16, A-18.
3. Done: A-17, A-13, A-6, A-8 — payload typing, provenance IDs, step timestamps, actor columns.
4. In progress: A-4 dry-run resolved. GET /rules, GET /rules/{rule_id}, POST /rules/{rule_id}/preview built with added/removed endpoints. POST versions remaining.
5. A-10, A-12 and the overview, then documents (A-9), then the domain reads.
6. A-11 investigations and candidate rules, then lineage and export.

## 6. What is built and how it was verified (2026-11-11)

Built:

* app/api/identity.py: the caller from x-forwarded-email (display only) and
  x-forwarded-access-token. user_client() forces the user token
  (auth_type pat) so the SDK cannot fall back to the app service principal.
* app/api/harness_sql.py: every statement. authority_check() is the rule and
  apply_block() embeds the same text, so the rendered button state and the
  write cannot disagree.
* app/api/envelopes.py: Figure, Verdict, Citation, Actor, Authority.
* app/api/harness.py: the service and the /api/v1 routes.
* app/templates/_ui.html: figure, citation, verdict, actor, act_button.
* app/templates/work.html, exception.html, confirm.html; routes in main.py
  (/work, /work/exceptions/{id}, /work/proposals/{id}/confirm, POST
  /work/proposals/{id}/apply|reject).
* deploy/harness_authority.sql: decision_attempts DDL, authority matrix,
  pilot role assignment.

The apply path, in order, inside one transaction under the caller's token:
replay check on request_id; authority_check; insert the attempt; if allowed,
insert the decision, insert the determination (apply only), set the
proposal's status where it is still pending. A failure anywhere rolls all of
it back, including the attempt.

Verified:

* checks/test_work_live.py, on scratch tables through the Statement
  Execution API on the app's warehouse: 20 of 20. Every reason code on the
  case built for it; reject not gated on the verdict; stale record set
  refused; apply writes attempt, decision, determination and status; a
  refusal writes only the attempt; a replay returns the first decision and
  writes nothing; a failing determination rolls the whole block back.
* checks/test_work.py, offline: 20 of 20. Money keeps every digit; unknown
  figures carry no value; staleness; verdict states including error; both
  step encodings; no statement takes a role; enabled links only where the
  server allowed; refusals render disabled with the reason; no token means
  read-only and no authority statement runs; forms refuse extra fields,
  cross-origin posts and reasonless rejects; a status of applied or rejected
  with no matching decision is flagged on the card. Two mutations (an always-enabled
  button, a raw amount in a template) were confirmed to fail the suite.
* checks/test_harness.py 55 of 55 (one new test for A-18), checks/test_app.py
  all checks pass.

Not yet verified: the deployed app with a real on-behalf-of token, because
the app has no sql scope yet (A-15).
