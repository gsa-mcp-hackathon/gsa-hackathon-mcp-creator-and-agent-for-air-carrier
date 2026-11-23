"""Return models for the analyst_ tools.

Each analyst_ tool declares one of these as its return type, so its MCP
listing carries an output schema: a client and its model can see what comes
back before calling. The same convention as the One Hub server
(the-one-hub/ops-center/mcp/hub_models.py).

The tools still return plain dicts; FastMCP checks each result against the
schema before it leaves the server. So the rules here are:

* A field is required only when the code sets it on every path.
* A value read from a source row is left loosely typed or nullable.
* Every model allows extra keys, so a tool that adds a field, and the
  source_notice a result can carry, still validate.

Every answer is grade LEAD: a scored hypothesis, never a figure.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

LEAD_ID = "Keep it: analyst_record_outcome needs it to record the confirmed answer."


class _Out(BaseModel):
    model_config = ConfigDict(extra="allow")


class _Lead(_Out):
    """What every logged lead carries."""

    engine: str = Field(description="Engine version that produced the answer.")
    question: str = Field(description="The question this answer addresses.")
    grade: str = Field(description="Always LEAD.")
    caveat: str = Field(description="How the answer may and may not be used.")
    lead_id: str = Field(description=LEAD_ID)
    lead_logged: bool = Field(description="False when the answer could not be saved as a lead.")


class PlanResult(_Out):
    ready: list[Any] = Field(description="Skills that can run on the clues in hand.")
    waiting: list[Any] = Field(description="Skills waiting for a clue, and which one.")


class ProfileResult(_Out):
    recognized: dict[str, Any] = Field(description="Record fields mapped to known data elements.")
    unrecognized_fields: dict[str, Any] = Field(description="Fields read as free text.")
    present: list[str] = Field(description="Critical data elements the record has.")
    missing_critical: list[dict[str, Any]] = Field(
        description="Each missing element: element, why, authoritative_in, held_by.")
    plan: PlanResult


class InvestigationResult(_Lead):
    profile: dict[str, Any] = Field(description="Which critical data elements are present or missing.")
    cases: list[dict[str, Any]] = Field(
        description="Top three: rank, case, label, confidence, basis, for, against.")
    clue_chain: list[dict[str, Any]] = Field(
        description="Each clue: id, key, value, from, parent, strength, citation.")
    perfect_match: bool = Field(description="True when the top case is deterministic and needs no review.")
    data_elements_recovered: dict[str, Any]
    still_missing: list[dict[str, Any]] = Field(
        description="Each element still missing, with its collection_requirement.")
    human_review: dict[str, Any] = Field(description="required, with reasons when the answer is weak.")
    flags: list[str]
    subject_key: str = Field(description="Stable key of the investigated record.")


class SourcesResult(_Out):
    documents_by_category: dict[str, Any]
    structured_sources: list[dict[str, Any]]
    knowledge_graph: dict[str, Any] = Field(description="Counts of contracts, vendors, accounts.")
    skills: list[dict[str, Any]] = Field(description="Each skill: skill, runs_on, reads.")
    not_loaded: list[str] = Field(description="Sources the analyst cannot read.")
    grades: dict[str, str]


class DocumentSearchResult(_Out):
    query: str
    n: int = Field(description="Hits found before the limit was applied.")
    hits: list[dict[str, Any]] = Field(description="Each hit: document, page, grade, category, snippet.")
    note: str


class TraceResult(_Out):
    entity: str
    resolved: list[Any] = Field(description="Knowledge-graph node ids the entity resolved to.")
    results: list[dict[str, Any]] = Field(
        description="Per node: the node, its links, the documents that mention it, co-occurring hulls.")
    note: str


class OpenQuestionsResult(_Out):
    piid: str
    grade: str
    n_transactions: int
    file_c_periods: list[Any]
    residual_periods: list[dict[str, Any]] = Field(
        description="File C periods that do not tie to FPDS, largest gap first, each with next.")
    tied_periods: list[Any]
    uncovered_months: list[dict[str, Any]] = Field(description="Months no File C submission covers.")
    largest_unattributed_transactions: list[dict[str, Any]]
    proven_by_arithmetic: int
    caveat: str
    as_of: str = Field(description="UTC time the source data was loaded.")


class TransactionLeadResult(_Lead):
    subject: dict[str, Any] = Field(description="piid, mod, date, amount, key of the transaction.")
    options: list[dict[str, Any]] = Field(
        description="Top three accounts: rank, loa, confidence, evidence, collection requirement.")
    none_of_these: float = Field(description="Probability that no listed account is the answer.")
    n_candidates: int
    kind: str
    as_of: str


class WindowLeadResult(_Lead):
    n_transactions: int
    gross_amount: str
    net_amount: str
    options: list[dict[str, Any]] = Field(
        description="Top three accounts: rank, tas, appropriation, expected_share.")
    none_of_these: float
    kind: str
    as_of: str


class ResidualLeadResult(_Lead):
    file_c: str = Field(description="File C total for the period, in dollars.")
    fpds_in_window: str = Field(description="FPDS obligations in the same window, in dollars.")
    gap: str
    facts: list[dict[str, Any]] = Field(description="Proven arithmetic facts, each with its proof.")
    options: list[dict[str, Any]] = Field(description="Up to three scored causes; empty when the period ties.")
    none_of_these: float
    kind: str
    as_of: str


class BacktestResult(_Out):
    piid: str
    engine: str
    n_tx_labels: int
    n_period_labels: int
    reading: str = Field(description="How to read the scores: with their n, against the baseline.")
    as_of: str
    model: dict[str, Any] = Field(description="Label counts and the weights that moved from the priors.")


class ModelStatusResult(_Out):
    engine: str
    labels: dict[str, Any] = Field(description="Label counts: deduced, confirmed_tx, confirmed_residual.")
    n_cases: int
    moved_from_prior: dict[str, Any]
    weights: dict[str, Any]
    priors: dict[str, Any]
    accepted_evidence: dict[str, str] = Field(description="Evidence types analyst_record_outcome accepts.")
    as_of: str


class OutcomeResult(_Out):
    outcome_id: str
    lead_id: str
    truth: str
    rank_of_truth: int | None = Field(description="Where the confirmed answer ranked; null if unranked.")
    was_top1: bool
    model: dict[str, Any]
    note: str
