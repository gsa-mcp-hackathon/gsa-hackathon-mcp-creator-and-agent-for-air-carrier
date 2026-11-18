# Working log: decisions and gaps

Two append-only registers. **Decisions** are settled questions, so check here before re-opening one.
**Gaps** are open questions, each typed with an executor, so this is a work queue.

Neither register restates the design. Each entry carries the decision or the finding and points to
`BLUEPRINT.md` or `BACKGROUND.md`, which own the full text.

---

# Part I. Decisions

Format: decision, reasoning, supersedes.

**D1. Pilot is CVN-79, and cost history runs from program inception rather than a chosen start
date.** A single hull keeps the layer model testable end to end, and a selected start date would
itself be an undocumented scope decision of the kind this effort exists to surface. Inception is a
stated modeling choice, since contract award, procurement year, and keel laying are all defensible.
See `BACKGROUND.md` section 7.

**D2. Method is funnel and onion-peeling.** Start from reported aggregates, work inward, tie each
layer before trusting the next. The alternative is assembling from transactions upward and hoping a
total emerges, which has no stopping condition and no way to know when the picture is wrong.
Starting from a published figure gives every later step something to disagree with.

**D3. Every fact carries the period it describes, separately from when it was found.** A figure
without a period cannot be compared to anything, which makes it unfalsifiable. A figure without a
discovery date cannot be audited for how the belief changed. Both are required and they are
different fields.

**D4. Public and secondary sources generate leads only.** They never support a conclusion on their
own. They are incomplete and inconsistent, and their value is pointing at the authoritative source.
Treating them as evidence contaminates the authoritative record with figures that cannot be defended.

**D5. Known limitations are carried forward visibly rather than resolved by presentation.** The open
items are the real state of the work. A polished surface over an unresolved gap transfers false
confidence to whoever reads it next, and that transfer is irreversible once a decision is made on it.

**D6. The product is the variance with its cause attached, not a single authoritative cost figure.**
The layers measure different things under different scope rules at different times, so convergence
to one figure is neither achievable nor desirable, and forcing it would destroy information. A
documented difference answers the question an auditor, a program office, and an independent estimator
each actually ask. So a difference with a documented cause is finished product, and only an
unexplained difference is incomplete.
*Supersedes:* the framing in which tie-out meant driving layers to agreement and any remaining
difference was an open item.

**D7. The layer topology is a hub and spokes with the ledger as the hub. The onion is the order of
approach, not the shape of the data.** Tested against the data: budget, asset, and program each tie
to the ledger on a different cut rather than forming a chain. The concentric model kept requiring
renumbering because a non-concentric structure was being forced into it. Reasoning in `BLUEPRINT.md`
section 8.
*Supersedes:* the strict concentric ring chain and the two rounds of renumbering applied to it.

**D8. Six layers: reported, budget, ledger, asset, program, evidence.** Applied the test of distinct
producer, purpose, and number characteristic. Asset accounting passes on its own and had been folded
into the ledger layer in error. For a ship, capitalized value and program cost diverge by
construction, so a model without a separate asset layer cannot represent the most predictable
disagreement in the picture.
*Supersedes:* the five-layer model, and the version treating asset valuation as a ledger attribute.

**D9. Cost scope is a variance cause, not a prerequisite decision.** Two layers routinely scope cost
differently by design and both are correct, so settling on one scope rule first would discard the
information that they differ. Standards in `BACKGROUND.md` section 4, application in `BLUEPRINT.md`
section 10.

**D10. Unreimbursed cost borne by another entity is in scope and requires explicit imputation.**
SFFAS 30 requires full cost to include goods and services received from other federal entities
without reimbursement. Such cost never appears in this program's own postings because it was never
charged there, so capturing it requires the providing entity's records plus a recorded method,
rationale, and approver. This is the one cost category that cannot be found by looking harder at the
program's own data.

**D11. The system must function at every access level, including zero.** Authority over
program-office data is granted by people on their own timeline and no capability substitutes for it.
If any layer were a precondition, the effort would stall on someone else's calendar. Public sources
already disagree about this hull, so a real variance ledger exists today with no access, and that
artifact is what the access conversation points at.

**D12. Database schema work is parked until the design is settled in prose.** Schema was built early
and revised three times as the layer model changed, which means it was tracking the thinking rather
than capturing it. Data definition language with constraints and approval columns reads as rigor and
substitutes for reasoning when the reasoning is not finished. The files remain in `schema/`; their
content is absorbed into the blueprint and they are not the source of truth for the design.
*Supersedes:* treating the schema files as the primary design artifact.

**D13. Risks are recorded only where they change a design decision.** Five recorded concerns were
tested against whether each changes anything in the design. Three converted into stated requirements:
graceful degradation under absent access, deliverable shape that makes incompleteness visible, and
reproducibility of allocation method. Two implied no design change and were removed. A concern that
changes no decision is decoration, and a document full of them reads as diligence while providing
none.
*Supersedes:* the standalone pushback and failure-mode sections in earlier versions.

**D14. Messy, incomplete data is the design premise, not an exception. The architecture is an
investigation apparatus before it is a reporting apparatus.** Named at the outset as the single
largest determinant of success or failure, and that is correct. A design treating incompleteness as a
condition to be cleared before operating will never operate.
*Supersedes:* the version that mentioned messiness once and then designed a comparison engine as
though inputs would arrive orderly.

**D15. Conflicting source values are retained with provenance, never resolved by selection.** Follows
from D6. If the product is the variance, two sources disagreeing about the same cell is the raw
material rather than a defect. Worth stating as a decision because selecting a golden record is the
default instinct of most data engineering practice, and here it is exactly wrong.

**D16. Unreliable material is quarantined in a zone with no join path to canonical data, and a lead's
only legitimate output is a Collection Requirement.** A confidence column is a label and can be
ignored; a zone with no join path cannot. Leads are graded on two axes using the Admiralty code,
because a named tradecraft framework survives review in a way ad hoc judgment does not. Totals
inherit the weakest trust state among their inputs.
*Supersedes:* the thinned four-state trust model written during the rebuild, which kept the state
names and dropped the Collection Requirement, the two-axis grading, the zone firewall, and
weakest-link aggregation. Those four did the actual work, and losing them was drift introduced by the
rebuild itself.

**D17. Unknowns are typed work items with assigned executors, and a gap is never assigned back to the
sponsor.** An open question with no owner and no method is parked, not managed. Typing a gap
determines who works it, and most apparent dead ends are document-answerable and merely unworked.
Tested immediately against four unknowns: two closed outright, one narrowed to a named office, one
reframed around an existing recommendation, none requiring access.
*Supersedes:* the open-questions section that listed four unknowns with no owner and thereby handed
them to the person who asked for the product.

**D18. The ledger layer for this program is two sources joined at a dated boundary, and this is
established fact.** STARS for FY10 and prior funding, Navy ERP for FY11 forward, ship construction
moving 1 April 2011, legacy data deliberately unconverted. Sourced in `BACKGROUND.md` section 3. The
design consequence is a two-source ledger layer with a documented boundary rather than one source
with an unexplained hole.

**D19. DoD FMR Volume 11B Chapter 12 does not govern the program office overhead and travel
question.** Volume 11B is working capital fund policy and the chapter's headquarters provisions
address DWCF activities. An appropriated-fund program office is not one. Authority stays with SFFAS 4
as amended by SFFAS 30 and FMR Volume 4 Chapter 19.

**D20. The hull-level cost allocation problem is an implementation question against an existing GAO
recommendation, not a methodology to invent.** GAO-17-575 already recommended per-hull life-cycle
cost estimates from NAVSEA 05C and per-hull cost and funding summary sections in the Ford-class SAR.
The correct first move is determining whether those were implemented, which either produces the
artifact or produces an unimplemented GAO recommendation. Either is stronger than inventing a method.
*Supersedes:* treating class-shared cost allocation as an open methodology question with no owner.

**D21. The document set is four files.** `README.md` as the map, `BLUEPRINT.md` for intent and design
and scaling, `BACKGROUND.md` for domain facts, `LOG.md` for decisions and gaps. Seven files had
accumulated with the same fact stated in up to four places, which is how the set drifts: an update
lands in one copy and the others silently go stale. Each fact now has one home and the other files
point to it.
*Supersedes:* `INTENT.md`, `ARCHITECTURE.md`, `GAPS.md`, `DECISIONS.md`, `docs/cost_scope_policy.md`,
and `docs/ai_agent_architecture.md`, all merged into the four and removed.

**D22. CVN-79 is the pilot for a department-wide enterprise capability, and there are two
deliverables: the answer for this hull and the transferable method.** The second is the larger one
and loses by default under schedule pressure, because the first is what gets asked for. Stating both
is what makes methodology work part of the deliverable rather than overhead on the way to it. The
transfer package is enumerated in `BLUEPRINT.md` section 15 so it cannot degrade into "read our
documentation and good luck."

**D23. The product surface is wider than the spine, and every element of it is either a view over
the spine or a graded input to it.** Program overview, execution, cost tracking, asset valuation,
insight, and detailed analysis are views over the layer model and variance ledger and need no new
architecture. The discipline replacing the old "anything else is out of scope" rule is that nothing
on the surface stands alone: a panel that cannot be traced back to the three spine artifacts is
commentary with a chart on it.
*Supersedes:* the narrower statement that anything not feeding the three artifacts is out of scope,
which was correct about discipline and wrong about scope.

**D24. Event and narrative material enters as L0 leads and feeds exactly two fields: cause evidence
and the Collection Requirement queue.** Congressional hearings, testimony, news, and legislative
action on the cap or appropriation are time-ordered external signal about the program. They add no
cause category, because the categories are mechanisms and a hearing is not a mechanism. What a
hearing supplies is evidence for a cause, dated and attributable to a named official, which is
stronger than anything derivable from the ledger alone: the ledger shows a number moved and never
says why. A figure quoted in news stays a lead at news-grade reliability permanently.

