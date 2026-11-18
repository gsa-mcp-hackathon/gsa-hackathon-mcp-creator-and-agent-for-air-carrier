# SCN J-Book Exhibit and Column Reference (Carrier Replacement Program, LI 2001)

Status: working reference, written 2026-11-10 from the 22 SCN budget books in the PDF store (PB2006-PB2027).
Scope: Shipbuilding and Conversion, Navy (appropriation 1611), Budget Line Item 2001 Carrier Replacement Program, plus the CVN-81 line. Hulls CVN-77 through CVN-82.
Every statement below is either (a) read from the books with a page anchor, (b) a tie-out run against the extracted numbers, or (c) marked INFERENCE / OPEN.

---

## 1. What a J-book is, and what it is not

* A J-book (budget justification book) is the Navy's request to Congress for one President's Budget (PB) cycle. PB N is published around Feb-Jun of calendar N-1 and requests funds for fiscal year N.
* All dollar amounts are **budget authority / Total Obligational Authority (TOA)** by fiscal year of appropriation. They are not obligations, not outlays, and not contract values.
* "Actuals" in a J-book means the budget authority actually provided for that fiscal year after enactment, rescissions and reprogrammings. It does **not** mean money spent.
* Obligations and outlays come from other sources: USAspending prime transactions, File C (federal account funding by award), and the DFAS/Navy ERP ledger. See section 9 for the join path.

## 2. Fiscal-year column roles (the request / enacted / actual triangle)

Each book shows three fiscal years of budget authority in its front-matter P-1, and the P-40 adds the prior years and the out-years. For **PB N**:

| Column | Role | Meaning |
| --- | --- | --- |
| FY N-2 | Prior year (PY) | Actual TOA after enactment and reprogramming |
| FY N-1 | Current year (CY) | Enacted. If there was no full-year bill at print time: annualized CR, or "PB request with CR adjustment" |
| FY N | Budget year (BY) | The request |
| FY N+1 to N+4 | Out-years (P-40 only) | FYDP projection, not a request |
| Prior Years / To Complete / Total | Cumulative (P-40 only) | Life-of-program totals |

So a single fiscal year's money appears three times: as the request in PB FY, as the enacted (or CR) amount in PB FY+1, and as the actual in PB FY+2. Example, CVN-80 subsequent full funding (SFF) for FY2025: 1,186.873 requested (PB2025), 1,123.124 enacted (PB2026), 1,123.124 actual (PB2027). Values in $M.

The column headings printed in the P-1 of each book (read from the page, not assumed):

| PB | FY N-2 heading | FY N-1 heading | FY N heading | P-1 pages |
| --- | --- | --- | --- | --- |
| 2006-2009 | unlabeled FY column | unlabeled FY column | unlabeled FY column | 3-8 |
| 2010 | FY 2008 Base&OCO Actuals | FY 2009 Base&OCO SupReq | FY 2010 Base / Total | 7 |
| 2011 | FY 2009 (Base & OCO) | FY 2010 Base & OCO Enacted | FY 2011 Base / Total Request | 9-10 |
| 2012 | FY 2010 (Base & OCO) | FY 2011 Request with CR Adj; FY 2011 Annualized CR | FY 2012 Base / Total | 8-10 |
| 2013 | FY 2011 Actuals | FY 2012 Base / Total (unlabeled) | FY 2013 Base / Total | 9-10 |
| 2014 | FY 2012 (Base & OCO) | FY 2013 Request with CR Adj | FY 2014 Base | 9-10 |
| 2015 | FY 2013 (Base & OCO) | FY 2014 Base / Total Enacted | FY 2015 Base | 7 |
| 2016 | FY 2014 (Base & OCO) | FY 2015 Base / Total Enacted | FY 2016 Base / Total | 9-10 |
| 2017 | FY 2015 (Base & OCO) | FY 2016 Base / Total Enacted | FY 2017 Base / Total | 11-12 |
| 2018 | FY 2016 Base + OCO | FY 2017 PB Request with CR Adj | FY 2018 Base / Total | 15-18 |
| 2019 | FY 2017 (Base + OCO) | FY 2018 PB Request with CR Adj | FY 2019 Base / Total | 15-18 |
| 2020 | FY 2018 (Base + OCO) | FY 2019 Base / Total Enacted | FY 2020 Base / Base + OCO | 16-18 |
| 2021 | FY 2019 (Base + OCO) | FY 2020 Base / Total Enacted (Base+Emerg+OCO) | FY 2021 Base / Base + OCO | 16-18 |
| 2022 | FY 2020 Actual | FY 2021 Enacted | FY 2022 Request | 10 |
| 2023 | FY 2021 (Base + OCO) | FY 2022 Enactment (less supplementals / total) | FY 2023 Request | 16-18 |
| 2024 | FY 2022 Actuals | FY 2023 Enactment (less supplementals / total) | FY 2024 Request | 12-13 |
| 2025 | FY 2023 Actuals | FY 2024 PB Request with CR Adjustments | FY 2025 Request | 13-14 |
| 2026 | FY 2024 Actuals | FY 2025 Enacted | FY 2026 Request (+ Reconciliation, Total) | 13-14 |
| 2027 | FY 2025 Actuals | FY 2026 Discretionary Enacted (+ PL 119-21, Total) | FY 2027 Discretionary / Mandatory Request, Total | 19-20 |

