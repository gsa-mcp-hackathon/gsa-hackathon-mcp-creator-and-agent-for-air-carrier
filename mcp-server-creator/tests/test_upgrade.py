"""Upgrading a generated project keeps the owner's edits (round 10, D2).

A template change is simulated by rewriting a file and its lock entry to an
"older template" text, as if an earlier Creator had generated it.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from mcp_server_creator.generators import generate_full_project
from mcp_server_creator.upgrade import (
    NotACreatorProject,
    apply_upgrade,
    main,
    plan_upgrade,
)

LOCK = ".mcp-creator/lock.json"
OWNED = ".mcp-creator/owned.txt"
BAKEHOUSE = Path(__file__).resolve().parents[2] / "mcp-servers" / "mcp-bakehouse-sales"


@pytest.fixture
def project(designed_spec, tmp_path):
    for f in generate_full_project(designed_spec).files:
        target = tmp_path / "proj" / f.path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f.content, encoding="utf-8")
    return tmp_path / "proj"


def _older_template(project: Path, path: str, text: str) -> None:
    """Make `path` look as if an earlier Creator generated `text` there."""
    (project / path).write_text(text, encoding="utf-8")
    lock = json.loads((project / LOCK).read_text())
    lock["files"][path] = hashlib.sha256(text.encode()).hexdigest()
    lock["creator_version"] = "0.9.0"
    (project / LOCK).write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")


def _drift(project: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, ".mcp-creator/check_drift.py"],
        cwd=project,
        capture_output=True,
        text=True,
    )


def test_a_fresh_project_has_nothing_to_upgrade(project):
    plan = plan_upgrade(project)
    assert plan.writes == [] and plan.can_apply
    assert not plan.actions["retired"] and not plan.actions["owned"]


def test_an_unedited_file_takes_the_new_template(project):
    current = (project / "README.md").read_text()
    _older_template(project, "README.md", "# Old README\n")
    plan = plan_upgrade(project)
    assert plan.from_version == "0.9.0"
    assert plan.actions["update"] == ["README.md"]
    apply_upgrade(plan)
    assert (project / "README.md").read_text() == current
    assert _drift(project).returncode == 0


def test_an_owned_file_is_kept_when_the_template_changes(project):
    _older_template(project, "README.md", "# Old README\n")
    (project / "README.md").write_text("# Old README\nThe owner's note.\n")
    (project / OWNED).write_text((project / OWNED).read_text() + "README.md\n")
    plan = plan_upgrade(project)
    assert plan.actions["owned"] == ["README.md"] and plan.can_apply
    apply_upgrade(plan)
    assert "The owner's note." in (project / "README.md").read_text()
    assert _drift(project).returncode == 0  # declared, so CI stays green


def test_an_undeclared_edit_over_a_changed_template_stops_the_upgrade(project):
    _older_template(project, "README.md", "# Old README\n")
    (project / "README.md").write_text("# Old README\nAn undeclared edit.\n")
    lock_before = (project / LOCK).read_text()
    plan = plan_upgrade(project)
    assert plan.actions["conflict"] == ["README.md"] and not plan.can_apply
    with pytest.raises(ValueError):
        apply_upgrade(plan)
    assert main([str(project), "--write"]) == 1
    assert "An undeclared edit." in (project / "README.md").read_text()
    assert (project / LOCK).read_text() == lock_before


def test_an_edit_where_the_template_did_not_move_is_left_to_the_drift_check(project):
    readme = project / "README.md"
    readme.write_text(readme.read_text() + "\nAn edit.\n")
    plan = plan_upgrade(project)
    assert "README.md" in plan.actions["unchanged"] and plan.writes == []
    assert "undeclared: README.md" in _drift(project).stdout


def test_a_missing_generated_file_is_restored(project):
    (project / "README.md").unlink()
    plan = plan_upgrade(project)
    assert plan.actions["add"] == ["README.md"]
    apply_upgrade(plan)
    assert (project / "README.md").exists()


def test_a_folder_without_a_lock_is_refused(tmp_path, capsys):
    with pytest.raises(NotACreatorProject):
        plan_upgrade(tmp_path)
    assert main([str(tmp_path)]) == 2


def test_the_committed_bakehouse_server_is_current():
    plan = plan_upgrade(BAKEHOUSE)  # reads only
    assert plan.writes == [] and plan.can_apply, plan.summary()
    assert not plan.actions["retired"]