**D25. The community of practice is the executor for SME gaps, and the gap register is its work
queue.** A one-off interview captures one answer while the knowledge behind it leaves anyway, and
SME gaps decay on a retirement schedule. A standing department-wide community is the only resolution
path for those gaps and for some that would otherwise be irreducible. The register is the mechanism
rather than an adjunct to it: a general invitation to share knowledge produces nothing, while a
specific, named, dollar-ranked open question gives someone a reason to answer the one thing they
know without joining a project. Contributions enter through the trust model with no exception, as
graded, attributed, timestamped leads, and where two contributors disagree both are retained under
the conflict-retention rule. The failure mode designed against is an unreviewed free-text dump,
which is how knowledge-management efforts usually end; the defense is that a contribution lands
against a specific gap or has nowhere to land.

**D26. Risk analysis is derived from the variance ledger and the event stream, and there is no
composite risk score.** A risk item carries four things: the named mechanism, the historical
precedent in specific variance records, current dated signal, and a dollar exposure derived from the
precedent. Missing any of the four makes it an opinion with a number attached. No composite index,
for the same reason as D6: a single score hides the mechanism and the mechanism is the entire useful
content. Buildable in the pilot, since cap headroom, testimony, oversight findings, and the lead
ship's documented growth mechanisms are all public.

**D27. Drill-through is a requirement, not a styling choice.** Every displayed figure must be
navigable to the record supporting it and every variance to its evidence, with the trust state
traveling with the number at every level. This is what separates a product someone can challenge
from one someone has to believe. If a number cannot be drilled, it is not displayed.

**D28. The prototype platform is Databricks Apps, and event capture is a scheduled job writing to
Delta rather than a live fetch from the front end.** Apps run on serverless compute and inherit
serverless egress control, which is deny-by-default in restricted workspaces, so a front end that
fetches on page load is both a larger governance ask and a demo that breaks when a source is slow.
A scheduled job also satisfies the trust model, which requires a retrieval timestamp and source
citation on every item; a live fetch records neither.

**D29. Event capture is scoped to government sources for the prototype.** Congressional hearing
records, GAO, DODIG, Navy releases, and the Federal Register. This is not a compromise forced by the
egress constraint, although it does turn a hard egress request into an easy one. Under the grading
model these are materially better evidence than commercial trade press, which the design already
treats as the lowest-reliability material in the system, and a hearing where a program official
explains a cost increase is the strongest cause evidence available anywhere in the architecture.
Commercial news can be added later with nothing lost by its absence now.

**D30. Phases are presented to the sponsor classified by what controls their duration rather than
as a schedule.** Effort-controlled, access-controlled, or knowledge-controlled. This is more honest
than a Gantt chart, since the long pole is an access conversation whose duration is not ours to
estimate, and it is more useful to an SES because it shows where their own leverage actually is.
The knowledge-controlled class carries the decay argument, which is the only case for moving now
that does not depend on anyone's enthusiasm.

---

**D31. Ring 0 has a source catalog file separate from the research notes, and they divide by kind
rather than by date.** `ring0/RING0_CVN79.md` holds the source catalog by document family, the
identifier set (appropriation, budget activity, line item, program element, subhead, contract, CAGE),
the dated program spine, and the public source disagreements. `ring0/ring0_research_notes.md` keeps
the gate-check narrative and the secondary-source seed pass with its confidence grades, alongside
`cvn79_funding_history.csv`. The alternative was one growing Ring 0 file, rejected because the
catalog is a reference surface that gets queried while the notes are a chronological record that
gets appended, and the two age differently. Reconciliation between them is itemized in that file's
section E.0 so the one-home rule stays checkable rather than asserted.

---

**D32. Reconstruction of the hull total is carried as a separate, explicitly non-reportable analysis
layer rather than folded into the source catalogue.** `ring0/RING0_CVN79.md` Part N reasons past its
sources to bound how the thirteen billion dollar total is composed, tagging every line verified,
reported, derived, estimate, unknown or rejected, with a confidence score, and stating at the top and
the bottom that nothing in it may be reported as a figure. The alternative was to leave the question
unanswered until the data arrives, rejected because the bounding exercise is what identifies which data
to ask for, and because an audience will ask the question whether or not there is an answer prepared.
The discipline that makes this safe is the tagging plus one rule learned by failing: a confidence score
attached to a mis-populated model is worse than no number, because it launders the error. See the
rejected iteration recorded in that Part, where cost category proportions captured from the shipbuilding
justification book turned out to belong to a submarine line rather than a carrier line, and would have
produced a tidy and entirely wrong category breakdown. This is the concrete case for D16's rule that
unreliable material gets no join path to canonical data.

---

**D33. Obligation figures come from the obligation record only, and a press release is never a
record.** A reader-supplied federal extract showed the construction preparation contract had obligated
4,519,300,324 dollars where this effort had carried roughly 1,080,000,000, an understatement by a factor
of four. The earlier figure had been assembled by summing announced Department of Defense contract
modifications. That method cannot produce a contract total for three compounding reasons: daily contract
announcements have a dollar threshold and are silent below it; they omit incremental and installment
funding actions, which are the dominant obligation mechanism on a cost-plus shipbuilding contract and
carry two and a half billion dollars on this one; and they cannot net deobligations, of which this
contract has sixty eight totalling minus sixty seven million. The rule has a corollary that matters more
than the rule. **A large unexplained residual is a finding, not a remainder.** The error was knowable
without any new data, because the residual it created had been written down and then given a narrative
label rather than a test. Two procedural consequences, both now standing. Any figure entering the
variance ledger as an obligation must name its source system, and the only acceptable sources are the
federal procurement data system, the federal spending transaction record, or the accounting system.
And externally supplied data gets a mandatory re-derivation pass rather than a reconciliation pass:
the question asked of it is not whether it agrees with what is held, but what method produced what is
held. Supersedes nothing; constrains D4 and D15 to the obligation case. See `ring0/RING0_CVN79.md`
sections N.4 and N.7, and E-13.

**D34. Identifier collisions are registered as named hazards with hard exclusions, not left to
reviewer memory.** The hull's construction preparation contract is N00024-09-C-2116. The contract for
the two following hulls is N00024-16-C-2116, and it carries a fourteen point nine billion dollar
modification. Same trailing four digits, seven years apart, three different hulls. Any partial match,
trailing-digit join or fuzzy contract comparison silently merges them, and the merge is undetectable
downstream because every other attribute looks right. The decision is that collisions of this kind go
in the quick-reference key set as explicit exclusions, in the gap register as catalogue work, and in
every query template as a hard filter on full contract number. The general form of the rule: where two
keys differ only in a position a human reads past, the defence is a constraint in the query rather than
a note in the documentation. Opened as G28. See `ring0/RING0_CVN79.md` section N.6b and E-15.


# Part II. Gap register

Gap types and the rules governing them are in `BLUEPRINT.md` section 12. The governing rule, repeated
because it is the one most easily drifted away from: **a gap is never assigned back to the sponsor.**

## G1. Which accounting systems carried this program's postings, and when
**RESOLVED 2026-11-06. `DOCUMENT`, executed by AI research.**

Answered from the NAVSEA Supervisor of Shipbuilding Operations Manual Chapter 4, which is
authoritative for this. NAVSEA entered Navy ERP 1 October 2010 for FY11 funds, ship construction and
other complex contracts were held to 1 April 2011, and NAVSEA general fund deliberately did not
convert legacy data, so FY10 and prior retains STARS. Full detail and the STARS instance and module
breakdown in `BACKGROUND.md` section 3. Design consequence recorded as D18.

## G2. Whether SABRS is in scope for this program
**NARROWED 2026-11-06. `DOCUMENT` done, residual `SME`.**

SABRS is the Marine Corps ledger, but Navy budget documentation describes it as serving the Marine
Corps and select Navy budget submitting offices, so a Navy BSO on SABRS is a real configuration
rather than an error. Against that, the NAVSEA source in G1 is specific that NAVSEA used STARS then
Navy ERP, and GAO lists SABRS as the Marine Corps system while naming four Navy ledgers.

**Residual question, now askable in one sentence:** was any budget submitting office carrying CVN-79
funds ever among the select Navy BSOs on SABRS, or did SABRS enter through a different route such as
a working capital fund activity performing program work. **Ask NAVSEA 01 (Comptroller) or DFAS.**
Moderate decay risk, since this concerns configuration from more than a decade ago.

**Sharpened 2026-11-07, still residual.** A named migration project gives this a concrete object to
check against rather than a general SABRS question: the Navy ran an actual STARS-to-SABRS (S2S)
project, FMP-4, to move Navy Budget Submitting Offices from STARS-FL onto SABRS ahead of later Navy
ERP consolidation. The question for NAVSEA 01 or DFAS is now specifically whether NAVSEA or PEO
Carriers' BSO was among the offices S2S moved. Source: `ring0/ring0_research_notes.md`, 2026-11-06
gate-check pass (highergov.com program profile for SABRS; SECNAV FMP-4 project description). This
does not close G2; it is the asks-list item in `PLAN.md` section 6.

## G3. Whether DoD FMR Volume 11B Chapter 12 governs program office overhead and travel
**RESOLVED NEGATIVE 2026-11-06. `DOCUMENT`, executed by AI research.**

It does not apply. Recorded as D19, citations in `BACKGROUND.md` section 4. Closing this also
surfaced FMR Volume 4 Chapter 23's allocation convention, now carried in the same section.

## G4. Hull-level cost and the shared class R&D allocation method
**REFRAMED 2026-11-06. `DOCUMENT` done, residual `DATA` and `SME`.**

Was framed as a methodology to invent. GAO-17-575 already recommended per-hull life-cycle cost
estimates from NAVSEA 05C starting with CVN-80, and per-hull cost and funding summary sections within
the Ford-class SAR. Detail in `BACKGROUND.md` section 6. Recorded as D20.

**Open work:** determine whether either recommendation was implemented. If the per-hull sections
exist, the hull-level figure is a document to retrieve rather than a number to derive. **Three named
doors: NAVSEA 05C, NCCA, CAPE.** Highest dollar materiality of any gap here, since it governs every
hull-level figure the product produces.

## G5. Full inventory of systems feeding the Advana financial management environment
**OPEN. `CATALOG`, executor is someone inside using that environment's own catalog.**

