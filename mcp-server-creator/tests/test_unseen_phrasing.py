"""Round 12 (N1): a schema and questions no other test uses.

A blind build on FEMA public assistance data, phrased the way an analyst
writes: 'per state', 'in each fiscal year', 'show ... for a given', 'distinct
counties in Texas', 'obligated amount'. Before round 12, four of nine got a
wrong tool and the review passed all of them, because it re-ran the designer
to decide whether a question was answered.
"""

from __future__ import annotations

from mcp_server_creator.designer import MAX_TOOLS, design_tools
from mcp_server_creator.generators.toolcode import tool_module
from mcp_server_creator.models import (
    DataModality,
    DataSourceProfile,
    FieldProfile,
    QueryPattern,
    ServerSpec,
    SourceKind,
)
from mcp_server_creator.profiling import infer_role, looks_like_pii
from mcp_server_creator.review.rubric import review_spec

COLUMNS = [
    ("disasterNumber", "bigint", None),
    ("declarationDate", "timestamp", None),
    ("fiscalYear", "int", 20),
    ("state", "string", 56),
    ("county", "string", 3000),
    ("incidentType", "string", 25),
    ("projectAmount", "double", None),
    ("federalShareObligated", "double", None),
    ("gallonsDelivered", "double", None),
    ("applicantId", "string", None),
    ("damageCategory", "string", 9),
    ("projectSize", "string", 2),
    ("pwNumber", "bigint", None),
    ("lastRefresh", "timestamp", None),
]

# question -> (pattern, aggregation, measure_field, group_field, a filter it needs)
EXPECTED = {
    "How many gallons of water were delivered per state?": (
        "rank", "sum", "gallonsDelivered", "state", None),
    "How many disasters were declared in each fiscal year?": (
        "rank", "count_distinct", "disasterNumber", "fiscalYear", None),
    "Show declarations for a given disaster number": (
        "lookup", None, None, None, "disasterNumber"),
    "How many distinct counties received assistance in Texas?": (
        "aggregate", "count_distinct", "county", "", "state"),
    "What is total federal share obligated by state?": (
        "rank", "sum", "federalShareObligated", "state", None),
    "Which incident types have the largest project amounts?": (
        "rank", "sum", "projectAmount", "incidentType", None),
    "Show projects for a given applicant": (
        "lookup", None, None, None, "applicantId"),
    "What was the monthly obligated amount in fiscal year 2024?": (
        "trend", "sum", "federalShareObligated", "", None),
    "How many large projects are there by damage category?": (
        "rank", "count", "", "damageCategory", "projectSize"),
}  # fmt: skip


def _fema() -> ServerSpec:
    fields = [
        FieldProfile(
            name=name,
            data_type=dtype,
            role=infer_role(name, dtype),
            pii=looks_like_pii(name),
            cardinality_hint=card,
            enum_values=["Large", "Small"] if name == "projectSize" else [],
        )
        for name, dtype, card in COLUMNS
    ]
    source = DataSourceProfile(
        name="pa_projects",
        kind=SourceKind.UC_TABLE,
        modality=DataModality.STRUCTURED,
        catalog="main",
        schema_name="fema",
        table="pa_projects",
        grain="one row per project worksheet",
        fields=fields,
    )
    return ServerSpec(
        server_name="fema-mcp",
        tool_prefix="fema",
        purpose="Answer FEMA public assistance questions.",
        data_sources=[source],
        jobs_to_be_done=list(EXPECTED),
    )


def _designed() -> ServerSpec:
    spec = _fema()
    spec.tools, _notes = design_tools(spec)
    return spec


def test_each_blind_question_gets_the_tool_it_asks_for() -> None:
    spec = _designed()
    for job, (pattern, agg, measure, group, needs) in EXPECTED.items():
        plan = next((p for p in spec.tools if p.goal == job), None)
        assert plan is not None, f"no tool for {job!r}"
        assert plan.pattern.value == pattern, (job, plan)
        if agg is not None:
            assert plan.aggregation == agg, (job, plan)
            assert plan.measure_field == measure, (job, plan)
            assert plan.group_field == group, (job, plan)
        if needs is not None:
            assert needs in {p.source_field for p in plan.params}, (job, plan.params)


