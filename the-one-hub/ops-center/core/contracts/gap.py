"""A gap and its Collection Requirement.

BLUEPRINT section 12. Every unknown carries a type and the type determines who
works it. A gap is never assigned back to the sponsor.

A lead's only legitimate output is a Collection Requirement. D16.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class GapType(str, Enum):
    DOCUMENT = "DOCUMENT"        # answer exists in a retrievable document. No access needed
    DATA = "DATA"                # answer exists in a system we can query, once access exists
    SME = "SME"                  # answer exists only in institutional memory
    CATALOG = "CATALOG"          # requires enumerating from inside an environment
    IRREDUCIBLE = "IRREDUCIBLE"  # no record, no living memory. Terminal


@dataclass
class CollectionRequirement:
    """A specific actionable instruction. Never a figure.

    Retrieve this document, from this system or this office, for this period
    and this account.
    """
    cr_id: str
    instruction: str
    target_document: str | None = None
    target_system: str | None = None
    target_office: str | None = None
    period: str | None = None
    account: str | None = None
    originating_lead_id: str | None = None
    exposure_usd_m: float = 0.0      # queue is ranked on this


@dataclass
class Gap:
    gap_id: str                       # G1..G28 and onward. Home is ../LOG.md Part II
    question: str
    gap_type: GapType
    executor: str                     # named office, role or process
    blocks: str = ""                  # what it blocks
    exposure_usd_m: float = 0.0       # dollar value of variance left unexplained
    ignorance: float = 1.0            # 1.0 = nothing known. Inverse of best confidence held
    closability: str = "unknown"      # zero_access | query | access_required | sme | terminal
    decay_risk: str = "unknown"       # SME gaps rank on decay alongside dollars
    opened_at: datetime | None = None
    closed_at: datetime | None = None
    resolution: str = ""
    collection_requirements: list[CollectionRequirement] = field(default_factory=list)
