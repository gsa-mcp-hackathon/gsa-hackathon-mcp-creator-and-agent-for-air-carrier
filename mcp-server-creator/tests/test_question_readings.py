"""Round 13 (1.0.0rc3): four more schemas no test had used, and a way for the
caller to correct how a question was read.

The changelog for 1.0.0rc2 said a fourth unseen set would measure the rules
honestly again. Two sets (federal contract awards, federal real property)
were written before any change and run against 1.0.0rc2: 5 of 19 questions
got the right tool. After the designer was fixed on those two, two more sets
(IT investments, a bridge inventory), written at the same time and kept
aside, were run once: 10 of 19 right, and the review caught none of the nine
misses. Every question in those four sets, and in a fifth written after
every fix (6 of 8 right, none wrong), is now a regression test here.

Rules will keep meeting phrasing they have not seen. So each tool now comes
back with its reading of the question, and the caller can send a corrected
reading; the columns are checked against the profile and the review still
compares the tool with the question's own words.
"""

from __future__ import annotations

import ast
import asyncio
import json
import os
import subprocess
import sys

import pytest
from fastmcp import Client

from mcp_server_creator.app import mcp
from mcp_server_creator.designer import (
    describe_reading,
    design_tools,
    parse_reading,
    plan_from_reading,
)
from mcp_server_creator.generators import formatting, generate_full_project
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

# Each column: (name, type, distinct values if known, allowed values if known).
# Each question: what the tool must be, or the words of the note that says
# why no generated pattern answers it.
#   (pattern, aggregation, measure, group, columns its parameters must cover)

AWARDS = {
    "table": "contract_awards",
    "grain": "one row per contract action",
    "prefix": "awards",
    "columns": [
        ("award_id_piid", "string", None, []),
        ("awarding_agency_name", "string", 100, []),
        ("awarding_sub_agency_name", "string", 500, []),
        ("recipient_name", "string", None, []),
        ("recipient_uei", "string", None, []),
        ("naics_code", "string", 1000, []),
        ("naics_description", "string", 1000, []),
        ("product_or_service_code", "string", 2000, []),
        ("action_date", "date", None, []),
        ("fiscal_year", "int", 10, []),
        ("federal_action_obligation", "double", None, []),
        ("current_total_value_of_award", "double", None, []),
        ("period_of_performance_start_date", "date", None, []),
        ("period_of_performance_current_end_date", "date", None, []),
        ("place_of_performance_state", "string", 56, []),
        ("type_of_set_aside", "string", 20, []),
        ("extent_competed", "string", 10, []),
        ("number_of_offers_received", "int", None, []),
        ("contracting_officer_business_size", "string", 2,
         ["SMALL BUSINESS", "OTHER THAN SMALL BUSINESS"]),
    ],
    "questions": {
        "Which agencies obligated the most money in fiscal year 2025?": (
            "rank", "sum", "federal_action_obligation", "awarding_agency_name",
            {"fiscal_year"}),
        "What is the average number of offers received per NAICS code?": (
            "rank", "avg", "number_of_offers_received", "naics_code", set()),
        "Which contracts expire in the next 90 days?": (
            "lookup", None, "", "", {"period_of_performance_current_end_date"}),
        "How much went to small businesses by agency?": "names no amount column",
        "Look up an award by its PIID": (
            "lookup", None, "", "", {"award_id_piid"}),
        "How many unique recipients did each sub-agency award to?": (
            "rank", "count_distinct", "recipient_name", "awarding_sub_agency_name",
            set()),
        "What are the top 10 recipients by total award value?": (
            "rank", "sum", "current_total_value_of_award", "recipient_name", set()),
        "How have obligations changed month over month?": (
            "trend", "sum", "federal_action_obligation", "", set()),
        "What share of awards were not competed?": (
            "rank", "count", "", "extent_competed", set()),
        "List all awards for a recipient": (
            "lookup", None, "", "", {"recipient_name"}),
    },
}  # fmt: skip

