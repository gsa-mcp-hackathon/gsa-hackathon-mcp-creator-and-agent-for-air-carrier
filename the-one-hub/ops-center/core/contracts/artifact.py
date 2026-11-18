"""A source artifact: one document, extract or dataset, registered on arrival."""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class SupplyRoute(str, Enum):
    """How the artifact reached us.

    This is a field rather than a note because D33 routes on it: externally
    supplied data gets a mandatory re-derivation pass, not a reconciliation pass.
    The question asked of it is what method produced what we hold, not whether
    it agrees with what we hold.
    """
    SELF_COLLECTED = "self_collected"
    EXTERNALLY_SUPPLIED = "externally_supplied"
    SCHEDULED_FETCH = "scheduled_fetch"
    HUMAN_UPLOAD = "human_upload"


@dataclass
class Artifact:
    artifact_id: str
    uri: str                       # UC Volume path
    origin_url: str | None         # where it came from, if public
    sha256: str
    retrieved_at: datetime         # D3: when we got it
    as_of: str | None              # D3: the period the document describes
    supply_route: SupplyRoute
    supplied_by: str | None        # named person for EXTERNALLY_SUPPLIED
    document_kind: str             # exhibit | prose_authority | transaction | unknown
    profile_id: str | None         # link into the source catalog once profiled
    bytes: int = 0
    notes: str = ""
    tags: list[str] = field(default_factory=list)
