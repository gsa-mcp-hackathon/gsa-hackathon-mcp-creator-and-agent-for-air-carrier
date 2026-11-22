"""The gate. Risk-tiered routing, not a score.

D26 rules out a composite score for the same reason it rules out a composite
risk index: a single number hides the mechanism and the mechanism is the whole
useful content. So this is a routing table evaluated on three independent axes.

  exposure     dollars the claim bears on, as a share of the subject total
  confidence   the existing Tag plus c value. Weakest-link already propagates it
  risk         PREMISE / INTERPRETATION / METHOD / KEY. Independent of confidence

The bottom rows are what keep the gate from becoming the bottleneck. Most
candidates are small and uncertain and should accumulate silently. Review
capacity goes to high exposure and to flagged risk, nothing else.
"""
import re
from dataclasses import dataclass
from enum import Enum

from ..contracts import Claim, Tag
from ..contracts.risk import RiskFlag

# Share of the subject total above which a claim is material.
# Expressed as a share so it transfers to the next hull without retuning.
MATERIALITY_FLOOR = 0.01            # 1 percent
SUBJECT_TOTAL_USD_M = 13409.970     # CVN-79, PB2027 Total Ship Estimate

# Each hull is measured against its own total, from the latest P-5c that
# carries it (app/data/curated/impact.json, figures tse_*_last). A hull with
# no total here cannot be measured for materiality, so the gate refuses to
# route its figures (R9) instead of borrowing CVN-79's total. Mirrored in
# seed/gate.yaml `subjects`; checks/test_gate.py fails if the two drift.
SUBJECT_TOTALS_USD_M = {
    "CVN-78": 12907.0,      # PB2018 P-5c, p.47, the last book carrying CVN-78
    "CVN-79": SUBJECT_TOTAL_USD_M,  # PB2027 P-5c, p.95
    "CVN-80": 14457.915,    # PB2027 P-5c, p.95
    "CVN-81": 15615.934,    # PB2027 P-5c, p.137
}


def normalize_hull(hull: str) -> str:
    """'cvn 79', 'CVN79' and 'CVN-79' are one hull."""
    m = re.fullmatch(r"\s*([A-Za-z]{2,4})[\s-]?(\d{1,3})\s*", hull or "")
    return f"{m.group(1).upper()}-{int(m.group(2))}" if m else (hull or "").strip().upper()


def subject_total(hull: str) -> float | None:
    """The total a hull's figures are measured against, or None when unknown."""
    return SUBJECT_TOTALS_USD_M.get(normalize_hull(hull))


# Risk flags that force human review regardless of anything else.
# These are the three error classes that have actually occurred and that
# announce themselves to nobody. INTERPRETATION is handled separately because
# below the floor it is cheap to leave as a candidate.
ALWAYS_REVIEW = {RiskFlag.PREMISE, RiskFlag.METHOD, RiskFlag.KEY}


class Decision(str, Enum):
    PROMOTE = "promote"                 # machine-promotable
    PROMOTE_IF_TIED_OUT = "promote_if_tied_out"   # conditional on the two-axis close
    HUMAN_REVIEW = "human_review"
    HOLD_CANDIDATE = "hold_candidate"   # stays a candidate, no review, costs nothing
    GAP = "gap"                         # UNKNOWN never promotes


@dataclass
class GateRoute:
    decision: Decision
    reason: str
    rule: str
    exposure_share: float
    flags: list[str]


def _exposure_share(claim: Claim) -> float:
    total = subject_total(claim.hull)
    if claim.value is None or not total:
        return 0.0
    return abs(claim.value) / total


def route(claim: Claim, violations: list | None = None) -> GateRoute:
    """Route a claim.

    Pass the result of policy.evaluate() as `violations`. A claim with an
    outstanding policy violation never promotes, whatever its tag or size:
    the decision log is enforcement, not advice.
    """
    flags = sorted(f.value for f in claim.risk_flags)
    share = _exposure_share(claim)
    material = share >= MATERIALITY_FLOOR

    if violations:
        names = ", ".join(sorted({v.decision for v in violations}))
        return GateRoute(Decision.HUMAN_REVIEW,
                         f"outstanding policy violation: {names}.",
                         "R-1", share, flags)

    if claim.value is not None and subject_total(claim.hull) is None:
        return GateRoute(Decision.GAP,
                         f"no subject total for {normalize_hull(claim.hull)}: materiality "
                         "cannot be measured, so the figure is not routed. Register the "
                         "hull's total from its own P-5c first.",
                         "R9", share, flags)

    if share > 1.0:
        return GateRoute(Decision.HUMAN_REVIEW,
                         f"claim is {share:.0%} of its own subject total. "
                         "A part larger than the whole is a premise signal.",
                         "R8", share, flags)

    if claim.tag is Tag.UNKNOWN:
        return GateRoute(Decision.GAP,
                         "UNKNOWN never promotes. It becomes a typed gap with an executor.",
                         "R0", share, flags)

    hard = claim.risk_flags & ALWAYS_REVIEW
    if hard:
        return GateRoute(Decision.HUMAN_REVIEW,
                         f"{', '.join(sorted(f.value for f in hard))} set. "
                         "These classes are internally coherent when wrong.",
                         "R1", share, flags)

    if RiskFlag.INTERPRETATION in claim.risk_flags:
        if material:
            return GateRoute(Decision.HUMAN_REVIEW,
                             "INTERPRETATION set above the materiality floor.",
                             "R2", share, flags)
        return GateRoute(Decision.HOLD_CANDIDATE,
                         "INTERPRETATION set below the floor. Cheap to leave as a candidate.",
                         "R3", share, flags)

    if material and claim.tag is not Tag.VERIFIED:
        return GateRoute(Decision.HUMAN_REVIEW,
                         f"material at {share:.1%} of the hull and tagged {claim.tag.value}.",
                         "R4", share, flags)

    if material:
        return GateRoute(Decision.PROMOTE_IF_TIED_OUT,
                         "material, VERIFIED, unflagged. Requires the two-axis close.",
                         "R5", share, flags)

    if claim.tag is Tag.VERIFIED:
        return GateRoute(Decision.PROMOTE, "below the floor, VERIFIED, unflagged.",
                         "R6", share, flags)

    return GateRoute(Decision.HOLD_CANDIDATE,
                     "below the floor and below VERIFIED. Accumulates without review.",
                     "R7", share, flags)
