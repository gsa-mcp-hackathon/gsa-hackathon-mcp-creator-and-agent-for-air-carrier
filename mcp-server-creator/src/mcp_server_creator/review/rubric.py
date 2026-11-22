"""Score a server specification against the design and security rubric.

Every check here is mechanical: it reads the specification and reports what
is true, so the same review runs the same way twice. Judgment belongs in the
conversation that follows, not in the scoring.

Dimensions follow `knowledge/judging_rubric.md`, which maps them onto the GSA
hackathon's criteria.
"""

from __future__ import annotations

import re

from mcp_server_creator import environments
from mcp_server_creator.generators import toolcode
from mcp_server_creator.models import (
    DataClassification,
    DataModality,
    DeploymentTarget,
    FieldRole,
    Finding,
    QueryPattern,
    ReviewReport,
    ServerSpec,
    Severity,
    SourceKind,
)

LIST_PATTERNS = {
    QueryPattern.SEARCH,
    QueryPattern.SEMANTIC_SEARCH,
    QueryPattern.RANK,
}

VAGUE_NAME_TAILS = {
    "data",
    "query",
    "records",
    "api",
    "all",
    "info",
    "stuff",
    "things",
    "results",
}

FORBIDDEN_PARAMS = {
    "url",
    "uri",
    "endpoint",
    "host",
    "sql",
    "statement",
    "path",
    "file_path",
    "filepath",
    "command",
    "script",
}

DIMENSIONS = (
    "goal_orientation",
    "input_design",
    "documentation",
    "context_economy",
    "error_quality",
    "security_posture",
    "evaluation",
    "reproducibility",
    "deployment",
    "environment_fit",
    "honesty",
)


def _penalize(scores: dict[str, int], dimension: str, amount: int) -> None:
    """Reduce one dimension's score, never below zero."""
    scores[dimension] = max(0, scores[dimension] - amount)


def review_spec(spec: ServerSpec) -> ReviewReport:
    """Review a specification and return scored findings."""
    findings: list[Finding] = []
    passed: list[str] = []
    scores = {dimension: 5 for dimension in DIMENSIONS}

    _check_goal_orientation(spec, findings, passed, scores)
    _check_inputs(spec, findings, passed, scores)
    _check_documentation(spec, findings, passed, scores)
    _check_context_economy(spec, findings, passed, scores)
    _check_errors(spec, findings, passed, scores)
    _check_security(spec, findings, passed, scores)
    _check_evaluation(spec, findings, passed, scores)
    _check_reproducibility(spec, findings, passed, scores)
    _check_deployment(spec, findings, passed, scores)
    _check_environment_fit(spec, findings, passed, scores)
    _check_honesty(spec, findings, passed, scores)
    _check_semantics(spec, findings, passed, scores)

    blockers = [f for f in findings if f.severity is Severity.BLOCKER]
    high = [f for f in findings if f.severity is Severity.HIGH]
    average = sum(scores.values()) / len(scores)
    if blockers:
        verdict = (
            f"{len(blockers)} blocker(s) to fix before generating. "
            f"Average score {average:.1f} of 5."
        )
    elif high:
        verdict = (
            f"Generatable, with {len(high)} high-severity finding(s) worth "
            f"fixing first. Average score {average:.1f} of 5."
        )
    elif findings:
        verdict = (
            f"Sound design. {len(findings)} smaller improvement(s) available. "
            f"Average score {average:.1f} of 5."
        )
    else:
        verdict = f"Clean review. Average score {average:.1f} of 5."

    return ReviewReport(
        subject=spec.server_name,
        findings=findings,
        scores=scores,
        passed_checks=passed,
        verdict=verdict,
    )


def _check_goal_orientation(
    spec: ServerSpec,
    findings: list[Finding],
    passed: list[str],
    scores: dict[str, int],
) -> None:
    """Are the tools named after the user's questions?"""
    if not spec.tools:
        findings.append(
            Finding(
                check="tools_exist",
                severity=Severity.BLOCKER,
                summary="The server plans no tools.",
                fix="Run the tool designer before generating.",
                criterion="goal_orientation",
            )
        )
        _penalize(scores, "goal_orientation", 5)
        return

    if len(spec.tools) > 8:
        findings.append(
            Finding(
                check="tool_count",
                severity=Severity.MEDIUM,
                summary=f"{len(spec.tools)} tools is more than a focused server needs.",
                evidence=", ".join(plan.name for plan in spec.tools),
                fix=(
                    "Keep the tools that answer the user's stated questions "
                    "and drop the rest. A model choosing between twelve "
                    "similar tools chooses worse than one choosing between "
                    "five."
                ),
                criterion="goal_orientation",
            )
        )
        _penalize(scores, "goal_orientation", 1)
    else:
        passed.append("tool_count")

    vague = [
        plan.name for plan in spec.tools if plan.name.split("_")[-1] in VAGUE_NAME_TAILS
    ]
    if vague:
        findings.append(
            Finding(
                check="tool_names_are_goals",
                severity=Severity.HIGH,
                summary="Some tool names describe an endpoint, not a question.",
                evidence=", ".join(vague),
                fix=(
                    "Rename each after the question a real user asks. Read "
                    "the name aloud to the person whose job it is: would "
                    "they recognize it?"
                ),
                criterion="goal_orientation",
            )
        )
        _penalize(scores, "goal_orientation", 2)
    else:
        passed.append("tool_names_are_goals")

    unprefixed = [
        plan.name
        for plan in spec.tools
        if not plan.name.startswith(f"{spec.tool_prefix}_")
    ]
    if unprefixed:
        findings.append(
            Finding(
                check="consistent_prefix",
                severity=Severity.LOW,
                summary="Not every tool shares the server's prefix.",
                evidence=", ".join(unprefixed),
                fix=(
                    f"Prefix every tool with '{spec.tool_prefix}_' so the "
                    "surface stays scannable when a client has a dozen "
                    "servers connected."
                ),
                criterion="goal_orientation",
            )
        )
        _penalize(scores, "goal_orientation", 1)
    else:
        passed.append("consistent_prefix")

    missing_goal = [plan.name for plan in spec.tools if len(plan.goal.strip()) < 15]
    if missing_goal:
        findings.append(
            Finding(
                check="tool_goals_stated",
                severity=Severity.MEDIUM,
                summary="Some tools have no stated user goal.",
                evidence=", ".join(missing_goal),
                fix="Write the goal as the user's own question.",
                criterion="goal_orientation",
            )
        )
        _penalize(scores, "goal_orientation", 1)


