"""Typed parameters for this server's tools.

Closed sets are enums so a model cannot invent a value the data does
not contain. Values are the exact spellings found in the source.
"""

from __future__ import annotations

from enum import Enum


class ExtractorValue(str, Enum):
    """Allowed values for ExtractorValue.

    A sentinel member such as ANY means no filter. An
    optional enum needs one: rendering the parameter as
    nullable would put an anyOf union in the schema,
    which some providers do not honor.
    """

    ANY = "any"
    PDFPLUMBER_LINES_V1 = "pdfplumber-lines/v1"
    PDFPLUMBER_TEXT_V1 = "pdfplumber-text/v1"


class KindValue(str, Enum):
    """Allowed values for KindValue.

    A sentinel member such as ANY means no filter. An
    optional enum needs one: rendering the parameter as
    nullable would put an anyOf union in the schema,
    which some providers do not honor.
    """

    ANY = "any"
    ARTIFACT = "artifact"
    CLAIM = "claim"
    GAP = "gap"
    VARIANCE = "variance"


class OwnerAgentValue(str, Enum):
    """Allowed values for OwnerAgentValue.

    A sentinel member such as ANY means no filter. An
    optional enum needs one: rendering the parameter as
    nullable would put an anyOf union in the schema,
    which some providers do not honor.
    """

    ANY = "any"
    COLLECT = "collect"
    INVESTIGATOR = "investigator"
    READER = "reader"


class StateValue(str, Enum):
    """Work item states in aircarrier_work (distinct values read 2026-11-18).

    ANY means no filter. OPEN means every state except closed and promoted.
    human_review holds the claims waiting for a person; open_question
    (needs investigation) and collection_required (needs data requested)
    are the live gaps and variances.
    """

    ANY = "any"
    OPEN = "open"
    CLOSED = "closed"
    COLLECTION_REQUIRED = "collection_required"
    HUMAN_REVIEW = "human_review"
    MATERIAL_IN_HAND = "material_in_hand"
    OPEN_QUESTION = "open_question"
    PROMOTED = "promoted"


TERMINAL_STATES = ("closed", "promoted")


def state_clause(state_column: str, state: "StateValue") -> tuple[str, list]:
    """SQL predicate and parameters for a state filter; ('', []) for ANY."""
    if state is StateValue.ANY:
        return "", []
    if state is StateValue.OPEN:
        return f"{state_column} NOT IN (?, ?)", list(TERMINAL_STATES)
    return f"{state_column} = ?", [state.value]


class DetailValue(str, Enum):
    """How much of each record to return.

    summary is the default and keeps answers small enough for an agent to
    read; full returns every column the source has.
    """

    SUMMARY = "summary"
    FULL = "full"


class RelValue(str, Enum):
    """Edge relations in aircarrier_kg_edges (distinct values read 2026-11-08).

    ANY means no filter. Contract-to-hull relations are prime_contract_for,
    partial_scope_for, excluded_from, resolved_not_this_hull and collides_with.
    """

    ANY = "any"
    ALIAS_OF = "alias_of"
    ALLOCATION_OPEN_IN = "allocation_open_in"
    APPROPRIATION = "appropriation"
    AWARDED_TO = "awarded_to"
    COLLIDES_WITH = "collides_with"
    CONTINUES = "continues"
    ENFORCED_IN = "enforced_in"
    EXCLUDED_FROM = "excluded_from"
    EXECUTED_BY = "executed_by"
    FLAGGED = "flagged"
    FUNDS = "funds"
    HAS_HAZARD = "has_hazard"
    HAS_TABLE = "has_table"
    HAS_TYPE = "has_type"
    INSTANCE_OF = "instance_of"
    LINE_ITEM = "line_item"
    LINE_OF = "line_of"
    MENTIONS = "mentions"
    NAME_COLLIDES_WITH = "name_collides_with"
    PART_OF = "part_of"
    PARTIAL_SCOPE_FOR = "partial_scope_for"
    PRIME_CONTRACT_FOR = "prime_contract_for"
    RECORDS = "records"
    REFERENCES = "references"
    RESOLVED_BY = "resolved_by"
    RESOLVED_NOT_THIS_HULL = "resolved_not_this_hull"
    SUPERSEDED_BY = "superseded_by"
    VIOLATION_RAISES = "violation_raises"
    YIELDED = "yielded"


class ValueKindValue(str, Enum):
    """Allowed values for ValueKindValue.

    A sentinel member such as ANY means no filter. An
    optional enum needs one: rendering the parameter as
    nullable would put an anyOf union in the schema,
    which some providers do not honor.
    """

    ANY = "any"
    DASH = "dash"
    EMPTY = "empty"
    NUMBER = "number"
    TEXT = "text"
