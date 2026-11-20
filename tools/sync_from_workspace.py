"""Copy the live Genie Code skills into this Git folder (one-way snapshot).

Since 2026-11-20 the apps and jobs deploy from this repo, and the old workspace
copies (mcp-server-creator, mcp-servers, the bundle files, the hub notebooks)
were moved to trash; edit those here. Only the skills still live elsewhere
(~/.assistant/skills, where Genie Code reads them), so this script now copies
just those. Run it from a Databricks
notebook or Python session, then review and commit in the Git folder UI.

    exec(open("/Workspace/Users/<you>/gsa-hackathon-mcp-creator-and-agent-for-cvn/tools/sync_from_workspace.py").read())
    report = sync(dry_run=True)   # preview
    report = sync()               # copy

What it does:
* Regular files are copied byte for byte (only when content differs).
* Notebooks are exported as SOURCE and imported into the Git folder
  (outputs are never copied).
* Excluded: nested .git, bundle state (.databricks), caches, virtualenvs,
  .env files (the .env.example files are kept) and video files.
* Nothing is deleted. Files in the repo that no longer exist in the source
  are listed in report["stale"] for you to remove by hand.
"""

from __future__ import annotations

import fnmatch
import hashlib
import os
import shutil

HOME = "/Workspace/Users/xiaobing.shang1.civ@mail.mil"
REPO = f"{HOME}/gsa-hackathon-mcp-creator-and-agent-for-cvn"

# source (workspace) -> destination (relative to REPO)
MAPPINGS = [
    (f"{HOME}/.assistant/skills/aircarrier-collection-request", "genie-code-skills/aircarrier-collection-request"),
    (f"{HOME}/.assistant/skills/aircarrier-verify-figure", "genie-code-skills/aircarrier-verify-figure"),
    (f"{HOME}/.assistant/skills/aircarrier-investigate", "genie-code-skills/aircarrier-investigate"),
]
# notebooks that sit directly in a folder whose other files are not copied
NOTEBOOK_MAPPINGS: list = []

EXCLUDE_DIRS = {
    ".git", ".databricks", ".bundle", ".ruff_cache", ".pytest_cache", "__pycache__",
    ".venv", "venv", "node_modules", "eval-results", ".ipynb_checkpoints",
}
EXCLUDE_FILES = [".env", "eval.env", "*.pyc", "*.pyo", "*.mp4", "*.mov", ".DS_Store"]


def _excluded_file(name: str) -> bool:
    return any(fnmatch.fnmatch(name, pat) for pat in EXCLUDE_FILES)


def _sha(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _notebooks(w, root: str, recursive: bool) -> list:
    """Workspace notebooks under root, skipping excluded folders."""
    out, stack = [], [root]
    while stack:
        cur = stack.pop()
        for obj in w.workspace.list(cur):
            name = obj.path.rsplit("/", 1)[-1]
            kind = obj.object_type.value if obj.object_type else ""
            if kind == "NOTEBOOK":
                out.append(obj)
            elif kind in ("DIRECTORY", "REPO") and recursive and name not in EXCLUDE_DIRS:
                stack.append(obj.path)
    return out


def _copy_notebook(w, obj, dest_dir: str, dry_run: bool, report: dict) -> None:
    from databricks.sdk.service.workspace import ExportFormat, ImportFormat

    name = obj.path.rsplit("/", 1)[-1]
    dest = f"{dest_dir}/{name}"
    report["notebooks"].append(dest.replace(REPO + "/", ""))
    if dry_run:
        return
    content = w.workspace.export(obj.path, format=ExportFormat.SOURCE).content
    w.workspace.mkdirs(dest_dir)
    w.workspace.import_(
        dest, content=content, format=ImportFormat.SOURCE, language=obj.language, overwrite=True
    )


def sync(dry_run: bool = False) -> dict:
    from databricks.sdk import WorkspaceClient

    w = WorkspaceClient()
    report = {"copied": [], "unchanged": 0, "notebooks": [], "skipped": [], "stale": []}
    expected = set()

    for src_root, rel_dest in MAPPINGS:
        dest_root = f"{REPO}/{rel_dest}"
        nb_paths = set()
        for obj in _notebooks(w, src_root, recursive=True):
            nb_paths.add(obj.path)
            sub = os.path.dirname(os.path.relpath(obj.path, src_root))
            dest_dir = os.path.normpath(os.path.join(dest_root, sub))
            _copy_notebook(w, obj, dest_dir, dry_run, report)
            expected.add(os.path.join(dest_dir, obj.path.rsplit("/", 1)[-1]))
        for dp, dn, fn in os.walk(src_root):
            dn[:] = [d for d in dn if d not in EXCLUDE_DIRS]
            rel = os.path.relpath(dp, src_root)
            for f in fn:
                src = os.path.join(dp, f)
                # FUSE shows notebooks as <name>.ipynb/.py; those are handled above
                if os.path.splitext(src)[0] in nb_paths or src in nb_paths:
                    continue
                rel_file = os.path.normpath(os.path.join(rel, f))
                if _excluded_file(f):
                    report["skipped"].append(f"{rel_dest}/{rel_file}")
                    continue
                dest = os.path.join(dest_root, rel_file)
                expected.add(dest)
                if os.path.exists(dest) and _sha(dest) == _sha(src):
                    report["unchanged"] += 1
                    continue
                report["copied"].append(f"{rel_dest}/{rel_file}")
                if not dry_run:
                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    shutil.copyfile(src, dest)

    for src_root, rel_dest in NOTEBOOK_MAPPINGS:
        dest_dir = f"{REPO}/{rel_dest}"
        for obj in _notebooks(w, src_root, recursive=False):
            _copy_notebook(w, obj, dest_dir, dry_run, report)
            expected.add(os.path.join(dest_dir, obj.path.rsplit("/", 1)[-1]))

    # files in the repo copy that no longer exist in any source (never deleted here)
    for _, rel_dest in MAPPINGS + NOTEBOOK_MAPPINGS:
        root = f"{REPO}/{rel_dest}"
        for dp, dn, fn in os.walk(root):
            dn[:] = [d for d in dn if d not in EXCLUDE_DIRS]
            for f in fn:
                p = os.path.join(dp, f)
                if p not in expected and os.path.splitext(p)[0] not in expected:
                    report["stale"].append(p.replace(REPO + "/", ""))

    print(
        f"{'DRY RUN: ' if dry_run else ''}copied {len(report['copied'])}, "
        f"unchanged {report['unchanged']}, notebooks {len(report['notebooks'])}, "
        f"skipped {len(report['skipped'])}, stale {len(report['stale'])}"
    )
    return report