Known elements are in `BACKGROUND.md` section 5. Permanently partial by nature, and the design
accounts for that rather than waiting on it, per D11. Completeness is not a precondition for
anything. Two named feeders already matter: the procurement environment for contract evidence, and
the travel system, which holds the fund citation settling the travel scope question empirically.

## G6. NSMA, the fourth Navy general ledger
**OPEN, opened 2026-11-06. `DOCUMENT` then `SME`.**

GAO records the Navy as operating four general ledgers: STARS-FL, STARS-HCM, Navy ERP, and Navy
Systems Management Activity. NSMA was in neither the original three-system scope nor anything built.
Determine what it carried and whether any of it touches shipbuilding. Opened by the G1 and G2
research, which is the register working as intended.

## G7. Construction in progress for NAVSEA shipbuilding uses manual adjustments
**OPEN, opened 2026-11-06, externally corroborated already. `DATA` then `SME`.**

The Navy's FY2025 agency financial report and DODIG-2013-105 both bear on this; detail in
`BACKGROUND.md` section 6. Valuable rather than discouraging: the asset layer has documented,
officially acknowledged manual adjustment practice, which is a ledger-to-asset variance cause with
external corroboration attached before this project has queried anything. Determine the nature and
magnitude of those adjustments for this hull, which needs the data and then someone who prepares
them.

---

## G8. The Navy ERP subhead to NWA/WBS mapping that isolates this hull
**OPEN, opened 2026-11-07. `SME` then `DATA`. Executor: NAVSEA 01 (Comptroller) or DFAS.**

Shipbuilding and Conversion, Navy is the one Department of the Navy appropriation that is line item
appropriated, and the Department's financial management policy manual states that the four digit SCN
subhead encodes the budget activity and the P-1 line, one per position. The line of accounting data
dictionary states that the subhead maps to the Navy ERP NWA or WBS. Taken together, the subhead is a
structural pointer from the ledger to the Carrier Replacement Program line.

**Question:** obtain the Navy ERP subhead table and the NWA or WBS node that distinguishes CVN-79
from CVN-80 and CVN-81 within budget line item 2001. Sources and the reasoning in
`ring0/RING0_CVN79.md` section D.2.

Highest value gap opened by the 2026-11-07 public research pass. Until it is answered the budget
layer cannot be split by hull in the ledger, which blocks the hull answer rather than delaying it.
Low decay risk, since this is current system configuration rather than historical fact.

## G9. Whether the payment path changed mid-program when MOCAS entitlement moved to Navy ERP
**OPEN, opened 2026-11-07. `DOCUMENT` then `SME`. Executor: DFAS Columbus or SUPSHIP Newport News.**

Shipbuilding progress payments are entitled in the Defense Finance and Accounting Service
Mechanization of Contract Administration Services system, and shipbuilding is the documented
exception to Defense Contract Management Agency administration, with the Supervisor of Shipbuilding
administering instead. A publicly briefed integration targeted end of month July 2025 for front end
entitlement in MOCAS with disbursement from Navy ERP direct to Treasury.

**Question:** did CVN-79 progress payments run through MOCAS for the whole life of the detail design
and construction contract, or did some portion move after that integration, and on what date.

This is a fourth dated seam, in the payment path rather than the ledger, and it decides whether the
disbursement population for this hull is one source or two. Detail in `ring0/RING0_CVN79.md` D.5.

## G10. The established obligation work limiting date for this hull
**OPEN, opened 2026-11-07. `DOCUMENT`. Executor: NAVSEA or Navy FMB.**

The obligation work limiting date is where financial responsibility transfers from construction
accounts to fleet operating accounts, and all new work identified after it is the fleet's to correct
with non-construction funding. The Department sets an end date with Treasury for each appropriated
SCN year, and that end date is the last ship obligation work limiting date.

**Question:** CVN-79's established OWLD as set with Treasury.

This is the empirical end boundary of construction phase cost, and therefore the concrete answer to
the scope question D9 treats as a variance cause and G3 closed only at the standards level. Resolve
the definitional conflict first: OPNAVINST 4700.8M sets OWLD at eleven months after completion of
fitting out, while the NAVSEA SCN desk reference states thirteen months after delivery. Those
produce different dates. Both citations in `ring0/RING0_CVN79.md` D.12 and E-3.

## G11. Cost and software data reporting submissions for this hull
**OPEN, opened 2026-11-07. `DATA`. Executor: OSD CAPE Defense Cost and Resource Center, via CADE.**

The cost and software data reporting system is the only route to cost below the appropriation line
structured by work breakdown rather than by appropriation. The contract plan is a DD Form 2794. This
program spans two reporting regimes: the DD 1921 series for its early years and the Cost and Hour
Report (FlexFile) afterward.

**Question:** retrieve the approved plan and the submissions for both eras.

Note this is a third seam, in the program layer, independent of the ledger and platform seams. The
two regimes are not the same structure, so a continuous series cannot be assumed. Detail in
`ring0/RING0_CVN79.md` D.9.

## G12. Which costs the FY2016 authorization act excluded from the cost caps
**OPEN, opened 2026-11-07. `DOCUMENT`. Executor: Navy FMB or Office of General Counsel.**

The provision that lowered the follow on cap to $11,398.0 million also amended the basis for
adjusting the caps for inflation and excluded certain costs from being counted against them. The
excluded set is not described in the secondary record.

**Question:** which cost categories are excluded, and on what authority.

This changes what the statutory cap measures, and therefore the meaning of the three ceiling spread
the product is expected to lead with: statutory cap, Secretary of the Navy cost limitation baseline,
and budget submission total procurement cost. Recorded as E-1 in `ring0/RING0_CVN79.md`.

## G13. Rework cost from the 2024 welding deviations
**OPEN, opened 2026-11-07. `DATA` then `SME`. Executor: NAVSEA or SUPSHIP Newport News.**

In September 2024 the shipbuilder self reported to the Navy and the Department of Justice that
welders had knowingly circumvented welding procedures. The House Armed Services Committee opened an
investigation, and the Secretary of the Navy told lawmakers that twenty six ships were affected.
Ford class carriers under construction were in the analysis population. No cost was ever made public.

**Question:** was any CVN-79 rework cost booked, and against which contract line and appropriation
year.

Small in likely dollars and deliberately kept anyway. It is a named, dated public event with no
public cost attached, which makes it the cleanest available end to end test of the event stream
feeding cause evidence and of the variance ledger carrying a cause through to a figure.

---

## G14. When construction in progress is relieved for this hull
**OPEN, opened 2026-11-08. `DOCUMENT` then `SME`. Executor: Navy Office of Financial Operations or NAVSEA.**

Financial Management Regulation Volume 11 is not the governing text here; Volume 4 Chapter 25 is, and it
superseded the Chapter 6 that most secondary sources still cite. That chapter ties relief of construction
in progress to the date the asset is placed in service in one paragraph and to acceptance of constructed
items in another. This hull reached preliminary acceptance on 29 September 2026 and is scheduled for
delivery in March 2027, and preliminary acceptance is explicitly not delivery.

**Question:** does relief trigger at preliminary acceptance, at delivery, or at commissioning, and which
document records the determination.

The three candidate dates straddle a fiscal year boundary, so the answer decides which year an asset of
roughly thirteen billion dollars appears on the balance sheet. Detail in `ring0/RING0_CVN79.md` section I.1.

## G15. Whether installed government furnished equipment is capitalized separately or inside the hull
**OPEN, opened 2026-11-08. `SME` then `DATA`. Executor: Navy Office of Financial Operations, Program
Executive Office Aircraft Carriers, Naval Air Systems Command PMA-251.**

The launch and recovery shipsets, the eleven weapons elevators and the air surveillance radar array are
each far above the one million dollar Department of the Navy capitalization threshold, and each is bought
on a different contract by a different command from the hull.

**Question:** is each capitalized as its own item of general equipment, or rolled into the vessel's
capitalized value.

Both answers are defensible and only one can be right. If both the hull record and the system record
capitalize the item the Department double counts it; if neither does it drops out. This is the asset-layer
twin of the attribution problem the budget layer has at G8. Detail in `ring0/RING0_CVN79.md` section I.3.

## G16. Government furnished property held by the shipbuilder for this hull
**OPEN, opened 2026-11-08. `DATA`. Executor: a Government Furnished Property Module role holder, or
SUPSHIP Newport News.**

Reporting of government property in contractor custody is mandatory through the Government Furnished
Property Module of the Procurement Integrated Enterprise Environment, with a seven business day clock on
status changes, and that module produces a position report keyed by contractor commercial and government
entity code or by contract number.

**Question:** run that position report for entity code 43689 scoped to both of this hull's contracts, and
cross-check items carrying a registered unique item identifier against the item registry.

Cheapest high value request in the whole research pass. The population is defined, the key exists, the
report already exists, and no new access path is needed. It also matters more than its cost suggests:
reporting of government property in contractor possession has been an audit material weakness since fiscal
year 2001, and GAO reported in 2025 that the Defense Contract Management Agency and the Navy's Supervisors
of Shipbuilding were not consistently verifying the accuracy of contractor property records on selected
major programs. SUPSHIP Newport News administers both of this hull's contracts, so this is the local test
of a department wide weakness. Detail in `ring0/RING0_CVN79.md` Part J.

## G17. What the dagger footnote marks on three cost analysis rows
**OPEN, opened 2026-11-08. `DOCUMENT`. Executor: Navy Office of Budget.**

The shipbuilding justification book's cost analysis exhibit carries a dagger on the electronics, hull
mechanical and electrical, and ordnance rows and on no others.

**Question:** what the footnote designates.

Those three are the categories most likely to be government furnished. If the dagger marks government
furnished content, then the budget exhibit already carries the split between government and contractor
furnished equipment that the property records do not, which would make the exhibit a bridge between the
budget layer and G15 rather than merely a cost breakdown. Detail in `ring0/RING0_CVN79.md` section K.1.

## G18. The cost analysis column for this hull, every year it was published
**OPEN, opened 2026-11-08. `DOCUMENT`, executable with no access. Executor: AI research or analyst reading.**

