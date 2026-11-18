"""A variance: the product. BLUEPRINT section 9, D6.

Not the cost figure. The difference between two layers' figures for the same
hull and period, with its cause attached. A difference with a documented cause
is finished product. Only UNEXPLAINED is incomplete.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class CauseCategory(str, Enum):
    """Closed set. Each is a real mechanism rather than a label.

    Event and narrative material adds no category. A hearing is not a mechanism.
    What a hearing supplies is evidence for a cause. D24.
    """
    TIMING = "TIMING"
    SCOPE = "SCOPE"
    ALLOCATION = "ALLOCATION"
    CAPITALIZATION = "CAPITALIZATION"
    INTER_ENTITY = "INTER_ENTITY"
    ERROR = "ERROR"
    UNEXPLAINED = "UNEXPLAINED"


@dataclass
class Variance:
    variance_id: str
    hull: str
    period: str
    left_claim_id: str
    right_claim_id: str
    difference: float
    materiality: str                  # above or below the floor, with the floor recorded
    cause: CauseCategory = CauseCategory.UNEXPLAINED
    evidence_claim_ids: list[str] = field(default_factory=list)
    mechanism_ids: list[str] = field(default_factory=list)
    determined_by: str | None = None
    determined_at: datetime | None = None
    notes: str = ""
