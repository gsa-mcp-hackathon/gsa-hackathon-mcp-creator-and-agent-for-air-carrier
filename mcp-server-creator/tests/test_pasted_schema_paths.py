"""The pasted-schema path, driven through the MCP tools as a client would.

Live inspection is the main path inside Databricks; a pasted schema is the
fallback and the only path outside it. These pin three failures found by an
end-to-end run of the README prompts with pasted schemas:

* a table name that is not a plain identifier was accepted and produced a
  server whose every call failed its own identifier check;
* `text_column` was ignored, so a review table's text read as a dimension;
* a text table marked unstructured got only a describe tool.
"""

from __future__ import annotations

import pytest
from fastmcp import Client

from mcp_server_creator.app import mcp

REVIEW_JOBS = [
    "Show reviews that mention wait times",
    "Which franchise has the most reviews?",
]
REVIEW_SCHEMA = (
    "franchiseID BIGINT, review_date TIMESTAMP, new_id BIGINT, review STRING"
)


async def _start(client: Client, jobs: list[str]) -> str:
    result = await client.call_tool(
        "creator_start_design",
        {
            "purpose": "Customer review insights",
            "primary_user": "Customer experience lead",
            "jobs_to_be_done": jobs,
        },
    )
    return result.structured_content["design_id"]


@pytest.mark.parametrize(
    "coordinates",
    [
        {"catalog": "main", "schema_name": "default", "table": "t; DROP TABLE x --"},
        {"catalog": "main`; --", "schema_name": "default", "table": "t"},
        {"catalog": "main", "schema_name": "de fault", "table": "t"},
    ],
)
async def test_pasted_schema_still_rejects_unsafe_table_coordinates(coordinates):
    async with Client(mcp) as client:
        design_id = await _start(client, ["What is the total amount?"])
        result = await client.call_tool(
            "creator_add_data_source",
            {
                "design_id": design_id,
                "name": "t",
                "kind": "uc_table",
                "modality": "structured",
                "schema_text": "amount DOUBLE, created_at TIMESTAMP",
                "try_live_inspection": False,
                **coordinates,
            },
            raise_on_error=False,
        )
    body = result.structured_content
    assert result.is_error  # error_contract: a refusal reaches the client as an error
    assert "Invalid Unity Catalog coordinates" in body["error"]


async def test_text_column_is_read_as_text_and_a_text_table_is_searchable():
    async with Client(mcp) as client:
        design_id = await _start(client, REVIEW_JOBS)
        added = await client.call_tool(
            "creator_add_data_source",
            {
                "design_id": design_id,
                "name": "reviews",
                "kind": "uc_table",
                "modality": "unstructured",
                "catalog": "samples",
                "schema_name": "bakehouse",
                "table": "media_customer_reviews",
                "schema_text": REVIEW_SCHEMA,
                "text_column": "review",
                "citation_columns": ["review_date", "franchiseID"],
                "try_live_inspection": False,
            },
        )
        assert added.structured_content["summary"]["by_role"]["text"] == ["review"]
        designed = await client.call_tool(
            "creator_design_tools", {"design_id": design_id}
        )
    body = designed.structured_content
    patterns = {tool["pattern"] for tool in body["tools"]}
    assert "search" in patterns, body["tools"]
    assert any("keyword matching" in note for note in body["design_notes"])


async def test_unstructured_source_with_no_columns_keeps_the_corpus_path():
    """A document corpus with no table behind it is unchanged: describe only,
    until an AI Search index exists."""
    async with Client(mcp) as client:
        design_id = await _start(client, REVIEW_JOBS)
        await client.call_tool(
            "creator_add_data_source",
            {
                "design_id": design_id,
                "name": "policies",
                "kind": "uc_volume_files",
                "modality": "unstructured",
                "volume_path": "/Volumes/main/default/policies",
            },
        )
        designed = await client.call_tool(
            "creator_design_tools", {"design_id": design_id}
        )
    names = [tool["name"] for tool in designed.structured_content["tools"]]
    assert names and all("search" not in name for name in names)


async def test_write_project_refuses_a_design_with_no_tools(tmp_path, monkeypatch):
    from mcp_server_creator.config import settings

    monkeypatch.setattr(settings, "creator_allow_write", True)
    monkeypatch.setattr(settings, "creator_output_root", str(tmp_path))
    async with Client(mcp) as client:
        design_id = await _start(client, ["What is the total amount?"])
        result = await client.call_tool(
            "creator_write_project",
            {"destination": "local", "design_id": design_id, "dry_run": False},
            raise_on_error=False,
        )
    assert result.is_error
    assert result.structured_content["error"] == "The design has no tools yet."
    assert not any(tmp_path.iterdir())