def _check_inputs(
    spec: ServerSpec,
    findings: list[Finding],
    passed: list[str],
    scores: dict[str, int],
) -> None:
    """Are closed sets enums, and numbers bounded?"""
    free_text_filters: list[str] = []
    unbounded: list[str] = []
    for plan in spec.tools:
        source = spec.source_by_name(plan.source)
        for param in plan.params:
            if param.source_field and not param.enum_values and source:
                field = next(
                    (f for f in source.fields if f.name == param.source_field),
                    None,
                )
                # Only a category is a closed set. An identifier, a date or an
                # amount with few distinct values in a pasted sample is not.
                if (
                    field is not None
                    and field.role in {FieldRole.DIMENSION, FieldRole.FLAG}
                    and field.cardinality_hint is not None
                    and field.cardinality_hint <= 50
                ):
                    free_text_filters.append(f"{plan.name}.{param.name}")
            if param.python_type in {"int", "float"} and param.maximum is None:
                unbounded.append(f"{plan.name}.{param.name}")

    if free_text_filters:
        findings.append(
            Finding(
                check="closed_sets_are_enums",
                severity=Severity.HIGH,
                summary="Low-cardinality filters are exposed as free text.",
                evidence=", ".join(free_text_filters),
                fix=(
                    "Turn each into an enum of the real values. A model "
                    "cannot guess a spelling it has never seen, and this is "
                    "the single biggest accuracy win available."
                ),
                criterion="input_design",
            )
        )
        _penalize(scores, "input_design", 2)
    else:
        passed.append("closed_sets_are_enums")

    if unbounded:
        findings.append(
            Finding(
                check="numbers_are_bounded",
                severity=Severity.MEDIUM,
                summary="Numeric parameters have no maximum.",
                evidence=", ".join(unbounded),
                fix="Add an upper bound so one call cannot request everything.",
                criterion="input_design",
            )
        )
        _penalize(scores, "input_design", 1)
    else:
        passed.append("numbers_are_bounded")

    for source in spec.data_sources:
        if source.modality is DataModality.UNSTRUCTURED:
            continue
        needs_resolver = source.identifiers() and not any(
            plan.pattern is QueryPattern.SEARCH and plan.source == source.name
            for plan in spec.tools
        )
        if needs_resolver:
            findings.append(
                Finding(
                    check="resolver_available",
                    severity=Severity.MEDIUM,
                    summary=(f"'{source.name}' is reachable only by exact identifier."),
                    fix=(
                        "Add a search or resolver tool. Humans say 'Region "
                        "5'; the table says 'GSA FAS AAS REGION 5'."
                    ),
                    criterion="input_design",
                )
            )
            _penalize(scores, "input_design", 1)


def _check_documentation(
    spec: ServerSpec,
    findings: list[Finding],
    passed: list[str],
    scores: dict[str, int],
) -> None:
    """Does every tool docstring have what the model needs?"""
    missing_returns = [plan.name for plan in spec.tools if not plan.returns.strip()]
    if missing_returns:
        findings.append(
            Finding(
                check="returns_documented",
                severity=Severity.HIGH,
                summary="Some tools do not document their return shape.",
                evidence=", ".join(missing_returns),
                fix=(
                    "Name the fields the tool returns. The docstring is the "
                    "only documentation the model gets."
                ),
                criterion="documentation",
            )
        )
        _penalize(scores, "documentation", 2)
    else:
        passed.append("returns_documented")

    no_grain = [s.name for s in spec.data_sources if not s.grain]
    if no_grain:
        findings.append(
            Finding(
                check="grain_recorded",
                severity=Severity.HIGH,
                summary="Some sources do not say what one record represents.",
                evidence=", ".join(no_grain),
                fix=(
                    "Record the grain. One row per modification is not one "
                    "row per award, and a model will miscount."
                ),
                criterion="documentation",
            )
        )
        _penalize(scores, "documentation", 2)
    else:
        passed.append("grain_recorded")

    no_freshness = [
        s.name
        for s in spec.data_sources
        if not s.as_of or s.update_cadence in ("", "unknown")
    ]
    if no_freshness:
        findings.append(
            Finding(
                check="freshness_recorded",
                severity=Severity.MEDIUM,
                summary="Some sources have no as-of date or refresh cadence.",
                evidence=", ".join(no_freshness),
                fix=(
                    "Record both. An agent that believes it has today's "
                    "numbers will state today's numbers."
                ),
                criterion="documentation",
            )
        )
        _penalize(scores, "documentation", 1)
    else:
        passed.append("freshness_recorded")

    undescribed = [
        f"{plan.name}.{param.name}"
        for plan in spec.tools
        for param in plan.params
        if len(param.description.strip()) < 10
    ]
    if undescribed:
        findings.append(
            Finding(
                check="parameters_described",
                severity=Severity.MEDIUM,
                summary="Some parameters have no usable description.",
                evidence=", ".join(undescribed[:8]),
                fix="Say what the parameter selects, and give an example value.",
                criterion="documentation",
            )
        )
        _penalize(scores, "documentation", 1)


def _check_context_economy(
    spec: ServerSpec,
    findings: list[Finding],
    passed: list[str],
    scores: dict[str, int],
) -> None:
    """Do list-shaped tools paginate?"""
    # The principle is that a list-shaped tool bounds its own result size.
    # Pagination is the usual way; a capped count parameter is another, and
    # is the right one for similarity search, where an offset into ranked
    # results means little.
    unbounded = [
        plan.name
        for plan in spec.tools
        if plan.pattern in LIST_PATTERNS
        and not plan.paginated
        and not any(param.maximum is not None for param in plan.params)
    ]
    if unbounded:
        findings.append(
            Finding(
                check="list_tools_bound_their_results",
                severity=Severity.HIGH,
                summary="Some list-shaped tools do not bound their results.",
                evidence=", ".join(unbounded),
                fix=(
                    "Add limit and offset and return total, has_more and "
                    "next_offset, or cap a count parameter with a maximum. A "
                    "tool that returns 500 rows has spent the agent's "
                    "context without answering anything."
                ),
                criterion="context_economy",
            )
        )
        _penalize(scores, "context_economy", 2)
    else:
        passed.append("list_tools_bound_their_results")

    has_dictionary = any(
        plan.pattern is QueryPattern.DESCRIBE_SOURCE for plan in spec.tools
    )
    if not has_dictionary and spec.data_sources:
        findings.append(
            Finding(
                check="dictionary_tool_present",
                severity=Severity.MEDIUM,
                summary="No tool returns the data dictionary.",
                fix=(
                    "Add a describe tool. It is the cheapest accuracy win "
                    "available: the agent stops guessing column semantics "
                    "and allowed values."
                ),
                criterion="context_economy",
            )
        )
        _penalize(scores, "context_economy", 1)
    else:
        passed.append("dictionary_tool_present")