def test_the_cap_keeps_every_question_tool_and_the_dictionary() -> None:
    spec = _fema()
    tools, notes = design_tools(spec)
    answering = [p for p in tools if p.goal in spec.jobs_to_be_done]
    assert len(answering) == len(EXPECTED) > MAX_TOOLS
    assert any(p.pattern is QueryPattern.DESCRIBE_SOURCE for p in tools)
    assert any("splitting the questions" in n for n in notes), notes


def test_review_passes_the_blind_design() -> None:
    report = review_spec(_designed())
    for check in ("tool_computes_its_question", "every_question_has_a_tool"):
        assert check in report.passed_checks, report.findings


def test_review_flags_the_round_11_tools_even_when_the_designer_agrees() -> None:
    """The four round 11 misreadings, put back into the design under the
    names the designer gives them. The review must catch each from the
    question's own words."""
    spec = _designed()
    by_goal = {p.goal: p for p in spec.tools}
    per_state = by_goal["How many gallons of water were delivered per state?"]
    per_state.pattern, per_state.group_field = QueryPattern.AGGREGATE, ""
    per_year = by_goal["How many disasters were declared in each fiscal year?"]
    per_year.aggregation, per_year.measure_field = "count", ""
    counties = by_goal["How many distinct counties received assistance in Texas?"]
    counties.aggregation, counties.measure_field = "count", ""
    show = by_goal["Show declarations for a given disaster number"]
    show.pattern, show.aggregation, show.paginated = (
        QueryPattern.AGGREGATE,
        "count",
        False,
    )
    report = review_spec(spec)
    evidence = " ".join(
        f.evidence for f in report.findings if f.check == "tool_computes_its_question"
    )
    assert "does not group by state" in evidence, evidence
    assert "distinct disasterNumber" in evidence, evidence
    assert "distinct county" in evidence, evidence
    assert "asks to list records" in evidence, evidence
    assert "every_question_has_a_tool" not in report.passed_checks


def test_generated_distinct_count_and_list_tools_compile() -> None:
    spec = _designed()
    by_goal = {p.goal: p for p in spec.tools}
    rank = by_goal["How many disasters were declared in each fiscal year?"]
    total = by_goal["How many distinct counties received assistance in Texas?"]
    listing = by_goal["Show declarations for a given disaster number"]
    for plan in (rank, total, listing):
        compile(tool_module(spec, plan), plan.name, "exec")
    assert "COUNT(DISTINCT {measure_column})" in tool_module(spec, rank)
    assert "COUNT(DISTINCT {measure_column}) AS distinct_count" in tool_module(
        spec, total
    )
    code = tool_module(spec, listing)
    assert "column('disasterNumber', COLUMNS)" in code or (
        'column("disasterNumber", COLUMNS)' in code
    )
    assert '"LIMIT ? OFFSET ?"' in code and '"total": total' in code
    assert "Give a value for disasternumber" in code


def test_a_lookup_matches_the_key_the_designer_chose() -> None:
    """The generated lookup reads the column its parameter names, not
    whichever identifier happens to be profiled first."""
    spec = _designed()
    listing = next(p for p in spec.tools if p.goal.startswith("Show projects"))
    code = tool_module(spec, listing)
    assert "column('applicantId', COLUMNS)" in code or (
        'column("applicantId", COLUMNS)' in code
    )
    assert "disasterNumber', COLUMNS" not in code
    assert 'disasterNumber", COLUMNS' not in code


STORM_COLUMNS = [
    ("event_id", "bigint", None),
    ("state", "string", 68),
    ("county", "string", 3100),
    ("event_type", "string", 48),
    ("begin_date", "timestamp", None),
    ("year", "int", 30),
    ("deaths_direct", "int", None),
    ("damage_property", "double", None),
    ("damage_crops", "double", None),
    ("magnitude", "double", None),
]
STORM = {
    "What were the total property damages in each year?": (
        "rank", "sum", "damage_property", "year"),
    "Number of unique event types per state": (
        "rank", "count_distinct", "event_type", "state"),
    "How many tornado events happened per state?": ("rank", "count", "", "state"),
    "Show monthly crop damage": ("trend", "sum", "damage_crops", ""),
}  # fmt: skip


