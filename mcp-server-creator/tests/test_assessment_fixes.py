"""Regression tests for the 2026-11-18 assessment fixes.

Each test reproduces a wrong tool the designer proposed in a live build on
samples.bakehouse or samples.tpch, and pins the corrected behavior.
"""

from __future__ import annotations

from mcp_server_creator.designer import _job_tool, _tool_name, design_tools
from mcp_server_creator.models import (
    DataModality,
    DataSourceProfile,
    FieldProfile,
    FieldRole,
    ServerSpec,
    Severity,
    SourceKind,
)
from mcp_server_creator.profiling import infer_role
from mcp_server_creator.review.rubric import review_spec


def _field(name, data_type, enum_values=()):
    return FieldProfile(
        name=name,
        data_type=data_type,
        role=infer_role(name, data_type, None, len(enum_values) or None),
        enum_values=list(enum_values),
    )


def _sales() -> DataSourceProfile:
    return DataSourceProfile(
        name="sales",
        kind=SourceKind.UC_TABLE,
        modality=DataModality.STRUCTURED,
        catalog="samples",
        schema_name="bakehouse",
        table="sales_transactions",
        grain="one sales transaction",
        fields=[
            _field("transactionID", "bigint"),
            _field("customerID", "bigint"),
            _field("franchiseID", "bigint"),
            _field("dateTime", "timestamp"),
            _field("product", "string", ["Golden Gate Ginger", "Pearly Pies"]),
            _field("quantity", "bigint"),
            _field("totalPrice", "bigint"),
        ],
    )


def _tpch() -> list[DataSourceProfile]:
    lineitem = DataSourceProfile(
        name="lineitem",
        kind=SourceKind.UC_TABLE,
        modality=DataModality.STRUCTURED,
        catalog="samples",
        schema_name="tpch",
        table="lineitem",
        grain="one order line item",
        fields=[
            _field("l_orderkey", "bigint"),
            _field("l_linenumber", "int"),
            _field("l_discount", "decimal(18,2)"),
            _field("l_shipinstruct", "string", ["NONE", "COLLECT COD"]),
            _field("l_shipmode", "string", ["AIR", "RAIL"]),
            _field("l_commitdate", "date"),
            _field("l_receiptdate", "date"),
        ],
    )
    orders = DataSourceProfile(
        name="orders",
        kind=SourceKind.UC_TABLE,
        modality=DataModality.STRUCTURED,
        catalog="samples",
        schema_name="tpch",
        table="orders",
        grain="one order",
        fields=[
            _field("o_orderkey", "bigint"),
            _field("o_custkey", "bigint"),
            _field("o_orderstatus", "string", ["F", "O", "P"]),
            _field("o_orderpriority", "string", ["1-URGENT", "2-HIGH"]),
            _field("o_clerk", "string", ["Clerk#000000001", "Clerk#000000002"]),
            _field("o_orderdate", "date"),
        ],
    )
    return [lineitem, orders]


def _spec(sources, jobs, out_of_scope=(), prefix="t") -> ServerSpec:
    return ServerSpec(
        server_name="t-mcp",
        purpose="Test server.",
        primary_user="an analyst",
        jobs_to_be_done=list(jobs),
        out_of_scope=list(out_of_scope),
        data_sources=sources,
        tool_prefix=prefix,
    )


def test_snake_case_compound_keys_are_identifiers_not_measures():
    for name in ("l_orderkey", "l_partkey", "o_custkey", "l_linenumber"):
        assert infer_role(name, "bigint") is FieldRole.IDENTIFIER, name
    assert infer_role("l_extendedprice", "decimal(18,2)") is FieldRole.MEASURE
    assert infer_role("customerID", "bigint") is FieldRole.IDENTIFIER


def test_tool_names_never_repeat_a_word():
    assert _tool_name("supply", "count", "count") == "supply_count"


def test_top_n_by_measure_groups_by_the_thing_ranked():
    spec = _spec([_sales()], ["What are the top 5 products by revenue?"])
    plan, _ = _job_tool(spec, spec.data_sources[0], spec.jobs_to_be_done[0])
    assert plan is not None
    assert plan.group_field == "product"
    assert plan.measure_field == "totalPrice"


def test_rank_tools_on_dated_tables_take_a_period():
    job = "Which franchise had the most revenue from May 1 to May 17, 2024?"
    spec = _spec([_sales()], [job])
    plan, _ = _job_tool(spec, spec.data_sources[0], job)
    assert plan is not None and plan.group_field == "franchiseID"
    assert {"start_date", "end_date"} <= {p.name for p in plan.params}