The cost analysis exhibit uses a fixed category set across hulls: plan costs, basic construction, change
orders, electronics, propulsion equipment, hull mechanical and electrical, ordnance, other cost, then
deductions for advance procurement, subsequent full funding and cost to complete by fiscal year. Columns
captured in the 2026-11-08 research pass belong to later hulls, not to this one.

**Question:** read this hull's column out of each year's book.

This produces a category by year variance rather than a total by year variance, which is the first real
deliverable of the variance ledger and requires no access at all. It pairs with the year over year contract
tables in the acquisition report. It should be done before any access is requested, because it is the
strongest thing that can be built from nothing. Detail in `ring0/RING0_CVN79.md` section K.1.

## G19. Content expensed rather than capitalized under the capitalization threshold
**OPEN, opened 2026-11-08. `DATA`. Executor: Navy Office of Financial Operations.**

The Department of the Navy general fund capitalization threshold for general equipment is one million
dollars, raised from one hundred thousand in October 2013. Items below it are expensed even when physically
installed on the ship.

**Question:** the magnitude of that expensed tail for this hull.

Sizes one of the three structural reasons capitalized value can never equal program cost, the other two
being timing and the boundary conflict recorded at E-3. Low urgency, real materiality, and it bears directly
on any claim that the balance sheet value represents what the ship cost. Detail in `ring0/RING0_CVN79.md`
section I.3.

---

## G20. Shipset prices for this hull's weapons elevators, radar suite and combat system
**OPEN, opened 2026-11-08. `DATA` then `SME`. Executor: Program Executive Office Aircraft Carriers,
NAVSEA, Naval Surface Warfare Center Philadelphia, Naval Air Systems Command.**

The eleven advanced weapons elevators, the air surveillance and surface search radar suite, and the
self defence and cooperative engagement combat system are each named in the public record, each is
certain to be individually large, and none has a published shipset price for this hull.

**Question:** the shipset cost of each, for this hull.

Together they are the largest identified block inside the untraced residual, which the 2026-11-08
correction pass reduced from roughly five billion dollars to 3,252 million, or twenty four per cent of
the hull,
in the reconstruction. Detail in `ring0/RING0_CVN79.md` sections N.5 and N.6.

## G21. Base award value of the January 2009 construction preparation contract
**CLOSED 2026-11-08.** The base award was 111,803,875 dollars on 15 January 2009 against solicitation
N0002408R2116, cost plus fixed fee, not competed under the single source authority with one offer
received. Lifetime obligations on the contract are 4,519,300,324 dollars across nine hundred and forty
eight actions. It was never unpriced; the base award was below the departmental announcement threshold,
which is why no announcement existed to find. See D33 and E-13.


---

## G22. Vendor level attribution of the propulsion equipment category
**OPEN, opened 2026-11-08. `DATA` then `SME`. Executor: Naval Reactors, NAVSEA, Department of Energy.**

The propulsion equipment category for this hull is 2,041.582 million dollars, fifteen point two per cent
of the ship and the second largest category in it. The shipbuilding justification book itemises equipment
by vendor for most categories and itemises none of this one.

**Question:** where that money goes, by vendor and contract.

Largest single unattributed block in the hull. Who builds the plant is established, the reactor design by
Bechtel Marine Propulsion and the core and fuel by BWX Technologies, with funding crossing into the
Department of Energy. What is absent is the money. This supersedes the propulsion portion of G20.
Detail in `ring0/RING0_CVN79.md` sections N.6 and N.8.

## G23. Outfitting and post delivery attributable to this hull
**OPEN, opened 2026-11-08. `DOCUMENT` then `DATA`. Executor: Navy Office of Budget, Program Executive
Office Aircraft Carriers.**

The budget line item justification shows outfitting and post delivery only as an informational row for
the whole carrier replacement line: eight hundred and ninety million in prior years, then sixty five,
one hundred and two and one hundred and twenty six million across fiscal years 2025 to 2027, totalling
one thousand seven hundred and sixty seven million across all hulls on the line.

**Question:** this hull's share.

Outfitting is the line that carries spares, which is the population G16 asks the shipbuilder to report,
so the two gaps answer the same question from opposite ends. Detail in `ring0/RING0_CVN79.md` section N.8.

---

## G24. Obligations on the construction preparation contract after its period of performance ended
**OPEN, opened 2026-11-08. `DOCUMENT` then `SME`. Executor: Supervisor of Shipbuilding Newport News;
Naval Sea Systems Command contracts.**

Contract N00024-09-C-2116 shows a published period of performance ending 31 July 2025, and 133.4 million
dollars obligated in fiscal year 2026, including a single sixty million dollar action dated 3 December
2025 described as advance construction. That is seventeen years after award and after the stated end of
performance.

**Question:** are these in-scope closeout actions, a period-of-performance extension not reflected in the
procurement record, or a data error?

Decides whether construction preparation obligations are still live cost or administrative cleanup, and
therefore whether the handoff boundary between the two prime contracts used throughout the reconstruction
is stable. Also bears on the obligation work limiting date analysis. Detail in
`ring0/RING0_CVN79.md` sections N.4 and D.12.

---

## G25. Award level outlay reporting for this hull covers under one per cent of obligations
**OPEN, opened 2026-11-08. `DATA` then `SME`. Executor: Defense Finance and Accounting Service Columbus;
Navy Office of Financial Operations; Office of the Under Secretary of Defense (Comptroller) spending
transparency reporting.**

Across the two prime contracts, 9,097.9 million dollars obligated carries 72.6 million dollars of
reported outlays, 0.80 per cent. The detail design and construction contract reports zero. The shipbuilder
has plainly been paid billions, so this is not a payment fact, it is a reporting fact: award level outlay
data reaches the public record through the award level financial submission, and the department's linkage
from that submission to disbursement is incomplete.

**Question:** what is the actual award level disbursement series for both contracts, and why does the
public submission not carry it?

This is the fund balance with Treasury and property-in-possession-of-contractors weakness appearing in
public data rather than in an audit report, which makes it unusually citable. Two standing consequences
until closed. No cost product may present outlay or expenditure figures sourced from the public spending
record for this hull. And the Advana financial management query must take disbursement from the mechanized
contract administration system or from Navy ERP directly. Detail in `ring0/RING0_CVN79.md` section N.4.

---

## G26. Full enumeration of contracts carrying scope for this hull, built outward from the ship
**OPEN, opened 2026-11-08. `DATA`. Executor: anyone with federal procurement data system or public
spending record access.**

Both authoritative contract catalogues are closed lists, and neither is a list of contracts that build
the ship. The selected acquisition report contract table names seven contract numbers for a thirteen point
four billion dollar ship, because it lists only the efforts under cost and software data reporting
surveillance. The shipbuilding justification book names vendors, contract types and award months for
equipment line items but prints no contract numbers at all. A contract held by a systems command for
equipment that is neither a surveilled major-programme effort nor printed in the budget exhibit is
invisible to both catalogues at once, which is how three contract numbers supplied from outside this
research came to be absent from it.

**Question:** the full contract population, queried on product service code 1901 aircraft carriers,
acquisition programme code 223, and funding office code N30270, across all contracting activities.

The systematic fix for a gap that was previously taken to be a completeness problem and is actually a
catalogue-design problem. Detail in `ring0/RING0_CVN79.md` section N.6a.

---

## G27. Two General Atomics contracts held by the systems command, scope unidentified
**CLOSED 2026-11-08, same day it opened. `DATA`. Closed against the federal procurement data system ATOM
feed, exact-match and free-text, with a control query. Neither contract belongs to this hull. One of them
never belonged to the vendor it was carried under. The lookup opened E-16.**

N00024-14-C-4201 and N00024-18-C-4100, both General Atomics, both systems command rather than air systems
command. Neither appears in any selected acquisition report, budget exhibit or justification book held in
`ring0/reference/`. Neither can be the launch and recovery shipset money, which is air systems command
contract N00019-14-C-0037 and is already carried in the hull at 830.438 million dollars, so adding either
on that assumption would double count.

**Question:** scope, platform, and whether any content for this hull exists that is not already counted.

A five minute lookup for anyone with a browser. It was attempted from the research session and refused by
network policy rather than by the data. Detail in `ring0/RING0_CVN79.md` section N.6a.

**Closed.** The public spending record route was refused again by the same allowlist, so the federal
procurement data system ATOM feed was queried directly instead. Result on both numbers, and the control:

- **N00024-18-C-4100 is not General Atomics.** It is **VERICOR POWER SYSTEMS LLC**, 19,169,760 dollars
  firm fixed price, signed 22 November 2017 by the systems command headquarters under solicitation
  N0002418R4100, one action, treasury account 17/1611, government furnished property flagged yes. The
  description is an ETF40B power producer group assembly for **LCAC 86**, a landing craft air cushion.
  Not this hull, not a carrier, and not the vendor the number was carried under.
- **N00024-14-C-4201 does not appear.** Absent from both the award and the indefinite delivery vehicle
  indexes, on exact match and on free text.
- **Control:** N0002409C2116 returned a complete record from the same feed in the same session, 948
  actions, base 111,803,875 dollars, 15 January 2009, cost plus fixed fee, funding office N30270, with
  the construction preparation effort description. The feed works, so the absence above is the finding
  rather than a failed query.

Neither number may be used as a cost source for this hull, which is where the gap started, but the reason
is now established rather than assumed. The register had carried both for a day on an inherited vendor
label that nobody had tested, and the test cost one query each. Recorded in the key set as
`resolved_not_this_hull`, keeping both numbers visible so the labels cannot be re-inherited.

**What this gap cost, and what it bought.** It was opened as a completeness question about two contracts.
It closed as an attribution error in the source that supplied them: a vendor name attached to a contract
number by inference and then carried as fact. That is the same failure as E-12 and E-13 and the third
instance of it in this effort, which is why D4 now reads as it does. The lookup also surfaced E-16.

---

## G28. The 2116 contract number collision, registered as a hard exclusion
**OPEN, opened 2026-11-08. `CATALOG`. Executor: this repository, then the Advana financial management data
product owner.**

