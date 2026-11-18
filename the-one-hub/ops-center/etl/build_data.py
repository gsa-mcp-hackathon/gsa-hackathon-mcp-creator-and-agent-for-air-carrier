#!/usr/bin/env python3
"""Build the front-center data bundle.

Two sources:
  1. The Ring 0 dossier, Parts A through N. Hand-transcribed tables whose home
     is ../../ring0/RING0_CVN79.md. Every figure here is already VERIFIED there
     against a primary document, and each entry carries its source.
  2. The USAspending bundles in ../../ring0/reference/, computed live. 1,875
     prime transactions, 2,990 sub-awards, 39 federal account funding rows.

Output: app/data/*.json. In production the same shapes come from Unity Catalog
through app/api/data.py; the JSON backend is what makes the app runnable with
no workspace at all, which is the graceful-degradation requirement (D11)
applied to the front end.

    python3 etl/build_data.py
"""
import csv
import collections
import json
import pathlib
import re
import zipfile
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
REF = ROOT.parent / "ring0" / "reference"
OUT = ROOT / "app" / "data"
OUT.mkdir(parents=True, exist_ok=True)

SRC_N = "ring0/RING0_CVN79.md Part N"
SRC_A = "ring0/RING0_CVN79.md Part A"
TOTAL = 13409.970


def num(x):
    try:
        return float(x) if x not in ("", "None", None) else 0.0
    except Exception:
        return 0.0


def write(name, obj):
    p = OUT / f"{name}.json"
    p.write_text(json.dumps(obj, indent=1))
    print(f"  {name:<22} {p.stat().st_size:>8,} bytes")


# ----------------------------------------------------------------- CSV inputs
def load_zips():
    tmp = pathlib.Path(tempfile.mkdtemp())
    for z in REF.glob("*.zip"):
        with zipfile.ZipFile(z) as zf:
            zf.extractall(tmp / z.stem)
    out = {}
    for p in tmp.rglob("*.csv"):
        out[p.name] = list(csv.DictReader(p.open(newline="", encoding="utf-8-sig")))
    return out


# In the workspace, ring0/reference does not exist (corpus binaries are excluded
# from bundle sync) and the two USAspending ZIPs were removed from the corpus
# volume on 2026-11-08 because every member is byte-identical to a loose CSV
# already there. Without this fallback the contract section summed nothing and
# died on a zero division at the outlay coverage line, so no data JSON could
# be rebuilt outside a local checkout. The loose CSVs are read through the
# volume's MANIFEST.json, which is the content-addressed catalogue of record.
CORPUS_VOLUME = pathlib.Path(
    __import__("os").environ.get(
        "AIRCARRIER_CORPUS_VOLUME",
        "/Volumes/users/xiaobing_shang1_civ/aircarrier_artifacts"))


def load_volume_csvs():
    man = CORPUS_VOLUME / "MANIFEST.json"
    if not man.exists():
        return {}
    m = json.loads(man.read_text())
    out = {}
    for r in m.get("rows", []):
        if not r["path"].lower().endswith(".csv"):
            continue
        name = pathlib.PurePosixPath(r["path"]).name
        hits = list((CORPUS_VOLUME / r["artifact_id"]).glob("*.csv"))
        if hits:
            out[name] = list(csv.DictReader(
                hits[0].open(newline="", encoding="utf-8-sig")))
    return out


CSV = load_zips() or load_volume_csvs()
if not CSV:
    raise SystemExit("no USAspending inputs: neither ring0/reference/*.zip nor "
                     f"{CORPUS_VOLUME}/MANIFEST.json is readable")


def pick(frag):
    for k, v in CSV.items():
        if frag.lower() in k.lower() and v:
            return v
    return []


tx_2114 = pick("Contract_N0002415C2114_TransactionHistory")
tx_2116 = pick("Contracts_PrimeTransactions")
faf = pick("FederalAccountFunding")
subs = pick("Sub-Awards")

print(f"inputs: 2114 tx {len(tx_2114)}  2116 tx {len(tx_2116)}  "
      f"faf {len(faf)}  subawards {len(subs)}")

# ------------------------------------------------------- 1. program identity
write("program", {
    "hull": "CVN-79", "name": "USS John F. Kennedy",
    "pre_delivery": "PCU John F. Kennedy",
    "ship_class": "Gerald R. Ford class (CVN 78)",
    "program": "CVN 78 Gerald R. Ford Class Nuclear Aircraft Carrier",
    "acat": "IC", "program_office": "PEO Aircraft Carriers",
    "builder": "HII Newport News Shipbuilding", "cage": "43689",
    "district": "VA-03", "motto": "Serve with courage",
    "sponsor": "Caroline Kennedy",
    "service_life_years": 50,
    "total_ship_estimate_usd_m": TOTAL,
    "total_source": "PB2027 SCN Book, Exhibit P-5c, 1611N/02/2001, FY2013 column",
    "statutory_cap_usd_m": 11398.0,
    "cost_limitation_baseline_usd_m": 12936.0,
    "above_cap_usd_m": round(TOTAL - 11398.0, 3),
    "above_cap_pct": round((TOTAL - 11398.0) / 11398.0 * 100, 1),
    "delivery": "March 2027", "cfo": "July 2027", "owld": "June 2028",
    "preliminary_acceptance": "29 September 2026",
    "schedule_variance_months": 54,
    "industrial_base": {"supplier_firms": 2000, "states": 46,
                        "nns_employees": 25000, "source": "CRS RS20643, 2019 basis"},
    "source": SRC_A,
})

