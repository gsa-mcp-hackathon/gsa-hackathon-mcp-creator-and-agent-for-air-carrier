#!/usr/bin/env python3
"""
CVN-79 cost reconciliation, iteration 3.
Supersedes recon.py / recon2.py / final.py.

Trigger: user-supplied USAspending prime-award summaries showing
N0002409C2116 obligated $4,519,300,323.83 -- roughly 4x the figure the
earlier iterations carried, which had been built by summing ANNOUNCED
DoD contract modifications rather than the obligation record.

All inputs below are VERIFIED from one of:
  [P5c]  SCN_Book PB27.pdf, Exhibit P-5c, 1611N / BA02 / LI 2001, FY2013 column
  [USA]  USAspending bulk downloads in ring0/reference/ (2026-11-08)
  [MSAR] CVN 78 MSAR (FY2027 PB, April 21 2026) contract tables
"""

# ---------------------------------------------------------------- [P5c]
P5C = {
    "Plan Costs":                      898.865,
    "Basic Construction/Conversion":  8463.156,
    "Change Orders":                   432.065,
    "Electronics":                     263.359,
    "Propulsion Equipment":           2041.582,
    "HM&E":                             30.302,
    "Ordnance":                       1149.651,
    "Other Cost":                      130.990,
}
TOTAL_SHIP_ESTIMATE = 13409.970

# Categories the SHIPBUILDER is paid out of (construction-contract scope)
SHIPBUILDER_SIDE = ["Plan Costs", "Basic Construction/Conversion",
                    "Change Orders", "Other Cost"]
# Categories that are government-furnished equipment lines
GFE_SIDE = ["Electronics", "Propulsion Equipment", "HM&E", "Ordnance"]

# ---------------------------------------------------------------- [USA]
OBL_2116 = 4519300323.83 / 1e6     # CVN 79 Construction Preparation
OBL_2114 = 4578603345.77 / 1e6     # CVN 79 Detail Design & Construction
VAL_2116 = 5386149876.01 / 1e6     # current = potential total value of award
VAL_2114 = 4615795653.36 / 1e6
OUT_2116 =   72620471.18 / 1e6     # reported outlays
OUT_2114 =          0.00 / 1e6

# Scope carved out of 2116 by transaction-description keyword [USA]
NONNUC_PROP_2116 = 398509353.00 / 1e6   # "CVN79 NON NUCLEAR PROPULSION PLANT"

# Non-SCN share observed on 2114's linked federal-account rows [USA]
NONSCN_SHARE_2114 = 0.0188   # 017-1319 RDT&E,N + 017-1804 O&M,N + 097-0400

def line(c="-", n=78): print(c * n)
def pct(x, y): return f"{100.0*x/y:6.2f}%"

print("=" * 78)
print("CVN-79 RECONCILIATION v3 -- corrected for true 2116 obligations")
print("=" * 78)

sb = sum(P5C[k] for k in SHIPBUILDER_SIDE)
gfe = sum(P5C[k] for k in GFE_SIDE)
print(f"\nP-5c Total Ship Estimate                  {TOTAL_SHIP_ESTIMATE:12,.3f}")
print(f"  category sum check                      {sum(P5C.values()):12,.3f}"
      f"   residual {TOTAL_SHIP_ESTIMATE-sum(P5C.values()):+.3f}")
print(f"  shipbuilder-side categories             {sb:12,.3f}  {pct(sb,TOTAL_SHIP_ESTIMATE)}")
print(f"  GFE-side categories                     {gfe:12,.3f}  {pct(gfe,TOTAL_SHIP_ESTIMATE)}")

line()
print("ITERATION 3a -- the two HII prime contracts, at face value")
line()
both = OBL_2116 + OBL_2114
print(f"  N00024-09-C-2116  CP    obligated      {OBL_2116:12,.3f}")
print(f"  N00024-15-C-2114  DD&C  obligated      {OBL_2114:12,.3f}")
print(f"  combined                                {both:12,.3f}")
print(f"    share of Total Ship Estimate                        {pct(both,TOTAL_SHIP_ESTIMATE)}")
print(f"    share of shipbuilder-side categories                {pct(both,sb)}")
print(f"  residual, shipbuilder-side less HII     {sb-both:12,.3f}")
print(f"  unobligated ceiling still on the two    "
      f"{(VAL_2116-OBL_2116)+(VAL_2114-OBL_2114):12,.3f}")

line()
print("ITERATION 3b -- move non-nuclear propulsion plant to its budget home")
line()
sb_hii = both - NONNUC_PROP_2116
print(f"  2116 'NON NUCLEAR PROPULSION PLANT'     {NONNUC_PROP_2116:12,.3f}"
      f"   -> Propulsion Equipment")