N00024-09-C-2116 is this hull's construction preparation contract. N00024-16-C-2116 is the detail design
and construction contract for the two following hulls, carrying a 14,917,738,145 dollar modification
awarded 31 January 2019. A third number, N00024-17-C-2117, appears in the same report tables with scope
unconfirmed.

**Question:** this is catalogue work rather than a question. The collision pair must be registered as an
explicit exclusion in the quick-reference key set, in every query template built from this dossier, and
in the Advana view, as a filter on full contract number rather than a note for a reviewer.

The most dangerous identifier hazard found so far, because a partial match merges three hulls and nothing
downstream reveals it. See D34. Detail in `ring0/RING0_CVN79.md` section N.6b and E-15.

---

## G29 to G65. Adopted from the investigator's proposed gaps

Adopted 2026-11-09, at the user's request, from `aircarrier_proposed_gaps` (run
`investigator-65a84c4f589d`, proposed 2026-11-09 02:18Z). Each was raised by the investigator from a
prose question it could not attach to an open gap, and each keeps its `PQ-` id so the mechanism ids,
question ids and plan trace remain one join away in that table. Every one carries seven collection
requirements in `aircarrier_collection_requirements`, and none dropped a hypothesis. Question and
blocks text is verbatim from the table. Exposure is not yet sized for any of them, so they rank on
closability and default ignorance until it is. `Related` notes are a reader's cross-reference, not a
merge: the investigator judged each one uncovered by the register, and both judgments are retained.
Duplicates in substance are marked `overlaps`; merge them only by closing one against the other.

## G29. The 2004 CVN 21 acquisition decision memorandum and its quantity basis
**OPEN, opened 2026-11-09, adopted from PQ-1a85a2d3. `DOCUMENT`, closability access_required.
Executor: Milestone Decision Authority / USD(A&S) acquisition document repository.**

**Question:** Can the April 26, 2004 CVN 21 Program Acquisition Decision Memorandum be obtained to verify
the scope and quantity basis of its low-rate initial production decision?
**Blocks:** The reported production quantity rests on a dated decision memorandum; without it the
quantity basis behind class-level estimates cannot be tied to the hull.

## G30. Records retention for this hull's payment records
**OPEN, opened 2026-11-09, adopted from PQ-1d2ba631. `CATALOG`, closability query.
Executor: DCMA records management / agency records officer.**

**Question:** What records retention and storage rules govern the CVN-79 payment records being requested
(per the cited DCMA records-management volumes and the DCMA Records File Plan), and do they establish that
the records for the hull's award years are still retrievable?
**Blocks:** If retention periods have expired for early hull years, the reconciliation must rely on
substitute sources and the record gap must be stated.

## G31. Reimbursable and project orders for this hull, and who records them
**OPEN, opened 2026-11-09, adopted from PQ-2114e407. `DATA`, closability access_required.
Executor: SUPSHIP Comptroller and PEO Aircraft Carriers (reimbursable order register / Navy ERP).**

**Question:** Which CVN-79-related reimbursable work orders, project orders and RCP-funded tasks exist,
and which performing activity owns the accounting record and obligation-recording event for each?
**Blocks:** Reimbursable and project-order work obligates at acceptance and is accounted for by the
performing activity, so costs recorded outside SUPSHIP's own ledger would be omitted or double counted in
the hull reconciliation.

## G32. Test scope in the DOT&E reports and the CVN 78 and Enterprise TEMPs
**OPEN, opened 2026-11-09, adopted from PQ-21555673. `DOCUMENT`, closability access_required.
Executor: DOT&E and the CVN-78 program office test and evaluation master plan library.**

**Question:** Can the FY2001 and FY2025 DOT&E annual reports, CVN 78 TEMP Revision F, and Enterprise TEMP
1910 be obtained to determine the coordinated test scope and which test activities are funded inside the
CVN-79 construction effort versus by separate programs of record?
**Blocks:** Test scope determines whether SSDS, CEC and other coordinated test activity costs belong in
the CVN-79 hull reconciliation or to separate program ledgers, which changes the content included in the
hull total. Overlaps G36: same two TEMPs.

## G33. Transaction-level support for this hull's funding and payment actions
**OPEN, opened 2026-11-09, adopted from PQ-28d0c320. `DOCUMENT`, closability access_required.
Executor: SUPSHIP Newport News Comptroller (document request via NAVSEA FM).**

**Question:** Can SUPSHIP produce the transaction-level supporting documentation for CVN-79 funding and
payment actions, specifically the NAVCOMPT Form 2275 and ERP-generated Form 2276A work requests, the ERP
approval histories and attachments for purchase requests, funding documents and project structures, and
the written delegations of funds authority with the related certifying-officer payment documentation?
**Blocks:** Without the underlying work requests, ERP approval trails and certification records,
commitments, obligations and disbursements attributed to CVN-79 cannot be traced to documentary support or
tied to the correct purpose, leaving the reconciliation unverifiable. Related: G9.

## G34. Ship acceptance records and SUPSHIP's certification role
**OPEN, opened 2026-11-09, adopted from PQ-35b8c6a7. `DOCUMENT`, closability access_required.
Executor: SUPSHIP Newport News; GAO report source files.**

**Question:** What do GAO-2018a and GAO-2022a, and the underlying SUPSHIP acceptance and inspection records
they cite, establish about ship acceptance documentation and SUPSHIP's role in certifying completed work
for CVN-79?
**Blocks:** Acceptance records govern when work is deemed complete and therefore which costs belong to
delivery versus post-delivery periods in the reconciliation. Related: G23.

## G35. EMALS baseline change 3 and its cost scope
**OPEN, opened 2026-11-09, adopted from PQ-3d37c3fb. `DOCUMENT`, closability access_required.
Executor: NAVAIR PMA 251 program office / Milestone Decision Authority baseline files.**

**Question:** Can EMALS Acquisition Program Baseline Change 3 and the original-baseline risk documentation
be obtained to establish how the EMALS baseline was qualified and what cost scope it carried?
**Blocks:** Separating EMALS subprogram baseline cost from hull construction cost. Related: G59, G61.

## G36. Systems on this hull that differ from the lead ship's tested configuration
**OPEN, opened 2026-11-09, adopted from PQ-518fc9b3. `DOCUMENT`, closability access_required.
Executor: DOT&E / PEO Aircraft Carriers test and evaluation office.**

**Question:** Can CVN-78 TEMP Revision F and the Enterprise Air Warfare TEMP 1910 be obtained to establish
which CVN-79 systems differ from the lead ship's tested configuration and what tests are planned for them?
**Blocks:** Without the test scope for CVN-79-unique combat system and radar configurations, test,
trials, and retrofit work cannot be separated from lead-ship or other-program costs when attributing them
to the hull. Overlaps G32: same two TEMPs.

## G37. What the Ford-class acquisition program baseline covers for this hull
**OPEN, opened 2026-11-09, adopted from PQ-5665638c. `DOCUMENT`, closability access_required.
Executor: PEO Aircraft Carriers (PMS 378) program office / Milestone Decision Authority baseline file.**

**Question:** Can the Ford-class Acquisition Program Baseline be obtained to determine exactly which cost
measures, ship quantities, and increments it covers for CVN-79?
**Blocks:** If the baseline covers the class rather than the hull, baseline cost measures cannot be used as
the reconciliation anchor for CVN-79 without an explicit hull allocation. Related: G4, G40.

## G38. The per-ship assumptions behind the Navy O&S estimate
**OPEN, opened 2026-11-09, adopted from PQ-60482249. `DOCUMENT`, closability access_required.
Executor: NCCA (Naval Center for Cost Analysis) and OPNAV N43/N98 maintenance notice holders.**

**Question:** Can the Navy Component Cost Estimate and the referenced OPNAV maintenance notices be obtained
to trace the per-ship operating and support assumptions, including ship count, service life and
inactivation treatment, down to a single hull?
**Blocks:** The O&S total is derived from average annual cost per ship times ship count and service life,
so without the underlying assumptions no per-hull O&S figure can be derived or reconciled for CVN-79.

## G39. Contractor debts and collections against this hull's contracts
**OPEN, opened 2026-11-09, adopted from PQ-6172e5ba. `DOCUMENT`, closability access_required.
Executor: Responsible DCMA ACO; DFAS Columbus debt management.**

**Question:** Do any contractor debt determinations or collection actions exist against the CVN-79
contracts (handled under DCMA's contractor-debt procedures rather than through the financing-request
stream), and can the debt and demand-letter records be obtained?
**Blocks:** Debts and collections are credits against the hull's recorded costs; omitting them would
overstate net cost.

## G40. Whether any hull-level or sub-program baseline exists
**OPEN, opened 2026-11-09, adopted from PQ-69390d94. `DOCUMENT`, closability access_required.
Executor: PEO Aircraft Carriers (PMS 378) acquisition program baseline records / ASN(RDA) baseline
repository.**

**Question:** Do separate acquisition program baselines, MDAP increment baselines, or sub-program baselines
exist for the CVN-79 capabilities managed under the Ford-class program, and if so which office holds them?
**Blocks:** Without knowing whether a CVN-79-specific baseline exists, reconciliation cannot determine
whether any authoritative hull-level cost baseline exists to reconcile against, or whether only
class-level baselines are available. Related: G4, G37.

## G41. The shipbuilder's integrated master schedule as a deliverable
**OPEN, opened 2026-11-09, adopted from PQ-6b0e0de0. `DOCUMENT`, closability access_required.
Executor: NAVSEA PMS 378 / shipbuilder contract data requirements list.**

**Question:** Can the shipbuilder provide the current integrated master schedule with advanced-construction
status, and does the detail-design-and-construction contract require exportable schedule data as a
deliverable that was in fact delivered?
**Blocks:** Progress measured in dollars cannot be validated against physical construction status,
including advanced construction, without an exportable up-to-date schedule; percent-complete inputs to the
reconciliation stay unverifiable.

## G42. Whether an independent cost estimate was ever made for this hull
**OPEN, opened 2026-11-09, adopted from PQ-74429161. `DOCUMENT`, closability query.
Executor: GAO published reports / Navy CAPE and program office independent cost estimate file.**