PROPERTY = {
    "table": "real_property",
    "grain": "one row per real property asset",
    "prefix": "property",
    "columns": [
        ("real_property_unique_id", "string", None, []),
        ("reporting_agency", "string", 60, []),
        ("bureau", "string", 300, []),
        ("property_type", "string", 3, ["Building", "Land", "Structure"]),
        ("property_use", "string", 40, []),
        ("legal_interest", "string", 2, ["Owned", "Leased"]),
        ("status", "string", 4, ["Active", "Excess", "Disposed", "Inactive"]),
        ("city", "string", 5000, []),
        ("state_name", "string", 56, []),
        ("zip_code", "string", None, []),
        ("congressional_district", "string", 440, []),
        ("square_feet", "double", None, []),
        ("acres", "double", None, []),
        ("annual_operating_cost", "double", None, []),
        ("annual_rent", "double", None, []),
        ("lease_expiration_date", "date", None, []),
        ("utilization", "string", 3, ["Utilized", "Underutilized", "Unutilized"]),
        ("construction_year", "int", 150, []),
        ("repair_needs", "double", None, []),
        ("latitude", "double", None, []),
        ("longitude", "double", None, []),
    ],
    "questions": {
        "How much square footage does each agency own versus lease?": (
            "rank", "sum", "square_feet", "reporting_agency", {"legal_interest"}),
        "Which states have the most underutilized buildings?": (
            "rank", "count", "", "state_name", {"utilization", "property_type"}),
        "What is the total annual rent for leases expiring in a given year?": (
            "aggregate", "sum", "annual_rent", "", {"lease_expiration_date"}),
        "Find a property by its unique ID": (
            "lookup", None, "", "", {"real_property_unique_id"}),
        "What is the average operating cost per square foot by property use?":
            "ratio (per square foot)",
        "How many buildings were built before 1970?": (
            "aggregate", "count", "", "", {"construction_year", "property_type"}),
        "Total repair needs across each bureau": (
            "rank", "sum", "repair_needs", "bureau", set()),
        "List excess properties in a given city": (
            "lookup", None, "", "", {"city", "status"}),
        "How many distinct agencies have property in Virginia?": (
            "aggregate", "count_distinct", "reporting_agency", "", {"state_name"}),
    },
}  # fmt: skip

INVESTMENTS = {
    "table": "it_investments",
    "grain": "one row per IT investment per budget year",
    "prefix": "itdash",
    "columns": [
        ("investment_id", "string", None, []),
        ("investment_title", "string", None, []),
        ("agency_code", "string", 30, []),
        ("agency_name", "string", 30, []),
        ("bureau_name", "string", 200, []),
        ("investment_type", "string", 3, ["Major", "Non-major", "Standard"]),
        ("cio_rating", "int", 5, []),
        ("total_it_spending", "double", None, []),
        ("dme_spending", "double", None, []),
        ("om_spending", "double", None, []),
        ("budget_year", "int", 8, []),
        ("project_count", "int", None, []),
        ("schedule_variance_pct", "double", None, []),
        ("cost_variance_pct", "double", None, []),
        ("risk_level", "string", 3, ["Low", "Medium", "High"]),
        ("start_date", "date", None, []),
        ("planned_completion_date", "date", None, []),
        ("cloud_status", "string", 5, []),
        ("contractor_name", "string", None, []),
    ],
    "questions": {
        "Which bureaus spend the most on operations and maintenance?": (
            "rank", "sum", "om_spending", "bureau_name", set()),
        "How many high risk investments does each agency have?": (
            "rank", "count", "", "agency_code", {"risk_level"}),
        "Average CIO rating by investment type": (
            "rank", "avg", "cio_rating", "investment_type", set()),
        "Pull up an investment by its ID": (
            "lookup", None, "", "", {"investment_id"}),
        "Total IT spending for a given budget year": (
            "aggregate", "sum", "total_it_spending", "", {"budget_year"}),
        "How many different contractors work on major investments?": (
            "aggregate", "count_distinct", "contractor_name", "",
            {"investment_type"}),
        "Which investments are scheduled to complete in 2027?": (
            "lookup", None, "", "", {"planned_completion_date"}),
        "Show all investments for one agency": (
            "lookup", None, "", "", {"agency_code"}),
        "What percentage of investments are in the cloud?": (
            "rank", "count", "", "cloud_status", set()),
        "DME spending trend by quarter": "asks by quarter",
    },
}  # fmt: skip

