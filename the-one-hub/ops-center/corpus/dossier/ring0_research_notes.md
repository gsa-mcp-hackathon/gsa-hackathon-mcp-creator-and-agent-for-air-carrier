# Ring 0 (Public/Congressional Anchor) — Research Notes, CVN-79

Status: **seed dataset from secondary sourcing** (news archives, CRS report mirrors, Wikipedia,
GAO report abstracts). This is NOT yet pulled from primary documents (DAMIR SAR PDFs line by
line, actual P-1/SCN budget justification books, GTAS/CARS). Treat every figure in
`cvn79_funding_history.csv` as `SECONDARY_NEWS` confidence until re-derived from a primary
source. That re-derivation is a Phase 1 task, not done here.

## Gate-check pass, 2026-11-06

Ran a verification pass against all seven files in this project, targeting the two claims most
load-bearing and most checkable against open sources.

**Resolved — the $11.341B figure.** CRS RS20643 (2018-05-18 edition) states directly: "The Navy's
proposed FY2019 budget estimates the ship's [CVN-79's] procurement cost at $11,341.4 million (i.e.,
about $11.3 billion) in then-year dollars." That's the exact figure that had been sitting in the
CSV as an `UNVERIFIED` "infobox total" with no real source. It isn't the same thing as the FY2013
$11,411M estimate two rows up — they're two different point-in-time budget estimates six years
apart, and the FY2019 one is actually slightly *lower*, before the 2023 cost-cap revision pushed it
up to $12,936M. Reclassified in the CSV: `TOTAL_COST_CITED` → `PROCUREMENT_COST_ESTIMATE`,
fiscal_year `2019`, confidence `UNVERIFIED` → `SECONDARY_NEWS`.

**Partially resolved — NAVSEA and Navy ERP.** Multiple Navy.mil/SeaPower Magazine sources on the
2019 Navy ERP tech refresh confirm the system serves "about 72,000 users across six Navy commands:
Naval Air Systems Command, Naval Sea Systems Command [NAVSEA], Naval Information Warfare Systems
Command, Naval Supply Systems Command, Strategic Systems Programs, [and] the Office of Naval
Research." So NAVSEA the command is confirmed on Navy ERP (HANA era) — a real, now-cited fact,
added to `reference.gl_system_era` with a `source_citation` column that didn't exist before (the
schema was asserting `confirmed_for_navsea = true` with no way to trace why). But this is a
command-level confirmation, not a PEO Aircraft Carriers/PMS 379 BSO-level one. It does not resolve
whether this specific program office's transactions ever routed through SABRS before landing on
Navy ERP. That stays open — don't let the command-level confirmation bleed into the narrower,
harder question.

**Correction — the ECC→HANA boundary date.** The schema had `2019-01-01` as a placeholder boundary
between Navy ERP ECC and Navy ERP HANA eras. The actual tech-refresh cutover completed August 19,
2019, per the Navy's own press release ("Navy Completes Its Largest Cloud Migration to Date").
Corrected in `gl_system_crosswalk.sql`.

**New source surfaced, not yet acted on.** GAO-26-107119 (2026) states "as of March 2026, Navy ERP
is the Navy's financial system of record" — consistent with everything above, nothing changed
structurally, but a newer citation than DODIG-2012-051, worth having on file.

**Schema gaps found and closed.** `docs/ai_agent_architecture.md` had Agent 1/5 writing to
`bronze.recon_candidates` and Agent 4 writing `lineage_candidate` rows — neither table actually
existed. Added both to `canonical_model.sql`. Also added a controlled `reference.milestone_type`
vocabulary table, since `milestone_type` was previously just a comment listing examples — free
text that would drift silently as more rows get added by hand or by Agent 1.

**One thing flagged, not fixed.** `TOTAL_COST_CITED`-style rows don't really belong in
`program_milestone` conceptually — that table is for discrete dated events, and a cited aggregate
budget figure is closer to a derived rollup. Reclassifying this one row as
`PROCUREMENT_COST_ESTIMATE` sidesteps the problem because it genuinely is a budget-year estimate
event, but if more "commonly cited total" rows show up that don't fit a real event type, that's a
sign `program_milestone` needs a sibling table for cited aggregates instead of forcing them into
the event log. Noted, not built — no evidence yet that it's needed.

## Ring 0 source taxonomy, formalized 2026-11-06

"Public docs" was too vague. Ring 0 covers several distinct document families, each with its own
reliability profile, named explicitly here instead of lumped together:

- **SARs** (Selected Acquisition Reports) — program/class-level cost baselines Congress receives.
  GAO-17-575's class-aggregation finding (below) is about this family specifically.
- **J-Books** — the Navy's budget justification materials: R-1/R-2 (RDT&E), P-1/P-5 (procurement),
  O-1 (O&M). What `cvn79_funding_history.csv`'s `appropriation_or_doc` column calls "SCN"/"RDT&E"
  line items are J-Book figures. Calling them "budget books" generically, as earlier passes did,
  undersold how specific and checkable these documents actually are.