# ------------------------------------------------------------- 2. timeline
write("timeline", [
 {"date": "2004-05", "y": 2004, "event": "Construction Preparation contract awarded (CVN 21 era)", "kind": "contract", "src": "FY2027 MSAR"},
 {"date": "2007", "y": 2007, "event": "First CVN-79-specific advance procurement increment, $52.750M", "kind": "funding", "src": "PB2027 P-5c"},
 {"date": "2008-08", "y": 2008, "event": "USD(AT&L) DAB authorizes CVN-79 construction preparation phase", "kind": "milestone", "src": "FY2022 SAR"},
 {"date": "2009-01-15", "y": 2009, "event": "Construction Preparation contract N00024-09-C-2116 awarded, $111,803,875 base", "kind": "contract", "src": "USAspending; FY2023 MSAR"},
 {"date": "2011-05-29", "y": 2011, "event": "Named John F. Kennedy by SECNAV Ray Mabus", "kind": "milestone", "src": "CRS RS20643"},
 {"date": "2013-03", "y": 2013, "event": "Construction Preparation contract extended through FY2013", "kind": "contract", "src": "FY2023 MSAR"},
 {"date": "2013", "y": 2013, "event": "Procurement year. Authorization moved FY2012 to FY2013. Procurement year carried only 3.7% of the ship", "kind": "funding", "src": "CRS RS20643; PB2027 P-5c"},
 {"date": "2015-06-05", "y": 2015, "event": "Detail Design & Construction contract N00024-15-C-2114 awarded, $3,352,611,760 FPIF target", "kind": "contract", "src": "HII release"},
 {"date": "2015-08-22", "y": 2015, "event": "Keel laid", "kind": "milestone", "src": "Naval Vessel Register"},
 {"date": "2017-06", "y": 2017, "event": "50% structurally erected, 224 of 447 erectables landed", "kind": "progress", "src": "FY2023 MSAR"},
 {"date": "2018-04", "y": 2018, "event": "75% structurally erected, 341 of 447 erectables landed", "kind": "progress", "src": "FY2023 MSAR"},
 {"date": "2019-10-01", "y": 2019, "event": "Crew activated as Pre-Commissioning Unit", "kind": "milestone", "src": "seaforces"},
 {"date": "2019-10-29", "y": 2019, "event": "Dry dock flooded, ship launched", "kind": "milestone", "src": "NavSource"},
 {"date": "2019-12-07", "y": 2019, "event": "Christened by Caroline Kennedy", "kind": "milestone", "src": "NavSource"},
 {"date": "2019-12-20", "y": 2019, "event": "FY2020 NDAA Sec. 124 mandates F-35C capability before PSA completion", "kind": "statute", "src": "CRS RS20643"},
 {"date": "2020-11", "y": 2020, "event": "NTE $284,285,022 FPIF mod for single-phase delivery and JSF work", "kind": "contract", "src": "HigherGov"},
 {"date": "2021-08", "y": 2021, "event": "Navy raises cost baseline $1.3B to ~$12.7B, primarily contract overruns. Ship over 88% complete", "kind": "cost", "src": "GAO via CRS RS20643"},
 {"date": "2023-06-23", "y": 2023, "event": "$393.3M in mods shift PSA work into baseline construction. Delivery reset to 31 Jul 2025", "kind": "cost", "src": "HII release"},
 {"date": "2023-08", "y": 2023, "event": "SECNAV notifies Congress of Cost Limitation Baseline rise to $12.936B", "kind": "cost", "src": "FY2023 MSAR"},
 {"date": "2023-12", "y": 2023, "event": "Ship 91% complete. DD&C contract 81.3% complete by dollars", "kind": "progress", "src": "FY2023 MSAR"},
 {"date": "2024-09", "y": 2024, "event": "Faulty welds disclosed at NNS, referred to DOJ. HASC opens investigation. 26 ships affected", "kind": "risk", "src": "USNI; Military.com"},
 {"date": "2025-04-08", "y": 2025, "event": "PEO Carriers tells SASC Seapower the ship is 95% complete", "kind": "progress", "src": "USNI; Inside Defense"},
 {"date": "2025-07", "y": 2025, "event": "FY2026 books move delivery from July 2025 to March 2027", "kind": "schedule", "src": "CRS RS20643"},
 {"date": "2025-11-21", "y": 2025, "event": "Four-part mod across both contracts, $142.9M, including FMS Canada and USMC RDT&E", "kind": "contract", "src": "DoW announcement"},
 {"date": "2026-01-28", "y": 2026, "event": "Builder's trials begin, first time underway", "kind": "milestone", "src": "USNI"},
 {"date": "2026-02-04", "y": 2026, "event": "Returns from builder's trials, eight days at sea", "kind": "milestone", "src": "Stars and Stripes"},
 {"date": "2026-03-14", "y": 2026, "event": "Navy extends USS Nimitz ten months to hold the 11-carrier floor", "kind": "risk", "src": "Stars and Stripes"},
 {"date": "2026-04-21", "y": 2026, "event": "FY2027 PB raises Total Ship Estimate to $13,409.970M, +$213.970M", "kind": "cost", "src": "PB2027 SCN Book P-5c"},
 {"date": "2026-07-02", "y": 2026, "event": "GAO-26-108457 reports program unit costs up 3%, about $480M in one year", "kind": "cost", "src": "GAO-26-108457"},
 {"date": "2026-08-12", "y": 2026, "event": "Acceptance trials, four days underway", "kind": "milestone", "src": "HII"},
 {"date": "2026-09-29", "y": 2026, "event": "Preliminary acceptance. Ship departs NNS for Naval Station Norfolk", "kind": "milestone", "src": "HII release; USNI"},
 {"date": "2026-10-13", "y": 2026, "event": "First F-35C launch and arrested recovery on a Ford-class ship", "kind": "milestone", "src": "Naval News"},
 {"date": "2027-03", "y": 2027, "event": "Delivery and commissioning planned. 141 months award to delivery", "kind": "planned", "src": "PB2027 SCN Book P-21"},
 {"date": "2027-07", "y": 2027, "event": "Completion of Fitting Out planned", "kind": "planned", "src": "PB2027 SCN Book P-21"},
 {"date": "2028-06", "y": 2028, "event": "Obligation Work Limit Date. CFO plus 11 months, confirming OPNAVINST 4700.8M", "kind": "planned", "src": "PB2027 SCN Book P-21"},
])

# ------------------------------------------------------- 3. cost structure
cats = [
 ("Plan Costs", 898.865, "government and contractor planning and design"),
 ("Basic Construction/Conversion", 8463.156, "the hull itself. 63.1% of the ship"),
 ("Change Orders", 432.065, "scope changed after award"),
 ("Electronics", 263.359, "SSDS only. EASR is budgeted under Ordnance"),
 ("Propulsion Equipment", 2041.582, "reactor plant. No public vendor line item anywhere"),
 ("Hull, Mechanical, and Electrical", 30.302, "government furnished engineering services"),
 ("Ordnance", 1149.651, "EMALS, EASR, AAG, MOVLAS"),
 ("Other Cost", 130.990, ""),
]
write("cost_categories", {
 "total": TOTAL, "residual": round(TOTAL - sum(c[1] for c in cats), 6),
 "source": "PB2027 Exhibit P-5c, FY2013 column. VERIFIED c=0.98",
 "rows": [{"name": n, "value": v, "pct": round(v / TOTAL * 100, 2), "note": d}
          for n, v, d in cats],
 "gfe_bearing": ["Electronics", "Propulsion Equipment",
                 "Hull, Mechanical, and Electrical", "Ordnance"],
 "shipbuilder_side": ["Plan Costs", "Basic Construction/Conversion",
                      "Change Orders", "Other Cost"],
})

ap = {2007: 52.750, 2008: 123.530, 2009: 1210.561, 2010: 482.938, 2011: 902.473, 2012: 554.798}
sff = {2014: 917.553, 2015: 1219.405, 2016: 1569.543, 2017: 1241.783, 2018: 2556.384}
ctc = {2022: 291.000, 2023: 461.700, 2024: 624.600, 2025: 236.000, 2026: 150.000, 2027: 324.000}
write("funding_streams", {
 "total": TOTAL,
 "source": "PB2027 Exhibit P-5c deduction block. VERIFIED c=0.98",
 "streams": [
  {"name": "Advance Procurement", "span": "FY2007-FY2012", "value": round(sum(ap.values()), 3),
   "pct": round(sum(ap.values()) / TOTAL * 100, 1), "by_year": ap,
   "note": "A quarter of the hull was bought before the ship was authorized"},
  {"name": "Subsequent Full Funding", "span": "FY2014-FY2018", "value": round(sum(sff.values()), 3),
   "pct": round(sum(sff.values()) / TOTAL * 100, 1), "by_year": sff, "note": ""},
  {"name": "Cost to Complete", "span": "FY2022-FY2027", "value": round(sum(ctc.values()), 3),
   "pct": round(sum(ctc.values()) / TOTAL * 100, 1), "by_year": ctc,
   "note": "Still running in FY2027 for a ship that reached preliminary acceptance in Sep 2026"},
  {"name": "Net P-1 Funding", "span": "FY2013", "value": 490.952,
   "pct": round(490.952 / TOTAL * 100, 1), "by_year": {2013: 490.952},
   "note": "The procurement year itself carried 3.7%. An accounting label, not an economic event"},
 ],
 "residual": round(TOTAL - (sum(ap.values()) + sum(sff.values()) + sum(ctc.values()) + 490.952), 6),
})

write("anchor_chain", {
 "source": SRC_N + ".3",
 "steps": [
  {"label": "Statutory cap, FY2020 NDAA", "delta": 11398.000, "cum": 11398.000, "tag": "VERIFIED"},
  {"label": "Aug 2021 baseline increase (contract overruns)", "delta": 1300.000, "cum": 12698.000, "tag": "VERIFIED"},
  {"label": "Aug 2023 increment to Cost Limitation Baseline", "delta": 238.000, "cum": 12936.000, "tag": "DERIVED"},
  {"label": "Increment to the FY2026 submission", "delta": 260.000, "cum": 13196.000, "tag": "DERIVED"},
  {"label": "Increment to the FY2027 submission", "delta": 213.970, "cum": 13409.970, "tag": "VERIFIED"},
 ],
 "above_cap": round(TOTAL - 11398.0, 3),
 "above_cap_pct": round((TOTAL - 11398.0) / 11398.0 * 100, 1),
})

