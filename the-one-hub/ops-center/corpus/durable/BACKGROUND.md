# Background: domain reference

Facts about how carrier money moves and who states what about it, with sources. This is the
reference substrate so `BLUEPRINT.md` can reason without re-explaining the domain, and so `LOG.md`
can record decisions without restating the facts behind them. Items needing confirmation are marked
rather than asserted, and the open ones are tracked as gaps in `LOG.md`.

## 1. How appropriated money becomes a ship

Carrier cost does not arrive on one line in one year. It arrives through several appropriations
across more than a decade, and that structure produces most of the disagreements the system has to
explain.

**Research and development.** Ford-class design was funded through RDT&E. This is a class cost, not
attributable to a single hull by any direct method, which makes every hull-level figure that
includes an R&D share dependent on an allocation choice.

**Advance procurement.** Long-lead items, principally nuclear propulsion components, are
appropriated years before the fiscal year associated with the ship itself. A hull's cost therefore
begins accumulating in appropriation years before the year the hull is commonly said to belong to.

**Shipbuilding and Conversion, Navy (SCN).** The construction appropriation, and a multiple-year
appropriation, so obligation availability extends past the year of enactment. Each fiscal year's SCN
appropriation is separate and discrete. Ships are a recognized exception to full funding policy, so
a carrier is funded incrementally across several fiscal years. There is no single year in which the
ship was bought, and the figure a document reports depends on whether it describes one year's
increment, the cumulative appropriation to date, or the total estimated cost at completion. SCN is
divided into budget activities, and its four-digit subhead structure carries the identifying data
elements.

**Other procurement and related lines.** Government-furnished equipment arrives through separate
lines. Whether any of it counts as part of the ship's cost is a scope question with no universal
answer.

**Outfitting, post-delivery, and operations.** Costs continue after construction under separate
appropriations, and operations and support fund the ship for its service life. Navy policy governs
the point at which shipbuilding construction funding can no longer be obligated and other
appropriation types must be used.

**Statutory cost cap.** Ford-class ships carry a cost limitation in law, set per hull and amended
several times. CVN-79's cap stood at $11.4 billion at the FY2013 budget position; SECNAV notified
Congress of an increase to $12.936 billion in August 2023 (CVN 78 MSAR, December 2023, which also
reported the ship 91 percent complete). $12.936 billion is the current baseline, not $11.4 billion.
This creates a reported hull-level figure with legal significance whose scope is defined by statute
rather than by the accounting structure, so it does not necessarily reconcile line for line to
appropriation-level execution.

## 2. The reporting artifacts and the named offices

The layer model in `BLUEPRINT.md` section 8 gives producer, purpose, and number characteristic for
each layer. What follows is only the specific artifacts and offices, which that table does not name.

**Acquisition reporting to Congress.** Historically Selected Acquisition Reports under statute, with
the reporting regime and its repository having changed in recent years. The current form and
location for this program needs confirmation. For carriers, cost has frequently been reported at
program or class level rather than per hull, so hull figures often have to be derived rather than
read. See section 6 and the GAO recommendation on this.

**Budget justification material.** The annual exhibits. P-1 lists procurement programs, P-5 carries
cost analysis detail, R-1 and R-2 cover research programs and projects, O-1 covers operations. These
state requested and prior-year amounts in budget structure as of the submission date, and are never
restated afterward.

**Congressional Research Service reports.** Analytical summaries written for Congress, compiling
figures from the above and often reconciling them narratively. Useful as leads with good citations,
and useful because the analyst frequently explains why two figures differ. A long-running carrier
program report is a primary reference of this kind.

**GAO and DODIG reports.** These contain findings about the other layers. Where one has already
documented a reconciliation failure or a cost reporting problem, that is a variance cause with
external corroboration already attached.

**Cost estimating and assessment offices, which are the doors for hull-level cost questions:**

- **NAVSEA 05C**, the Cost Engineering and Industrial Analysis Group, owns Ford-class cost estimates.
- **NCCA**, the Naval Center for Cost Analysis, performs the independent cost assessment.
- **CAPE** holds an independent cost position, and has projected differently from the Navy on
  CVN-79.
- **NAVSEA 01** is the comptroller directorate, which provides financial policy, budgeting, and
  accounting and manages appropriation areas. NAVSEA 01 created an SCN desk guide for SCN execution.

**SUPSHIP**, the Supervisor of Shipbuilding, Conversion and Repair, is the naval supervisory
authority at the building yard. It administers the contract, monitors the contractor's earned value
data, and signs the DD Form 250 material inspection and receiving report at acceptance, which
carries the list of outstanding construction deficiencies. SUPSHIP is therefore both a financial and
an evidence-layer actor for a ship under construction.