- **CRS reports** — RS20643 and similar; Congress's own research arm synthesizing the above.
- **GAO reports** — independent reviews (GAO-17-575; GAO-26-107119 on Navy ERP's current status).
- **DODIG reports** — the Pentagon's own IG, including material weakness findings (DODIG-2012-051
  on Navy ERP/SFIS compliance). This is a standing Ring 0 source category for this project, not a
  one-off citation — DODIG findings bear directly on the audit-readiness audience this product is
  eventually meant to serve, and should get checked on every future gate-check pass.
- **Secondary tier** — news archives, Wikipedia. Useful for dates and milestones, lowest
  confidence, everything in this tier gets re-verified against one of the above before it's
  trusted. This is the tier the current CSV mostly still sits in.

## The "program born" problem, concretely

Four defensible anchor dates surfaced, each correct for a different audience:

| Date | What it marks | Who cares |
|---|---|---|
| FY2001 | Congress begins advance procurement funding for the shared CVN-21 program (pre-split between what became CVN-78/79/80) | Budget historian tracing the technology base (EMALS, AAG, Dual Band Radar) |
| FY2007 | First CVN-79-*specific* advance procurement increment ($45M) | PPBE view — first dollar tagged to this hull |
| 15 Jan 2009 | Construction (DD&C) contract award | Contracts/program view |
| FY2013 | CVN-79's procurement year per the budget (the year its full procurement cost is "on the books") | CRS/GAO convention — this is the date most public reporting treats as "CVN-79 was procured" |
| 22 Aug 2015 | Keel laid | Physical construction / shipyard milestone view |

Recommendation given "go back as far as it can": carry **all** of these as typed events in the
canonical model (see `schema/canonical_model.sql`, `program_milestone` table) rather than picking
one. Let the product's UI ask the viewer which lens they want ("budget view starts FY2001",
"hull-specific view starts FY2007", "contract view starts 2009"). Don't collapse them into a
single "program start" field — that was the mistake to avoid, not a formatting choice.

## The finding that changes the plan: SARs don't give you a hull-specific number cleanly

GAO-17-575 states plainly that the Ford-class program's Selected Acquisition Reports report only
**aggregate program cost for all ships in the class**, not broken out by hull — and calls this out
as a transparency limitation Congress itself flagged. That means the single most authoritative
public document series (the SAR) does not hand you a clean "CVN-79 total cost" figure. You have to
either:

1. Use the CVN-79-specific procurement-cost-cap figures (which DO exist — $11.4B then-year at
   FY2013 PB, revised cost limitation baseline $12.936B as of Aug 2023) as the hull-specific
   procurement anchor, and
2. Build an explicit, documented allocation methodology for the *shared* RDT&E (EMALS, AAG, Dual
   Band Radar, PE 0604112N "CVN 78-80") rather than treating it as directly attributable to CVN-79.

This allocation methodology is a real open design decision, not something I can resolve by
searching harder. It needs a cost-estimating judgment call (pro-rata by hull? fixed CVN-78 bears
all first-of-class R&D? something else?), and whoever signs off on this product needs to see that
judgment call documented, not hidden inside a pipeline.

## GL system chain — supports your three-system call, with one wrinkle

Your list (STARS-FL, SABRS, Navy ERP early + current) matches a real, documented Navy transition:
the Navy ran an actual "STARS-to-SABRS" (S2S) migration project (FMP-4) to move Navy Budget
Submitting Offices from STARS-FL onto SABRS before later consolidating into Navy ERP. SABRS itself
is officially described as serving the Marine Corps and only "select" Navy BSOs — so the open
question for the pilot is whether NAVSEA/PEO Carriers' BSO was one of the ones routed through
SABRS, or went STARS-FL → Navy ERP directly without a SABRS stop. That's a one-question check
against NAVSEA's financial systems history once you have the access to ask it; don't guess at it
in the schema, just leave the slot open (see `gl_system_crosswalk.sql`).

One more documented wrinkle worth carrying into the crosswalk confidence design: DODIG-2012-051
found that Navy ERP, as implemented, did **not** comply with the Standard Financial Information
Structure or the USSGL at the time of that audit. That's not a hypothetical risk I'm flagging —
it's a cited finding. Expect a real share of early Navy ERP mappings to land as `DERIVED` or
`ESTIMATED` confidence, not `EXACT`, and build the product to surface that honestly rather than
assume Navy ERP data is clean just because it's the modern system.

## Sources (secondary, for this seed pass — re-verify against primary documents in Phase 1)

- CRS Report RS20643, multiple editions 2006–2013 (Navy Ford-class carrier program background),
  via everycrsreport.com
- GAO-17-575, *Ford-Class Carriers: Ensuring Adequate Design and Construction Knowledge...*
- CVN 78 MSAR, December 2023 (DAMIR / esd.whs.mil FOIA reading room)
- Wikipedia / Wikiwand, "USS John F. Kennedy (CVN-79)" and "Gerald R. Ford-class aircraft carrier"
- uscarriers.net CVN-79 history page; TWZ, Janes.com reporting on 2026 sea trials
- DODIG-2012-051, *Navy Enterprise Resource Planning System Does Not Comply With SFIS and USSGL*
- highergov.com program profile for SABRS; SECNAV FMP-4 (STARS-to-SABRS) project description