write("estimate_history", {
 "source": "ring0/RING0_CVN79.md K.2, from CRS RS20643 Table 2",
 "net_movement_pct": 45.9,
 "rows": [
  {"as_of": "FY2008 PB", "y": 2008, "value": 9192.0, "authority": "Budget submission", "what": "Pre-procurement estimate", "mech": "estimate"},
  {"as_of": "FY2011 PB", "y": 2011, "value": 10413.1, "authority": "Budget submission", "what": "Estimate revision", "mech": "estimate"},
  {"as_of": "FY2012 PB", "y": 2012, "value": 10253.0, "authority": "Budget submission", "what": "Revision, slightly down", "mech": "estimate"},
  {"as_of": "FY2013 PB", "y": 2013, "value": 11411.0, "authority": "Budget submission", "what": "Procurement year", "mech": "estimate"},
  {"as_of": "Nov 2015", "y": 2015, "value": 11398.0, "authority": "FY2016 NDAA", "what": "Cap lowered by statute", "mech": "statute"},
  {"as_of": "FY2017 PB", "y": 2017, "value": 11398.0, "authority": "Budget submission", "what": "Estimate equals the cap exactly", "mech": "statute"},
  {"as_of": "FY2019 PB", "y": 2019, "value": 11341.4, "authority": "Budget submission", "what": "Revision below the cap", "mech": "estimate"},
  {"as_of": "Aug 2021", "y": 2021, "value": 12698.0, "authority": "Navy, via GAO", "what": "Contract overruns at 88% complete", "mech": "overrun"},
  {"as_of": "FY2022 PB", "y": 2022, "value": 11929.7, "authority": "Budget submission", "what": "Estimate revision", "mech": "estimate"},
  {"as_of": "Aug 2023", "y": 2023, "value": 12936.0, "authority": "SECNAV to Congress", "what": "PSA work moved into construction", "mech": "scope"},
  {"as_of": "FY2026 PB", "y": 2026, "value": 13196.0, "authority": "Budget submission", "what": "Cost to complete", "mech": "estimate"},
  {"as_of": "FY2027 PB", "y": 2027, "value": 13409.970, "authority": "Budget submission", "what": "AAG testing, delay and disruption, AWE, wage and manning surge", "mech": "overrun"},
 ],
 "mechanisms": [
  {"id": "estimate", "label": "Estimate revision with no scope change", "note": "The ship did not change; the estimate did"},
  {"id": "statute", "label": "Statute moved and the estimate followed it", "note": "GAO: the cost cap informed the program cost estimate rather than the reverse"},
  {"id": "overrun", "label": "Genuine contract overrun", "note": "The only one of the five that is cost growth in the ordinary sense"},
  {"id": "scope", "label": "Scope transferred into the baseline", "note": "The ship got more expensive; the program did not"},
  {"id": "reclass", "label": "Reclassification inside the program", "note": "GAO FY2026-27: not new program costs"},
 ],
})

write("cap_history", {
 "source": "ring0/RING0_CVN79.md C.4, from CRS RS20643 footnotes",
 "three_ceilings": [
  {"name": "Statutory cost cap", "value": 11398.0, "basis": "10 U.S.C. 8691, FY2020 NDAA", "note": "SECNAV may raise by up to $100M to $11,498M"},
  {"name": "SECNAV Cost Limitation Baseline", "value": 12936.0, "basis": "Aug 2023 notification to Congress", "note": ""},
  {"name": "Budget submission total", "value": 13409.970, "basis": "FY2027 PB", "note": "All three are current and all three are correct for their own purpose"},
 ],
 "rows": [
  {"authority": "FY2007 NDAA (P.L. 109-364) Sec. 121", "action": "CVN-78 cap $10.5B, follow-ons $8.1B, plus inflation adjustment"},
  {"authority": "FY2014 NDAA", "action": "Raised CVN-79 and follow-on cap to $11,498M"},
  {"authority": "FY2016 NDAA (P.L. 114-92)", "action": "Lowered follow-on cap to $11,398.0M. Excluded certain costs from the caps (G12)"},
  {"authority": "FY2018 NDAA (P.L. 115-91)", "action": "CVN-80 and subsequent to $12,568.0M. CVN-79 held"},
  {"authority": "FY2020 NDAA (P.L. 116-92)", "action": "CVN-78 $13,224.0M, CVN-79 $11,398.0M, CVN-80 $12,202.0M, CVN-81 $12,451.0M"},
  {"authority": "FY2021 NDAA (P.L. 116-283) Sec. 1054", "action": "10 U.S.C. 8062(g), no retirement before first refueling"},
 ],
})
print("static tables written")

# ============================================================ COMPUTED FROM CSV
PIID_2116, PIID_2114 = "N0002409C2116", "N0002415C2114"


def fy_curve(rows, label):
    by = collections.defaultdict(float)
    cnt = collections.Counter()
    for r in rows:
        y = r.get("action_date_fiscal_year") or r["action_date"][:4]
        by[int(y)] += num(r["federal_action_obligation"])
        cnt[int(y)] += 1
    return [{"fy": y, "usd_m": round(by[y] / 1e6, 3), "n": cnt[y], "contract": label}
            for y in sorted(by)]


c2116 = fy_curve(tx_2116, "N00024-09-C-2116")
c2114 = fy_curve(tx_2114, "N00024-15-C-2114")
years = sorted({r["fy"] for r in c2116} | {r["fy"] for r in c2114})
m16 = {r["fy"]: r["usd_m"] for r in c2116}
m14 = {r["fy"]: r["usd_m"] for r in c2114}
cum = 0.0
curve = []
for y in years:
    a, b = m16.get(y, 0.0), m14.get(y, 0.0)
    cum += a + b
    curve.append({"fy": y, "cp": round(a, 1), "ddc": round(b, 1),
                  "combined": round(a + b, 1), "cumulative": round(cum, 1)})

tot16 = sum(num(r["federal_action_obligation"]) for r in tx_2116)
tot14 = sum(num(r["federal_action_obligation"]) for r in tx_2114)


def deobs(rows):
    n = [r for r in rows if num(r["federal_action_obligation"]) < 0]
    return {"n": len(n), "usd_m": round(sum(num(r["federal_action_obligation"]) for r in n) / 1e6, 3)}


def desc(r):
    return (r.get("transaction_description")
            or r.get("prime_award_base_transaction_description") or "").strip()


def classify(rows):
    buckets = collections.defaultdict(lambda: {"n": 0, "usd_m": 0.0})
    pats = [("Advance construction", r"ADVANCE CONSTRUCTION"),
            ("Construction preparation", r"CONSTRUCTION PREP"),
            ("Non-nuclear propulsion plant", r"NON ?NUCLEAR PROPULSION"),
            ("Incremental / installment funding", r"INCREMENTAL FUNDING|INSTALLMENT FUNDING"),
            ("Detail design and construction", r"DETAIL DESIGN")]
    for r in rows:
        d = desc(r).upper()
        hit = False
        for name, p in pats:
            if re.search(p, d):
                buckets[name]["n"] += 1
                buckets[name]["usd_m"] += num(r["federal_action_obligation"]) / 1e6
                hit = True
        if not hit:
            buckets["Other / administrative"]["n"] += 1
            buckets["Other / administrative"]["usd_m"] += num(r["federal_action_obligation"]) / 1e6
    return [{"label": k, "n": v["n"], "usd_m": round(v["usd_m"], 1)}
            for k, v in sorted(buckets.items(), key=lambda x: -x[1]["usd_m"])]


def hull_scan(rows):
    pats = [("CVN 79 / Kennedy", r"CVN ?-?79|KENNEDY"), ("CVN 80 / Enterprise", r"CVN ?-?80|ENTERPRISE"),
            ("CVN 78 / Ford", r"CVN ?-?78"), ("Nimitz class", r"NIMITZ")]
    out = collections.defaultdict(lambda: {"n": 0, "usd_m": 0.0})
    for r in rows:
        d = desc(r).upper()
        lab = "no hull keyword"
        for name, p in pats:
            if re.search(p, d):
                lab = name
                break
        out[lab]["n"] += 1
        out[lab]["usd_m"] += num(r["federal_action_obligation"]) / 1e6
    return [{"label": k, "n": v["n"], "usd_m": round(v["usd_m"], 1)}
            for k, v in sorted(out.items(), key=lambda x: -x[1]["usd_m"])]


def top(rows, k=15):
    s = sorted(rows, key=lambda r: -abs(num(r["federal_action_obligation"])))[:k]
    return [{"date": r["action_date"][:10], "mod": r["modification_number"],
             "usd_m": round(num(r["federal_action_obligation"]) / 1e6, 3),
             "desc": desc(r)[:140]} for r in s]