Rules that follow from the table:

* An unlabeled FY N-2 column (e.g. "FY 2019 (Base + OCO)") is still the prior-year actual by position. The extracted tables record this as `prior_year_unlabeled` so you can tell printed labels from positional ones.
* In CR years (PB2012, 2014, 2018, 2019, 2025) the CY column is **not** an enacted amount. Use PB N+1's PY column for the final figure. PB2025 carries the note "A full-year FY 2024 appropriation for this account was not enacted at the time the budget was prepared ... reflect the annualized level provided by the continuing resolution" (pp. 9-11).
* PB2012 and PB2014 carry the note "Reflects the FY 20xx President's Budget with an undistributed adjustment to match the Annualized Continuing Resolution funding level".
* Base/OCO (PB2010-2021), Discretionary/Mandatory and Reconciliation (PB2026-2027) are sub-columns. Use the Total column when it exists.

## 3. Book inventory and exhibit page anchors (LI 2001)

Pages are 1-based PDF page numbers, as stored in `aircarrier_pdf_pages.page`. "-" means none was found, not that the exhibit doesn't exist.

| PB | artifact_id | file | pages | P-1 | P-40 | P-5 / P-5c | P-5b | P-27 | P-10 narrative |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2006 | a74c553062dd5476 | SCN_Bookpb2006.pdf | 183 | 4 | - | - | - | - | 12-13 |
| 2007 | d3b6d8bb4997e16e | SCN_Bookpb2007.pdf | 192 | 3 | - | - | - | - | 10-13 |
| 2008 | 327129143fe06b83 | SCN_Bookpb2008.pdf | 298 | 3 | 11 | 12 | 13 | 14 | 74-75 |
| 2009 | eaadf6094ef1c60c | SCN_Bookpb2009.pdf | 271 | 8 | 12 | 13 | 14 | 15 | 67-68 |
| 2010 | e5a485e49897b854 | SCN_Bookpb2010.pdf | 224 | 7 | 11 | 12 | 13 | 14 | 47-48 |
| 2011 | 49d99002d0a89acc | SCN_Bookpb2011.pdf | 224 | 9-10 | 17 | 18 | 19 | 20 | 51-52 |
| 2012 | 4d0800f702218e89 | SCN_Bookpb2012.pdf | 216 | 8-10 | 21 | 22 | 23 | 24 | 49-50 |
| 2013 | ba2628d2c2b5fc75 | SCN_Bookpb2013.pdf | 246 | 9-10 | 15 | 16 | 17 | 18 | - |
| 2014 | 7b5a586d6ffb270a | SCN_BOOKpb2014.pdf | 216 | 9-10 | 15 | 16 | 17 | 18 | - |
| 2015 | 860ca470dcc01c85 | SCN_Bookpb2015.pdf | 210 | 7 | 11 | 12 | 13 | 14 | - |
| 2016 | dcfe7661c9ed109d | SCN_Bookpb2016.pdf | 246 | 9-10 | 17 | 18 | 19 | 20 | 49-50 |
| 2017 | e7b07bfcdeb0ba6a | SCN_Bookpb2017.pdf | 296 | 11-12 | 25 | 27 | - | 28 | 59-60 |
| 2018 | 4ef754f30e96491e | SCN_Bookpb2018.pdf | 322 | 15-18 | 45 | 47-48 | - | 49 | - |
| 2019 | 37b391627588a4cb | SCN_Bookpb2019.pdf | 300 | 15-18 | 45 | 47 | - | 48 | - |
| 2020 | b37473bac9565e26 | SCN_Bookpb2020.pdf | 356 | 16-18 | 49 | 51 | - | 53 | - |
| 2021 | 3a148bf9c8ba1805 | SCN_Bookpb2021.pdf | 416 | 16-18 | 67 | 70 | - | 72 | - |
| 2022 | 9cfc2ec7d970ea12 | SCN_Bookpb2022.pdf | 390 | 10 | 51 | 53 | - | 55 | - |
| 2023 | 1ec0a996bf497f15 | SCN_Bookpb2023.pdf | 460 | 16-18 | 75 | 78 | - | 80 | - |
| 2024 | 0e22875425eafbd3 | SCN_BookPB2024.pdf | 466 | 12-13 | 71 | 73 | - | 75 | - |
| 2025 | fc826e7935d0668c | SCN_BookPB2025.pdf | 460 | 13-14 | 65 | 67-68 | - | 69 | - |
| 2026 | 9a61b0a5733e09c7 | SCN_BookPB2026.pdf | 440 | 13-14 | 73 | 75-76 | - | 77 | 115-116 |
| 2027 | bb2e90fd1d91a0bc | SCN_Book PB27.pdf | 504 | 19-20 | 93 | 95-96 | - | 97 | 133-134 |

