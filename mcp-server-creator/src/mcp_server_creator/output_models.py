"""Return models for the creator_ tools.

Each creator_ tool declares one of these as its return type, so its MCP
listing carries an output schema: a client and its model can see what comes
back before calling. The same convention as the One Hub server
(the-one-hub/ops-center/mcp/hub_models.py).

The tools still return plain dicts; FastMCP checks each result against the
schema before it leaves the server. A creator_ tool reports a failure as a
body with ``error`` and ``hint`` (error_contract.py marks it isError), and
several tools answer in stages. So every field here is optional: a model
names what a path can return, and no path is refused for leaving a field
out. Every model allows extra keys.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _Out(BaseModel):
    model_config = ConfigDict(extra="allow")

    error: str | None = Field(
        None, description="Set when the call failed; the result is then isError."
    )
    hint: str | None = Field(None, description="What to do about the error.")


class _Design(_Out):
    design_id: str | None = Field(
        None, description="Handle of the stored design. Empty when spec_json is used."
    )
    spec: dict[str, Any] | None = Field(
        None,
        description="The full specification, returned when no design_id is in use.",
    )
    next_step: str | None = Field(None, description="The call to make next.")


class CheckEnvironmentResult(_Out):
    environment: str | None = None
    workspace_host: str | None = None
    capabilities: Any = Field(
        None, description="Each platform feature: supported, verify or unsupported."
    )
    source_kinds: Any = Field(
        None, description="Which data-source kinds are usable, verify-first or blocked."
    )
    blocking: list[str] | None = Field(
        None, description="Source kinds that cannot work in this environment."
    )
    probe: dict[str, Any] | None = Field(
        None, description="What this server could confirm about its own workspace."
    )
    next_step: str | None = None


class StartDesignResult(_Design):
    blocking_gaps: list[Any] | None = Field(
        None, description="Questions that must be answered before generating."
    )
    gaps: list[dict[str, Any]] | None = Field(None, description="Every open question.")
    derived: dict[str, Any] | None = Field(
        None, description="Names derived from the spec: server, package, app, dataset."
    )
    details: list[Any] | None = Field(
        None,
        description="Field-by-field validation errors, when the spec is not valid.",
    )


class AddDataSourceResult(_Design):
    source: str | None = Field(None, description="Name of the profiled source.")
    sources_on_design: list[str] | None = None
    summary: dict[str, Any] | None = Field(
        None, description="Field roles, enum candidates and observations."
    )
    observations: list[Any] | None = None
    required_grants: list[Any] | None = Field(
        None, description="Unity Catalog grants the generated server will need."
    )
    inspection: dict[str, Any] | None = Field(
        None, description="Whether the live table was read, and as which identity."
    )
    details: list[Any] | None = None


class DesignToolsResult(_Design):
    tools: list[dict[str, Any]] | None = Field(
        None,
        description="Each proposed tool: name, title, goal, pattern, source, params.",
    )
    tool_count: int | None = None
    by_source: dict[str, list[str]] | None = Field(
        None, description="Tool names grouped by the source they read."
    )
    design_notes: list[Any] | None = None
    review_first: str | None = Field(
        None, description="What to confirm with the user before generating."
    )


class GenerateProjectResult(_Out):
    design_id: str | None = None
    server_name: str | None = None
    package_name: str | None = None
    index: Any = Field(None, description="Every generated file with its size.")
    totals: dict[str, Any] | None = Field(
        None, description="file_count and total_bytes."
    )
    warnings: list[Any] | None = None
    next_steps: list[Any] | None = None


class WriteProjectResult(_Out):
    dry_run: bool | None = Field(
        None,
        description="True when nothing was written and would_write lists the files.",
    )
    root: str | None = Field(
        None, description="Where the project was, or would be, written."
    )
    written: list[Any] | None = None
    would_write: list[Any] | None = None
    file_count: int | None = None
    total_bytes: int | None = None
    warnings: list[Any] | None = None
    collisions: list[Any] | None = Field(
        None, description="Files that already exist; nothing was written."
    )
    next_step: str | None = None


class ReviewServerResult(_Out):
    design_id: str | None = None
    subject: str | None = None
    verdict: str | None = Field(None, description="The review's overall verdict.")
    scores: dict[str, Any] | None = Field(
        None, description="Score per rubric dimension."
    )
    weakest_dimensions: list[str] | None = None
    blockers: list[dict[str, Any]] | None = Field(
        None, description="Findings that must be fixed before deployment."
    )
    findings: list[dict[str, Any]] | None = None
    passed_checks: list[Any] | None = None
    next_step: str | None = None


class DeployServerResult(_Out):
    status: str | None = Field(
        None,
        description=(
            "blocked, needs_approval, creating, starting, deploying, live or failed. "
            "Call again until live."
        ),
    )
    app_name: str | None = None
    security: dict[str, Any] | None = Field(
        None, description="The review verdict and what the app will be able to read."
    )
    plan: dict[str, Any] | None = Field(
        None, description="What will be created, shown first."
    )
    approval: dict[str, Any] | None = Field(
        None, description="What to ask the user, and the token that confirms it."
    )
    url: str | None = None
    mcp_url: str | None = Field(None, description="The deployed server's MCP endpoint.")
    next_step: str | None = None


class ListLibraryResult(_Out):
    skills: list[dict[str, Any]] | None = Field(
        None, description="Each skill: name, description, references."
    )
    knowledge: list[dict[str, Any]] | None = Field(
        None, description="Each knowledge document: slug, title, size."
    )
    start_with: str | None = None
    phases: list[str] | None = None
    note: str | None = None


class LoadDocumentResult(_Out):
    kind: str | None = Field(None, description="skill, skill_reference or knowledge.")
    name: str | None = None
    content: str | None = Field(None, description="The document text.")
    description: str | None = None
    references: list[Any] | None = None
    reference: str | None = None