**Question:** Can the GAO (2017b) report cited for the independent-estimate and milestone history be
obtained to verify when independent cost estimates were prepared for individual carriers and which
milestone decisions they supported?
**Blocks:** Whether any independent cost estimate was ever produced for CVN-79 specifically determines if
an external hull-level comparison point exists for the reconciliation. Related: G4.

## G43. ACO-approved versus disbursed financing payments
**OPEN, opened 2026-11-09, adopted from PQ-79adb445. `DATA`, closability access_required.
Executor: Responsible DCMA ACO and DFAS Columbus contract pay.**

**Question:** For CVN-79 performance-based-payment or financing activity, can the ACO-approved payment
amounts and the payment office's actual disbursed amounts be obtained and compared, and were any
differences pursued and resolved?
**Blocks:** Unreconciled differences between approved and disbursed financing amounts would leave the
hull's disbursement total unverified. Related: G9, G25.

## G44. Cost for this hull carried in other programs of record
**OPEN, opened 2026-11-09, adopted from PQ-7dc2992b. `DATA`, closability sme.
Executor: PMS 378 government-furnished-equipment cost sponsor list and the responsible other-program
offices.**

**Question:** Which outside-program records (for technologies developed by programs other than the carrier
program) carry CVN-79-related content, and how, if at all, are those costs reflected in or excluded from
CVN-79 program records?
**Blocks:** Costs residing in other programs of record determine whether the hull reconciliation is
understating installed capability or double counting amounts also reported in those programs' own
submissions. Related: G15, G16.

## G45. The 2015 Service Cost Position and the O&S cost-element structures
**OPEN, opened 2026-11-09, adopted from PQ-8c81891f. `DOCUMENT`, closability access_required.
Executor: NAVSEA 05C / NCCA (Naval Center for Cost Analysis).**

**Question:** Can the April 2015 Department of the Navy Service Cost Position memorandum and the CAPE 2020
operating and support cost-element structure guidance be obtained to establish the independent estimate's
scope and to map indirect support across the 2015 and current estimates?
**Blocks:** Making O&S estimate comparisons like-for-like before attributing differences to the hull.
Overlaps G54 on the CAPE cost-element structure guidance; the Service Cost Position memorandum is this
gap's alone.

## G46. What CLIN 0001 covers, against the contract performance report
**OPEN, opened 2026-11-09, adopted from PQ-9c84f959. `DOCUMENT`, closability access_required.
Executor: PEO Aircraft Carriers (PMS 378) contracting file / NAVSEA 02 contracts office.**

**Question:** Can the CVN-79 detail design and construction contract CLIN schedule and the contract
performance report be obtained to establish what CLIN 0001 covers and to reconcile the CLIN-level
completion measure with the whole-contract work-completed measure?
**Blocks:** Converting reported contract completion percentages into a hull-level progress and cost basis.

## G47. The program deviation report and the baseline change that followed
**OPEN, opened 2026-11-09, adopted from PQ-a62e3390. `DOCUMENT`, closability access_required.
Executor: PEO Aircraft Carriers program office / Milestone Decision Authority correspondence file.**

**Question:** Can the CVN-79 Program Deviation Report and the subsequent acquisition program baseline
change be obtained to establish the approved schedule baseline and any associated cost baseline change?
**Blocks:** Fixing the approved baseline against which hull cost variance is measured.

## G48. MOCAS field definitions and the contracts' payment clauses
**OPEN, opened 2026-11-09, adopted from PQ-a8652d97. `CATALOG`, closability access_required.
Executor: DFAS Columbus MOCAS system documentation office; contract file holder.**

**Question:** Can the MOCAS User Guide and the payment and receiving-report clauses incorporated in the
CVN-79 contracts be obtained, to establish the meaning and completeness of the MOCAS data fields used in
the reconciliation?
**Blocks:** Without field-level definitions, MOCAS extracts cannot be mapped to obligation and
disbursement categories used in the reconciliation. Related: G9.

## G49. Class development funded in shipbuilding rather than RDT&E
**OPEN, opened 2026-11-09, adopted from PQ-ac29b248. `DATA`, closability access_required.
Executor: NAVSEA FMB / PMS 378 budget execution records for SCN line 1611N and the RDT&E-to-SCN strategy
change file.**

**Question:** Which appropriation accounts and program records document the Ford-class development work
that was directed into shipbuilding accounts rather than RDT&E, and how is that content identified within
CVN-79 shipbuilding records?
**Blocks:** If class development was funded through shipbuilding accounts, that content may be embedded in
hull construction figures and would be double counted or wrongly attributed to CVN-79 construction unless
identified. Related: G4, G8.

## G50. The prescribed equipment valuation and CIP relief record formats
**OPEN, opened 2026-11-09, adopted from PQ-ba0bdc8d. `DOCUMENT`, closability access_required.
Executor: ASN (FM&C) Office of Financial Operations.**

**Question:** Can SECNAV M-5200.45 and the cited DON financial-reporting references, including reference
(w) and enclosure (2) paragraph 4l asset-list specifications, be obtained to establish the prescribed
equipment valuation, CIP relief, and quarterly reporting record formats and whether those records identify
CVN-79?
**Blocks:** Knowing which prescribed records can carry hull-identifiable equipment valuation and CIP
relief evidence. Related: G14, G15, G60.

## G51. Which program of record carries each capability modification
**OPEN, opened 2026-11-09, adopted from PQ-bebcd323. `DOCUMENT`, closability access_required.
Executor: ASN(RD&A) acquisition policy office / PEO Aircraft Carriers program documentation.**

**Question:** How were the CVN-79 capability modifications (updated combat system, replacement radar,
AAG/AWE changes) managed under SECNAVINST 5000.02G reporting provisions and DoDI 5000.80 MTA naming,
reporting, and scope rules, and which program of record carries each cost?
**Blocks:** Costs managed under a separate program or MTA belong to that program's records, not the hull,
so scope boundaries must be fixed before attributing modification costs to CVN-79. Related: G20.

## G52. The sources behind the antecedent carrier O&S estimate
**OPEN, opened 2026-11-09, adopted from PQ-bf51ebc4. `DOCUMENT`, closability access_required.
Executor: OPNAV N9 / NAVSEA cost engineering (VAMOSC program office).**

**Question:** Can the cited source estimating references for the antecedent carrier operating and support
estimate, specifically the June 2022 OPNAV 4700 letter, the CVN 68 Ship Manpower Document, and the
underlying VAMOSC extract, be obtained to reproduce the antecedent O&S comparison?
**Blocks:** Validating the antecedent baseline used in O&S comparisons that frame hull cost growth.

## G53. The FY2026 budget submission's full funding, AP and cost-to-complete lines
**OPEN, opened 2026-11-09, adopted from PQ-bfcb40e8. `DOCUMENT`, closability query.
Executor: Office of the Assistant Secretary of the Navy (Financial Management and Comptroller), FMB - SCN
budget justification books.**

**Question:** Can the Navy's FY2026 budget submission, including Table 1's annual full-funding,
advance-procurement, and cost-to-complete lines for CVN-79, be obtained to verify the budget presentation
underlying the reported procurement and cost-to-complete amounts?
**Blocks:** Without the underlying SCN budget exhibits, budget estimates cannot be separated from recorded
obligations and outlays, so appropriation-year funding cannot be tied to hull cost in the reconciliation.
Related: G18.

## G54. CAPE O&S cost-element structures, 2014 and 2020
**OPEN, opened 2026-11-09, adopted from PQ-c8684acc. `DOCUMENT`, closability access_required.
Executor: OSD Cost Assessment and Program Evaluation (CAPE).**

**Question:** Can the CAPE 2014 and 2020 operating-and-support cost-element structure guidance be obtained
to map Indirect Support between the 2015 independent estimate and the current estimate?
**Blocks:** Without the two cost-element structures the sustainment estimates cannot be placed on a
like-for-like basis, so any sustainment figure carried into the reconciliation is non-comparable.
Overlaps G45.

## G55. The approved acquisition strategy and its review tailoring
**OPEN, opened 2026-11-09, adopted from PQ-d09f38c9. `DOCUMENT`, closability access_required.
Executor: PEO Aircraft Carriers program office; ASN(RD&A) acquisition strategy approval file.**

**Question:** Can the approved CVN-79 acquisition strategy and its shipbuilding-review tailoring
documentation be obtained to identify which reviews, decision points, and reporting events actually
applied to this hull?
**Blocks:** Tailored or combined milestones determine which dated cost estimates and reports exist for the
hull, setting the available reconciliation checkpoints.

## G56. Estimate-at-completion documentation held by DCMA
**OPEN, opened 2026-11-09, adopted from PQ-d0b14fc4. `DOCUMENT`, closability access_required.
Executor: DCMA contract management office / Program Support Team for the shipbuilder, via the responsible
ACO.**

**Question:** For the CVN-79 contracts administered by DCMA, what estimate-at-completion and
cost-to-complete documentation exists (Program Support Team collaboration site EACs, contractor-provided
EAC/ETC methods and periodic updates, and the semiannual ACO reports to the PCO and program integrator),
and can it be obtained?
**Blocks:** Without contractor EAC/ETC documentation, reported costs for the hull cannot be reconciled to
projected completion cost or tested against physical progress.

## G57. The new-construction berthing adjustment in the O&M estimate
**OPEN, opened 2026-11-09, adopted from PQ-d331ac6b. `DOCUMENT`, closability access_required.
Executor: OPNAV N9 / ASN (FM&C) budget policy.**

**Question:** Can the Navy policy governing the new-construction berthing adjustment in the CVN 78 class
acquisition O&M budget estimate be obtained to establish that adjustment's scope and whether any portion
is hull-attributable?
**Blocks:** Deciding whether a budgeted berthing adjustment belongs in hull cost.

## G58. The November 2018 two-ship buy certification and its exclusions
**OPEN, opened 2026-11-09, adopted from PQ-d4890327. `DOCUMENT`, closability access_required.
Executor: OUSD(A&S) / PEO Aircraft Carriers (PEO CVN) certification file.**