def _check_errors(
    spec: ServerSpec,
    findings: list[Finding],
    passed: list[str],
    scores: dict[str, int],
) -> None:
    """Does every tool teach the model what to do when it fails?"""
    no_hints = [
        plan.name
        for plan in spec.tools
        if not plan.error_hints and plan.pattern is not QueryPattern.DESCRIBE_SOURCE
    ]
    if no_hints:
        findings.append(
            Finding(
                check="error_hints_present",
                severity=Severity.MEDIUM,
                summary="Some tools record no actionable error hint.",
                evidence=", ".join(no_hints),
                fix=(
                    "Write the hint the model needs when the tool cannot "
                    "answer. An error is a turn already spent; make it buy "
                    "something."
                ),
                criterion="error_quality",
            )
        )
        _penalize(scores, "error_quality", 2)
    else:
        passed.append("error_hints_present")


def _check_security(
    spec: ServerSpec,
    findings: list[Finding],
    passed: list[str],
    scores: dict[str, int],
) -> None:
    """The failure modes that exist only because a model is driving."""
    offenders = [
        f"{plan.name}.{param.name}"
        for plan in spec.tools
        for param in plan.params
        if param.name.lower() in FORBIDDEN_PARAMS
    ]
    if offenders:
        findings.append(
            Finding(
                check="no_url_sql_or_path_arguments",
                severity=Severity.BLOCKER,
                summary=("A tool accepts a URL, raw SQL, or a filesystem path."),
                evidence=", ".join(offenders),
                fix=(
                    "Remove it. These three arguments turn a data tool into "
                    "an exfiltration primitive: an injected instruction in "
                    "retrieved content can then name the destination. If one "
                    "is genuinely required, allowlist exact values and "
                    "validate at connection time."
                ),
                criterion="security_posture",
            )
        )
        _penalize(scores, "security_posture", 5)
    else:
        passed.append("no_url_sql_or_path_arguments")

    writers = [plan.name for plan in spec.tools if not plan.read_only]
    if writers and spec.read_only:
        findings.append(
            Finding(
                check="read_only_consistent",
                severity=Severity.HIGH,
                summary=("The server claims to be read-only but plans a write tool."),
                evidence=", ".join(writers),
                fix=(
                    "Either set read_only to false and annotate the tool "
                    "honestly, or remove the write. A read-only annotation "
                    "on a tool that writes is a lie the client will act on."
                ),
                criterion="security_posture",
            )
        )
        _penalize(scores, "security_posture", 2)

    for plan in writers:
        findings.append(
            Finding(
                check="write_tool_confirmation",
                severity=Severity.HIGH,
                summary=f"'{plan}' writes and needs explicit confirmation.",
                fix=(
                    "Require a confirmation argument the model cannot "
                    "default to true, log every write with the caller "
                    "identity, and set destructiveHint honestly."
                ),
                criterion="security_posture",
            )
        )
        _penalize(scores, "security_posture", 1)

    unstructured = [
        source
        for source in spec.data_sources
        if source.modality is DataModality.UNSTRUCTURED
    ]
    if unstructured and not spec.evaluation.include_injection:
        findings.append(
            Finding(
                check="injection_tested",
                severity=Severity.HIGH,
                summary=(
                    "The server returns document text but tests no prompt injection."
                ),
                fix=(
                    "Plant an injection string in an indexed document and "
                    "assert the agent reports it rather than obeying it. "
                    "This is the failure mode unique to retrieval tools."
                ),
                criterion="security_posture",
            )
        )
        _penalize(scores, "security_posture", 2)
    elif unstructured:
        passed.append("injection_tested")

    if spec.pii_present and spec.classification is DataClassification.PUBLIC:
        findings.append(
            Finding(
                check="classification_consistent",
                severity=Severity.HIGH,
                summary=(
                    "The data is marked public but is said to contain "
                    "personal information."
                ),
                fix=(
                    "Reclassify. Classification drives logging rules, the "
                    "read-only posture, and whether a snapshot may be "
                    "committed at all."
                ),
                criterion="security_posture",
            )
        )
        _penalize(scores, "security_posture", 2)

    for source in spec.data_sources:
        if source.kind is SourceKind.REST_API and not source.api_base_url:
            findings.append(
                Finding(
                    check="fixed_api_origin",
                    severity=Severity.BLOCKER,
                    summary=f"'{source.name}' has no fixed API origin.",
                    fix=(
                        "Set api_base_url. The origin must be operator "
                        "controlled, never a tool argument."
                    ),
                    criterion="security_posture",
                )
            )
            _penalize(scores, "security_posture", 3)


def _check_evaluation(
    spec: ServerSpec,
    findings: list[Finding],
    passed: list[str],
    scores: dict[str, int],
) -> None:
    """Does the evaluation have the five ingredients that make it mean anything?"""
    plan = spec.evaluation
    missing: list[str] = []
    if not plan.baseline_without_tools:
        missing.append("a no-tool baseline")
    if not plan.include_decoys:
        missing.append("decoys")
    if not plan.include_no_action:
        missing.append("no-action cases")
    if not plan.include_injection:
        missing.append("an injection case")
    if not plan.include_out_of_scope:
        missing.append("an out-of-scope case")
    if missing:
        findings.append(
            Finding(
                check="evaluation_ingredients",
                severity=Severity.HIGH,
                summary="The evaluation is missing " + ", ".join(missing) + ".",
                fix=(
                    "Turn each on. Without the baseline there is no way to "
                    "say what the server contributed; without decoys and "
                    "no-action cases a server that pattern-matches scores "
                    "the same as one that works."
                ),
                criterion="evaluation",
            )
        )
        _penalize(scores, "evaluation", 2)
    else:
        passed.append("evaluation_ingredients")

    if plan.golden_question_count < 20:
        findings.append(
            Finding(
                check="golden_question_count",
                severity=Severity.MEDIUM,
                summary=(f"{plan.golden_question_count} golden questions is thin."),
                fix=(
                    "Aim for twenty or more: three per tool, one easy, one "
                    "needing a filter choice, one needing two tools composed."
                ),
                criterion="evaluation",
            )
        )
        _penalize(scores, "evaluation", 1)
    if plan.repeats < 3:
        findings.append(
            Finding(
                check="evaluation_repeats",
                severity=Severity.MEDIUM,
                summary=f"{plan.repeats} repeat(s) per question.",
                fix=(
                    "Use three to five. A single run of a stochastic agent "
                    "is an anecdote."
                ),
                criterion="evaluation",
            )
        )
        _penalize(scores, "evaluation", 1)
    if plan.agent_model and plan.agent_model == plan.judge_model:
        findings.append(
            Finding(
                check="distinct_judge_model",
                severity=Severity.MEDIUM,
                summary="The agent and the judge use the same model.",
                fix=(
                    "Judge with a different, usually stronger model. It "
                    "reduces self-preference bias and lets you hold the "
                    "judge fixed while iterating on the agent."
                ),
                criterion="evaluation",
            )
        )
        _penalize(scores, "evaluation", 1)