BRIDGES = {
    "table": "bridge_inventory",
    "grain": "one row per bridge",
    "prefix": "bridges",
    "columns": [
        ("structure_number", "string", None, []),
        ("state_code", "string", 52, []),
        ("county_name", "string", 3000, []),
        ("owner_agency", "string", 30, []),
        ("year_built", "int", 150, []),
        ("deck_condition", "int", 10, []),
        ("superstructure_condition", "int", 10, []),
        ("bridge_condition", "string", 3, ["Good", "Fair", "Poor"]),
        ("average_daily_traffic", "int", None, []),
        ("structure_length_m", "double", None, []),
        ("deck_area_sqm", "double", None, []),
        ("last_inspection_date", "date", None, []),
        ("improvement_cost", "double", None, []),
        ("functional_class", "string", 12, []),
        ("toll_status", "string", 2, ["Toll", "Free"]),
        ("route_number", "string", None, []),
    ],
    "questions": {
        "How many bridges are in poor condition in each state?": (
            "rank", "count", "", "state_code", {"bridge_condition"}),
        "What is the total deck area of poor bridges by owner?": (
            "rank", "sum", "deck_area_sqm", "owner_agency", {"bridge_condition"}),
        "Get a bridge by structure number": (
            "lookup", None, "", "", {"structure_number"}),
        "Which counties have the highest average daily traffic?": (
            "rank", "avg", "average_daily_traffic", "county_name", set()),
        "How much would it cost to improve all bridges built before 1960?": (
            "aggregate", "sum", "improvement_cost", "", {"year_built"}),
        "List bridges on a given route": (
            "lookup", None, "", "", {"route_number"}),
        "How many bridges were inspected each month?": (
            "trend", "count", "", "", {"last_inspection_date"}),
        "Number of unique owners per state": (
            "rank", "count_distinct", "owner_agency", "state_code", set()),
        "What is the oldest bridge in each county?": "oldest record",
    },
}  # fmt: skip

# Written after every fix above and run once, as a last check: 6 of 8 right,
# none wrong. The two it could not read each named no column; one of them had
# no note saying so, which is fixed.
GRANTS = {
    "table": "grants",
    "grain": "one row per grant award",
    "prefix": "grants",
    "columns": [
        ("grant_id", "string", None, []),
        ("recipient_name", "string", None, []),
        ("recipient_state", "string", None, []),
        ("cfda_number", "string", None, []),
        ("program_title", "string", None, []),
        ("awarding_agency", "string", None, []),
        ("award_date", "date", None, []),
        ("period_end_date", "date", None, []),
        ("obligated_amount", "double", None, []),
        ("outlayed_amount", "double", None, []),
        ("recipient_type", "string", None,
         ["State government", "Nonprofit", "Tribal government", "Higher education"]),
    ],
    "questions": {
        "Total obligated amount by awarding agency": (
            "rank", "sum", "obligated_amount", "awarding_agency", set()),
        "How many grants went to tribal governments?": (
            "aggregate", "count", "", "", {"recipient_type"}),
        "Which programs received the most funding?": "names no amount column",
        "Outlays per month in 2025": ("trend", "sum", "outlayed_amount", "", set()),
        "Show grants for a given CFDA number": (
            "lookup", None, "", "", {"cfda_number"}),
        "Which grants end this quarter?": (
            "lookup", None, "", "", {"period_end_date"}),
        "Average award size by recipient type": "names no column to average",
        "How many recipients are there in each state?": (
            "rank", "count_distinct", "recipient_name", "recipient_state", set()),
    },
}  # fmt: skip

SETS = {
    "awards": AWARDS,
    "property": PROPERTY,
    "investments": INVESTMENTS,
    "bridges": BRIDGES,
    "grants": GRANTS,
}
CASES = [(name, q) for name, s in SETS.items() for q in s["questions"]]


def _spec(name: str) -> ServerSpec:
    schema = SETS[name]
    source = DataSourceProfile(
        name=schema["table"],
        kind=SourceKind.UC_TABLE,
        modality=DataModality.STRUCTURED,
        catalog="main",
        schema_name="gov",
        table=schema["table"],
        grain=schema["grain"],
        fields=[
            FieldProfile(
                name=column,
                data_type=dtype,
                role=infer_role(column, dtype),
                pii=looks_like_pii(column),
                cardinality_hint=distinct,
                enum_values=values,
            )
            for column, dtype, distinct, values in schema["columns"]
        ],
    )
    return ServerSpec(
        server_name=f"{schema['prefix']}-mcp",
        tool_prefix=schema["prefix"],
        purpose=f"Answer questions about {schema['table']}.",
        data_sources=[source],
        jobs_to_be_done=list(schema["questions"]),
    )


def _designed(name: str, readings: list[str] | None = None):
    spec = _spec(name)
    parsed = [parse_reading(line)[0] for line in readings or []]
    assert all(parsed), readings
    spec.tools, notes = design_tools(spec, parsed)
    return spec, notes


def _reviewed(spec: ServerSpec, check: str) -> str:
    return " ".join(f.evidence for f in review_spec(spec).findings if f.check == check)