## 3. Accounting system history

Established 2026-11-06 from the NAVSEA Supervisor of Shipbuilding Operations Manual Chapter 4
(Financial Management), plus GAO and Navy budget documentation. Sourcing detail is in `LOG.md` gaps
G1 and G2. This replaced an earlier version that carried the system chain as an unresolved question.

**The seam is dated, and it is hard.** NAVSEA's transition into Navy ERP began 1 October 2010, at
which point Navy ERP became NAVSEA's system of record for transactions using FY11 funds. Ship
construction and other complex contracts were held back to **1 April 2011** while ship construction
functionality was developed and tested, so a carrier program follows the April date rather than the
October one.

**Legacy data was deliberately not converted.** NAVSEA general fund decided against converting
legacy data into Navy ERP. FY10 and prior funding retains STARS as the financial system of record,
and all NAVSEA financial data for FY10 and prior resides in STARS. This is a decision on the record
rather than a data loss, which is a materially different situation: the early record exists, in a
known place, under a known system.

**Which STARS.** STARS-FL Charleston is the accounting system for SUPSHIP mission funding. STARS-FL
Norfolk covers fleet-funded ship work actions. SUPSHIPs use both STARS-FL and STARS-HCM, the
headquarters claimant module. So STARS for a shipbuilding program means a specific instance and
module combination rather than one undifferentiated system. Obligations in STARS were not
immediately available for invoice payment, taking 24 hours to update, which matters for any
timing-based variance at the day level.

**Navy ERP since.** Navy ERP is SAP-based, is the Department of the Navy's system of record for
financial management as well as supply chain, acquisition, and maintenance, and has itself migrated
platforms from SAP ECC to SAP HANA. Navy ERP consolidated multiple separate general ledger systems.
The Navy announced completion of the migration of its remaining commands in January 2026, and GAO
records Navy ERP as the Navy's financial system of record as of March 2026 (GAO-26-107119).

**SABRS.** The Marine Corps general ledger, developed from 1978, implemented 1 October 1992, run by
DFAS Kansas City, with the Marine Corps transitioning off it in FY2022. Navy budget documentation
describes it as the official general ledger for the Marine Corps **and for select Navy budget
submitting offices**, and records a working capital fund and SABRS user migration to Navy ERP. So a
Navy BSO on SABRS is a real configuration rather than an error. Whether any office carrying CVN-79
funds was ever among them is the narrowed question in gap G2.

A named migration project bears directly on that question. The Navy ran an actual STARS-to-SABRS
(S2S) project, FMP-4, to move Navy Budget Submitting Offices from STARS-FL onto SABRS ahead of later
Navy ERP consolidation. That gives gap G2 a concrete object to check against, rather than a general
question about SABRS: whether NAVSEA or PEO Carriers' BSO was among the offices S2S moved, or
whether that BSO went STARS-FL to Navy ERP directly with no SABRS stop. Source:
`ring0/ring0_research_notes.md`, 2026-11-06 gate-check pass (highergov.com program profile for
SABRS; SECNAV FMP-4 project description).

**Navy ERP's own migration has a dated boundary too, with a documented compliance gap on one side
of it.** The on-prem-to-cloud tech refresh, SAP ECC to SAP HANA, completed 19 August 2019 (Navy.mil,
"Navy Completes Its Largest Cloud Migration to Date"). DODIG-2012-051 found the earlier ECC-era
implementation out of compliance with the Standard Financial Information Structure and the USSGL.
That is a documented reason to expect DERIVED or ESTIMATED crosswalk confidence, not EXACT, for
pre-August-2019 Navy ERP data specifically, layered on top of the STARS/Navy ERP seam already
established above. Public sources (2019 Navy.mil and SeaPower Magazine coverage of the cloud
migration) confirm NAVSEA the command on Navy ERP HANA, naming it among six commands on the
platform; that is a command-level confirmation, not a PEO Aircraft Carriers/PMS 379 BSO-level one,
and does not resolve the SABRS-routing question above.

**A fourth Navy general ledger.** GAO records the Navy as operating four: STARS-FL, STARS-HCM, Navy
ERP, and Navy Systems Management Activity (NSMA). NSMA was in neither the original scope nor
anything built, and is gap G6.

## 4. Governing standards for cost scope

Citations. The reasoning that applies them is in `BLUEPRINT.md` section 10.

- **SFFAS 4**, Managerial Cost Accounting Concepts and Standards for the Federal Government (1995).
  Defines the cost object, direct and indirect cost assignment, and full cost of program outputs.