PDFs: `/Volumes/users/xiaobing_shang1_civ/aircarrier_artifacts/<artifact_id>/<file>`.
OPEN: P-10 pages are the pages where P-10 narrative sentences were captured. The P-10 tables have not been parsed and may span more pages. P-8a and P-35 pages are not yet catalogued (PB27 p.103 is a P-35, 21x17 cells).

## 4. Exhibit catalog

### P-1 Procurement Program (front matter, all lines of the appropriation)
* **Answers:** what was requested, enacted and actual for each funding line of the item, in the same units for every line item.
* **Rows for the carrier item.** A numbered line item ("2/3/5 Carrier Replacement Program", later a separate "CVN-81" line) has these sub-rows:
  * gross "Carrier Replacement Program" (in parentheses) in the full-funding year
  * "Less: Advance Procurement (PY)" and "Less: Subsequent Full Funding (FY)"
  * the net line, below a dashed rule
  * "Subsequent Full Funding for FY yyyy"
  * "Completion PY Shipbuild for FY yyyy" (cost to complete)
  * "Advance Procurement (CY)", with memo lines "C (FY a for FY b) (M)" = AP appropriated in FY a for the ship funded in FY b
* **Columns:** Qty / Cost pairs for the three FY columns in section 2.
* **Units:** $M in PB2006-2009, $K ("Dollars in Thousands") from PB2010.
* **Parentheses:** gross, memo and "Less" amounts are non-add; only un-parenthesized amounts sum to the line.
* **Extracted:** `aircarrier_jb_p1_vintage`.
* **Caveat (tie-out):** the LI 2001 P-1 request column does not show cost-to-complete. The P-40 for the same year includes it (section 7).

