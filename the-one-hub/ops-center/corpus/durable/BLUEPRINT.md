# Blueprint: intent, design, and scaling path

Single home for why this exists, what it produces, how it works, and how it grows. Domain facts
live in `BACKGROUND.md`. Decisions already made and gaps still open live in `LOG.md`. Facts are
not repeated across those three files; each points to the one that owns it.

---

# Part I. Intent

## 1. The problem

Nobody can answer "what has CVN-79 cost" with a number that is both defensible and traceable to
evidence. The data exists. What is missing is the connection between how the cost is reported and
how it was recorded.

Four causes:

1. The cost is reported in several places by several producers, and those places do not agree. A
   congressional report, a budget exhibit, the general ledger, and a contract performance report
   will give different figures for the same hull in the same year. All four can be correct, because
   they measure different things under different scope rules at different times.
2. The accounting record spans multiple general ledger systems across roughly two decades, with
   field definitions and account structures changing at each transition. For this program the
   transition is a hard dated seam rather than a gradual migration. See `BACKGROUND.md` section 3.
3. No one owns the reconciliation between the reported figure and the recorded figure. Each time
   someone needs it, it gets assembled by hand, differently.
4. The scope of "program cost" is undefined in practice. Contract cost is obvious. Whether a
   program office's travel for a site visit belongs in the number is answered inconsistently,
   usually implicitly.

## 2. Why now

**Audit.** The Department is under a clean-opinion mandate, and several active material weaknesses
are this problem at enterprise scale: a reported balance that cannot be traced to supporting
transactions. A program whose cost cannot be walked from report to voucher is that weakness in
miniature. From DCFO, this is the priority that matters most, even where the broader organizational
conversation is framed around AI and budget execution.

**Program cost and independent assessment.** CAPE builds independent cost positions and needs a
traceable actuals baseline. The leadership intent for that handoff is specific: give CAPE a cost
model they can adopt into their own program review and assessment work. That is harder than being
validated once, because a model someone else adopts has to be reproducible without its author, on a
program it was not piloted on.

**AI changes the cost of the work.** The reason this was never done is labor: reading decades of
documents, crosswalking account semantics across system eras, chasing one variance through five
systems. That labor is now compressible, which moves the bottleneck from effort to access and
judgment.

## 3. The goal

For a given hull and period, show how the cost appears in each reporting layer, and explain why the
layers differ, with evidence attached to each explanation.

The goal is not a single authoritative number. A single number tied to one declared source of truth
is worth less than a defensible account of how the number is reported, how it is recorded, where
those diverge, and why. The divergence with its cause attached is the product. That is also the
artifact an auditor asks for, which is why audit readiness falls out of the design rather than being
bolted on.

**Success looks like:** a variance table for CVN-79 across available layers where every difference
above a materiality floor has a documented cause or an explicit unexplained flag; a coverage map
stating which layers are accessible and what access would change that; a method a second person can
run on a second hull without the original author; and something a program office, CAPE, or an
auditor can challenge on the merits, because the methodology and its gaps are both visible.

## 4. The design premise: the data is messy and the picture is never complete

Stated before the design because treating this as an exception rather than the normal condition is
how this kind of effort fails.

In a perfect world there would be complete, clean, authoritative data for the whole program history.
There is not, there will not be, and this is the single largest determinant of success. The
architecture is therefore an **investigation apparatus** before it is a reporting apparatus. Its job
is to build an evidence trail from unreliable material toward authoritative sources, and to stay
defensible while incomplete.

Four properties follow, each load-bearing later.

**Completeness is never a gate.** No component may require that a layer be present, that a system
inventory be finished, or that a question be settled before it produces output. Part II section 11.

**Conflicting values are retained, never resolved by selection.** When two sources give different
figures for the same cell, both are kept with their provenance. No winner is picked. This follows
from the product being the variance with its cause attached: a pipeline that cleans conflicting
values destroys the raw material the product is made of. Cleaning is the default instinct of most
data engineering practice and it is wrong here.

