# Build decisions

Same format as `../../LOG.md` Part I: decision, reasoning, supersedes. These
are build decisions rather than design decisions, kept separate so they can be
folded into LOG.md as a block when the build settles rather than interleaved
with D1-D34 while they are still moving.

**B1. Ops agents run as Databricks job tasks, not on the Databricks agent
runtime.** Agent Bricks CLI and DurableAgentServer target interactive served
agents with an invocation API. The ops agents are batch workers claiming rows
from a queue and need neither. Job tasks plus model serving endpoints are also
the primitives most likely to exist in the DoD environment, where the agent
runtime is Beta. Each agent's core stays a pure function with a typed
signature, so an MLflow `ResponsesAgent` wrapper can be added later without
touching the agent.

**B2. Model access is requested by role, never by model name.** Agents ask for
`reasoning` or `extraction`. Binding is in `seed/models.yaml`. Swapping a model
is a change in one file.

**B3. The embedding model is chosen for IL5 portability.**
`system.ai.bge-large-en` over `models.ai.text-embedding-3-large`. system.ai
models are Databricks provided and most likely to survive transfer; an
external-provider embedding endpoint almost certainly will not. The cost of
choosing wrong is re-embedding the corpus after the index is load-bearing.

**B4. Declarative Automation Bundles are the only deploy path.** Anything
created by clicking does not transfer.

**B5. One repository, three packages, and `app/` is a self-contained transfer
unit.** GitHub is record keeping. Advana FM needs its own GitLab repo with the
Dragon pipeline for the App, so `app/` carries everything that deployment
needs and `core/` is vendored into it rather than imported across the boundary.
*Supersedes:* the earlier recommendation that `app` import from `core`
directly, which would have broken the transfer unit.

**B6. Genie is a front-center tool only.** A Genie answer has no coordinate
chain and cannot satisfy D27, so it never enters the ops center path.

**B7. The decision log becomes executable policy.** D3, D4, D27, D33 and D34
are predicates evaluated at claim admission in `core/policy/decisions.py`, and
every rejection names its D-number. A rule that lives only as prose depends on
the reader remembering it.

**B8. The gate is a routing table on three independent axes, not a score.**
Follows D26 for the same reason: a single number hides the mechanism.
Risk is a separate axis from confidence, because all three errors in N.7 were
high confidence and wrong at the premise level.

**B9. The live tie-out suite moved from `analysis/` to `dbrepo/checks/`, and
`analysis/` became history.** The five working scripts are the deterministic
suite now and belong with the build. `analysis/superseded/` keeps the rejected
iterations and the reasons. `analysis/synth.py`, the Monte Carlo built on an
incomplete advance procurement series, was deleted under D32.

**B10. `seed/` is a projection, not a second home.** The markdown document set
keeps the one-home rule. Each seed file names its source section, and
`tools/extract_seed.py` is the eventual generator with a divergence check.

**B11. Policy violations set a risk flag and block promotion.** The first run
of `checks/test_gate.py` routed a claim to promote that had already failed D34,
because the violation never reached the gate. A violation is evidence of a risk
class, not only a rejection: D33 implies METHOD, D34 implies KEY, D4 implies
PREMISE, E12 implies INTERPRETATION. The gate now takes the violation list and
a claim with an outstanding violation never promotes whatever its tag or size.
Added at the same time: a claim larger than 100 per cent of its own subject
total routes to review, because a part larger than the whole is a premise
signal.

**B12. The front center is FastAPI with Jinja2 templates, not Streamlit.** One process serving both
the JSON API and the server-rendered pages, which is what Databricks Apps wants. FastAPI gives the
typed API and the OpenAPI document that other consumers and the ops center read; Jinja2 gives the
page composition. Streamlit is quick for a notebook-shaped app and wrong for a product with
fourteen pages, a public API, a write path and a design system.
*Supersedes:* the Streamlit scaffold in the first iteration.

**B13. Charts are server-rendered SVG with no chart library, no CDN and no build step.** A
restricted IL5 workspace is deny-by-default on egress, so a chart library loaded from a CDN renders
nothing after transfer, and an npm build step needs a registry that is not reachable. The charts
emit SVG that inherits the page theme through CSS custom properties, so light and dark both work
with no regeneration and no client-side redraw. `app/api/charts.py` carries donut, horizontal bar,
stacked columns, waterfall, line, dual-axis obligation curve and bubble.

**B14. The data layer has two backends behind one interface and the app ships with the files
backend live.** `files` reads JSON bundles built by `etl/build_data.py`; `uc` reads named views in
the serving schema. This is D11, graceful degradation, applied to the front end: the product works
at every access level including zero, and the demo does not depend on a workspace existing.