### P-40 Budget Line Item Justification (resource summary)
* **Answers:** the funding stream of the whole line item (all hulls) by FY, from Prior Years to To Complete.
* **Rows, modern (PB2017+):** Quantity; Gross/Weapon System Cost; Less PY Advance Procurement; Less Subsequent Year Full Funding; Less Cost To Complete; Net Procurement (P-1); Plus CY Advance Procurement; Plus Subsequent Year Full Funding; Plus Cost To Complete; Total Obligation Authority; Full Funding TOA.
* **Rows, legacy only (PB2008-2016):** End Cost; Unit Cost; Plus Outfitting and Post Delivery; Total (incl. Outfitting/Post Delivery); Plus/Less Escalation (PB2008-2011); Transfer (PB2008-2009).
* **Columns:** Prior Years, then FY N-2 to FY N+4 (the BY split into Base/OCO/Total in PB2017-2021), To Complete, Total.
* **Narrative:** the description and justification text under the table (130 sentences captured, every book PB2008-2027).
* **Extracted:** `aircarrier_jb_p40_resource`, values normalized to $M.
* **Caveat:** the legacy End Cost row is the only CVN-79 cost estimate before PB2013 (e.g. PB2008 9,192.0).

### P-5 (PB2008-2016) / P-5c (PB2017+) Ship Cost Analysis
* **Answers:** the cost estimate of each hull by cost category, and how it is funded across years.
* **Columns:** one per hull, headed by the hull's full-funding FY (CVN-77 FY2001, CVN-78 FY2008, CVN-79 FY2013, CVN-80 FY2018, CVN-81 FY2020), with Qty / Total Cost.
* **Rows, cost side:** Plan Costs; Basic Construction/Conversion; Change Orders; Electronics; Propulsion Equipment; HM&E; Ordnance; Other Cost; Escalation (legacy PB2008-2015 only).
* **Rows, funding side:** Total Ship Estimate; Less Advance Procurement FY yyyy (one row per year); Less Subsequent Full Funding FY yyyy; Less Cost To Complete FY yyyy; Net P-1.
* **Remarks:** P-5c remarks explain each change against the prior book by category (51 sentences captured, PB2020-2027; legacy P-5 pages add 15 sentences, PB2008-2016). Example, PB2023 CVN-79: Basic +588.5, Change Orders +125.0, Ordnance +56.8.
* **Units:** $K in the legacy P-5 (rotated landscape pages, "BLI: 2001" header); $M in the P-5c.
* **Extracted:** `aircarrier_jb_ship_cost` (value_musd normalized) and `aircarrier_jb_funding_tranche`.
* **Tie rules:** the 8 categories sum to the Total Ship Estimate; Total Ship Estimate minus all "Less" rows = Net P-1.

### P-5b Analysis of Ship Cost Estimate - Basic Construction (PB2008-2016)
* **Answers:** contract type, award and delivery schedule, escalation basis, and shipbuilder.
* **Status:** captured as narrative only (17 sentences), not tabulated.

### P-27 Ship Production Schedule
* **Answers:** for each hull, the fiscal year, contract award, start of construction and delivery dates as planned in each book.
* **Columns:** Hull, FY, Contract Award, Start Construction, Delivery, footnote markers.
* **Extracted:** `aircarrier_jb_schedule` (51 rows).
* **Caveat:** PB2008 prints CVN-77 delivery with a century typo; it is corrected in the table and the printed line is kept in `source_line`.
* **Use:** a slip history per hull, e.g. CVN-79 delivery Sep 2019 (PB2008) to Mar 2027 (PB2026-2027).

### P-10 Advance Procurement Requirements Analysis
* **Answers:** what the AP buys (plans, nuclear propulsion, HM&E, long-lead components) and in which years, with lead times.
* **Status:** narrative captured (107 sentences); tables NOT yet parsed (OPEN).

