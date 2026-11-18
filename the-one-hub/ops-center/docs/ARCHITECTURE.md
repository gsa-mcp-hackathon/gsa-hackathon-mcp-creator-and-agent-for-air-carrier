# Ops center and front center architecture

This document owns the build design. Intent, the layer model, the trust zones
and the investigation model live in `../../BLUEPRINT.md` and are not restated
here. Decisions live in `../../LOG.md` Part I and are referenced by number.

## What is being built

Six agents, four shared stores, one dispatcher.

The ops center is the automation of a loop that has already been run by hand
six times between 2026-11-06 and 2026-11-08, with every component already
written in prose. The build is a transcription plus replacing the one
component that is a person.

| Component | Where it already exists | Status |
|---|---|---|
| claim ledger | `ring0/RING0_CVN79.md` Part N | tagged, scored, closes to zero on two axes |
| selector registry | Part G | `seed/keyset.yaml` |
| mechanism store | BACKGROUND, D1-D34, I.3, K.3, L.3 | ~40 rules |
| variance ledger | Part E | E-1 to E-15, `seed/variances.index.yaml` |
| collection requirement queue | LOG Part II | G1 to G28, `seed/gaps.index.yaml` |
| policy set | LOG Part I | `core/policy/decisions.py` |
| falsification | `checks/falsify.py`, N.7 | `seed/negative_vocabulary.yaml` |
| reconciliation suite | `checks/recon_v3.py`, `checks/verify.py` | `ops/agents/tieout/` |
| orchestrator | a person | `ops/dispatcher/` |

## The four stores

| Store | Schema | Holds |
|---|---|---|
| Source catalog | `source` | document profiles, exhibit registry with hazards, system catalog |
| Mechanism store | `mechanism` | rules with their establishing passages |
| Claim ledger | `claim` | values with full coordinates, tag, confidence, lineage |
| Work register | `work` | gaps, collection requirements, variances, states, risk flags, gate misses |

Plus three schemas that are not stores:

- `leads` is firewalled. It carries no grant that permits a join to `claim`.
  D16 says the firewall is structural rather than procedural, and a schema with
  no join grant is structural in a way a confidence column is not.
- `capture` takes front-center human input. INSERT only. No UPDATE, no DELETE.
- `serving` holds the only views the app may read.

This is the common knowledge layer. It is what makes six agents one system.

## The six agents

### Investigator
Unknowns in, hypotheses and collection requirements out. Build first: discovery
is the phase the project is in and every other agent is downstream of knowing
where to look. Never asserts a value.

Ranks its queue on **exposure x ignorance x closability**, not on dollars
alone. Publication ranks on materiality; discovery ranks on what is worth
spending the next hour on. This is why G16, the GFP Position Report, currently
outranks G22, the propulsion attribution: G22 is five times larger and G16 is
free.

Hand-run equivalents in the record: Part M, the clue map, and Part F.

### Reader
Documents in, typed knowledge out. Three handlers by document kind.

| Handler | Documents | Produces |
|---|---|---|
| exhibit | SCN book, SAR, MSAR, budget exhibits | cells with full coordinate chain and page legends |
| prose authority | SUPSHIP SOM, OPNAVINST, FMR, FMPM, GAO, DODIG, FASAB | mechanisms, implications, contradictions, questions |
| transaction | USAspending, FPDS extracts | aggregations under the D33 and D34 constraints |

The rule the exhibit handler exists to enforce: never return a cell without its
coordinate chain and every legend on its page. Both of the worst errors in the
record are prevented by that storage rule rather than by a stronger model.

The prose handler's output contract has four parts: mechanisms, implications,
contradictions, questions. A pass that returns only facts has not finished.
Build it before the exhibit handler, because mechanisms are what the
Investigator needs and the Investigator ranks everything else.

Documents are read more than once. Parsed text and page images are retained so
re-reading costs inference only. E-12 is the worked example of why.

### Tie-out
Deterministic. No model, ever. If a check needs judgment it emits a flag and
stops. Build second, before extraction: the asset it protects exists today and
the asset extraction would add does not.

### Challenger
Tries to break a claim or a reconciliation and sets the four risk flags. Never
promotes. `checks/falsify.py` is the prototype; `seed/negative_vocabulary.yaml`
is the vocabulary it tests against.

### Attributor
Crosswalk and identity resolution. Scored candidates only, never a silent
merge, never EXACT. Deliberately last: it needs real extracts to validate
against. The hard case here is not the ledger seam, it is cross-command GFE.

### Briefer
Audience-specific explanation. Never introduces a figure not in the ledger.
Trust state travels with every number at every level.

## The workflow

```
OPEN QUESTION  (gap, unexplained variance, residual above floor)
      |  Investigator: hypotheses + collection requirements, ranked
      v
COLLECTION REQUIRED
      |  routed by CR type
      |  DOCUMENT -> fetch     DATA -> query
      |  SME -> human queue    CATALOG -> human inside
      |  IRREDUCIBLE -> terminal, bounded estimate
      v
MATERIAL IN HAND
      |  Reader: extracts, mechanisms, profile
      v
CANDIDATE
      |  Challenger: risk flags      Tie-out: deterministic checks
      v
GATED
      |  routing table -> promote | human review | hold candidate
      v
PROMOTED
      |  closes the question?
      |    yes -> close gap
      |    no  -> residual re-enters as OPEN QUESTION
      |  emits: new gaps, new mechanisms, sometimes a new decision
      +-------------------------------------------------> loop
```