**Unreliable material is quarantined, not excluded.** Public and secondary sources are valuable and
dangerous for the same reason. Their job is to point at where the authoritative record lives, which
system holds it, and which office or community can produce it. Their job is never to supply a
figure. Part II section 9 is the mechanism.

**The system models its own ignorance as first-class data.** What is not known has a type, an owner,
a resolution method, a dollar consequence, and a decay risk. Part II section 10, register in
`LOG.md`.

## 5. Design requirements derived from constraints

Constraints that survived being tested against the question "does this change a design decision."
Items that changed nothing are not listed, because a warning implying no design change is
decoration.

**Access is granted by people on their own timeline, and no amount of AI changes that.** The binding
constraint is authority over NAVSEA and PEO Carriers data, not capability. Requirement: the layer
model degrades gracefully, and any layer can be absent while the system still produces explained
variances among the layers present. This also sets the entry point in section 16.

**Delivery pressure pulls scope toward whatever looks finished.** A dashboard can ship empty and
still look complete. Requirement: the primary artifact is a variance with a cause attached, because
that cannot be faked. A variance table with no causes attributed is visibly unfinished in a way a
dashboard is not. The shape of the deliverable does work that discipline alone will not.

**An independent cost reviewer will test the allocation methodology first.** Shared class costs,
principally Ford-class RDT&E, must be split across hulls by some method, and that method is the
weakest point in any derived hull-level number. Requirement: every allocation carries its method,
rationale, and a named approver, and must be reproducible from those three. An allocation that
cannot be re-derived by someone else is an estimate, not a figure.

**Some questions will never resolve.** Institutional knowledge about early system-era routing may no
longer exist. Requirement: permanent "best current estimate, still open" states are first-class, and
an open item is not a defect awaiting closure.

## 6. What this is not

Not a new cost accounting system. Not a competing cost estimate. Not a replacement for FIAR
remediation or for the program office's own reporting. It reads what those produce and explains
where they diverge.

---

# Part II. Design

Every structural choice states why it is that way, because a design asserted without its reasoning
cannot be corrected later by anyone except its author.

## 7. What the system produces

Leading with the output, because it disciplines everything else. For a hull and a period:

1. **A layer comparison.** The cost figure as each layer states it, with the scope rule each layer
   used and the as-of date of each figure.
2. **A variance ledger.** For each pair of layers compared, the difference and its cause. A cause
   comes from a closed set of categories, carries evidence, and is attributable to a specific
   mechanism. Differences with no determined cause are flagged unexplained and ranked by dollar size.
3. **A coverage map.** Which layers are present, at what fidelity, and for absent ones, what
   specific access would change that.

Anything that does not feed those three is out of scope.

## 8. The six layers and their real topology

A layer is a distinct place the cost is stated. The test for whether something is its own layer is a
different **producer**, a different **purpose**, and a different **number characteristic**. Two
artifacts with the same producer and purpose are one layer however different they look.

| Layer | Producer | Purpose | Number characteristic |
|---|---|---|---|
| **L0 Reported** | The Department to Congress and the public, plus oversight bodies reporting on the Department | Justification and accountability | Aggregated, frequently class-level rather than hull-level, often estimate at completion rather than actuals, point-in-time snapshots never restated |
| **L1 Budget** | The comptroller chain | Plan, request, appropriate, apportion, allot, obligate, expend | Appropriation-year structured, anchored to a Treasury Account Symbol, execution against a budget line |
| **L2 Ledger** | The accounting systems and DFAS | Record transactions under the USSGL, produce financial statements | Double entry, budgetary and proprietary accounts, posted by source document, closed by period |
| **L3 Asset** | Accounting plus property accountability | Accumulate construction in progress, capitalize at placement in service, depreciate | Cumulative cost of a capital asset rather than cost of a period |
| **L4 Program** | PEO Carriers, PMS 379, the shipbuilder | Manage cost and schedule against a baseline | Contract-scoped, work-breakdown-structure granular, budgeted and actual cost of work performed with estimate at completion |
| **L5 Evidence** | Feeder systems | The underlying documents | Individual, dated, each with supporting documentation or without it |