write("contracts", {
 "source": SRC_N + ".4, computed live from the USAspending bundles in ring0/reference/",
 "as_of": "2026-07-20",
 "primes": [
  {"piid": "N00024-09-C-2116", "title": "CVN 79 Construction Preparation", "short": "CP",
   "pricing": "Cost Plus Fixed Fee", "base_date": "2009-01-15", "base_usd_m": 111.804,
   "solicitation": "N0002408R2116", "obligated_usd_m": round(tot16 / 1e6, 3),
   "value_usd_m": 5386.150, "unobligated_usd_m": round(5386.150 - tot16 / 1e6, 1),
   "outlayed_usd_m": 72.620, "n": len(tx_2116), "deob": deobs(tx_2116),
   "pop_end": "2025-07-31", "share_of_hull": round(tot16 / 1e6 / TOTAL * 100, 1),
   "admin": "SUPSHIP Newport News", "competition": "Not competed, one source, FAR 6.302-1"},
  {"piid": "N00024-15-C-2114", "title": "CVN 79 Detail Design and Construction", "short": "DD&C",
   "pricing": "Fixed Price Incentive", "base_date": "2015-06-05", "base_usd_m": 3352.612,
   "solicitation": "", "obligated_usd_m": round(tot14 / 1e6, 3),
   "value_usd_m": 4615.796, "unobligated_usd_m": round(4615.796 - tot14 / 1e6, 1),
   "outlayed_usd_m": 0.0, "n": len(tx_2114), "deob": deobs(tx_2114),
   "pop_end": "", "share_of_hull": round(tot14 / 1e6 / TOTAL * 100, 1),
   "admin": "SUPSHIP Newport News", "competition": "Not competed, one source, FAR 6.302-1"},
 ],
 "combined_usd_m": round((tot16 + tot14) / 1e6, 3),
 "combined_share_of_hull": round((tot16 + tot14) / 1e6 / TOTAL * 100, 1),
 "combined_share_of_shipbuilder_side": 91.7,
 "outlay_coverage_pct": round(72.620 / ((tot16 + tot14) / 1e6) * 100, 2),
 "others": [
  {"piid": "N00019-14-C-0037", "office": "NAVAIR", "vendor": "General Atomics EMS",
   "scope": "EMALS and AAG, CVN 79 and CVN 80", "cvn79_usd_m": 830.438},
  {"piid": "N00024-16-C-5370", "office": "NAVSEA", "vendor": "Raytheon",
   "scope": "AN/SPY-6(V)3 EASR, six platforms", "cvn79_usd_m": 110.075,
   "warning": "Obligation total is not a CVN-79 number"},
 ],
 "collision": {"ours": "N00024-09-C-2116", "not_ours": "N00024-16-C-2116",
               "not_ours_mod_usd_m": 14917.738,
               "note": "Seven years apart, three hulls, same trailing four digits"},
})

write("obligations", {
 "source": "computed from 1,875 prime transactions",
 "curve": curve,
 "peak": max(curve, key=lambda r: r["combined"]),
 "crossover_fy": 2017,
 "cp_pct_by_fy2017": round(sum(r["cp"] for r in curve if r["fy"] <= 2017) / (tot16 / 1e6) * 100, 1),
 "classification_2116": classify(tx_2116),
 "classification_2114": classify(tx_2114),
 "hull_scan_2116": hull_scan(tx_2116),
 "top_2116": top(tx_2116),
 "top_2114": top(tx_2114),
})

acct = collections.defaultdict(float)
tas = collections.defaultdict(float)
oc = collections.defaultdict(float)
pa = collections.defaultdict(float)
for r in faf:
    a = num(r["transaction_obligated_amount"])
    acct[f"{r['federal_account_symbol']} {r['federal_account_name']}"] += a
    tas[r["treasury_account_symbol"]] += a
    oc[f"{r['object_class_code']} {r['object_class_name']}"] += a
    pa[r["program_activity_name"] or "(blank)"] += a
linked = sum(acct.values())
write("federal_accounts", {
 "source": "Contract_N0002415C2114_FederalAccountFunding, 39 rows. " + SRC_N + ".5",
 "linked_usd_m": round(linked / 1e6, 3),
 "coverage_pct": round(linked / tot14 * 100, 1),
 "coverage_warning": "Account linkage covers only a third of the contract. The remainder "
                     "predates award-level account reporting and the page carries no warning.",
 "accounts": [{"label": k, "usd_m": round(v / 1e6, 3), "pct": round(v / linked * 100, 2)}
              for k, v in sorted(acct.items(), key=lambda x: -x[1])],
 "tas": [{"label": k, "usd_m": round(v / 1e6, 3)} for k, v in sorted(tas.items(), key=lambda x: -x[1])[:8]],
 "object_class": [{"label": k, "usd_m": round(v / 1e6, 3)} for k, v in sorted(oc.items(), key=lambda x: -x[1])],
 "program_activity": [{"label": k, "usd_m": round(v / 1e6, 3), "pct": round(v / linked * 100, 1)}
                      for k, v in sorted(pa.items(), key=lambda x: -x[1])],
})

SA = "subaward_amount"
sv, sc, sstate, sfy, sbiz = (collections.defaultdict(float), collections.Counter(),
                             collections.defaultdict(float), collections.defaultdict(float),
                             collections.Counter())
state_of, place_of = {}, {}
for r in subs:
    n = (r["subawardee_name"] or "?").strip()
    a = num(r[SA])
    sv[n] += a
    sc[n] += 1
    state_of.setdefault(n, r["subawardee_state_code"])
    place_of.setdefault(n, r["subaward_primary_place_of_performance_state_code"])
    sstate[(r["subawardee_state_code"] or "?").strip()] += a
    sfy[r["subaward_action_date_fiscal_year"] or r["subaward_action_date"][:4]] += a
    for t in (r.get("subawardee_business_types") or "").split(","):
        if t.strip():
            sbiz[t.strip()] += 1
stot = sum(sv.values())
write("subawards", {
 "source": "Contract_N0002415C2114_Sub-Awards, 2,990 rows. NEW: not previously in the dossier. "
           "Extends Part L.3, the finding that the vendor map runs one tier deeper than the contract map.",
 "rows": len(subs), "total_usd_m": round(stot / 1e6, 2),
 "distinct_subawardees": len(sv),
 "share_of_prime_obligations_pct": round(stot / tot14 * 100, 1),
 "note": "Only the DD&C contract reports sub-awards. This is the visible tier-2 map and it "
         "covers under a tenth of the prime. The rest of the supply chain is not reported at all.",
 "top": [{"name": n, "usd_m": round(v / 1e6, 2), "n": sc[n],
          "state": state_of.get(n, ""), "pop_state": place_of.get(n, "")}
         for n, v in sorted(sv.items(), key=lambda x: -x[1])[:30]],
 "by_state": [{"state": k, "usd_m": round(v / 1e6, 2)}
              for k, v in sorted(sstate.items(), key=lambda x: -x[1]) if v > 0],
 "by_fy": [{"fy": k, "usd_m": round(v / 1e6, 2)} for k, v in sorted(sfy.items())],
 "business_types": [{"label": k, "n": v} for k, v in sbiz.most_common(14)],
 "largest": [{"date": r["subaward_action_date"][:10], "name": r["subawardee_name"],
              "usd_m": round(num(r[SA]) / 1e6, 2),
              "desc": (r.get("subaward_description") or "")[:110]}
             for r in sorted(subs, key=lambda r: -num(r[SA]))[:15]],
})
print("computed tables written")