def test_for_one_entity_becomes_a_filter():
    job = "What were daily sales for one franchise?"
    spec = _spec([_sales()], [job])
    plan, _ = _job_tool(spec, spec.data_sources[0], job)
    assert plan is not None and plan.granularity == "day"
    assert "franchiseid" in {p.name for p in plan.params}


def test_adjacent_words_pick_the_named_column():
    job = "What is the average discount by ship mode?"
    spec = _spec(_tpch(), [job])
    plan, _ = _job_tool(spec, spec.data_sources[0], job)
    assert plan is not None and plan.group_field == "l_shipmode"


def test_row_comparisons_and_business_states_are_reported_not_faked():
    jobs = [
        "Which line items arrived after their commit date in 1997?",
        "Which ship mode is late most often?",
    ]
    spec = _spec(_tpch(), jobs)
    for job in jobs:
        plan, reason = _job_tool(spec, spec.data_sources[0], job)
        assert plan is None and reason, job


def test_out_of_scope_rules_exclude_the_columns_they_name():
    spec = _spec(
        _tpch(),
        ["How many urgent orders are still open?"],
        out_of_scope=["Questions about individual clerks"],
    )
    design_tools(spec)
    orders = spec.source_by_name("orders")
    assert next(f for f in orders.fields if f.name == "o_clerk").pii
    sales = _spec([_sales()], ["x"], out_of_scope=["Show individual customers"])
    design_tools(sales)
    assert next(f for f in sales.data_sources[0].fields if f.name == "customerID").pii


def test_no_search_tool_over_identifiers_only():
    spec = _spec([_sales()], ["What are the top 5 products by revenue?"])
    plans, _ = design_tools(spec)
    assert not any(p.name == "t_search_sales" for p in plans)


def test_question_goes_to_the_source_it_names():
    spec = _spec(_tpch(), ["How many urgent orders are still open?"])
    plans, _ = design_tools(spec)
    counts = [p for p in plans if p.aggregation == "count" and p.goal]
    assert [p.source for p in counts if "urgent" in p.goal] == ["orders"]


def test_design_never_exceeds_the_tool_cap():
    jobs = [
        "Which line items arrived after their commit date in 1997?",
        "How many urgent orders are still open?",
        "Which ship mode is late most often?",
        "What is the average discount by ship mode?",
    ]
    plans, _ = design_tools(_spec(_tpch(), jobs))
    assert len(plans) <= 8


def test_review_blocks_a_sum_of_identifiers_and_flags_unanswered_questions():
    jobs = ["Which ship mode is late most often?"]
    spec = _spec(_tpch(), jobs)
    spec.tools, _ = design_tools(spec)
    report = review_spec(spec)
    checks = {f.check: f for f in report.findings}
    assert "every_question_has_a_tool" in checks
    assert report.scores["honesty"] <= 2

    spec = _spec(_tpch(), ["What is the average discount by ship mode?"])
    spec.tools, _ = design_tools(spec)
    plan = next(p for p in spec.tools if p.measure_field == "l_discount")
    plan.measure_field = "l_orderkey"
    report = review_spec(spec)
    blocker = next(f for f in report.findings if f.check == "measure_is_not_identifier")
    assert blocker.severity is Severity.BLOCKER


# CVN-79 (One Hub) design dsn_6654fa35: usage rules hid the money column and
# page numbers were summed.
CVN79_OUT_OF_SCOPE = [
    "Attribute a budget column to a hull (that is the Attributor's job)",
    "Sum total_dollars_obligated or announced modifications as obligations",
    "Write to, promote, or edit any table",
    "Questions about hulls or programs outside the CVN-78 class corpus",
]


def _cvn79() -> list[DataSourceProfile]:
    cells = DataSourceProfile(
        name="exhibit_cells",
        kind=SourceKind.UC_TABLE,
        modality=DataModality.STRUCTURED,
        catalog="users",
        schema_name="s",
        table="aircarrier_pdf_cells",
        grain="one cell of one PDF table on one page",
        fields=[
            _field("table_id", "string"),
            _field("artifact_id", "string"),
            _field("page", "int"),
            _field("row_idx", "int"),
            _field("col_idx", "int"),
            _field("value", "string"),
            _field("value_kind", "string", ["number", "text", "empty"]),
        ],
    )
    obligations = DataSourceProfile(
        name="obligations_2116",
        kind=SourceKind.UC_TABLE,
        modality=DataModality.STRUCTURED,
        catalog="users",
        schema_name="s",
        table="aircarrier_src_2116_contract_transactions",
        grain="one contract action",
        fields=[
            _field("contract_transaction_unique_key", "string"),
            _field("modification_number", "string"),
            _field("federal_action_obligation", "decimal(20,2)"),
            _field("total_dollars_obligated", "decimal(20,2)"),
            _field("program_acronym", "string"),
            _field("action_date", "date"),
        ],
    )
    return [cells, obligations]