# ---------------------------------------------------------------------------
# The five sets: every question gets the tool it asks for, or a reason.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,question", CASES, ids=[f"{n}:{q[:40]}" for n, q in CASES]
)
def test_each_question_gets_the_tool_it_asks_for_or_a_reason(name, question) -> None:
    spec, notes = _designed(name)
    expected = SETS[name]["questions"][question]
    plan = next((p for p in spec.tools if p.goal == question), None)
    if isinstance(expected, str):
        assert plan is None, plan
        assert any(question in n and expected in n for n in notes), notes
        return
    pattern, aggregation, measure, group, covers = expected
    assert plan is not None, notes
    assert plan.pattern.value == pattern, plan
    if aggregation is not None:
        assert plan.aggregation == aggregation, plan
    assert (plan.measure_field, plan.group_field) == (measure, group), plan
    assert covers <= {p.source_field for p in plan.params}, plan.params


@pytest.mark.parametrize("name", list(SETS))
def test_the_review_agrees_and_lists_only_the_questions_with_a_reason(name) -> None:
    spec, _notes = _designed(name)
    report = review_spec(spec)
    assert "tool_computes_its_question" in report.passed_checks, report.findings
    unanswered = _reviewed(spec, "every_question_has_a_tool")
    for question, expected in SETS[name]["questions"].items():
        assert (question in unanswered) == isinstance(expected, str), question


def test_a_date_window_list_binds_its_bounds_and_requires_the_first() -> None:
    """'Which contracts expire in the next 90 days?' is the question this
    server's own example prompt asks. It is a paged list bounded on the end
    date; the caller works the window out from today, so it moves."""
    from mcp_server_creator.generators.toolcode import tool_module

    spec, _ = _designed("awards")
    plan = next(p for p in spec.tools if p.goal.startswith("Which contracts expire"))
    bounds = {p.name: (p.source_field, p.operator, p.required) for p in plan.params}
    end = "period_of_performance_current_end_date"
    assert bounds["start_date"] == (end, ">=", True)
    assert bounds["end_date"] == (end, "<", False)
    code = tool_module(spec, plan)
    assert f'column("{end}", COLUMNS) + " >= ?"' in code
    assert f'column("{end}", COLUMNS) + " < ?"' in code
    assert "Give a value for start_date." in code
    assert "LIMIT ? OFFSET ?" in code


def test_long_tool_names_end_on_a_word() -> None:
    spec, _ = _designed("awards")
    for plan in spec.tools:
        assert len(plan.name) <= 63
        assert (
            plan.name.split("_")[-1]
            in json.dumps(
                [plan.goal, plan.source, plan.measure_field, plan.group_field]
                + [p.source_field for p in plan.params]
                + ["describe", "search", "count", "for", "by", "filtered"]
            ).lower()
        ), plan.name


# ---------------------------------------------------------------------------
# What the first run on the held-out sets got wrong, put back as readings.
# The review must catch each from the question's own words.
# ---------------------------------------------------------------------------

FIRST_RUN_MISREADINGS = [
    ("investments",
     "Which bureaus spend the most on operations and maintenance? => "
     "shape=ranking; aggregation=sum; measure=total_it_spending; "
     "group_by=bureau_name",
     "names om_spending"),
    ("investments",
     "How many high risk investments does each agency have? => shape=ranking; "
     "aggregation=count_distinct; measure=risk_level; group_by=agency_code",
     "does not ask for distinct values"),
    ("investments",
     "Which investments are scheduled to complete in 2027? => shape=ranking; "
     "aggregation=sum; measure=schedule_variance_pct; group_by=investment_id",
     "asks to list records"),
    ("investments",
     "DME spending trend by quarter => shape=trend; aggregation=sum; "
     "measure=total_it_spending",
     "names dme_spending"),
    ("bridges",
     "Get a bridge by structure number => shape=ranking; aggregation=sum; "
     "measure=structure_length_m; group_by=structure_number",
     "asks to list records"),
    ("bridges",
     "Which counties have the highest average daily traffic? => shape=trend; "
     "aggregation=avg; measure=average_daily_traffic; granularity=day",
     "returns a trend"),
    ("bridges",
     "What is the oldest bridge in each county? => shape=ranking; "
     "aggregation=count; group_by=county_name",
     "asks for the oldest record"),
    ("awards",
     "What share of awards were not competed? => shape=total; aggregation=sum; "
     "measure=current_total_value_of_award",
     "asks for a share"),
    ("awards",
     "List all awards for a recipient => shape=total; aggregation=count",
     "asks to list records"),
    ("property",
     "How many buildings were built before 1970? => shape=list; key=city",
     "asks for a figure"),
]  # fmt: skip


