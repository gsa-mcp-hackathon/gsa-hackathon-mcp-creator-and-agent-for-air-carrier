"""The decision log as executable policy.

D1 to D34 live in ../../../LOG.md Part I. That file is the home and carries the
reasoning. This module carries only the subset that can be evaluated against a
claim at admission time, so that a rule is enforced rather than remembered.

Every rejection names its D-number. A reviewer reading a rejection sees which
decision it violated and can go read the reasoning.
"""
from collections.abc import Callable
from dataclasses import dataclass

from ..contracts import Claim, Tag, Zone
from ..contracts.risk import RiskFlag


class PolicyViolation(Exception):
    def __init__(self, decision: str, message: str):
        self.decision = decision
        self.message = message
        super().__init__(f"{decision}: {message}")


# D33. The only acceptable sources for an obligation figure.
# A press release is an announcement, never a record.
OBLIGATION_SOURCE_WHITELIST = {
    "FPDS-NG",
    "USASPENDING_TRANSACTIONS",
    "NAVY_ERP",
    "STARS_HCM",
    "STARS_FL",
    "MOCAS",
}

# D34 / G28 / E-15. Collision pairs that any partial match merges silently.
COLLISION_PAIRS = [
    ("N00024-09-C-2116", "N00024-16-C-2116"),
]
# G27, closed 2026-11-08 against the FPDS-NG ATOM feed. Still do-not-use, but now for an
# established reason rather than an open question. N00024-18-C-4100 is Vericor Power Systems,
# an LCAC 86 power producer assembly, not this hull and not the vendor it was carried under.
# N00024-14-C-4201 is absent from the feed entirely, verified against a control query.
NOT_THIS_HULL = ["N00024-14-C-4201", "N00024-18-C-4100"]
UNRESOLVED_DO_NOT_USE = NOT_THIS_HULL  # name kept; callers predate the closure


@dataclass
class Policy:
    decision: str
    statement: str
    predicate: Callable[[Claim], bool]   # True means the claim passes
    message: str


def _d3(c: Claim) -> bool:
    return bool(c.period) and c.discovered_at is not None


def _d4(c: Claim) -> bool:
    # A lead may never occupy a figure position. Leads contribute selectors,
    # structure and hypotheses. Measures come from authoritative sources only.
    return not (c.zone is Zone.LEADS and c.value is not None and c.tag in (Tag.VERIFIED, Tag.DERIVED))


def _d27(c: Claim) -> bool:
    # If a number cannot be drilled, it is not displayed.
    if c.value is None:
        return True
    return c.coordinate is not None and c.coordinate.artifact_id != ""


def _d33(c: Claim) -> bool:
    if "obligat" not in c.element.lower():
        return True
    return c.source_system in OBLIGATION_SOURCE_WHITELIST


def _d34(c: Claim) -> bool:
    text = f"{c.element} {c.notes}"
    for a, b in COLLISION_PAIRS:
        tail = a[-4:]
        if tail in text and a not in text and b not in text:
            return False          # a bare trailing-digit reference
    return not any(p in text for p in UNRESOLVED_DO_NOT_USE)


def _interpretation_capture(c: Claim) -> bool:
    # A value read from an exhibit must carry the legends present on its page.
    # E-12: the dagger's definition was on the page and was not captured.
    if c.coordinate is None or c.coordinate.exhibit is None:
        return True
    if not c.coordinate.page_legends:
        c.risk_flags.add(RiskFlag.INTERPRETATION)
    return True


POLICIES: list[Policy] = [
    Policy("D3", "Every fact carries its period and its discovery date, separately.",
           _d3, "period and discovered_at are both required"),
    Policy("D4", "Public and secondary sources generate leads only.",
           _d4, "a lead cannot occupy a figure position"),
    Policy("D27", "Drill-through is a requirement. If it cannot be drilled, it is not displayed.",
           _d27, "no coordinate chain, so the value is not displayable"),
    Policy("D33", "Obligation figures come from the obligation record only.",
           _d33, f"source_system must be one of {sorted(OBLIGATION_SOURCE_WHITELIST)}"),
    Policy("D34", "Identifier collisions are hard exclusions, not reviewer memory.",
           _d34, "partial contract-number match, or an unresolved PIID"),
    Policy("E12", "An exhibit value carries the legends printed on its page.",
           _interpretation_capture, "page legends missing"),
]


# A policy violation is not only a rejection, it is evidence of a risk class.
# Without this map the gate never sees the violation and can still promote the
# claim, which is what the first smoke test run did with the 2116 collision.
VIOLATION_FLAGS: dict[str, RiskFlag] = {
    "D33": RiskFlag.METHOD,
    "D34": RiskFlag.KEY,
    "E12": RiskFlag.INTERPRETATION,
    "D4": RiskFlag.PREMISE,
}


def evaluate(claim: Claim, *, raise_on_fail: bool = False) -> list[PolicyViolation]:
    """Run every policy. Returns the violations; raises on the first if asked.

    D15 is not enforced here because it is not a rejection: a second value for
    an occupied cell creates a conflict pair rather than overwriting. That is
    handled by the claim writer, not the gate.
    """
    out: list[PolicyViolation] = []
    for p in POLICIES:
        try:
            ok = p.predicate(claim)
        except Exception as exc:  # noqa: BLE001 - a policy must never crash the pipeline
            ok = False
            out.append(PolicyViolation(p.decision, f"policy error: {exc}"))
            continue
        if not ok:
            v = PolicyViolation(p.decision, p.message)
            flag = VIOLATION_FLAGS.get(p.decision)
            if flag is not None:
                claim.risk_flags.add(flag)
            if raise_on_fail:
                raise v
            out.append(v)
    return out