# ============================================================ remaining tables
write("equipment", {
 "source": SRC_N + ".6, PB2027 P-5a and P-8a equipment pages, FY2013 / CVN 79 rows",
 "captured_usd_m": 1059.688,
 "share_of_gfe_categories_pct": 30.4,
 "note": "Propulsion Equipment, the second largest category in the ship at $2,041.582M, "
         "has no captured line items at all. The reactor plant is not itemised by vendor "
         "in any public exhibit. That is the largest single unattributed block in the hull.",
 "rows": [
  {"usd_m": 611.307, "vendor": "GENERAL ATOMICS", "type": "SS/FFP", "award": "May 2014", "note": "EMALS"},
  {"usd_m": 219.131, "vendor": "GENERAL ATOMICS", "type": "SS/FFP", "award": "May 2014", "note": "AAG"},
  {"usd_m": 44.937, "vendor": "RAYTHEON", "type": "C/CPIF", "award": "Dec 2019", "note": ""},
  {"usd_m": 39.607, "vendor": "RAYTHEON", "type": "C/FFP", "award": "Nov 2019", "note": ""},
  {"usd_m": 39.423, "vendor": "LOCKHEED MARTIN", "type": "SS/FFP", "award": "Dec 2022", "note": ""},
  {"usd_m": 12.305, "vendor": "VARIOUS", "type": "C/FFP", "award": "Mar 2017", "note": ""},
  {"usd_m": 11.135, "vendor": "LOCKHEED MARTIN", "type": "C/FFP", "award": "Apr 2019", "note": ""},
  {"usd_m": 10.117, "vendor": "LOCKHEED MARTIN", "type": "C/FFP", "award": "Jan 2020", "note": ""},
  {"usd_m": 9.162, "vendor": "RAYTHEON", "type": "C/FFP", "award": "Nov 2021", "note": ""},
  {"usd_m": 7.730, "vendor": "GENERAL DYNAMICS", "type": "C/FFP", "award": "Sep 2014", "note": ""},
  {"usd_m": 7.389, "vendor": "NAWCAD", "type": "Various", "award": "Dec 2016", "note": ""},
  {"usd_m": 6.092, "vendor": "RAYTHEON", "type": "C/FFP", "award": "Jun 2019", "note": "qty 2"},
  {"usd_m": 5.903, "vendor": "BAE SYSTEMS", "type": "C/FFP", "award": "May 2016", "note": ""},
  {"usd_m": 5.186, "vendor": "RAYTHEON", "type": "C/FFP", "award": "Mar 2020", "note": "qty 3"},
  {"usd_m": 5.091, "vendor": "RAYTHEON", "type": "C/FFP", "award": "Jun 2014", "note": ""},
  {"usd_m": 4.528, "vendor": "GENERAL DYNAMICS", "type": "C/FFP", "award": "Feb 2019", "note": ""},
  {"usd_m": 4.505, "vendor": "LAUREL TECHNOLOGIES", "type": "SS/FFP", "award": "Mar 2020", "note": ""},
  {"usd_m": 4.024, "vendor": "DRS", "type": "C/FFP", "award": "May 2020", "note": ""},
  {"usd_m": 3.771, "vendor": "VARIOUS", "type": "Various", "award": "Apr 2020", "note": ""},
  {"usd_m": 2.863, "vendor": "VARIOUS", "type": "Various", "award": "Jan 2020", "note": ""},
  {"usd_m": 2.743, "vendor": "VARIOUS", "type": "Various", "award": "Jan 2020", "note": ""},
  {"usd_m": 2.739, "vendor": "BOWHEAD", "type": "C/FFP", "award": "Jul 2016", "note": "option"},
 ],
 "by_vendor": [
  {"vendor": "General Atomics", "usd_m": 830.438}, {"vendor": "Raytheon", "usd_m": 110.075},
  {"vendor": "Lockheed Martin", "usd_m": 60.675}, {"vendor": "Various", "usd_m": 21.682},
  {"vendor": "General Dynamics", "usd_m": 12.258}, {"vendor": "NAWCAD", "usd_m": 7.389},
  {"vendor": "BAE Systems", "usd_m": 5.903}, {"vendor": "Laurel Technologies", "usd_m": 4.505},
  {"vendor": "DRS", "usd_m": 4.024}, {"vendor": "Bowhead", "usd_m": 2.739},
 ],
})

write("industrial", {
 "source": "ring0/RING0_CVN79.md Part L",
 "integrator": {
  "name": "HII Newport News Shipbuilding",
  "role": "hull builder and systems integrator. Not the manufacturer of most major systems",
  "monopoly": "The only US shipyard able to build large-deck nuclear carriers. "
              "Every US carrier procured since FY1958 was built there",
  "method": "Modular construction. Sections welded into superlifts, equipment installed "
            "while the unit is on the ground, lifted into Dry Dock 12 by a 1,050 metric ton gantry crane",
  "lifts": 447, "employees_on_class": 6600, "total_employees": 25000,
  "build_strategy": "CVN-79 took modular construction and pre-outfitting to a new level: larger "
                    "superlifts at a higher state of outfitting completion, more parts installed "
                    "in shop and on the final assembly platen",
 },
 "systems": [
  {"system": "A1B reactor plant, two per ship", "maker": "Bechtel Marine Propulsion (design); BWXT (core and fuel)",
   "delivery": "GFE", "path": "SCN advance procurement, Nuclear Propulsion Equipment, 30 to 72 month lead. "
   "Naval Reactors is jointly Navy and DOE", "command": "Naval Reactors / DOE"},
  {"system": "EMALS and AAG", "maker": "General Atomics Electromagnetic Systems; QinetiQ subcontract",
   "delivery": "GFE, installed by HII", "path": "N00019-14-C-0037, CVN 79 and CVN 80. "
   "CVN-79 share $830.438M", "command": "NAVAIR PMA-251"},
  {"system": "Advanced Weapons Elevators, eleven per ship", "maker": "Federal Equipment Company; "
   "MagneMotion linear synchronous motors; Curtiss-Wright Exlar actuators",
   "delivery": "installed on the ship", "path": "N64498-18-D-4022 engineering and the land-based test site. "
   "The single largest driver of this hull's delay", "command": "NSWC Philadelphia"},
  {"system": "Radar", "maker": "Raytheon AN/SPY-6(V)3 EASR plus AN/SPQ-9B",
   "delivery": "GFE", "path": "A configuration break from CVN-78's Dual Band Radar. "
   "CVN-79 is a different configuration, not a second copy, which weakens any learning-curve "
   "comparison between the two hulls", "command": "NAVSEA"},
  {"system": "Combat system", "maker": "Raytheon Ship Self-Defense System Mk 2 with CEC",
   "delivery": "GFE", "path": "", "command": "NAVSEA"},
  {"system": "EMALS energy storage subsystems", "maker": "KATO Engineering, CAGE 3LVT8",
   "delivery": "GFE", "path": "On CVN-79 this sits inside the GA contract as a subcontract and is "
   "invisible at prime level. On CVN-81 it is its own prime, N00019-23-C-0040. The cleanest worked "
   "example that the vendor map runs a tier deeper than the contract map", "command": "NAVAIR"},
  {"system": "Networks (CANES)", "maker": "integrated by HII", "delivery": "under the HII contract",
   "path": "$37,544,972 FPIF mod to 2114, Mar 2024, funded 65% FY2024 SCN and 35% FY2018 SCN",
   "command": "NAVSEA"},
 ],
 "consequences": [
  "The two HII contracts buy construction and integration, not content. Electronics, "
  "Propulsion Equipment and Ordnance are substantially government furnished, bought on other "
  "contracts by other commands.",
  "Neither roll-up method is sufficient alone. A contract roll-up anchored on CAGE 43689 captures "
  "the hull and misses the systems. A category roll-up from the P-5 captures the systems but "
  "cannot see the contracts beneath them.",
  "Cross-command GFE is where hull attribution breaks. An EMALS shipset bought by NAVAIR on an "
  "aviation contract and installed by HII on a NAVSEA ship under a NAVSEA contract has no single "
  "line of accounting that says CVN-79 from end to end. That, not the ledger seam, is the hardest "
  "attribution problem in this program.",
 ],
})

write("attribution", {
 "source": SRC_N + ".8",
 "total": TOTAL, "attributed_usd_m": 10157.592, "attributed_pct": 75.8,
 "residual_usd_m": 3252.378, "residual_pct": 24.2,
 "improved_from_pct": 42.2,
 "note": "Attribution improved from 42.2% to 75.8% in one pass, entirely by replacing an "
         "announcement-derived figure with the obligation record. The residual is not a budget "
         "gap: the budget closes to zero twice over. It is the portion of the hull that no public "
         "contract-level record attributes to CVN-79.",
 "components": [
  {"label": "CP contract N00024-09-C-2116", "usd_m": 4519.300, "tag": "VERIFIED", "c": 0.95},
  {"label": "DD&C contract N00024-15-C-2114", "usd_m": 4578.603, "tag": "VERIFIED", "c": 0.95},
  {"label": "EMALS, N00019-14-C-0037", "usd_m": 611.307, "tag": "VERIFIED", "c": 0.95},
  {"label": "AAG, N00019-14-C-0037", "usd_m": 219.131, "tag": "VERIFIED", "c": 0.95},
  {"label": "Other equipment line items", "usd_m": 229.251, "tag": "VERIFIED", "c": 0.90},
 ],
 "residual_contents": [
  {"label": "Nuclear propulsion plant, Naval Reactors furnished", "usd_m": 1643.073, "tag": "UNKNOWN", "c": 0.10, "gap": "G22"},
  {"label": "Ordnance less EMALS, AAG and EASR", "usd_m": 319.213, "tag": "UNKNOWN", "c": 0.15, "gap": "G20"},
  {"label": "Government plans, engineering, program management", "usd_m": None, "tag": "UNKNOWN", "c": 0.15, "gap": ""},
  {"label": "Outfitting and post-delivery, this hull's share", "usd_m": None, "tag": "UNKNOWN", "c": 0.20, "gap": "G23"},
  {"label": "Unobligated ceiling and cost to complete FY26-27", "usd_m": None, "tag": "UNKNOWN", "c": 0.30, "gap": ""},
 ],
})