def test_positions_are_identifiers_not_measures():
    for name in ("page", "row_idx", "col_idx", "evidence_page", "sort_index"):
        assert infer_role(name, "int") is FieldRole.IDENTIFIER, name
    assert infer_role("page_count", "int") is FieldRole.MEASURE
    assert infer_role("attempts", "int") is FieldRole.MEASURE


def test_usage_rules_hide_no_columns():
    spec = _spec(
        _cvn79(),
        ["How much has been obligated on the contract, by fiscal year?"],
        out_of_scope=CVN79_OUT_OF_SCOPE,
    )
    _, notes = design_tools(spec)
    hidden = {f.name for s in spec.data_sources for f in s.fields if f.pii}
    assert hidden == set(), hidden
    assert not any("excluded from every tool" in n for n in notes)
    # 'Sum total_dollars_obligated ...' keeps the column but stops summing it.
    roles = {f.name: f.role for f in spec.data_sources[1].fields}
    assert roles["total_dollars_obligated"] is FieldRole.DIMENSION
    assert roles["federal_action_obligation"] is FieldRole.MEASURE
    assert any("never added up" in n for n in notes)


def test_withholding_rules_still_hide_what_they_name():
    spec = _spec(
        [_sales()],
        ["x"],
        out_of_scope=["Anything about individual customers' card numbers"],
    )
    design_tools(spec)
    assert next(f for f in spec.data_sources[0].fields if f.name == "customerID").pii


def test_no_tool_adds_up_page_numbers():
    spec = _spec(
        _cvn79(),
        ["What does the P-5c exhibit say for this cost category, on which page?"],
        out_of_scope=CVN79_OUT_OF_SCOPE,
    )
    plans, _ = design_tools(spec)
    measures = {p.measure_field for p in plans if p.measure_field}
    assert not measures & {"page", "row_idx", "col_idx"}, measures


# Live CVN-79 run on 2026-11-18 (design dsn_98ee2fc3): seven defects.
JOBS_CVN79 = [
    "What does the P-5c exhibit say for this cost category, on which page, "
    "with which legends?",
    "How much has been obligated on contract N00024-09-C-2116, by fiscal year?",
    "Which documents and tables mention this contract number or hull?",
    "Which open gaps and variances are queued, and for which agent?",
    "Is this contract number safe to use for CVN-79, or is it a collision or "
    "exclusion?",
]


def _lossless_2116() -> DataSourceProfile:
    money = FieldProfile(
        name="federal_action_obligation",
        data_type="string",
        role=FieldRole.MEASURE,
        stored_as_text=True,
    )
    return DataSourceProfile(
        name="obligations_2116",
        kind=SourceKind.UC_TABLE,
        modality=DataModality.STRUCTURED,
        catalog="users",
        schema_name="s",
        table="aircarrier_src_2116_contract_transactions",
        grain="one contract action",
        fields=[
            _field("_row_num", "bigint"),
            _field("contract_transaction_unique_key", "string"),
            money,
            _field("action_date", "string"),
            _field("action_date_fiscal_year", "string"),
            _field(
                "other_than_full_and_open_competition_code", "string", ["ONE", "UNQ"]
            ),
        ],
    )


def _work() -> DataSourceProfile:
    return DataSourceProfile(
        name="work_register",
        kind=SourceKind.UC_TABLE,
        modality=DataModality.STRUCTURED,
        catalog="users",
        schema_name="s",
        table="aircarrier_work",
        grain="one work item",
        fields=[
            _field("work_id", "string"),
            _field("kind", "string", ["artifact", "claim", "gap", "variance"]),
            _field("state", "string", ["closed", "open_question", "promoted"]),
            _field("owner_agent", "string", ["collect", "investigator", "reader"]),
            _field("updated_at", "timestamp"),
        ],
    )


def test_loader_columns_are_identifiers():
    assert infer_role("_row_num", "bigint") is FieldRole.IDENTIFIER
    assert infer_role("_source_locator", "string") is FieldRole.IDENTIFIER


def test_text_stored_amount_is_summed_by_fiscal_year_with_a_cast():
    from mcp_server_creator.generators import generate_full_project

    spec = _spec([_lossless_2116()], [JOBS_CVN79[1]])
    plan, why = _job_tool(spec, spec.data_sources[0], JOBS_CVN79[1])
    assert plan is not None, why
    assert plan.measure_field == "federal_action_obligation"
    assert plan.group_field == "action_date_fiscal_year"
    # The label is grouped as written; it never becomes a date bound.
    assert plan.date_field == "action_date"
    spec.tools = [plan]
    files = generate_full_project(spec).files
    code = next(f.content for f in files if f.path.endswith(f"/{plan.name}.py"))
    assert "TRY_CAST(" in code and "DECIMAL(38, 6)" in code


