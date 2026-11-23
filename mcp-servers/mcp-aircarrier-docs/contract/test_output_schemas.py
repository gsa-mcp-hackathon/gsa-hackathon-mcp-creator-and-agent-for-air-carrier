"""Every docs_ tool lists a typed output schema, and a real answer fits it.

FastMCP checks each result against the tool's output schema before it leaves
the server, so a model in output_models.py that is stricter than the code
turns a working tool into an error. This calls every tool through the MCP
client on the fixture corpus the unit tests use and fails if any answer is
refused. Run: PYTHONPATH=src python -m pytest contract
"""
import asyncio
import importlib.util
import sys
from pathlib import Path

import pytest
from fastmcp import Client

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))

from docs_core.corpus import Corpus
from mcp_aircarrier_docs import store, volume
from mcp_aircarrier_docs.app import mcp

_spec = importlib.util.spec_from_file_location("docs_fixture", HERE.parent / "tests" / "test_docs.py")
FIXTURE = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(FIXTURE)
AID = FIXTURE.AID
TABLE = f"{AID}:0095:00"


def _one_page_pdf() -> bytes:
    """The smallest PDF pdfplumber reads: one page, one line of text."""
    stream = b"BT /F1 12 Tf 72 720 Td (Exhibit P-40 Budget Line Item Justification) Tj ET"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
         b"/Resources << /Font << /F1 5 0 R >> >> >>"),
        b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offsets = b"%PDF-1.4\n", []
    for number, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n%s\nendobj\n" % (number, body)
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)
    return out


CALLS = [
    ("docs_status", {}),
    ("docs_list_documents", {}),
    ("docs_document_map", {"artifact_id": AID}),
    ("docs_read_page", {"artifact_id": AID, "page": 95}),
    ("docs_get_table", {"table_id": TABLE}),
    ("docs_find_line_item", {"line_item": "2001"}),
    ("docs_find_line_item", {"line_item": "2001", "budget_cycle": "PB2019"}),
    ("docs_search", {"query": "Total Ship Estimate"}),
    ("docs_find_figure", {"value_musd": "13409.97"}),
    ("docs_find_figure", {"value_musd": "1.23"}),
    ("docs_compare_figures", {"figures": [{"label": "TSE", "value_musd": "13409.97"},
                                          {"label": "none", "value_musd": "1.23"}]}),
    ("docs_tieout_document", {"artifact_id": AID}),
    ("docs_parse_pdf", {"volume_path": "/Volumes/c/s/v/one.pdf"}),
]


@pytest.fixture
def corpus(monkeypatch):
    store.set_corpus(Corpus(*FIXTURE.rows()))
    monkeypatch.setattr(volume, "read", lambda path, limit: _one_page_pdf())


def _tools():
    async def go():
        async with Client(mcp) as client:
            return await client.list_tools()

    return asyncio.run(go())


def test_every_tool_lists_named_output_fields():
    tools = _tools()
    assert len(tools) == 11
    for tool in tools:
        schema = tool.outputSchema or {}
        fields = schema.get("properties", {})
        if schema.get("x-fastmcp-wrap-result"):  # a list result is wrapped as {"result": [...]}
            fields = fields["result"]["items"].get("properties", {})
        assert len(fields) >= 3, f"{tool.name} does not say what it returns"


def test_the_calls_cover_every_tool():
    assert {name for name, _ in CALLS} == {tool.name for tool in _tools()}


@pytest.mark.parametrize("name,arguments", CALLS, ids=[f"{n}-{i}" for i, (n, _) in enumerate(CALLS)])
def test_a_real_answer_fits_the_schema(corpus, name, arguments):
    async def go():
        async with Client(mcp) as client:
            return await client.call_tool(name, arguments, raise_on_error=False)

    result = asyncio.run(go())
    assert not result.is_error, result.content[0].text
    assert result.structured_content
