"""Free text in a design can never become code in the generated project.

The purpose, the primary user, the questions and the out-of-scope list are
written by a model that may have read untrusted text. Before this test, a
purpose of  x\"\"\"+str(__import__("os").system("..."))+\"\"\"  made the
generated correctness judge run a shell command on import, and a plain
double quote made pyproject.toml and server.json unparseable.

Every payload carries the marker PWNED. After generation, every Python file
must parse and the marker may appear only inside string constants; every
TOML, JSON, YAML and XML file must still parse.
"""

from __future__ import annotations

import ast
import json
import tomllib
import xml.etree.ElementTree as ElementTree

import pytest
import yaml

from mcp_server_creator.designer import design_tools
from mcp_server_creator.generators import generate_full_project
from mcp_server_creator.models import (
    DataModality,
    DataSourceProfile,
    ServerSpec,
    SourceKind,
)
from mcp_server_creator.profiling import parse_tabular_text

MARKER = "PWNED"
PAYLOADS = [
    'x"""+str(__import__("os").system("PWNED"))+"""',
    "x'''+str(__import__('os').system('PWNED'))+'''",
    'x"+__import__("os").system("PWNED")+"',
    'trailing backslash \\" PWNED \\',
    'x\n"""\nPWNED()\n"""\n',
    "{input} {{PWNED}} }}{{ {0}",
    "a: b # PWNED\nkey: [PWNED, {x: 1}]",
    "</description><PWNED/>&amp; <![CDATA[",
]


class _StripStrings(ast.NodeTransformer):
    def visit_Constant(self, node: ast.Constant) -> ast.AST:
        if isinstance(node.value, str):
            return ast.copy_location(ast.Constant(""), node)
        return node


def _spec(payload: str) -> ServerSpec:
    source = DataSourceProfile(
        name="sales",
        kind=SourceKind.UC_TABLE,
        modality=DataModality.STRUCTURED,
        catalog="main",
        schema_name="default",
        table="sales",
        fields=parse_tabular_text("amount DOUBLE, region STRING, sold_at TIMESTAMP"),
    )
    spec = ServerSpec(
        server_name="injection-check",
        purpose=f"Sales totals. {payload}",
        primary_user=f"Analyst {payload}",
        jobs_to_be_done=[f"What is the total amount by region? {payload}"],
        out_of_scope=[f"individual customers {payload}"],
        data_sources=[source],
    )
    spec.tools, _ = design_tools(spec)
    return spec


@pytest.mark.parametrize("payload", PAYLOADS)
def test_free_text_never_becomes_code_or_breaks_a_file(payload):
    manifest = generate_full_project(_spec(payload))
    problems: list[str] = []
    for generated in manifest.files:
        path, content = generated.path, generated.content
        try:
            if path.endswith(".py"):
                tree = ast.parse(content, filename=path)
                code_only = ast.unparse(_StripStrings().visit(tree))
                if MARKER in code_only:
                    problems.append(f"{path}: marker outside a string")
            elif path.endswith(".toml"):
                tomllib.loads(content)
            elif path.endswith(".json"):
                json.loads(content)
            elif path.endswith((".yml", ".yaml")):
                list(yaml.safe_load_all(content))
            elif path.endswith(".xml"):
                ElementTree.fromstring(content)
        except Exception as error:  # any parse failure is a finding
            problems.append(f"{path}: {type(error).__name__}: {error}")
    assert not problems, problems


def test_databricks_bundle_keeps_the_purpose_as_one_string():
    manifest = generate_full_project(_spec("a: b # c"))
    bundle = next(f for f in manifest.files if f.path == "databricks.yml")
    apps = yaml.safe_load(bundle.content)["resources"]["apps"]
    (app,) = apps.values()
    assert app["description"].startswith("Sales totals. a: b # c")