**B15. The sub-award file is a new source and it is now in the product.** The USAspending bundle in
`ring0/reference/` carries 2,990 sub-awards worth $426.8M across 261 distinct subcontractors on the
detail design contract, which is 9.3 per cent of that prime's obligations. Nothing in the dossier
had looked at it. It is the first quantified tier-two vendor map for this hull and it confirms the
Part L.3 finding at transaction level: Curtiss-Wright Exlar and Federal Equipment Company appear as
named subcontractors, the same firms the industrial map identified from the prime record. The
preparation contract reports no sub-awards at all, so the visible supply chain is one contract deep
and under a tenth wide.

**B16. The MCP server is the agent surface, and it is the same code the gate runs.**
`mcp/mcp_server.py` exposes twelve tools over the four stores and the three deterministic
checkers. It imports `core.policy.gate`, `core.policy.decisions`, `ops.agents.challenger` and
`ops.agents.tieout` directly rather than reimplementing them, so a model asking "is this figure
usable" gets the identical routing decision the pipeline would make, including the identical
policy violations by D-number. A second implementation of the gate for conversational use would
drift from the pipeline within a week and nobody would notice, because both would answer
plausibly. It runs as stdio for a local agent and as `uvicorn mcp_server:http_app` for hosting
beside the front end as a second Databricks App, with the same auth and the same egress.

**B17. Three skills, each named for a decision rather than a capability.**
`aircarrier-investigate`, `aircarrier-verify-figure` and `aircarrier-collection-request`. Each
one encodes the order of operations that was learned the expensive way: check the mechanism store
before interpreting a document, capture the full coordinate chain before using a cell, challenge
the premise before trusting the arithmetic, and emit a collection requirement rather than a
figure when working from leads. A skill that merely described the tools would leave the ordering
to the model, and the ordering is the part that prevented the three recorded errors.

**B18. Gate checks are a script, not a checklist.**
`checks/gates.py` runs the four PLAN.md verification gates against the workspace through the
Databricks SDK, read only, and prints the admin action where a gate needs one rather than taking
it. A checklist of things to click gets done once and never again; a script gets re-run after
every workspace change, which is when a gate silently flips. Gate B also checks the egress
allowlist against the specific government sources the event stream needs, because a restricted
workspace that permits pypi but not the sources is a configuration that passes a casual look and
fails the product.

**B19. G27 closed by direct query, and the closure changed the method rather than the total.**
Both contracts are out of this hull: one belongs to a different vendor and a landing craft, the
other does not exist in the procurement feed at all, established against a control query that
returned a complete record in the same session. No figure in the hull moved. What moved is the
confidence in inherited labels: the gap had rested for a day on a vendor name that had been
inferred and then carried as fact, which is the third instance of that failure here after E-12
and E-13. Both numbers stay visible in the key set under `resolved_not_this_hull` instead of
being deleted, because a deleted exclusion is an exclusion that gets re-inherited. The lookup
also opened E-16, a $583,963.00 disagreement between the procurement feed and the public spending
record on the same contract, which is immaterial to every total and is therefore the kind of
disagreement that survives review.

**B20. `dbrepo/` is the complete transfer unit, and binaries do not travel as
workspace files.** The corpus moved inside the repository so that dropping this
folder into any Databricks environment gives a working system with its evidence
attached. The split is in `databricks.yml`: code, text, the manifest and the
built index sync as workspace files; `corpus/reference` and `corpus/imagery`
go to a Unity Catalog volume by `tools/upload_corpus.py`. 38MB of PDFs sync
slowly, read awkwardly from a job, and get no content addressing; the volume
gives all three. The manifest travels with the code either way, so the
catalogue exists before the bytes do and the app degrades to showing the
catalogue rather than breaking.

**B21. The artifact id is the first sixteen of the sha256.** A claim's
coordinate points at an artifact id. When a document is replaced with a newer
edition the hash changes, old claims keep pointing at the old hash, and the
supersession is visible instead of silent. A filename-addressed store makes
that same replacement invisible, which is the quiet way a dossier starts citing
a document that no longer says what it said.

**B22. Structured data is not embedded.** The first ingest produced 18,871
chunks, of which 16,072 were rows from three CSVs. Semantic search answers a
question about a transaction worse than a WHERE clause does, and embedding
rows swamps the index with near-identical neighbours. The manifest routes
every artifact: `embed` for prose and the tables inside documents, `table` for
structured extracts, `asset` for images. 20 documents are indexed, 11 are
queryable, 12 are neither. Ask the corpus for meaning and the tables for
numbers.

