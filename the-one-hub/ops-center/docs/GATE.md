# The gate

Enforced in `core/policy/gate.py`. Thresholds in `seed/gate.yaml`.

## Why a routing table and not a score

D26 rules out a composite risk score, for the reason that applies here exactly:
a single number hides the mechanism, and the mechanism is the whole useful
content. Three axes, evaluated independently, each routing on its own.

## Axis 1, exposure

Dollars the claim bears on, as a share of the subject total. Expressed as a
share rather than an absolute so it transfers to the next hull without
retuning. Floor is 1 percent. Subject total is 13,409.970 USD M.

## Axis 2, confidence

Two grading systems already exist and a third is not added. The Admiralty two
axes on the source, A-F and 1-6. The VERIFIED / DERIVED / ESTIMATE / UNKNOWN /
REJECTED tag with its c value on the claim. Weakest-link aggregation propagates
both. The gate reads them, it does not replace them.

## Axis 3, risk

The axis that was not formalized, and the one that matters. All three errors in
`ring0/RING0_CVN79.md` N.7 were high confidence, internally coherent, and wrong
in a way that was invisible downstream. None would have been caught by the
other two axes.

| Flag | The claim depends on | Instance |
|---|---|---|
| PREMISE | an assumption about which population the data describes | Error 1, the Columbia-class columns |
| INTERPRETATION | reading a convention, footnote, legend or field meaning | Error 2, the dagger, E-12 |
| METHOD | a construction method that may be incapable of producing the thing claimed | Error 3, announced mods, D33 |
| KEY | an identifier join that could silently merge populations | D34, E-15, and the P00154 description |

A flag is set by the handler from what the extraction actually did, and by the
Challenger from the negative vocabulary. It is never set by a model judging its
own output.

## The routing table

| Rule | Condition | Route |
|---|---|---|
| R0 | tag is UNKNOWN | becomes a typed gap with an executor |
| R1 | any of PREMISE, METHOD, KEY | human review, regardless of exposure or confidence |
| R2 | INTERPRETATION and above the floor | human review |
| R3 | INTERPRETATION and below the floor | hold as candidate, no review |
| R4 | above the floor and below VERIFIED | human review |
| R5 | above the floor, VERIFIED, unflagged | promote, conditional on the two-axis close |
| R6 | below the floor, VERIFIED, unflagged | promote |
| R7 | below the floor, below VERIFIED | hold as candidate, no review |

R3, R6 and R7 are what keep the gate from becoming the bottleneck. Most
candidates are small and uncertain and should accumulate silently. Review
capacity goes to R1, R2 and R4 and nowhere else.

The structural borrow from tiered capital review: scrutiny proportionate to
size and risk, full qualitative review reserved for the top tier, and the
tiering itself auditable.

## Two properties that make it a gate rather than paperwork

**The review queue is ranked by exposure and shows its reason.** A reviewer
sees the claim, the flag, the specific tell, and what it bears on. An unranked
queue of undifferentiated candidates becomes its own bottleneck, which is the
same argument already made for the Collection Requirement queue.

**The gate records its own misses.** `work.gate_misses`. When something gets
through and is caught later, as E-13 was caught by a reader, that becomes a
row: what the gate saw, what it allowed, the tell, and which flag should have
fired. The negative vocabulary and the flag rules grow from that table.
Without it the gate is static and catches only what it was built to catch.

## The honest limit, stated as a design property

The Challenger catches the error classes already seen, and catches a novel one
only where the vocabulary happens to reach. Subject consistency generalizes as
far as the negative vocabulary goes, and that vocabulary exists because someone
knew a Large Aperture Bow array is submarine equipment.

So D13's gate is permanent rather than transitional, and the miss log is the
mechanism by which the limit moves. That is the design, and it is also what
should be said in any brief to an audit audience, because BLUEPRINT section 15
already identifies that audience as the one where overclaiming costs the most.