**Question:** Can the November 2018 DoD Ford Class Aircraft Carrier Certification and its supporting GFE
and shipbuilder savings estimates for the CVN-80/81 two-ship buy be obtained to identify what was excluded
and which hulls were covered?
**Blocks:** Unverified GFE and savings estimate boundaries risk mis-attributing two-ship-buy or GFE amounts
to CVN-79 in the reconciliation. Related: G65, G28.

## G59. Whether the EMALS long-lead and shipset contracts overlap
**OPEN, opened 2026-11-09, adopted from PQ-d6a755ff. `DOCUMENT`, closability access_required.
Executor: NAVAIR PMA 251 contracting officer / contract files.**

**Question:** Can the CVN-79 EMALS long-lead-time-material contract and the subsequent EMALS shipset
contract records be obtained to establish whether their reported amounts overlap or are additive for this
hull?
**Blocks:** Avoiding double counting of EMALS content in hull cost. Related: G26, G35, G61.

## G60. The budget submitting office's quarterly asset submissions
**OPEN, opened 2026-11-09, adopted from PQ-d7b5136e. `DATA`, closability access_required.
Executor: NAVSEA Budget Submitting Office financial reporting / ASN (FM&C) quarterly submission
repository.**

**Question:** Can the responsible Budget Submitting Office provide its quarterly asset-universe submissions
for the CVN-79 asset balances, including the APSR-to-general-ledger reconciliations, the
budgetary-reporting reconciliation, field-level journal vouchers, and trial-balance extraction parameters?
**Blocks:** Tying hull equipment and CIP balances to reported general-ledger amounts. Related: G7, G14,
G50.

## G61. Whether the EMALS subprogram estimates sit inside the CVN 78 estimates
**OPEN, opened 2026-11-09, adopted from PQ-dd15e896. `DOCUMENT`, closability sme.
Executor: CVN-78 Class MSAR preparer (PMS 378 business financial manager) and the EMALS program office.**

**Question:** What documentation establishes whether the EMALS subprogram acquisition, O&S and MILCON
estimates are included within or additional to the CVN 78 subprogram estimates?
**Blocks:** If EMALS subprogram estimates overlap the CVN-78 subprogram estimates, combining them double
counts launch and recovery content in the CVN-79 reconciliation; if additive, omitting them understates
it. Related: G35, G59.

## G62. Which office is accountable for this hull's equipment
**OPEN, opened 2026-11-09, adopted from PQ-e7aa6f1a. `SME`, closability sme.
Executor: PEO Aircraft Carriers (PMS 378) with NAVSEA Command Property Officer.**

**Question:** Which lifecycle-management responsibilities for CVN-79 equipment are assigned under the cited
DON lifecycle-management reference, and which PEO and supporting BSO therefore carry financial
accountability and reporting for that equipment?
**Blocks:** Identifying the accountable office whose records must be reconciled for hull equipment.
Related: G15, G16.

## G63. What the governing authorities require at ship versus class level
**OPEN, opened 2026-11-09, adopted from PQ-efe41def. `DOCUMENT`, closability access_required.
Executor: ASN(RDA)/Navy acquisition policy office and the CVN-78 program office APB/statutory reference
file.**

**Question:** What do the governing acquisition and reporting authorities for this program require as to
ship-level versus class-level reporting and baseline scope, specifically SECNAVINST 5000.02G, the FY2013
National Defense Authorization Act provisions cited in the MSAR, 10 USC 8671, and APB Change 5's treatment
of disposal costs within the O&S objective?
**Blocks:** These authorities define whether hull-level figures must exist, what the cost caps and
full-funding rules cover, and whether disposal sits inside or outside the O&S objective; misreading them
would misdraw the boundary of what the reconciliation is allowed to count. Related: G4, G12.

## G64. The FY2007 split-funding authority and its scope
**OPEN, opened 2026-11-09, adopted from PQ-f0037537. `DOCUMENT`, closability query.
Executor: Public statute text / Navy Office of Legislative Affairs.**

**Question:** Can the FY 2007 National Defense Authorization Act split-funding authority and its detailed
terms be obtained to establish what funding scope that authority permitted for the carrier construction?
**Blocks:** Determining which appropriation years legitimately carry hull construction cost.

## G65. The Section 121(b) certification against CAPE's two-ship savings estimate
**OPEN, opened 2026-11-09, adopted from PQ-f124b1bc. `DOCUMENT`, closability access_required.
Executor: OSD CAPE and ASN(RDA) two-ship-buy certification file.**

**Question:** Can the Section 121(b) certification package and the CAPE independent two-ship savings
estimate be obtained to compare their treatment of government-furnished equipment and production change
orders?
**Blocks:** The GFE and production-change-order treatments drive how shared two-ship savings and GFE
purchases are split, which directly changes amounts attributable to CVN-79. Related: G58.

---

# Part III. Verification record

What was checked rather than assumed, and what remains unverified. Added at the consolidation pass
because "verified" is a claim that should itself be auditable.

**Verified against primary or authoritative sources during this effort:** the NAVSEA system of record
seam and the non-conversion decision (NAVSEA SUPSHIP Operations Manual Chapter 4); SABRS ownership
and its select-Navy-BSO scope (GAO-12-132, GAO-24-106313, Navy budget documentation, Marine Corps
order); the four Navy general ledgers (GAO-12-132); Navy ERP's current system-of-record status
(GAO-26-107119); Volume 11B Chapter 12's scope (the chapter itself, both the current and the prior
titled version); the GAO per-hull recommendations and the CVN-79 estimate assessment (GAO-17-575, and
the case study in GAO-20-195G); CIP manual adjustment practice (Navy FY2025 agency financial report)
and the military equipment valuation weakness examination (DODIG-2013-105); SFFAS 4, SFFAS 30, and
the implementing FMR volumes and chapters.

**Internal consistency checked at consolidation:** layer numbering and the hub-and-spoke description
agree across all four files; the variance cause categories in the blueprint match the reconciliation
difficulties listed in the background; the gap identifiers G1 through G7 referenced from the blueprint
and background all exist here; decision numbering runs D1 through D21 without gaps or duplicates; the
single order-of-work sequence replaced two overlapping ones; the gap type table now appears once.

**Carried as stated but not independently verified:** the Advana environment description in
`BACKGROUND.md` section 5, which comes from direct report rather than documentation, including the
fifteen minute Navy ERP cadence and the periodic-update status of legacy data. The three GL systems
originally named for scope, which G2 partially addresses. The current form and repository of
acquisition reporting for this program. The CVN-79 figures and milestones in `ring0/`, which are
lead-grade by design and need primary-source confirmation before use beyond lead purposes. DODIG-
2012-051's finding that Navy ERP did not post standard financial information structure (SFIS) and
USSGL-compliant transactions at cutover, and the NAVSEA command-versus-BSO-level scope of that
finding, which comes from the `ring0/` gate-check pass and needs primary-document confirmation.

---

# Changelog

- **2026-11-06.** Decision log created, replacing an activity-style gate-check log that recorded which
  files changed on which day. That is history without reasoning and does not prevent drift. A decision
  with its reasoning can be held against a later proposal, which is the purpose.
- **2026-11-06.** Gap register created, replacing an open-questions list that had no owners.
- **2026-11-06, consolidation.** Merged the decision log and gap register into this file, stripped
  design restatement from both so each entry points to the owning document, added D21 and the
  verification record.
- **2026-11-07, enterprise scope.** Added D22 through D27 covering the enterprise-pilot framing and
  the two deliverables, the product surface and the rule keeping it tied to the spine, the event and
  narrative stream, the community of practice as SME executor, derived risk analysis, and
  drill-through as a requirement. No gap was closed or opened by this pass. Note that the community
  of practice is the mitigation for the SME decay risk that the register had been carrying with none,
  which is why it moved to step 3 of the order of work rather than sitting late in the sequence.
- **2026-11-07, delivery plan.** Added D28 through D30 for the prototype platform decisions, and
  `PLAN.md` for the sponsor brief in the 18 to 21 November window. `PLAN.md` is deliberately outside
  the durable four, since it goes stale on a known date. Verified against Databricks documentation
  that Apps inherit serverless egress control, that pypi.org must be allowlisted for the app build
  itself in a restricted workspace, that apps are reachable only by authenticated users in the same
  Databricks account, and that a `*.databricksapps.mil` serving domain exists for AWS GovCloud DoD.
- **2026-11-07, reconciliation pass.** Folded `ring0/ring0_research_notes.md`'s 2026-11-06 gate-check
  findings into the durable files rather than leaving them stranded in the research notes. Sharpened
  G2 with the named STARS-to-SABRS (S2S) / FMP-4 migration project as the concrete object behind the
  residual NAVSEA 01 / DFAS question. Added DODIG-2012-051's Navy ERP SFIS/USSGL non-compliance finding
  to the verification record as carried-but-unverified. `BACKGROUND.md` received the matching cost-cap,
  accounting-history, GAO-17-575, and dated-facts updates in the same pass. No gap was opened or
  closed; G2 was narrowed in specificity only.
- **2026-11-07, public data research pass.** Added `ring0/RING0_CVN79.md` as the Ring 0 source catalog
  and identifier set, and D31 for the division of labor against `ring0/ring0_research_notes.md`.
  Opened G8 through G13 from that research: the Navy ERP subhead to NWA/WBS mapping, the MOCAS to
  Navy ERP entitlement seam, this hull's obligation work limiting date, the cost and software data
  reporting submissions, the FY2016 cap exclusions, and the 2024 welding rework cost. Sharpened G5
  with a specific sub-question, whether STARS-HCM as distinct from STARS-FL is ingested into the
  Advana financial management environment, since only STARS-FL appears on public source lists and the
  answer decides whether FY2007 to FY2010 cost for this hull is reachable there at all. Added a
  fourth route to G4, Freedom of Information Act request, for the independent cost estimate and the
  labor hour estimates that GAO-17-575 carries redacted. Three corrections of record: the $11.341
  billion figure is a sourced FY2019 budget estimate rather than an unsupported number, so it is
  usable as a dated estimate and never as a total; the Selected Acquisition Report family gives
  contract and subprogram detail but not a hull allocated total program cost, per GAO-17-575, which
  is what makes G4 load bearing; and the shared class research and development element is 0604112N,
  distinct from procurement element 0204112N. Two further dated seams recorded beyond the ledger
  seam in D18: Navy ERP's own platform refresh completing 19 August 2019, and the program layer's
  move from the DD 1921 series to FlexFile reporting.