### P-8a Major Equipment and P-35 Major Ship Component Fact Sheet
* **Answers:** government-furnished equipment (radar, combat systems, aircraft launch and recovery) by quantity and cost, plus contractor, award date and delivery for each component.
* **Pages (LI 2001, contiguous blocks):** P-8a and P-35 found in PB2008-2027, e.g. PB27 P-8a pp.98-102, P-35 pp.103-132. They were not found in PB2006-2007 by the header rule. CVN-68 RCOH pages are excluded.
* **P-8a layout:** sections Electronics / HM&E / Ordnance (legacy PB2008 adds Other), each split into P-35 Items, Major Items and Other Cost Elements, with subtotals and a Total per section; Qty / Cost per hull column. Units: $K through PB2016, $M from PB2017.
* **P-35 layout:** one fact sheet per equipment item: Equipment Item, PARM code, I. Description, II. Current Funding (P-35 categories such as Major Hardware, Technical Data and Documentation, Spares, System Engineering, Technical Engineering Services, Other Costs, Total, per hull), III. Contract Data, IV. Delivery Date.
* **Extracted (2026-11-10):** `aircarrier_jb_p8a_equipment` (5,081 rows), `aircarrier_jb_p35_funding` (7,691 rows), `aircarrier_jb_p35_contract` (928 rows: contractor, contract_type, award_date/award_ym, new_option, qty, unit_cost, unit_cost_musd, missing_fields, contractor_clipped, plus a check against the P-35 Major Hardware cost), `aircarrier_jb_p35_delivery` (928 rows: ship_delivery, months_before_delivery, production_leadtime, required_award, with _ym forms), `aircarrier_jb_p35_p8a_xcheck` (847 rows, one per P-35 total). The earlier `aircarrier_jb_p35_contract_delivery` table was replaced by these.
* **Contract column order:** PB2008 is contractor, type, qty, unit cost, award date. PB2009-2016 is contractor, type, award date, (new/option), qty, unit cost. PB2017+ uses the same order in $M. Contract type is accepted only when it matches a contract-type pattern (FFP, C/FFP, SS/FFP, CPFF, CPIF, T&M, WR, TBD, VARIOUS and similar); otherwise the cell is treated as blank. 35 rows have blank cells in the PDF text (`missing_fields`), mostly PB2009. 12 contractor names lose their first letter in the PDF text layer (`contractor_clipped`, e.g. "ultiple vendors").
* **Contract check:** qty x unit cost = P-35 Major Hardware for 797 of 801 rows where both exist. Differences in the printed values: PB2010 CVN-78 DBR (204.471 vs 181.471), PB2018/2019 CVN-80 EASR (56.000 vs 58.000), PB2024 CVN-79 CV-TSC (3.150 vs 2.924).
* **Delivery:** 921 / 928 rows split into 4 fields. The 7 remaining rows carry notes or have missing cells (e.g. "Multiple Deliveries", "(Note 1)").
* **P-35 label fix:** in PB2017+, the column header was fused to the first category row ("P-35 Category (Each) ($ M) ... Major Hardware"). This is fixed in `aircarrier_jb_p35_funding`.
* **Tie-outs:**
  * P-8a items = section Total: 116 / 116 (pb, hull, section).
  * P-8a section Total = P-5/P-5c category (Electronics, HM&E, Ordnance): 114 / 114 matched.
  * P-35 categories = P-35 Total: 846 / 847. Exception: PB2009 CVN-77 AN/SQQ-34 TIS upgrade.
  * P-35 Total = P-8a item cost (matched by normalized name): 721 of 721 name-matched P-35 totals equal a P-8a row; 126 P-35 totals have no P-8a name match (42 of them in PB2008; naming differences, not reviewed). The earlier "41 mismatches" were not mismatches. In 41 cases an item name appears twice in the P-8a for the same hull: one row is 0 and the other equals the P-35 total. The usual case is an item shown at zero under P-35 Items and funded under Major Items, or the reverse. Matching took the first row, which made 762 joined rows look like 721 equal plus 41 unequal.
* **Extraction fixes applied:** dropped footer tokens ("Volume n", "Page n of"), hull header lines ("CVN 77 CVN 78", "SHIP TYPE: CVN"), and footnote text that contained hull numbers.