write("layers", {
 "source": "BLUEPRINT.md section 8. Hub and spoke with the ledger as hub.",
 "layers": [
  {"id": "L0", "name": "Reported", "producer": "The Department to Congress, plus oversight bodies",
   "purpose": "Justification and accountability", "status": "rich",
   "present": "Parts A to E and K.2. SARs, MSARs, J-Books, CRS, GAO, DODIG",
   "access": "none needed"},
  {"id": "L1", "name": "Budget", "producer": "The comptroller chain",
   "purpose": "Plan, request, appropriate, apportion, allot, obligate, expend", "status": "partial",
   "present": "P-5c categories, P-40 funding streams by year, the appropriation map from the contract's own account file",
   "access": "Advana budget execution for the specific appropriation lines (Gate D)"},
  {"id": "L2", "name": "Ledger", "producer": "The accounting systems and DFAS",
   "purpose": "Record transactions under the USSGL", "status": "absent",
   "present": "nothing", "access": "NAVSEA 01 or PEO Carriers. The long pole"},
  {"id": "L3", "name": "Asset", "producer": "Accounting plus property accountability",
   "purpose": "Accumulate CIP, capitalize at placement in service, depreciate", "status": "standards only",
   "present": "Part I. The standards stack and the three structural divergences. No figures",
   "access": "Navy Office of Financial Operations"},
  {"id": "L4", "name": "Program", "producer": "PEO Carriers, PMS 379, the shipbuilder",
   "purpose": "Manage cost and schedule against a baseline", "status": "partial",
   "present": "MSAR EVM for CVN-80 at 56.43% complete, cost variance -$1,745.6M. Sister-hull only",
   "access": "CADE / DCARC. Compliance rated Red"},
  {"id": "L5", "name": "Evidence", "producer": "Feeder systems",
   "purpose": "The underlying documents", "status": "partial",
   "present": "1,875 prime transactions and 2,990 sub-awards, held and parsed",
   "access": "PIEE, EDA, MOCAS for the rest"},
 ],
 "topology": "L2 is the hub, the only layer where every dollar has a posting. L1, L3 and L4 each "
             "tie to it on a different cut. L0 ties to L1 and L4 and never directly to L2. "
             "L5 sits beneath L2.",
})

write("variances", {
 "source": "ring0/RING0_CVN79.md Part E",
 "rows": [
  {"id": "E-1", "status": "live", "flag": "", "title": "Three different cost caps in circulation",
   "detail": "Statutory cap $11,398.0M, SECNAV Cost Limitation Baseline $12,936M, budget submission "
   "$13,409.970M. All three are current and all three are correct for their own purpose. Any product "
   "showing one number as the cost cap will be wrong."},
  {"id": "E-2", "status": "resolved", "flag": "", "title": "The $11.341B figure",
   "detail": "A sourced FY2019 budget estimate in then-year dollars, not a total and not a cap. "
   "Usable as a dated estimate, never as the cost of the ship."},
  {"id": "E-3", "status": "resolved", "flag": "", "title": "Obligation Work Limiting Date",
   "detail": "Resolved in favour of OPNAVINST 4700.8M. CFO Jul 2027 plus eleven months gives Jun 2028. "
   "The NAVSEA desk reference reading of thirteen months after delivery would give Apr 2028."},
  {"id": "E-4", "status": "live", "flag": "", "title": "Keel laying date",
   "detail": "20 July 2015 in some records, 22 August 2015 in others."},
  {"id": "E-5", "status": "live", "flag": "", "title": "Attributed delay cause shifts by year and by authority",
   "detail": "The budget footnote says AAG certification and AWE. DOT&E adds supply chain. GAO adds "
   "material availability and workforce. HII adds untimely availability of Ford lessons. Same slip, "
   "four causes. That is itself a finding."},
  {"id": "E-6", "status": "live", "flag": "", "title": "Life-cycle savings claim, $4B against $5B",
   "detail": "Per ship over 50 years versus Nimitz class."},
  {"id": "E-7", "status": "live", "flag": "", "title": "Is the FY2026-FY2027 unit cost increase new cost",
   "detail": "GAO: unit costs up 3%, about $480M, roughly half from delivery schedule changes, but "
   "the Navy is using funds already budgeted for post-delivery, so these are not new program costs. "
   "The same dollars are a cost increase in one view and a reclassification in another."},
  {"id": "E-8", "status": "live", "flag": "", "title": "Program start has at least six defensible dates",
   "detail": "FY2001 shared CVN-21 AP, FY2004 CP contract, FY2007 first hull-specific AP, Jan 2009 CP "
   "award, FY2013 procurement year, Jun 2015 DD&C award, Aug 2015 keel. Each correct for a different audience."},
  {"id": "E-9", "status": "live", "flag": "", "title": "Supplier footprint count", "detail": "2,000 firms in 46 states against 43 states."},
  {"id": "E-10", "status": "live", "flag": "", "title": "Delivery against commissioning conflated",
   "detail": "Several outlets treat March 2027 as both. Preliminary acceptance actually occurred 29 Sep 2026."},
  {"id": "E-11", "status": "live", "flag": "", "title": "A contract mislabel in the research notes",
   "detail": "January 2009 was the Construction Preparation contract. DD&C was awarded 5 June 2015. "
   "Two different contracts six years apart."},
  {"id": "E-12", "status": "recorded", "flag": "INTERPRETATION", "title": "The dagger inference",
   "detail": "Part K.1 reasoned the dagger marked GFE-bearing categories. The exhibit defines it in "
   "place as indicating the presence of a P-8a. Plausible, convenient, consistent with everything "
   "else, and wrong. Kept because the shape recurs: a real structural pattern with an invented "
   "interpretation laid over it."},
  {"id": "E-13", "status": "recorded", "flag": "METHOD", "title": "Announced modifications summed as obligations",
   "detail": "N00024-09-C-2116 was carried at roughly $1.08B, built by summing announced DoD contract "
   "modifications. The obligation record gives $4,519,300,323.83, an understatement by a factor of "
   "4.18. Announcements have a dollar threshold, omit incremental funding (which carries $2.49B here) "
   "and cannot net deobligations (68 actions, -$66.8M). A press release is an announcement, never a record."},
  {"id": "E-14", "status": "live", "flag": "METHOD", "title": "USAspending disagrees with itself",
   "detail": "By exactly $5,880,250.00 on N00024-15-C-2114. Two of three products agree, so the "
   "transaction sum is canonical. Both are the same system on the same as-of date."},
  {"id": "E-15", "status": "live", "flag": "KEY", "title": "The 2116 identifier collision",
   "detail": "N00024-09-C-2116 is this hull's Construction Preparation. N00024-16-C-2116 is CVN-80 "
   "and CVN-81 DD&C, carrying a $14,917,738,145 modification. Same last four digits, seven years "
   "apart, different hulls. Any fuzzy or partial match merges three hulls undetectably."},
  {"id": "E-16", "status": "resolved", "flag": "METHOD",
   "title": "FPDS-NG and USAspending differ by $583,963.00 on the construction preparation contract: an as-of difference",
   "detail": "Resolved 2026-11-08. The contract is N00024-09-C-2116 (construction preparation), not "
   "the DD&C contract N00024-15-C-2114, whose transaction sum is $4,578,603,345.77. The FPDS-NG ATOM "
   "feed reported totalObligatedAmount $4,518,716,360.83 against USAspending's transaction sum of "
   "$4,519,300,323.83. The USAspending running total on 09-C-2116 through action date 2026-06-10 is "
   "exactly $4,518,716,360.83. The eight actions dated 2026-06-17 to 2026-07-20 (A00645 to AZ0122) "
   "sum to exactly $583,963.00. Cause: as-of date. totalObligatedAmount is cumulative per "
   "modification, and the entry read was the 10 June action, not the latest. Method rule: read "
   "totalObligatedAmount from the latest modification, and state the as-of date with every "
   "obligation figure. Caveat: the FPDS side is the figure as recorded on 2026-11-08 and was not "
   "re-pulled."},
 ],
})