@pytest.mark.parametrize(
    "name,reading,flagged",
    FIRST_RUN_MISREADINGS,
    ids=[f"{n}:{r[:32]}" for n, r, _ in FIRST_RUN_MISREADINGS],
)
def test_the_review_catches_a_wrong_reading_whoever_wrote_it(
    name, reading, flagged
) -> None:
    spec, notes = _designed(name, [reading])
    question = reading.split(" => ")[0]
    assert any(p.goal == question for p in spec.tools), notes
    evidence = _reviewed(spec, "tool_computes_its_question")
    assert flagged in evidence, evidence
    assert question in _reviewed(spec, "every_question_has_a_tool")


# ---------------------------------------------------------------------------
# Readings: the caller corrects one question; everything is checked.
# ---------------------------------------------------------------------------


def test_a_reading_answers_the_question_the_designer_could_not() -> None:
    question = "How much went to small businesses by agency?"
    spec, notes = _designed(
        "awards",
        [
            f"{question} => shape=ranking; aggregation=sum; "
            "measure=federal_action_obligation; group_by=awarding_agency_name; "
            "filters=contracting_officer_business_size"
        ],
    )
    plan = next(p for p in spec.tools if p.goal == question)
    assert plan.pattern is QueryPattern.RANK and plan.aggregation == "sum"
    assert plan.measure_field == "federal_action_obligation"
    assert plan.group_field == "awarding_agency_name"
    size = next(
        p for p in plan.params if p.source_field == "contracting_officer_business_size"
    )
    assert size.enum_values == ["SMALL BUSINESS", "OTHER THAN SMALL BUSINESS"]
    assert not any(question in n for n in notes), notes
    assert question not in _reviewed(spec, "every_question_has_a_tool")
    # Two questions rank agencies by obligations; the names stay distinct and whole.
    names = [p.name for p in spec.tools]
    assert len(names) == len(set(names)) and plan.name.endswith("_filtered")


@pytest.mark.parametrize("name", list(SETS))
def test_a_reading_the_designer_reports_can_be_sent_back_unchanged(name) -> None:
    """What `describe_reading` says is what a QuestionReading accepts."""
    spec, _ = _designed(name)
    lines = []
    for plan in spec.tools:
        reading = describe_reading(plan)
        if reading is None or plan.goal not in spec.jobs_to_be_done:
            continue
        columns = {f.name for f in spec.data_sources[0].fields}
        filters = [f for f in reading.pop("filters", []) if f in columns]
        pairs = [f"{key}={value}" for key, value in reading.items() if value]
        # A date bound is not an equality filter; computed tools add it themselves.
        dates = {f.name for f in spec.data_sources[0].dates()}
        equal = [f for f in filters if f not in dates][:2]
        if equal:
            pairs.append("filters=" + ",".join(equal))
        lines.append(f"{plan.goal} => " + "; ".join(pairs))
    again, notes = _designed(name, lines)
    assert not any("Reading" in n for n in notes), notes

    def shape(tools):
        return {
            p.goal: (p.pattern, p.aggregation, p.measure_field, p.group_field)
            for p in tools
            if p.goal in spec.jobs_to_be_done
        }

    assert shape(again.tools) == shape(spec.tools)


def test_readings_answer_the_two_grant_questions_that_name_no_column() -> None:
    funding = "Which programs received the most funding?"
    size = "Average award size by recipient type"
    spec, notes = _designed(
        "grants",
        [
            f"{funding} => shape=ranking; aggregation=sum; "
            "measure=obligated_amount; group_by=program_title",
            f"{size} => shape=ranking; aggregation=avg; "
            "measure=obligated_amount; group_by=recipient_type",
        ],
    )
    by_goal = {p.goal: p for p in spec.tools}
    assert by_goal[funding].group_field == "program_title"
    assert by_goal[size].aggregation == "avg"
    report = review_spec(spec)
    assert "tool_computes_its_question" in report.passed_checks, report.findings
    assert "every_question_has_a_tool" in report.passed_checks, report.findings


@pytest.mark.parametrize(
    "line,problem",
    [
        ("no arrow here", "write it as"),
        (" => shape=total", "write it as"),
        ("A question => shape=pie chart", "shape"),
        ("A question => aggregation=median; shape=total", "aggregation"),
        ("A question => shape=total; drop table=x", "is not one of"),
        ("A question => shape=list; key=x'; DROP TABLE t; --", "is not one of"),
        ("A question => shape=total; filters=a,b,c", "filters"),
        ("A question => aggregation=sum", "shape"),
        ("A question => shape=total; measure=" + "m" * 200, "measure"),
    ],
)
def test_a_malformed_reading_is_refused_with_its_reason(line, problem) -> None:
    reading, reason = parse_reading(line)
    assert reading is None and problem in reason, reason


