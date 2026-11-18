# Air Carrier program cost tracking

Tracking what a Ford-class aircraft carrier has actually cost, from program inception, with CVN-79
as the pilot for a department-wide enterprise capability. The core output is a defensible account of
how the cost is reported, how it was recorded, where those diverge, and why. Two deliverables: the
answer for this hull, and the transferable method. See `BLUEPRINT.md` section 3.

## The documents

Four files. Each fact has one home, and the others point to it rather than repeating it.

| Document | Job |
|---|---|
| `BLUEPRINT.md` | Intent and design. The problem, the drivers, the two deliverables, the design premise, the product surface, the six-layer model and its real topology, the variance record, cost scope, data trust, the investigation model and the community of practice, where AI goes, risk analysis, scaling and the transfer package, audiences, and the order of work. |
| `BACKGROUND.md` | Domain reference. How carrier appropriations work, the reporting artifacts and named offices, accounting system history, governing standards, the data environment, why carrier reconciliation is specifically hard, and dated CVN-79 facts. |
| `LOG.md` | Decisions (D1 to D21, settled, check before re-opening), gaps (G1 to G7, open, each typed with an executor), and the verification record. |
| `README.md` | This map. |
| `dbrepo/` | The Databricks build. Ops center and front center, one deploy path, IL5 transfer seam. Owns the build and restates none of the design. See `dbrepo/README.md`. |
| `PLAN.md` | Time-bound and disposable, unlike the four above. The delivery plan for the sponsor brief in the window of 18 to 21 November 2026: verification gates, the two-week prototype scope, the demo, scope and size framing, and the asks. Rewrite or delete after the brief. |

## Current state

**Design:** settled in prose. Consolidated from seven documents to four on 2026-11-06.

**Data:** `ring0/` holds the zero-access source layer. `RING0_CVN79.md` is the source catalog by
document family plus the identifier set that isolates this hull in budget and ledger data,
appropriation through contract number, with the public source disagreements kept as a variance
record. `ring0_research_notes.md` and `cvn79_funding_history.csv` hold the gate-check narrative and
the seed figures with their confidence grading. All of it is lead-grade material under D4, suitable
for pointing at authoritative sources and for the first variance ledger between public sources. The
two prose files divide by kind rather than by date, per D31.

**Build:** `dbrepo/` holds the Databricks build, started 2026-11-08. Structure, contracts,
policy and seed content are in place; agent bodies are iteration 2. The live deterministic
tie-out suite moved there from `analysis/`, which is now history.

**Parked:** `schema/` holds data definition work built before the design settled and revised three
times chasing it. Content absorbed into `BLUEPRINT.md`. See D12. Not the source of truth.

**Access:** none beyond public sources and budget execution data. The ledger hub, asset records, and
program management data all require sponsorship that has not been requested yet.

## Next step

Sponsor brief in the window of 18 to 21 November 2026, with a prototype front end in Databricks
Apps. `PLAN.md` has the two-week plan. The first two days are verification gates rather than build
work, because the serverless egress policy on the workspace determines whether live event capture is
possible at all and that answer changes the design.

The build itself is `BLUEPRINT.md` section 17 step 1 brought forward: the variance ledger from public
sources, hand-curated, with the coverage map and the gap register beside it.

## Gaps

In `LOG.md` Part II, typed by resolution method with an executor on each. Nothing in that register is
assigned to the sponsor. Of the four original gaps, two are closed by research, one is narrowed to a
single question for NAVSEA 01 or DFAS, and one is reframed around GAO-17-575's standing per-hull cost
reporting recommendation with three named offices to approach. Two opened in the process: NSMA as a
fourth Navy general ledger, and documented manual adjustment practice in NAVSEA shipbuilding CIP.