write("clue_map", {
 "source": "ring0/RING0_CVN79.md Part M. Ordered by expected materiality.",
 "rows": [
  {"n": 1, "where": "SCN line 2001 Carrier Replacement Program", "key": "1611N / BA 02 / BLI 2001 / PE 0204112N; subhead", "note": "The construction spine"},
  {"n": 2, "where": "SCN line 5110 Outfitting", "key": "1611N / BA 05 / LI 5110", "note": "Outfitting and spares. Not on the construction line"},
  {"n": 3, "where": "SCN line 5300 Completion of PY Shipbuilding", "key": "1611N / BA 05 / LI 5300", "note": "Where post-OWLD completion money lands"},
  {"n": 4, "where": "NAVAIR EMALS and AAG", "key": "N00019-14-C-0037; PMA-251", "note": "CVN-79 share $830.438M"},
  {"n": 5, "where": "Naval Reactors reactor plant", "key": "SCN AP Nuclear Propulsion Equipment; DOE Naval Reactors", "note": "Crosses from Navy to DOE. 30 to 72 month lead"},
  {"n": 6, "where": "NSWC Philadelphia AWE", "key": "N64498-18-D-4022", "note": "Engineering, technical services, land-based test site"},
  {"n": 7, "where": "Shared class RDT&E", "key": "PE 0604112N", "note": "EMALS, AAG, DBR development. Allocation method open, G4"},
  {"n": 8, "where": "Other Procurement, Navy", "key": "OPN", "note": "Small but proves the line exists"},
  {"n": 9, "where": "Other appropriations on the MSAR funding table", "key": "1810N / 5664; 1804N / 1B5B", "note": "Published by the program itself"},
  {"n": 10, "where": "Foreign Military Sales funds on the hull contract", "key": "FMS Canada, Norway, Spain", "note": "Arguably not US program cost at all"},
  {"n": 11, "where": "Other-service funds on the hull contract", "key": "FY2025 RDT&E (USMC) $250,000", "note": "Same point, other direction"},
  {"n": 12, "where": "GFP in contractor possession", "key": "GFP Position Report, CAGE 43689; IUID Registry", "note": "G16. Cheapest high-value request in the file"},
  {"n": 13, "where": "Contractor cost by work breakdown", "key": "CSDR: DD 2794, DD 1921 series, FlexFile, in CADE", "note": "G11. The only below-appropriation view. Compliance rated Red"},
  {"n": 14, "where": "Post-delivery, PSA and fitting out", "key": "Between delivery and OWLD", "note": "Part of SCN by rule"},
  {"n": 15, "where": "Consequence cost on other hulls", "key": "Nimitz ten-month extension and inactivation planning", "note": "Caused by this hull's delay, will never carry a CVN-79 line of accounting"},
  {"n": 16, "where": "Shore infrastructure driven by the ship", "key": "$145M electrical overhaul at Naval Base Kitsap", "note": "Real property, FMR Vol 4 Ch 24"},
  {"n": 17, "where": "Below-threshold expensed content", "key": "items under the $1M Navy capitalization threshold", "note": "G19. Installed on the ship, never capitalized"},
  {"n": 18, "where": "Reprogramming and apportionment", "key": "DD 1415-1; OMB apportionment for TAFS 017-1611", "note": "Movement after appropriation that no J-book shows"},
 ],
})

write("asset", {
 "source": "ring0/RING0_CVN79.md Parts I and J",
 "status": "The hull is on the Navy's books today as Construction in Progress, not as a vessel.",
 "balance_sheet": {"gppe_net_book_value_usd_b": 503.1, "share_of_total_assets_pct": 55.9,
                   "note": "Vessels and aircraft make up over 90% of the CIP balance. GPP&E remains a material weakness.",
                   "source": "DON FY2025 Agency Financial Report"},
 "parameters": [
  {"label": "Capitalization threshold", "value": "$1,000,000", "note": "Department of the Navy general fund general equipment. Raised from $100,000 in October 2013"},
  {"label": "Useful life", "value": "50 years", "note": "FMR Table 25-2, Aircraft Carrier"},
  {"label": "Depreciation", "value": "Straight line only", "note": "Alternate methods require written OUSD(C) approval"},
 ],
 "divergences": [
  {"n": 1, "name": "Scope", "detail": "Capitalized value is the acquisition cost of the asset placed in service. "
   "Program cost includes things that never capitalize: terminated or reworked scope, the cost of delay, "
   "class research benefiting later hulls, program office overhead, FMS-funded content. And every "
   "component below the $1M threshold is expensed even though it is physically installed on the ship."},
  {"n": 2, "name": "Timing", "detail": "Program cost accrues from FY2001 or FY2007 depending on convention. "
   "Capitalized value appears at a single instant at placed in service. Roughly twenty years of "
   "accumulated cost collapses onto one date, and the depreciation clock then runs 50 years forward."},
  {"n": 3, "name": "Boundary", "detail": "Two authorities set two different end points. OWLD governs what may "
   "be charged to the appropriation. Placed in service governs when the asset is recognized. Different "
   "dates, different offices, different purposes."},
 ],
 "open_risk": "Whether GFE installed on the hull is capitalized separately or rolled into the vessel's "
              "value. EMALS, AAG, the eleven AWEs and the EASR array are each far above the threshold "
              "and each bought by a different command. If both records capitalize it the Navy double "
              "counts. If neither does it drops. G15.",
 "cip_relief_question": {"gap": "G14",
   "candidates": ["Preliminary acceptance, 29 Sep 2026", "Delivery, Mar 2027", "Commissioning"],
   "note": "FMR Vol 4 Ch 25 ties relief to placed in service in one paragraph and to acceptance in "
           "another. The three candidate dates straddle a fiscal year boundary, so the answer decides "
           "which year a roughly $13 billion asset appears on the balance sheet."},
 "gfp": {
   "weakness_since": 2001,
   "detail": "Reporting of government property in contractor possession has been a DoD-wide material "
             "weakness since fiscal year 2001. GAO-25-106868 found that DCMA and the Navy's Supervisors "
             "of Shipbuilding were not consistently verifying the accuracy of contractor property records "
             "on selected major programs. SUPSHIP Newport News administers both of this hull's contracts. "
             "That is not an analogy, it is the same office.",
   "f35_precedent": {"facilities": 50, "lost_parts": 1000000, "lost_usd_m": 85,
                     "reviewed_pct": 2, "estimate_usd_b": 220,
                     "note": "DoD has estimated the value of F-35 parts in contractor possession at over "
                             "$220 billion, which GAO reports is likely significantly understated. The root "
                             "cause is a categorization dispute, not a counting failure."},
   "actionable": "Run the GFP Position Report for CAGE 43689 scoped to both contracts and cross-check "
                 "against the IUID Registry. Defined population, defined key, existing report, mandated "
                 "seven-business-day cadence, no new access path. G16.",
 },
})