REJECTED = [
    ("Not a recorded question => shape=total; aggregation=count",
     "not a recorded question"),
    ("Look up an award by its PIID => shape=list; key=no_such_column",
     "is not a column"),
    ("Look up an award by its PIID => shape=list; key=x' OR '1'='1",
     "is not a column"),
    ("What share of awards were not competed? => shape=total; aggregation=sum; "
     "measure=award_id_piid", "is not a numeric measure"),
    ("What share of awards were not competed? => shape=ranking; "
     "group_by=federal_action_obligation", "is a measure, not a grouping"),
    ("What share of awards were not competed? => shape=ranking; aggregation=count",
     "group_by '' is not a column"),
    ("What share of awards were not competed? => shape=total; "
     "aggregation=count_distinct", "measure '' is not a column"),
    ("What share of awards were not competed? => shape=total; aggregation=count; "
     "filters=nope", "filter 'nope' is not a column"),
    ("What share of awards were not competed? => shape=total; aggregation=count; "
     "source=other_table", "no table source named 'other_table'"),
]  # fmt: skip


@pytest.mark.parametrize("line,reason", REJECTED, ids=[r for _, r in REJECTED])
def test_a_reading_that_does_not_fit_the_source_is_reported_and_ignored(
    line, reason
) -> None:
    plain, _ = _designed("awards")
    spec, notes = _designed("awards", [line])
    assert any(reason in n and "own reading was kept" in n for n in notes), notes
    assert [p.model_dump() for p in spec.tools] == [p.model_dump() for p in plain.tools]


def test_a_reading_cannot_reach_a_personal_column_or_a_dateless_trend() -> None:
    spec = _spec("bridges")
    source = spec.data_sources[0]
    next(f for f in source.fields if f.name == "owner_agency").pii = True
    question = "Number of unique owners per state"
    reading, _ = parse_reading(
        f"{question} => shape=ranking; aggregation=count_distinct; "
        "measure=owner_agency; group_by=state_code"
    )
    plan, reason = plan_from_reading(spec, source, reading)
    assert plan is None and "measure 'owner_agency' is not a column" in reason

    source.fields = [f for f in source.fields if f.name != "last_inspection_date"]
    trend, _ = parse_reading(
        "How many bridges were inspected each month? => shape=trend; aggregation=count"
    )
    plan, reason = plan_from_reading(spec, source, trend)
    assert plan is None and "no date field for a trend" in reason


def test_a_list_reading_on_a_date_becomes_a_window() -> None:
    question = "Which contracts expire in the next 90 days?"
    spec, notes = _designed(
        "awards", [f"{question} => shape=list; key=period_of_performance_start_date"]
    )
    plan = next(p for p in spec.tools if p.goal == question)
    assert [p.operator for p in plan.params[:2]] == [">=", "<"], notes
    assert plan.params[0].source_field == "period_of_performance_start_date"


# ---------------------------------------------------------------------------
# Second pass: what a review of this release's own change found.
# ---------------------------------------------------------------------------

SALES_COLUMNS = [
    "sale_id STRING", "employee_name STRING", "employee STRING", "store STRING",
    "sale_amount DOUBLE", "sale_date DATE", "due_date DATE", "end_date DATE",
    "fiscal_year INT", "year_built INT",
]  # fmt: skip


def _sales(jobs, kind=SourceKind.UC_TABLE, out_of_scope=()):
    from mcp_server_creator.profiling import parse_tabular_text

    place = (
        {"catalog": "main", "schema_name": "s", "table": "sales"}
        if kind is SourceKind.UC_TABLE
        else {"snapshot_path": "data/sales.json"}
    )
    source = DataSourceProfile(
        name="sales",
        kind=kind,
        modality=DataModality.STRUCTURED,
        grain="one row per sale",
        fields=parse_tabular_text(", ".join(SALES_COLUMNS)),
        **place,
    )
    spec = ServerSpec(
        server_name="sales-mcp",
        tool_prefix="sales",
        purpose="Answer sales questions.",
        data_sources=[source],
        jobs_to_be_done=list(jobs),
        out_of_scope=list(out_of_scope),
    )
    spec.tools, notes = design_tools(spec)
    return spec, notes


