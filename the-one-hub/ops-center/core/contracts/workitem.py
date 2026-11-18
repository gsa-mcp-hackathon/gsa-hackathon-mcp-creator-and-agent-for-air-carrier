"""The work register row and the state machine.

The pipeline is not a DAG. Discovery is re-entrant: a promoted claim or a new
mechanism can invalidate earlier work, which marks affected rows STALE and
re-enters them. Jobs are workers that claim rows in a state.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class State(str, Enum):
    OPEN_QUESTION = "open_question"
    COLLECTION_REQUIRED = "collection_required"
    MATERIAL_IN_HAND = "material_in_hand"
    CANDIDATE = "candidate"
    GATED = "gated"
    HUMAN_REVIEW = "human_review"
    PROMOTED = "promoted"
    STALE = "stale"               # re-enters at the tie-out stage
    CLOSED = "closed"
    TERMINAL = "terminal"         # IRREDUCIBLE


@dataclass
class WorkItem:
    work_id: str
    kind: str                     # gap | artifact | claim | variance | reconciliation
    ref_id: str                   # id in the owning store
    state: State
    owner_agent: str | None = None
    claimed_at: datetime | None = None
    exposure_usd_m: float = 0.0
    attempts: int = 0
    last_error: str | None = None
    history: list[str] = field(default_factory=list)
