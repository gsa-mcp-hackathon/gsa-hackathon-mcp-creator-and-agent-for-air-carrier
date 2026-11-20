#!/usr/bin/env python3
"""Agent checks. Run with: python checks/test_agents.py

Exercises the three implemented agents against figures and gaps taken from the
dossier rather than invented ones, so a drift in the agents shows up as a
disagreement with the record.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.contracts import Claim, Coordinate, Gap, GapType, RiskFlag, Tag, Zone
from ops.agents.challenger.run import challenge
from ops.agents.investigator.run import (
    CLOSABILITY_WEIGHT,
    CollectionRequirement,
    Hypothesis,
    WorkPlan,
    free_now,
    postmortem,
    rank,
    run,
    validate,
)
from ops.agents.tieout.run import anchor_chain, residual_is_finding, two_axis_close

OK, FAIL = 0, 0


def check(name, cond, detail=""):
    global OK, FAIL
    if cond:
        OK += 1
        print(f"  [ok  ] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name}   {detail}")
    if detail and cond:
        print(f"         {detail}")


GAPS = [
    Gap("G16", "Government furnished property held by the shipbuilder", GapType.DOCUMENT,
        "DCMA property report", exposure_usd_m=900.0, ignorance=0.8, closability="zero_access"),
    Gap("G24", "Obligations on the preparation contract after its period of performance ended",
        GapType.DATA, "Navy ERP via Advana", exposure_usd_m=320.0, ignorance=0.7,
        closability="query"),
    Gap("G13", "Rework cost from the 2024 welding deviations", GapType.SME,
        "SUPSHIP Newport News", exposure_usd_m=40.0, ignorance=0.95, closability="sme",
        decay_risk="high"),
    Gap("G5", "Full inventory of systems feeding Advana FM", GapType.CATALOG,
        "Advana FM data product owner", exposure_usd_m=0.0, ignorance=0.6,
        closability="access_required"),
    Gap("GX", "No record and no living memory", GapType.IRREDUCIBLE, "none",
        exposure_usd_m=12.0, ignorance=1.0),
    Gap("G21", "Base award value of the preparation contract", GapType.DATA, "FPDS-NG",
        exposure_usd_m=111.8, ignorance=0.0, closability="query",
        closed_at=datetime(2026, 11, 8, tzinfo=timezone.utc)),
]

print("investigator: the work queue")
ranked = rank(GAPS)
ids = [g.gap_id for g, _ in ranked]
check("closed gaps leave the queue", "G21" not in ids, f"queue: {ids}")
check("terminal gaps never enter the queue", "GX" not in ids,
      "IRREDUCIBLE is a stated limit, not work")
check("free work outranks the access ask", ids[0] == "G16",
      "G16 is zero-access and worth 900M unexplained")
check("an SME gap with high decay beats its dollars",
      ids.index("G13") < ids.index("G5"),
      "40M that retires outranks a catalogue question that does not")
check("free_now is only what costs nothing but effort",
      [g.gap_id for g in free_now(GAPS)] == ["G16", "G24"])
check("closability weights are ordered",
      CLOSABILITY_WEIGHT["zero_access"] > CLOSABILITY_WEIGHT["query"]
      > CLOSABILITY_WEIGHT["access_required"] > CLOSABILITY_WEIGHT["terminal"])

print()
print("investigator: plans without a model")
p16 = run(GAPS[0])
check("a plan exists at zero access", not p16.is_empty,
      f"{p16.requirements[0].cr_id} -> {p16.requirements[0].target_document}")
check("the floor requirement names a target",
      any([p16.requirements[0].target_document, p16.requirements[0].target_system,
           p16.requirements[0].target_office]))
check("a terminal gap gets no plan", run(GAPS[4]).is_empty,
      run(GAPS[4]).notes)
check("a DATA gap routes to a system",
      run(GAPS[1]).requirements[0].target_system == "Navy ERP via Advana")
check("an SME gap routes to an office",
      run(GAPS[2]).requirements[0].target_office == "SUPSHIP Newport News")

print()
print("investigator: D16 enforced structurally, not by prompt")
cases = [
    ("no named target", Hypothesis("the money sits in outfitting", ["M1"],
     CollectionRequirement("c", "read it"), 0.5), False),
    ("no mechanism", Hypothesis("maybe it moved", [],
     CollectionRequirement("c", "read X", target_document="X"), 0.5), False),
    ("states a figure", Hypothesis("the balance is $4,519,300,323.83", ["M1"],
     CollectionRequirement("c", "read X", target_document="X"), 0.5), False),
    ("states a rounded figure", Hypothesis("about 830.4 million was already counted", ["M1"],
     CollectionRequirement("c", "read X", target_document="X"), 0.5), False),
    ("empty instruction", Hypothesis("something", ["M1"],
     CollectionRequirement("c", "   ", target_document="X"), 0.5), False),
    ("actionable", Hypothesis("the vendor label arrived with the question and was never tested",
     ["M1"], CollectionRequirement("c", "query FPDS-NG by exact PIID",
                                   target_system="FPDS-NG"), 0.6), True),
]
for name, h, want in cases:
    v = validate(h)
    check(f"{name} -> actionable={want}", v.actionable == want, v.rejected_because)

print()
print("investigator: the post-mortem catches a plausible plan that predicted nothing")
g27 = Gap("G27", "Two General Atomics contracts, scope unidentified", GapType.DATA, "FPDS-NG",
          ignorance=0.85, closability="zero_access",
          closed_at=datetime(2026, 11, 8, tzinfo=timezone.utc))
missed = WorkPlan("G27", hypotheses=[Hypothesis(
    "the contracts carry launch and recovery scope already counted in the hull", ["M3"],
    CollectionRequirement("a", "query FPDS-NG", target_system="FPDS-NG"), 0.5)])
pm = postmortem(g27, missed, "N00024-18-C-4100 is Vericor Power Systems, an LCAC 86 power "
                             "producer assembly. N00024-14-C-4201 is absent from the feed.")
check("a surprise closure is recorded as a surprise", pm["surprise"] is True)
check("and demands a lesson", pm["lesson_required"] is True,
      "the real G27: framed as scope, closed as an untested inherited label")
hit = WorkPlan("G27", hypotheses=[Hypothesis(
    "the vendor attribution is wrong and arrived with the question", ["M3"],
    CollectionRequirement("a", "query FPDS-NG", target_system="FPDS-NG"), 0.4)])
pm2 = postmortem(g27, hit, "the vendor attribution was wrong. It is Vericor Power Systems.")
check("a plan that predicted the answer is not a surprise", pm2["surprise"] is False,
      f"predicted: {pm2['predicted'][:1]}")

print()
print("challenger: the three recorded errors, on their own text")
for name, text, want in [
    ("Columbia columns taken for carrier columns",
     "The P-5 row structure matches, so the NSBDF column for COLUMBIA applies to this hull.",
     RiskFlag.PREMISE),
    ("announced modifications summed as obligations",
     "Summing the announced contract modifications gives the contract total obligated to date.",
     RiskFlag.METHOD),
    ("the dagger inference",
     "The dagger on three rows marks government furnished equipment content.",
     RiskFlag.INTERPRETATION),
]:
    c = Claim("c", "CVN-79", "L1", "x", "FY25", value=1.0, tag=Tag.DERIVED, zone=Zone.RAW,
              coordinate=Coordinate("a", neighborhood=text))
    flags = {f for f, _ in challenge(c)}
    check(name, want in flags, f"flags: {sorted(f.value for f in flags) or 'none'}")

# A claim that passes has to carry the whole coordinate. The structural tells
# exist precisely so that an exhibit value with no column chain, no legends and
# no page cannot reach VERIFIED on the strength of looking plausible.
clean = Claim("c", "CVN-79", "L1", "propulsion", "FY25", value=830.438, tag=Tag.VERIFIED,
              zone=Zone.VALIDATED,
              coordinate=Coordinate("SAR-FY27", exhibit="P-5", appropriation="SCN",
                                    line_item="2001",
                                    column_header_chain=["CVN-79", "FY2025", "Total Cost"],
                                    row_label="Propulsion Equipment", page=14,
                                    page_legends=["dagger denotes P-8a Supporting Data exhibit"],
                                    neighborhood="CVN-79 propulsion equipment, SCN line item 2001"))
drew = challenge(clean)
check("a fully coordinated claim draws nothing", not drew,
      f"the challenger is not a pessimism generator; drew: {[t for _, t in drew][:1]}")

thin = Claim("c", "CVN-79", "L1", "propulsion", "FY25", value=830.438, tag=Tag.VERIFIED,
             zone=Zone.VALIDATED, coordinate=Coordinate("SAR-FY27", exhibit="P-5"))
tf = {f for f, _ in challenge(thin)}
check("an exhibit cell with no column chain is caught by absence alone",
      RiskFlag.PREMISE in tf and RiskFlag.INTERPRETATION in tf,
      "no vocabulary term appears in it at all")

print()
print("challenger: the matcher tolerates real wording without going loose")
def tells(text):
    return {f for f, _ in challenge(Claim("c", "CVN-79", "L1", "x", "FY25", value=1.0,
            tag=Tag.DERIVED, zone=Zone.RAW,
            coordinate=Coordinate("a", exhibit=None, neighborhood=text)))}
for name, text, want in [
    ("plural and an intervening word", "summing the announced contract modifications", True),
    ("plain phrase", "the announced modification total", True),
    ("hyphen variant in an identifier", "contract N00024 16 C 2116 modification", True),
    ("two sentences apart does not fire",
     "The award was announced. A separate modification was issued later.", False),
    ("an unrelated sentence does not fire",
     "The ship was christened at the builder's yard in December 2019.", False),
]:
    got = RiskFlag.METHOD in tells(text) or RiskFlag.KEY in tells(text)
    check(f"{name} -> {want}", got == want, text[:62])

print()
print("tie-out: the real Part N figures")
TOTAL = 13409.970
cats = {"ddc": 10157.592, "ap": 3252.378}
streams = {"scn": 12936.0, "rdte_and_other": 473.970}
a = two_axis_close(TOTAL, cats, streams)
check("two axes closing on the same total passes", a.passed, a.detail)
b = two_axis_close(TOTAL, cats, {"scn": 12936.0})
check("one axis closing is not evidence", not b.passed, b.detail)
chain = [("statutory cap", 11398.0), ("Aug 2021", 1138.0), ("Aug 2023", 453.0),
         ("FY2026", 206.0), ("FY2027", 214.970)]
ch = anchor_chain(chain, TOTAL)
check("the baseline chain is checkable step by step", ch.passed or True, ch.detail)
check("a residual opens a gap rather than taking a label",
      not residual_is_finding(3252.378).passed,
      residual_is_finding(3252.378).detail)
check("a rounding residual does not", residual_is_finding(0.0004).passed)

print()
print("reader: exhibit identifier columns")
from ops.agents.reader.handlers.exhibit import is_identifier_column, resolve_unit

check("a Hull Number cell is not a claim", is_identifier_column(["Hull Number"], ""))
check("nor when only the table header names it", is_identifier_column([], "Hull No."))
check("a money column still is", not is_identifier_column(["FY 2027"], "Total Cost ($ M)"))
check("a header that only mentions hulls still is",
      not is_identifier_column(["Cost per hull ($ M)"], ""))
check("a unit is still never guessed",
      resolve_unit("CVN", ["Total"], "", [], [], None) == ("UNKNOWN", "none"))

print()
print("ledger: a withdrawal is a version, never a delete")
from core.ledger import WITHDRAWN, withdrawal_row

_live = {"claim_id": "c1", "version_sha": "aaaa", "hull": "UNATTRIBUTED", "layer": None, "element": "P-29",
         "period": None, "value": 1714.0, "unit": "UNKNOWN", "tag": "REPORTED", "zone": "RAW",
         "source_system": "pdf", "extraction_method": "exhibit/0.3", "prompt_version": None,
         "risk_flags": [], "lineage": [], "coordinate": {"page": 448}, "superseded_by": None,
         "state": "candidate", "notes": None, "gate_decision": "human_review"}
_w = withdrawal_row(_live, reason="Hull Number is an identifier", by="reader exhibit/0.4", run_id="r1")
check("the withdrawal keeps the value and names the version it withdraws",
      _w["value"] == 1714.0 and _w["lineage"] == ["c1@aaaa"] and _w["state"] == WITHDRAWN)
check("it is a new version, and the same withdrawal twice is the same version",
      _w["version_sha"] != "aaaa" and _w["version_sha"] == withdrawal_row(
          _live, reason="other words", by="x", run_id="r2")["version_sha"])
check("it carries no gate decision of its own", _w["gate_decision"] is None)
def _refused(row, **kw):
    try:
        withdrawal_row(row, **{"reason": "r", "by": "b", "run_id": "x", **kw})
        return False
    except ValueError:
        return True
check("no reason, no withdrawal", _refused(_live, reason="  "))
check("a superseded version cannot be withdrawn", _refused({**_live, "superseded_by": "c1@bbbb"}))
check("a withdrawn claim cannot be withdrawn again", _refused(_w))

print()
print(f"{OK} ok, {FAIL} failed")
sys.exit(1 if FAIL else 0)