- **2026-11-08, asset, property and industrial research pass.** Extended `ring0/RING0_CVN79.md` with five
  sections: asset valuation and evaluation, government furnished property with the F-35 precedent, the cost
  increase timeline against the official cost categories, the industrial map of who builds what, and a clue
  map for costs outside the two shipbuilder contracts. Opened G14 through G19. Four findings change the design
  rather than only adding reference. First, the hull is on the books today as construction in progress and not
  as a vessel, and the governing text is Financial Management Regulation Volume 4 Chapter 25, which superseded
  the Chapter 6 that secondary sources still cite; the Navy general fund capitalization threshold is one
  million dollars, the aircraft carrier useful life is fifty years, and straight line is the only permitted
  depreciation method. Second, capitalized value can never equal program cost for three structural reasons
  that no amount of better data removes: scope, timing, and a boundary conflict where the obligation work
  limiting date governs the appropriation while placed in service governs the asset. Third, reporting of
  government property in contractor possession has been an audit material weakness since fiscal year 2001,
  and GAO reported in 2025 that the Supervisors of Shipbuilding were not consistently verifying contractor
  property records on selected major programs, which names this hull's own contract administrator rather than
  offering an analogy. Fourth, the two shipbuilder contracts buy construction and integration and not content:
  the launch and recovery systems come from Naval Air Systems Command, the weapons elevator engineering from a
  Naval Surface Warfare Center division, and the reactor plant from Naval Reactors and the Department of
  Energy, so no single line of accounting says this hull from end to end, and cross command government
  furnished equipment is a harder attribution problem than the ledger seam in D18. One correction of scope:
  the shared class research and development element is a separate program element from procurement, so a
  roll-up that omits it understates the hull and one that adds it without an allocation rule overstates it,
  which is the same conclusion G4 already reached from the acquisition reporting side.
- **2026-11-08, reconstruction pass.** Added Part N to `ring0/RING0_CVN79.md`, an explicitly
  non-reportable analyst reconstruction of how the hull total is composed, and D32 for the decision to
  carry that reasoning as a separate tagged layer. Opened G20 and G21. Four results worth holding onto.
  The baseline history reconciles to the dollar: the statutory cap plus the August 2021 overrun plus the
  August 2023 increment to the cost limitation baseline plus a later increment equals the budget
  submission total exactly, which means the amount above the legal cap is fully attributable, and only
  about seventy two per cent of it is overrun while the rest is accounting boundary movement. Under half
  the hull, about forty six per cent, is traceable to any named public contract action, and the two
  shipbuilder contracts account for roughly forty per cent of the ship, which is the quantified version
  of the Part L finding that those contracts buy construction and integration rather than content. Roughly
  one sixth of the hull was bought before it was authorised, since advance procurement began six years
  ahead of the procurement year, so any timeline starting at authorisation misses about two billion
  dollars. And a December 2024 modification worth fifty four million dollars for Nimitz class defueling
  and inactivation facility upgrades sits on this hull's own construction contract number, which proves
  contract number is a necessary key and an insufficient one, and which supports G8 rather than
  substituting for it. Supporting scripts committed to `analysis/`.
- **2026-11-08, primary source pass.** Rebuilt Part N of `ring0/RING0_CVN79.md` on primary documents after
  they were placed in `ring0/reference/`: the fiscal year 2027 shipbuilding justification book and a full
  federal transaction download for the detail design and construction contract. The reconstruction is no
  longer an estimate and reconciles to zero residual on two independent axes. Closed G10, G17 and G18,
  narrowed G20, opened G22 and G23, and resolved E-3. The authoritative total for this hull is now
  13,409.970 million dollars from the fiscal year 2027 submission rather than the 13,196.0 million carried
  through the earlier parts. By category the hull is sixty three per cent basic construction, fifteen per
  cent propulsion equipment, nine per cent ordnance, seven per cent plans; by funding stream it is twenty
  five per cent advance procurement obligated before the ship was ever authorised, fifty six per cent
  subsequent full funding, sixteen per cent cost to complete which is still running in fiscal year 2027,
  and under four per cent in the procurement year itself. The contract everyone calls the ship's contract
  accounts for thirty four per cent of the ship, four point five eight billion dollars obligated across
  nine hundred and twenty seven transactions. Two interpretation errors were found and are recorded rather
  than quietly fixed. The dagger footnote on three cost rows marks the presence of a further exhibit and
  does not mark government furnished content, which the earlier pass had inferred; that inference was
  plausible, convenient, consistent with everything else and wrong, and it is now E-12. And an earlier
  draft of the reconstruction had borrowed cost category proportions from columns that turned out to belong
  to a submarine line rather than a carrier line, which would have inverted the two largest categories in
  the ship while carrying an estimate tag and a confidence score. The rule taken from that, recorded in
  D32 and now evidenced: a confidence score on a mis-populated model does not warn a reader, it reassures
  one. Two schedule facts also landed, both of which settle open questions: completion of fitting out July
  2027 and obligation work limiting date June 2028, which is eleven months after fitting out and therefore
  confirms the OPNAVINST rule and refutes the NAVSEA desk reference reading of thirteen months after
  delivery. Analysis scripts committed to `analysis/`.
- **2026-11-08, correction pass, reader initiated.** A reader supplied a federal spending extract for the
  two prime contracts and asked why three contract numbers in it were absent from the research and why the
  construction preparation contract was carried at roughly a billion dollars when its obligations were four
  and a half. Both questions had answers and both answers were findings. The construction preparation
  contract N00024-09-C-2116 has obligated 4,519,300,324 dollars across nine hundred and forty eight actions,
  not the one point zero eight billion this effort carried; the earlier figure had been built by summing
  announced contract modifications, which is a method that cannot produce a contract total, and the rule
  taken from that is now D33 with the correction at E-13 and the post mortem at N.7. The two prime contracts
  together are 9,097,903,670 dollars, which is sixty eight per cent of the hull and ninety two per cent of
  every budget category the shipbuilder is paid out of, so attribution of the hull to a named contract or
  vendor line moved from forty two per cent to seventy six per cent in one pass. Construction preparation
  turns out to be a misnomer: two and a half billion dollars of that contract is described as advance
  construction and only half a billion in preparation language, so the contract built the ship during the
  advance procurement years rather than planning it, and the two contracts are sequential rather than
  parallel, crossing in fiscal year 2017. G21 closed with the base award at 111,803,875 dollars on 15
  January 2009; it had never been unpriced, it was simply below the announcement threshold. Five gaps opened.
  Obligations on the preparation contract continue into fiscal year 2026 after its stated period of
  performance ended, which is G24. Award level outlay reporting covers eight tenths of one per cent of the
  two contracts' obligations and the detail design contract reports zero, which is the fund balance with
  Treasury weakness appearing in public data rather than an audit report, and is G25; until it closes, no
  cost product may take outlays for this hull from the public spending record. Both authoritative contract
  catalogues turn out to be closed lists that between them name seven contract numbers for a thirteen point
  four billion dollar ship, which is why the reader's three numbers were absent and is now G26. Two of those
  three remain unidentified and are G27; the third is the air surveillance radar contract, which is
  genuinely partly this hull but is a six platform contract whose obligation total is not a hull number, and
  whose hull share of about a hundred and ten million was already counted. And a contract number collision
  was found that is worse than any of them: the preparation contract for this hull and the detail design
  contract for the two following hulls share their last four digits seven years apart, the latter carrying a
  fifteen billion dollar modification, so any partial match merges three hulls undetectably. That is D34,
  G28 and E-15, and it is now a hard exclusion in the key set. Two further findings came out of the
  selected acquisition report tables while answering the question. The cost and resource centre rates this
  programme's contractor cost data reporting compliance as red, which materially lowers the expected value
  of the data path this dossier had identified as the only public route below the appropriation line, and is
  recorded against G22. And the energy storage subsystem that is an invisible subcontract on this hull is a
  separate prime contract on the fourth hull, held by a vendor not previously in the industrial map, which
  is the cleanest worked example of the finding that the vendor map runs a tier deeper than the contract map.
  Reconciliation script committed to `analysis/recon_v3.py`, superseding the earlier iterations.
- **2026-11-08, G27 closed by direct query.** The public spending record was refused by the session's
  network allowlist for the third time, so the federal procurement data system ATOM feed was queried
  directly and G27 closed the same day it opened. Neither contract belongs to this hull. N00024-18-C-4100
  is Vericor Power Systems, not General Atomics, and is a landing craft part. N00024-14-C-4201 does not
  exist in the feed at all, established against a control query that returned a complete record. A gap
  that had been described as blocked by access was blocked by nobody having run the query; the vendor
  label it rested on had been inferred and then carried as fact, which is the third instance of that
  failure in this effort. Opened E-16: the feed and the public spending record disagree by 583,963
  dollars on the detail design and construction contract's total obligation, a third source disagreement
  on obligations for this hull and one small enough to pass every reasonableness check. No figure in the
  hull moves. The key set now carries both numbers under `resolved_not_this_hull` rather than dropping
  them, so the labels cannot be re-inherited.
- **2026-11-09, proposed gaps adopted.** All 37 gaps the investigator proposed from prose questions
  (`aircarrier_proposed_gaps`, run `investigator-65a84c4f589d`) adopted as G29 to G65, each keeping its
  `PQ-` id. By type 29 are `DOCUMENT`, 5 `DATA`, 2 `CATALOG` and 1 `SME`; by closability 30 wait on
  access, 4 are reachable by query and 3 wait on a person. None is sized for
  exposure yet. Two pairs overlap in substance and are marked rather than merged: G32 with G36 (the same
  two test plans) and G45 with G54 (the same cost-element guidance). No gap was closed.
