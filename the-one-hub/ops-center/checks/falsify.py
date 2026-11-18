# FALSIFICATION TEST on the Iteration 2 premise.
# The captured P-5 columns were assumed to be Ford-class hulls. Test that assumption
# against the surrounding text in the same extracts.
tells = [
 ("'Less AP Transfer to NSBDF FY2017-FY2023' lines in the same column block",
  "NSBDF = National Sea-Based Deterrence Fund. Statutory purpose is SSBN construction, not carriers."),
 ("'Large Aperture Bow (LAB) array hydrophones' in the same page extract",
  "LAB array is a submarine bow sonar. Carriers do not carry one."),
 ("'AN/WSQ-9 signal analysis system', 'Low Cost Conformal Array'",
  "Submarine acoustic systems."),
 ("'Advanced Carbon Dioxide Removal Unit (ACRU) ... will be the system for COLUMBIA Class Submarines'",
  "Explicit Columbia-class reference in the same extract."),
 ("'Less Subsequent Full Funding FY 2025 = 3,341.235'",
  "Matches Columbia incremental full funding scale, not a carrier CTC line."),
]
print("="*78); print("FALSIFICATION — are the captured P-5 columns carrier columns?"); print("="*78)
for t,why in tells:
    print(f"\n  TELL: {t}\n     -> {why}")
print("\n  VERDICT: the captured columns are COLUMBIA-class (SSBN-826) columns, not")
print("  Ford-class. Iteration 2's magnitudes and category mix are REJECTED.")
print("  The P-5 *row structure* is still valid: it is the same exhibit format on every")
print("  SCN line. Only the numbers were wrong, and they were wrong by platform.\n")

print("  Consequence: any carrier category mix I derive from them would have carried")
print("  submarine proportions (65% basic construction, 19% propulsion) into a carrier")
print("  estimate. That is the exact failure mode the trust rules exist to prevent:")
print("  right structure, wrong population, plausible-looking output.\n")

# What carrier-specific category evidence actually survives?
print("="*78); print("CARRIER-SPECIFIC category evidence that survives"); print("="*78)
surv = [
 ("FY2017 SCN P-5, carrier line: 'Propulsion Equipment  1,515.612 | 2,044.582'",
  "Two carrier columns. Establishes carrier propulsion equipment in the 1.5-2.0B band.", "VERIFIED-STRUCTURE", 0.70),
 ("FY2017 SCN P-10, carrier line: 'NUCLEAR PROPULSION PLANT EQUIPMENT  30-72  1,700.900'",
  "Carrier nuclear propulsion plant equipment, lead time 30-72 months.", "VERIFIED", 0.80),
 ("FY2017 SCN P-10, carrier line: 'ELECTRONICS EQUIPMENT  37-43  10.600 / 24.700'",
  "AP-year electronics increments, not a total.", "VERIFIED", 0.75),
 ("FY2007 SCN carrier element-of-cost: PROPULSION 96.203, ELECTRONICS 186.756, ORDNANCE 66.469",
  "AP-year increments in that budget year only.", "VERIFIED", 0.75),
 ("CVN-79 AP by FY (FY2017 book, CVN-79 column): FY08 123.530, FY10 482.938, FY11 902.473, FY12 554.798",
  "Partial AP series for this hull.", "VERIFIED", 0.85),
 ("FY2017 book 'Less PY Advance Procurement ... 2,233.142'",
  "Plausibly CVN-79 total prior-year AP. Column attribution not proven.", "UNVERIFIED", 0.45),
]
for a,b,t,c in surv:
    print(f"\n  [{t}] c={c:.2f}\n    {a}\n    -> {b}")
