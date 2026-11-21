"""The deterministic checks, as functions rather than scripts.

The scripts in checks/ carry figures inline. That separates the number from its
provenance at the moment the script is written, which is the same failure class
as the submarine columns. In the ops center the figures come from the claim
table with their lineage attached, and these functions take them as arguments.
"""
from dataclasses import dataclass
from decimal import Decimal

# A residual at or above this opens a gap (residual_is_finding).
RESIDUAL_FLOOR_USD_M = 1.0
# A tie-out closes only to the exhibit's own rounding: half the last printed digit of a
# figure printed in $ millions to three decimals. 2026-11-20 (B2): the tie-outs used the
# $1.0M gap floor with float sums, so a $970,000 residual on $13,409.970M "closed".
TIEOUT_TOLERANCE_USD_M = Decimal("0.0005")


def _d(v) -> Decimal:
    """Exact decimal from a figure as written, so 0.1 + 0.2 is 0.3."""
    return v if isinstance(v, Decimal) else Decimal(str(v))


@dataclass
class CheckResult:
    passed: bool
    rule: str
    detail: str
    residual: float = 0.0


def two_axis_close(total: float, axis_a: dict[str, float], axis_b: dict[str, float]) -> CheckResult:
    """A reconciliation does not promote on one axis.

    One axis closing is arithmetic. Two independent decompositions closing on
    the same total is evidence. Part N.1 closes on cost category and Part N.2
    closes on funding stream, both to zero.
    """
    t = _d(total)
    ra = t - sum((_d(v) for v in axis_a.values()), Decimal(0))
    rb = t - sum((_d(v) for v in axis_b.values()), Decimal(0))
    ok = abs(ra) <= TIEOUT_TOLERANCE_USD_M and abs(rb) <= TIEOUT_TOLERANCE_USD_M
    return CheckResult(ok, "two_axis_close",
                       f"axis_a residual {ra:+.3f}, axis_b residual {rb:+.3f}", float(max(abs(ra), abs(rb))))


def anchor_chain(steps: list[tuple[str, float]], expected_total: float) -> CheckResult:
    """Each step named, each increment attributable, ending at the published total.

    Part N.3: statutory cap, plus the Aug 2021 baseline increase, plus the
    Aug 2023 increment, plus the FY2026 and FY2027 increments, equals the
    FY2027 Total Ship Estimate exactly.
    """
    got = sum((_d(v) for _, v in steps), Decimal(0))
    r = _d(expected_total) - got
    return CheckResult(abs(r) <= TIEOUT_TOLERANCE_USD_M, "anchor_chain",
                       f"chain sums to {got:,.3f} against {_d(expected_total):,.3f}", float(r))


def residual_is_finding(residual: float, floor: float = RESIDUAL_FLOOR_USD_M) -> CheckResult:
    """D33 corollary. A large unexplained residual is a finding, not a remainder.

    The 4.18x error was knowable without new data: the residual it created had
    been written down and given a narrative label instead of a test. A residual
    above the floor opens a gap automatically.
    """
    ok = abs(residual) < floor
    return CheckResult(ok, "residual_is_finding",
                       "within floor" if ok else
                       f"residual {residual:+,.3f} opens a gap rather than taking a label",
                       residual)
