#!/usr/bin/env python3
"""Every job entry point must import the way serverless runs it.

Serverless does not run a `spark_python_task` as a script. It reads the file
and exec()s the bytes, so `__file__` is never bound in that namespace. Any
module-level `pathlib.Path(__file__)` raises NameError at import time, before
main() is reached, and the run aborts on a line unrelated to the work. That
cost one deployed ingest run and would have cost a scheduled tieout run the
next morning.

It is invisible locally, because a local run is a script and a script has
__file__. This harness is the only thing that sees it before deployment.

    python3 checks/test_serverless_entrypoints.py

What it does, for every spark_python_task in resources/jobs.yml:

  * executes the file with no __file__ in globals
  * from the entry point's own directory, which is the serverless cwd
  * with the job's own parameters, so a missing --root shows up here

It stops at import. main() is not called, so a NotImplementedError body is
fine and nothing touches the workspace.
"""
from __future__ import annotations

import pathlib
import sys
import traceback

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _tasks() -> list[tuple[str, pathlib.Path, list[str]]]:
    """Entry points exactly as the bundle declares them, so a job added to
    resources/jobs.yml is covered without touching this file."""
    spec = yaml.safe_load((ROOT / "resources" / "jobs.yml").read_text())
    out = []
    for job_key, job in (spec.get("resources", {}).get("jobs") or {}).items():
        for task in job.get("tasks") or []:
            spt = task.get("spark_python_task")
            if not spt:
                continue
            # python_file is relative to resources/, as the CLI resolves it.
            f = (ROOT / "resources" / spt["python_file"]).resolve()
            params = [_substitute(p) for p in (spt.get("parameters") or [])]
            out.append((f"{job_key}.{task['task_key']}", f, params))
    return out


def _substitute(p: str) -> str:
    """Stand in for the deploy-time values. Only workspace.file_path matters:
    it is the deployed files/ folder, which is this repo."""
    if p == "${workspace.file_path}":
        return str(ROOT)
    if p.startswith("${"):
        return "/placeholder"
    return p


def _exec_as_serverless(path: pathlib.Path, params: list[str]) -> None:
    cwd = pathlib.Path.cwd()
    try:
        import os
        os.chdir(path.parent)
        saved, sys.argv = sys.argv, [str(path), *params]
        # No __file__ key. That absence is the whole point of the harness.
        g = {"__name__": "__serverless_probe__", "__builtins__": __builtins__}
        exec(compile(path.read_bytes(), str(path), "exec"), g)
    finally:
        sys.argv = saved
        import os
        os.chdir(cwd)


def main() -> int:
    tasks = _tasks()
    print(f"serverless import probe, {len(tasks)} entry point(s)\n")
    failed = 0
    for name, path, params in tasks:
        rel = path.relative_to(ROOT)
        try:
            _exec_as_serverless(path, params)
        except Exception as exc:
            failed += 1
            print(f"  [FAIL] {name}")
            print(f"         {rel}")
            print(f"         {type(exc).__name__}: {exc}")
            if isinstance(exc, NameError) and "__file__" in str(exc):
                print("         module-level __file__. Take the root from "
                      "--root ${workspace.file_path} instead.")
            else:
                traceback.print_exc()
            continue
        has_root = "--root" in params
        print(f"  [ok  ] {name}")
        print(f"         {rel}{'' if has_root else '   (no --root; relying on the cwd walk)'}")

    print()
    if failed:
        print(f"{failed} entry point(s) would fail on serverless")
        return 1
    print("every entry point imports with no __file__ bound")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