**B23. Retrieval is lexical first and respects the trust hierarchy.** BM25 over
the chunks, with no model, no network and no service, because a cold IL5
environment needs working citable retrieval before any endpoint is configured,
and because BM25 is better than an embedding at exactly what this corpus is
full of: contract numbers, exhibit codes, account lines. An embedding maps a
rare exact token onto its neighbours, and a neighbouring contract number is a
different hull. Semantic fuses in by reciprocal rank when a model exists.

Search defaults to authoritative sources only. Measured, not assumed: on the
first unfiltered run the analyst's own dossier outranked every primary source
it summarises, because a summary written in the asker's vocabulary always
out-matches its source. Citing the summary instead of the document is precisely
how a lead becomes a figure, which is what D16 exists to prevent, so the
hierarchy is enforced in retrieval rather than left to whoever reads the
results.

**B24. The dashboard's insight panel is rule-derived, not model-written.** Each
item appears because a named rule fired on the tables, and carries the figure
it rests on. A model is useful for phrasing and for narrative around these
items; it is not what decides that an item appears. A dashboard that prints
model prose beside a number invites the reader to trust the prose at the
number's confidence level, and in this programme the numbers carry explicit
trust states the prose would quietly launder. An item can be disagreed with by
checking its evidence rather than by doubting the narrator.

**B25. Readability is measured.** `tools/contrast.py` checks every text colour
against every background in both themes and the suite fails below 4.5:1. Three
colours failed on first run, including every "muted" text in light mode. Muted
means lower emphasis, not harder to read: a figure someone is deciding whether
to trust must never be the grey one. Light is the default and the OS preference
no longer overrides it, because this is read on work laptops set to dark for a
terminal and a product full of tabular figures is read in light.

**B26. The contribute page is ordered by answerability, not by exposure.** It
is the one page written for someone who is not on this team. A reader who opens
it and sees a nine-billion-dollar question they cannot help with closes the
tab; one who sees a question they can answer from memory answers it. No
contributor is asked to grade their own answer on an Admiralty scale. The
load-bearing field is "how do you know it", which decides whether the answer
can become a figure and which protects the contributor: an answer recorded with
how they knew it cannot later be quoted as something they certified.

**B27. The cost capture / valuation / cost model harness is adopted into this
package, not scaffolded beside it (2026-11-10, approved by the user via Execute
plan).** Reconciliation C1-C11 accepted as written: C1 harness agents run as job
tasks under B1, POST /runs starts a job run; C2 the seven read tools are UC SQL
functions, stage_proposal and run_cost_model_scenario are orchestrator-side
Python tools; C3 the /ask agent's run_sql is outside the harness (removal is the
user's call); C4 application and source-view objects use the prefixes
aircarrier_app_ and aircarrier_srcv_ in the one schema until an admin provides
schemas; C5 rules with no source feed are seeded blocked_no_source, never
approximated; C6 role groups and row filters need account-admin action; C7 add a
staging target, il5 is prod; C8 the claim gate constants are flagged, not moved;
C9 atomic apply depends on warehouse multi-statement transactions, verified
first; C10 the no-source-write check is a grep plus SHOW GRANTS job; C11 the API
is a FastAPI router under app/api/v1/.

**B28. The five harness parameters, as answered by the user on 2026-11-10.**
Recorded verbatim from the user's selections:
1. CAP-05: "Seed CAP-05 unset; CAP rules emit a 'baseline not provided' gap".
2. AV-06: "Preliminary acceptance".
3. CC-01 WBS level: "Level 3 (as specified)".
4. On-behalf-of-user auth: "Yes: add OBO (sql scope) to the front-center app".
5. Checker endpoint: "Different family (gpt-5-5 or gemini), after a
   tool-calling probe".
No value other than these was chosen on the user's behalf.

**B29. The harness works with the project owner's current role and the
existing service principals; nothing depends on an administrator (the user,
2026-11-10).** Creating a service principal or an account group is admin-only
(SCIM 403), so neither is used.
1. Agent principal = the front-center app SP 7e1ec6c0. The orchestrator runs
   inside that app; its grants are deploy/grants_harness_agent.sql. It reads
   source data only through the aircarrier_srcv_* views: api/live.py was
   repointed and its four src_ base-table SELECTs are revoked. Net grants were
   simulated from the live grant list: no src_ grant, MODIFY on five
   aircarrier_app_ tables only.
2. Authority-bearing calls (apply, reject, POST /rules) run on the caller's
   on-behalf-of token, never on the app SP (B28.4).
