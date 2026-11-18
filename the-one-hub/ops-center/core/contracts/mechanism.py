"""A mechanism: a rule about how carrier money works.

Distinct from a claim. A claim is a value. A mechanism is a rule that tells you
where to look, when a value is impossible, and why two layers differ.

Example, from BACKGROUND section 3: NAVSEA's system of record is STARS for FY10
and prior funding and Navy ERP for FY11 forward, with ship construction held to
1 April 2011. That is not a number and it reshaped the whole L2 design.

A mechanism without an establishing passage is an opinion and does not enter.
"""
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Mechanism:
    mechanism_id: str
    statement: str                    # the rule, one or two sentences
    passage: str                      # verbatim text that establishes it
    artifact_id: str | None           # where the passage came from
    citation: str                     # human-readable source
    scope: list[str] = field(default_factory=list)   # layers, hulls or systems it governs
    established_at: datetime | None = None
    confidence: float = 0.0
    consequence: str = ""             # what it changes. Used by the gate to rank review
    superseded_by: str | None = None  # marked, never deleted. Prior reasoning needs rechecking
    decision_ref: str | None = None   # LOG D-number where this became policy
