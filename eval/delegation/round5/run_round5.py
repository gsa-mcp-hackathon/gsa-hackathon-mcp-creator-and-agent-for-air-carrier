"""Round 5: the independent author's ten questions through the round 4 runner.

Same runner, grader, tools, models and repeats as round 4; round 4's files are not
edited. This wrapper registers the round 5 file's sealed hash with the runner and
points it at questions_i5.json. In a Databricks notebook with fastmcp installed
(as for round 4):

    import runpy
    REPO = "/Workspace/Users/<you>/gsa-hackathon-mcp-creator-and-agent-for-cvn"
    r5 = runpy.run_path(REPO + "/eval/delegation/round5/run_round5.py")
    rows = r5["run"](spark, REPO, run_id="r5-<8 hex>", budget_s=420)  # repeat until "0 left"
    r5["save"](spark, rows)                                         # once, with every row
"""

from __future__ import annotations

import runpy

SEALED = {"i5": "eef64b36072f71749184c179d5b1f9864f36de162e39ecf1b66cad793d231d53"}


def _round4(repo_dir: str) -> dict:
    r4 = runpy.run_path(f"{repo_dir}/eval/delegation/round4/run_round4.py")
    r4["SEALED_SHA256"].update(SEALED)  # load_questions reads this dict at call time
    return r4


def run(spark, repo_dir: str, run_id: str, **kwargs) -> list[dict]:
    if not run_id.startswith("r5-"):
        raise ValueError("round 5 run ids start with r5-")
    r4 = _round4(repo_dir)
    return r4["run"](spark, repo_dir, questions_path=f"{repo_dir}/eval/delegation/round5/questions_i5.json",
                     run_id=run_id, **kwargs)


def save(spark, rows: list[dict]) -> int:
    from pathlib import Path
    repo_dir = str(Path(__file__).resolve().parents[3])
    return _round4(repo_dir)["save"](spark, rows)