def _check_reproducibility(
    spec: ServerSpec,
    findings: list[Finding],
    passed: list[str],
    scores: dict[str, int],
) -> None:
    """Can a reviewer clone the repository and run it?"""
    keyless = any(
        source.kind is SourceKind.LOCAL_SNAPSHOT for source in spec.data_sources
    )
    if not keyless and spec.data_sources:
        findings.append(
            Finding(
                check="keyless_path_available",
                severity=Severity.MEDIUM,
                summary="Every source needs credentials to reach.",
                fix=(
                    "Package a small snapshot alongside the live path. A "
                    "reviewer who can clone and run every tool with no "
                    "credentials evaluates the server; one who cannot reads "
                    "the README and guesses."
                ),
                criterion="reproducibility",
            )
        )
        _penalize(scores, "reproducibility", 2)
    elif keyless:
        passed.append("keyless_path_available")


def _check_deployment(
    spec: ServerSpec,
    findings: list[Finding],
    passed: list[str],
    scores: dict[str, int],
) -> None:
    """Will the platform actually recognize and run this?"""
    deployment = spec.deployment
    if deployment.target is not DeploymentTarget.DATABRICKS_APPS:
        return

    if not deployment.app_name.startswith("mcp-"):
        findings.append(
            Finding(
                check="app_name_prefix",
                severity=Severity.BLOCKER,
                summary=(
                    f"The app name '{deployment.app_name}' does not start with 'mcp-'."
                ),
                fix=(
                    "Rename it. AI Playground and Unity Gateway use the "
                    "prefix to recognize an app as an MCP server; without it "
                    "the app deploys and is never offered as an MCP."
                ),
                criterion="deployment",
            )
        )
        _penalize(scores, "deployment", 4)
    else:
        passed.append("app_name_prefix")

    needs_grants = [
        source
        for source in spec.data_sources
        if source.kind
        in {
            SourceKind.UC_TABLE,
            SourceKind.UC_FUNCTION,
            SourceKind.AI_SEARCH_INDEX,
            SourceKind.UC_VOLUME_FILES,
            SourceKind.GENIE_SPACE,
        }
    ]
    undocumented = [s.name for s in needs_grants if not s.required_grants]
    if undocumented:
        findings.append(
            Finding(
                check="grants_recorded",
                severity=Severity.HIGH,
                summary="Some governed sources record no required grants.",
                evidence=", ".join(undocumented),
                fix=(
                    "Record them. The app runs as its own service principal, "
                    "and a server that works locally and returns empty "
                    "results once deployed has almost always missed this."
                ),
                criterion="deployment",
            )
        )
        _penalize(scores, "deployment", 2)
    elif needs_grants:
        passed.append("grants_recorded")

    if needs_grants and not deployment.use_bundle:
        findings.append(
            Finding(
                check="bundle_declared",
                severity=Severity.LOW,
                summary="No asset bundle, so resources are bound by hand.",
                fix=(
                    "Emit databricks.yml. Declaring a warehouse or secret as "
                    "a resource grants it on deploy and keeps the deployment "
                    "reproducible."
                ),
                criterion="deployment",
            )
        )
        _penalize(scores, "deployment", 1)


def _check_honesty(
    spec: ServerSpec,
    findings: list[Finding],
    passed: list[str],
    scores: dict[str, int],
) -> None:
    """Does the design say what it cannot do?"""
    if not spec.out_of_scope:
        findings.append(
            Finding(
                check="scope_declared",
                severity=Severity.MEDIUM,
                summary="Nothing is declared out of scope.",
                fix=(
                    "Name what the server must refuse. A server that answers "
                    "everything confidently cannot be evaluated, and scope "
                    "refusal is scoreable."
                ),
                criterion="honesty",
            )
        )
        _penalize(scores, "honesty", 2)
    else:
        passed.append("scope_declared")

    if not spec.jobs_to_be_done:
        findings.append(
            Finding(
                check="jobs_recorded",
                severity=Severity.BLOCKER,
                summary="No user questions are recorded.",
                fix=(
                    "Collect three to eight questions in the user's own "
                    "words. They become the tool names and the golden "
                    "questions; without them there is nothing to design "
                    "against or measure."
                ),
                criterion="honesty",
            )
        )
        _penalize(scores, "honesty", 3)
    else:
        passed.append("jobs_recorded")

    if not spec.primary_user:
        findings.append(
            Finding(
                check="user_named",
                severity=Severity.MEDIUM,
                summary="No primary user is named.",
                fix=(
                    "Name one person and the task they do by hand today. "
                    "Mission alignment is a judged criterion and it starts "
                    "here."
                ),
                criterion="honesty",
            )
        )
        _penalize(scores, "honesty", 1)

    stubbed = [
        plan.name
        for plan in spec.tools
        for source in [spec.source_by_name(plan.source)]
        if source is not None and not toolcode.is_supported(source.kind, plan.pattern)
    ]
    if stubbed:
        findings.append(
            Finding(
                check="all_tools_implementable",
                severity=Severity.MEDIUM,
                summary=(
                    "Some tools pair a pattern and a source the generator "
                    "cannot implement, so they will be stubs."
                ),
                evidence=", ".join(stubbed),
                fix=(
                    "Either implement them by hand after generating, or "
                    "replace them with a supported pattern for that source."
                ),
                criterion="honesty",
            )
        )
        _penalize(scores, "honesty", 1)


def _tool_name_root(name: str) -> str:
    """'x_filtered' was renamed from 'x' when two questions shared a name."""
    return name.removesuffix("_filtered")


def _stems(text: str) -> set[str]:
    """Four-letter stems of the singular words: 'cities' and 'city' agree."""
    from mcp_server_creator.designer import singular
    from mcp_server_creator.profiling import name_words

    return {singular(w)[:4] for w in name_words(text) if len(w) >= 3}


# Words that narrow what a question counts. A tool mapped to such a question
# needs a filter on a field that records the state.
_QUALIFIERS = frozenset(
    "negative positive complaint complaints urgent open closed late overdue "
    "cancelled canceled failed rejected approved pending unpaid active inactive "
    "expired refunded returned fraudulent flagged delinquent disputed".split()
)


_TIME = frozenset("day days week weeks month months year years quarter quarters "
                  "time period".split())  # fmt: skip
_LISTING = re.compile(
    r"^\s*(show|list|display|give me|get|pull|look up|lookup|find|fetch|retrieve|"
    r"open|view)\b"
)
# 'for a given disaster number', 'by its PIID', 'in a given city': the column
# whose value selects the records. The determiner is required, so 'in Texas'
# is a value and not a key.
_KEYED = re.compile(
    r"\b(?:for|by|in|on|at|with|from)\s+(?:a given|a specific|a particular|"
    r"a single|one|its|their|the|a|an|that|this)\s+([a-z]+(?:\s+[a-z]+)?)"
)
_SHARE = re.compile(r"\b(share|percentage|percent|proportion|fraction)\s+of\b")
_COMPUTING = re.compile(
    r"\b(how many|how much|total|average|sum|count|top|most|least|per|by|daily|"
    r"weekly|monthly|trend|sales|revenue|spend|cost|units)\b"
)