- **SFFAS 30**, Inter-Entity Cost Implementation (2005). Amends SFFAS 4 to require full cost to
  include goods and services received from other federal entities even when unreimbursed. FASAB
  Interpretation 6 covers imputed intra-departmental costs.
- **SFFAS 6**, Accounting for Property, Plant, and Equipment. Governs construction in progress,
  capitalization, and depreciation, which is the L3 layer.
- **DoD FMR Volume 4 Chapter 19**, Managerial Cost Accounting. The Department's implementation of
  SFFAS 4.
- **DoD FMR Volume 6B Chapter 5**, Statement of Net Cost. Defines program gross cost as full cost
  including imputed cost.
- **DoD FMR Volume 11**, reimbursable operations, for the case where another entity performs work and
  is reimbursed.
- **DoD FMR Volume 4 Chapter 23**, which contains a section on identification and allocation of costs
  and states that general and administrative costs are normally allocated on total direct costs. A
  Department-sanctioned allocation convention, useful as a defensible default and as precedent that
  documenting allocation method is standard practice.
- **DoD FMR Volume 11B Chapter 12 does not apply.** Checked 2026-11-06, resolved negative. Volume 11B
  is reimbursable operations policy for working capital funds, and the chapter's headquarters cost
  provisions govern Defense Working Capital Fund activities. An appropriated-fund program office is
  not a DWCF activity. See gap G3.

## 5. The data environment

From direct report rather than documentation:

- General ledger data arrives partly as ingested flat files.
- Navy ERP refreshes on a roughly fifteen minute cadence, which makes near-real-time comparison
  technically possible once access exists.
- Historical data from legacy field-level systems is present and may still receive periodic updates,
  since execution cycles on old appropriations can remain open.
- Several hundred feeder systems exist in the broader population. Named examples include the
  procurement enterprise environment (PIEE), the travel system (DTS), and logistics systems. The full
  population has not been enumerated and cannot be produced from outside, since it requires that
  environment's own system catalog. Gap G5.

Two named feeders already matter to open questions. The procurement environment holds contract and
invoice evidence, which is L5 for contract cost. The travel system holds the fund citation that
settles the travel scope question empirically, because the appropriation on the voucher is the
determining fact.

## 6. Why carrier cost reconciliation is specifically hard

The structural reasons the layers disagree. These map onto the variance cause categories in
`BLUEPRINT.md` section 9, which is the point of listing them.

- **Class-level reporting against hull-level questions.** Reported cost is often stated for the
  program or class, so hull figures get derived and the derivation method becomes part of the answer.
  For the Ford class specifically, this is not a generic observation: GAO-17-575 states plainly that
  the Ford-class SAR reports only aggregate program cost for all ships in the class, not broken out
  by hull, and calls this out as a transparency limitation Congress itself flagged. The single most
  authoritative public document series does not hand you a clean per-hull total, which is the
  specific problem GAO-17-575's per-hull reporting recommendation (gap G4) is meant to fix.
- **Shared research and development.** A class cost with no direct hull attribution.
- **Multi-year incremental funding.** No single appropriation year owns the hull, so cost in a given
  fiscal year is ambiguous without stating whether it means the increment, the cumulative total, or
  the estimate at completion.
- **Advance procurement preceding the hull's own year.** Accumulation starts before the year the hull
  is nominally associated with.
- **Build duration of roughly a decade.** The record spans accounting system transitions, policy
  changes, and reorganizations.
- **Government-furnished equipment on separate lines.** In or out depending on the scope rule the
  document used.
- **Late settlements.** Change orders and claims resolve years after the work, so a figure stated at
  one time and restated later will differ for reasons that are correct.
- **Capitalization subset.** Only part of program cost becomes asset value, which guarantees an L2 to
  L3 difference that is right rather than wrong.
- **Manual adjustment practice in the asset layer.** The Navy's FY2025 agency financial report states
  that real property balances are reported via trial balances with on-top manual adjustments as
  needed to support an accurate CIP balance, and describes controls developed for NAVSEA shipbuilding
  program offices to set up accurate financial reporting. DODIG-2013-105 separately examined Navy ERP
  asset accounting for the aircraft and shipbuilding appropriations against a military equipment
  valuation material weakness. A documented, officially acknowledged variance cause for the
  ledger-to-asset comparison. Gap G7.
- **Hull-level reporting is a known, named deficiency with an owner.** GAO-17-575 (2017) assessed the
  CVN-79 cost estimate against GAO's Cost Estimating and Assessment Guide and found it not reliable,
  and found the $11.4 billion budgeted likely to be exceeded. It recommended that NAVSEA 05C develop
  per-hull life-cycle cost estimates starting with CVN-80, and that the program office prepare
  per-hull cost summary and funding summary sections within the Ford-class SAR. CVN-79's estimate is
  carried as a named case study in GAO's current cost estimating guide (GAO-20-195G). Gap G4.