write("sources", {
 "source": "ring0/RING0_CVN79.md Parts C and H",
 "families": [
  {"name": "Modernized Selected Acquisition Report", "short": "MSAR / SAR",
   "carries": "contract numbers, CAGE codes, percent complete, EVM variances, funding by appropriation and line item, Cost Limitation Baseline history",
   "limit": "Reports aggregate program cost for all ships in the class, not broken out by hull. "
            "Genuine CVN-79 detail at contract and subprogram level; no clean hull-allocated total.",
   "held": ["CVN 78 MSAR FY2027 PB", "CVN 78 MSAR Dec 2023", "CVN 78 SAR Dec 2022"]},
  {"name": "SCN Justification Book", "short": "J-Book",
   "carries": "P-1 total obligational authority, P-40 funding profile, P-5/P-5a/P-5c cost analysis by category, P-10 advance procurement, P-21 production schedule and OWLD",
   "limit": "Printed P-1 line number is renumbered between budget years while the BLI stays 2001.",
   "held": ["SCN Book PB27"]},
  {"name": "Congressional Research Service", "short": "CRS",
   "carries": "Table 1 procurement funding for CVNs 78-82 by fiscal year; Table 2 the estimate in each successive budget submission; Table 3 congressional action",
   "limit": "Secondary. Good citations, written for Congress.",
   "held": ["RS20643 current", "RS20643.302 (2007)"]},
  {"name": "Government Accountability Office", "short": "GAO",
   "carries": "independent assessment, cost estimate reliability, post-delivery and OWLD policy, shipbuilding financing payments",
   "limit": "Findings about other layers, which is a free head start on variance causes.",
   "held": ["GAO-17-575 Ford-class cost estimates", "GAO-15-22 cost cap legislation"]},
  {"name": "DoD Inspector General", "short": "DODIG",
   "carries": "material weakness findings, shipbuilding CIP, government property in contractor possession",
   "limit": "", "held": []},
  {"name": "Policy and standards", "short": "FMR / OPNAVINST / FASAB",
   "carries": "the rules that make a figure mean something",
   "limit": "Produces mechanisms, not figures.",
   "held": ["SUPSHIP Operations Manual Ch 4 Financial Management", "DCMA MAN 2101-02 Payment",
            "DoN 5200.45A General Equipment Accountability"]},
  {"name": "Federal spending transaction record", "short": "USAspending / FPDS",
   "carries": "1,875 prime transactions, 2,990 sub-awards, 39 federal account funding rows",
   "limit": "Obligations usable. Outlays are not: award-level outlay reporting covers 0.80% of "
            "obligations on this hull. Account linkage covers a third of the DD&C contract.",
   "held": ["CONT_N0002415C2114 bundle", "PrimeAwardSummariesAndTransactions bundle"]},
  {"name": "Academic and industry", "short": "other",
   "carries": "method and context", "limit": "Lead grade.",
   "held": ["NPS-AM-26-055"]},
 ],
})
print("remaining tables written")

# ----------------------------------------- gaps, projected from seed + LOG text
import yaml
SEED = ROOT / "seed"
gi = yaml.safe_load((SEED / "gaps.index.yaml").read_text())["gaps"]
TITLES = {
 "G1": "Which accounting systems carried this program's postings, and when",
 "G2": "Whether SABRS is in scope for this program",
 "G3": "Whether FMR Volume 11B Chapter 12 governs program office overhead and travel",
 "G4": "Hull-level cost and the shared class R&D allocation method",
 "G5": "Full inventory of systems feeding the Advana financial management environment",
 "G6": "NSMA, the fourth Navy general ledger",
 "G7": "Construction in progress for NAVSEA shipbuilding uses manual adjustments",
 "G8": "The Navy ERP subhead to NWA/WBS mapping that isolates this hull",
 "G9": "Whether the payment path changed when MOCAS entitlement moved to Navy ERP",
 "G10": "The established obligation work limiting date for this hull",
 "G11": "Cost and software data reporting submissions for this hull",
 "G12": "Which costs the FY2016 authorization act excluded from the cost caps",
 "G13": "Rework cost from the 2024 welding deviations",
 "G14": "When construction in progress is relieved for this hull",
 "G15": "Whether installed GFE is capitalized separately or inside the hull",
 "G16": "Government furnished property held by the shipbuilder for this hull",
 "G17": "What the dagger footnote marks on three cost analysis rows",
 "G18": "The cost analysis column for this hull, every year it was published",
 "G19": "Content expensed rather than capitalized under the capitalization threshold",
 "G20": "Shipset prices for the weapons elevators and remaining ordnance",
 "G21": "Base award value of the January 2009 construction preparation contract",
 "G22": "Vendor level attribution of the propulsion equipment category",
 "G23": "Outfitting and post delivery attributable to this hull",
 "G24": "Obligations on the preparation contract after its period of performance ended",
 "G25": "Award level outlay reporting covers under one per cent of obligations",
 "G26": "Full enumeration of contracts carrying scope for this hull",
 "G27": "Two contracts carried as General Atomics. Neither is this hull, one is not that vendor",
 "G28": "The 2116 contract number collision, registered as a hard exclusion",
 # G29-G65 adopted 2026-11-09 from aircarrier_proposed_gaps; headings in LOG.md Part II.
 "G29": "The 2004 CVN 21 acquisition decision memorandum and its quantity basis",
 "G30": "Records retention for this hull's payment records",
 "G31": "Reimbursable and project orders for this hull, and who records them",
 "G32": "Test scope in the DOT&E reports and the CVN 78 and Enterprise TEMPs",
 "G33": "Transaction-level support for this hull's funding and payment actions",
 "G34": "Ship acceptance records and SUPSHIP's certification role",
 "G35": "EMALS baseline change 3 and its cost scope",
 "G36": "Systems on this hull that differ from the lead ship's tested configuration",
 "G37": "What the Ford-class acquisition program baseline covers for this hull",
 "G38": "The per-ship assumptions behind the Navy O&S estimate",
 "G39": "Contractor debts and collections against this hull's contracts",
 "G40": "Whether any hull-level or sub-program baseline exists",
 "G41": "The shipbuilder's integrated master schedule as a deliverable",
 "G42": "Whether an independent cost estimate was ever made for this hull",
 "G43": "ACO-approved versus disbursed financing payments",
 "G44": "Cost for this hull carried in other programs of record",
 "G45": "The 2015 Service Cost Position and the O&S cost-element structures",
 "G46": "What CLIN 0001 covers, against the contract performance report",
 "G47": "The program deviation report and the baseline change that followed",
 "G48": "MOCAS field definitions and the contracts' payment clauses",
 "G49": "Class development funded in shipbuilding rather than RDT&E",
 "G50": "The prescribed equipment valuation and CIP relief record formats",
 "G51": "Which program of record carries each capability modification",
 "G52": "The sources behind the antecedent carrier O&S estimate",
 "G53": "The FY2026 budget submission's full funding, AP and cost-to-complete lines",
 "G54": "CAPE O&S cost-element structures, 2014 and 2020",
 "G55": "The approved acquisition strategy and its review tailoring",
 "G56": "Estimate-at-completion documentation held by DCMA",
 "G57": "The new-construction berthing adjustment in the O&M estimate",
 "G58": "The November 2018 two-ship buy certification and its exclusions",
 "G59": "Whether the EMALS long-lead and shipset contracts overlap",
 "G60": "The budget submitting office's quarterly asset submissions",
 "G61": "Whether the EMALS subprogram estimates sit inside the CVN 78 estimates",
 "G62": "Which office is accountable for this hull's equipment",
 "G63": "What the governing authorities require at ship versus class level",
 "G64": "The FY2007 split-funding authority and its scope",
 "G65": "The Section 121(b) certification against CAPE's two-ship savings estimate",
}
W = {"zero_access": 1.00, "query": 0.80, "access_required": 0.35, "sme": 0.25,
     "terminal": 0.05, "unknown": 0.50}
rows = []
for g in gi:
    closed = g["status"] in ("resolved", "resolved_negative", "closed")
    exp = g.get("exposure_usd_m", 0.0)
    ign = g.get("ignorance", 0.5)
    clos = g.get("closability", "unknown")
    rows.append({
        "id": g["id"], "title": TITLES.get(g["id"], ""), "status": g["status"],
        "type": g.get("type", ""), "executor": g.get("executor", ""),
        "exposure_usd_m": exp, "ignorance": ign, "closability": clos,
        "decay": g.get("decay", ""), "note": (g.get("note") or g.get("resolution") or "").strip(),
        "closed": closed,
        # Scored means a person has put an ignorance value on the gap in the
        # index. Gaps adopted from the investigator arrive unscored and carry
        # the 0.5 default, which is a placeholder, not a position on a chart.
        "scored": "ignorance" in g,
        "priority": 0.0 if closed else round(max(exp, 1.0) * ign * W.get(clos, 0.5), 2),
    })
open_rows = sorted([r for r in rows if not r["closed"]], key=lambda r: -r["priority"])
write("gaps", {
 "source": "LOG.md Part II, projected through seed/gaps.index.yaml",
 "ranking": "exposure x ignorance x closability. Discovery ranks differently from publication: "
            "high closability gets worked because it is free, high exposure with low closability "
            "becomes the access ask.",
 "total": len(rows), "open": len(open_rows), "closed": len(rows) - len(open_rows),
 "rows": rows, "ranked": [r["id"] for r in open_rows],
 "free_now": [r["id"] for r in open_rows if r["closability"] in ("zero_access", "query")],
})
print("gaps written")
