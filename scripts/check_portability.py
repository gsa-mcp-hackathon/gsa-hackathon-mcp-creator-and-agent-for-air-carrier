#!/usr/bin/env python3
"""No runtime code names the pilot workspace outside the places allowed to.

Round 10 (A8), 2026-11-21: 28 runtime files carried the pilot's personal
schema, volume or address as a default, so a clean clone deployed into
another workspace would read the pilot's names. Now:

* the MCP servers take every location from app.yaml and stop at start-up
  without it (a local run gets a neutral placeholder);
* the One Hub's jobs and app take it from core/catalog.py (PILOT_SCHEMA),
  the one place it is named, and its analyst copy;
* deploy configuration (app.yaml, databricks.yml, grants SQL) and the
  evaluation records may name it, because they describe this deployment.

This scans every tracked .py file and fails on any other occurrence.

    python3 scripts/check_portability.py
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PERSONAL = re.compile(r"xiaobing[._]shang1|shang1[._]civ", re.IGNORECASE)

ALLOWED = {
    # The one declaration for the One Hub, and the analyst's byte-identical copy.
    "the-one-hub/ops-center/core/catalog.py": "PILOT_SCHEMA, the single declaration",
    "mcp-servers/mcp-aircarrier-analyst/src/core/catalog.py": "vendored copy of core/catalog.py",
    # Standalone build scripts run from the pilot bundle; elsewhere pass --schema.
    "the-one-hub/ops-center/etl/build_data.py": "standalone build script, --volume overrides",
    "the-one-hub/ops-center/etl/build_extracts.py": "standalone build script, --schema overrides",
    "the-one-hub/ops-center/etl/build_rules.py": "standalone build script, --schema overrides",
    "the-one-hub/ops-center/etl/publish_serving_docs.py": "standalone, AIRCARRIER_SCHEMA overrides",
    "the-one-hub/ops-center/deploy/seed_rules.py": "one-time seed, overridden by env at transfer",
    "tools/sync_from_workspace.py": "copies the pilot's Genie Code skills; pilot-only by design",
}
# Records of runs in the pilot workspace: changing them would rewrite history.
ALLOWED_PREFIXES = (
    "eval/delegation/",  # sealed rounds and their analysis
    "the-one-hub/notebooks/",  # build notebooks run in the pilot workspace
    "mcp-servers/Air Carrier Delegation Eval.py",
    "mcp-servers/mcp-aircarrier-ops/eval/",
    "mcp-servers/mcp-aircarrier-analyst/tests/run_checks.py",  # live checks in the pilot
    "the-one-hub/ops-center/checks/test_work_live.py",  # live checks in the pilot
    "mcp-servers/aircarrier-mcp-probe/test_probe.py",  # asserts the deployed targets
    "the-one-hub/ops-center/checks/test_impact.py",  # records where the figures were checked
)


def main() -> int:
    files = subprocess.run(["git", "ls-files", "-z", "*.py"], cwd=ROOT, capture_output=True,
                           text=True, check=True).stdout.split("\0")
    files = [f for f in files if f]
    bad = []
    for f in files:
        if f in ALLOWED or f.startswith(ALLOWED_PREFIXES):
            continue
        text = (ROOT / f).read_text(encoding="utf-8", errors="replace")
        for n, line in enumerate(text.splitlines(), 1):
            if PERSONAL.search(line):
                bad.append(f"{f}:{n}: {line.strip()[:100]}")
    if bad:
        print("Pilot workspace names in runtime code (set them in app.yaml or core/catalog.py):")
        print("\n".join(bad))
        return 1
    print(f"portability: {len(files)} Python files, pilot names only in the {len(ALLOWED)} "
          "declared places and the run records")
    return 0


if __name__ == "__main__":
    sys.exit(main())