**Oversight-origin documents inside L0 get a distinguishing tag,** because their content differs in
kind. A GAO or DODIG report contains findings about the other layers, which is a free head start on
variance causes: it says where the layers are already known to disagree and why someone else
concluded they do.

**L1 and L2 are separate layers** even though L1's execution figures derive from L2's budgetary
accounts. The derivation is the point. The same postings presented in budget structure versus
account structure will not match line for line, and the difference is informative.

**L3 is its own layer, and folding it into L2 was an error.** For a ship, capitalized asset value
and program cost diverge by construction. Research and development does not capitalize. Some support
cost expenses. The eventual book value of CVN-79 will not equal what the program spent on CVN-79,
and that gap is a legitimate explainable variance. A model that folds asset into ledger cannot
represent the most predictable disagreement in the whole picture.

**L2 for this program is two sources at a dated boundary,** which is established fact rather than an
open question. NAVSEA's system of record is STARS for FY10 and prior funding and Navy ERP for FY11
forward, legacy data was deliberately not converted, and ship construction moved on 1 April 2011
rather than with the general October 2010 cutover. CVN-79 straddles it. Sourcing in `BACKGROUND.md`
section 3. The consequence here is that L2 is designed as two sources joined at a documented
boundary, not one source with a hole in it.

### The onion is the method, not the shape

This correction matters most, and it explains why the layer numbering kept needing to be fixed.

An earlier version treated the layers as concentric rings, each containing the next, each tying to
the one immediately outside it in a single chain. That kept breaking under review because the data
is not concentric. Test it. L4 ties to L2 only partially, at contract level, because earned value is
contract-scoped while the ledger is appropriation-scoped and the contractor's own cost accounting
never enters the Department's ledger at the same granularity. L3 ties to L2 directly, because
construction in progress is a ledger account, but on a cumulative capitalized-subset cut rather than
the annual obligation cut L1 ties on.

The real structure is a hub and spokes:

- **L2 is the hub.** It is the only layer where every dollar has a posting.
- **L1, L3, and L4 each tie to L2 on a different cut.** L1 on budgetary accounts by appropriation
  year. L3 on the capitalized subset, cumulatively. L4 on contract-scoped actual cost.
- **L0 ties to L1 and to L4**, since budget exhibits restate budget positions and acquisition
  reports restate program cost positions. L0 does not tie directly to L2.
- **L5 sits beneath L2** as supporting detail for individual postings.

Funnel and onion-peeling still hold exactly as stated: start outside with reported aggregates, work
inward, tie each layer before trusting the next. That is the **order of approach**. Hub and spoke is
the **topology of the data**. Conflating the two is what produced the renumbering problem. The L0
through L5 numbers are retained and now mean distance along the approach path rather than
containment. L3 and L4 are not deeper than L2. They are adjacent to it on different cuts, reached
later because they are harder to get.

## 9. The variance is the unit of work, and data trust is a firewall

### The variance record

Not the cost figure. The variance. A variance record compares one layer's figure to another's for
the same hull and period, and carries: the two layers and figures each with its own as-of date; the
scope rule each figure was produced under; the difference and a materiality judgment on it; a cause
category; evidence supporting the cause or an explicit unexplained flag; and who determined the
cause and when.

Cause categories, a closed set, each a real mechanism rather than a label:

- **Timing.** Figures are as-of different dates, or one layer recognizes a cost in a different period.
- **Scope.** The layers applied different cost scope rules. Section 10.
- **Allocation.** One figure includes a share of a shared class cost derived by a method and the
  other does not, or uses a different method.