_STOPWORDS = frozenset(
    "the a an of in for to was were did do does is are have has had with and "
    "or on at from which what how many much most".split()
)


def _phrase(q: str, start: int, limit: int = 3) -> list[str]:
    """Up to `limit` words from `start`, stopping at a connective."""
    words: list[str] = []
    for word in re.findall(r"[a-z]+", q[start:])[:limit]:
        if word in _STOPWORDS:
            break
        words.append(word)
    return words


def _fields_named(words: list[str], fields: list) -> list[str]:
    """The non-measure columns a phrase names: those sharing the most stems
    with it, then the most whole words, then the fewest stems it does not
    share. Columns that tie are all returned: 'recipients' names
    recipient_name and recipient_uei alike, and either reading is right.

    Read from the field names directly, never through the designer, so the
    review does not inherit a designer misreading. A period word ('each
    year') names only a period column such as year or fiscalYear.
    """
    from mcp_server_creator.designer import singular
    from mcp_server_creator.profiling import name_words

    asked = _stems(" ".join(words))
    if not asked:
        return []
    whole = {singular(w) for w in words}
    period = words[0] if words and words[0].rstrip("s") in _TIME else ""
    best: list[str] = []
    best_key = (0, 0, 0)
    for field in fields:
        if field.role is FieldRole.MEASURE or field.pii:
            continue
        if period and period.rstrip("s") not in field.name.lower():
            continue
        own = _stems(field.name)
        own_words = {singular(w) for w in name_words(field.name)}
        key = (len(own & asked), len(own_words & whole), -len(own - asked))
        if not key[0] or key < best_key:
            continue
        if key > best_key:
            best, best_key = [], key
        best.append(field.name)
    return best


def _names_measure(words: list[str], fields: list) -> bool:
    """'by total award value' names an amount, not a grouping."""
    asked = _stems(" ".join(words))
    shared = {
        measure: max(
            (
                len(_stems(f.name) & asked)
                for f in fields
                if (f.role is FieldRole.MEASURE) is measure and not f.pii
            ),
            default=0,
        )
        for measure in (True, False)
    }
    return shared[True] > shared[False]


def _group_named(q: str, fields: list) -> list[str]:
    """The columns a question groups by: 'top 10 recipients by value', 'per
    state', 'in each fiscal year', 'by category', 'which cities ... most'."""
    top = re.search(r"\b(?:top|bottom|best|worst)\s+(?:\d+\s+)?([a-z ]+?)\s+by\b", q)
    if top:
        named = _fields_named(top.group(1).split()[-3:], fields)
        if named:
            return named
    for marker in ("per", "each", "by"):
        m = re.search(rf"\b{marker}\s+", q)
        if m is None:
            continue
        words = _phrase(q, m.end())
        if marker == "by" and _names_measure(words, fields):
            continue
        named = _fields_named(words, fields)
        if named:
            return named
    # 'Which cities received the most loans?' ranks cities.
    m = re.search(
        r"\bwhich\s+(?=.*\b(most|highest|largest|top|least|lowest|fewest|biggest)\b)",
        q,
    )
    return _fields_named(_phrase(q, m.end()), fields) if m else []


def _key_named(q: str, source) -> list[str]:
    """The columns a list or lookup question selects records by."""
    fields = list(source.fields) if source is not None else []
    for match in _KEYED.finditer(q):
        named = _fields_named(match.group(1).split(), fields)
        if named:
            return named
    return []


_LOOKUP_VERB = re.compile(
    r"^\s*(get|pull|look up|lookup|find|fetch|retrieve|open|view)\b"
)
_SUPERLATIVE = re.compile(
    r"\b(most|highest|largest|biggest|top|least|lowest|fewest|smallest|best|"
    r"worst|bottom)\b"
)
_EXTREME = re.compile(r"\b(oldest|newest|earliest|latest|youngest|most recent)\b")
_FIGURE = re.compile(r"\b(how many|how much|total|average|sum of|count of|number of)\b")


def _asks_list(q: str, source=None) -> bool:
    """'Show ...', 'Look up ... by its PIID', 'Which investments complete in
    2027?' on a table of investments: records, not a figure."""
    # After a lookup verb 'by' names the key; after 'show' it may group.
    plain = q.replace(" by ", " ") if _LOOKUP_VERB.search(q) else q
    if _LISTING.search(q) and not _COMPUTING.search(plain):
        return True
    which = re.match(r"\s*which\s+([a-z]+)", q)
    if which is None or source is None or _SUPERLATIVE.search(q):
        return False
    return bool(_stems(which.group(1)) & _row_stems(source))


def _lists_for_a_figure(plan, source, question: str | None = None) -> bool:
    """A list of records mapped to 'how many', 'how much' or 'total'."""
    q = (question or plan.goal).lower()
    return (
        plan.pattern is QueryPattern.LOOKUP
        and bool(_FIGURE.search(q))
        and not _asks_list(q, source)
    )


def _row_stems(source) -> set[str]:
    """Stems naming what one row is ('storm_events', 'one row per storm
    event'), without the words every grain sentence uses."""
    if source is None:
        return set()
    text = f"{source.name} {source.title} {source.grain}"
    return _stems(text) - {"one", "row", "rows", "per", "each"}


_STEP = re.compile(
    r"\b(daily|weekly|monthly|quarterly|trend|over time|(per|each|by) "
    r"(day|week|month|quarter)|(day|week|month) (by|over|to) (day|week|month))\b"
)


def _asks_trend(q: str, source) -> bool:
    """A step word of the question's own, outside any column it names."""
    from mcp_server_creator.profiling import name_words

    for field in source.fields if source is not None else []:
        q = q.replace(" ".join(name_words(field.name)), " ")
    return bool(_STEP.search(q))


def _measure_fit(q: str, name: str) -> int:
    """How strongly a question names a measure column: its specific words,
    and initials such as om for 'operations and maintenance'."""
    from mcp_server_creator.profiling import name_words

    generic = {"tota", "amou", "valu", "coun", "numb"}
    fit = len((_stems(name) - generic) & _stems(q))
    long = [w for w in re.findall(r"[a-z]+", q) if len(w) >= 4]
    initials = {
        "".join(w[0] for w in long[i:j])
        for i in range(len(long))
        for j in range(i + 2, min(i + 5, len(long) + 1))
    }
    return fit + sum(1 for w in name_words(name) if 2 <= len(w) <= 4 and w in initials)