def test_per_a_column_groups_and_per_a_unit_is_a_ratio() -> None:
    """'Sales per employee' on a table with an employee column is a grouping.
    The ratio rule must not take it: only 'per mile' with no such column is
    one column divided by another."""
    job = "What are total sales per employee?"
    spec, notes = _sales([job])
    plan = next(p for p in spec.tools if p.goal == job)
    assert (plan.pattern, plan.measure_field) == (QueryPattern.RANK, "sale_amount")
    assert plan.group_field in {"employee", "employee_name"}, notes
    job = "What are total sales per mile?"
    spec, notes = _sales([job])
    assert not any(p.goal == job for p in spec.tools)
    assert any("ratio (per mile)" in n for n in notes), notes


def test_a_rule_that_withholds_people_hides_their_name_column_too() -> None:
    """Name columns can now be grouped and listed by, so 'questions about
    individual employees' must hide employee_name with the employee key."""
    jobs = ["Which employees had the highest total sale amount?"]
    spec, notes = _sales(jobs, out_of_scope=["Questions about individual employees"])
    hidden = {f.name for f in spec.data_sources[0].fields if f.pii}
    assert {"employee", "employee_name"} <= hidden, notes
    for plan in spec.tools:
        used = {plan.group_field} | {p.source_field for p in plan.params}
        assert not used & hidden, plan


def test_the_rows_own_noun_does_not_pick_the_date() -> None:
    """'Which sales are due within 30 days?' on a table of sales bounds the
    due date. 'Sales' names the row, not sale_date."""
    job = "Which sales are due within 30 days?"
    spec, _ = _sales([job])
    plan = next(p for p in spec.tools if p.goal == job)
    assert [p.source_field for p in plan.params[:2]] == ["due_date", "due_date"]
    assert describe_reading(plan) == {"shape": "list", "key": "due_date", "filters": []}


def test_a_window_question_on_a_snapshot_is_reported_not_ranked() -> None:
    """A packaged snapshot has no paging. The question is reported, as it was
    before 1.0.0rc3, and never becomes a ranking by amount."""
    job = "Which sales expire in the next 90 days?"
    spec, notes = _sales([job], kind=SourceKind.LOCAL_SNAPSHOT)
    assert not any(p.goal == job for p in spec.tools)
    assert any(job in n and "date window" in n for n in notes), notes


def test_a_named_period_with_its_value_becomes_a_filter() -> None:
    job = "What were total sales in fiscal year 2025?"
    spec, _ = _sales([job])
    plan = next(p for p in spec.tools if p.goal == job)
    assert plan.params[0].source_field == "fiscal_year"
    assert "2025" in plan.params[0].description


def test_how_much_with_no_column_named_lists_the_measures_there_are() -> None:
    job = "How much did we get by store?"
    spec, notes = _sales([job])
    assert not any(p.goal == job for p in spec.tools)
    note = next(n for n in notes if job in n)
    assert "sale_amount" in note and "no numeric column" not in note


# ---------------------------------------------------------------------------
# Through the MCP tool, the way a client calls it.
# ---------------------------------------------------------------------------


def _call(tool: str, args: dict) -> dict:
    async def go():
        async with Client(mcp) as client:
            return await client.call_tool(tool, args, raise_on_error=False)

    result = asyncio.run(go())
    assert not result.is_error, result.content
    return result.structured_content or json.loads(result.content[0].text)


def _started(name: str) -> str:
    schema = SETS[name]
    design_id = _call(
        "creator_start_design",
        {
            "purpose": f"Answer questions about {schema['table']}.",
            "primary_user": "Budget analyst",
            "jobs_to_be_done": list(schema["questions"]),
        },
    )["design_id"]
    _call(
        "creator_add_data_source",
        {
            "design_id": design_id,
            "name": schema["table"],
            "kind": "uc_table",
            "modality": "structured",
            "catalog": "main",
            "schema_name": "gov",
            "table": schema["table"],
            "grain": schema["grain"],
            "schema_text": ", ".join(
                f"{column} {dtype.upper()}" for column, dtype, *_ in schema["columns"]
            ),
            "try_live_inspection": False,
        },
    )
    return design_id