- **Capitalization.** The difference is the non-capitalizing portion of program cost. The predictable
  L2 to L3 variance.
- **Inter-entity cost not recorded.** Another entity bore a cost never charged to this program's
  accounts. Section 10.
- **Error.** One figure is wrong. This is a finding, and it goes to whoever owns that layer.
- **Unexplained.** No determined cause yet, ranked by dollar size. This is the work queue.

A difference with a documented cause is finished product. Only **unexplained** is incomplete. That
distinction is the whole design, and it is why the system delivers value without ever converging the
layers to one figure.

### Three zones and a one-way door

The mechanism that makes it safe to work with unreliable material. A single confidence column is a
label. This is a firewall.

**Zone L, Leads.** Everything from public or secondary sourcing lives here and only here. A lead is
graded on two independent axes following the Admiralty code used for this problem in intelligence
work: source reliability (A through F) and information credibility (1 through 6), so a lead is
tagged something like B2 or E5. A named tradecraft framework survives review in a way ad hoc
judgment does not.

**A lead's only legitimate output is a Collection Requirement.** Not a figure. A Collection
Requirement is a specific actionable instruction: retrieve this document, from this system or this
office, for this period and this account. This is what connects the trust model to the investigation
model, and it is why a weak public source is useful rather than merely risky. The requirement queue
is ranked by dollar materiality, because an unranked queue becomes its own bottleneck at human
review.

Zone L has no join path into the canonical tables. That is structural, not procedural. There is no
route by which a lead's dollar figure ends up adjacent to a validated one and gets mistaken for it.

**Zone R, Raw authoritative.** Only primary material actually collected: a real budget justification
page, a real report, a real extract, with full chain of custody. Ingested, not yet trusted for
arithmetic.

**Zone V, Validated.** A record enters only when a named person or a documented deterministic rule
validates it against the source or ties it to a control total. Only this zone feeds anything
presented as a figure. A further **Certified** state marks records tied out and fit to present
outside the team.

The rules that do the work:

- Promotion between zones is always a separate logged event naming who, when, and citing the primary
  document. No pipeline step may treat a graded lead as validated, at any grade.
- Demotion carries equal rigor and is equally logged. A validated figure contradicted by a later
  primary source, or traced to a crosswalk rule that turns out wrong, produces a demotion record
  rather than a silent overwrite. The record of what was believed and why it changed survives, and
  that history is part of what makes the product defensible under challenge.
- **Weakest-link aggregation.** Any total inherits the weakest trust state among its inputs. If one
  period's contribution is lead-grade, the whole total displays as lead-grade. This prevents a
  good-looking aggregate from concealing a weak input, and it is what makes it safe to show partial
  work to an audience that will not read footnotes.
- Nothing is displayed without its state visible.

## 10. Cost scope is a dimension of the variance, not a prerequisite decision

The question that prompted this: beyond contract cost, what counts? Does a program office's travel
to the shipyard for a site visit or inspection belong in CVN-79's cost?

**The governing standard.** SFFAS 4 is the authority. Full cost of a program's output equals direct
costs plus indirect costs assigned to the cost object, where assignment is by direct tracing, by
cause and effect, or by documented allocation when neither of the first two is practical. SFFAS 30
amended SFFAS 4 to require that full cost incorporate goods and services received from other federal
entities even when unreimbursed. The Department implements this in DoD FMR Volume 4 Chapter 19.
Citations and the ruled-out alternatives are in `BACKGROUND.md` section 4.

**Applied to the travel question.** The determining fact is which appropriation funded it, which is
checkable on the voucher rather than a matter of judgment:

- Funded by the program's own appropriation: direct cost, already posted to the program's accounts,
  appears in L2 without special handling.
- Performed by another command and reimbursed through a funding document: direct cost once the
  reimbursement posts, under the reimbursable rules.