def _slots(q: str, source) -> list[str]:
    """What the question itself asks for, as 'kind:columns' strings: a
    grouping, a distinct count ('how many disasters', 'unique event types')
    or a list of records. Columns that fit equally are joined with '|'."""
    found: list[str] = []
    fields = list(source.fields) if source is not None else []
    rows = _row_stems(source)
    grouped = _group_named(q, fields)
    if grouped:
        found.append("group:" + "|".join(grouped))
    # 'number of unique event types': the distinct cue is nearer the column.
    counted = re.search(r"\b(?:distinct|unique|different)\s+", q) or re.search(
        r"\b(?:how many|number of|count of)\s+", q
    )
    if counted:
        # 'unique event types' on storm events counts event_type; 'how many
        # projects' on a table of projects counts rows.
        ahead = _phrase(q, counted.end(), 4)
        # 'how many high risk investments' on a table of investments counts
        # rows: the words before the row's own noun describe it.
        describes_rows = any(_stems(w) & rows for w in ahead[1:])
        # 'distinct recipients won awards': the first word already names a
        # column other than the row's own noun, as the designer reads it.
        if describes_rows and ahead and not (_stems(ahead[0]) & rows):
            first = [
                name
                for name in _fields_named(ahead[:1], fields)
                if (_stems(name) - rows) & _stems(ahead[0])
            ]
            describes_rows = not first
        words = [w for w in ahead[:2] if w.rstrip("s") not in _TIME]
        if describes_rows:
            words = []
        named = [
            name
            for name in (_fields_named(words, fields) if words else [])
            if (_stems(name) - rows) & _stems(" ".join(words))
        ]
        if named:
            found.append("distinct:" + "|".join(named))
    if _asks_list(q, source):
        found.append("list:")
    return found


def _misread(spec: ServerSpec, plan, question: str | None = None) -> list[str]:
    """Ways a computed tool answers a different question from the one it is
    mapped to, read from the question's own words. Each is a confident tool
    that returns a well-formed number for the wrong question."""
    # Hyphens that join words are spaces: 'sub-agency', 'month-over-month'.
    q = re.sub(r"(?<=[a-z])-(?=[a-z])", " ", (question or plan.goal).lower())
    out: list[str] = []
    wants_avg = bool(re.search(r"\b(average|avg|mean)\b", q))
    wants_count = bool(re.search(r"\b(how many|number of|count of|count)\b", q))
    wants_amount = bool(
        re.search(r"\b(how much|total|sum|revenue|sales|spend|spent|amount|"
                  r"dollars?|cost|value|obligated|obligations?|funding|funds)\b", q)
    )  # fmt: skip
    agg = plan.aggregation
    takes = {
        "sum": "a sum",
        "avg": "an average",
        "count": "a count",
        "count_distinct": "a distinct count",
    }[agg]
    counts = agg in ("count", "count_distinct")
    source = spec.source_by_name(plan.source)
    quantity = None
    if source is not None:
        from mcp_server_creator.designer import counted_measure

        quantity = counted_measure(
            q, [f for f in source.fields if f.role is FieldRole.MEASURE and not f.pii]
        )
    # 'average number of offers' averages the offers column; that is not a
    # count of rows either.
    averaged = wants_avg and agg == "avg" and quantity is not None
    if averaged and plan.measure_field == quantity.name:
        pass
    elif quantity is not None and agg != "sum":
        out.append(
            f"{plan.name} takes {takes}; '{plan.goal}' asks for a sum of "
            f"{quantity.name}, not a count of rows"
        )
    elif quantity is not None:
        pass
    elif wants_avg and agg != "avg":
        out.append(f"{plan.name} takes {takes}; '{plan.goal}' asks for an average")
    elif (
        wants_count
        and not wants_amount
        and not counts
        # An aggregate tool returns record_count with its sum and mean, so
        # 'how many and what average' is answered by one call.
        and plan.pattern is not QueryPattern.AGGREGATE
    ):
        out.append(f"{plan.name} takes {takes}; '{plan.goal}' asks how many")
    elif counts and wants_amount and not wants_count:
        out.append(f"{plan.name} counts rows; '{plan.goal}' asks for an amount")
    elif agg == "avg" and not wants_avg:
        out.append(f"{plan.name} averages; '{plan.goal}' does not ask for an average")

    # 'Top 5 products by quantity' asks for a ranking; one total answers a
    # different question (bakehouse, 2026-11-21).
    if (
        re.search(r"\b(top|bottom|best|worst|highest|lowest|rank)\b", q)
        and plan.pattern is QueryPattern.AGGREGATE
    ):
        out.append(f"{plan.name} returns one total; '{plan.goal}' asks for a ranking")

    from mcp_server_creator.designer import RATIO_CUES

    ratio = RATIO_CUES.search(q)
    if ratio and agg in ("sum", "avg"):
        out.append(
            f"{plan.name} takes {takes} of one column; '{plan.goal}' asks for "
            f"a ratio (per {ratio.group(1)})"
        )
    # A ranking returns each group's share of the whole; one total does not.
    if _SHARE.search(q) and plan.pattern is not QueryPattern.RANK:
        out.append(
            f"{plan.name} returns one figure; '{plan.goal}' asks for a share, "
            "which needs a ranking by the column that splits the rows"
        )

    # A qualifier on what is counted ("negative reviews", "open orders")
    # needs a filter on a field that records it; without one the tool counts
    # every row and answers a broader question.
    covered = " ".join(
        [plan.group_field]
        + [p.source_field for p in plan.params]
        + [v for p in plan.params for v in p.enum_values]
    ).lower()
    stateful = re.search(
        r"status|state|flag|priority|type|category|sentiment|rating|score|label",
        covered,
    )
    for word in re.findall(r"[a-z]+", q):
        if word in _QUALIFIERS and word[:4] not in covered and not stateful:
            out.append(
                f"{plan.name} has no filter for '{word}' in '{plan.goal}', so it "
                "counts every row"
            )
            break

    source = spec.source_by_name(plan.source)
    if source is not None and agg in ("sum", "avg") and plan.measure_field:
        named = [
            f.name
            for f in source.fields
            if f.role is FieldRole.MEASURE
            and f.name != plan.measure_field
            and _stems(f.name) & _stems(plan.goal)
        ]
        # 'units' resolves to quantity through the designer's synonyms, so a
        # stem it shares with unitPrice is not a second measure named.
        resolved = quantity is not None and quantity.name == plan.measure_field
        shared = _stems(plan.measure_field) & _stems(plan.goal)
        own = _measure_fit(q, plan.measure_field)
        closer = [n for n in named if _measure_fit(q, n) > own]
        if named and not resolved and (not shared or closer):
            out.append(
                f"{plan.name} adds up {plan.measure_field}; '{plan.goal}' names "
                f"{', '.join(closer or named)}"
            )

    extreme = _EXTREME.search(q)
    if extreme:
        out.append(
            f"{plan.name} returns a figure; '{plan.goal}' asks for the "
            f"{extreme.group(1)} record"
        )

    out += _slot_misreads(plan, q, source, takes)
    out += _step_misreads(plan, q)
    return out


