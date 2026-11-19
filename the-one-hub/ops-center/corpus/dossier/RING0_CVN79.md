# RING0_CVN79.md
## CVN-79 (USS John F. Kennedy) Public Data Dossier

**Compiled:** 2026-11-07
**Purpose:** Ring 0 (public / zero-access) source layer for the Air Carrier program cost product. Every fact carries its source URL. Nothing here is authoritative for a reported number. Everything here is a lead that names where the authoritative number lives.
**Trust rule applied:** Public and secondary sources generate investigative leads and collection requirements. They do not populate canonical data. Where sources disagree, the disagreement is recorded in Part E rather than resolved.

**Contents.** Parts A to D are the dated spine, the source catalog and the tracing identifiers. Part E is the variance record, Part F the gap feed, Part G the key set, Part H the source index. Parts I to M were added 2026-11-08: asset valuation and evaluation, government furnished property and the F-35 precedent, the cost increase timeline against the official cost categories, the industrial map of who builds what, and the clue map for costs outside the two HII contracts. Part N is the analyst reconstruction of the hull total.

> **Revision 2026-11-08, second pass — read this before using any Part N figure.** A reader-supplied USAspending extract showed that the Construction Preparation contract N00024-09-C-2116 has obligated **$4,519,300,323.83**, against roughly $1.08B carried in the first version of Part N. The earlier figure had been built by summing **announced** DoD contract modifications, a method that cannot produce a contract total. The correction is at **E-13**, the method post-mortem at **N.7 Error 3**, and it moves hull attribution from 42.2% to **75.8%**. Also revised in this pass: N.4 (rewritten for both prime contracts), N.6a and N.6b (new), N.8, N.9, D.9 (DCARC CSDR rating is **Red**), L.2 (KATO Engineering; EMALS/AAG contract values resolved), Part G key set (**identifier collision warning**), E-14, E-15, G21 closed, G24 to G28 opened. **Third pass, same day:** G27 closed against the FPDS-NG ATOM feed and both of its contracts removed from this hull, one of them having never belonged to the vendor it was carried under; the lookup opened **E-16**.

**Relationship to the rest of the repo.** This file is the source catalog and identifier set. It does not restate design, which lives in `BLUEPRINT.md`, or domain reference, which lives in `BACKGROUND.md`. Gaps are numbered in `LOG.md` and referenced here by number rather than re-registered. `ring0/ring0_research_notes.md` keeps the 2026-11-06 gate-check narrative and the secondary-source seed pass; where the two files cover the same ground, the reconciliation is itemized in Part E.0 below and this file carries the identifier and source detail.

**Grading legend used below:**
- `[P]` Primary government document (budget exhibit, SAR/MSAR, GAO/DODIG report, statute, FMR)
- `[S]` Secondary reporting quoting a primary document
- `[T]` Tertiary / aggregator, use only to find the primary
- `[C]` Conflicting with another source in this file, see Part E

---

# PART A. Program spine, dated

These are the anchor dates and figures. Timestamps matter more than values, because the same ship has a different cost at every timestamp.

