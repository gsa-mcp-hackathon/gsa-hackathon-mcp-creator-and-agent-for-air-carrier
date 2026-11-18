#!/usr/bin/env python3
"""Regression test for the policy set and the gate.

Every case is one of the three errors actually recorded in
ring0/RING0_CVN79.md N.7, or a real figure from Part N. The point of the suite
is that the gate keeps catching the errors that have already happened, which
is the honest limit of what it can be built to catch. The gate miss log is how
that limit moves.

This test found a real defect on its first run: a claim that had already failed
D34 still routed to promote, because policy violations were not reaching the
gate. B11.

    python3 checks/test_gate.py
"""
import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.contracts import Claim, Coordinate, Tag, Zone                    # noqa: E402
from core.policy.decisions import evaluate                                 # noqa: E402
from core.policy.gate import Decision, route                               # noqa: E402
from ops.agents.challenger.run import challenge                            # noqa: E402
from ops.agents.tieout.run import anchor_chain, residual_is_finding, two_axis_close  # noqa: E402

NOW = datetime.datetime(2026, 11, 8)
FAILURES: list[str] = []


def expect(label: str, claim: Claim, want: Decision, *, run_challenger: bool = False) -> None:
    if run_challenger:
        for flag, _tell in challenge(claim):
            claim.risk_flags.add(flag)
    violations = evaluate(claim)
    got = route(claim, violations)
    ok = got.decision is want
    print(f"  [{'ok  ' if ok else 'FAIL'}] {label}")
    print(f"         -> {got.decision.value} [{got.rule}] {got.reason}")
    if not ok:
        FAILURES.append(f"{label}: wanted {want.value}, got {got.decision.value}")


def main() -> int:
    print("gate")

    expect("verified P-5c category, fully coordinated",
           Claim(claim_id="C1", hull="CVN-79", layer="L1", element="Propulsion Equipment",
                 period="FY2013", value=2041.582, discovered_at=NOW, tag=Tag.VERIFIED,
                 confidence=0.98, zone=Zone.VALIDATED,
                 coordinate=Coordinate("A-SCN-PB27", "P-5c", "1611N", "2001",
                                       ["FY2013", "CVN 79"], "Propulsion Equipment", 1,
                                       ["(dagger) indicates the presence of a P-8a"])),
           Decision.PROMOTE_IF_TIED_OUT)

    expect("N.7 Error 1: Columbia-class columns taken for carrier columns",
           Claim(claim_id="C2", hull="CVN-79", layer="L1", element="Basic Construction",
                 period="FY2013", value=5451.193, discovered_at=NOW, tag=Tag.ESTIMATE,
                 confidence=0.55, zone=Zone.RAW,
                 coordinate=Coordinate("A-SCN-FY24", exhibit="P-5",
                                       row_label="Basic Construction",
                                       neighborhood="Less AP Transfer to NSBDF FY2017; "
                                                    "Large Aperture Bow array hydrophones; "
                                                    "COLUMBIA Class Submarines")),
           Decision.HUMAN_REVIEW, run_challenger=True)

    expect("N.7 Error 3: announced modifications summed as obligations",
           Claim(claim_id="C3", hull="CVN-79", layer="L5",
                 element="obligations N00024-09-C-2116", period="FY2009-FY2025",
                 value=1080.0, discovered_at=NOW, tag=Tag.DERIVED, confidence=0.92,
                 zone=Zone.RAW, source_system="DOD_CONTRACT_ANNOUNCEMENTS",
                 coordinate=Coordinate("A-ANN")),
           Decision.HUMAN_REVIEW)

    expect("E-15: the 2116 collision, matched on trailing digits",
           Claim(claim_id="C4", hull="CVN-79", layer="L5",
                 element="contract 2116 obligations", period="FY2019", value=14917.738,
                 discovered_at=NOW, tag=Tag.VERIFIED, confidence=0.95, zone=Zone.RAW,
                 source_system="FPDS-NG", coordinate=Coordinate("A-FPDS"),
                 notes="matched on trailing 2116"),
           Decision.HUMAN_REVIEW)

    expect("D3: no discovery date",
           Claim(claim_id="C5", hull="CVN-79", layer="L1", element="Ordnance",
                 period="FY2013", value=1149.651, tag=Tag.VERIFIED, confidence=0.9,
                 zone=Zone.RAW, coordinate=Coordinate("A-SCN-PB27")),
           Decision.HUMAN_REVIEW)

    expect("pressure valve: small and uncertain, nobody looks at it",
           Claim(claim_id="C6", hull="CVN-79", layer="L1", element="HM&E", period="FY2013",
                 value=30.302, discovered_at=NOW, tag=Tag.ESTIMATE, confidence=0.4,
                 zone=Zone.RAW, coordinate=Coordinate("A-SCN-PB27")),
           Decision.HOLD_CANDIDATE)

    expect("UNKNOWN never promotes, it becomes a gap",
           Claim(claim_id="C7", hull="CVN-79", layer="L1", element="AWE shipset",
                 period="FY2013", value=None, discovered_at=NOW, tag=Tag.UNKNOWN,
                 zone=Zone.LEADS),
           Decision.GAP)

    print("\ntie-out, on the real Part N figures")
    cats = {"Plan Costs": 898.865, "Basic Construction/Conversion": 8463.156,
            "Change Orders": 432.065, "Electronics": 263.359,
            "Propulsion Equipment": 2041.582, "HM&E": 30.302,
            "Ordnance": 1149.651, "Other Cost": 130.990}
    streams = {"Advance Procurement": 3327.050, "Subsequent Full Funding": 7504.668,
               "Cost to Complete": 2087.300, "Net P-1 Funding": 490.952}
    chain = [("statutory cap", 11398.0), ("Aug 2021 baseline", 1300.0),
             ("Aug 2023 increment", 238.0), ("FY2026 increment", 260.0),
             ("FY2027 increment", 213.970)]

    for name, res in [("two-axis close", two_axis_close(13409.970, cats, streams)),
                      ("anchor chain", anchor_chain(chain, 13409.970))]:
        print(f"  [{'ok  ' if res.passed else 'FAIL'}] {name}: {res.detail}")
        if not res.passed:
            FAILURES.append(name)

    r = residual_is_finding(3252.378)
    print(f"  [{'ok  ' if not r.passed else 'FAIL'}] residual opens a gap: {r.detail}")
    if r.passed:
        FAILURES.append("residual_is_finding did not flag the 3,252.378 residual")

    print()
    if FAILURES:
        for f in FAILURES:
            print(f"FAILURE: {f}")
        return 1
    print("all checks pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