def test_the_tool_reports_each_reading_and_takes_a_correction() -> None:
    """A pasted schema, no workspace: the path a reviewer takes first."""
    design_id = _started("awards")
    first = _call("creator_design_tools", {"design_id": design_id})
    by_question = {t["question"]: t for t in first["tools"] if "question" in t}
    ranked = by_question["Which agencies obligated the most money in fiscal year 2025?"]
    assert ranked["reading"] == {
        "shape": "ranking",
        "aggregation": "sum",
        "measure": "federal_action_obligation",
        "group_by": "awarding_agency_name",
        "filters": ["fiscal_year", "action_date"],
    }
    assert by_question["Look up an award by its PIID"]["reading"] == {
        "shape": "list",
        "key": "award_id_piid",
        "filters": [],
    }
    question = "How much went to small businesses by agency?"
    assert question not in by_question
    assert any(question in n for n in first["design_notes"])
    # A tool nobody asked a question about carries no reading.
    assert all("reading" not in t for t in first["tools"] if "question" not in t)

    second = _call(
        "creator_design_tools",
        {
            "design_id": design_id,
            "readings": [
                f"{question} => shape=ranking; aggregation=sum; "
                "measure=federal_action_obligation; group_by=awarding_agency_name",
                "this one has no arrow",
                "Look up an award by its PIID => shape=list; key=secret",
            ],
        },
    )
    fixed = {t["question"]: t for t in second["tools"] if "question" in t}
    assert fixed[question]["reading"]["measure"] == "federal_action_obligation"
    notes = " ".join(second["design_notes"])
    assert "Reading 2 was ignored" in notes and "key 'secret' is not a column" in notes
    assert fixed["Look up an award by its PIID"]["reading"]["key"] == "award_id_piid"

    review = _call("creator_review_server", {"design_id": design_id})
    unanswered = " ".join(
        f["evidence"]
        for f in review["findings"]
        if f["check"] == "every_question_has_a_tool"
    )
    assert question not in unanswered


# ---------------------------------------------------------------------------
# The generated projects: lint clean, their own tests pass, strings capped.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module", params=["awards", "property"])
def project(request, tmp_path_factory):
    spec, _ = _designed(request.param)
    manifest = generate_full_project(spec)
    root = tmp_path_factory.mktemp(request.param)
    for generated in manifest.files:
        destination = root / generated.path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(generated.content, encoding="utf-8", newline="\n")
    return root, manifest


def test_the_generated_project_is_lint_clean_and_passes_its_own_tests(project) -> None:
    root, _manifest = project
    if formatting.ruff_available():
        for args in (["check", "--output-format=concise"], ["format", "--check"]):
            lint = subprocess.run(
                ["ruff", *args, str(root)], capture_output=True, text=True, check=False
            )
            assert lint.returncode == 0, lint.stdout + lint.stderr
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-q", "-p", "no:cacheprovider"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        env={
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": str(root / "src"),
            "HOME": os.environ.get("HOME", ""),
            "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
        },
    )
    assert result.returncode == 0, result.stdout[-4000:] + result.stderr[-2000:]


def test_every_generated_string_argument_is_capped(project) -> None:
    """A free-text argument with no length cap reaches the warehouse at any
    size. Generated tools now refuse an oversized value by validation, as the
    Creator's own tools do."""
    _root, manifest = project
    uncapped: list[str] = []
    for generated in manifest.files:
        if "/tools/" not in generated.path or not generated.path.endswith(".py"):
            continue
        for node in ast.walk(ast.parse(generated.content)):
            if not isinstance(node, ast.arg) or node.annotation is None:
                continue
            note = ast.unparse(node.annotation)
            if note.startswith("Annotated[str,") and "max_length=" not in note:
                uncapped.append(f"{generated.path}: {node.arg}")
    assert not uncapped, uncapped


# ---------------------------------------------------------------------------
# A verb between the counted thing and the row's own noun keeps the distinct
# count: 'distinct recipients won awards' on a table of awards.
# ---------------------------------------------------------------------------

DISTINCT_BEFORE_A_VERB = [
    "How many unique recipients won awards?",
    "How many distinct recipients won awards from the Department of the Navy?",
    "How many different recipients received awards in fiscal year 2025?",
]


@pytest.mark.parametrize("question", DISTINCT_BEFORE_A_VERB)
def test_a_distinct_count_survives_a_verb_before_the_row_noun(question) -> None:
    spec = _spec("awards")
    spec.jobs_to_be_done = [question]
    spec.tools, notes = design_tools(spec, [])
    plan = next((p for p in spec.tools if p.goal == question), None)
    assert plan is not None, notes
    assert plan.aggregation == "count_distinct", plan
    assert plan.measure_field == "recipient_name", plan


@pytest.mark.parametrize("question", DISTINCT_BEFORE_A_VERB)
def test_the_review_agrees_with_a_distinct_count_before_a_verb(question) -> None:
    spec = _spec("awards")
    spec.jobs_to_be_done = [question]
    spec.tools, _notes = design_tools(spec, [])
    report = review_spec(spec)
    assert question not in _reviewed(spec, "tool_computes_its_question"), report
    assert question not in _reviewed(spec, "every_question_has_a_tool"), report