- Performed by another command on its own operating funds with no reimbursement: the inter-entity
  case SFFAS 30 added. Full cost should include it, and it will never appear in this program's L2
  postings because it was never charged there. Capturing it requires the providing command's records
  and an explicit imputation carrying method, rationale, and approver.
- Agency-wide overhead too remote to trace to one hull: out of scope. SFFAS 4's full cost requirement
  operates at the program and output level and does not demand unlimited tracing. This bucket exists
  so the exclusion is a recorded decision rather than a silent default.

**The architectural point.** Scope is not a decision to settle before building. Two layers can
disagree entirely because they scoped cost differently, and they often do by design. An acquisition
report's program acquisition unit cost and the ledger's obligations against the shipbuilding line
are scoped differently by construction, and neither is wrong. So scope difference is a named variance
cause, and the system attributes differences to it rather than forcing all layers onto one scope
rule. Forcing one rule would destroy real information.

## 11. Graceful degradation

Derived from the access constraint in section 5, stated as a requirement because it governs
implementation order.

The system produces its three artifacts at every access level, including zero. With only L0 it
compares public sources against each other and explains their disagreements. Adding L1 adds
reported-to-executed variance. Adding L2 makes the hub available and opens the L1, L3, and L4 ties.
Each layer added increases resolution. No layer is a precondition for functioning.

Practical consequence: nothing is built that assumes a layer exists. The variance ledger treats an
absent layer as absent, and the coverage map reports it as absent with the access ask attached.

## 12. Investigation: how a gap gets worked

Section 4 says unknowns are first-class data. This is the machinery. The register itself is in
`LOG.md`.

Every unknown carries a type, and the type determines who works it:

| Type | Resolution method | Executor |
|---|---|---|
| `DOCUMENT` | The answer exists in a retrievable document. | AI research, verified by a person. Needs no access. |
| `DATA` | The answer exists in a system we can query. | Pipeline, once access exists. |
| `SME` | The answer exists only in institutional memory. | A person, interviewing a named role. |
| `CATALOG` | Requires enumerating something from inside an environment. | Someone inside. Partial by nature. |
| `IRREDUCIBLE` | No record, no living memory. | Nobody. Terminal. Bounded estimate with documented method, or carried permanently. |

Three rules:

**A gap is never assigned back to the sponsor.** An unknown is work to be executed, not a question
to hand upward. Stated as a rule because the natural drift is to produce a tidy list of open
questions and call that diligence, which converts the product's own job into someone else's homework.

**`DOCUMENT` gaps get worked immediately, because they are the cheap ones.** Most apparent dead ends
are document-answerable and simply have not been looked up. Of the four unknowns this design carried
on first writing, two were fully resolved by research, one was narrowed to a single precise question
for a named office, and one was reframed around an existing GAO recommendation. None needed access
or authority.

**`SME` gaps are prioritized on decay risk alongside dollar materiality.** Institutional memory about
a 2010 system cutover leaves on a retirement schedule, not a project schedule. A low-dollar SME
question with high decay risk can outrank a high-dollar one still answerable in three years.

Each gap records what it blocks and the dollar value of variance left unexplained because of it.
That makes the register a ranked work queue and makes an access request specific: not "we would like
the ledger extract," but "this gap leaves this much unexplained and this extract closes it."

Closing gaps opens gaps, and that is the register working rather than failing. The first research
pass closed two and opened two, including a fourth Navy general ledger that was in neither the
original scope nor anything built.

## 13. Where AI goes

**The one rule everything else follows: no AI output writes directly to a trusted table.** Every
role below writes to a candidate location with a confidence grade and full provenance, meaning what
it looked at, what rule or model produced the output, and when. A person, or a deterministic rule for
mechanical checks like tie-outs, promotes a candidate. An AI-embedded stack that writes straight
into the canonical tables is a plausible-looking black box and will not survive the first auditor who
asks how you know it is right. More AI roles means more candidates arriving at the gate, never a
looser gate.