## 5. Funding-line vocabulary and ship-year to hull map

| Term | Meaning |
| --- | --- |
| AP / Advance Procurement (CY) | Long-lead funds appropriated before the full-funding year. A memo "C (FY a for FY b)" says which ship (FY b) it buys for |
| Full funding (FY) | The year the ship is funded. Gross cost less prior AP less planned SFF = the net P-1 amount in that year |
| SFF / Subsequent Full Funding | Carriers are incrementally funded (split funding); later-year increments for the same ship |
| CTC / Cost To Complete / Completion of PY Shipbuilding | Funds added after the funding plan closed, to cover cost growth on a ship already funded |
| Total Ship Estimate | The end cost of one hull in that book (the sum of all funding rows) |
| Net P-1 | What the P-1 shows for the hull in its full-funding year |

Ship FY to hull: FY2001 CVN-77, FY2008 CVN-78, FY2013 CVN-79, FY2018 CVN-80, FY2020 CVN-81.
The P-1 lines "Subsequent Full Funding for FY 2018" and "Completion PY Shipbuild for FY 2013" therefore mean CVN-80 SFF and CVN-79 CTC respectively.
Legacy P-1 rows without "for FY yyyy" are attributed by year (`hull_inferred = true`):
* SFF in FY2009-2011 = CVN-78; SFF in FY2014-2016 = CVN-79
* CTC in FY2009 = CVN-77; CTC in FY2014-2015 = CVN-78

INFERENCE / OPEN: the AP memo lines in PB2026 ("FY 2026 for FY 2030") and PB2027 ("FY 2027 for FY 2029") name different target years. The hull (CVN-82 or later) is not assigned until the P-27 confirms it.

Treasury account: funds appropriated in FY a are carried on SCN account 017-a/(a+4)-1611 (5-year availability). The column `scn_tas_derived` in `aircarrier_jb_funding_tranche` is built from this rule; it is not printed in the books.

## 6. Format eras

| Era | Books | Characteristics |
| --- | --- | --- |
| Legacy A | PB2006-2007 | P-1 + P-10 only for LI 2001 (CVN-78 still in AP); no P-40/P-5 found |
| Legacy B | PB2008-2016 | "BLI: 2001" headers, P-5 (not P-5c) in $K on rotated pages, P-5b present, P-40 with End Cost/Unit Cost/Outfitting rows; P-1 in $M through PB2009 |
| Modern | PB2017-2027 | Exhibit P-40 / P-5c / P-27 with "Exhibit P-xx" headers, $M, Base/OCO split through PB2021, then Request/Enacted/Actuals labels; PB2026-2027 add Reconciliation / Mandatory columns |

Parsing notes:
* The pdfplumber store text splits digits on some legacy pages (PB2008 p.12 "3 ,806,071"). The jb_* tables were extracted from PyMuPDF word coordinates instead, with page rotation applied, and keep the `printed` string for audit.
* The docs-server labeler `structure.py` does not recognize the legacy headers ("BLI:", "(P-40)", "P-8A EXHIBIT") or the PB2018 exhibit line. A prototype fix exists but is not yet in the server code.

## 7. Tie-outs and what they prove

| Check | Result (2026-11-10) |
| --- | --- |
| P-5/P-5c: Total Ship Estimate - Less rows = Net P-1 | passes in every hull column, 20 books |
| P-5/P-5c: 8 categories = Total Ship Estimate | passes except 4 legacy columns off by 1 $K (source rounding): PB2008, 2009, 2010 CVN-77 and PB2016 CVN-79 |
| P-40 column arithmetic | 535 / 560; the 25 failures are in legacy PB2008-2013 |
| P-1 carrier lines summed vs P-40 TOA, same book and FY | 44 / 60 within 0.1 $M; misses mostly equal the CTC amount (588.1, 663.0, 291.0, 461.7, 624.6, 236.0, 150.0); unexplained: 643.0 (PB2021 FY2019) and 71.0 (FY2021, PB2021-2023) |
| Remarks vs numbers | PB2026 states a FY2024 congressional reduction of 10.875 for JPALS on CVN-80, which equals the triangle's FY2024 actual-minus-enacted (1,104.421 - 1,115.296) |
| Known answers | PB2027 CVN-79 TSE 13,409.970 and Net P-1 490.952; PB2026 13,195.970; PB2025 12,935.970; PB2013 11,411.0 matches CRS RS20643 p.14 |