def test_open_gaps_by_agent_go_to_the_work_register():
    spec = _spec([_lossless_2116(), _work()], [JOBS_CVN79[3]])
    plans, _ = design_tools(spec)
    job_plans = [p for p in plans if p.goal == JOBS_CVN79[3]]
    assert [p.source for p in job_plans] == ["work_register"], job_plans
    assert job_plans[0].group_field == "owner_agent"
    assert not any("competition" in p.name for p in plans)


def test_one_stray_word_does_not_pick_a_grouping():
    from mcp_server_creator.designer import _best_field

    fields = _lossless_2116().fields
    assert _best_field(["open", "gaps"], fields) is None


def test_read_questions_need_a_search_not_a_total():
    spec = _spec(_cvn79(), [JOBS_CVN79[0], JOBS_CVN79[2], JOBS_CVN79[4]])
    for job in spec.jobs_to_be_done:
        assert _job_tool(spec, spec.data_sources[0], job) == (None, "")


def test_review_flags_an_unanswered_how_much_question():
    spec = _spec([_work()], [JOBS_CVN79[1]])
    spec.tools, _ = design_tools(spec)
    report = review_spec(spec)
    finding = next(f for f in report.findings if f.check == "every_question_has_a_tool")
    assert "How much has been obligated" in finding.evidence


def test_high_variety_text_gets_a_search_tool():
    cells = _cvn79()[0]
    for field in cells.fields:
        if field.name == "value":
            field.role = FieldRole.TEXT
    spec = _spec([cells, _work()], JOBS_CVN79)
    plans, _ = design_tools(spec)
    assert any(
        p.pattern.value == "search" and p.source == "exhibit_cells" for p in plans
    )


def test_a_source_with_no_columns_blocks_generation():
    empty = DataSourceProfile(
        name="exhibit_cells",
        kind=SourceKind.UC_TABLE,
        modality=DataModality.STRUCTURED,
        catalog="users",
        schema_name="s",
        table="aircarrier_pdf_cells",
        fields=[],
    )
    spec = _spec([empty], ["x"])
    spec.tools, notes = design_tools(spec)
    assert any("has no columns" in n for n in notes)
    report = review_spec(spec)
    blocker = next(f for f in report.findings if f.check == "sources_have_columns")
    assert blocker.severity is Severity.BLOCKER


# Hand fixes made to the deployed ops server, now generated.
def _wide_2116() -> DataSourceProfile:
    source = _lossless_2116()
    source.fields += [
        _field("transaction_description", "string"),
        _field("modification_number", "string"),
    ] + [_field(f"extra_col_{i}", "string") for i in range(30)]
    return source


def _generated_search(spec):
    from mcp_server_creator.generators import generate_full_project

    spec.tools, _ = design_tools(spec)
    search = next(p for p in spec.tools if p.pattern.value == "search")
    files = generate_full_project(spec).files
    code = next(f.content for f in files if f.path.endswith(f"/{search.name}.py"))
    return search, code


def test_paged_search_has_a_stable_order():
    _, code = _generated_search(_spec([_wide_2116()], [JOBS_CVN79[1]]))
    assert "ORDER BY" in code and "ordered_by" in code


def test_search_reports_the_exact_total_a_question_sums():
    search, code = _generated_search(_spec([_wide_2116()], [JOBS_CVN79[1]]))
    assert search.measure_field == "federal_action_obligation"
    assert "SUM(" in code and "TRY_CAST(" in code
    assert "federal_action_obligation_total" in code


def test_wide_table_search_returns_key_fields_by_default():
    search, code = _generated_search(_spec([_wide_2116()], [JOBS_CVN79[1]]))
    assert any(p.name == "full_detail" for p in search.params)
    assert "if full_detail" in code


def test_search_takes_an_exact_key_the_questions_name():
    spec = _spec([_wide_2116()], ["Which actions carry modification number P00067?"])
    search, _ = _generated_search(spec)
    exact = [p for p in search.params if p.source_field == "modification_number"]
    assert exact and exact[0].operator == "="


def test_tool_prefix_skips_generic_name_parts():
    def prefix(name):
        return ServerSpec(server_name=name, purpose="p", primary_user="u").tool_prefix

    assert prefix("mcp-aircarrier-ops-v2") == "aircarrier"
    assert prefix("contract-triage-mcp") == "contract"
    assert prefix("mcp-server") == "mcp"