| Date | Event | Source |
|---|---|---|
| May 2004 | Construction Preparation contract awarded (funds research, design) | [P] [FY2027 MSAR](https://www.esd.whs.mil/Portals/54/Documents/FOID/Reading%20Room/Selected_Acquisition_Reports/PB_2027_MSARs/CVN_78_MSAR_FY2027_PBv2.pdf) |
| Aug 2008 | USD(AT&L) DAB authorized CVN-78 production and CVN-79 construction preparation phase | [P] [FY2022 SAR](https://www.esd.whs.mil/Portals/54/Documents/FOID/Reading%20Room/Selected_Acquisition_Reports/FY_2022_SARS/CVN%2078%20_SAR_DEC_2022_final.pdf) |
| Jan 2009 | CVN-79 Construction Preparation contract awarded (N00024-09-C-2116) | [P] [FY2023 MSAR](https://www.esd.whs.mil/Portals/54/Documents/FOID/Reading%20Room/Selected_Acquisition_Reports/FY_2023_SARS/CVN%2078%20MSAR%20Dec%202023.pdf) |
| 29 May 2011 | Named *John F. Kennedy* by SECNAV Ray Mabus at the JFK Presidential Library | [P] [CRS RS20643](https://www.congress.gov/crs-product/RS20643); [NavSource](https://www.navsource.net/archives/02/79.htm) |
| Mar 2013 | Construction Preparation contract extended through FY2013 | [P] [FY2023 MSAR](https://www.esd.whs.mil/Portals/54/Documents/FOID/Reading%20Room/Selected_Acquisition_Reports/FY_2023_SARS/CVN%2078%20MSAR%20Dec%202023.pdf) |
| FY2013 | Ship procured (authorization year moved FY2012 to FY2013) | [P] [CRS RS20643](https://www.congress.gov/crs-product/RS20643) |
| 5 Jun 2015 | DD&C contract awarded, $3,352,611,760 FPIF target (N00024-15-C-2114), plus $941,175,219 CPIF mod to the CP contract. Total announced $4.29B | [P] [HII release](https://hii.com/news/hii-awarded-3-35-billion-contract-for-detail-design-and-construction-of-aircraft-carrier-john-f-kennedy-cvn-79/); [S] [USNI](https://news.usni.org/2015/06/08/hii-awarded-4-29-billion-in-contracts-for-john-f-kennedy-carrier-construction) |
| 20-22 Jul / Aug 2015 | Keel laid | [T] [Wikipedia, cites Naval Vessel Register](https://en.wikipedia.org/wiki/USS_John_F._Kennedy_(CVN-79)) `[C]` |
| Jun 2017 | 50% structurally erected, 224 of 447 erectables landed | [P] [FY2023 MSAR](https://www.esd.whs.mil/Portals/54/Documents/FOID/Reading%20Room/Selected_Acquisition_Reports/FY_2023_SARS/CVN%2078%20MSAR%20Dec%202023.pdf) |
| Apr 2018 | 75% structurally erected, 341 of 447 erectables landed | [P] same |
| 1 Oct 2019 | Crew activated as Pre-Commissioning Unit (PCU) | [T] [seaforces](https://www.seaforces.org/usnships/cvn/CVN-79-USS-John-F-Kennedy.htm) |
| 29 Oct 2019 | Dry dock flooded / launched | [T] [Wikipedia](https://en.wikipedia.org/wiki/USS_John_F._Kennedy_(CVN-79)) |
| 7 Dec 2019 | Christened by Caroline Kennedy | [T] same |
| 20 Dec 2019 | FY2020 NDAA (P.L. 116-92) Sec. 124 mandates F-35C capability before PSA completion | [P] [CRS RS20643](https://www.congress.gov/crs-product/RS20643) |
| Nov 2020 | NTE $284,285,022 FPIF mod for single-phase delivery and Joint Strike Fighter work | [S] [HigherGov on N0002415C2114](https://www.highergov.com/contract/N0002415C2114/) |
| Aug 2021 | Navy raised CVN-79 cost baseline $1.3B to $12.7B, primarily contract overruns. Ship then over 88% complete | [P] GAO, quoted in [CRS RS20643 Feb 2024](https://www.everycrsreport.com/files/2024-02-05_RS20643_30f85cf958d29497fe153cd4363584ede7f4e3dd.pdf) |
| 23 Jun 2023 | $393.3M in mods shift PSA work into baseline construction; delivery reset to 31 Jul 2025 | [P] [HII release](https://www.hii.com/news/hii-is-awarded-contract-modification-for-aircraft-carrier-john-f-kennedy-cvn-79) |
| Aug 2023 | SECNAV notified Congress of raising the CVN-79 **Cost Limitation Baseline to $12.936B** | [P] [FY2023 MSAR](https://www.esd.whs.mil/Portals/54/Documents/FOID/Reading%20Room/Selected_Acquisition_Reports/FY_2023_SARS/CVN%2078%20MSAR%20Dec%202023.pdf) |
| Dec 2023 | Ship 91% complete; DD&C contract 81.3% complete by dollars | [P] same |
| Sep 2024 | Faulty welds disclosed at NNS, referred to DOJ; HASC opens investigation | [S] [USNI](https://news.usni.org/2024/09/27/lawmakers-announce-investigation-into-faulty-submarine-carrier-welding-at-newport-news-shipbuilding-ships-affected-in-low-single-digits-officials-say) |
| 8 Apr 2025 | PEO Carriers RADM Casey Moton tells SASC Seapower the ship is 95% complete, delivery "pressurized by remaining critical path work" | [S] [Inside Defense](https://insidedefense.com/daily-news/cvn-79-delivery-pushed-back-navy-official-tells-lawmakers); [USNI](https://news.usni.org/2025/04/09/first-columbia-class-sub-two-aircraft-carriers-face-delivery-delays-navy-officials-tell-senate) |
| Jun/Jul 2025 | FY2026 budget books move delivery July 2025 to **March 2027**, preliminary acceptance TBD | [P] quoted in [CRS RS20643](https://www.congress.gov/crs-product/RS20643); [S] [USNI](https://news.usni.org/2025/07/07/carrier-john-f-kennedy-delivery-delayed-2-years-fleet-will-drop-to-10-carriers-for-1-year) |
| 21 Nov 2025 | Four-part mod across both contracts: $60,000,000 cost-reimbursable, $58,556,527 CPIF, $20,924,993 FPIF, $3,436,456 CPFF | [P] DoW contract announcement via [GlobalSecurity](https://www.globalsecurity.org/military/library/news/2025/11/dod-contracts_4340534.htm) |
| 28 Jan 2026 | Builder's trials begin, first time underway | [S] [USNI](https://news.usni.org/2026/01/28/carrier-uss-john-f-kennedy-gets-underway-for-first-time-ahead-of-builders-trials) |
| 4 Feb 2026 | Returns from builder's trials, eight days at sea | [S] [Stars and Stripes](https://www.stripes.com/branches/navy/2026-02-04/uss-john-f-kennedy-returns-sea-trials-20626354.html) |
| 14 Mar 2026 | Navy extends USS Nimitz (CVN-68) service ten months to March 2027 to hold the 11-carrier floor | [S] [Stars and Stripes](https://www.stripes.com/branches/navy/2026-03-15/uss-nimitz-service-life-extended-21073175.html) |
| 21 Apr 2026 | FY2027 PB released; FY2027 MSAR data date | [P] [FY2027 MSAR](https://www.esd.whs.mil/Portals/54/Documents/FOID/Reading%20Room/Selected_Acquisition_Reports/PB_2027_MSARs/CVN_78_MSAR_FY2027_PBv2.pdf) |
| 2 Jul 2026 | GAO-26-108457 reports program unit costs up 3%, about $480M in one year | [P] [GAO-26-108457](https://www.gao.gov/products/gao-26-108457), quoted in [CRS RS20643](https://www.congress.gov/crs-product/RS20643) |
| 12-15 Aug 2026 | Acceptance trials, four days underway | [S] [HII via ArmyRecognition](https://www.armyrecognition.com/news/navy-news/2026/future-uss-john-f-kennedy-aircraft-carrier-enters-final-trials-before-2027-u-s-navy-delivery) |
| 29 Sep 2026 | **Preliminary acceptance.** Ship departs NNS for Naval Station Norfolk waterfront | [P] [HII release](https://www.hii.com/news/hiis-newport-news-shipbuilding-achieves-preliminary-acceptance-of-john-f-kennedy-cvn-79); [S] [USNI](https://news.usni.org/2026/09/29/navy-partially-accepts-carrier-john-f-kennedy-from-hii-newport-news-shipbuilding) |
| 13-14 Oct 2026 | First F-35C launch and arrested recovery on a Ford-class ship, VX-23 aircraft compatibility testing | [S] [Naval News](https://www.navalnews.com/naval-news/2026/10/f-35c-commences-testing-on-ford-class-carrier-john-f-kennedy/) |
| 21 Apr 2026 | **FY2027 PB raises the Total Ship Estimate to $13,409.970M**, +$213.970M, attributed to AAG Water Twister MOD II testing, delay and disruption, time-related services, continued AWE work, wage and overtime increases, and a manning surge for sea trials | [P] [PB2027 SCN book, Exhibit P-5c](https://www.secnav.navy.mil/fmc/fmb/Documents/27pres/SCN_Book.pdf) |
| Mar 2027 (planned) | Delivery and commissioning. Award to delivery 141 months; construction start to delivery 193 months | [P] PB2027 SCN book |
| Jul 2027 (planned) | **Completion of Fitting Out** | [P] PB2027 SCN book |
| Jun 2028 (planned) | **Obligation Work Limit Date.** CFO plus 11 months, confirming OPNAVINST 4700.8M | [P] PB2027 SCN book |
| 2029 (planned) | Homeport shift to Naval Base Kitsap; $145M electrical systems overhaul underway there | [S] [Stars and Stripes](https://www.stripes.com/branches/navy/2026-02-04/uss-john-f-kennedy-returns-sea-trials-20626354.html) |

**The authoritative cost figure, as of the FY2027 submission, is $13,409.970M.** Parts B through M were written against the FY2026 figure of $13,196.0M and still cite it where the source does. Part N uses the current figure and reconciles it.

**The headline schedule variance, stated by CRS:** the FY2013 budget submission (the procurement year) showed a September 2022 delivery. The FY2026 submission shows March 2027. That is a **54-month, four-and-a-half year delay**. [CRS RS20643](https://www.congress.gov/crs-product/RS20643)

---

# PART B. String 1: insight, news, lessons learned, cost growth, political and societal impact

## B.1 The causal chain the Navy and the builder state publicly

Four causes recur across primary documents. They are the only publicly attributed causes, which makes them the starting set for a variance cause taxonomy.

1. **Advanced Weapons Elevators (AWE).** Eleven elevators. Installation and certification ran behind forecast. GAO: "Continuing delays to Advanced Weapons Elevators construction put CVN 79's July 2025 delivery at risk, according to program officials." [GAO June 2025, quoted in CRS RS20643](https://www.congress.gov/crs-product/RS20643)
2. **Advanced Arresting Gear (AAG).** Certification work drove the budget footnote language verbatim: "The CVN 79 delivery date shifted from July 2025 to March 2027 (preliminary acceptance TBD) to support completion of Advanced Arresting Gear (AAG) certification and continued Advanced Weapons Elevator (AWE) work." [FY2026 SCN book, quoted in CRS RS20643](https://www.congress.gov/crs-product/RS20643). Note the fourth AAG engine was never installed on Ford-class as a cost savings measure. [DOT&E FY2023](https://www.dote.osd.mil/Portals/97/pub/reports/FY2023/navy/2023cvn78.pdf)
3. **Material availability and workforce.** "Program officials attributed this delay to construction material availability and persistent shipyard workforce issues that the program is working to mitigate with revised schedules and worker incentives." [GAO June 2025 via TWZ](https://www.twz.com/sea/future-uss-john-f-kennedy-second-ford-class-carrier-has-set-sail-for-the-first-time)
4. **Scope added during construction, not overrun.** The 2020 switch from two-phase to single-phase delivery, and the 2023 move of PSA work into the construction contract, both added work to the baseline. [HII June 2023](https://www.hii.com/news/hii-is-awarded-contract-modification-for-aircraft-carrier-john-f-kennedy-cvn-79)

## B.2 The lessons-learned claim, and why it is a cost-attribution problem

HII's own framing is the single most useful sentence in the public record for a cost model, because it asserts that the second-ship learning benefit did not land:

> "Specifically, *John F. Kennedy* (CVN 79) construction was fairly advanced when many *Ford* lessons were realized, precluding timely implementation of lessons learned for *Kennedy*. In contrast, *Enterprise* (CVN 80) and *Doris Miller* (CVN 81) have been able to incorporate, leverage and capitalize on *Ford* lessons learned earlier in the construction process."
> Todd Corillo, NNS spokesperson, quoted in [USNI 7 Jul 2025](https://news.usni.org/2025/07/07/carrier-john-f-kennedy-delivery-delayed-2-years-fleet-will-drop-to-10-carriers-for-1-year)

The Navy's congressional testimony version: initial design problems from Ford were resolved, but "early class production-focused challenges and associated learning continue on CVN 79." [Stars and Stripes](https://www.stripes.com/branches/navy/2025-07-08/kennedy-aircraft-carrier-delay-18372497.html)

GAO found this risk in advance, in 2014 and 2017. The DD&C contract was priced on an 18% man-hour reduction versus CVN-78. GAO wrote that reducing CVN-79 construction by roughly 7 to 12 million labor hours versus CVN-78 "would be unprecedented in aircraft carrier construction," and that the largest reduction ever achieved hull to hull was 9.3% (CVN-69 vs CVN-68). [GAO-15-22](https://www.gao.gov/assets/gao-15-22.pdf)

**Lead:** the 18% contract man-hour reduction target, the realized reduction (reported at 17% in one SAR, with the SAR noting "cost performance is slightly reduced from the 18 percent contract target... largely from the delayed availability of certain categories of material"), and the current realized figure, form a directly measurable learning-curve variance. [Inside Defense quoting the SAR](https://insidedefense.com/insider/nns-cvn-79-60-percent-structurally-complete). GAO's 2026 figure for the class: "a production man-hours step down that is equivalent to an 82 percent learning curve since CVN 79." [quoted in CRS RS20643](https://www.congress.gov/crs-product/RS20643)

## B.3 GAO's standing judgment on the estimate itself

This matters for the methodology deliverable more than the hull answer. GAO assessed the CVN-79 estimate against the GAO Cost Estimating and Assessment Guide (GAO-09-3SP) and found it **not reliable**: it substantially met one of four characteristics and failed the others. Specific findings worth carrying forward:

- The cost cap drove the estimate rather than the reverse. "Rather than the program cost estimate informing the cost cap, the cost cap informed the program cost estimate."
- No independent cost estimate existed before Congress raised the cap from $8.1B to $11.5B in 2013, and none before construction start.
- NAVSEA 05C's estimate "is not realistic, as it does not accurately" reflect shipbuilder performance.
- CAPE's independent cost estimate and NCCA's two labor-hour estimates were both higher than the program estimate. The specific figures were **redacted** because NAVSEA contracting deemed them sensitive.
- GAO recommended NAVSEA 05C update the CVN-79 estimate as part of a Ford-class **life-cycle cost estimate**, and recommended per-hull cost and funding summary sections in the Ford-class SAR.

Source: [GAO-17-575 full report](https://www.gao.gov/assets/gao-17-575.pdf), [highlights](https://www.gao.gov/assets/gao-17-575-highlights.pdf), [product page](https://www.gao.gov/products/gao-17-575)

Earlier GAO on the same program: [GAO-13-396](https://www.gao.gov/assets/gao-13-396.pdf) (recommended deferring the DD&C award), [GAO-15-22](https://www.gao.gov/assets/gao-15-22.pdf) (recommended Congress revise the cost cap approach), [GAO-16-84T](https://www.gao.gov/assets/gao-16-84t.pdf) ("Poor Outcomes Are the Predictable Consequence..."), [GAO-18-238SP](https://www.gao.gov/assets/gao-18-238sp.pdf) (Navy accepts ships with large numbers of uncorrected deficiencies).

## B.4 Statutory and political structure

**The 11-carrier floor.** 10 U.S.C. 8062(b) requires not less than 11 operational aircraft carriers. It also defines an operational carrier to include one "temporarily unavailable for worldwide deployment due to routine or scheduled maintenance or repair." 10 U.S.C. 8062(g), added by Sec. 1054 of the FY2021 NDAA (P.L. 116-283), bars retiring a nuclear carrier before its first refueling. [CRS RS20643](https://www.congress.gov/crs-product/RS20643)

**The "Nimitz Gap."** CVN-79's delay collided with the planned May 2026 Nimitz decommissioning. The Navy chose to extend Nimitz to March 2027 rather than seek a waiver. Precedent cited: Congress refused a comparable waiver in 2009 for USS Enterprise. [Stars and Stripes 27 Feb 2026](https://www.stripes.com/branches/navy/2026-02-27/nimitz-gap-retirement-oldest-aircraft-carrier-20894757.html), [Stars and Stripes 15 Mar 2026](https://www.stripes.com/branches/navy/2026-03-15/uss-nimitz-service-life-extended-21073175.html), [National Interest](https://nationalinterest.org/blog/buzz/uss-nimitz-wont-be-decommissioned-until-2027-ps-031626)

**Cost-model consequence:** the schedule delay on CVN-79 created a direct, traceable cost on a *different* hull. The Nimitz ten-month extension, and the NNS advance planning and long-lead material contract for Nimitz inactivation and defueling, are CVN-79 schedule consequences that will never appear in a CVN-79 line of accounting. This is a concrete, defensible example of why hull-scoped cost understates program cost.

**The F-35C mandate.** HASC seapower subcommittee language in the FY2020 NDAA barred the Navy from accepting CVN-79 without the ability to embark the F-35C. That mandate is a named driver of the single-phase delivery decision and therefore of the scope added to the construction contract. [Naval News](https://www.navalnews.com/naval-news/2026/10/f-35c-commences-testing-on-ford-class-carrier-john-f-kennedy/), [CRS RS20643](https://www.congress.gov/crs-product/RS20643)

**Faulty welds, Sept-Oct 2024.** NNS self-reported to the Navy and DOJ that welders "knowingly circumvented certain welding procedures." HASC leadership opened an investigation and demanded "absolute transparency." SECNAV Del Toro told lawmakers on 3 Oct 2024 that more than two dozen ships, 26 total, were affected, three of them in service. HII stated no indication of malicious intent. Ford-class carriers under construction were in the analysis population.
Sources: [USNI 27 Sep 2024](https://news.usni.org/2024/09/27/lawmakers-announce-investigation-into-faulty-submarine-carrier-welding-at-newport-news-shipbuilding-ships-affected-in-low-single-digits-officials-say), [Military.com 7 Oct 2024](https://www.military.com/daily-news/2024/10/07/navy-says-26-ships-affected-faulty-welds-newport-news-shipyard-virginia.html), [Navy Times](https://www.navytimes.com/news/your-navy/2024/09/27/lawmakers-demand-answers-over-reports-of-faulty-navy-ship-welding/), [Maritime Executive](https://maritime-executive.com/article/workers-at-newport-news-made-faulty-welds-on-u-s-navy-carriers-and-subs)
**Open collection requirement:** whether any CVN-79 rework cost was booked, and against which contract line and appropriation year, is not public.

## B.5 Industrial base and societal footprint

- Newport News Shipbuilding is the only US shipyard able to build large-deck nuclear carriers. All US carriers procured since FY1958 were built there. [CRS RS20643](https://www.congress.gov/crs-product/RS20643)
- The carrier construction industrial base as of 2019 included roughly **2,000 supplier firms in 46 states**. [CRS RS20643](https://www.congress.gov/crs_external_products/RS/PDF/RS20643/RS20643.297.pdf)
- NNS employs **over 25,000 Virginians** and is the Commonwealth's largest industrial employer. [Virginia Economic Development Partnership](https://www.vedp.org/success-story/huntington-ingalls-industries-builds-virginia)
- Congressional district VA-03. CAGE codes: **43689** (Huntington Ingalls Inc / NNS), 6BTC1 (HII Inc), 34293 (Ingalls, Pascagoula). UEI F9SDJAZFTLG6 (HII parent). [govconinabox](https://www.govconinabox.com/explore/contractors/profile/huntington-ingalls-industries-inc-f9sdja)
- The Ford-class design was justified in part on reduced crew size, with the Navy estimating roughly **$4 billion lower 50-year life-cycle O&S cost per ship** versus Nimitz-class. [CRS RS20643](https://www.congress.gov/crs_external_products/RS/PDF/RS20643/RS20643.243.pdf). The FY2027 FYDP materials state a $5 billion ownership-cost reduction. [Naval News](https://www.navalnews.com/naval-news/2026/05/u-s-navy-reveals-future-plans-for-its-aircraft-carrier-fleet/) `[C]`
- Broader context on the industrial base, useful for the risk layer: [CSIS, Outlining the Challenges to U.S. Naval Shipbuilding, Dec 2025](https://csis-website-prod.s3.amazonaws.com/s3fs-public/2025-12/251216_Daniels_Naval_Shipbuilding.pdf), [GAO Navy Shipbuilding: Enduring Challenges Call for Systemic Change](https://www.gao.gov/assets/880/876409.pdf), [CBO testimony on shipbuilding and the industrial base](https://www.cbo.gov/publication/62375)

## B.6 Test and evaluation record (independent of the program office)

DOT&E annual reports are a separate authority from the program office and the budget books, which makes them a cross-check on stated cause.
- [DOT&E FY2025 CVN 78 article](https://www.dote.osd.mil/Portals/97/pub/reports/FY2025/navy/2025cvn78.pdf): "CVN 79 delivery is now scheduled for FY27, two years later than reported in the FY24 Annual Report. A combination of supply chain impediments, difficulties with AAG installation and certification, and Advanced Weapons Elevator (AWE) installation progressing slower than forecasted all contributed to this delay."
- [DOT&E FY2024](https://www.dote.osd.mil/Portals/97/pub/reports/FY2024/navy/2024cvn78.pdf)
- [DOT&E FY2023](https://www.dote.osd.mil/Portals/97/pub/reports/FY2023/navy/2023cvn78.pdf): CVN 79 delivery then late FY25, delay attributed to the Navy moving work from the post-delivery period into construction.
- Index of all DOT&E annual reports: https://www.dote.osd.mil/Annual-Reports/

Note the cause mix shifts year over year across DOT&E, GAO, and the budget footnote for the same delay. That is itself a finding, not noise, and belongs in the variance record.

---

# PART C. String 2: the complete public cost source catalog

Organized by document family. For each: what it is, what it uniquely carries, and the URL.

## C.1 Modernized Selected Acquisition Report (MSAR) — the single richest public source

This is the document to start from. It is the acquisition-side cost record, released through the OSD FOIA reading room, and it carries contract numbers, CAGE codes, percent complete, EVM variances, funding by appropriation and line item, and the Cost Limitation Baseline history.

- **Current: CVN 78 MSAR, FY2027 PB, data date 21 April 2026**
  https://www.esd.whs.mil/Portals/54/Documents/FOID/Reading%20Room/Selected_Acquisition_Reports/PB_2027_MSARs/CVN_78_MSAR_FY2027_PBv2.pdf
- Full PB 2027 MSAR directory (includes AAG MSAR, which carries CVN-79 arresting gear separately):
  https://www.esd.whs.mil/Records-Declass/FOIA/Reading-Room/Reading-Room-List_2/Selected_Acquisition_Reports/PB_2027_MSARs/
- CVN 78 MSAR Dec 2023: https://www.esd.whs.mil/Portals/54/Documents/FOID/Reading%20Room/Selected_Acquisition_Reports/FY_2023_SARS/CVN%2078%20MSAR%20Dec%202023.pdf
- CVN 78 SAR Dec 2022: https://www.esd.whs.mil/Portals/54/Documents/FOID/Reading%20Room/Selected_Acquisition_Reports/FY_2022_SARS/CVN%2078%20_SAR_DEC_2022_final.pdf
- CVN 78 SAR Dec 2021: https://www.esd.whs.mil/Portals/54/Documents/FOID/Reading%20Room/Selected_Acquisition_Reports/FY_2021_SARS/22-F-0762_CVN_78_SAR_2021.pdf
- CVN 78 SAR Dec 2018 (redacted): https://www.esd.whs.mil/Portals/54/Documents/FOID/Reading%20Room/Selected_Acquisition_Reports/FY_2018_SARS/19-F-1098_DOC_57_Navy_CVN_78_SAR_Dec_2018_REDACTED.pdf
- AAG MSAR Dec 2023 (documents transfer of one AAG engine set from CVN 78 to CVN 79, dated 19 May 2016): https://www.esd.whs.mil/Portals/54/Documents/FOID/Reading%20Room/Selected_Acquisition_Reports/FY_2023_SARS/AAG%20MSAR%20Dec%202023.pdf
- Reading-room year directories: https://www.esd.whs.mil/Records-Declass/FOIA/Reading-Room/Reading-Room-List_2/Selected_Acquisition_Reports/

**Build a full back-run of these by year.** The year-over-year delta in the MSAR is the public variance ledger.

**Important limit on this family, do not overread it.** GAO-17-575 found that the Ford-class SAR reports **aggregate program cost for all ships in the class**, not broken out by hull, and flagged that as a transparency limitation Congress itself raised. GAO therefore recommended adding per-hull cost and funding summary sections to the Ford-class SAR. So the MSAR gives genuine CVN-79-specific detail at the **contract and subprogram** level (contract numbers, target price, percent complete, EVM variance, Cost Limitation Baseline) while **not** giving a clean hull-allocated total program cost. The hull-specific anchors that do exist publicly are the procurement cost cap and the Cost Limitation Baseline, not a SAR line. Whether GAO's per-hull recommendation was ever implemented is open work under **G4**. [GAO-17-575](https://www.gao.gov/assets/gao-17-575.pdf)

Program office identified in the MSAR: **Program Executive Office, Aircraft Carriers (PEO Carriers)**. ACAT level: **IC** (per [DOT&E](https://www.dote.osd.mil/Portals/97/pub/reports/FY2025/navy/2025cvn78.pdf)). Expected service life 50 years, operational 2017-2094 for CVN 78.

## C.2 SCN Justification Book (J-Book) — the budget authority record

Appropriation **1611N, Shipbuilding and Conversion, Navy**. CVN-79 lives in **Budget Activity 02 (Other Warships), P-1 Line Item 2001, Carrier Replacement Program, BLI 2001 / 200100.**

Relevant exhibits inside the book, each of which answers a different question:
- **P-1** total obligational authority by line
- **P-40** budget line item justification, the funding profile by fiscal year including prior years and to-complete
- **P-5 / P-5a** cost analysis by category (plans, basic construction, change orders, electronics, propulsion equipment, HM&E, ordnance, other cost, escalation). This is the closest public approximation of a cost breakdown structure.
- **P-10** advance procurement requirements analysis, including nuclear propulsion equipment
- **P-21** production schedule, award to delivery months, construction start to delivery months, delivery date, and **Obligation Work Limiting Date**

Direct links by year (note: secnav.navy.mil blocks automated fetching, open these in a browser):
- FY2027: https://www.secnav.navy.mil/fmc/fmb/Documents/27pres/SCN_Book.pdf
- FY2025: https://www.secnav.navy.mil/fmc/fmb/Documents/25pres/SCN_Book.pdf
- FY2024: https://media.defense.gov/2023/Mar/29/2003188820/-1/-1/0/SCN_BOOK.PDF
- FY2022: https://www.secnav.navy.mil/fmc/fmb/Documents/22pres/SCN_Book.pdf
- FY2017: https://www.secnav.navy.mil/fmc/fmb/Documents/17pres/SCN_Book.pdf
- FY2014: https://www.secnav.navy.mil/fmc/fmb/Documents/14pres/SCN_BOOK.pdf
- FY2012: https://www.globalsecurity.org/military//library/budget/fy2012/navy/scn-book.pdf
- FY2011: https://www.secnav.navy.mil/fmc/fmb/Documents/11pres/SCN_Book.pdf
- FY2010: https://www.globalsecurity.org/military/library/budget/fy2010/navy/fy2010-scn.pdf
- FY2007: https://www.secnav.navy.mil/fmc/fmb/Documents/07pres/proc/scn_book.pdf
- FY2005: https://www.secnav.navy.mil/fmc/fmb/Documents/05pres/PROC/SCN_BOOK.pdf
- Index of all DON budget materials: https://www.secnav.navy.mil/fmc/fmb/Pages/Fiscal-Year-2027.aspx

**FY2027 topline for context:** SCN request $65,825,017,000 total ($60,176,117K discretionary plus $5,648,900K mandatory), against FY2026 of $27,151,616K discretionary plus $17,930,426K reconciliation, $45,082,042K total. Carrier Replacement Program FY2027: $2,619,473,000, split $678,907,000 for FY2027 and $1,940,566,000 advance procurement for FY2029. [FY2027 SCN Book](https://www.secnav.navy.mil/fmc/fmb/Documents/27pres/SCN_Book.pdf); [Naval News](https://www.navalnews.com/naval-news/2026/04/landmark-u-s-budget-request-includes-65-8-billion-for-navy-shipbuilding/); [Janes](https://www.janes.com/defence-intelligence-insights/defence-news/sea/pentagon-budget-2027-us-navy-spending-request-seeks-to-bolster-shipbuilding)

## C.3 CRS — the assembled funding history, already reconciled

CRS RS20643, *Navy Ford (CVN-78) Class Aircraft Carrier Program*, Ronald O'Rourke. This report contains two tables that would otherwise take weeks to rebuild from J-books:
- **Table 1:** Procurement funding for CVNs 78-82 by fiscal year
- **Table 2:** Changes in estimated procurement costs, showing the estimate in **each successive budget submission**. This is a ready-made public variance record.
- **Table 3:** Congressional action on the funding request (request, HASC, SASC, authorization enacted, HAC, SAC, appropriation enacted)

- Current version: https://www.congress.gov/crs-product/RS20643
- HTML full text: https://www.congress.gov/crs_external_products/RS/HTML/RS20643.html
- Versioned PDFs (useful for as-of-date reconstruction): https://www.congress.gov/crs_external_products/RS/PDF/RS20643/RS20643.301.pdf and the .297, .300, .292, .286, .249, .243 variants
- Full version history with diffs between editions: https://www.everycrsreport.com/reports/RS20643.html

Illustrative Table 2 fragment from the FY2022 edition, showing how the CVN-79 estimate moved by submission year: FY08 $9,192.0M, FY08 $9,191.6M, FY11 $10,413.1M, FY12 $10,253.0M, FY13 $11,411.0M, FY17 $11,398.0M, FY22 $11,929.7M, FY26 $13,196.0M. [RS20643.249](https://congress.gov/crs_external_products/RS/PDF/RS20643/RS20643.249.pdf), [RS20643.301](https://www.congress.gov/crs_external_products/RS/PDF/RS20643/RS20643.301.pdf)

Related CRS: [R48860, FY2026 Defense Budget: Funding for Selected Weapon Systems](https://www.congress.gov/crs-product/R48860); [IN12641, FY2026 NDAA Summary of Funding Authorizations](https://www.everycrsreport.com/reports/IN12641.html)

## C.4 Statutory cost cap history (10 U.S.C. 8692 lineage)

This is the legal ceiling, and it is a different number from both the budget estimate and the Cost Limitation Baseline. All from [CRS RS20643 footnotes](https://www.congress.gov/crs_external_products/RS/HTML/RS20643.html):

| Authority | Action |
|---|---|
| FY2007 NDAA (P.L. 109-364) Sec. 121 | Established CVN-78 cap at $10.5B, follow-ons at $8.1B, plus inflation adjustment. Granted six-year incremental funding authority for CVN-78/79/80 |
| FY2014 NDAA | Raised CVN-79 and follow-on cap to **$11,498M** to account for inflation and non-recurring engineering for lead-ship lessons learned |
| FY2016 NDAA (P.L. 114-92, 25 Nov 2015) | **Lowered** follow-on cap to **$11,398.0M**. Added a provision: if during CVN-79 construction the CNO determines that staying within the cap would cause an unacceptable reduction in operational capability, SECNAV may raise the CVN-79 cap by up to $100M, to **$11,498M**. Also amended the inflation-adjustment basis and **excluded certain costs from counting against the caps** |
| FY2018 NDAA (P.L. 115-91) | CVN-80 and subsequent raised to $12,568.0M. CVN-79 held at $11,398.0M |
| FY2020 NDAA (P.L. 116-92, 20 Dec 2019) | Set caps: CVN-78 $13,224.0M, **CVN-79 $11,398.0M**, CVN-80 $12,202.0M, CVN-81 $12,451.0M |
| FY2021 NDAA (P.L. 116-283) Sec. 1054 | Added 10 U.S.C. 8062(g), no retirement before first refueling |

Also: [Defense News, Congress lowers cost caps on future carriers](https://www.defensenews.com/naval/2019/12/10/congress-lowers-cost-caps-on-future-carriers/)

**Three distinct ceilings exist and they are not interchangeable:** the statutory cost cap ($11.398B / $11.498B), the SECNAV Cost Limitation Baseline ($12.936B as of Aug 2023), and the budget-submission total procurement cost ($13.196B as of FY2026 PB). Any product that shows one number as "the cost cap" will be wrong. The spread between them is the single most important public-facing insight in this dossier.

## C.5 GAO

- **GAO-26-108457**, Weapon Systems Annual Assessment, 2 July 2026, 24th annual, 104 programs. Contains a CVN 78 Gerald R. Ford Class program assessment page. https://www.gao.gov/products/gao-26-108457 and https://www.gao.gov/assets/gao-26-108457.pdf
- GAO-25-107569, 2025 edition (23rd): https://www.gao.gov/products/gao-25-107569
- GAO-17-575, Ford-Class Aircraft Carrier: Follow-On Ships Need More Frequent and Accurate Cost Estimates: https://www.gao.gov/products/gao-17-575 / https://www.gao.gov/assets/gao-17-575.pdf
- GAO-15-22, Congress Should Consider Revising Cost Cap Legislation: https://www.gao.gov/assets/gao-15-22.pdf
- GAO-13-396, Lead Ship Testing and Reliability Shortfalls: https://www.gao.gov/assets/gao-13-396.pdf
- GAO-16-84T, Poor Outcomes Are the Predictable Consequence: https://www.gao.gov/assets/gao-16-84t.pdf
- GAO-18-238SP, Navy Shipbuilding (delivery with uncorrected deficiencies): https://www.gao.gov/assets/gao-18-238sp.pdf
- **GAO-17-418, Policy Changes Needed to Improve the Post-Delivery Process** — this is the OWLD reference, essential for cost scope: https://www.gao.gov/assets/gao-17-418.pdf
- GAO on SUPSHIP authority: https://www.gao.gov/assets/730/720005.pdf
- **GAO-22-105007, Defense Contracting: More Insight into Use of Financing Payments** — documents that shipbuilding progress payment data comes from DFAS MOCAS and from SUPSHIP, and that SUPSHIP rather than DCMA administers Navy shipbuilding contracts: https://www.gao.gov/assets/gao-22-105007.pdf
- GAO-18-289, Navy internal control over real property and CIP: https://www.gao.gov/assets/gao-18-289.pdf
- GAO Cost Estimating and Assessment Guide, GAO-09-3SP, the standard CVN-79 was judged against: https://www.gao.gov/products/gao-09-3sp

## C.6 DOD OIG

- **DODIG-2026-032**, FY2025 DoD agency-wide financial statement audit report, 19 Dec 2025. Consolidates the department's **26 material weaknesses** and states DoD will correct the general-ledger-systems weakness by FY2028. https://media.defense.gov/2025/Dec/19/2003847587/-1/-1/1/DODIG-2026-032.PDF
- **DODIG 09-065, Navy Presentation of Shipbuilding Construction Contract Financing on the Financial Statements** — directly on shipbuilding CIP compilation and valuation methodology. Dated but structurally the closest OIG work to this project: https://media.defense.gov/2009/Mar/26/2001711998/-1/-1/1/09-065.pdf
- DODIG 09-008, Internal Controls Over the DON Military Equipment Baseline Valuation Effort: https://media.defense.gov/2008/Oct/31/2001712175/-1/-1/1/09-008.pdf
- DoD OIG report search: https://www.dodig.mil/reports.html

## C.7 Accounting and asset-valuation sources

- **DON FY2025 Agency Financial Report**, 8 Dec 2025. GPP&E net book value **$503.1 billion**. Vessels and Aircraft make up over half of PP&E Construction in Progress. GPP&E remains a material weakness. Describes RP CIP migration into Navy ERP, CIP project establishment, monthly CIP settlement, and relieving CIP into assets placed in service. https://www.secnav.navy.mil/fmc/FR/FY25_NavyAFR_12.8.25_FINAL.pdf
- DON FY2023 AFR (carries the material weakness and assertion target table): https://www.secnav.navy.mil/fmc/FR/FY_2023_DON_Agency%20Financial_Report_FINAL_11.15.2023.pdf
- DoD FY2024 AFR financial section: https://comptroller.war.gov/Portals/45/Documents/afr/fy2024/4-Financial_Section.pdf
- SFFAS 6, Accounting for Property, Plant, and Equipment (FASAB Handbook): https://www.fasab.gov/accounting-standards/
- OSD Military Equipment Valuation Contractor Acquired Property business rule. States that title passes to DoD when the contractor obtains the property, but the property is not recorded on DoD financial statements **other than as construction in process** until delivered. This is the governing rule for how a partially built carrier sits on the balance sheet. https://www.acq.osd.mil/asda/dpc/ce/gfp/docs/MEV-Contractor-Acquired-Property-Business-Rule.pdf
- SECNAVINST 5200.45A, General Equipment and CIP accountability definitions: https://www.secnav.navy.mil/doni/Directives/05000%20General%20Management%20Security%20and%20Safety%20Services/05-200%20Management%20Program%20and%20Techniques%20Services/5200.45A%20CH-1.pdf

## C.8 Congressional hearings and reports

- SASC Seapower Subcommittee, 8 Apr 2025, nuclear shipbuilding. RADM Casey Moton (PEO Carriers) testimony that CVN-79 is 95% complete. https://www.armed-services.senate.gov/hearings and coverage at [USNI](https://news.usni.org/2025/04/09/first-columbia-class-sub-two-aircraft-carriers-face-delivery-delays-navy-officials-tell-senate) and [Inside Defense](https://insidedefense.com/daily-news/cvn-79-delivery-pushed-back-navy-official-tells-lawmakers)
- FY2026 NDAA (S. 1071) and the Joint Explanatory Statement. CRS summary: https://www.everycrsreport.com/reports/IN12641.html
- HASC FY2026 NDAA report on H.R. 3838: https://armedservices.house.gov/uploadedfiles/h.r._3838_fy26_ndaa_as_reported_to_the_house.pdf
- Congressional hearing full-text archive: https://www.congress.gov/congressional-hearings
- Navy FY2027 budget rollout briefing transcript, including "across the FYDP, we have $39 billion in shipbuilding for our carriers": https://www.navy.mil/Press-Office/Speeches/display-speech/Article/4466519/navy-fy27-budget-request/

## C.9 Reprogramming, apportionment, and execution

These are the sources that show money moving after appropriation, which no J-book captures.
- DoD prior-approval and internal reprogramming actions (DD 1415-1): https://comptroller.defense.gov/Budget-Execution/Reprogramming/
- OMB apportionment files for TAFS 017-1611, including footnoted apportionment limits: https://apportionment-public.max.gov/ and mirrored at https://openomb.org/file/11319811 (017-1611 2024/2028) and https://openomb.org/file/11490885 (017-1611 2015/2026)
- Treasury Account Symbol / BETC master list: https://catalog.data.gov/dataset/treasury-account-symbols

## C.10 CBO

CBO independently re-estimates carrier costs and explicitly states what the Navy's shipbuilding plan excludes. Useful for the cost-scope boundary question.
- An Analysis of the Navy's 2025 Shipbuilding Plan: https://www.cbo.gov/publication/61155. Key statement: new-ship construction "excludes the costs of refueling nuclear-powered aircraft carriers, purchasing ships that are not part of the battle force, constructing large unmanned surface vessels, **conducting outfitting and postdelivery activities**... and other smaller items."
- CBO October 2023 shipbuilding analysis: https://www.cbo.gov/system/files/2023-10/59508-shipbuilding.pdf
- CBO notes it marks the beginning of production with the appropriation of advance procurement funding, typically two years before authorization, used for long-lead items such as the nuclear propulsion plant. That is the defensible public answer to "when does the program start."

## C.11 FOIA

- OSD/JS FOIA requester service center and reading room (where SARs are posted): https://www.esd.whs.mil/FOID/
- DON FOIA: https://www.secnav.navy.mil/foia/
- NAVSEA FOIA: https://www.navsea.navy.mil/Resources/FOIA/
- **Named FOIA targets for this program**, based on what is redacted or absent in public documents:
  1. The CAPE independent cost estimate and the NCCA labor-hour estimates for CVN-79, redacted in GAO-17-575 at NAVSEA contracting's request
  2. The SECNAV August 2023 notification to Congress raising the Cost Limitation Baseline to $12.936B, and its supporting cost basis
  3. The CVN-79 CSDR / FlexFile submissions held in CADE
  4. Any rework cost attributable to the 2024 weld deviations
  5. The CVN-79 OWLD as currently established with Treasury

---

# PART D. String 3: tracing identifiers into Advana FM, the GL systems, and feeder systems

This is the part that actually isolates CVN-79 from the data ocean. Each identifier below is sourced, and each is tagged with where it will appear.

## D.1 The appropriation, line item, and program element map

The FY2027 MSAR publishes the program's complete funding-source table. This is the authoritative public key set for a GL query. Verbatim structure from [CVN_78_MSAR_FY2027_PBv2.pdf](https://www.esd.whs.mil/Portals/54/Documents/FOID/Reading%20Room/Selected_Acquisition_Reports/PB_2027_MSARs/CVN_78_MSAR_FY2027_PBv2.pdf):

| Appn | BA | Line Item | Program Element | Note |
|---|---|---|---|---|
| 1611N | 02 | **2001 - Carrier Replacement Program** | **0204112N** Multi-Purpose Aircraft Carriers - Nimitz (CVN) | Shared. **This is CVN-79's primary line.** |
| 1611N | 02 | 2004 - CVN-81 | 0204112N | |
| 1611N | 02 | 2086 - CVN Refueling Overhauls | 0204112N | Shared |
| 1611N | 05 | **5110 - Outfitting** | 0204112N | Shared. **Carries CVN-79 outfitting.** |
| 1611N | 05 | **5300 - Completion of PY Shipbuilding Programs** | 0204112N | Shared. **Carries CVN-79 prior-year completion.** |
| 1810N | 04 | 5664 - Surface Training Equipment | 0204112N | Shared |
| 1804N | 01 | 1B5B - Ship Depot Operations Support | 0204112N | Sunk |

Cross-confirmed from [CEC MSAR FY2027](https://www.esd.whs.mil/Portals/54/Documents/FOID/Reading%20Room/Selected_Acquisition_Reports/PB_2027_MSARs/CEC_MSAR_FY2027_PBv2.pdf) and [MIDS SAR](https://apps.dtic.mil/sti/pdfs/AD1019499.pdf), which show the same 1611N / 02 / 2001 / 0204112N structure.

**The shared RDT&E program element is separate and must not be confused with the procurement one.** Procurement is **PE 0204112N**. The class research and development that produced EMALS, AAG, and Dual Band Radar sits in RDT&E under **PE 0604112N, "CVN 78-80"**, which is shared across hulls by construction and is the subject of the allocation-method question in **G4**. Source for the RDT&E element: `ring0/ring0_research_notes.md`, 2026-11-06 gate-check pass.

**Immediate consequence for the product: CVN-79 cost does not live on one line.** At minimum it spans SCN lines 2001, 5110, and 5300, plus OPN, plus shared RDT&E under a different appropriation and a different program element. A query filtered to line 2001 alone will understate the hull. A query that adds 0604112N without an allocation rule will overstate it. That is a defensible, publicly sourced finding you can brief before you have any data access.

**Key values:**
- Appropriation symbol: **1611N** (Treasury main account **1611**, agency **017**)
- TAFS form: **017-1611 YYYY/YYYY** (for example 017-1611 2015/2026, 017-1611 2024/2028). Verified at [openomb](https://openomb.org/file/11490885)
- Appropriation symbol with no-year indicator form: **17*1611**, where the asterisk in the third position indicates multiple-year availability. [DoD agency-wide financial statements appendix](https://comptroller.defense.gov/Portals/45/documents/cfs/fy2000/10_Section_7_FY2000.pdf)
- Budget Line Item: **2001**, also written **200100** in older exhibits. [FY2005 SCN Book](https://www.secnav.navy.mil/fmc/fmb/Documents/05pres/PROC/SCN_BOOK.pdf)
- Program Element: **0204112N**
- PARM code seen on some CVN-79 P-5 equipment rows: **PMW 120**
- Weapon System field value on the P-10: **CVN 79**

**Caution on P-1 line numbers.** The *line number* in the P-1 exhibit is renumbered between budget years while the *BLI* stays 2001. The Carrier Replacement Program appears as P-1 Line #1 in FY2010-FY2012, Line #2 in FY2020, and Line #3 in FY2025. Any multi-year query keyed on the printed P-1 line number will silently break. Key on BLI 2001 and PE 0204112N instead. Evidence: [FY2012](https://www.globalsecurity.org/military//library/budget/fy2012/navy/scn-book.pdf), [FY2020](https://www.globalsecurity.org/military/library/budget/fy2020/navy/SCN_Book.pdf), [FY2025](https://www.secnav.navy.mil/fmc/fmb/Documents/25pres/SCN_Book.pdf).

## D.2 The SCN subhead, and why it is the highest-value single element

The DON Financial Management Policy Manual states that SCN is **line item appropriated**, unlike every other DON appropriation, and that the SCN four-digit subhead encodes the budget activity and P-1 line:

> "The Shipbuilding and Conversion, Navy (SCN) appropriation is divided into five budget activities... further divided into procurement line items (P-1 line item) for which funds have been budgeted... activity and P-1 line each represents one of the four positions of the subhead for this appropriation."

Sources: [DON FMPM](https://www.secnav.navy.mil/fmc/Documents/FINAL-FMPM.pdf), mirrored copy that renders in search: https://www.navymwr.org/modules/media/?do=download&id=db495ee9-737a-4399-8751-d21cda75ebf3 and https://www.secnav.navy.mil/fmc/Documents/Financial-Management-Policy.pdf

**Why this is the key:** because SCN is line-item appropriated and the subhead carries BA plus P-1 line, the subhead in the ledger is a direct, structural pointer to the Carrier Replacement Program. In Navy ERP the subhead is mapped to the NWA or WBS. Confirmed in the DTS/LOA data dictionary: "ACCT 3 - Subhead with the NAVY ERP subhead table for the NWA or WBS." [DTA Appendix R](https://media.defense.gov/2021/Nov/15/2002893225/-1/-1/0/DTA_APP_R.PDF), [LOA formats by service](https://acqnotes.com/wp-content/uploads/2014/09/Lines-of-Accounting-LOAS-Formats-by-Service-Agency-and-LOA-Data-Elements-For-Customer-Identification-Codes-CICS.pdf)

**Collection requirement CR-1:** obtain the Navy ERP subhead table and the NWA/WBS mapping for BLI 2001, and the specific NWA or WBS node that carries CVN-79 as distinct from CVN-80/81. This is the single question that most advances the project. Executor: NAVSEA 01 comptroller or DFAS.

## D.3 Contracts, orders, and CAGE

| Identifier | What it is | Source |
|---|---|---|
| **N00024-15-C-2114** | CVN 79 Detail Design & Construction (DD&C). FPIF target, $3,352,611,760 at award 5 Jun 2015. FAR 15 negotiated, sole source under FAR 6.302-1. Ceiling reported up to $4,526,748,310 | [FY2027 MSAR](https://www.esd.whs.mil/Portals/54/Documents/FOID/Reading%20Room/Selected_Acquisition_Reports/PB_2027_MSARs/CVN_78_MSAR_FY2027_PBv2.pdf); [HigherGov](https://www.highergov.com/contract/N0002415C2114/) |
| **N00024-09-C-2116** | CVN 79 Construction Preparation (CP). Awarded Jan 2009. 96.84% work complete as of the Dec 2022 SAR | [FY2022 SAR](https://www.esd.whs.mil/Portals/54/Documents/FOID/Reading%20Room/Selected_Acquisition_Reports/FY_2022_SARS/CVN%2078%20_SAR_DEC_2022_final.pdf) |
| N00024-04-C-2118 | CVN 21 design, long lead material, non-nuclear advance construction. Predecessor effort | [GlobalSecurity DoD contracts](https://www.globalsecurity.org/military/library/news/2006/11/dod-contracts_3391.htm) |
| **CAGE 43689** | Huntington Ingalls Industries (HII) Newport News Shipbuilding (NNS), the contractor of record on both contracts | [FY2023 MSAR](https://www.esd.whs.mil/Portals/54/Documents/FOID/Reading%20Room/Selected_Acquisition_Reports/FY_2023_SARS/CVN%2078%20MSAR%20Dec%202023.pdf) |
| Contracting offices | **NAVSEA** (Washington Navy Yard) on the base awards. **SUPSHIP Newport News** on later mods | [FY2023 MSAR](https://www.esd.whs.mil/Portals/54/Documents/FOID/Reading%20Room/Selected_Acquisition_Reports/FY_2023_SARS/CVN%2078%20MSAR%20Dec%202023.pdf); [Mar 2024 contract announcement](https://dailydefensenews.wordpress.com/2024/03/11/contracts-for-march-11-2024/) |

Separate contracts that carry CVN-79 cost but not the CVN-79 contract number:
- **EMALS CVN 79 shipset:** General Atomics, awarded 2015 [FY2022 SAR](https://www.esd.whs.mil/Portals/54/Documents/FOID/Reading%20Room/Selected_Acquisition_Reports/FY_2022_SARS/CVN%2078%20_SAR_DEC_2022_final.pdf)
- **AAG:** separate MDAP with its own MSAR; one AAG engine set was transferred from CVN 78 to CVN 79 by PEO Carriers memo dated 19 May 2016, meaning an asset moved between hulls without a contract action [AAG MSAR](https://www.esd.whs.mil/Portals/54/Documents/FOID/Reading%20Room/Selected_Acquisition_Reports/FY_2023_SARS/AAG%20MSAR%20Dec%202023.pdf)
- Lockheed Martin and Raytheon C/FFP equipment lines appear on the FY2025 P-5 for FY2013 CVN 79, in the $2.9M to $39.3M range per line

**Mod-level examples showing cross-fiscal-year funding on one action**, which is the core reconciliation problem in miniature:
- 11 Mar 2024, $37,544,972 FPIF mod to N00024-15-C-2114 for CANES outfitting. Funded **FY2024 SCN $24,395,466 (65%) and FY2018 SCN $13,149,506 (35%)**. Will not expire at end of current fiscal year. [contract announcement](https://dailydefensenews.wordpress.com/2024/03/11/contracts-for-march-11-2024/)
- Jul 2023, $274,041,192 FPIF plus $119,213,388 CPFF/CPIF across both contracts, with FY2021 SCN, FMS Norway and FMS Spain funds cited on the same action. [Aerotech News reprint of the DoD announcement](https://www.aerotechnews.com/blog/2023/07/12/contract-briefs-376/)
- 21 Nov 2025, four-part mod including FMS (Canada) $1,979,967, FY2025 OPN $1,650,000, FY2025 RDT&E (USMC) $250,000. [GlobalSecurity](https://www.globalsecurity.org/military/library/news/2025/11/dod-contracts_4340534.htm)

**Finding:** CVN-79 contract actions carry Foreign Military Sales funds and other-service RDT&E funds. Any hull cost roll-up that assumes SCN-only funding on the DD&C contract will be wrong, and the FMS portions are arguably not US program cost at all. This is a cost-scope boundary question with a concrete public example.

## D.4 Procurement data systems where those contract numbers resolve

- **USAspending.gov.** Award search by PIID. https://www.usaspending.gov/search/ Use PIID `N0002415C2114` and `N0002409C2116`. Agency: Department of the Navy, awarding sub-agency NAVSEA.
- **FPDS-NG.** https://www.fpds.gov/ Field names to query: PIID, Referenced IDV PIID, Modification Number, Contracting Office ID, PSC, NAICS **336611** (Ship Building and Repairing), Principal Place of Performance.
- **SAM.gov** contract data (successor to FPDS front end): https://sam.gov/
- **EDA (Electronic Document Access)** within PIEE, holds the contract PDFs and the Procurement Data Standard XML: https://piee.eb.mil/
- Commercial mirrors useful for fast mod-history reconstruction, then verify in FPDS: [HigherGov N0002415C2114](https://www.highergov.com/contract/N0002415C2114/)

## D.5 Payment and entitlement path

This is where contract dollars become GL transactions, and it is the handoff most likely to be the source of unmatched transactions.

- **SUPSHIP Newport News administers the contract**, not DCMA. GAO documents this explicitly: shipbuilding is the "notable exception" to DCMA administration. [GAO-22-105007](https://www.gao.gov/assets/gao-22-105007.pdf)
  SUPSHIPNN: 4101 Washington Avenue Bldg 2, Newport News VA 23607-2787. Roughly 535 civilians and 52 military. https://www.navsea.navy.mil/Home/SUPSHIP/Newport-News/
- **MOCAS** (DFAS Columbus) is the entitlement system for complex, multi-year, incrementally funded contracts with progress payments. MOCAS carries progress payments, performance-based payments, interim cost payments, and contract withholds. It has been SFIS/SLOA standardized and reports NTDO daily to Treasury. [MOCAS Overview and Update](https://www.acq.osd.mil/asda/dpc/ce/p2p/docs/training-presentations/2024/p2p%202024%20-%20mocas%20update.pdf), [DFAS Contract Pay guide](https://www.dfas.mil/Portals/98/Documents/Contractors-Vendors/ContractPayInformation-011110.pdf)
- **MOCAS / Navy ERP integration** was targeted end of month July 2025, front-end entitlement in MOCAS with disbursement from Navy ERP direct to Treasury. If that landed, the disbursement path for CVN-79 **changed mid-program**, which means the transaction shape changes at a dated seam inside the Navy ERP era. [From MOCAS to ERP briefing](https://cdn.fs.pathlms.com/CsKdcDsPQf62Via1tmMQ)
- **WAWF / PIEE document type: Navy Shipbuilding Invoice (NSI)**, applicable to ship design and construction. Each line item must carry at least one **ACRN-SDN-AAI** combination. There is also a "Cost Voucher - Shipbuilding" type. [WAWF NSI guide](https://pieetraining.eb.mil/wbt/wawf/documents/NSI.pdf), [P2P SOP](https://www.acq.osd.mil/dpap/policy/policyvault/USA000988-20-DPC.pdf)
- DCMA Manual 2101-02 on progress payments and the MOCAS Progress Payment Master: https://www.dcma.mil/Portals/31/Documents/Policy/DCMA_MAN_2101-02.pdf

**Collection requirement CR-2:** confirm whether CVN-79 progress payments ran through MOCAS for the whole life of the DD&C contract, or whether any portion moved to Navy ERP entitlement after the July 2025 integration. This determines whether the disbursement population is one source or two.

## D.6 General ledger systems and the dated seams

This confirms and extends what is already in BACKGROUND.md. Primary source is the **SUPSHIP Operations Manual (SOM) Chapter 4, Financial Management**, S0300-B2-MAN-010:
https://www.navsea.navy.mil/Portals/103/Documents/SUPSHIP/SOM/Ch4-FinancialManagement-18Aug19.pdf

Verbatim findings:
- "Navy ERP became NAVSEA's system of record for financial transactions using FY11 funds, with the exception of **ship construction or 'complex' contracts, which were delayed until 1 April 2011**."
- "FY10 and prior funding retain the Standard Accounting and Reporting System (STARS) as the financial system of record, while any transactions using FY11 funding and beyond are completed in Navy ERP."
- "For **NAVSEA General Fund, legacy data was not converted**, and STARS HCM remains the accounting system for all funds FY10 and prior."
- "The SUPSHIPs have access and use both the **STARS-HCM** and the **STARS-FL** modules to maintain legacy accounting and general ledger data."
- **STARS-FL Charleston**: official accounting system for SUPSHIP Mission Funding
- **STARS-FL Norfolk**: official accounting system for Fleet funded ship work actions

**A third dated seam inside the Navy ERP era.** Navy ERP's own ECC to HANA technical refresh cutover completed **19 August 2019**, per the Navy's "Navy Completes Its Largest Cloud Migration to Date" release. Navy ERP remained the Navy's financial system of record as of March 2026 per **GAO-26-107119**. So the Navy ERP era is itself two platform generations, not one. Source: `ring0/ring0_research_notes.md`, 2026-11-06 gate-check pass, which also corrected an earlier placeholder of 2019-01-01 in `schema/gl_system_crosswalk.sql`.

**Do not assume the modern system is clean.** DODIG-2012-051 found that Navy ERP as implemented did not post SFIS- and USSGL-compliant transactions at the time of that audit. That is a cited finding, not a hypothetical. Expect early Navy ERP mappings to grade below EXACT and build the product to surface that rather than assume otherwise. Carried as unverified in the `LOG.md` verification record pending primary-document confirmation.

**A fourth Navy general ledger exists and is in neither the original scope nor anything built.** GAO records the Navy operating **STARS-FL, STARS-HCM, Navy ERP, and NSMA (Navy Systems Management Activity)**. NSMA is open work under **G6**.

**Consequence for CVN-79 specifically.** CVN-79 received advance procurement funding from FY2007 onward and construction preparation funding from FY2009. Those are FY10-and-prior appropriations. Therefore:
1. CVN-79 cost is permanently split across **STARS-HCM (FY10 and prior)** and **Navy ERP (FY11 forward)**, at a seam dated **1 April 2011** rather than the 1 October 2010 general cutover.
2. NAVSEA general fund legacy data was never converted, so the pre-FY11 portion cannot be queried from Navy ERP at all.
3. The DD&C contract mods above show **FY2018 SCN funds obligated in FY2024**. SCN's extended availability means a single contract action can draw on appropriations years apart, each potentially sitting in a different ledger.

**On SABRS, see G2 rather than re-registering it here.** G2 already narrows this to one askable sentence and names the concrete object: the Navy ran a real **STARS-to-SABRS (S2S) migration project, FMP-4**, moving Navy Budget Submitting Offices off STARS-FL onto SABRS ahead of later Navy ERP consolidation. The residual question for NAVSEA 01 or DFAS is whether NAVSEA's or PEO Carriers' BSO was among the offices S2S moved. One public datum to add to that file: MCO 7322.1 states "The value of Military Equipment CIP is accumulated using disbursement data extracted from the SABRS general ledger," which is USMC equipment rather than Navy vessels, so it is not evidence for CVN-79 either way. https://www.marines.mil/Portals/1/Publications/MCO%207322.1.pdf

## D.7 Standard data elements that make the cross-system join possible

- **SFIS (Standard Financial Information Structure)**: roughly 70 data elements, DoD FMR Volume 1 Chapter 4. https://comptroller.war.gov/portals/45/documents/fmr/current/01/01_04.pdf
- **SLOA (Standard Line of Accounting)**: the 26-element subset of SFIS that must be exchanged for any business event with accounting impact, from commitment through disbursement. Mandated by OUSD(C) CFO memo 14 Sep 2012. Elements relevant here include Availability Type (X = no-year), Main Account (4), Sub Account (3), **Sub-Allocation / Budget Line**, Business Event Type Code (BETC), Security Cooperation customer code. https://www.dla.mil/Portals/104/Documents/DLMS/ADC/ADC_1043_Standard%20Line%20of%20Accounting.pdf and https://comptroller.war.gov/Portals/45/Documents/ODCFO/SFIS/SLOA_FDD_v1_2.4_12222022.pdf
- **SLOA matching criteria used in practice**: "Match by ALC, reconciliation number, TAS, BETC, and amount." [MOCAS Session 2](https://www.acq.osd.mil/asda/dpc/ce/p2p/docs/training-presentations/2022/MOCAS-Session-2.pdf)
- **LOA elements to carry in the schema**: Appropriation (APPN, AN4), **Subhead (SUBH, AN4)**, Object Class, Bureau Control Number, **ACRN (AN2)**, AAA / Agency Accounting Identifier, **SDN / Standard Document Number (13/30)**, Cost Code, Fund Code. The SDN itself decomposes into 6-digit Activity Address Code, 2-digit fiscal year, 2-digit Document Type Code, 5-digit serial. [Accounting Basics](https://www.logcom.marines.mil/Portals/184/Docs/Sites/prog_resources/files/prd/Accounting-Basics.pdf)
- USSGL: FMR Volume 1 Chapter 7 SFIS Transaction Library. https://comptroller.war.gov/fmr/

## D.8 Advana

- **DoD FMR Volume 1 Chapter 10** establishes Advana as the official DoD repository of common enterprise data and requires components to "provide authoritative source-level transactional data to Advana from all DoD business systems **daily**," obtained "from the business system in which the data originated (i.e., not a separate data warehouse or data lake but the system that originated the transaction)." Components define the business rules mapping source elements to the Advana common data model, which includes SFIS and the Procurement Data Standard.
  https://comptroller.war.gov/Portals/45/documents/fmr/current/01/01_10.pdf
- Advana scale as publicly stated: 450 to 500+ data sources, 90K datasets, 18 petabytes, 100K+ active users. Named sources include **GFEBS, STARS-FL, iRAPT, MOCAS, FPDS-NG, USAspending, EDA PDFs, EDA PDS XML**, Government Furnished Property, IUID Registry, and general ledger systems. [Advana Procurement Data briefing](https://www.acq.osd.mil/asda/dpc/ce/p2p/docs/training-presentations/2022/Advana's-Procurement-Data.pdf), [Advana 101 May 2024](https://www.acq.osd.mil/asda/dpc/ce/p2p/docs/training-presentations/2024/p2p_2024-procurement_analytics_data_in_advana_part_i_508_Oct25.pdf), [Advana Overview Sept 2024](https://govtribe.com/file/government-file/fa800324r0014-advana-overview-v1-dot-0-dot-pptx), [Advana 101 Jul 2021 (lists STARS-FL explicitly)](https://buildersummit.com/wp-content/uploads/2020/08/Advana-101-Briefing_JUL2021.pdf)
- **Jupiter** is the Department of the Navy community space on Advana. [Advana 101](https://www.acq.osd.mil/asda/dpc/ce/p2p/docs/training-presentations/2024/p2p_2024-procurement_analytics_data_in_advana_part_i_508_Oct25.pdf)
- Advana originated as the Universe of Transactions for financial statement audit. [Advana 101 Jul 2021](https://buildersummit.com/wp-content/uploads/2020/08/Advana-101-Briefing_JUL2021.pdf)

**Consequence:** MOCAS, FPDS-NG, USAspending, EDA, and STARS-FL are all publicly documented as Advana sources. That means the contract-to-obligation-to-disbursement chain for CVN-79 is assemblable inside Advana from already-ingested sources, without new system access, for the Navy ERP era. The pre-FY11 STARS-HCM portion is the open question, because STARS-HCM is not named on any public Advana source list while STARS-FL is.

**Collection requirement CR-3:** confirm whether STARS-HCM (as distinct from STARS-FL) is ingested into Advana, and for which fiscal years. If it is not, the FY2007-FY2010 CVN-79 advance procurement and construction preparation cost has no path into Advana and the answer must be sourced from NAVSEA records directly.

## D.9 Contractor-side cost reporting (CSDR / CADE)

This is the only public-system path to cost below the appropriation line, structured by work breakdown rather than by appropriation.
- DoD Manual 5000.04, Cost and Software Data Reporting: https://www.esd.whs.mil/Portals/54/Documents/DD/issuances/dodm/500004p.pdf
- CSDR Plan is **DD Form 2794**: https://cade.osd.mil/policy/dd2794
- **Cost and Hour Report (FlexFile)**, DID **DI-FNCL-82162**, JSON encoded, replaces DD 1921, 1921-1, 1921-2, 1921-5. Requires at-completion costs and hours reported in monthly increments. https://cade.osd.mil/policy/flexfile-quantity
- Quantity Data Report accompanies the FlexFile
- Submissions go to the OSD CAPE Defense Cost and Resource Center (DCARC) via the **CADE CSDR Submit-Review** system: https://cade.osd.mil/
- Legacy forms still relevant for the pre-2019 portion of CVN-79: DD 1921 Cost Data Summary Report, DD 1921-1 Functional Cost-Hour Report, DD 1921-2 Progress Curve Report, DD 1921-3 Contractor Business Data Report. OMB control 0704-0671: https://omb.report/omb/0704-0671
- FlexFile Implementation Guide: https://www.midnitedynamics.com/assets/docs/March2021FlexFileImplementationGuide.pdf

**CVN-79 is a pre-FlexFile program that crossed into the FlexFile era.** Its early cost reporting is in the 1921 series and its later reporting is FlexFile. These are not the same structure. That is a second dated seam, independent of the GL seam, and it sits in the program layer rather than the ledger layer.

> **Added 2026-11-08, and it lowers the expected value of this entire path.** The FY2027 MSAR (21 April 2026) prints **"DCARC CSDR Compliance Rating: Red"** against both the HII contract block and the launch-and-recovery contract block. **The program's contractor cost data reporting is formally assessed as deficient by the office that receives it.** Three consequences for collection: a FlexFile or 1921-series pull from CADE for this program should be expected to be late, incomplete or non-compliant; the request must ask for **the DCARC compliance assessment alongside the data**, because the assessment is what tells you which reports are missing; and my prior confidence that CADE could resolve the Propulsion Equipment attribution gap (**G22**) is materially reduced. CSDR remains the only public-system path below the appropriation line — it is just a weaker one than the policy documents imply. `VERIFIED` c=0.95. [FY2027 MSAR](https://www.esd.whs.mil/Portals/54/Documents/FOID/Reading%20Room/Selected_Acquisition_Reports/PB_2027_MSARs/CVN_78_MSAR_FY2027_PBv2.pdf)

## D.10 Work breakdown structures

- **SWBS / ESWBS**, the Navy's systems-oriented ship classification, three-digit groups, used across the full ship life cycle for cost, weight, specifications, and drawings. Reference: **NAVSEA 0900-LP-039-9010**. Groups: 000 General Guidance and Administration, 100 Hull Structure, 200 Propulsion Plant, 300 Electric Plant, 400 Command and Surveillance, 500 Auxiliary Systems, 600 Outfit and Furnishings, 700 Armament, 800 Integration/Engineering, 900 Ship Assembly and Support. [DTIC ADA451787](https://apps.dtic.mil/sti/tr/pdf/ADA451787.pdf), [DTIC ADA455524](https://apps.dtic.mil/sti/tr/pdf/ADA455524.pdf)
- **MIL-STD-881** carries the DoD WBS, with ESWBS as a separate document Navy programs should use: https://quicksearch.dla.mil/
- **SWLIN (Ship Work Line Item)** is a distinct structure from SWBS and appears in the SUPSHIP cost vocabulary. [SOM Ch 6](https://www.navsea.navy.mil/Portals/103/Documents/SUPSHIP/SOM/Ch6-CostEstimating-01Nov17.pdf)
- Current reform work worth reading before designing a WBS layer: **From Rivets to Requirements: Modernizing the Ship Work Breakdown Structure**, ICEAA 2026. Notes that SWBS Group 600 mixes trades with distinct cost drivers, which is a real obstacle to per-hull cost allocation. https://www.iceaaonline.com/wp-content/uploads/2026/04/TT02-paper-Caldwell-Dafoe-Modernizing-the-Ship-WBS.pdf

## D.11 SUPSHIP estimating vocabulary, for the method deliverable

**SUPSHIP Operations Manual Chapter 6, Cost Estimating:** https://www.navsea.navy.mil/Portals/103/Documents/SUPSHIP/SOM/Ch6-CostEstimating-01Nov17.pdf
- Estimate classes A through F. **Class C is the recommended classification for budget submittals to Congress, NAVCOMPT, and higher authority.** Class F is a feasibility "ball park" estimate from a one-digit SWBS weight group.
- **EAC (Estimate at Completion)**: estimated cost to complete all work on a new construction contract or project
- **PEC (Predicted End Cost)**: estimated cost of all work in a ship repair availability

The estimate class is a public, sanctioned confidence label. It is a better basis for your data-grading scheme than inventing one, because it is already the Navy's own vocabulary and will survive contact with NAVSEA.

## D.12 Cost scope: what the appropriation itself says is in and out

**SCN includes, per SOM Ch 4.4.1.3:** "hull, mechanical and electrical equipment, electronics, guns, torpedo and missile launching systems, and communications systems. It also includes plant equipment, **ship outfitting and post-delivery projects**, machines, and tools."
https://www.navsea.navy.mil/Portals/103/Documents/SUPSHIP/SOM/Ch4-FinancialManagement-18Aug19.pdf

**Availability.** SCN is a multiple-year appropriation available five fiscal years. Statutory language permits additional obligations after the five-year limit "for engineering services, tests, evaluations, trials and deferred work" performed in the final stages of ship construction. DON sets an end date with Treasury for each appropriated year, and **that end date is the last ship Obligation Work Limiting Date**. [DON FMPM](https://www.secnav.navy.mil/fmc/Documents/FINAL-FMPM.pdf); FY2025 appropriation language in the [FY2025 SCN Book](https://www.secnav.navy.mil/fmc/fmb/Documents/25pres/SCN_Book.pdf): "to remain available for obligation until September 30, 2029. Provided, that additional obligations may be incurred after September 30, 2029, for engineering services, tests, evaluations, and other such budgeted work that must be performed in the final stage of ship construction."

**OWLD, the cost-scope boundary that matters most.**
- GAO: OWLD is "the date when full financial responsibility for maintaining and operating" the ship transfers. "All new work identified after OWLD is the fleet's responsibility to correct using non-construction funding accounts, per Navy policy." GAO treats OWLD as the date the ship is provided to the fleet. [GAO-17-418](https://www.gao.gov/assets/gao-17-418.pdf)
- **OPNAVINST 4700.8M:** "The CFO date becomes the basis for establishing the OWLD, which is **11 months following the CFO** of the ship." PSA is normally complete one to two months prior to OWLD. Obligations for construction, conversion, outfitting, and post-delivery must occur prior to OWLD. https://www.secnav.navy.mil/doni/Directives/04000%20Logistical%20Support%20and%20Services/04-700%20General%20Maintenance%20and%20Construction%20Support/4700.8M.pdf
- **NAVSEA Desk Reference for SCN:** "The overall OWLD for SCN funding is **thirteen months after delivery** of the ship." Also: SEA 01P "has consistently ruled to permit work after the work-limiting date, but within the" scope planned in good faith before it. http://pdf4pro.com/cdn/scn-desk-reference-sunset-design-5526fa.pdf
- CVN 78 reached OWLD **July 2022**, five years after its May 2017 delivery. [FY2022 SAR](https://www.esd.whs.mil/Portals/54/Documents/FOID/Reading%20Room/Selected_Acquisition_Reports/FY_2022_SARS/CVN%2078%20_SAR_DEC_2022_final.pdf)
- Practitioner framing: "At OWLD, all funding for support of the ship... will revert from new-construction budgets to the various ship's operations, maintenance, and personnel budget accounts." [USNI Proceedings](https://www.usni.org/magazines/proceedings/2020/october/advice-new-construction-ships-crew)

**OWLD is the defensible answer to your cost-scope boundary question.** "Program cost" for a hull under the appropriation's own rules runs from first advance procurement obligation to OWLD. The PM office TDY example you raised resolves on whether the travel is charged to SCN before OWLD, in which case it is construction cost, or to O&M after, in which case it is operating cost. The FMR convention for allocating general and administrative cost on total direct cost is Volume 4 Chapter 23, already in BACKGROUND.md.

## D.13 Ship identity keys

- Hull: **CVN-79**. Pre-delivery designation **PCU John F. Kennedy**. Post-commissioning **USS John F. Kennedy**.
- Naval Vessel Register: https://www.nvr.navy.mil/ (search CVN 79)
- Navy official page: https://www.navy.mil/Resources/Fact-Files/Display-FactFiles/Article/2169795/aircraft-carriers-cvn/
- MyNavy HR new-ship page for CVN-79: https://www.mynavyhr.navy.mil/Career-Management/Detailing/Enlisted/Sea-Special/New-Ships/CVN-79
- NHHC infographic: https://www.history.navy.mil/content/dam/nhhc/news-and-events/multimedia%20gallery/Infographics/FINAL_JFK_CVN79_highres_PDF.pdf
- NavSource photo and build archive, useful for dating construction milestones: https://www.navsource.net/archives/02/79.htm
- Motto: "Serve with courage." Sponsor: Caroline Kennedy.
- No IMO or MMSI assigned (naval vessel).

**Watch for name collision in any text-based search.** CVN-79 shares a name with CV-67, the previous USS John F. Kennedy, which was dismantled starting 2025. Any keyword search on "John F. Kennedy" across historical records will return CV-67 records, including its own construction at the same shipyard. Keyed searches must use the hull number.

---

# PART E. Variance record: where public sources disagree

## E.0 Reconciliation against `ring0/ring0_research_notes.md`

Both files are Ring 0. They do not conflict after this pass. The division of labor:

| Content | Home |
|---|---|
| Source catalog by document family, with URLs | this file, Part C |
| Appropriation / line item / PE / subhead / contract / CAGE identifier set | this file, Parts D and G |
| Dated program spine | this file, Part A |
| Source disagreements | this file, Part E |
| 2026-11-06 gate-check narrative and what it resolved | research notes |
| Secondary-source seed figures and their confidence grades | research notes plus `cvn79_funding_history.csv` |
| Ring 0 source taxonomy | research notes, now expanded with per-document detail here |
| Gap register | `LOG.md`, G1 to G13 |

**What this pass changed in the two files' combined position:**
1. E-2 corrected. The $11.341B figure is a sourced FY2019 budget estimate, not an unsourced infobox number. My earlier draft wrongly called it unsupported.
2. C.1 qualified. The SAR family does not give a hull-allocated total program cost, per GAO-17-575. Earlier draft overstated what the MSAR provides.
3. PE 0604112N added as the shared RDT&E element, distinct from procurement PE 0204112N.
4. Third dated seam added: Navy ERP ECC to HANA, 19 August 2019.
5. NSMA added as the fourth Navy general ledger (G6).
6. DODIG-2012-051 added to the SFIS discussion.
7. SABRS no longer re-registered here; it points to G2, which already names S2S / FMP-4.
8. E-11 added, flagging a contract mislabel in the research notes.

## E.1 The disagreements themselves

Carry these forward rather than resolving them. Each is a real finding about the reporting, not a data error to clean.

| # | Disagreement | Sources |
|---|---|---|
| E-1 | **Three different "cost caps" in circulation.** Statutory cap $11,398.0M (with $100M SECNAV discretion to $11,498M), SECNAV Cost Limitation Baseline $12,936M (Aug 2023), budget-submission total procurement cost $13,196.0M (FY2026 PB). All three are current and all three are correct for their own purpose. | FY2020 NDAA; [FY2023 MSAR](https://www.esd.whs.mil/Portals/54/Documents/FOID/Reading%20Room/Selected_Acquisition_Reports/FY_2023_SARS/CVN%2078%20MSAR%20Dec%202023.pdf); [CRS RS20643](https://www.congress.gov/crs-product/RS20643) |
| E-2 | **RESOLVED, correcting an earlier reading in this file.** The $11.341B figure circulating on Wikipedia and derivative sites is not spurious. CRS RS20643, 18 May 2018 edition, states the FY2019 budget estimated CVN-79's procurement cost at **$11,341.4 million in then-year dollars**. It is a dated point-in-time budget estimate, not a total or a cap, and it is slightly *lower* than the FY2013 $11,411M estimate. Usable as a `PROCUREMENT_COST_ESTIMATE` at fiscal_year 2019, never as "the cost of the ship." Resolution credit: `ring0/ring0_research_notes.md`, 2026-11-06 gate-check pass. | [CRS RS20643 editions](https://www.everycrsreport.com/reports/RS20643.html) |
| E-3 | **RESOLVED 2026-11-08 in favor of OPNAVINST.** The PB2027 production-status block gives CVN-79 Completion of Fitting Out Jul 2027 and Obligation Work Limit Date **Jun 2028**, which is CFO plus eleven months exactly. The NAVSEA SCN Desk Reference reading of thirteen months after delivery would give Apr 2028. See N.8. | [OPNAVINST 4700.8M](https://www.secnav.navy.mil/doni/Directives/04000%20Logistical%20Support%20and%20Services/04-700%20General%20Maintenance%20and%20Construction%20Support/4700.8M.pdf) vs [NAVSEA SCN Desk Reference](http://pdf4pro.com/cdn/scn-desk-reference-sunset-design-5526fa.pdf) |
| E-4 | **Keel laying date.** 20 July 2015 in some records, 22 August 2015 in others (the keel-laying ceremony date). The earlier date appears in Wikipedia citing the Naval Vessel Register. | [Wikipedia](https://en.wikipedia.org/wiki/USS_John_F._Kennedy_(CVN-79)) vs [USNI keel-laying coverage](https://news.usni.org/) |
| E-5 | **Attributed delay cause shifts by year and by authority** for the same slip. FY2026 budget footnote says AAG certification and AWE work. DOT&E FY2025 adds supply chain impediments. GAO June 2025 adds material availability and workforce. HII adds untimely availability of Ford lessons. | [CRS RS20643](https://www.congress.gov/crs-product/RS20643), [DOT&E FY2025](https://www.dote.osd.mil/Portals/97/pub/reports/FY2025/navy/2025cvn78.pdf), [GAO via TWZ](https://www.twz.com/sea/future-uss-john-f-kennedy-second-ford-class-carrier-has-set-sail-for-the-first-time) |
| E-6 | **Ford-class life-cycle savings claim: $4B vs $5B** per ship over 50 years. | [CRS](https://www.congress.gov/crs_external_products/RS/PDF/RS20643/RS20643.243.pdf) vs [FY2027 FYDP materials via Naval News](https://www.navalnews.com/naval-news/2026/05/u-s-navy-reveals-future-plans-for-its-aircraft-carrier-fleet/) |
| E-7 | **Is the FY2026-FY2027 unit cost increase new cost?** GAO: unit costs up 3%, about $480M, roughly half from delivery schedule changes, "but the Navy is using funds it previously planned and budgeted for post-delivery activities, so **these are not new program costs**." The same dollars are a cost increase in one view and a reclassification in another. | [GAO-26-108457 quoted in CRS RS20643](https://www.congress.gov/crs-product/RS20643) |
| E-8 | **"Program start" has at least six defensible dates, each correct for a different audience:** FY2001 advance procurement for the shared CVN-21 program before the CVN-78/79/80 split, FY2004 Construction Preparation contract, FY2007 first CVN-79-specific AP increment (about $45M), Jan 2009 CP contract award, FY2013 procurement/authorization year (the CRS and GAO convention), Jun 2015 DD&C award, Aug 2015 keel laid. CBO's convention is the first advance procurement appropriation. Carry all of them as typed events and let the view choose, per the existing recommendation in the research notes. | [CBO](https://www.cbo.gov/system/files/2023-10/59508-shipbuilding.pdf); [CRS FY2007-era](https://apps.dtic.mil/sti/pdfs/ADA467394.pdf); [FY2027 MSAR](https://www.esd.whs.mil/Portals/54/Documents/FOID/Reading%20Room/Selected_Acquisition_Reports/PB_2027_MSARs/CVN_78_MSAR_FY2027_PBv2.pdf) |
| E-11 | **A mislabel to fix in `ring0/ring0_research_notes.md`.** Its program-born table lists "15 Jan 2009 — Construction (DD&C) contract award." January 2009 was the **Construction Preparation** contract (N00024-09-C-2116). The DD&C contract (N00024-15-C-2114) was awarded **5 June 2015**. Two different contracts six years apart, and the CP/DD&C split is load-bearing for contract-level cost tracing. | [FY2023 MSAR](https://www.esd.whs.mil/Portals/54/Documents/FOID/Reading%20Room/Selected_Acquisition_Reports/FY_2023_SARS/CVN%2078%20MSAR%20Dec%202023.pdf); [HII 5 Jun 2015](https://hii.com/news/hii-awarded-3-35-billion-contract-for-detail-design-and-construction-of-aircraft-carrier-john-f-kennedy-cvn-79/) |
| E-12 | **An inference of mine that the primary document refuted.** Part K.1 reasoned that the P-5 dagger marked GFE-bearing categories. The exhibit defines it as indicating the presence of a P-8a exhibit. Plausible, convenient, consistent with everything else, and wrong. Kept as a recorded error because the shape of it recurs: a real structural pattern with an invented interpretation laid over it. | [PB2027 SCN book, Exhibit P-5c](https://www.secnav.navy.mil/fmc/fmb/Documents/27pres/SCN_Book.pdf) |
| E-9 | **Supplier footprint count varies:** 2,000 firms in 46 states (CRS, 2019 basis) vs 43 states (secondary). Use the CRS figure and date it. | [CRS](https://www.congress.gov/crs_external_products/RS/PDF/RS20643/RS20643.297.pdf) |
| **E-13** | **A correction to this file, not a source disagreement, recorded because the method failure is reusable.** The Construction Preparation contract N00024-09-C-2116 was carried in the first version of Part N at roughly **$1.08B**, derived by summing **announced** DoD contract modifications. The obligation record gives **$4,519,300,323.83** — an understatement of $3.44B, a factor of **4.18**. DoD daily contract announcements have a dollar threshold and are silent below it; they omit incremental and installment funding actions, which are the dominant obligation mechanism on a cost-plus shipbuilding contract ($2.49B on this one); and they cannot net deobligations (68 actions, −$66.8M here). **Rule: a press release is an announcement, never a record.** Reader-caught, 2026-11-08. See N.7 Error 3. | [USAspending `Contracts_PrimeAwardSummaries` + 948-row transaction history, `ring0/reference/PrimeAwardSummariesAndTransactions_2026-11-08_*.zip`](https://www.usaspending.gov/award/CONT_AWD_N0002409C2116_9700_-NONE-_-NONE-/) |
| **E-14** | **USAspending disagrees with itself by exactly $5,880,250.00 on one contract.** For N00024-15-C-2114 the `ContractAwardSummary` in the single-award download reports total obligated **$4,584,483,595.77**, while the `Contracts_PrimeAwardSummaries` product and the sum of all 927 transaction-level `federal_action_obligation` values both give **$4,578,603,345.77**. Two of three agree, so this file carries $4,578,603,345.77 as canonical and the earlier figure is superseded. Both products are the same system on the same as-of date (2026-07-20). **Use the transaction sum, and reconcile it against the summary every time.** | `ring0/reference/CONT_N0002415C2114_2026-11-08_*.zip` vs `PrimeAwardSummariesAndTransactions_2026-11-08_*.zip` |
| **E-15** | **The 2116 identifier collision.** `N00024-09-C-2116` is CVN-79 Construction Preparation. `N00024-16-C-2116` is CVN-80 and CVN-81 Detail Design & Construction, carrying a **$14,917,738,145** FPIF-target modification awarded 31 Jan 2019. Same last four digits, seven years apart, different hulls, different appropriation years. Any fuzzy or partial match on "2116" merges CVN-79 money with CVN-80/81 money. Carried as a standing hazard, not a resolvable disagreement. See G28 and the Part G key set. | [FY2027 MSAR, 21 Apr 2026, contract tables](https://www.esd.whs.mil/Portals/54/Documents/FOID/Reading%20Room/Selected_Acquisition_Reports/PB_2027_MSARs/CVN_78_MSAR_FY2027_PBv2.pdf) |
| **E-16** | **RESOLVED 2026-11-08: as-of date, on N00024-09-C-2116 and not the DD&C contract.** The USAspending running total on the construction preparation contract N00024-09-C-2116 through action date 2026-06-10 is exactly **$4,518,716,360.83**. The eight actions dated 2026-06-17 to 2026-07-20 (A00645 to AZ0122) sum to exactly **$583,963.00**. `totalObligatedAmount` is cumulative per modification, and the entry read was the 10 June one. The DD&C contract N00024-15-C-2114 sums to $4,578,603,345.77, as E-14 records. Method rule: take `totalObligatedAmount` from the latest modification, and state the as-of date with every obligation figure. The FPDS side was not re-pulled. *Original entry, kept as recorded:* **FPDS-NG and USAspending disagree by $583,963.00 on the same contract.** For the Detail Design & Construction contract [sic: the figures are N00024-09-C-2116's], the FPDS-NG ATOM feed reports `totalObligatedAmount` **$4,518,716,360.83** while USAspending's canonical transaction sum gives **$4,519,300,323.83**. USAspending is sourced from FPDS, so the two should not differ. This is a third source disagreement on obligations for this hull, alongside E-14's $5,880,250.00 on the other prime contract. The difference is 0.013% and immaterial to any total, and that is exactly why it matters: it is small enough to survive every reasonableness check a reviewer would apply. Candidate causes, none yet tested: an as-of date difference, a pending-correction transaction visible in one system and not the other, or a deobligation posted to a modification that FPDS reports under a different base PIID. Until one is established, cite the system by name with every obligation figure and never present an obligation total as if it had one value. | FPDS-NG ATOM feed, retrieved 2026-11-08, vs `ring0/reference/PrimeAwardSummariesAndTransactions_2026-11-08_*.zip` |
| **E-17** | **A December 2025 Cost Limitation Baseline of $13,529M is printed but not yet confirmed.** The FY2027 MSAR says SECNAV notified Congress in December 2025 of an increase in the CVN-79 Cost Limitation Baseline from $12.936B to $13.529B. The pilot keeps $12,936M (August 2023) as the baseline in force until a human confirms the new figure under CAP-05, because the gate routed $13,529M to human review: it comes from an MSAR sentence, not the notification. Hull caution: $13.529B is also CVN 80's baseline since August 2023. If confirmed, the FY2027 budget total of $13,409.970M is $119.03M under the baseline rather than $473.97M over it. Registered 2026-11-19 from evaluation finding F1. | CVN_78_MSAR_FY2027_PBv2.pdf p.8; CVN 78 MSAR Dec 2023.pdf p.7; docs/requests/CAP05_BASELINE_FIGURE.md |
| E-10 | **Delivery vs commissioning conflated in reporting.** Several outlets treat March 2027 as both. Budget documents state March 2027 delivery with preliminary acceptance separately. Preliminary acceptance actually occurred 29 Sep 2026. | [FY2026 SCN footnote](https://www.congress.gov/crs-product/RS20643) vs [HII](https://www.hii.com/news/hiis-newport-news-shipbuilding-achieves-preliminary-acceptance-of-john-f-kennedy-cvn-79) |

---

# PART F. Collection requirements, mapped to the gap register

Public data cannot answer these. The register in `LOG.md` is the one home for gaps, so this pass **feeds** it rather than running a parallel list.

## F.1 Already registered, no new entry needed

| Question raised by this research | Existing gap |
|---|---|
| Was any CVN-79 office ever served by SABRS | **G2**, already narrowed to S2S / FMP-4 |
| CAPE ICE and NCCA labor-hour estimates for CVN-79, redacted in GAO-17-575 at NAVSEA contracting's request | **G4**, same three doors: NAVSEA 05C, NCCA, CAPE. Add FOIA as a fourth route. |
| Was GAO's per-hull SAR recommendation ever implemented | **G4** |
| Is STARS-HCM ingested into Advana, and for which years | **G5**, sharpened. This is the specific sub-question that decides whether FY2007-FY2010 CVN-79 cost is reachable in Advana at all. STARS-FL is named on public Advana source lists; STARS-HCM is not. |
| What NSMA carried and whether it touches shipbuilding | **G6** |
| CIP manual adjustment nature and magnitude for this hull | **G7** |

## F.2 Proposed new gaps, G8 to G13

| ID | Question | Type | Executor | Why it matters |
|---|---|---|---|---|
| **G8** | The Navy ERP subhead table and the NWA/WBS node that isolates CVN-79 from CVN-80/81 within BLI 2001 | `SME` then `DATA` | NAVSEA 01 Comptroller, or DFAS | **Highest value single item in this pass.** SCN is the one DON appropriation that is line-item appropriated, and the four-digit subhead encodes BA plus P-1 line, which maps to the Navy ERP NWA or WBS. Without this mapping, line 2001 cannot be split by hull in the ledger and the hull answer stays blocked at the budget layer. |
| **G9** | Did CVN-79 progress payments move from MOCAS entitlement to Navy ERP after the July 2025 integration, and on what date | `DOCUMENT` then `SME` | DFAS Columbus, SUPSHIP Newport News | A fourth dated seam, in the payment path rather than the ledger. Decides whether the disbursement population is one source or two. |
| ~~**G10**~~ | **CLOSED 2026-11-08. OWLD is Jun 2028**, with Completion of Fitting Out Jul 2027, per the PB2027 production-status block. Also resolves E-3 in favor of OPNAVINST 4700.8M. Residual work: confirm the date as actually set with Treasury rather than as budgeted. |  |  |  |
| **G11** | CVN-79 CSDR submissions: the DD 2794 plan, the 1921-series era, and the FlexFile era | `DATA` | OSD CAPE DCARC via CADE | The only path to cost below the appropriation line structured by work breakdown rather than by appropriation. Also a second seam, since CVN-79 crossed from 1921-series into FlexFile reporting mid-program. |
| **G12** | Which costs the FY2016 NDAA excluded from counting against the cost caps | `DOCUMENT` | DON FMB, OGC | Changes what the cap number measures, which changes the meaning of the E-1 three-ceiling spread the product will lead with. |
| **G13** | Rework cost from the 2024 weld deviations, by contract line and appropriation year | `DATA` then `SME` | NAVSEA, SUPSHIP Newport News | A named, dated public event with no public cost attached. A clean end-to-end test of the variance ledger and the event stream feeding cause evidence. |

## F.3 Proposed new gaps from the 2026-11-08 asset, property and industrial research, G14 to G19

| ID | Question | Type | Executor | Why it matters |
|---|---|---|---|---|
| **G14** | Does CIP relief for this hull trigger at preliminary acceptance (29 Sep 2026), at delivery (Mar 2027), or at commissioning? Name the authority and the determination document | `DOCUMENT` then `SME` | Navy FMO, NAVSEA | FMR Vol 4 Ch 25 ties relief to "placed in service" in one place and to "accepted" in another. The three candidate dates straddle a fiscal year boundary, so this decides which year a roughly $13 billion asset lands on the balance sheet. Part I.1. |
| **G15** | Is GFE installed on the hull (EMALS and AAG shipsets, the eleven AWEs, the EASR array) capitalized separately as its own general equipment, or rolled into the vessel's capitalized value? | `SME` then `DATA` | Navy FMO, PEO Carriers, NAVAIR PMA-251 | Each item is far above the $1 million Navy threshold and each is bought by a different command. If both the hull record and the system record capitalize it, the Navy double counts. If neither does, it drops. Part I.3. |
| **G16** | GFP Position Report for CAGE 43689 scoped to N00024-15-C-2114 and N00024-09-C-2116, cross-checked to the IUID Registry | `DATA` | PIEE GFP Module role holder; SUPSHIP Newport News | **Cheapest high-value request in this file.** Existing report, defined key, mandated 7-business-day reporting cadence, no new access path. GAO-25-106868 names SUPSHIP as not consistently verifying contractor CAP records, so this is the local test of a DoD-wide material weakness standing since FY2001. Part J. |
| ~~**G17**~~ | **RESOLVED NEGATIVELY 2026-11-08.** The exhibit defines it in place: "(†) indicates the presence of a P-8a." It is an exhibit cross-reference, not a GFE marker. The GFE/CFE split must be sought elsewhere. See N.1 and E-12. | | | |
| ~~**G18**~~ | **CLOSED 2026-11-08 for PB2027.** The full CVN-79 column is in Part N.1 and reconciles to zero residual. Residual work, now narrower: repeat the read for each prior budget year to build the category-by-year variance series. Still needs zero access. |  |  |  |
| **G19** | Magnitude of CVN-79 content expensed rather than capitalized because it fell below the $1 million Navy general equipment threshold | `DATA` | Navy FMO | Physically installed on the ship, never on the balance sheet. Sizes one of the three structural gaps between program cost and capitalized value. Part I.3. |
| **G20** | **Narrowed 2026-11-08.** EMALS ($611.307M) and AAG ($219.131M) are now verified from the PB2027 equipment exhibit. Still unpriced for this hull: the Advanced Weapons Elevators, and the residual $319.213M of the Ordnance category covering EASR, MOVLAS and other | `DATA` | PEO Carriers; NSWC Philadelphia; NAVAIR | What remains is a fifth of what the gap originally covered. See N.6. |
| **G22** | Vendor-level attribution of the Propulsion Equipment category, **$2,041.582M and 15.2% of the hull** | `DATA` then `SME` | Naval Reactors; NAVSEA; DOE | **The largest single unattributed block in the ship.** Part L establishes who builds the reactor plant. The money is not itemised in any public exhibit, and the funding crosses into the Department of Energy. Supersedes the propulsion half of the old G20. |
| **G23** | Outfitting and post-delivery attributable to this hull | `DOCUMENT` then `DATA` | Navy FMB; PEO Carriers | The PB2027 P-40 shows Outfitting and Post Delivery only as an informational row for all of line 2001: prior years 890.169, FY2025 64.813, FY2026 101.780, FY2027 125.843, total **1,766.730**. The CVN-79 share is not separable from the published row. |
| ~~**G21**~~ | **CLOSED 2026-11-08.** Base award of N00024-09-C-2116 is **$111,803,875.00, 15 January 2009**, solicitation N0002408R2116, cost-plus-fixed-fee, not competed (FAR 6.302-1, one offer). Lifetime obligations **$4,519,300,323.83**. It was never unpriced — it was below the DoD announcement threshold. See N.4 and E-13. | | | |

## F.4 Proposed new gaps from the 2026-11-08 contract-record pass, G24 to G28

| ID | Question | Type | Executor | Why it matters |
|---|---|---|---|---|
| **G24** | Why is N00024-09-C-2116 obligating money in FY2026 (**$133.4M**, including **$60,000,000 on 2025-12-03**) when its published period of performance ended **2025-07-31**? Are these in-scope closeout actions, a PoP extension not reflected in FPDS, or a data error? | `DOCUMENT` then `SME` | SUPSHIP Newport News; NAVSEA 02 | Decides whether CP-contract obligations are still live cost or administrative cleanup, and therefore whether the CP/DD&C handoff boundary used throughout Part N is stable. Also bears on the OWLD analysis in D.12. |
| **G25** | Award-level outlay (File C) linkage for both CVN-79 prime contracts. Reported outlays cover **0.80%** of $9,097.9M obligated; 2114 reports **$0.00** | `DATA` then `SME` | DFAS Columbus (MOCAS); Navy FMO; OUSD(C) DATA Act reporting | **The audit finding visible in public data.** Obligations in USAspending are usable for this hull; disbursements are not measurable at all. Until this is closed, no cost product should present outlay or expenditure figures sourced from USAspending, and the Advana FM query must take disbursement from MOCAS or Navy ERP directly. Part N.4. |
| **G26** | Full enumeration of contracts carrying CVN-79 scope, built **outward from the ship** rather than inward from the documents: FPDS-NG / USAspending query on PSC **1901**, DoD acquisition program code **223**, and funding office **N30270** (PEO Carriers), across all contracting activities | `DATA` | Anyone with FPDS-NG or USAspending access | **Structural gap, now proven.** The MSAR contract table names only seven PIIDs for a $13.4B ship because it lists only CSDR-surveilled MDAP efforts; the SCN P-5a/P-8a names vendors but prints no PIIDs. A NAVSEA-held equipment contract sits outside both catalogs simultaneously. This query is the systematic fix. Part N.6a. |
| **G27** | Identify **N00024-14-C-4201** and **N00024-18-C-4100** (both General Atomics, both NAVSEA): scope, platform, and whether any CVN-79 content exists that is not already counted via N00019-14-C-0037 | `DATA` | FPDS-NG PIID search, or USAspending award page | Supplied from outside this research. Cannot be the EMALS/AAG shipset money, which is NAVAIR N00019-14-C-0037 and already in the hull at $830.438M — **adding them on that assumption would double-count.** A five-minute lookup; blocked here only by network allowlist. Part N.6a. |
| **G28** | Register `N00024-09-C-2116` and `N00024-16-C-2116` as a **named collision pair** in every tracing artifact, query template and Advana view built from this dossier | `CATALOG` | This repo; then the Advana FM data product owner | **The most dangerous identifier hazard found.** CVN-79 Construction Preparation and CVN-80/81 DD&C share the last four digits seven years apart, and the CVN-80/81 vehicle carries a **$14.9B** modification. Any `LIKE '%2116%'`, trailing-digit join, or fuzzy contract match silently merges three hulls. Must be a hard exclusion in the query, not a reviewer's memory. Part N.6b. |

---

# PART G. Quick-reference key set

For schema and query construction.

```
Ship
  Hull                 CVN-79  (pre-delivery: PCU; post: USS)
  Name                 JOHN F. KENNEDY
  Class                CVN 78 GERALD R. FORD
  Program (MDAP)       CVN 78 Gerald R. Ford Class Nuclear Aircraft Carrier
  ACAT                 IC
  Program office       PEO Carriers (PEO Aircraft Carriers)

Budget
  Appropriation        1611N  (Treasury main account 1611, agency 017)
  Shared RDT&E PE      0604112N  "CVN 78-80"  (allocation method open, G4)
  TAFS                 017-1611 YYYY/YYYY   (e.g. 017-1611 2015/2026)
  Legacy symbol form   17*1611
  Budget Activity      02 Other Warships  (primary)
                       05 Auxiliaries, craft, prior-year program costs (outfitting, completion PY)
  P-1 Line Item / BLI  2001 Carrier Replacement Program  (also 200100)
                       5110 Outfitting
                       5300 Completion of PY Shipbuilding Programs
  Program Element      0204112N  Multi-Purpose Aircraft Carriers - Nimitz (CVN)
  Other appropriations 1810N BA 04 LI 5664 Surface Training Equipment
                       1804N BA 01 1B5B Ship Depot Operations Support
                       OPN, RDT&E (seen on contract mods)
  Subhead              4-digit; BA and P-1 line occupy positions. Maps to Navy ERP NWA/WBS.

Contract  -- CVN-79 (use these two, and only these two, as the HII prime keys)
  Construction Prep    N00024-09-C-2116    CPFF, base 15 Jan 2009 $111,803,875
                                           obligated $4,519,300,323.83 / 948 actions
                                           value $5,386,149,876.01, PoP end 2025-07-31
                                           solicitation N0002408R2116
  DD&C                 N00024-15-C-2114    FPIF target, 5 Jun 2015, $3,352,611,760
                                           obligated $4,578,603,345.77 / 927 actions
                                           value $4,615,795,653.36
  Two primes combined  $9,097,903,669.60 = 67.8% of hull, 91.7% of shipbuilder-side
  Launch & recovery    N00019-14-C-0037    NAVAIR, GA-EMS CAGE 4V360, 8 May 2014
                                           EMALS/AAG CVN 79+80, total value $1,629.0M
                                           CVN-79 share $830.438M (611.307 + 219.131)
  EASR (multi-hull)    N00024-16-C-5370    NAVSEA, Raytheon; CVN-79 share only ~$110M
                                           also LHA-8, CVN-74, LPD-29/30, FFG-62

!! COLLISION -- HARD EXCLUSION REQUIRED (G28, E-15)
  N00024-09-C-2116     CVN-79 Construction Preparation          <-- ours
  N00024-16-C-2116     CVN-80 + CVN-81 DD&C, $14,917,738,145    <-- NOT ours
  N00024-17-C-2117     appears in MSAR tables, scope unconfirmed <-- NOT ours
  Never match on trailing digits, never LIKE '%2116%'. Match full PIID only.

  UNRESOLVED, do not use (G27)
  N00024-14-C-4201     General Atomics, NAVSEA -- scope unknown
  N00024-18-C-4100     General Atomics, NAVSEA -- scope unknown

  Contractor CAGE      43689  HII Newport News Shipbuilding
  HII parent UEI       F9SDJAZFTLG6 / recipient UEI WMXDDH6HJNA5
  NAICS / PSC          336611 / 1901 Aircraft Carriers
  DoD claimant         A3 SHIPS;  acquisition program code 223 (labelled "CVN 78")
  Contracting offices  N62793 SUPSHIP Newport News; NAVSEA HQ
  Funding office       N30270 PROGRAM EXECUTIVE OFFICER CARRIERS
  Admin                SUPSHIP Newport News (not DCMA)
  Outlay warning       USAspending award-level outlays cover 0.80% of obligations.
                       Obligations usable; outlays NOT. Take disbursement from
                       MOCAS or Navy ERP, never from USAspending. (G25)
  Entitlement          MOCAS (DFAS Columbus); Navy ERP post-integration
  Invoice doc types    Navy Shipbuilding Invoice (NSI); Cost Voucher - Shipbuilding

Ledger
  FY10 and prior       STARS-HCM (NAVSEA general fund; legacy data NOT converted)
  FY11 forward         Navy ERP (ship construction / complex contracts from 1 Apr 2011)
  SUPSHIP legacy       STARS-FL Charleston (mission funding), STARS-FL Norfolk (fleet work)
  Fourth Navy GL       NSMA (Navy Systems Management Activity) — scope open, G6
  Seam 1 (ledger)      1 April 2011   STARS -> Navy ERP, complex contracts
  Seam 2 (platform)    19 August 2019 Navy ERP ECC -> HANA
  Seam 3 (program)     ~2019          DD 1921 series -> FlexFile
  Seam 4 (payment)     ~July 2025     MOCAS -> Navy ERP entitlement (open, G9)

Accounting classification
  SFIS                 ~70 elements (FMR Vol 1 Ch 4)
  SLOA                 26-element subset; required commitment through disbursement
  Join keys            TAS, BETC, ALC, reconciliation number, amount
  LOA elements         APPN, SUBH, Object Class, BCN, ACRN, AAA/AAI, SDN, Cost Code, Fund Code

Cost structure
  Ship WBS             SWBS / ESWBS (NAVSEA 0900-LP-039-9010); MIL-STD-881
  Ship work line       SWLIN
  Contractor reporting CSDR: DD 2794 plan; FlexFile DI-FNCL-82162; legacy DD 1921 series
  Repository           CADE / DCARC  (cade.osd.mil)
  Estimate classes     A-F; Class C for congressional budget submittals
  Measures             EAC (construction), PEC (repair availability)

Scope boundary
  Start                first AP obligation, FY2007 ($52.750M) — but see E-8
  End                  OWLD = Jun 2028  (CFO Jul 2027 + 11 months; OPNAVINST rule confirmed, E-3)
  Delivery             Mar 2027      Completion of Fitting Out  Jul 2027
  Total Ship Estimate  $13,409.970M (PB2027)   MDAP/MAIS code 223
  Asset transition     CIP accumulation then relief to GPP&E at placed-in-service (SFFAS 6)
```

---

# PART H. Master source index

**Primary government**
- CRS RS20643: https://www.congress.gov/crs-product/RS20643 | version history https://www.everycrsreport.com/reports/RS20643.html
- CVN 78 MSAR FY2027 PB: https://www.esd.whs.mil/Portals/54/Documents/FOID/Reading%20Room/Selected_Acquisition_Reports/PB_2027_MSARs/CVN_78_MSAR_FY2027_PBv2.pdf
- SAR/MSAR reading room: https://www.esd.whs.mil/Records-Declass/FOIA/Reading-Room/Reading-Room-List_2/Selected_Acquisition_Reports/
- FY2027 SCN J-Book: https://www.secnav.navy.mil/fmc/fmb/Documents/27pres/SCN_Book.pdf
- DON budget materials index: https://www.secnav.navy.mil/fmc/fmb/Pages/Fiscal-Year-2027.aspx
- GAO-26-108457: https://www.gao.gov/products/gao-26-108457
- GAO-17-575: https://www.gao.gov/products/gao-17-575
- GAO-17-418 (OWLD / post-delivery): https://www.gao.gov/assets/gao-17-418.pdf
- GAO-22-105007 (shipbuilding financing payments): https://www.gao.gov/assets/gao-22-105007.pdf
- DODIG-2026-032: https://media.defense.gov/2025/Dec/19/2003847587/-1/-1/1/DODIG-2026-032.PDF
- DODIG 09-065 (shipbuilding CIP): https://media.defense.gov/2009/Mar/26/2001711998/-1/-1/1/09-065.pdf
- DOT&E FY2025 CVN 78: https://www.dote.osd.mil/Portals/97/pub/reports/FY2025/navy/2025cvn78.pdf
- DON FY2025 AFR: https://www.secnav.navy.mil/fmc/FR/FY25_NavyAFR_12.8.25_FINAL.pdf
- SUPSHIP SOM Ch 4 Financial Management: https://www.navsea.navy.mil/Portals/103/Documents/SUPSHIP/SOM/Ch4-FinancialManagement-18Aug19.pdf
- SUPSHIP SOM Ch 6 Cost Estimating: https://www.navsea.navy.mil/Portals/103/Documents/SUPSHIP/SOM/Ch6-CostEstimating-01Nov17.pdf
- DON Financial Management Policy Manual: https://www.secnav.navy.mil/fmc/Documents/FINAL-FMPM.pdf
- NAVSEA SCN Desk Reference: http://pdf4pro.com/cdn/scn-desk-reference-sunset-design-5526fa.pdf
- OPNAVINST 4700.8M: https://www.secnav.navy.mil/doni/Directives/04000%20Logistical%20Support%20and%20Services/04-700%20General%20Maintenance%20and%20Construction%20Support/4700.8M.pdf
- DoD FMR Vol 1 Ch 4 (SFIS/SLOA): https://comptroller.war.gov/portals/45/documents/fmr/current/01/01_04.pdf
- DoD FMR Vol 1 Ch 10 (Advana): https://comptroller.war.gov/Portals/45/documents/fmr/current/01/01_10.pdf
- DoDM 5000.04 CSDR: https://www.esd.whs.mil/Portals/54/Documents/DD/issuances/dodm/500004p.pdf
- CADE: https://cade.osd.mil/

**Asset valuation and property (added 2026-11-08)**
- FMR Vol 4 Ch 25, General Equipment (supersedes Ch 6): https://comptroller.defense.gov/Portals/45/documents/fmr/current/04/04_25.pdf
- FMR Vol 4 Ch 24, Real Property: https://comptroller.defense.gov/Portals/45/documents/fmr/current/04/04_24.pdf
- FASAB handbook by chapter (SFFAS 6, 10, 23, 44, 50): https://fasab.gov/accounting-standards/document-by-chapter/
- SFFAS 23: https://files.fasab.gov/pdffiles/sffas-23.pdf
- SFFAS 44: https://files.fasab.gov/pdffiles/handbook_sffas_44.pdf
- SFFAS 50: https://files.fasab.gov/pdffiles/handbook_sffas_50.pdf
- MEV Contractor Acquired Property business rule: https://www.acq.osd.mil/asda/dpc/ke/gfp/docs/MEV-Contractor-Acquired-Property-Business-Rule.pdf
- OMB Circular A-123: https://www.commerce.gov/sites/default/files/opog/omb_circular_a-123.pdf
- OMB Bulletin 24-02 (audit requirements, GAGAS): https://www.whitehouse.gov/wp-content/uploads/2024/07/OMB-Bulletin-No.-24-02.pdf
- GAO-09-3SP Cost Estimating and Assessment Guide: https://www.gao.gov/products/gao-09-3sp
- Cost Accounting Standards, 48 CFR 9903 contract coverage: https://www.ecfr.gov/current/title-48/chapter-99/subchapter-B/part-9903
- DCAA Contract Audit Manual Chapter 8, CAS: https://www.dcaa.mil/Portals/88/Chapter%208%20Cost%20Accounting%20Standards%2004-23-21%20(508F).pdf
- FAR 52.230-2 Cost Accounting Standards clause: https://www.acquisition.gov/far/52.230-2
- DFARS Subpart 245.1: https://www.acq.osd.mil/dpap/dars/dfars/html/current/245_1.htm
- DFARS 252.245-7005 Management and Reporting of Government Property: https://www.acquisition.gov/dfars/252.245-7005-management-and-reporting-government-property.
- DoD GFP Operating Guide: https://toolbox-piee.eb.mil/uploads/GFP_SOP_Oct_2021_v7_0_7cdf02c1df.pdf
- GFP Module update briefing (GFP Position Report by CAGE or contract): https://www.waru.edu/sites/default/files/Migrate/EventAttachments/673/GFP%20Module%20Update%20DAU%20Sept%202022.pdf
- PIEE: https://piee.eb.mil/
- GAO-25-106868, Greater Accountability Needed over Contractor Acquired Property (names SUPSHIP): https://www.gao.gov/assets/gao-25-106868.pdf
- GAO-23-106098, F-35 Global Spare Parts: https://www.gao.gov/assets/gao-23-106098.pdf
- DODIG-2026-016, GPIPC remediation: https://www.dodig.mil/reports.html/Article/4339824/audit-of-dod-efforts-to-remediate-financial-statement-material-weaknesses-relat/
- DODIG-2015-144 (Material Weakness 7, GPIPC): https://comptroller.war.gov/Portals/45/documents/micp_docs/Reference_Documents/DODIG-2015-144.pdf
- DODIG-2013-105, Navy ERP and the military equipment material weakness: https://media.defense.gov/2013/Jul/18/2001712861/-1/-1/1/DODIG-2013-105.pdf
- DODIG 97-202, Financial Reporting of Government Property in the Custody of Contractors: https://media.defense.gov/1997/Aug/04/2001713628/-1/-1/1/97-202.pdf

**Industrial map (added 2026-11-08)**
- NAVSEA Sea Air Space 2019 carrier new construction brief (build strategy, lift counts, workforce): https://www.navsea.navy.mil/Portals/103/Documents/Exhibits/SAS2019/Capt%20Malone-SAS-05062019.pdf
- NAVAIR EMALS/AAG contract announcement: https://www.navair.navy.mil/news/US-Navy-awards-launch-and-recovery-system-contract-fourth-Ford-class-aircraft-carrier/Thu
- AWE engineering IDC N64498-18-D-4022: https://www.highergov.com/idv/N6449818D4022/
- DOE Naval Reactors FY2027 congressional justification: https://www.energy.gov/documents/doe-fy-2027-volume-1-nr
- BWXT as sole manufacturer of naval nuclear reactors (company filing): https://www.sec.gov/Archives/edgar/data/0001486957/000119312515225298/d943329dex991.htm
- EASR selection for CVN-79 in place of DBR: https://news.usni.org/2016/08/22/raytheon-awarded-92m-navy-contract-future-carrier-big-deck-aesa-radars
- CBO 2025 shipbuilding plan analysis: https://www.cbo.gov/publication/61155
- Naval Vessel Register: https://www.nvr.navy.mil/

**Data systems**
- USAspending: https://www.usaspending.gov/search/
- FPDS-NG: https://www.fpds.gov/
- SAM.gov: https://sam.gov/
- PIEE / EDA: https://piee.eb.mil/
- Treasury TAS/BETC: https://catalog.data.gov/dataset/treasury-account-symbols
- OMB apportionments: https://apportionment-public.max.gov/
- DoD reprogramming actions: https://comptroller.defense.gov/Budget-Execution/Reprogramming/

**Reporting, for leads only**
- USNI News CVN-79 coverage: https://news.usni.org/
- Inside Defense: https://insidedefense.com/
- HII news releases: https://www.hii.com/news/
- Naval News: https://www.navalnews.com/
- Stars and Stripes Navy: https://www.stripes.com/branches/navy/

---

---

# PART I. Asset valuation and evaluation

## I.1 Is Kennedy on the Navy's books? Yes, but not as a ship.

As of today the hull sits in **Construction in Progress**, not in Vessels. The accounting is explicit about the mechanism.

- **SFFAS 6** requires that for constructed PP&E, cost be accumulated in a CIP account and transferred to the applicable General PP&E account when construction is complete and the asset is placed in service. [FASAB standards](https://fasab.gov/accounting-standards/document-by-chapter/)
- **FMR Volume 4, Chapter 25** (which supersedes the long-cited Chapter 6) sets out the lifecycle. A CIP account is created after the decision to proceed is granted at Milestone C and the funding authorization document is complete (section 2.4.7.4). "Upon the date the asset is placed in service, the CIP will be relieved by the funding entity" (2.4.3.1). "When constructed items are accepted, the costs accumulated in the CIP account must be relieved" (2.4.7.8). Contractor Acquired Property "must be recognized by the funding DoD Component as general equipment when the item is delivered and accepted," and until acceptance, constructive delivery is recorded in CIP (2.4.1.6). https://comptroller.defense.gov/Portals/45/documents/fmr/current/04/04_25.pdf
- The **Military Equipment Valuation CAP business rule** states the same thing from the title side: title passes to DoD when the contractor obtains the property, but the property is not recorded on DoD financial statements "as other than construction in process" until it is delivered to DoD. https://www.acq.osd.mil/asda/dpc/ke/gfp/docs/MEV-Contractor-Acquired-Property-Business-Rule.pdf

**The live question this creates for CVN-79.** The ship reached **preliminary acceptance on 29 September 2026** and is scheduled for **delivery in March 2027**. Chapter 25 ties CIP relief to "placed in service" in one sentence and to "accepted" in another. Preliminary acceptance is an acceptance event that is explicitly not delivery. Whether CIP relief is triggered at preliminary acceptance, at delivery, or at commissioning decides **which fiscal year a roughly $13 billion asset appears on the balance sheet**, and the three candidate dates straddle a fiscal year boundary. Registered as **G14**.

**What the balance sheet says now.** The DON FY2025 Agency Financial Report reports General PP&E net book value of **$503.1 billion, 55.9% of total assets**, with Fund Balance with Treasury at $302.8 billion (33.6%) and Inventory and Related Property at $90.5 billion (10.1%). GPP&E "consists of Real Property (buildings, structures, utilities), Vessels, Aircraft, Construction-in-Progress." And the line that matters most here: **"Vessels and Aircraft make up over 90% of the CIP balance."** GPP&E as a whole remains a material weakness, with the Navy stating it "lacks adequate policies, procedures, and controls over the lifecycle of recording GPP&E as a whole." https://www.secnav.navy.mil/fmc/FR/FY25_NavyAFR_12.8.25_FINAL.pdf

So CVN-79 is inside a balance-sheet line that is (a) over 90% ships and aircraft, (b) carrying a material weakness, and (c) supported in part by manual on-top adjustments, which is **G7**.

## I.2 The standards stack, named

A carrier is **General Equipment**. It used to be its own category and is not any more, which is the single most important fact in this section.

### Accounting standards
| Standard | What it does here |
|---|---|
| **SFFAS 6**, Accounting for Property, Plant, and Equipment (Nov 1995, as amended) | The base standard. Historical cost, CIP treatment, placed-in-service transfer. [PDF](https://fasab.gov/accounting-standards/document-by-chapter/) |
| **SFFAS 23**, Eliminating the Category National Defense Property, Plant, and Equipment (May 2003) | Rescinded SFFAS 11 and the term "ND PP&E," and reclassified military equipment as **General PP&E** subject to SFFAS 6. This is why the ship is general equipment rather than a special defense category. https://files.fasab.gov/pdffiles/sffas-23.pdf |
| **SFFAS 44**, Accounting for Impairment of General PP&E Remaining in Use | Two-step: identify potential impairments, then test. Impairment requires both a decline in service utility and that it be permanent. https://files.fasab.gov/pdffiles/handbook_sffas_44.pdf |
| **SFFAS 50**, Establishing Opening Balances for General PP&E | Amends SFFAS 6, 10 and 23, rescinds SFFAS 35, and permits alternative valuation methods for opening balances. Issued explicitly so DoD could "focus on needed improvements to its systems and controls." https://files.fasab.gov/pdffiles/handbook_sffas_50.pdf |
| **FMR Volume 4, Chapter 25**, General Equipment | The DoD implementation. Supersedes Chapter 6. Capitalization thresholds, GFP and CAP treatment, CIP lifecycle, useful lives, depreciation. https://comptroller.defense.gov/Portals/45/documents/fmr/current/04/04_25.pdf |
| **FMR Volume 4, Chapter 24**, Real Property | For the shore side, including the Kitsap homeport work. https://comptroller.defense.gov/Portals/45/documents/fmr/current/04/04_24.pdf |

### The three parameters that actually drive the number
1. **Capitalization threshold: $1 million for Department of the Navy general fund general equipment.** $250,000 for other DoD components and working capital funds. Raised from $100,000 effective October 2013. Items below the threshold, or with a useful life under two years, are **expensed**. (FMR Vol 4 Ch 25, section 2.4.4; confirmed in the DoD FY2017 AFR: "the Departments of the Air Force and Navy General Funds capitalize General Equipment acquisitions that are $1 million and greater.") https://comptroller.war.gov/Portals/45/Documents/afr/fy2017/3-Financial_Section.pdf
2. **Useful life: Aircraft Carrier 50 years.** The FMR Table 25-2 weapon-system list gives Combat Ship 35 years, Cargo Ship 40 years, Aircraft Carrier 50 years, Submarine 33 years. Consistent with the MSAR, which records CVN 78 unit expected service life of 50.0 years and operational years 2017 to 2094.
3. **Depreciation: straight line only.** "DoD policy permits only the use of the straight line method of depreciation." Alternate methods such as activity-based or OPTEMPO require written OUSD(C)/ODCFO approval. Depreciation begins under the Month Available for Service method.

### Audit standards
| Standard | Role |
|---|---|
| **GAGAS**, the Yellow Book | The standard every financial statement audit and DoD OIG audit is performed under. OMB Bulletin 24-02: "The auditor's report(s) must state that the audit was performed in accordance with GAGAS." https://www.whitehouse.gov/wp-content/uploads/2024/07/OMB-Bulletin-No.-24-02.pdf |
| **OMB Circular A-123**, Management's Responsibility for Enterprise Risk Management and Internal Control | Implements the Federal Managers' Financial Integrity Act. Appendix A governs internal control over reporting and is the source of the "material weakness" vocabulary used throughout the DoD audit. https://www.commerce.gov/sites/default/files/opog/omb_circular_a-123.pdf |
| **OMB Circular A-136** | Form and content of the Agency Financial Report, including the MD&A. |
| **OMB Bulletin 24-02** | Audit requirements for federal financial statements, including who may audit and the ICOFR reporting path. |
| **GAO Green Book**, Standards for Internal Control in the Federal Government | The internal control standards A-123 points to. |
| **FISCAM**, Federal Information System Controls Audit Manual | How the system-side controls get tested, which is where the Navy's access and segregation of duties weakness lives. |

### Cost standards
| Standard | Role |
|---|---|
| **GAO-09-3SP**, GAO Cost Estimating and Assessment Guide | The four characteristics (comprehensive, well documented, accurate, credible) that GAO measured the CVN-79 estimate against and found it met one of four. https://www.gao.gov/products/gao-09-3sp |
| **DoDM 5000.04**, Cost and Software Data Reporting | The contractor cost reporting regime, DD 2794 plan, FlexFile. https://www.esd.whs.mil/Portals/54/Documents/DD/issuances/dodm/500004p.pdf |
| **MIL-STD-881** and ESWBS | The work breakdown structures cost is reported against. |
| **SUPSHIP SOM Chapter 6** | Estimate classes A through F, with **Class C the recommended classification for budget submittals to Congress**. EAC for construction, PEC for repair. https://www.navsea.navy.mil/Portals/103/Documents/SUPSHIP/SOM/Ch6-CostEstimating-01Nov17.pdf |
| **Cost Accounting Standards, 48 CFR 9904** | 19 standards governing how the contractor measures, assigns and allocates contract cost. Full coverage attaches at a single CAS-covered award of $50 million or more, requiring a CASB DS-1 Disclosure Statement describing the contractor's cost accounting practices. HII's CVN-79 awards are far above that. The Disclosure Statement is therefore the authoritative description of how HII's own books allocate direct and indirect cost to this hull. https://www.ecfr.gov/current/title-48/chapter-99/subchapter-B/part-9903 and [DCAA Chapter 8](https://www.dcaa.mil/Portals/88/Chapter%208%20Cost%20Accounting%20Standards%2004-23-21%20(508F).pdf) |
| **FAR Part 31** cost principles; **FAR 52.230-2** CAS clause | Allowability and the contractual CAS obligation. https://www.acquisition.gov/far/52.230-2 |
| **FMR Volume 4 Chapter 23** | The sanctioned G&A-on-total-direct-cost allocation convention already carried in `BACKGROUND.md`. |

## I.3 The three structural reasons capitalized value will never equal program cost

This is the part worth briefing, because it is not a data quality problem. It is definitional, and it will not go away with better data.

1. **Scope.** Capitalized value is the acquisition cost of the asset placed in service. Program cost includes things that never capitalize: terminated or reworked scope, the cost of delay, class research that benefited later hulls, government program office overhead, and FMS-funded content. Separately, the **$1 million Navy threshold means every component below it is expensed rather than capitalized even though it is physically installed on the ship**. Magnitude of that expensed tail for this hull is unknown and is **G19**.
2. **Timing.** Program cost accrues from FY2001 or FY2007 depending on the convention. Capitalized value appears at a single instant at placed in service. Roughly twenty years of accumulated cost collapses onto one date, and the depreciation clock then runs 50 years forward from it. No single report shows both shapes.
3. **Boundary.** Two different authorities set two different end points. **OWLD** governs what may be charged to the appropriation and is 11 months after completion of fitting out or 13 months after delivery depending on which document you read (E-3). **Placed in service** governs when the asset is recognized. They are different dates, set by different offices, for different purposes, and work legitimately charged to SCN after the asset is capitalized is real.

A fourth divergence is a genuine open risk rather than a definitional one: **whether GFE installed on the hull is capitalized separately as its own general equipment or rolled into the vessel's value.** The EMALS and AAG shipsets, the eleven Advanced Weapons Elevators and the EASR array are each individually well above the $1 million threshold and each is procured on a different contract by a different command. If both the hull record and the system record capitalize them, the Navy double counts. If neither does, they drop. Registered as **G15**.

## I.4 What could be done better

Five concrete items, each tied to something already acknowledged in a primary document rather than invented here.

1. **Per-hull CIP subledger keyed to the P-5 cost categories.** GAO already recommended per-hull cost and funding summary sections in the Ford-class SAR (GAO-17-575). The same cut applied to CIP would make capitalized value reconcilable to the budget categories in Part K rather than to a single total.
2. **Replace manual on-top adjustments with transaction-level settlement.** The Navy has already done this for Real Property CIP: the FY2025 AFR describes migrating RP CIP into Navy ERP and executing CIP transactions there, "Establishing CIP projects, accumulating CIP transactions (through monthly CIP settlement), and relieving CIP and recording assets placed into service." Vessels CIP is the remaining case. The pattern exists in-house.
3. **Record the placed-in-service determination as a dated, evidenced event with a named authority.** Today it is inferred from delivery. For a ship spending roughly six months between preliminary acceptance and delivery, and longer to commissioning, inference is not good enough to survive an audit test.
4. **Make the GFE and CFE split explicit in the asset record.** The P-5 and P-10 already separate them on the budget side (Part K.1). Carrying that same split into the property record closes G15 structurally rather than by reconciliation after the fact.
5. **Carry an impairment and useful-life review trigger.** SFFAS 44 applies to general PP&E remaining in use. A hull whose delivery slipped 54 months, whose radar suite changed from the lead ship's, and which sat between acceptance events across a fiscal year boundary is exactly the fact pattern where useful life and salvage assumptions should be revisited deliberately rather than defaulted.

---

# PART J. Government furnished property, contractor-held property, and spare parts

## J.1 The definitions, because the whole problem is a categorization dispute

- **FAR 45.101:** "Government property means all property owned or leased by the Government. Government property includes both government furnished property (GFP) and contractor acquired property (CAP)."
- **FMR Volume 4 Chapter 25:** GFP is "property in the possession of, or directly acquired by, the Government" (2.1.4). CAP is "property acquired, fabricated, or otherwise provided by the contractor" to which the Government holds title (2.1.1). Both become general equipment if they meet the general equipment criteria (2.1.3.2).
- **DFARS Subpart 245.1 and DFARS 252.245-7005**, Management and Reporting of Government Property: "It is DoD policy that all Government property be reported in the GFP module or Wide Area WorkFlow module of the Procurement Integrated Enterprise Environment (PIEE)." https://www.acq.osd.mil/dpap/dars/dfars/html/current/245_1.htm and https://www.acquisition.gov/dfars/252.245-7005-management-and-reporting-government-property.
- **The reporting clock:** the contractor "shall report the updated status of the property to the GFP module **within 7 business days** of the date the change in status occurs."

## J.2 This is a 25-year-old unresolved material weakness, not a new risk

- DoD's financial statement auditors have reported a DoD-wide material weakness related to **government property in the possession of contractors since fiscal year 2001**. [GAO-25-106868](https://www.gao.gov/assets/gao-25-106868.pdf)
- The same finding appears in **DODIG 97-202** (1997), "Financial Reporting of Government Property in the Custody of Contractors," which identified a material management control weakness in exactly this area. https://media.defense.gov/1997/Aug/04/2001713628/-1/-1/1/97-202.pdf
- **DODIG-2015-144** carried it as **Material Weakness 7, Government Property In Possession of Contractors**. https://comptroller.war.gov/Portals/45/documents/micp_docs/Reference_Documents/DODIG-2015-144.pdf
- In the FY2024 audit, GPIPC was one of **seven asset-accountability material weaknesses** out of the total set.
- **DODIG-2026-016**, 24 November 2025, "Audit of DoD Efforts to Remediate Financial Statement Material Weaknesses Related to Government Property in the Possession of Contractors." https://www.dodig.mil/reports.html/Article/4339824/audit-of-dod-efforts-to-remediate-financial-statement-material-weaknesses-relat/

**The finding that names this program's own contract administrator.** GAO-25-106868 found that **DCMA and the Navy (SUPSHIP) "were not consistently verifying the accuracy of contractors' CAP records for selected major defense acquisition programs,"** and that specialized equipment and high-dollar assets associated with the Air Force and Navy contracts reviewed "were not scheduled" for verification. SUPSHIP Newport News is the contract administrator for both CVN-79 contracts (Part D.5). This is not an analogy. It is the same office. https://www.gao.gov/assets/gao-25-106868.pdf

Also relevant and already in the verification record: **DODIG-2013-105** found that the Navy spent **$870 million** implementing Navy ERP for the Aircraft, Shipbuilding and related business processes and did not resolve the existing military equipment material weakness. https://media.defense.gov/2013/Jul/18/2001712861/-1/-1/1/DODIG-2013-105.pdf

## J.3 The F-35 precedent, stated precisely

The user's instinct is right, and the F-35 case is worth stating with exact figures because it is the most documented instance of this failure mode in DoD.

From **GAO-23-106098**, F-35 Program: DOD Needs Better Accountability for Global Spare Parts: https://www.gao.gov/assets/gao-23-106098.pdf

- The F-35 Joint Program Office "does not maintain accountability over the spare parts in the global spares pool held at non-prime contractor facilities," and the total value is "currently unknown, but estimated to be in the **billions of dollars**."
- Those parts are held at **more than 50 domestic and international facilities**. They include engines, tires and landing gear as well as bolts, screws and fasteners.
- The parts are not entered into an accountable property system of record that would capture real-time changes to property records.
- **Root cause is a categorization dispute, not a counting failure.** "One contributing factor to DOD's lack of accountability over these spare parts is the lack of agreement among various organizations as to whether the spare parts are both accountable under a contract and government-furnished property."
- **Since May 2018, one prime contractor incurred losses of over 1 million spare parts totaling over $85 million, of which less than 2 percent had been reviewed by the JPO.** As of October 2022 the same prime had reported over 900,000 parts valued at over $66 million for review.
- "DOD's lack of accountability over the F-35 global spares pool affects its ability to resolve the material weakness related to the F-35 program."
- DoD has estimated the value of F-35 parts in contractor possession at **over $220 billion**, which GAO reports is "likely significantly understated."
- Secondary but worth carrying as a lead: POGO reports program officials estimating **$18.63 billion or more** of F-35 property not properly accounted for, and notes that the prime's property database keys on the company's own tracking number rather than the OEM number, which is a join-key failure rather than a records failure. https://www.pogo.org/investigates/spare-us-the-f-35-parts-mismanagement

## J.4 Does the same exposure apply to CVN-79? Yes, with three differences each way.

**Same mechanism.** Single prime, sole source under FAR 6.302-1, two-decade duration, large GFE content, and the contract administered by SUPSHIP, the office GAO named as not consistently verifying CAP records.

**Worse for the carrier:**
1. The GFE includes the **nuclear propulsion plant**, funded as a separate advance procurement category with a 30 to 72 month lead time and its own security regime, which limits ordinary property-audit sampling.
2. **Outfitting and spares sit on a different SCN line (5110) from construction (2001)**, so the spares population is not even on the same budget line as the hull it outfits. A query scoped to the construction line cannot see them.
3. **Assets have moved between hulls without a procurement transaction.** The AAG MSAR records the transfer of one AAG engine set from CVN 78 to CVN 79 by PEO Carriers memorandum dated 19 May 2016. That is an inter-hull asset movement effected by memo. Any hull-level cost or asset attribution that relies on contract actions will miss it entirely. https://www.esd.whs.mil/Portals/54/Documents/FOID/Reading%20Room/Selected_Acquisition_Reports/FY_2023_SARS/AAG%20MSAR%20Dec%202023.pdf

**Better for the carrier:**
1. The end item is **one serialized hull at one fixed location**, not a million fungible parts across 50 sites. Existence and completeness testing is tractable in a way the F-35 spares pool is not.
2. The GFP ecosystem now exists and is mandatory: the **PIEE GFP Module**, the **IUID Registry**, and a 7-business-day reporting clock under DFARS 252.245-7005.
3. There is a **named report that answers the question directly**. The GFP Module produces a **GFP Position Report, which reports "GFP at Contractor by CAGE or Contract Number."** https://www.waru.edu/sites/default/files/Migrate/EventAttachments/673/GFP%20Module%20Update%20DAU%20Sept%202022.pdf

## J.5 The actionable query, which needs no new system

Run the **GFP Position Report for CAGE 43689** (HII Newport News Shipbuilding), scoped to contracts **N00024-15-C-2114** and **N00024-09-C-2116**. Cross-check against the IUID Registry for items carrying a registered UII. PIEE: https://piee.eb.mil/ ; GFP operating guide: https://toolbox-piee.eb.mil/uploads/GFP_SOP_Oct_2021_v7_0_7cdf02c1df.pdf

That is a defined population, a defined key, an existing report, and a mandated reporting cadence. Registered as **G16**. It is the cheapest high-value data request in this entire file, because unlike the ledger questions it needs no new access path, only the right role in a system that already exists.

---

# PART K. The cost increase timeline against the official cost categories

## K.1 The official cost category structure

The SCN justification book's **P-5 Cost Analysis** exhibit uses a fixed category set, identical across hulls, which makes it the only public structure that can carry a category-level variance. Row labels, in order:

```
Plan Costs
Basic Construction/Conversion
Change Orders
Electronics  (†)
Propulsion Equipment
Hull, Mechanical, and Electrical (HM&E)  (†)
Ordnance  (†)
Other Cost
  = Total Ship Estimate
Less Advance Procurement FY xxxx
Less Subsequent Full Funding FY xxxx
Less Cost to Complete FY xxxx
Less AP Transfer to NSBDF FY xxxx        (submarine lines only)
  = the year's request
```

Source: FY2024 and FY2025 SCN books. https://media.defense.gov/2023/Mar/29/2003188820/-1/-1/0/SCN_BOOK.PDF and https://www.secnav.navy.mil/fmc/fmb/Documents/25pres/SCN_Book.pdf

The **P-10 Advance Procurement Requirements Analysis** decomposes AP differently, and this is where GFE becomes visible:
```
Plans (Detailed)
Nuclear Propulsion Equipment
Basic
  = Total AP
```
with the narrative stating, verbatim from the FY2007 and FY2010 books: **"Nuclear Propulsion Equipment GFE funding is required to fund a shipset of reactor plant components for CVN 79"**; **"Hull, Mechanical, & Electrical (HM&E) funding is required for government furnished engineering services support"**; and basic funding for "the longest lead non-reactor plant propulsion and electric plant **contractor furnished equipment** necessary to support an efficient CVN 79 construction schedule." Lead times shown: Nuclear Propulsion Plant Equipment **30 to 72 months**, Electronics Equipment 37 to 43 months, Ordnance 12 to 24 months.
https://www.secnav.navy.mil/fmc/fmb/Documents/07pres/proc/scn_book.pdf and https://www.globalsecurity.org/military/library/budget/fy2010/navy/fy2010-scn.pdf

**This is the bridge between Part K and Part J.** The budget structure already separates government furnished from contractor furnished content by category and by lead time. The property records do not carry that split through. That gap is G15.

**Magnitudes: superseded. See Part N.1 for the verified CVN-79 column.** The paragraph below is retained only because the error in it is instructive, and N.7 explains it. The columns described here are COLUMBIA-class, not carrier.

**Original text, REJECTED:** The FY2024 and FY2025 books show two columns in the Carrier Replacement Program P-5 with these values (dollars in millions): Plan Costs 6,557.555 and 556.415; Basic Construction/Conversion 5,451.193 and 5,768.379; Change Orders 299.365 and 286.485; Electronics 358.141 and 349.701; Propulsion Equipment 1,700.896 and 1,614.000; HM&E 174.348 and 119.108; Ordnance 564.115 and 522.370; Other Cost 73.445 and 66.618; **Total Ship Estimate 15,179.058 and 9,283.076**. Neither total matches CVN-79, and these are not carrier columns at all. **G18 is now closed: see Part N.1.** **Correction, 2026-11-08.** An earlier version of this section inferred that the dagger (†) on Electronics, HM&E and Ordnance marked government-furnished content. The exhibit defines it in place: **"(†) indicates the presence of a P-8a."** It is an exhibit cross-reference, not a GFE marker. G17 is resolved negatively. See E-12 and N.7.

## K.2 The dated cost increase timeline

Each row is a budget submission's own estimate of total procurement cost for CVN-79, in then-year millions, except where noted. Primary assembly from CRS RS20643 Table 2, which exists precisely to show this movement.

| As of | CVN-79 estimate / baseline | Authority | What moved |
|---|---|---|---|
| FY2008 PB | 9,192.0 | Budget submission | Pre-procurement estimate |
| FY2011 PB | 10,413.1 | Budget submission | Estimate revision |
| FY2012 PB | 10,253.0 | Budget submission | Estimate revision, slightly down |
| FY2013 PB | 11,411.0 | Budget submission | Procurement year |
| Nov 2015 | cap lowered to 11,398.0 | FY2016 NDAA, P.L. 114-92 | Statute, not estimate |
| FY2017 PB | 11,398.0 | Budget submission | **Estimate equals the cap exactly** |
| FY2019 PB | 11,341.4 | Budget submission | Estimate revision, below the cap |
| FY2022 PB | 11,929.7 | Budget submission | Estimate revision |
| Aug 2021 | baseline +1,300 to ~12,700 | Navy, reported by GAO | Contract overruns, ship then over 88% complete |
| Aug 2023 | Cost Limitation Baseline to 12,936 | SECNAV notification to Congress | Capability-based delivery: PSA work moved into construction |
| FY2026 PB | 13,196.0, plus 150.0 CTC requested | Budget submission | Cost to complete |
| Jul 2026 | unit cost +3%, about +480 | GAO-26-108457 | About half from delivery schedule; funded from money already budgeted for post-delivery |

**Net movement: 9,192.0 to 13,196.0, about +$4.0 billion, roughly +44%, across nineteen budget submissions.**

## K.3 The analytic point: that single number is five different things

A product that draws one line labeled "cost growth" will be wrong about four fifths of it. The public record supports at least five distinct mechanisms, and they belong in separate cause categories in the variance ledger:

1. **Estimate revision with no scope change.** FY2011 through FY2013 and FY2019. The ship did not change; the estimate did.
2. **Statute moving and the estimate following it.** FY2016 NDAA lowered the cap to $11,398.0M and the FY2017 submission estimated exactly $11,398.0M. This is the documented instance of GAO's finding that "rather than the program cost estimate informing the cost cap, the cost cap informed the program cost estimate."
3. **Genuine contract overrun.** August 2021, +$1.3 billion, attributed by the Navy to contract overruns at over 88% complete. This is the only one of the five that is cost growth in the ordinary sense.
4. **Scope transferred into the baseline.** The 2020 two-phase to single-phase delivery change and the 2023 move of Post Shakedown Availability work into the construction contract. Work the Navy was always going to pay for moved from one accounting period and account into another. The ship got more expensive; the program did not.
5. **Reclassification inside the program.** FY2026 to FY2027. GAO's own words: unit costs rose about $480 million, about half from delivery schedule changes, "but the Navy is using funds it previously planned and budgeted for post-delivery activities, **so these are not new program costs**."

A sixth mechanism is visible in the same exhibit family and is worth carrying for other hulls: **"Less AP Transfer to NSBDF"** lines show advance procurement moving out of SCN into the National Sea-Based Deterrence Fund. That is a cost leaving the appropriation without leaving the program.

**The join that does not exist publicly.** The P-5 gives categories. The timeline gives dates and mechanisms. Nothing public attributes a dated increase to a category. The public approximation is the year-over-year delta of the P-5 by category, cross-read against the year-over-year delta of the MSAR contract tables. That is buildable from Ring 0 alone, it is the first real deliverable of the variance ledger, and it needs no access.

---

# PART L. Industrial map: what HII does, and who makes everything else

## L.1 What HII Newport News actually does

HII Newport News is the **hull builder and the systems integrator**. It is not the manufacturer of most of the ship's major systems.

- **Monopoly position.** The only US shipyard able to build large-deck nuclear carriers. Every US carrier procured since FY1958 was built there. The 2019 industrial base included roughly 2,000 supplier firms in 46 states. [CRS RS20643](https://www.congress.gov/crs_external_products/RS/PDF/RS20643/RS20643.297.pdf)
- **Method: modular construction.** Smaller sections are welded into large structural units called **superlifts**, equipment is installed while the unit is still on the ground, and the unit is lifted into **Dry Dock 12** by a **1,050-metric-ton gantry crane**. [Marine Log](https://www.marinelog.com/shipbuilding/shipyards/shipyard-news/video-newport-news-carries-out-704-ton-superlift/)
- **Scale: CVN-79 was planned at 447 total lifts** (one NAVSEA briefing says 448). 317 erected by February 2018. 90% erected March 2019. The MSAR records the structural milestones against **447 total erectables**: 50% at 224 units (June 2017), 75% at 341 units (April 2018). NAVSEA records 91% erected at 407 of 448.
- **The CVN-79 build strategy change, which is the heart of the 18% man-hour reduction claim:** larger superlifts erected at a higher state of outfitting completion, more parts installed in the shop and on the final assembly platen rather than on the ship, a new unit outfitting hall, and design changes carried over from CVN-78 lessons. NAVSEA's own words: "CVN 79 build sequence installs more parts in shop and on the final assembly platen, increasing the proportion of work accomplished early in the construction process." [NAVSEA SAS 2019 brief, CAPT Philip Malone](https://www.navsea.navy.mil/Portals/103/Documents/Exhibits/SAS2019/Capt%20Malone-SAS-05062019.pdf)
- **Representative superlifts, which give a feel for the unit of work:** 704 metric tons, January 2016, built from 22 smaller units, first portion of hangar bay, 80 by 105 feet. 900 tons, September 2016. 806 metric tons, February 2018, 17 individual units, 171 by 92 feet, berthing, electrical equipment rooms and workshops, 18 months to build. 780 tons, July 2019, the upper bow with the two forward catapults, completing the primary hull and the flight deck, 18 months to build.
- **Labor:** roughly **6,600 HII Newport News employees** involved across CVN 78 to CVN 81 construction as of 2019. NNS employs over 25,000 Virginians overall.
- **Class evolution, in NAVSEA's own framing:** CVN-78 was "First Nuclear / First Modular Construction," CVN-79 "Taking Modular Construction / Pre-Outfitting to a New Level," against the Nimitz-class baseline of "Stick-built With Some Box Units."

So HII's scope is detail design, structural fabrication, module assembly, pre-outfitting, erection, systems installation, integration, test and trials, and delivery. The content of most major systems arrives from elsewhere.

## L.2 Who makes the major systems

| System | Who makes it | How it reaches the ship | Funding and contracting path |
|---|---|---|---|
| **A1B reactor plant**, two per ship | Design by **Bechtel Marine Propulsion Corporation** (the "B" in A1B; Bechtel runs the Bettis and Knolls atomic power laboratories). **BWXT manufactured the reactor core and fuel and other nuclear components**, and is described in its own filings as "the sole manufacturer of naval nuclear reactors for submarines and aircraft carriers." | **GFE** | SCN advance procurement, category **Nuclear Propulsion Equipment**, 30 to 72 month lead time. Naval Reactors is jointly a Navy and DOE program; DOE funds the Naval Reactors appropriation separately. [ANS](https://www.ans.org/news/article-8074/us-navy-to-power-norfolk-base-using-aircraft-carrier/), [World Nuclear Association](https://world-nuclear.org/information-library/non-power-nuclear-applications/transport/nuclear-powered-ships), [BWXT filing](https://www.sec.gov/Archives/edgar/data/0001486957/000119312515225298/d943329dex991.htm), [DOE Naval Reactors FY2027 justification](https://www.energy.gov/documents/doe-fy-2027-volume-1-nr) |
| **EMALS** (Electromagnetic Aircraft Launch System) and **AAG** (Advanced Arresting Gear) | **General Atomics Electromagnetic Systems**, San Diego. Subcontractor **QinetiQ North America** supplies the launch control and arresting control hardware and software, a $16 million award for CVN-79. | **GFE**, installed by HII | **NAVAIR**, program office **PMA-251** (Aircraft Launch and Recovery Equipment). Contract **N00019-14-C-0037**, EMALS CVN 79 / CVN 80 Production. **Resolved 2026-11-08.** The differing MSAR figures are the same contract at different dates, not a conflict: the **Dec 2022 SAR** states a total contract value of **$1,629.0M**, award **8 May 2014**, definitized **22 Dec 2016**, CAGE **4V360**, contracting office NAVAIR Patuxent River, firm-fixed-price. The contract grew past **$1.7 billion** by 2026 through corrective-engineering modifications. **Nothing in these contract-level totals is the CVN-79 number** — the contract is CVN 79 *and* CVN 80, later extended, and the hull's share is the P-8a pair **EMALS $611.307M + AAG $219.131M = $830.438M**. The widely reported "~$737M" June 2015 figure is an announced not-to-exceed UCA value, not an obligation and not a CVN-79 total (see **E-13** on announcement-derived figures). Corrective-engineering modifications on this contract are class-wide and must not be attributed to CVN-79 without CLIN detail: $36.4M May 2021 (18 AAG Water Twister Mod-II shipsets), $9.63M Sep 2021 (Gen-3 EMALS position sensor blocks), $42.85M Jan 2023 (CVN-79 **and** CVN-80 hardware/software integration), $27.96M Dec 2023, $15.58M May 2026 (CVN-80). [NAVAIR](https://www.navair.navy.mil/news/US-Navy-awards-launch-and-recovery-system-contract-fourth-Ford-class-aircraft-carrier/Thu), [Defense Industry Daily](https://www.defenseindustrydaily.com/EMALS-Electro-Magnetic-Launch-for-Carriers-05220/), [QinetiQ](https://www.adsgroup.org.uk/knowledge/industry-member-news/qinetiq-awarded-emals-and-aag-support-contract-for-us-navy-s-future-aircraft-carrier/) |
| **Advanced Weapons Elevators**, eleven per ship | **Federal Equipment Company**, Cincinnati, Ohio. Ropeless design using **linear synchronous motors**, developed with **MagneMotion** plus NNS and NAVSEA. Capacity to 24,000 lb, speed to 150 ft/min. **Curtiss-Wright Exlar** supplies the electro-mechanical lock actuators. Selected in a competition against Oldenburg Lakeshore that began in 2003. | Installed on the ship; the AWE was the single largest driver of CVN-79's delay | **NSWC Philadelphia Division** holds **N64498-18-D-4022** for AWE engineering and technical services and the land-based test site. [HigherGov](https://www.highergov.com/idv/N6449818D4022/), [Naval Today](https://www.navaltoday.com/2021/12/24/us-navy-receives-final-weapons-elevator-for-13bln-ford-class-aircraft-carrier), [Curtiss-Wright](https://www.designworldonline.com/curtiss-wright-awarded-contract-from-federal-equipment-company-to-support-u-s-navy-cvn-80-and-81-ford-class-aircraft-carrier-programs/) |
| **Radar.** This is a **configuration break between CVN-78 and CVN-79.** | CVN-78 carries **Dual Band Radar**: Raytheon **AN/SPY-3** X-band plus Lockheed Martin **AN/SPY-4** Volume Search Radar S-band, with a Raytheon Radar Suite Controller. **CVN-79 and later replaced DBR** with Raytheon **AN/SPY-6(V)3 EASR** S-band, three fixed-face arrays, plus **AN/SPQ-9B** X-band surface search. DBR was dropped for the rest of the class after the Zumwalt class was truncated. | GFE | EASR engineering development model contract $92 million, August 2016. [USNI](https://news.usni.org/2016/08/22/raytheon-awarded-92m-navy-contract-future-carrier-big-deck-aesa-radars), [Seapower](https://seapowermagazine.org/raytheon-is-cranking-out-spy-6-radars-for-the-fleet/) |
| **Combat system** | **Ship Self-Defense System (SSDS) Mk 2**, Raytheon, integrated with **Cooperative Engagement Capability**. A CVN-78-class SSDS variant exists as its own program of record. | GFE | [Seapower](https://seapowermagazine.org/first-dual-target-test-of-ford-class-cvn-integrated-combat-system/?print=print) |
| **EMALS energy storage subsystems** | **KATO Engineering, Inc**, CAGE **3LVT8**, North Mankato, Minnesota. Holds **N00019-23-C-0040** for the **CVN-81** energy storage subsystems, firm-fixed-price, awarded **7 September 2023**, latest mod P00005 of 30 April 2025, **limited** technical data rights. | GFE | **The CVN-79 equivalent scope is invisible at prime level.** For CVN-79 the energy storage subsystem sits inside N00019-14-C-0037 as a General Atomics subcontract; the Navy only pulled it out as a separate prime for CVN-81. This is the cleanest worked example of the L.3 finding that the vendor map runs one tier deeper than the contract map — the same hardware is a prime contract on one hull and an invisible subcontract on another. [FY2027 MSAR](https://www.esd.whs.mil/Portals/54/Documents/FOID/Reading%20Room/Selected_Acquisition_Reports/PB_2027_MSARs/CVN_78_MSAR_FY2027_PBv2.pdf) |
| **Networks** | **CANES** (Consolidated Afloat Networks and Enterprise Services) | Installed under the HII contract | $37,544,972 FPIF modification to **N00024-15-C-2114**, March 2024, funded 65% FY2024 SCN and 35% FY2018 SCN |
| **Flight deck actuation** | **Curtiss-Wright Exlar** actuators in the Jet Blast Deflector, Integrated Catapult Control Station and LSO actuation systems | Various | [Curtiss-Wright](https://www.designworldonline.com/curtiss-wright-awarded-contract-from-federal-equipment-company-to-support-u-s-navy-cvn-80-and-81-ford-class-aircraft-carrier-programs/) |
| **Propulsion train** | Four shafts and propellers driven by steam turbines off the two A1B plants; roughly 260,000 shaft horsepower, with about three times the Nimitz-class electrical generating capacity | Mixed GFE and CFE | [Lyncean marine nuclear study](https://lynceans.org/wp-content/uploads/2018/07/Marine-Nuclear-Power-1939-2018_Part-2B_USA_surface-ships.pdf) |

**The radar change deserves its own note for the cost model.** CVN-79 does not carry the lead ship's radar. That makes CVN-79 a different configuration, not simply a second copy, which (a) adds non-recurring engineering and integration cost that has no CVN-78 analogue, and (b) weakens any learning-curve comparison between the two hulls. Any man-hour or cost-per-ton comparison between CVN-78 and CVN-79 that does not adjust for the DBR to EASR change is comparing two different ships.

## L.3 Why the industrial map changes the cost architecture

Three consequences, each actionable.

1. **The two HII contracts buy construction and integration, not content.** The P-5 categories **Electronics, Propulsion Equipment and Ordnance** are substantially government furnished, bought on other contracts by other commands: NAVAIR PMA-251 for EMALS and AAG, NSWC Philadelphia for AWE engineering, Naval Reactors and DOE for the reactor plant. The P-10 says so in plain language.
2. **Neither roll-up method is sufficient alone.** A contract-based roll-up anchored on CAGE 43689 captures the hull and misses the systems. A category-based roll-up from the P-5 captures the systems but cannot see the contracts beneath them. The hull answer requires both, joined, which is why G8 (subhead to NWA mapping) and G18 (the CVN-79 P-5 column) are complementary rather than alternatives.
3. **Cross-command GFE is where hull attribution breaks.** Different commands mean different contract writing systems, different contracting officers, different entitlement paths and different accounting offices. The reactor plant adds a different *department*, since Naval Reactors is funded through DOE. An EMALS shipset bought by NAVAIR on an aviation contract and installed by HII on a NAVSEA ship under a NAVSEA contract has no single line of accounting that says "CVN-79" from end to end. That, not the ledger seam, is the hardest attribution problem in this program.

---

# PART M. Where the other costs hide: the clue map

Ordered by expected materiality. Each entry gives the key to query, not just the place to look.

| # | Where | Key to query | Notes |
|---|---|---|---|
| 1 | **SCN line 2001** Carrier Replacement Program | 1611N / BA 02 / BLI 2001 / PE 0204112N; subhead | The construction spine. Part D.1. |
| 2 | **SCN line 5110 Outfitting** | 1611N / BA 05 / LI 5110 / PE 0204112N | Outfitting and spares. **Not on the construction line.** Directly implicated in J.4. |
| 3 | **SCN line 5300** Completion of PY Shipbuilding Programs | 1611N / BA 05 / LI 5300 / PE 0204112N | Where post-OWLD-era completion money lands. |
| 4 | **NAVAIR EMALS and AAG** | **N00019-14-C-0037**; PMA-251; General Atomics | Shipset value in the $1.36B to $1.70B range per the MSAR, needs resolution. |
| 5 | **Naval Reactors reactor plant** | SCN AP category "Nuclear Propulsion Equipment"; DOE Naval Reactors appropriation; BWXT; Bechtel Marine Propulsion | Crosses from Navy to DOE. 30 to 72 month lead. |
| 6 | **NSWC Philadelphia AWE** | **N64498-18-D-4022**; Federal Equipment Co | Engineering, technical services, land-based test site. |
| 7 | **Shared class RDT&E** | **PE 0604112N "CVN 78-80"** | EMALS, AAG, DBR development. Allocation method open, **G4**. |
| 8 | **Other Procurement, Navy** | OPN; seen as $1,650,000 of FY2025 OPN on the 21 Nov 2025 CVN-79 modification | Small but proves the line exists. |
| 9 | **Other appropriations on the MSAR funding table** | **1810N / BA 04 / LI 5664** Surface Training Equipment; **1804N / BA 01 / 1B5B** Ship Depot Operations Support | Published by the program itself as funding sources. |
| 10 | **Foreign Military Sales funds on the hull contract** | FMS Canada $1,979,967; FMS Norway $232,407; FMS Spain $10,542, all on CVN-79 modifications | **Arguably not US program cost at all.** A real cost-scope boundary case with a documented example. |
| 11 | **Other-service funds on the hull contract** | FY2025 RDT&E (USMC) $250,000 on the 21 Nov 2025 modification | Same point, different direction. |
| 12 | **GFP in contractor possession** | **GFP Position Report by CAGE 43689 / contract number**; IUID Registry | **G16.** Cheapest high-value request in the file. |
| 13 | **Contractor cost by work breakdown** | CSDR: DD 2794 plan, DD 1921 series, FlexFile, in **CADE** | **G11.** The only below-appropriation view. |
| 14 | **Post-delivery, PSA and fitting out** | Between delivery and OWLD; SCN per SOM Ch 4.4.1.3 | Part of SCN by rule, and the account the 2023 scope move drained. |
| 15 | **Consequence cost on other hulls** | Nimitz ten-month extension, and the NNS advance planning and long-lead contract for Nimitz inactivation and defueling | Caused by CVN-79's delay, will never carry a CVN-79 line of accounting. |
| 16 | **Shore infrastructure driven by the ship** | $145 million electrical systems overhaul at Naval Base Kitsap ahead of the 2029 homeport shift | Real property, FMR Vol 4 Ch 24, not general equipment. |
| 17 | **Below-threshold expensed content** | Items under the $1 million Navy capitalization threshold | **G19.** Installed on the ship, never capitalized. |
| 18 | **Reprogramming and apportionment** | DD 1415-1 actions; OMB apportionment footnotes for TAFS 017-1611 | Movement after appropriation that no J-book shows. |

---

---

# PART N. Analyst reconstruction: how the hull total is made up

**This Part was rebuilt 2026-11-08 on primary documents.** An earlier version of it reasoned from estimates because the primary sources had not been pulled. They have now: the FY2027 SCN justification book and a full USAspending transaction download for the detail design and construction contract, both in `ring0/reference/`. **The reconstruction is no longer an estimate. It reconciles to zero residual on two independent axes.** The method narrative is kept because one of its iterations failed instructively, and that failure is the most transferable thing in this file.

**Tags:** `VERIFIED` primary document. `DERIVED` arithmetic from verified inputs. `ESTIMATE` modelled. `UNKNOWN` no public value. `REJECTED` tested and failed.

## N.1 The answer. The authoritative figure is $13,409.970M, not $13,196.0M.

The FY2027 President's Budget supersedes the FY2026 figure carried through Parts A to M. Source: **Exhibit P-5c, Ship Cost Analysis, PB 2027 Navy, dated April 2026, appropriation 1611N / 02 / 1, P-1 line item 2001 Carrier Replacement Program, FY2013 column** (the FY2013 column is CVN-79, its procurement year). All `VERIFIED`, c=0.98.

| Cost category | $M | % of hull |
|---|---|---|
| Plan Costs | 898.865 | 6.7% |
| **Basic Construction/Conversion** | **8,463.156** | **63.1%** |
| Change Orders | 432.065 | 3.2% |
| Electronics (†) | 263.359 | 2.0% |
| **Propulsion Equipment** | **2,041.582** | **15.2%** |
| Hull, Mechanical, and Electrical (†) | 30.302 | 0.2% |
| **Ordnance (†)** | **1,149.651** | **8.6%** |
| Other Cost | 130.990 | 1.0% |
| **Total Ship Estimate** | **13,409.970** | 100.0% |

Computed sum of the eight categories equals the published total exactly. **Residual 0.000.**

**Two things in that table are counter-intuitive and both matter.**

**First, EASR is budgeted under Ordnance, not Electronics.** The P-40 Systems list for this line is explicit: under **Electronics** it lists only SHIP SELF DEFENSE SYSTEM (SSDS). Under **Ordnance** it lists ELECTROMAGNETIC AIRCRAFT LAUNCHING SYSTEM (EMALS), AN/SPY-6(V)3 ENTERPRISE AIR SURVEILLANCE RADAR (EASR), ADVANCED ARRESTING GEAR (AAG), and MANUALLY OPERATED VISUAL LANDING AID SYSTEM (MOVLAS). A radar sits in Ordnance. Anyone reading "Electronics 263.359" as the ship's electronics content will understate it by a factor of five.

**Second, the dagger does not mean what Part K.1 guessed it meant.** The exhibit defines it in place: **"(†) indicates the presence of a P-8a."** It is an exhibit cross-reference, not a government-furnished-equipment marker. My inference in K.1 was wrong and is corrected there. **G17 is resolved, negatively.**

## N.2 The second axis: funding streams. Also reconciles to zero.

Same exhibit, the deduction block beneath the categories.

| Stream | Years | $M | % of hull |
|---|---|---|---|
| Advance Procurement | FY2007 to FY2012 | 3,327.050 | 24.8% |
| Subsequent Full Funding | FY2014 to FY2018 | 7,504.668 | 56.0% |
| Cost to Complete | FY2022 to FY2027 | 2,087.300 | 15.6% |
| Net P-1 Funding (procurement-year residual) | FY2013 | 490.952 | 3.7% |
| **Total** | | **13,409.970** | 100.0% |

By year, all `VERIFIED`:
- **AP:** FY2007 52.750, FY2008 123.530, FY2009 **1,210.561**, FY2010 482.938, FY2011 902.473, FY2012 554.798
- **Subsequent Full Funding:** FY2014 917.553, FY2015 1,219.405, FY2016 1,569.543, FY2017 1,241.783, FY2018 2,556.384
- **Cost to Complete:** FY2022 291.000, FY2023 461.700, FY2024 624.600, FY2025 236.000, FY2026 150.000, FY2027 324.000

**Three findings from this axis.**

1. **A quarter of the hull, $3.33 billion, was bought before the ship was authorized.** Advance procurement ran FY2007 to FY2012; the procurement year was FY2013. My earlier estimate of the AP share was 15.6% to 16.9%; the true figure is **24.8%**, half again larger. The error came from an incomplete AP series that was missing FY2009's $1,210.561M, the single largest AP year. Any timeline that starts at authorization misses a quarter of the ship.
2. **Cost to Complete is not finished.** FY2027 adds another 324.000, so CTC now totals 2,087.300 and runs across six fiscal years, FY2022 through FY2027, for a ship that achieved preliminary acceptance in September 2026.
3. **The procurement year itself carried only 3.7%.** The nominal "procurement" of CVN-79 in FY2013 funded $490.952M of a $13.4 billion ship. The procurement year is an accounting label, not an economic event.

## N.3 The anchor chain, extended

| Step | $M | Tag |
|---|---|---|
| Statutory cap, FY2020 NDAA | 11,398.000 | VERIFIED |
| + Aug 2021 baseline increase (contract overruns) | 1,300.000 | VERIFIED |
| = implied baseline | 12,698.000 | GAO states "$12.7 billion" |
| + Aug 2023 increment to the Cost Limitation Baseline | 238.000 | DERIVED |
| = SECNAV Cost Limitation Baseline | 12,936.000 | VERIFIED |
| + increment to the FY2026 submission | 260.000 | DERIVED |
| = FY2026 PB total | 13,196.000 | VERIFIED |
| + increment to the FY2027 submission | 213.970 | VERIFIED |
| = **FY2027 PB Total Ship Estimate** | **13,409.970** | VERIFIED |

**Amount above the statutory cap: $2,011.970M, 17.7% over.**

The FY2027 increment is itemized in the book's own remarks, which is the best cause attribution in the entire public record for this hull:

> "Increase of $214M from the FY 2026 budget submission. The increase within Basic Construction ($187.6M) and Change Orders ($19.3M) ... supports Advanced Arresting Gear (AAG) Water Twister MOD II testing, associated delay and disruption, time related services, continued Advanced Weapons Elevator (AWE) work, wage and overtime increases, surge in manning to support sea trials and preliminary acceptance and additional outside engineering and vendor support to provide a more complete ship at delivery. Realignments within Electronics ($3.582), Propulsion equipment $7.000M, HM&E $.317M, Other Costs $.745M and Ordnance $2.601M due to fact of life changes and actual execution."

So +206.9 of the +213.97 is new money in two categories, and the rest is realignment between categories. **Delay and disruption, time-related services, and a manning surge are named as cost drivers in a budget exhibit.** That is a verified causal link from schedule slip to dollars, which is exactly what the variance ledger needs and what public data almost never supplies.

## N.4 Contract-level reconciliation, on real transaction data, both HII contracts

> **CORRECTION, 2026-11-08, second pass.** The first version of this section reconciled only the DD&C contract and carried the Construction Preparation contract at roughly $1.08B, a figure built by summing **announced** Department of Defense contract modifications. That method was wrong by a factor of four. The obligation record shows **$4,519,300,323.83** on N00024-09-C-2116. The correction is recorded at **E-13**, the method failure at **N.7 Error 3**, and it changes the headline of this section and of N.9. `VERIFIED`.

Two prime contracts, both HII Newport News, both from USAspending bulk downloads held in `ring0/reference/`, downloaded 2026-11-08. **1,875 transactions** in total.

| | **N00024-09-C-2116** | **N00024-15-C-2114** |
|---|---|---|
| MSAR contract title | CVN 79 **Construction Preparation (CP)** | CVN 79 **Detail Design & Construction (DD&C)** |
| Base action date | **2009-01-15** | 2015-06 (UCA) |
| **Base award obligation (mod 0)** | **$111,803,875.00** | — |
| Solicitation | N0002408R2116 | — |
| Pricing | **Cost Plus Fixed Fee** (937 of 948 actions) | Fixed-Price Incentive |
| Period of performance, current end | **2025-07-31** | — |
| **Total obligated** | **$4,519,300,323.83** | **$4,578,603,345.77** |
| Current = potential total value | $5,386,149,876.01 | $4,615,795,653.36 |
| **Unobligated ceiling remaining** | **$866,849,552** | **$37,192,308** |
| Total outlayed (reported) | $72,620,471.18 | **$0.00** |
| Transactions | 948 | 927 |
| Deobligations | 68, **−$66,794,065** | 52, **−$23,943,715** |
| Awarding office | SUPSHIP 770 actions / **NAVSEA HQ 178** | SUPSHIP |
| Funding office | PEO Carriers 883 / NAVSEA HQ 47 / SUPSHIP 16 | PEO Carriers |
| Federal accounts | **017-1611 and 017-1319** | 017-1611, 017-1319, 017-1804, 097-0400 |
| PSC / NAICS | 1901 Aircraft Carriers / 336611 | 1901 / 336611 |
| Competition | **Not competed, only one source, FAR 6.302-1, 1 offer** | same |
| CAS clause | **Included** | Included |
| GFE/GFP flag | 11 of 948 actions **do** use GFE/GFP | — |
| Last modified | 2026-07-20 | 2026-07-20 |

**G21 is now closed.** The Construction Preparation contract's base award was **$111,803,875.00 on 15 January 2009**, description `TAS::17 1611::TAS CVN79 CONSTRUCTION PREPARATION EFFORTS FY09`. It was never unpriced; it was simply never announced at a value that reached the press-release threshold.

### The handoff, which is the real structure of the ship's cost

| FY | 2116 CP $M | 2114 DD&C $M | combined/yr $M | cumulative both $M |
|---|---|---|---|---|
| 2009 | 195.3 | — | 195.3 | 195.3 |
| 2010 | 212.0 | — | 212.0 | 407.3 |
| 2011 | 327.4 | — | 327.4 | 734.7 |
| 2012 | 559.2 | — | 559.2 | 1,293.8 |
| 2013 | 398.1 | — | 398.1 | 1,691.9 |
| 2014 | 686.0 | — | 686.0 | 2,377.9 |
| **2015** | **885.6** | 196.5 | **1,082.1** | 3,460.0 |
| 2016 | 634.9 | 342.3 | 977.2 | 4,437.2 |
| 2017 | 312.4 | 616.7 | 929.1 | 5,366.3 |
| **2018** | 10.5 | **763.4** | 773.9 | 6,140.2 |
| 2019 | 2.8 | 648.6 | 651.4 | 6,791.6 |
| 2020 | 7.7 | 502.7 | 510.5 | 7,302.1 |
| 2021 | 17.5 | 243.1 | 260.6 | 7,562.7 |
| 2022 | 56.7 | 300.6 | 357.3 | 7,920.0 |
| 2023 | 29.2 | 371.6 | 400.8 | 8,320.8 |
| 2024 | 45.4 | 360.9 | 406.3 | 8,727.1 |
| 2025 | 5.1 | 120.0 | 125.2 | 8,852.3 |
| 2026 | 133.4 | 112.2 | 245.6 | **9,097.9** |
| **Total** | **4,519.3** | **4,578.6** | | **9,097.9** |

**Four findings from the curve, none of which was visible before this pass.**

1. **"Construction Preparation" is a misnomer, and the misnomer is where $4.5 billion went.** 635 of the 948 actions, **$2,493.7M**, are described `CVN 79 ADVANCE CONSTRUCTION`. Only 124 actions, $560.2M, use construction-preparation language. The CP contract was the Navy's vehicle for *building the ship* during the advance-procurement years, not for planning it. The three largest actions on it are **P00116, 2016-03-04, $520,091,550**, "CVN 79 ADVANCE CONSTRUCTION INCREMENTAL FUNDING"; **P00079, 2014-03-20, $451,075,032**; and **P00103, 2015-06-05, $350,843,727**.
2. **The two contracts are sequential, not parallel, and they cross in FY2017.** 2116 carries 93.2% of its lifetime total ($4,210.9M of $4,519.3M) by the end of FY2017 and then stops. 2114 ramps from FY2015 and peaks in FY2018. Peak combined obligation year is **FY2015 at $1,082.1M**, which is the year the DD&C contract was awarded — the Navy was funding both at once precisely during the transition.
3. **Both contracts are still open and still taking money in FY2026.** 2116 shows **$133.4M in FY2026**, including **P00181, 2025-12-03, $60,000,000**, "CVN 79 ADVANCE CONSTRUCTION" — on a contract whose published period of performance ended **2025-07-31**. Obligations after the stated end of performance, seventeen years after award. Either the PoP field is stale or these are closeout actions; the public record does not say which. New gap **G24**.
4. **$398.5M of the CP contract is non-nuclear propulsion plant.** 69 actions carry `CVN79 NON NUCLEAR PROPULSION PLANT`, including **P00053, 2012-09-27, $146,883,870** and **P00009, 2010-02-26, $79,273,618**. In the P-5c that scope belongs under **Propulsion Equipment**, not Basic Construction. The budget category and the contract vehicle do not align, which matters for every attribution below.

### Hull attribution: is 2116 actually CVN-79?

Keyword scan of all 948 transaction descriptions:

| Hull referenced | actions | $M |
|---|---|---|
| **CVN 79 / Kennedy** | **872** | **3,503.0** |
| no hull keyword (funding and admin mods) | 72 | 1,014.2 |
| CVN 80 / Enterprise | 3 | 1.8 |
| CVN 78 / Ford | 2 | 0.3 |
| Nimitz-class / defueling / inactivation | 1 | 0.0 |

**2116 is materially a single-hull contract.** Cross-hull contamination is $2.1M on $4,519.3M, 0.05%. The $1,014.2M with no hull keyword is administrative-mod text on a contract whose every titled effort is CVN 79 in the MSAR. `VERIFIED` c=0.92.

### The corrected reconciliation

| Iteration | | $M | share |
|---|---|---|---|
| **3a** | 2116 CP obligated | 4,519.300 | 33.70% of hull |
| | 2114 DD&C obligated | 4,578.603 | 34.14% of hull |
| | **combined** | **9,097.904** | **67.84% of hull** |
| | shipbuilder-side categories (Plan + Basic Construction + Change Orders + Other) | 9,925.076 | 74.01% of hull |
| | **combined as a share of those categories** | | **91.67%** |
| | residual left for government plan and engineering | 827.172 | |
| **3b** | less non-nuclear propulsion plant, moved to Propulsion Equipment | −398.509 | |
| | HII against shipbuilder-side categories | 8,699.394 | **87.65%** |
| | residual | 1,225.682 | |
| | Propulsion Equipment explained by 2116 | 398.509 | 19.52% of that category |
| **3c** | less the non-SCN slice (1.88%, from 2114's File C) | −163.549 | |
| | **SCN-only HII, shipbuilder-side** | **8,535.846** | **86.00%** |
| | residual for government plan and engineering | 1,389.230 | |

**The headline changes, and it changes in the direction that makes the ship easier to explain.** The old number said the contract everyone calls "the CVN-79 contract" was 34.2% of the ship, leaving two thirds unexplained. The true statement is that **two prime contracts with one company account for 67.8% of the hull and 91.7% of every budget category the shipbuilder is paid out of.** Iterations 3b and 3c tighten that to a band of **86% to 92%** depending on how the non-nuclear propulsion plant and the non-SCN slice are treated. Under every treatment the conclusion holds: **the shipbuilder side of CVN-79 is essentially two contract numbers, and the residual is government engineering, not hidden industry.**

### The outlay finding, which is the audit finding

| | obligated $M | outlayed $M | coverage |
|---|---|---|---|
| 2116 | 4,519.3 | 72.6 | 1.61% |
| 2114 | 4,578.6 | **0.0** | **0.00%** |
| combined | 9,097.9 | 72.6 | **0.80%** |

HII has obviously been paid billions of dollars. **What this shows is not a payment fact, it is a data fact: award-level outlay reporting to USAspending covers 0.8% of CVN-79's prime-contract obligations.** Outlays reach USAspending through File C, the award-level financial submission, and DoD's File C linkage to disbursement is incomplete. This is the public face of the same Fund Balance with Treasury and Government Property in Possession of Contractors weaknesses described in Parts I and J. **Operational rule: obligations in USAspending are usable for CVN-79; outlays are not, and the page carries no warning.** `VERIFIED` c=0.95. New gap **G25**.

### A $5,880,250 discrepancy inside USAspending itself

Two USAspending products disagree on the same contract. The `ContractAwardSummary` inside `CONT_N0002415C2114_*.zip` reports total obligated **$4,584,483,595.77**. The `Contracts_PrimeAwardSummaries` product and the sum of all 927 transaction-level `federal_action_obligation` values both give **$4,578,603,345.77**. The difference is exactly **$5,880,250.00**. The transaction sum and the prime-award summary agree with each other, so this file now carries **$4,578,603,345.77** as canonical and the earlier $4,584.484M figure is superseded. Recorded at **E-14**.

**A contamination case, confirmed from the federal record.** Transaction **P00154, dated 2024-12-16, $54,000,000**, carries the USAspending description "DETAIL DESIGN AND CONSTRUCTION CVN 79." The Department's own contract announcement for that same action describes it as establishing "requirements for facility upgrades for **Nimitz class aircraft carrier defueling and inactivation**." The authoritative transaction record and the authoritative press announcement describe the same $54M differently, and the transaction description is the one that is wrong. **Contract number is a necessary key and an insufficient one, and so is the transaction description field.** `VERIFIED` c=0.90.

## N.5 The appropriation map, from the contract's own account file

`Contract_N0002415C2114_FederalAccountFunding_1.csv`, 39 rows, total linked obligations **$1,656,686,482**.

| Federal account | $M | share of linked |
|---|---|---|
| **017-1611 Shipbuilding and Conversion, Navy** | 1,625.584 | **98.12%** |
| 017-1319 Research, Development, Test, and Evaluation, Navy | 28.281 | 1.71% |
| 017-1804 Operation and Maintenance, Navy | 3.656 | 0.22% |
| 097-0400 RDT&E, Defense-Wide | -0.835 | -0.05% |

Dominant Treasury Account Symbol: **017-2018/2022-1611-000**, $1,627.0M, 98.21%. Other TAS present span beginning periods of availability FY2015 through FY2021. Object class is **31.0 Equipment** at 100.05%. All funding is direct, none reimbursable. Program activity is **0002 SHIPBUILDING** at 58.30%, with **40.88% blank**.

**Four findings.**

1. **The TAS proves the five-year availability rule empirically.** `017-2018/2022-1611-000` is an FY2018 appropriation with availability through FY2022, exactly the SCN five-year window described in Part D.12, visible in the transaction record rather than inferred from policy.
2. **RDT&E and O&M money is obligated on the ship construction contract.** Small, $28.3M and $3.7M, but it falsifies any model that treats the construction contract as SCN-only. The Part M clue map is correct, and now has transaction-level proof.
3. **Account linkage covers only 36.1% of the contract.** $1.657B of $4.584B obligated. The remainder predates DoD's award-level account reporting to USAspending. **An analyst querying USAspending for this contract's appropriation split is seeing roughly a third of it, with no warning on the page.** `DERIVED` c=0.90.
4. **40.88% of the linked amount has a blank program activity.** The field exists, is required, and is empty for two fifths of the money.

## N.6 Equipment line items, by vendor

Captured from the PB2027 P-5a and P-8a equipment pages, FY2013 / CVN 79 rows. 22 items, **$1,059.688M total**, which is **30.4%** of the four GFE-bearing categories.

| $M | Vendor | Type | Award | Note |
|---|---|---|---|---|
| **611.307** | GENERAL ATOMICS | SS/FFP | May 2014 | EMALS |
| **219.131** | GENERAL ATOMICS | SS/FFP | May 2014 | AAG |
| 44.937 | RAYTHEON | C/CPIF | Dec 2019 | |
| 39.607 | RAYTHEON | C/FFP | Nov 2019 | |
| 39.423 | LOCKHEED MARTIN | SS/FFP | Dec 2022 | |
| 12.305 | VARIOUS | C/FFP | Mar 2017 | |
| 11.135 | LOCKHEED MARTIN | C/FFP | Apr 2019 | |
| 10.117 | LOCKHEED MARTIN | C/FFP | Jan 2020 | |
| 9.162 | RAYTHEON | C/FFP | Nov 2021 | |
| 7.730 | GENERAL DYNAMICS | C/FFP | Sep 2014 | |
| 7.389 | NAWCAD | Various | Dec 2016 | |
| 6.092 | RAYTHEON | C/FFP | Jun 2019 | qty 2 |
| 5.903 | BAE SYSTEMS | C/FFP | May 2016 | |
| 5.186 | RAYTHEON | C/FFP | Mar 2020 | qty 3 |
| 5.091 | RAYTHEON | C/FFP | Jun 2014 | |
| 4.528 | GENERAL DYNAMICS | C/FFP | Feb 2019 | |
| 4.505 | LAUREL TECHNOLOGIES | SS/FFP | Mar 2020 | |
| 4.024 | DRS | C/FFP | May 2020 | |
| 3.771 | VARIOUS | Various | Apr 2020 | |
| 2.863 | VARIOUS | Various | Jan 2020 | |
| 2.743 | Various | Various | Jan 2020 | |
| 2.739 | BOWHEAD | C/FFP | Jul 2016 | option |

By vendor: General Atomics 830.438, Raytheon 110.075, Lockheed Martin 60.675, Various 21.682, General Dynamics 12.258, NAWCAD 7.389, BAE Systems 5.903, Laurel Technologies 4.505, DRS 4.024, Bowhead 2.739.

**EMALS and AAG are now verified separately: $611.307M and $219.131M, $830.438M together, 6.2% of the hull.** That replaces the `REPORTED` $737M plus $26.6M in Part L.2, which was close on the total and wrong on the split. The book's own note records the contracting history: long-lead material undefinitized contract action May 2014, undefinitized production UCA June 2015 for CVN 79, production UCA definitized December 2016 for CVN 79 with a CVN 80 option exercised January 2017.

**Ordnance category 1,149.651 less EMALS and AAG leaves 319.213** for EASR, MOVLAS and the rest. **Propulsion Equipment, $2,041.582 and the second-largest category in the ship, has no captured line items at all.** The reactor plant is not itemized by vendor in the public exhibit. That is the largest single block of the hull with no public vendor attribution, and it replaces the old G20 with a sharper question.

## N.6a The three externally supplied contract numbers, run to ground

Three PIIDs were supplied from outside this research on 2026-11-08 with the question of why they were absent from it. The answer to the absence question is structural and worth stating before the individual answers, because it is a reusable rule.

**Why they were absent: both of my authoritative contract catalogs are closed lists, and neither one is a list of contracts that build the ship.**

- The **MSAR contract table** lists only the efforts under Cost and Software Data Reporting surveillance for the MDAP. For CVN 78-class that is four HII efforts and three launch-and-recovery efforts, and nothing else. Verified by extraction: the only contract numbers appearing anywhere in the FY2027 MSAR, the Dec 2023 MSAR and the Dec 2022 SAR are `N00024-09-C-2116`, `N00024-15-C-2114`, `N00024-16-C-2116`, `N00024-17-C-2117`, `N00019-14-C-0037`, `N00019-22-C-0033` and `N00019-23-C-0040`. **Seven numbers for a $13.4 billion ship.**
- The **SCN P-5a / P-8a equipment detail** lists vendor, contract type and award date for equipment line items, but **not contract numbers**. It gave me "GENERAL ATOMICS, SS/FFP, May 2014, $611.307M" — which I can now match to `N00019-14-C-0037`, award date **8 May 2014** per the MSAR, an exact date match — but the exhibit itself never prints a PIID.

**So a NAVSEA-held equipment contract that is neither a CSDR-surveilled MDAP effort nor printed in the budget exhibit is invisible to both catalogs simultaneously.** That is the gap these three numbers fell into. Correcting it requires querying FPDS-NG or USAspending by PSC 1901 and by DoD acquisition program code 223, outward from the ship rather than inward from the document. New gap **G26**.

### N00024-16-C-5370 — Raytheon — CVN-79 scope CONFIRMED, share bounded

| | |
|---|---|
| Vendor | Raytheon (now RTX) |
| Contracting activity | **NAVSEA, Washington Navy Yard** — not SUPSHIP |
| System | **AN/SPY-6(V)3 Enterprise Air Surveillance Radar (EASR)** |
| Base award | August 2016, $92.1M, engineering and manufacturing development |
| Relevant action | **July 2020, $125,881,928 FPIF option**, EASR low-rate initial production, **six units** |
| CVN-79 content | The LRIP option covers **two AN/SPY-6(V)3 fixed-face units for USS John F. Kennedy (CVN 79)** and units for the first FFG(X) |
| Funding | FY2017, FY2018 and FY2020 **SCN**, $122,301,170 obligated at option exercise |

**Is it CVN-79? Partly, and the part is already inside the $13.4 billion.** The PB2027 P-8a lists **AN/SPY-6(V)3 EASR** among CVN 79's Ordnance systems, and the equipment line items carry **Raytheon at $110.075M across three lines** (C/CPIF Dec 2019 $44.937M; C/FFP Nov 2019 $39.607M; and a smaller line). So the CVN-79 share of this contract is approximately **$110M, not its full obligated value**, and that $110M is already counted in N.6 and in the reconciliation above. **No correction to the hull total is required.** `VERIFIED` on the contract identity c=0.92; `DERIVED` on the $110M attribution c=0.80.

**The important structural point: this is a multi-platform, multi-hull contract.** EASR under 5370 goes to LHA-8, CVN-74, LPD-29, LPD-30, CVN-79 and FFG-62. **Its obligation total is not a CVN-79 number and must never be used as one.** Attribution requires CLIN and ACRN detail, which is not public. This is the clearest live example of the Part M rule that a contract number alone is not a hull key.

### N00024-14-C-4201 and N00024-18-C-4100 — General Atomics — UNRESOLVED

**Status: not identified. Do not use either number as a CVN-79 cost source until resolved.** `UNKNOWN` c=0.15.

What is established, and what it rules out:

1. **Neither appears in any MSAR, SAR or SCN exhibit held in `ring0/reference/`.** Direct extraction over all four documents returns no match.
2. **Neither can be the EMALS/AAG shipset money.** Both are `N00024` (NAVSEA) prefixes. The CVN-79/80 EMALS and AAG production contract is **`N00019-14-C-0037`**, a **NAVAIR** Patuxent River contract, CAGE **4V360** General Atomics, award **8 May 2014**, definitized 22 Dec 2016, total contract value **$1,629.0M** per the Dec 2022 SAR. The MSAR records it as the sole EMALS/AAG production vehicle for both hulls. The CVN-79 shipset portion is already in the hull at **$611.307M EMALS + $219.131M AAG = $830.438M**, matched to the P-8a by vendor, pricing type and award month. **Adding either N00024 contract to the hull on the assumption it is launch-and-recovery money would double-count.**
3. **The vendor name is ambiguous in the federal record.** "General Atomics" resolves to several distinct entities with different CAGE codes — GA Electromagnetic Systems (4V360), GA Aeronautical Systems, GA proper. NAVSEA buys railgun, hypervelocity projectile, high-power laser and power-conversion work from GA-EMS, none of which is carrier shipset scope.
4. **A USAspending search returning a contract alongside CVN-79 contracts does not make it CVN-79.** A search on PSC **1901 Aircraft Carriers**, on DoD acquisition program code **223**, or on vendor plus Navy will all return carrier-adjacent and non-carrier results together. N00024-09-C-2116 itself carries acquisition program code 223 labelled **"CVN 78"** — the class code, on a CVN-79 contract.

**Resolution path, cheapest first.** USAspending award page by generated unique award ID (`CONT_AWD_N0002414C4201_9700_-NONE-_-NONE-`), or FPDS-NG Advanced Search on PIID, either of which returns the base transaction description, PSC, place of performance and funding office in one look. Both were attempted from this session and refused by the network allowlist, not by the data. **This is a five-minute lookup for anyone with a browser, and it should be done before the numbers are used.** New gap **G27**.

## N.6b What the MSAR contract table yields that was not previously catalogued

Extraction of the FY2027 MSAR (dated **21 April 2026**) contract tables produced four findings beyond CVN-79.

**1. The HII effort structure is four efforts across three PIIDs, not two contracts.**

| Effort | PIID / effort no. | Contractor | Phase |
|---|---|---|---|
| CVN 79 Construction Preparation (CP) | N00024-09-C-2116 / 1 | HII NNS | Production |
| CVN 79 Detail Design & Construction | N00024-15-C-2114 / 1 | HII NNS | Production |
| **CVN 80 Detail Design & Construction** | **N00024-16-C-2116 / 2** | HII NNS | Production |
| **CVN 81 Detail Design & Construction** | **N00024-16-C-2116 / 3** | HII NNS | Production |

**`N00024-16-C-2116` is not a typo for `N00024-09-C-2116`.** They share the last four digits and are different contracts seven years apart. **Any keyword or fuzzy match on "2116" will merge CVN-79 money with CVN-80 and CVN-81 money.** That is a live contamination hazard for exactly the kind of Advana query this dossier is written to support, and it is the single most dangerous identifier collision found so far. New gap **G28**; add to the Part G key set.

**2. The two-carrier block buy, with its own price and variance.** The MSAR states that on **31 January 2019 a $14,917,738,145 fixed-price-incentive-firm-target modification** to N00024-16-C-2116 was awarded for DD&C of CVN 80 and CVN 81. For effort 2 (CVN 80): initial target price **$152.0M**, current target **$8,560.9M** against ceiling **$9,614.3M**, estimate at completion **$10,039.5M**, latest modification **P00166 dated 12 December 2025**, work start **24 August 2017**. Against an IPMDAR effective date of **15 December 2025**: **work completed 56.43%, cost variance −$1,745.6M, schedule variance −$1,431.8M.** The MSAR attributes the schedule variance to assembly trades, facilities trades, platform engineering and nuclear engineering and testing, citing resequenced and deferred work, rework, green labor and **labor shared across all shipbuilding programs at the shipbuilder** — the same constrained-workforce mechanism Part B identifies for CVN-79, now quantified on the follow-on hulls. `VERIFIED` c=0.95.

**3. DCARC CSDR compliance is rated Red.** The MSAR prints **"DCARC CSDR Compliance Rating: Red"** against both the HII contract block and the launch-and-recovery contract block. **The program's contractor cost data reporting is formally deficient.** This has a direct consequence for Part D.9: a FlexFile or legacy 1921-series pull from CADE for this program should be expected to be late, incomplete or non-compliant, and the collection request should ask for the compliance assessment alongside the data. This materially lowers my prior confidence that CADE can resolve the Propulsion Equipment attribution gap. `VERIFIED` c=0.95.

**4. A new named vendor at shipset level.** **KATO Engineering, Inc**, CAGE **3LVT8**, North Mankato, Minnesota, holds **N00019-23-C-0040**, CVN 81 **EMALS Energy Storage Subsystems** production, firm-fixed-price, awarded **7 September 2023**, latest mod P00005 dated 30 April 2025, limited technical data rights. The equivalent CVN-79 energy-storage scope sits inside N00019-14-C-0037 as a GA subcontract and is therefore invisible at prime level — **a worked example of the Part L finding that the vendor map goes one tier deeper than the contract map.** Add to Part L.2.

## N.7 What the method got wrong, and why that is worth keeping

Three errors. Two were caught internally. The third was caught by the reader, and it is the worst of them.

**Error 1, rejected before publication: borrowing cost-category proportions from the wrong platform.** The first attempt applied P-5 percentages from columns captured out of an earlier SCN book. The output looked clean. Falsification tells in the same page extracts: "Less AP Transfer to NSBDF," which is statutorily a ballistic-missile-submarine fund; "Large Aperture Bow array hydrophones"; "AN/WSQ-9 signal analysis system"; and an explicit sentence naming COLUMBIA Class Submarines. **Those were submarine columns.** The row structure is identical across every SCN line, which is why the extract passed inspection.

Comparing that rejected model against the verified answer shows how wrong it would have been. It produced Basic Construction at 38.3% and Plan Costs at 40.8%. The truth is **Basic Construction 63.1% and Plan Costs 6.7%.** The model had the two largest categories almost exactly inverted, and it would have been published with an `ESTIMATE` tag and a confidence score of 0.55.

**The lesson, stated as a rule: a confidence score attached to a mis-populated model does not warn the reader, it reassures them.** Tagging is necessary and not sufficient. What caught this was not the tag, it was going back to the surrounding text and asking what platform the numbers belonged to. This is the concrete case for decision D16's rule that unreliable material gets no join path to canonical data.

**Error 2, published and now corrected: inferring the dagger footnote's meaning.** Part K.1 reasoned that the dagger on Electronics, HM&E and Ordnance probably marked government-furnished content, because those are the GFE-heavy categories and the pattern fit. The exhibit defines it in place: it indicates the presence of a P-8a exhibit. The inference was plausible, convenient, consistent with everything else, and wrong. It is corrected in K.1 and recorded at E-12.

**Error 3, published, caught by the reader, and the most serious of the three: summing announced contract modifications and treating the sum as obligations.** The Construction Preparation contract was carried at roughly **$1.08B**. Its actual obligated value is **$4,519,300,323.83**. The understatement was **$3.44 billion, a factor of 4.18**, and it propagated into the N.4 headline, into N.8, and into sentence 2 of the brief.

The mechanism was this. Department of Defense daily contract announcements have a dollar **threshold** — they report actions above it and are silent below. I reconstructed the contract by collecting announcements and adding them up. That method cannot produce a contract total, for three compounding reasons:

1. **It omits every below-threshold action.** On 2116 that is most of the 948 actions.
2. **It omits incremental funding actions**, which on a cost-plus shipbuilding contract are the dominant obligation mechanism. `CVN 79 ADVANCE CONSTRUCTION INCREMENTAL FUNDING` and `INSTALLMENT FUNDING` actions carry $2.49 billion on this contract and are mostly unannounced.
3. **It cannot net deobligations.** 2116 carries **68 deobligating actions totalling −$66.8M**, invisible to press releases by construction.

**The error was knowable without new data.** The contract ran from 2009 to 2025 on a ship whose shipbuilder-side budget categories total $9.9 billion, and the other prime contract alone accounted for $4.6 billion. A $1.08 billion Construction Preparation contract left a $4.2 billion hole in the shipbuilder side that I described as "government engineering, production support and waterfront support" rather than treating as a falsification signal. **I had the residual in front of me, wrote it down, and rationalized it instead of testing it.**

**The rule, stated so it is reusable: a press release is an announcement, never a record. Obligations come from the obligation record — FPDS-NG, USAspending transaction history, or the accounting system — and from nowhere else.** The corollary matters more: **a large unexplained residual is a finding, not a remainder.** When a reconciliation leaves a gap and the gap gets a narrative label, the label is a hypothesis that needs a test, and the test here was one download.

**All three errors share a shape.** A structural pattern was real, the interpretation laid over it was invented, and the result was coherent. Coherence is not evidence. In Errors 1 and 2 what settled the question was reading the primary document; in Error 3 what settled it was reading the primary *data*, and nobody had read it because the narrative already closed.

## N.8 Confidence summary and what remains unknown

| Component | $M | % hull | Tag | c |
|---|---|---|---|---|
| **Total Ship Estimate, PB2027** | **13,409.970** | 100.0% | VERIFIED | 0.98 |
| Eight cost categories, each | per N.1 | | VERIFIED | 0.98 |
| Four funding streams, each by year | per N.2 | | VERIFIED | 0.98 |
| **CP contract N00024-09-C-2116 obligated** | **4,519.300** | **33.7%** | VERIFIED | 0.95 |
| **CP contract base award, 15 Jan 2009** | **111.804** | 0.8% | VERIFIED | 0.95 |
| **DD&C contract N00024-15-C-2114 obligated** | **4,578.603** | **34.1%** | VERIFIED | 0.95 |
| **Two HII primes combined** | **9,097.904** | **67.8%** | VERIFIED | 0.95 |
| CP non-nuclear propulsion plant content | 398.509 | 2.97% | VERIFIED | 0.90 |
| DD&C appropriation split (partial coverage) | 1,656.686 linked | 36.1% of contract | VERIFIED | 0.90 |
| EMALS, N00019-14-C-0037 | 611.307 | 4.6% | VERIFIED | 0.95 |
| AAG, N00019-14-C-0037 | 219.131 | 1.6% | VERIFIED | 0.95 |
| Equipment line items captured, all vendors | 1,059.688 | 7.9% | VERIFIED | 0.90 |
| EASR CVN-79 share, N00024-16-C-5370 | ~110.075 | 0.8% | DERIVED | 0.80 |
| **Total attributed to a named contract or vendor line** | **10,157.592** | **75.8%** | | |
| **Unattributed residual** | **3,252.378** | **24.2%** | | |
| Propulsion Equipment, less the CP non-nuclear content | 1,643.073 | 12.3% | **UNKNOWN** | 0.10 |
| N00024-14-C-4201 and N00024-18-C-4100 identity | n/a | n/a | **UNKNOWN** | 0.15 |
| Advanced Weapons Elevators shipset price | n/a | n/a | **UNKNOWN** | 0.15 |
| Outfitting and post-delivery attributable to this hull | n/a | n/a | **UNKNOWN** | 0.20 |
| CVN-79 disbursements from public data | n/a | n/a | **UNKNOWN** | 0.05 |

**Attribution improved from 42.2% to 75.8% of the hull in this pass**, entirely by replacing an announcement-derived figure with the obligation record. The remaining **$3,252.4M residual is not a budget gap** — the budget closes to zero twice over, in N.1 and N.2. It is the portion of the hull that **no public contract-level record attributes to CVN-79**, and it is dominated by one thing: the nuclear propulsion plant at up to $1,643.1M, furnished through Naval Reactors with funding crossing into the Department of Energy and no public vendor line item anywhere.

**Gaps closed by this pass:** G10 (OWLD), G17 (dagger, resolved negatively), G18 (CVN-79 P-5 column obtained in full), **G21 (CP base award, now $111,803,875 on 15 Jan 2009)**.
**Gaps opened by this pass:** G24 (post-PoP obligations on 2116), G25 (outlay linkage at 0.8%), G26 (contract catalogs are closed lists), G27 (the two GA PIIDs), G28 (**the 2116 identifier collision**).

**G10 is resolved and it settles a documentary conflict.** The PB2027 production-status block gives, for CVN 79: contract award **Jun 2015**; award to delivery **141 months**; construction start to delivery **193 months**; delivery **Mar 2027**; **Completion of Fitting Out Jul 2027**; **Obligation Work Limit Date Jun 2028**. July 2027 plus eleven months is June 2028. That **confirms OPNAVINST 4700.8M** (OWLD is eleven months after completion of fitting out) and **refutes** the NAVSEA SCN Desk Reference reading of thirteen months after delivery, which would give April 2028. **E-3 is resolved in favor of the OPNAVINST rule.**

**Still open, now sharper:** the reactor plant is $2.04 billion, 15.2% of the ship, the second-largest category, and carries **no public vendor line item**. Part L establishes who makes it, Bechtel Marine Propulsion designing and BWXT manufacturing the core and fuel, with funding crossing into the Department of Energy. What does not exist publicly is the money. That is now the largest single unattributed block in the hull, and it is a better-posed question than the old G20.

**Outfitting and post-delivery** appears on the P-40 as an informational row for the whole line item, not per hull: prior years 890.169, FY2025 64.813, FY2026 101.780, FY2027 125.843, total **1,766.730** across all hulls on line 2001. The CVN-79 share is not separable from the published row, which is a new gap.

## N.9 The three sentences to brief

1. **The ship is $13,409.970M and it decomposes exactly, two different ways.** By category it is 63.1% basic construction, 15.2% propulsion equipment, 8.6% ordnance, 6.7% plans, and 6.4% everything else. By funding stream it is 24.8% advance procurement before authorization, 56.0% subsequent full funding, 15.6% cost to complete still running, and 3.7% in the procurement year itself. Both sum to the published total with zero residual. `VERIFIED`.
2. **Two contracts with one company are 67.8% of the ship and 91.7% of everything the shipbuilder is paid out of.** $4.519 billion on N00024-09-C-2116, Construction Preparation, 2009 to 2017; $4.579 billion on N00024-15-C-2114, Detail Design and Construction, 2015 to now; $9.098 billion combined across 1,875 transactions, against a $13.410 billion hull. The two are sequential and cross in FY2017. **"Construction Preparation" built the ship — $2.49 billion of it is described as advance construction, not planning.** `VERIFIED`.
3. **The ship is $2.012 billion, 17.7%, above its statutory cost cap, and that overage is fully attributable to four dated movements** of which the $1.3 billion August 2021 contract overrun is the only one that is cost growth in the ordinary sense. `VERIFIED` on the figures, `DERIVED` on two of the increments.
4. **What cannot be answered from public data, stated so the sponsor is not surprised later.** Two things. The **nuclear propulsion plant, up to $1.64 billion, 12.3% of the hull**, has no public vendor attribution of any kind. And **disbursements are not measurable at all**: award-level outlay reporting covers **0.8%** of the $9.098 billion obligated on the two prime contracts, which is the audit's Fund Balance with Treasury weakness appearing in the public record. **Obligations are usable, outlays are not.** `VERIFIED`.

---

**End of file.** Parts A to M are source material and nothing in them is cleared for use as a reported figure without pulling the cited primary source and recording its as-of date. Part N is analysis built on primary documents held in `ring0/reference/`; its `VERIFIED` lines are quotable with their source, and its `ESTIMATE` and `UNKNOWN` lines are not.
