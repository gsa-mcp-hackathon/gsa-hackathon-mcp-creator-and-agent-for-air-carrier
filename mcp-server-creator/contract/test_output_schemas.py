"""Every creator_ tool lists a typed output schema, and a real answer fits it.

FastMCP checks each result against the tool's output schema before it leaves
the server, so a model in output_models.py that is stricter than the code
turns a working tool into an error. This walks one design through all ten
tools as a client would, and fails if any answer is refused. A failure body
must still reach the client as the tool's own error, not as a schema error.
Run: uv run pytest contract
"""

from __future__ import annotations

import json

from fastmcp import Client

from mcp_server_creator.app import mcp
from mcp_server_creator.models import ServerSpec

SOURCE = {
    "name": "sales",
    "kind": "uc_table",
    "modality": "structured",
    "catalog": "samples",
    "schema_name": "bakehouse",
    "table": "sales_transactions",
    "schema_text": (
        "transactionID BIGINT, franchiseID BIGINT, dateTime TIMESTAMP, "
        "product STRING, quantity BIGINT, totalPrice DOUBLE, paymentMethod STRING"
    ),
    "try_live_inspection": False,
}


def _fits(result) -> dict:
    assert not result.is_error, result.content[0].text
    assert result.structured_content
    return result.structured_content


async def test_every_tool_lists_named_output_fields():
    async with Client(mcp) as client:
        tools = await client.list_tools()
    assert len(tools) == 10
    for tool in tools:
        fields = (tool.outputSchema or {}).get("properties", {})
        assert len(fields) >= 4, f"{tool.name} does not say what it returns"


async def test_one_design_through_every_tool_fits_the_schemas():
    called = set()
    async with Client(mcp) as client:

        async def call(name: str, arguments: dict | None = None):
            called.add(name)
            return await client.call_tool(name, arguments or {}, raise_on_error=False)

        _fits(await call("creator_list_library"))
        _fits(await call("creator_load_document", {"name": "mcp-a-creator"}))
        _fits(await call("creator_check_environment", {"environment": "gov_il5"}))
        started = _fits(
            await call(
                "creator_start_design",
                {
                    "purpose": "Daily bakery sales by franchise and product",
                    "primary_user": "Franchise operations analyst",
                    "jobs_to_be_done": ["Which product sold the most last month?"],
                },
            )
        )
        design = {"design_id": started["design_id"]}
        _fits(await call("creator_add_data_source", {**design, **SOURCE}))
        designed = _fits(await call("creator_design_tools", design))
        assert designed["tool_count"] == len(designed["tools"]) > 0
        _fits(await call("creator_review_server", design))
        _fits(await call("creator_generate_project", design))
        # Writing is off by default and deploying needs a workspace. Each
        # must answer in its own words, which means its body validated.
        written = await call("creator_write_project", {**design, "dry_run": True})
        assert written.structured_content["write_enabled"] is False
        deployed = await call("creator_deploy_server", design)
        assert deployed.structured_content.get("status")
        tools = {tool.name for tool in await client.list_tools()}
    assert called == tools


async def test_a_failure_body_keeps_its_own_message():
    async with Client(mcp) as client:
        result = await client.call_tool(
            "creator_load_document", {"name": "no-such-skill"}, raise_on_error=False
        )
    assert result.is_error
    assert result.structured_content["error"]
    assert "creator_list_library" in result.structured_content["hint"]


async def test_the_spec_schema_resource_is_the_models_schema():
    """spec_json is a string so any model can pass it; this is its shape."""
    async with Client(mcp) as client:
        contents = await client.read_resource("creator://schema/server-spec")
        bad = await client.call_tool(
            "creator_design_tools",
            {"spec_json": json.dumps({"server_name": "x"})},
            raise_on_error=False,
        )
    assert json.loads(contents[0].text) == ServerSpec.model_json_schema()
    assert bad.is_error
    assert "creator://schema/server-spec" in bad.structured_content["error"]
