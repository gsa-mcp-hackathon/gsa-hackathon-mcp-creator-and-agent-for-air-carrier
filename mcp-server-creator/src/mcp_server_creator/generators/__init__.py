"""Code generators: specification in, complete project out.

`generate_full_project` is the usual entry point. The individual generators
are exposed so a caller can regenerate one layer, such as the deployment kit
after moving a table, without rewriting the whole project.
"""

from __future__ import annotations

from mcp_server_creator.generators import (
    dataaccess,
    databricks,
    evaluation,
    formatting,
    project,
    provenance,
    toolcode,
)
from mcp_server_creator.models import FileManifest, ServerSpec

__all__ = [
    "dataaccess",
    "databricks",
    "evaluation",
    "formatting",
    "generate_full_project",
    "project",
    "toolcode",
]


def generate_full_project(
    spec: ServerSpec,
    include_evaluation: bool = True,
    include_deployment: bool = True,
) -> FileManifest:
    """Generate the whole project: server, deployment kit, and evaluation."""
    manifest = project.generate_project(spec)
    if include_deployment:
        manifest.merge(databricks.generate_deployment(spec))
    if include_evaluation:
        manifest.merge(evaluation.generate_evaluation(spec))
        _add_eval_dependency_group(manifest, spec)

    provenance.add_files(manifest, spec)
    # Format before the files leave the generator, so the project passes its
    # own `ruff check` and `ruff format --check` on the first commit.
    formatting.format_manifest_python(manifest.files, first_party=spec.package_name)
    # Last: the lock hashes every file as it will be written.
    provenance.stamp(manifest, spec)
    if not formatting.ruff_available():
        manifest.warnings.append(
            "ruff was not available, so the generated Python was not "
            "formatted. Run 'uv run ruff format .' in the new project "
            "before the first commit, or its CI format check will fail."
        )

    manifest.next_steps = [
        "Write the manifest to disk.",
        "uv sync && uv run ruff format . && uv run pytest tests/ -v",
        "Connect a local client over stdio and ask one real question.",
        "Fill in the golden answers via eval/answer_key.py, then run the "
        "--no-tools baseline followed by the tooled run.",
        "Deploy with deploy/databricks/deploy.sh, then apply grants.sql to "
        "the app service principal.",
    ]
    return manifest


def _add_eval_dependency_group(manifest: FileManifest, spec: ServerSpec) -> None:
    """Write the evaluation dependencies to eval/requirements.txt.

    They stay out of pyproject.toml on purpose. uv resolves every dependency
    group together with the project and installs `dev` by default, so a
    harness pin that disagrees with the server's own pins (arize-phoenix 20.7
    and later need fastmcp 4; the server pins fastmcp below 4) would make
    `uv sync` fail before the server ever starts. The Phoenix harness launches
    the server as a subprocess, so it does not need to share its environment.
    """
    lines = [
        "# Evaluation harness dependencies (eval/phoenix and eval/answer_key.py).",
        "# Kept apart from pyproject.toml so `uv sync` for the server never has",
        "# to resolve them. Install into an isolated environment, for example:",
        "#   cd eval/phoenix",
        "#   uv run --no-project --with-requirements ../requirements.txt \\",
        "#       python run_experiment.py --dataset-name <name>",
        *evaluation.eval_dependencies(),
        "",
    ]
    manifest.add(
        "eval/requirements.txt",
        "\n".join(lines),
        f"Evaluation dependencies for {spec.server_name}, isolated from the server",
    )