def _storms() -> ServerSpec:
    source = DataSourceProfile(
        name="storm_events",
        kind=SourceKind.UC_TABLE,
        modality=DataModality.STRUCTURED,
        catalog="main",
        schema_name="noaa",
        table="storm_events",
        grain="one row per storm event",
        fields=[
            FieldProfile(name=n, data_type=t, role=infer_role(n, t), cardinality_hint=c)
            for n, t, c in STORM_COLUMNS
        ],
    )
    spec = ServerSpec(
        server_name="storms-mcp",
        tool_prefix="storms",
        purpose="Answer storm event questions.",
        data_sources=[source],
        jobs_to_be_done=list(STORM),
    )
    spec.tools, _notes = design_tools(spec)
    return spec


def test_a_second_schema_groups_by_a_year_column_and_counts_event_types() -> None:
    """The second blind set: 'in each year' groups by a year column, and
    'unique event types' on a table of events counts event_type, not rows."""
    spec = _storms()
    for job, (pattern, agg, measure, group) in STORM.items():
        plan = next(p for p in spec.tools if p.goal == job)
        assert (plan.pattern.value, plan.aggregation) == (pattern, agg), (job, plan)
        assert (plan.measure_field, plan.group_field) == (measure, group), (job, plan)
    report = review_spec(spec)
    assert "tool_computes_its_question" in report.passed_checks, report.findings

    by_goal = {p.goal: p for p in spec.tools}
    yearly = by_goal["What were the total property damages in each year?"]
    yearly.pattern, yearly.group_field = QueryPattern.AGGREGATE, ""
    types = by_goal["Number of unique event types per state"]
    types.aggregation, types.measure_field = "count", ""
    evidence = " ".join(
        f.evidence
        for f in review_spec(spec).findings
        if f.check == "tool_computes_its_question"
    )
    assert "does not group by year" in evidence, evidence
    assert "distinct event_type" in evidence, evidence


def test_which_cities_most_ranks_cities_and_the_review_checks_it() -> None:
    """Third blind set, first run 7 of 8: 'cities' never met borrower_city,
    so the tool returned one Ohio total. Plurals now match, and the review
    reads 'which X ... most' as a ranking by X."""
    fields = [
        FieldProfile(name=n, data_type=t, role=infer_role(n, t), cardinality_hint=c)
        for n, t, c in [
            ("loan_number", "bigint", None),
            ("borrower_state", "string", 57),
            ("borrower_city", "string", 9000),
            ("approval_date", "timestamp", None),
            ("current_approval_amount", "double", None),
        ]
    ]
    job = "Which cities in Ohio received the most loans?"
    spec = ServerSpec(
        server_name="ppp-mcp",
        tool_prefix="ppp",
        purpose="Answer PPP loan questions.",
        data_sources=[
            DataSourceProfile(
                name="ppp_loans",
                kind=SourceKind.UC_TABLE,
                modality=DataModality.STRUCTURED,
                catalog="main",
                schema_name="sba",
                table="ppp_loans",
                grain="one row per loan",
                fields=fields,
            )
        ],
        jobs_to_be_done=[job],
    )
    spec.tools, _notes = design_tools(spec)
    plan = next(p for p in spec.tools if p.goal == job)
    assert plan.group_field == "borrower_city" and plan.aggregation == "count", plan
    assert "borrower_state" in {p.source_field for p in plan.params}
    assert "tool_computes_its_question" in review_spec(spec).passed_checks
    plan.pattern, plan.group_field = QueryPattern.AGGREGATE, ""
    evidence = " ".join(f.evidence for f in review_spec(spec).findings)
    assert "does not group by borrower_city" in evidence, evidence