## 8. Unity Catalog tables (schema users.xiaobing_shang1_civ)

| Table | Grain | Key columns |
| --- | --- | --- |
| aircarrier_pdf_pages / _tables / _cells | page / table / cell of all 33 stored documents | artifact_id, page, table_id, extractor |
| aircarrier_jb_p1_vintage | (pb, fy, funding line, ship FY), one value | pb, page, row, column (printed), role, role_printed, part, fy, line (SFF, CTC, AP_CY, AP_MEMO, FULL_FUNDING_NET/GROSS), ship_fy, hull, hull_inferred, printed, musd, stage |
| aircarrier_jb_funding_triangle | (line, ship FY, FY) | request, current_year, prior_year, cong_delta_cy_vs_req, delta_py_vs_cy |
| aircarrier_jb_p40_resource | (pb, row, column) | row, column, printed, value_musd, column_ties, tie_residuals |
| aircarrier_jb_ship_cost | (pb, hull, category, tranche FY) | funding_fy, category, tranche_fy, printed, unit, value_musd, net_p1_ties, categories_tie |
| aircarrier_jb_funding_tranche | (pb, hull, tranche type, appropriation FY) | value_musd, scn_tas_derived |
| aircarrier_jb_schedule | (pb, hull) | fiscal_year, contract_award, start_construction, delivery, footnotes, source_line |
| aircarrier_jb_narrative | sentence | exhibit, hulls, hull_inherited, tags, amounts, text |

Every jb_* row carries artifact_id (or pb) + page, so any number can be opened in the PDF.

## 9. Joining J-book money to execution data

1. Pick the hull and funding slice in `aircarrier_jb_funding_tranche` (e.g. CVN-79 SFF FY2018 = 2,556.384 in PB2027).
2. Derive the account: 017-2018/2022-1611.
3. Match File C (`aircarrier_src_2114_federal_account_funding.treasury_account_symbol`). For contract N00024-15-C-2114 that account shows $1,627,004,167.80 obligated in the File C window.
4. The difference is unobligated balance, other contracts (GFE, planning yard) or timing. This is a lead, not a proof, until matched to the ledger.

Other accounts in that File C (1319 RDT&E, 1804 O&M,N, 0400 DoD-wide) are outside the SCN J-book and need their own budget books.

## 10. Extending to CVN-80, CVN-81 and other programs

* CVN-80 and CVN-81 are already in the P-1, P-40, P-5c, P-27 and triangle tables: filter `hull`.
* For another SCN line item: change the line-item filter in the P-1 parser (the `CARRIER` regex) and the LI page labeling, then run the same tie-outs. The column-role logic in section 2 is appropriation-wide and does not change.
* Gaps to close for full cost capture: P-10 tables, the CTC request line outside LI 2001, and the 643.0 / 71.0 residuals.

## 11. Open items

* OPEN-1: find where CTC requests are budgeted in the P-1 (likely another line item; unverified).
* OPEN-2: explain the PB2021 FY2019 643.0 and the FY2021 71.0 P-1 vs P-40 residuals.
* OPEN-3: parse the P-10 tables. P-8a/P-35 are done, including the contract/delivery field split and the 41-row review. Still open: 126 P-35 totals with no P-8a name match, the 4 printed qty x unit cost differences, and coverage of PB2006-2007.
* OPEN-4: the extraction ran as ad hoc session code. Save it as a rerunnable notebook and gate it on the checks in section 7.
* OPEN-5: merge the legacy-header labeler fix into the docs server `structure.py`, and update the store notebook gate (lines == 700 must become 4,856).