## 7. Dated program facts for CVN-79

Collected during this effort, at the confidence noted. Seed figures and milestones with citations are
in `ring0/`, which is lead-grade material under the trust model.

- Second Ford-class carrier, built at Huntington Ingalls Newport News.
- At least five defensible program-inception dates, each correct for a different audience, which is
  why inception is a stated modeling decision rather than a looked-up fact: FY2001, when Congress
  begins advance procurement funding for the shared CVN-21 technology base that became CVN-78/79/80
  (the budget historian's view); FY2007, the first CVN-79-specific advance procurement increment,
  $45 million (the first dollar tagged to this hull); 15 January 2009, the Detail Design &
  Construction contract award (the contracts/program view); FY2013, CVN-79's procurement year, the
  convention most public reporting treats as "CVN-79 was procured"; and 22 August 2015, keel laid
  (the physical-construction view).
- Early cost estimates moved before settling. FY2009's budget estimated procurement cost at about
  $9.2 billion then-year, with the ship then scheduled for FY2012 procurement; FY2010's budget
  deferred the procurement year to FY2013. The FY2013 budget then estimated $11,411.0 million. The
  FY2019 budget separately estimated $11,341.4 million, a distinct point-in-time estimate six years
  later rather than a restatement of the FY2013 figure.
- Launched and dry-dock-flooded 29 October 2019; christened 7 December 2019.
- The statutory cost cap stood at $11.4 billion at the FY2013 budget position. SECNAV notified
  Congress of an increase to $12.936 billion in August 2023, per the CVN 78 MSAR of December 2023,
  which also reported the ship 91 percent complete. $12.936 billion is the current cap; $11.4 billion
  describes an earlier budget position, not today's limitation.
- Labor hours were estimated at 40.2 million against CVN-78's 49.0 million, an 18 percent reduction
  negotiated as of June 2015, per GAO-17-575.
- Builder's (Alpha) sea trials: departed Newport News 28 January 2026, completed 5 February 2026.
  Acceptance sea trials completed mid-August 2026. Navy delivery is currently projected March 2027,
  having slipped from an original 2022 target and then 2024.
- All figures above are seed-pass, secondary-source material (CRS, GAO, Wikipedia, trade press)
  carried at that confidence level in `ring0/cvn79_funding_history.csv` and not yet re-derived from
  primary documents (DAMIR SAR filings line by line, the actual P-1/SCN budget justification books,
  GTAS/CARS). That re-derivation is a Phase 1 task, not done here.

## 8. Changelog

- **2026-11-06, first version.** Written as an argument against a specific failure pattern.
- **2026-11-06, rewritten.** Converted from argument to domain reference. The failure-pattern
  argument moved into the blueprint as a design requirement, and the parts implying no design change
  were dropped. Added appropriation structure, standards, environment, and the carrier-specific
  reconciliation difficulties.
- **2026-11-06, research pass.** Section 3 replaced an unresolved question with established system
  history: the dated NAVSEA seam, the decision not to convert legacy data, which STARS instance and
  module applies, SABRS correctly placed, and NSMA surfaced as a fourth Navy general ledger missing
  from scope. Ruled out FMR Volume 11B Chapter 12, added Volume 4 Chapter 23. Added the CIP manual
  adjustment practice and the GAO per-hull recommendation.
- **2026-11-06, consolidation.** Document set reduced from seven files to four. Removed the producer
  map that duplicated the layer table in the blueprint, and reduced the standards section to
  citations with the application reasoning left in one place. Added the named cost-estimating offices,
  SUPSHIP's role, and the dated CVN-79 program facts, which had been scattered across files or held
  only in conversation.
- **2026-11-07, reconciliation pass.** Pulled forward findings already made in
  `ring0/ring0_research_notes.md`'s 2026-11-06 gate-check pass and not yet reflected here: the CVN-79
  cost cap revision to $12.936 billion (August 2023); the fuller dated-facts timeline, including the
  FY2001 and FY2007 advance-procurement anchors, the FY2009 estimate and FY2010 deferral, and the
  2026 sea-trial milestones; the named STARS-to-SABRS (S2S, FMP-4) migration project as a concrete
  lead for gap G2; DODIG-2012-051's Navy ERP SFIS/USSGL non-compliance finding and the August 2019
  ECC-to-HANA cutover date; and the Ford-class SAR's class-only, not hull-level, cost reporting as
  the specific GAO-flagged limitation behind gap G4. No gap was closed or opened by this pass; G2 is
  sharpened rather than resolved.
