cat5 = {
 "Plan Costs":898.865,"Basic Construction/Conversion":8463.156,"Change Orders":432.065,
 "Electronics (†)":263.359,"Propulsion Equipment":2041.582,"Hull, Mechanical, and Electrical (†)":30.302,
 "Ordnance (†)":1149.651,"Other Cost":130.990}
TOT=13409.970
ap={2007:52.750,2008:123.530,2009:1210.561,2010:482.938,2011:902.473,2012:554.798}
sff={2014:917.553,2015:1219.405,2016:1569.543,2017:1241.783,2018:2556.384}
ctc={2022:291.000,2023:461.700,2024:624.600,2025:236.000,2026:150.000,2027:324.000}
net=490.952
print("="*74); print("CVN-79 P-5c, PB2027, FY2013 column. ALL VERIFIED PRIMARY."); print("="*74)
s=0
for k,v in cat5.items():
    s+=v; print(f"  {k:<42}{v:>12,.3f}{v/TOT*100:>8.1f}%")
print(f"  {'computed sum':<42}{s:>12,.3f}")
print(f"  {'published Total Ship Estimate':<42}{TOT:>12,.3f}   residual {TOT-s:+.3f}")
A,F,C=sum(ap.values()),sum(sff.values()),sum(ctc.values())
print(f"\n  {'Advance Procurement FY2007-FY2012':<42}{A:>12,.3f}{A/TOT*100:>8.1f}%")
print(f"  {'Subsequent Full Funding FY2014-FY2018':<42}{F:>12,.3f}{F/TOT*100:>8.1f}%")
print(f"  {'Cost to Complete FY2022-FY2027':<42}{C:>12,.3f}{C/TOT*100:>8.1f}%")
print(f"  {'Net P-1 Funding (residual year)':<42}{net:>12,.3f}{net/TOT*100:>8.1f}%")
print(f"  {'funding streams sum':<42}{A+F+C+net:>12,.3f}   residual vs total {TOT-(A+F+C+net):+.3f}")
print("\n  AP by year:   "+"  ".join(f"FY{y} {v:,.1f}" for y,v in sorted(ap.items())))
print("  SFF by year:  "+"  ".join(f"FY{y} {v:,.1f}" for y,v in sorted(sff.items())))
print("  CTC by year:  "+"  ".join(f"FY{y} {v:,.1f}" for y,v in sorted(ctc.items())))
pb26=13196.0
print(f"\n  PB2026 total {pb26:,.1f} -> PB2027 total {TOT:,.3f} = {TOT-pb26:+,.3f}  (book states '$214M')")
print(f"  of which Basic Construction +187.6 and Change Orders +19.3 = {187.6+19.3:+,.1f}; realignments "
      f"Elec 3.582 Prop 7.000 HM&E 0.317 Other 0.745 Ord 2.601")
cap=11398.0
print(f"\n  above statutory cap: {TOT-cap:+,.3f}  ({(TOT-cap)/cap*100:.1f}%)")
# GFE-bearing categories, per the P-40 Systems list
ord_sys="EMALS + EASR + AAG + MOVLAS"; ele_sys="SSDS"
gfe=cat5["Ordnance (†)"]+cat5["Electronics (†)"]+cat5["Propulsion Equipment"]+cat5["Hull, Mechanical, and Electrical (†)"]
sb=cat5["Plan Costs"]+cat5["Basic Construction/Conversion"]+cat5["Change Orders"]+cat5["Other Cost"]
print(f"\n  Ordnance category contains: {ord_sys}")
print(f"  Electronics category contains: {ele_sys}")
print(f"  {'GFE-bearing categories':<42}{gfe:>12,.3f}{gfe/TOT*100:>8.1f}%")
print(f"  {'Shipbuilder-side categories':<42}{sb:>12,.3f}{sb/TOT*100:>8.1f}%")
# reconcile to the actual obligated DD&C contract
ddc_obl=4584.484; ddc_val=4615.796
print(f"\n  DD&C N00024-15-C-2114 obligated, award-level total (USAspending award record, 2026-07-20): {ddc_obl:,.3f}")
# The transaction sum differs (finding F8); quote one with its basis, never interchangeably.
ddc_txn=4578.603  # sum of 927 prime transactions, $4,578,603,345.77
print(f"  DD&C N00024-15-C-2114 obligated, sum of 927 transactions (USAspending):          {ddc_txn:,.3f}")
print(f"  -> award-level minus transaction sum: {ddc_obl-ddc_txn:,.3f} $M; quote the basis with each figure")
print(f"  DD&C current/potential total value:                        {ddc_val:,.3f}")
print(f"  Basic Construction + Change Orders + Plan:                 {cat5['Basic Construction/Conversion']+cat5['Change Orders']+cat5['Plan Costs']:,.3f}")
print(f"  -> DD&C obligations are {ddc_obl/(cat5['Basic Construction/Conversion']+cat5['Change Orders']+cat5['Plan Costs'])*100:.1f}% of the shipbuilder-side budget categories")
print(f"  -> and {ddc_obl/TOT*100:.1f}% of the whole hull")
