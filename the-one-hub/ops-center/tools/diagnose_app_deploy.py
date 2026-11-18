#!/usr/bin/env python3
"""Why the deployed app does not have the files the bundle uploaded.

Answers one question: for every file the bundle sends to app/, what is
actually in the workspace, and what type is it.

The reason this script exists. A deploy reported success, 'bundle run'
created a new app deployment, the app started, and every page returned
TemplateNotFound for a template that the CLI's own sync snapshot says it
uploaded. Three explanations survive that evidence and only one of them is
true:

  A  the .html files are NOTEBOOK objects in the workspace, not FILE
     objects. The workspace import API treats .html as a notebook format,
     and a notebook loses its extension, so 'overview.html' becomes a
     notebook called 'overview' and never reaches the container as a
     template.
  B  the files are correct in the workspace and the Apps source copy is
     dropping them.
  C  something else, in which case the listing below says what.

Telling A from B takes one call. Guessing takes an afternoon.

    python3 tools/diagnose_app_deploy.py --profile databricks-dev
    python3 tools/diagnose_app_deploy.py --profile databricks-dev \\
        --remote /Workspace/Users/you@org/.../files/app

Read only. It lists and compares. It changes nothing.
"""
from __future__ import annotations

import argparse
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
LOCAL_APP = ROOT / "app"

# Mirrors databricks.yml sync.exclude plus .gitignore, so "local" here means
# what the bundle actually sends rather than what is on disk.
SKIP_DIRS = {"_preview", "_core", "__pycache__", ".venv"}


def _local_files() -> set[str]:
    out = set()
    for p in LOCAL_APP.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(LOCAL_APP)
        if SKIP_DIRS & set(rel.parts):
            continue
        if rel.suffix == ".pyc":
            continue
        out.add(rel.as_posix())
    return out


def _walk(w, base: str, prefix: str = "") -> dict[str, str]:
    """Every object under base, as {relative path: object_type}."""
    found: dict[str, str] = {}
    try:
        entries = list(w.workspace.list(base))
    except Exception as exc:
        print(f"  cannot list {base}: {type(exc).__name__}: {exc}")
        return found
    for e in entries:
        name = e.path.rsplit("/", 1)[-1]
        rel = f"{prefix}{name}"
        kind = getattr(e.object_type, "value", str(e.object_type))
        if kind == "DIRECTORY":
            found.update(_walk(w, e.path, rel + "/"))
        else:
            found[rel] = kind
    return found


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="databricks-dev")
    ap.add_argument("--remote", default=None,
                    help="Workspace path of the app source. Defaults to the "
                         "source_code_path recorded in the bundle state.")
    args = ap.parse_args()

    remote = args.remote
    if not remote:
        import json
        state = ROOT / ".databricks" / "bundle" / "dev" / "resources.json"
        if not state.exists():
            print("no bundle state. Deploy once, or pass --remote.")
            return 2
        s = json.loads(state.read_text())["state"]
        app = s.get("resources.apps.aircarrier_front_center")
        if not app:
            print("the app is not in the bundle state. Pass --remote.")
            return 2
        remote = app["state"]["source_code_path"]

    try:
        from databricks.sdk import WorkspaceClient
    except ImportError:
        print("pip install databricks-sdk")
        return 2

    w = WorkspaceClient(profile=args.profile)
    print(f"profile  {args.profile}")
    print(f"remote   {remote}")
    print(f"local    {LOCAL_APP}\n")

    remote_objs = _walk(w, remote)
    local = _local_files()

    notebooks = {k: v for k, v in remote_objs.items() if v == "NOTEBOOK"}
    missing = sorted(local - set(remote_objs))
    extra = sorted(set(remote_objs) - local)

    print(f"local files the bundle sends : {len(local)}")
    print(f"objects found in the workspace: {len(remote_objs)}")
    print(f"  FILE     {sum(1 for v in remote_objs.values() if v == 'FILE')}")
    print(f"  NOTEBOOK {len(notebooks)}")
    other = {k: v for k, v in remote_objs.items()
             if v not in ("FILE", "NOTEBOOK")}
    if other:
        print(f"  other    {len(other)}  {sorted(set(other.values()))}")

    verdict = []

    if notebooks:
        print("\nNOTEBOOK objects. These are not files and the app will not "
              "receive them as files:")
        for k in sorted(notebooks)[:30]:
            print(f"  {k}")
        if len(notebooks) > 30:
            print(f"  ... and {len(notebooks) - 30} more")
        verdict.append(
            "A: the workspace holds notebooks where the app needs files. "
            "The import classified them by extension. Rename the affected "
            "files to an extension the workspace does not treat as a "
            "notebook format, for example .html -> .html.j2, and point the "
            "template loader at the new names.")

    if missing:
        print(f"\nMISSING from the workspace entirely ({len(missing)}):")
        for k in missing[:30]:
            print(f"  {k}")
        if len(missing) > 30:
            print(f"  ... and {len(missing) - 30} more")
        verdict.append(
            "The bundle did not upload these, or something removed them. "
            "Check databricks.yml sync.exclude and .gitignore first: a "
            "bundle honours .gitignore, so an ignored path silently never "
            "ships. app/_core/* is already in that position.")

    if extra:
        print(f"\nIn the workspace but not local ({len(extra)}). Stale, or a "
              f"notebook that lost its extension:")
        for k in extra[:30]:
            print(f"  {k}")

    tpl_local = sorted(k for k in local if k.startswith("templates/"))
    tpl_remote = {k: v for k, v in remote_objs.items()
                  if k.startswith("templates/")}
    print(f"\ntemplates/: {len(tpl_local)} local, {len(tpl_remote)} in the "
          f"workspace")
    for k in tpl_local:
        got = tpl_remote.get(k)
        stem = k.rsplit(".", 1)[0]
        alt = tpl_remote.get(stem)
        if got == "FILE":
            mark = "ok  "
        elif got:
            mark = "TYPE"
        elif alt:
            mark = "STRP"   # extension stripped: imported as a notebook
        else:
            mark = "GONE"
        print(f"  [{mark}] {k}{'' if got else f'   (found: {stem} as {alt})' if alt else ''}")

    print()
    if not verdict and not missing and not notebooks:
        print("The workspace copy is correct and complete. The fault is "
              "downstream, in the Apps source copy rather than in the "
              "bundle. Compare against the app's own inventory from "
              "/api/_diag, which reports what the container actually has.")
        return 0
    for v in verdict:
        print(f"VERDICT  {v}\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
