"""Return models for the mcp-aircarrier-hub tools.

Each hub_ tool declares one of these as its return type, so its MCP listing
carries an output schema: a client and its model can see what comes back
before calling. The fields named here are the ones a caller acts on. Every
model allows extra keys, so a tool that adds a field, and the source_notice a
result can carry, still validate.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class _Out(BaseModel):
    model_config = ConfigDict(extra="allow")


class CorpusHit(_Out):
    citation: str = Field(description="Document and page, e.g. 'PB2027 SCN p.95'.")
    grade: str = Field(description="Source grade: authoritative or secondary.")
    zone: str = Field(description="L (lead), R (raw authoritative) or V (validated).")
    page: int | None = Field(None, description="PDF page of the passage.")
    artifact_id: str = Field(description="The document's id in the corpus.")
    text: str = Field(description="The passage. A lead until read in place on the page.")
    score: float = Field(description="Retrieval score; higher is closer.")


class SearchCorpusResult(_Out):
    query: str
    authoritative_only: bool
    hits: list[CorpusHit]
    rule: str = Field(description="How to use a hit before it becomes a figure.")


class CorpusStatusResult(_Out):
    index: dict[str, Any] = Field(description="Whether the index is built, and its size.")
    corpus: dict[str, Any] = Field(description="Artifacts and bytes, by bucket and route.")
    note: str = ""


class TableListResult(_Out):
    tables: list[str] = Field(description="Names to pass to hub_get_table.")
    note: str = ""


class TableResult(_Out):
    source: Any = Field("", description="The document and section the table comes from.")
    rows: Any = Field(None, description="The rows; a table stored as a list comes back here.")


class MechanismHit(_Out):
    store: str
    text: str


class MechanismsResult(_Out):
    query: str
    hits: list[MechanismHit]
    home: str = Field("", description="Where the full rule set lives.")


class KeysetResult(_Out):
    # With a section named, only that section comes back.
    ship: dict[str, Any] | None = Field(None, description="Hull, name, class, program.")
    budget: dict[str, Any] | None = Field(None, description="Appropriation, line items.")
    collisions: Any = Field(None, description="Contract numbers one digit from CVN-79's.")


class HazardsResult(_Out):
    known: list[str] = Field(description="Exhibits with recorded hazards.")


class GapRow(_Out):
    id: str = Field(description="Gap id, e.g. G14.")
    title: str
    status: str
    type: str
    executor: str = Field(description="The office or role that can close it.")
    exposure_usd_m: float | None = Field(None, description="Dollars it bears on, $M.")
    closability: str
    priority: float | None = None


class RankGapsResult(_Out):
    ranking: str = Field(description="How the rows are ordered.")
    open: int
    rows: list[GapRow]


class CollectionRequirementRow(_Out):
    instruction: str = Field(description="What to retrieve, in one instruction.")
    target_document: str | None = None
    target_system: str | None = None
    target_office: str | None = None
    period: str | None = None
    account: str | None = None


class PlanGapResult(_Out):
    gap_id: str
    question: str
    terminal: bool = Field(description="True when nothing more can be collected.")
    requirements: list[CollectionRequirementRow]
    rule: str


class WorkItem(_Out):
    id: str
    title: str
    priority: float | None = None
    first_step: str
    target: str | None = None


class NextWorkResult(_Out):
    open: int
    work_now: list[WorkItem] = Field(description="Work that needs no new access.")
    access_ask: list[WorkItem] = Field(description="Work that needs access to ask for.")
    rule: str


class PolicyViolation(_Out):
    decision: str = Field(description="The decision-log entry it breaks, e.g. D34.")
    message: str


class CheckClaimResult(_Out):
    decision: Literal["promote", "promote_if_tied_out", "human_review",
                      "hold_candidate", "gap"] = Field(
        description="A routing decision, never a promotion: a person or a "
                    "deterministic rule acts on it.")
    rule: str = Field(description="The gate route that decided, e.g. R5 or R9.")
    reason: str
    exposure_share: float = Field(description="The figure as a share of its hull's total.")
    risk_flags: list[str] = Field(description="PREMISE, INTERPRETATION, METHOD or KEY.")
    policy_violations: list[PolicyViolation]
    tells: list[str] = Field(description="Why each flag was set.")
    note: str = ""


class Tell(_Out):
    flag: str
    why: str


class ChallengeTextResult(_Out):
    subject: str
    flags: list[str]
    tells: list[Tell]
    clean: bool = Field(description="True when no falsification pattern matched.")


class TieOutResult(_Out):
    passed: bool = Field(description="True only when both axes close to the rounding.")
    detail: str
    residual: float = Field(description="The larger of the two residuals, $M.")
    residual_verdict: str = ""


class AnchorChainResult(_Out):
    passed: bool
    detail: str
    residual: float = Field(description="Published total minus the chain's sum, $M.")


class CollectionRequirementResult(CollectionRequirementRow):
    gap_id: str | None = None
    zone: str = Field(description="L: a draft lead, never a figure.")
    note: str = ""
