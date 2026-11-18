"""A claim: one value, with everything needed to defend it or retire it.

This is the load-bearing contract. Every other store points at it.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from .risk import RiskFlag


class Tag(str, Enum):
    VERIFIED = "VERIFIED"      # read from a primary document or the obligation record
    DERIVED = "DERIVED"        # arithmetic from verified inputs
    ESTIMATE = "ESTIMATE"      # modelled
    UNKNOWN = "UNKNOWN"        # no public value. Never promotes. Becomes a gap
    REJECTED = "REJECTED"      # tested and failed. Kept, never deleted


class Zone(str, Enum):
    """D16. Promotion between zones is always a separate logged event."""
    LEADS = "L"            # public and secondary. No join path to canonical
    RAW = "R"              # primary material collected, not yet trusted for arithmetic
    VALIDATED = "V"         # tied out by a named person or a deterministic rule
    CERTIFIED = "C"         # fit to present outside the team


@dataclass
class Coordinate:
    """Where the value physically sits.

    page_legends is not optional. E-12 happened because a dagger's definition
    was printed on the same page as the value and was not captured with it.
    An extraction that cannot fill page_legends sets RiskFlag.INTERPRETATION.
    """
    artifact_id: str
    exhibit: str | None = None          # e.g. "P-5c"
    appropriation: str | None = None    # e.g. "1611N"
    line_item: str | None = None        # e.g. "2001"
    column_header_chain: list[str] = field(default_factory=list)  # e.g. ["FY2013", "CVN 79"]
    row_label: str | None = None
    page: int | None = None
    page_legends: list[str] = field(default_factory=list)
    neighborhood: str = ""       # surrounding text, retained for falsification


@dataclass
class Claim:
    claim_id: str

    # Subject. Cross-check is only possible where two sources resolve to the
    # same subject key, so this is the join that decides whether the system works.
    hull: str                    # CVN-79
    layer: str                   # L0..L5
    element: str                 # cost category, funding stream, contract, account
    period: str                  # D3: the period the figure describes

    value: float | None = None   # UNKNOWN claims carry no value and are still claims
    unit: str = "USD_M"

    discovered_at: datetime | None = None   # D3: separate field from period
    coordinate: Coordinate | None = None

    tag: Tag = Tag.UNKNOWN
    confidence: float = 0.0
    zone: Zone = Zone.LEADS

    # D33: obligation claims may only name FPDS-NG, the federal spending
    # transaction record, or the accounting system. Enforced in policy.decisions.
    source_system: str | None = None

    extraction_method: str = ""   # handler name and version
    prompt_version: str | None = None
    mlflow_trace_id: str | None = None

    risk_flags: set[RiskFlag] = field(default_factory=set)
    lineage: list[str] = field(default_factory=list)   # parent claim ids

    superseded_by: str | None = None
    state: str = "candidate"
    notes: str = ""