Seven roles, organized by the bottleneck each attacks. This can be one orchestrated pipeline with
seven responsibilities rather than seven products.

**Finding reported figures.** L0 is thousands of pages across decades. Extract hull, period, cost
concept, figure, and page citation from that corpus. Output goes to lead or raw grade, never further.
Scope includes the public document categories: acquisition reports and their repository, FOIA reading
rooms, CRS reports, GAO and DODIG reports, and budget justification books in public archives.

**Reading scanned legacy material.** Old budget books, contract modifications, and reports with
inconsistent table formatting need OCR, table structure extraction, and assisted cleanup, preserving
page and line citation on every figure. Several documents already pulled in this effort had badly
OCR'd tables. Output feeds the same candidate store as the role above, tagged by extraction method so
a reviewer knows whether a figure came from clean text or reconstructed OCR.

**Crosswalking semantics across system eras.** Given a source system's field and value pairs and the
canonical structure, propose candidate mappings using pattern rules, description similarity, and
precedent from already-validated rows for the same era. It proposes `DERIVED` or `ESTIMATED` and
never `EXACT`; only a financial professional's validation promotes to exact. A crosswalk validated on
one era and one hull does not transfer to another era or program by inheritance, and that limit holds
permanently rather than only during the pilot.

**Resolving identity across systems with no shared key.** The hard problem in the original ask.
Propose that a STARS-era document and a Navy ERP record describe the same underlying event, using
amount, date proximity, document-number fragment matching, and narrative similarity. Output is a
scored candidate, never a silent merge. This is the closest thing to magic in the stack and the most
likely to be wrong in a way that looks confident, so review it harder than any other output. Expect a
real backlog of no-match rows for the oldest, thinnest-documented periods, and treat that backlog as
useful information: it is where "back to inception, as far as it can go" meets its actual limit.

**Generating and testing candidate causes.** Given an unexplained variance, enumerate the mechanisms
that could produce a difference of that size and direction, then test each against available data.
Run the tie-out checks automatically once two comparable layers have data, rank failures and
unexplained results by dollar materiality, and route the largest breaks to review first. Never
auto-resolve a break by adjusting either side.

**Working `DOCUMENT` gaps, and chasing one question until it has a sourced answer.** The detective
role, and the highest-leverage one for a project whose binding constraint is unknowns rather than
compute. Given a dead end, find the authoritative document that settles it, retrieve it, and produce
either an answer with a citation or a precise statement of what remains and who can answer it. A dead
end is usually an unworked research task, and treating it as a constraint is the mistake this role
exists to prevent.

**Retrieval over the reference work already done.** The existing roughly 104-page DoD GL systems
reference document profiles GFEBS, Navy ERP, DAI and others with audit and accounting annexes. Index
it so the other roles query it before re-deriving system-specific logic. Lowest risk and highest
immediate leverage, because it is pure reuse and it directly improves crosswalk proposals.

**Explaining a variance for a specific audience.** The same variance reads differently to the program
office, to CAPE, and to an auditor. Drafting those readings from one underlying record is a
generation job.

**Team mapping.** Across the three sub-teams: RPA and automation own extraction and the legacy
reading roles; analytics owns the tie-out and variance logic; AI and ML own crosswalk inference and
identity resolution; all three share the retrieval layer.

**Build order for the AI roles.** Start with retrieval over the existing reference document, because
it is pure reuse and de-risks everything else, and with figure extraction, because that is what has
been done by hand so far and formalizing it is the natural next step. Both need no access beyond
what already exists. The tie-out checker is next because it is deterministic rather than
model-based, and it is what keeps every other role honest. Crosswalk inference, identity resolution,
and legacy reading are hardest and should wait for real extracts to validate against. Building a
crosswalk model against data you do not have is a way to ship something confident-sounding and wrong.

Separately from the product's own roles, whatever coding assistance the environment authorizes gets
used to build the pipeline faster. That is velocity and touches nothing about what gets trusted.

---