3. Roles resolve from identity without account groups: aircarrier_app_role_map
   holds either a UC group (checked with is_account_group_member) or a user
   email (checked against current_user() under the OBO token). Either way it
   is the identity Databricks authenticated, never a request field or a UI
   selector. The table is owned and written only by the schema owner. Row
   filters on component tables use the same lookup. When groups exist, rows
   move from emails to groups with no code change.
4. Weaker than separate principals, recorded rather than hidden: the app and
   the agent share one identity. So the app's read-only SELECTs on the
   app-derived stores are also visible to the agents. The agents still reach
   them only through the parameterized tools, never through free SQL.
5. Found, not changed: dinne.kopelevich1@cms.hhs.gov holds schema-wide
   SELECT, EXECUTE and READ_VOLUME on users.xiaobing_shang1_civ. It is
   read-only, but it covers every harness table.

**B30. Rule evaluation engine and job (task 8).**
1. ops/harness/evaluate.py: pure function `evaluate(trigger, triggered_by,
   rule_ids=None)` — reads current_rules view, binds table placeholders and
   named params, executes each, writes exceptions stamped with rule_version and
   eval_id. Returns dict with eval_id and per-rule results. Writes a
   rule_evals summary row (array of structs via ARRAY/named_struct, not
   from_json, because from_json silently returns NULL in INSERT VALUES).
2. Expression_sql must not contain embedded SQL string literals. All string
   values in expressions are named params (`:param_name`) and _bind replaces
   them with properly single-quoted literals. This avoids the sq()
   double-escaping problem (sq() doubles all single quotes for the INSERT, so
   `'CC-01'` becomes `''CC-01''` and stores without the intended quotes).
3. Three expressions delivered: CC-02 (escalation timer, reads exceptions
   table), CM-01 (EAC growth QoQ using LAG window function over model_runs —
   correlated scalar subquery unsupported in Spark), CM-02 (stale inputs using
   LATERAL VIEW OUTER explode of MAP<STRING,TIMESTAMP>).
4. ops/entrypoints/eval_job.py: serverless job entrypoint with --rule, --trigger,
   --triggered-by args. Exits 1 on any rule error.
5. resources/jobs.yml: aircarrier_rule_eval job, scheduled daily at noon ET,
   PAUSED until first deploy.
6. Acceptance tested: CC-02 correctly detects 50-day-old open CC-01 exceptions
   and ignores 10-day-old ones. Invariant 2 confirmed: lowering
   escalation_days from 45→5 detected both items, restoring to 45 detected
   only the overdue one.
7. deploy/seed_rules.py updated: v1 expressions use the fixed parameterized
   forms. Live table has v2/v3/v4 of the 3 rules from iterative fixes.
8. Test artifacts in exceptions and model_runs tables from tool and eval tests.

**B31. Orchestrator, checker, and specialist profiles (task 9).**
1. ops/harness/specialists.py: 5 specialist profiles (cost_capture, evm,
   cost_cap, valuation, cost_model), each with a system prompt and a
   frozen tool_allowlist (invariant 3: narrow agents). Common read tools
   (get_exception, get_rule, get_document_text) + one area-specific tool +
   stage_proposal.
2. ops/harness/orchestrator.py: run_exception(exception_id) loads the exception
   via get_exception, selects specialist by area, builds the tool set from the
   allowlist, runs the OpenAI-compatible tool-calling loop (MAX_STEPS=8), writes
   agent_runs and agent_steps. stage_proposal receives _run_id from the
   orchestrator (invariant 6: the model never knows the run_id). Model chain
   from env vars (AIRCARRIER_REASONING_MODEL / _FALLBACKS), defaulting to
   seed/models.yaml reasoning role.
3. ops/harness/checker.py: check_proposal(proposal_id) re-reads the proposal,
   verifies grounding completeness (structural check, no model), then calls the
   checker model (AIRCARRIER_CHECKER_MODEL / _FALLBACKS, default gpt-5-5 /
   gemini-3-8-flash per B28.5) for consistency check. Writes checker_verdicts.
   Fail blocks the proposal.
4. agent_steps CHECK constraint citation_complete: specialist steps must have
   rule_id, rule_version, and non-empty record_ids. Orchestrator steps are
   exempt (agent_name = 'orchestrator').
5. ops/entrypoints/harness_job.py: processes open exceptions, runs orchestrator
   then checker for each. --exception-id, --dry-run, --skip-checker flags.
6. resources/jobs.yml: aircarrier_harness job, daily 12:30 ET, PAUSED.
   Depends on databricks-sdk for the model call.
7. Acceptance tested with mock model: 3 tool steps (get_exception, get_rule,
   stage_proposal), 1 proposal staged, checker pass verdict, all rows verified
   in agent_runs, agent_steps, proposals, checker_verdicts.