def _slot_misreads(plan, q: str, source, takes: str) -> list[str]:
    """The question's own grouping, distinct count and list request, checked
    against the tool."""
    out: list[str] = []
    agg = plan.aggregation
    slots = _slots(q, source)
    if agg == "count_distinct" and not any(s.startswith("distinct:") for s in slots):
        out.append(
            f"{plan.name} counts distinct {plan.measure_field}; '{plan.goal}' "
            "does not ask for distinct values of it"
        )
    for slot in slots:
        kind, _, columns = slot.partition(":")
        fits = columns.split("|")
        word = fits[0]
        if kind == "group" and plan.pattern is QueryPattern.TREND:
            # 'average daily traffic' is a column; without a step word of its
            # own the question asks for each group, not for a trend.
            if not _asks_trend(q, source):
                out.append(f"{plan.name} returns a trend; '{q}' asks for each {word}")
        elif kind == "group" and plan.group_field not in fits:
            out.append(f"{plan.name} does not group by {word}; '{q}' asks for each")
        elif kind == "distinct" and (
            agg != "count_distinct" or plan.measure_field not in fits
        ):
            out.append(
                f"{plan.name} takes {takes}; '{q}' asks how many distinct {word}"
            )
        elif kind == "list":
            out.append(f"{plan.name} returns a figure; '{q}' asks to list records")
    return out


_STEP_CUES = {
    "daily": "day", "per day": "day", "by day": "day", "each day": "day",
    "weekly": "week", "per week": "week", "by week": "week", "each week": "week",
    "monthly": "month", "per month": "month", "by month": "month",
    "each month": "month", "quarterly": "quarter", "by quarter": "quarter",
    "per quarter": "quarter", "each quarter": "quarter",
}  # fmt: skip


def _step_misreads(plan, q: str) -> list[str]:
    """A trend at a different step from the one the question names."""
    if plan.pattern is not QueryPattern.TREND:
        return []
    asked = {step for cue, step in _STEP_CUES.items() if cue in q}
    if len(asked) == 1 and plan.granularity not in asked:
        return [
            f"{plan.name} is by {plan.granularity}; '{plan.goal}' asks by {asked.pop()}"
        ]
    return []


def _answered_jobs(spec: ServerSpec) -> set[str]:
    """The recorded questions some tool on the design answers as asked."""
    from mcp_server_creator.designer import _job_tool, is_retrieval

    computed = {QueryPattern.RANK, QueryPattern.AGGREGATE, QueryPattern.TREND}
    # A question counts as answered only if the designer, asked again, maps
    # it to a tool that is still on the design. Golden-question seeds are not
    # evidence: unanswered questions are attached to the nearest tool too.
    # The designer's mapping alone is not evidence: the tool on the design must
    # also pass the question-word checks above, which never call the designer.
    by_name = {plan.name: plan for plan in spec.tools}
    readers = {QueryPattern.SEARCH, QueryPattern.SEMANTIC_SEARCH, QueryPattern.LOOKUP}
    answered: set[str] = set()
    keyed: dict[str, list[str]] = {}
    for job in spec.jobs_to_be_done:
        q = job.lower()
        if _asks_list(q):
            keys = [k for s in spec.data_sources for k in _key_named(q, s)]
            if keys:
                keyed[job] = keys
        # The tool the design maps to the question: one built for it (its
        # goal, which is how a reading from the caller arrives), or the one
        # the designer names when asked again.
        mapped = [plan for plan in spec.tools if plan.goal == job]
        for source in spec.data_sources:
            plan, _ = _job_tool(spec, source, job)
            if plan is not None:
                mapped.append(
                    by_name.get(plan.name) or by_name.get(_tool_name_root(plan.name))
                )
        for actual in mapped:
            if actual is None:
                continue
            wrong = (
                _misread(spec, actual, job)
                if actual.pattern in computed
                else _lists_for_a_figure(
                    actual, spec.source_by_name(actual.source), job
                )
            )
            if not wrong:
                answered.add(job)
                break
    # A read question ('what does the exhibit say', 'which documents
    # mention') is answered by a search or lookup, not a computed tool.
    if any(plan.pattern in readers for plan in spec.tools):
        answered |= {job for job in spec.jobs_to_be_done if is_retrieval(job)}
    # 'List excess properties in a given city' needs a reader that takes the
    # city: a search that cannot be narrowed to it does not answer it.
    for job, keys in keyed.items():
        takes_key = any(
            param.source_field in keys
            for plan in spec.tools
            if plan.pattern in readers
            for param in plan.params
        )
        if not takes_key:
            answered.discard(job)
    return answered