# Part III. Scaling and audiences

## 14. What generalizes cheaply and what does not

**Cheap: one carrier to the rest of the class.** CVN-78 through CVN-81 share lifecycle vocabulary,
the accounting system chain, the appropriation structure, and the shared research and development
program. Adding a hull is a registry entry and an allocation set. No new architecture. Worth doing
early for a reason beyond its own value: it is the proof the method generalizes, and that proof is
what makes the CAPE conversation possible.

**Moderate: carriers to other Navy ship programs.** Same appropriation structure, largely the same
accounting chain. Different program offices, baselines, and shared-cost patterns. The layer model
holds. The new access conversations are the cost.

**Expensive: ships to non-ship programs.** An aircraft or missile program has different lifecycle
vocabulary, different acquisition category rules, a different accounting chain, and different
capitalization treatment by asset type. The layer model holds in structure and nearly everything
inside each layer is new. This is a separate project with its own resourcing request. Treating it as
a natural extension of carrier momentum would misrepresent the cost to whoever is being asked.

## 15. One ledger, different views per audience

Not four products. One variance ledger and coverage map with a view layer per audience.

**The team.** Full detail, every trust state visible, unexplained variances ranked. The working view.

**Leadership.** The coverage map leads, with the specific access request attached to each absent
layer, and the variance ledger as evidence the method works on what is already available. This view
exists to convert attention into access.

**Program office, PEO Carriers and PMS 379.** Methodology-transparent, framed as filling a gap
together. A variance implicating their layer is a question, not a finding, until they have seen it.
The failure mode to avoid is arriving with their program's numbers assembled without them.

**CAPE.** CAPE builds independent cost positions under a documented methodology, which makes them
the most useful external reference available and the audience most likely to find the weakest point,
because finding it is their function. The leadership intent is handing them a model they can adopt
into their own program review and assessment work, which requires reproducibility without the author
on a program it was not piloted on. Two things must be true first: the shared class cost allocation
method is documented to a standard an independent estimator would accept and is re-derivable by
someone else, and the method has run on more than one hull so the conversation is about a method
rather than an anecdote. Bring the reconciliation and variance attribution method and the question of
whether it complements or can be validated against their own position. Do not bring a finished cost
claim.

**Audit community.** Last, gated on the ledger hub and evidence sampling being real rather than
illustrative. The ordering is specific rather than cautious: the audit community's question is
exactly the product's output, which makes this the audience where it is most useful and most exposed.
Showing partly illustrative variance attribution to people whose job is testing assertions would
spend credibility in the one place this effort most needs it, given that audit is the priority driver
in section 2. When it happens, the framing is a tool supporting remediation already underway with
its own owners and cadence. A competing claim to have solved a material weakness invites the
challenge rather than the collaboration.

## 16. Order of work

One sequence. Earlier drafts carried two overlapping ones.

1. **CVN-79, public layers only, no access needed.** Collect cost figures from congressional,
   budget-justification, and oversight sources. Document where they disagree. Attribute causes where
   the documents themselves determine them, principally scope and timing. This produces a real
   variance ledger immediately and gives the access conversation an artifact. Public sources already
   disagree about this hull, today, which is why this is the entry point rather than a warm-up.
2. **Add L1 budget execution** for the appropriation lines funding the hull. Already reachable.
3. **Open the ledger access conversation,** carrying the artifacts from steps 1 and 2.
4. **Add L2, the hub.** Everything after depends on it. Deepen this one hull to full rigor before
   widening.
5. **Add L3 and L4** as access allows. Separate asks to separate owners.
6. **L5 sampling** only once L2 is real, since evidence sampling without a population is meaningless.
7. **Generalize to the rest of the Ford class.** Cheap, and it is the proof point.
8. **CAPE,** with the method and more than one hull behind it.
9. **Audit community,** once evidence sampling against a real population exists.
10. **Other ship programs, then non-ship programs,** as separately resourced efforts.