print(f"  HII money against shipbuilder-side      {sb_hii:12,.3f}  {pct(sb_hii,sb)}")
print(f"  residual, shipbuilder-side less HII     {sb-sb_hii:12,.3f}")
print(f"  Propulsion Equipment explained by 2116                {pct(NONNUC_PROP_2116,P5C['Propulsion Equipment'])}")
print(f"  Propulsion Equipment still unexplained  "
      f"{P5C['Propulsion Equipment']-NONNUC_PROP_2116:12,.3f}   (nuclear plant, NR-furnished)")

line()
print("ITERATION 3c -- strip the non-SCN slice (only SCN is inside the 13.4B)")
line()
adj = sb_hii * (1 - NONSCN_SHARE_2114)
print(f"  non-SCN share applied (from 2114 File C)        {NONSCN_SHARE_2114:.4f}")
print(f"  SCN-only HII, shipbuilder-side          {adj:12,.3f}  {pct(adj,sb)}")
print(f"  residual for govt plan/engineering      {sb-adj:12,.3f}")

line()
print("WHAT THE EARLIER ITERATIONS GOT WRONG")
line()
OLD_2116 = 1080.0   # sum of ANNOUNCED DoD contract modifications
print(f"  2116 as previously carried (announced mods) {OLD_2116:12,.3f}")
print(f"  2116 actual obligations                     {OBL_2116:12,.3f}")
print(f"  understatement                              {OBL_2116-OLD_2116:12,.3f}"
      f"   ({OBL_2116/OLD_2116:.2f}x)")
old_both = OLD_2116 + OBL_2114
print(f"  old combined / old share of hull            {old_both:12,.3f}  {pct(old_both,TOTAL_SHIP_ESTIMATE)}")
print(f"  new combined / new share of hull            {both:12,.3f}  {pct(both,TOTAL_SHIP_ESTIMATE)}")

line()
print("OUTLAY LINKAGE -- why USAspending cannot measure CVN-79 disbursements")
line()
print(f"  2116  obligated {OBL_2116:10,.1f}   outlayed {OUT_2116:8,.1f}   {pct(OUT_2116,OBL_2116)}")
print(f"  2114  obligated {OBL_2114:10,.1f}   outlayed {OUT_2114:8,.1f}   {pct(OUT_2114,OBL_2114) if OBL_2114 else 'n/a'}")
print(f"  combined                                    outlay coverage "
      f"{pct(OUT_2116+OUT_2114, both)}")
print("  -> obligations are usable; outlays are not. File C award-level")
print("     linkage is the public face of the FBwT / GPIPC weakness.")

line()
print("CLOSING THE HULL -- every dollar of the 13,409.970")
line()
rows = [
    ("HII N00024-09-C-2116 (CP), less non-nuc prop",
     OBL_2116 - NONNUC_PROP_2116, "VERIFIED", 0.95),
    ("HII N00024-15-C-2114 (DD&C)", OBL_2114, "VERIFIED", 0.95),
    ("Non-nuclear propulsion plant, via 2116", NONNUC_PROP_2116, "VERIFIED", 0.90),
    ("GA EMALS shipset, N00019-14-C-0037 [P-8a]", 611.307, "VERIFIED", 0.95),
    ("GA AAG shipset, N00019-14-C-0037 [P-8a]", 219.131, "VERIFIED", 0.95),
    ("Raytheon equipment lines [P-8a]", 110.075, "VERIFIED", 0.90),
    ("Lockheed Martin equipment lines [P-8a]", 60.675, "VERIFIED", 0.90),
    ("Other named-vendor equipment lines [P-8a]", 58.500, "VERIFIED", 0.85),
]
acc = 0.0
print(f"  {'component':48s}{'$M':>11}  {'tag':9s} conf")
for name, amt, tag, conf in rows:
    acc += amt
    print(f"  {name:48s}{amt:11,.3f}  {tag:9s} {conf:.2f}")
print(f"  {'-'*48}{'-'*11}")
print(f"  {'subtotal accounted':48s}{acc:11,.3f}  {pct(acc,TOTAL_SHIP_ESTIMATE)}")
resid = TOTAL_SHIP_ESTIMATE - acc
print(f"  {'UNATTRIBUTED RESIDUAL':48s}{resid:11,.3f}  {pct(resid,TOTAL_SHIP_ESTIMATE)}")

print("\n  residual must contain, in rough order of size:")
for n, v in [("nuclear propulsion plant (Naval Reactors furnished)", "~1,643 max"),
             ("Ordnance less EMALS/AAG/EASR already counted", "~ 209"),
             ("govt plan costs: NAVSEA/NSWC/planning yard/SUPSHIP", "~ 500-830"),
             ("Electronics less SSDS/EASR lines counted", "~ 150"),
             ("unobligated ceiling + cost-to-complete FY26-27", "~ 474")]:
    print(f"    - {n:54s} {v:>12}")
print("\n  NOTE: residual is NOT a gap in the budget. It is the part of the")
print("  hull that no public contract-level record attributes to CVN-79.")