def _check_semantics(
    spec: ServerSpec,
    findings: list[Finding],
    passed: list[str],
    scores: dict[str, int],
) -> None:
    """Does each tool compute what its question asks? Shape is not enough."""
    from mcp_server_creator.designer import _coverage_ok, _tokens, is_retrieval

    empty = [
        s.name
        for s in spec.data_sources
        if not s.fields and s.modality is not DataModality.UNSTRUCTURED
    ]
    if empty:
        findings.append(
            Finding(
                check="sources_have_columns",
                severity=Severity.BLOCKER,
                summary="Some sources have no columns, so no tool can read them.",
                evidence=", ".join(empty),
                fix=(
                    "Live inspection did not run or failed. Add each source again "
                    "with schema_text, or fix access, then re-run "
                    "creator_design_tools."
                ),
                criterion="goal_orientation",
            )
        )
        _penalize(scores, "goal_orientation", 5)
    else:
        passed.append("sources_have_columns")

    computed = {QueryPattern.RANK, QueryPattern.AGGREGATE, QueryPattern.TREND}
    id_measures: list[str] = []
    off_groups: list[str] = []
    misread: list[str] = []
    repeated: list[str] = []
    for plan in spec.tools:
        words = plan.name.split("_")
        if any(a == b for a, b in zip(words, words[1:])):
            repeated.append(plan.name)
        source = spec.source_by_name(plan.source)
        if plan.goal in spec.jobs_to_be_done and _lists_for_a_figure(plan, source):
            misread.append(
                f"{plan.name} lists records; '{plan.goal}' asks for a figure"
            )
        if source is None or plan.pattern not in computed:
            continue
        fields = {f.name: f for f in source.fields}
        measure = fields.get(plan.measure_field)
        keyed = plan.aggregation == "count_distinct"  # counting keys is right
        if measure is not None and (
            (measure.role is FieldRole.IDENTIFIER and not keyed) or measure.pii
        ):
            id_measures.append(f"{plan.name} ({plan.measure_field})")
        group = fields.get(plan.group_field)
        if (
            plan.group_field
            and plan.goal in spec.jobs_to_be_done
            and (
                not _stems(plan.group_field) & _stems(plan.goal)
                or (group is not None and not _coverage_ok(group, _tokens(plan.goal)))
            )
        ):
            off_groups.append(f"{plan.name} groups by {plan.group_field}")
        if plan.goal in spec.jobs_to_be_done:
            misread.extend(_misread(spec, plan))

    answered = _answered_jobs(spec)
    unanswered = [job for job in spec.jobs_to_be_done if job not in answered]
    computed_jobs = [
        job
        for job in spec.jobs_to_be_done
        if is_retrieval(job)
        or any(cue in job.lower() for cue in ("how many", "how much", "total",
               "average", "most", "top", "which", "daily", "monthly", "trend",
               "per ", " by ", " each "))
        or _EXTREME.search(job.lower())
        or _SHARE.search(job.lower())
    ]  # fmt: skip
    unanswered = [job for job in unanswered if job in computed_jobs]

    if id_measures:
        findings.append(
            Finding(
                check="measure_is_not_identifier",
                severity=Severity.BLOCKER,
                summary="Some tools add up or average an identifier.",
                evidence=", ".join(id_measures),
                fix=(
                    "Pick the amount column the question means, or mark the "
                    "field as an identifier and re-run creator_design_tools. "
                    "A sum of keys is a confident, meaningless number."
                ),
                criterion="honesty",
            )
        )
        _penalize(scores, "honesty", 3)
        _penalize(scores, "goal_orientation", 2)
    else:
        passed.append("measure_is_not_identifier")

    if off_groups:
        findings.append(
            Finding(
                check="grouping_matches_question",
                severity=Severity.HIGH,
                summary="A tool groups by a column its question never mentions.",
                evidence="; ".join(off_groups),
                fix="Group by the column the question names, or drop the tool.",
                criterion="goal_orientation",
            )
        )
        _penalize(scores, "goal_orientation", 2)
    else:
        passed.append("grouping_matches_question")

    if misread:
        findings.append(
            Finding(
                check="tool_computes_its_question",
                severity=Severity.HIGH,
                summary=(
                    "A tool is mapped to a question but computes something else: "
                    "a different total, measure or time step."
                ),
                evidence="; ".join(misread),
                fix=(
                    "Send creator_design_tools a reading for the question "
                    "('<question> => shape=...; aggregation=...; measure=...; "
                    "group_by=...') with the aggregation, measure, grouping or "
                    "step it asks for, or drop the tool and tell the user the "
                    "server will not answer it."
                ),
                criterion="honesty",
            )
        )
        _penalize(scores, "honesty", min(3, len(misread)))
        _penalize(scores, "goal_orientation", 1)
    else:
        passed.append("tool_computes_its_question")

    if unanswered:
        findings.append(
            Finding(
                check="every_question_has_a_tool",
                severity=Severity.HIGH,
                summary="Some recorded questions have no tool that computes them.",
                evidence="; ".join(f"'{job}'" for job in unanswered),
                fix=(
                    "Read the design notes for the reason. Where the question "
                    "only names no column, send creator_design_tools a reading "
                    "for it; where no generated pattern answers it, tell the "
                    "user the server will not answer it."
                ),
                criterion="honesty",
            )
        )
        _penalize(scores, "honesty", min(3, len(unanswered)))
    else:
        passed.append("every_question_has_a_tool")

    if repeated:
        findings.append(
            Finding(
                check="tool_names_read_cleanly",
                severity=Severity.MEDIUM,
                summary="Some tool names repeat a word.",
                evidence=", ".join(repeated),
                fix="Rename each so it reads as the question it answers.",
                criterion="goal_orientation",
            )
        )
        _penalize(scores, "goal_orientation", 1)

    if id_measures or unanswered or misread:
        # A design that computes the wrong thing cannot score as honest.
        scores["honesty"] = min(scores["honesty"], 2)


def _check_environment_fit(
    spec: ServerSpec,
    findings: list[Finding],
    passed: list[str],
    scores: dict[str, int],
) -> None:
    """Will this design work in the environment it is going to?

    A design validated against the commercial feature set can fail on
    deployment in a FedRAMP High or IL5 workspace, because the feature it
    depends on is not there. That is not a code problem and no code review
    finds it.
    """
    profile = spec.environment
    if profile is environments.EnvironmentProfile.UNKNOWN:
        findings.append(
            Finding(
                check="environment_declared",
                severity=Severity.MEDIUM,
                summary="The target environment is not declared.",
                fix=(
                    "Run creator_check_environment and set it. Commercial, "
                    "FedRAMP High and IL5 workspaces do not have the same "
                    "features, and the gaps are not guessable."
                ),
                criterion="environment_fit",
            )
        )
        _penalize(scores, "environment_fit", 2)
        return

    passed.append("environment_declared")
    kinds = [source.kind.value for source in spec.data_sources]
    for finding in environments.check_design(
        profile, kinds, uses_in_process_state=False
    ):
        severity = {
            "blocker": Severity.BLOCKER,
            "high": Severity.HIGH,
            "medium": Severity.MEDIUM,
        }.get(finding.severity, Severity.LOW)
        findings.append(
            Finding(
                check=f"environment_{finding.capability}",
                severity=severity,
                summary=finding.summary,
                evidence=f"source: {finding.subject}",
                fix=finding.fix,
                criterion="environment_fit",
            )
        )
        _penalize(scores, "environment_fit", 3 if severity is Severity.BLOCKER else 1)

    unstructured = [
        source
        for source in spec.data_sources
        if source.modality is DataModality.UNSTRUCTURED
    ]
    full_text = environments.availability(profile, "vector_search_full_text")
    if unstructured and full_text is environments.Availability.UNSUPPORTED:
        findings.append(
            Finding(
                check="keyword_retrieval_path",
                severity=Severity.MEDIUM,
                summary=(
                    "This environment has no full-text index, so there is no "
                    "BM25 path for identifier-like queries."
                ),
                fix=(
                    "Add a second tool that runs an exact match or SQL LIKE "
                    "against the chunk table. Semantic search is the wrong "
                    "tool for a clause number or a contract id."
                ),
                criterion="environment_fit",
            )
        )
        _penalize(scores, "environment_fit", 1)

    if (
        not any(
            source.kind is SourceKind.LOCAL_SNAPSHOT for source in spec.data_sources
        )
        and environments.availability(profile, "public_package_index")
        is not environments.Availability.SUPPORTED
    ):
        findings.append(
            Finding(
                check="offline_installability",
                severity=Severity.LOW,
                summary=(
                    "Package index reachability is not confirmed here and "
                    "the server has no credential-free path."
                ),
                fix=(
                    "Keep the dependency list short, and package a snapshot "
                    "so the server can be demonstrated without a warehouse "
                    "or a network."
                ),
                criterion="environment_fit",
            )
        )