Two properties make it work rather than run.

**It is re-entrant.** A promoted claim or a new mechanism can invalidate
earlier work, which marks affected rows STALE and re-enters them at the tie-out
stage. Discovery never closes, so the pipeline cannot be a DAG.

**Agents never call each other.** Every handoff is a state change on a row.
That is what makes them lego: any agent can be replaced, a new one inserted, or
two implementations run on the same queue and compared. An agent that calls
another agent welds the architecture shut.

## Platform decisions

**B1. Ops agents run as job tasks, not on the Databricks agent runtime.**
Agent Bricks CLI and DurableAgentServer target interactive, served agents.
The ops agents are batch workers over a queue: they need no invocation API and
no chat UI. Job tasks plus model serving endpoints are also the primitives most
likely to exist in the DoD environment, where the agent runtime is a Beta
feature that may not be present. Each agent's core stays a pure function with a
typed signature, so a second thin entry point wrapping it in MLflow
`ResponsesAgent` can be added later without touching the agent.

**B2. Model access goes through Unity Gateway, by role and not by name.**
Agents ask for `role="reasoning"` or `role="extraction"`. The binding is in
`seed/models.yaml`. Swapping a model is a config change in one file.

**B3. The embedding model is chosen for IL5 portability, not for benchmark
position.** `system.ai.bge-large-en` over `models.ai.text-embedding-3-large`:
system.ai models are Databricks-provided and are the ones most likely to exist
after transfer, where an external-provider embedding endpoint almost certainly
will not. Choosing the portable one now avoids re-embedding the corpus later.

**B4. Declarative Automation Bundles are the only deploy path.** Nothing is
created by clicking in the workspace, because anything created outside the
bundle does not transfer.

**B5. `app/` is a self-contained transfer unit.** Advana FM needs its own
GitLab repo with the Dragon pipeline for the App, and that pipeline gets `app/`
and nothing else. `core/` is vendored into `app/_core/` by
`tools/sync_core_to_app.py`.

**B6. Genie is a front-center tool only.** A Genie answer is not a claim and
has no coordinate chain, so it cannot satisfy D27 and never enters the ops
center path.

## The front center

FastAPI serving the JSON API and fourteen server-rendered pages from one process (B12). Charts are
server-side SVG with no library and no CDN (B13). Data comes through a two-backend interface, files
or Unity Catalog views, so the app runs with no workspace at all (B14).

| Page | What it carries |
|---|---|
| Overview | The three sentences, the two-axis close, attribution, layer coverage, the work queue |
| Kennedy | Identity, specifications, the 35-event dated spine with source on every row, construction gallery |
| Cost | Category and funding-stream decomposition, attribution, equipment line items by vendor |
| Execution | Both primes, the FY obligation curve and the FY2017 handoff, transaction classification, hull attribution scan, appropriation map, largest actions |
| Baseline | The three ceilings, the estimate across nineteen submissions coloured by mechanism, the anchor chain as a waterfall, statutory cap history |
| Industrial base | The integrator, major systems by command, and the tier-two sub-award map |
| Asset | CIP status, the three structural divergences, the CIP relief question, government property |
| Variance register | E-1 to E-15, filterable by status and risk flag |
| Gap register | G1 to G28, the discovery bubble chart, sortable table with exposure and closability |
| Coverage | The six layers with what would change each, the clue map, the asks in order of cost |
| Sources | Document families with what each carries and its limit |
| Insight capture | Contribution against a named gap, graded on the two Admiralty axes |
| Method | Trust zones, the three recorded errors, where AI sits and the one rule |
| Build progress | Phases by what controls their duration, and what will not be realistic |

The write path is the one in `app/README.md`: the app writes evidence and intent, never facts.
INSERT only on the capture schema, attributed to the authenticated user rather than to the app
service principal.

## Build order

| # | Build | Why here |
|---|---|---|
| 1 | Seed the source catalog and mechanism store | Transcription of Parts C, H, M and D1-D34. No access, no egress, no model. Everything is downstream |
| 2 | Tie-out | Deterministic. Protects the asset that exists today |
| 3 | Investigator, assisted mode | Discovery is the phase. Highest leverage per hour |
| 4 | Reader, prose handler | Mechanisms are what the Investigator needs most |
| 5 | Reader, exhibit handler | Then the figures |
| 6 | Challenger | Once there are candidates to break |
| 7 | Briefer | Any time after the spine has content |
| 8 | Attributor | After real extracts. Realistically after L2 |

Step 1 and the Investigator run by hand are what ships before the sponsor brief
in the 18 to 21 November window. Steps 2 and 3 if the platform gates clear
early. Everything else is defined and empty, shown as the pipeline's own
coverage map, which is the same move PLAN section 2 makes for egress.
