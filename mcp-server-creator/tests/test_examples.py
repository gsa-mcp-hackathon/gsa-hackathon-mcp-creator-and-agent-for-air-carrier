"""The starter examples must name data that exists, and say whose tool it is."""

from __future__ import annotations

from pathlib import Path

from mcp_server_creator import examples
from mcp_server_creator.app import mcp

ROOT = Path(__file__).resolve().parents[1]


def test_every_prompt_names_the_creator():
    for prompt in examples.prompts():
        assert prompt.startswith("Use MCP A Creator"), prompt


def test_examples_cover_several_people():
    personas = {e["persona"] for e in examples.EXAMPLES}
    assert len(personas) >= 4


def test_concrete_tables_are_samples_tables_named_in_the_prompt():
    for e in examples.EXAMPLES:
        for table in e["tables"]:
            assert table.startswith("samples."), table
            assert table in e["prompt"], table


def test_own_table_example_is_a_placeholder_and_checks_existence():
    own = [e for e in examples.EXAMPLES if not e["tables"]]
    assert own, "keep one bring-your-own-table template"
    for e in own:
        assert "<catalog.schema." in e["prompt"]
        assert "confirm the table exists" in e["prompt"]


def test_no_example_points_at_a_table_that_does_not_exist():
    for path in [
        ROOT / "README.md",
        ROOT / "src/mcp_server_creator/app.py",
        ROOT / "src/mcp_server_creator/routes.py",
        ROOT / "src/mcp_server_creator/examples.py",
    ]:
        assert "main.contracts" not in path.read_text(encoding="utf-8"), path


def test_instructions_carry_the_examples_and_the_existence_check():
    text = mcp.instructions or ""
    for prompt in examples.prompts():
        assert prompt in text
    assert "Confirm every table exists" in text


# The weapon-system example, checked on a USAspending contract transactions
# schema: each question gets the tool it asks for and the review agrees.
_TRANSACTIONS = (
    "contract_transaction_unique_key STRING, contract_award_unique_key STRING, "
    "award_id_piid STRING, modification_number STRING, "
    "federal_action_obligation DOUBLE, total_dollars_obligated DOUBLE, "
    "current_total_value_of_award DOUBLE, action_date DATE, "
    "action_date_fiscal_year INT, recipient_name STRING, recipient_uei STRING, "
    "funding_office_name STRING, awarding_agency_name STRING, "
    "transaction_description STRING, product_or_service_code STRING"
)
_WEAPON_TOOLS = {
    "What is the total federal action obligation by fiscal year?": (
        "rank", "action_date_fiscal_year"),
    "What is the total federal action obligation by PIID?": (
        "rank", "award_id_piid"),
    "Show monthly federal action obligation from October 1, 2023 to "
    "September 30, 2024": ("trend", ""),
    "List the contract actions for a given PIID": ("lookup", ""),
}  # fmt: skip


async def test_the_weapon_system_example_designs_the_tool_each_question_asks_for():
    from fastmcp import Client

    example = next(e for e in examples.EXAMPLES if "weapon system" in e["persona"])
    for question in _WEAPON_TOOLS:
        assert question.split(" from ")[0] in example["prompt"], question
    async with Client(mcp) as client:
        started = await client.call_tool(
            "creator_start_design",
            {
                "purpose": "Answer a weapon system cost analyst's questions "
                "about the program's contract obligations",
                "primary_user": "Weapon system cost analyst",
                "jobs_to_be_done": list(_WEAPON_TOOLS),
            },
        )
        design_id = started.structured_content["design_id"]
        await client.call_tool(
            "creator_add_data_source",
            {
                "design_id": design_id,
                "name": "contract_transactions",
                "kind": "uc_table",
                "modality": "structured",
                "catalog": "main",
                "schema_name": "program",
                "table": "contract_transactions",
                "schema_text": _TRANSACTIONS,
                "try_live_inspection": False,
            },
        )
        designed = await client.call_tool(
            "creator_design_tools", {"design_id": design_id}
        )
        reviewed = await client.call_tool(
            "creator_review_server", {"design_id": design_id}, raise_on_error=False
        )
    tools = {t["goal"]: t for t in designed.structured_content["tools"]}
    for question, (pattern, group) in _WEAPON_TOOLS.items():
        tool = tools[question]
        assert tool["pattern"] == pattern, tool
        assert group in tool["name"], tool
        if pattern in ("rank", "trend"):
            assert "federal_action_obligation" in tool["name"], tool
    flagged = " ".join(
        f["evidence"]
        for f in reviewed.structured_content["findings"]
        if f["check"] in ("tool_computes_its_question", "every_question_has_a_tool")
    )
    for question in _WEAPON_TOOLS:
        assert question not in flagged, flagged
