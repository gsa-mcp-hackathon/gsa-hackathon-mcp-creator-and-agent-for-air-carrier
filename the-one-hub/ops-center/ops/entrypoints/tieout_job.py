"""Databricks job entry point for the tieout agent.

The standing deterministic suite. Runs the two-axis close, the anchor chain
and the residual test against the current tables and fails loudly.

Built before extraction on purpose: it protects the asset that exists today.
If a figure in the hull moves because someone edited a table, this is what
says so, the morning after rather than in a sponsor briefing.

No model, no network, no workspace needed. It reads the same JSON tables the
front end reads, so the job and the page can never disagree.
"""
from __future__ import annotations

import json
import pathlib
import sys


def _root() -> pathlib.Path:
    """The repository root, found without __file__.

    A serverless Python task does not run this file as a script. It reads the
    bytes and exec()s them, so __file__ is never bound in this namespace and
    pathlib.Path(__file__) raises NameError at import time, before main() is
    reached. The whole run aborts on a line that has nothing to do with the
    work. That is what happened on the first deployed ingest run.

    Three sources, most explicit first:

      --root        passed by the bundle as ${workspace.file_path}, which is
                    the absolute workspace path of the deployed files/ folder.
                    Deterministic, and the same mechanism in dev and in IL5.
      __file__      set by a normal interpreter, so a local run needs no flag.
      upward walk   from the working directory, which on serverless is the
                    entry point's own folder. The last resort, not the first,
                    because a working directory is someone else's to change.
    """
    argv = sys.argv
    if "--root" in argv:
        i = argv.index("--root")
        if i + 1 < len(argv):
            return pathlib.Path(argv[i + 1])
    here = globals().get("__file__")
    if here:
        return pathlib.Path(here).resolve().parents[2]
    start = pathlib.Path.cwd().resolve()
    for base in (start, *start.parents):
        if (base / "ops" / "entrypoints").is_dir():
            return base
    raise RuntimeError(
        "cannot locate the repository root. No --root argument, no __file__, "
        f"and no ops/entrypoints at or above {start}. A serverless task must "
        "be given --root ${workspace.file_path} in the job definition.")


ROOT = _root()
sys.path.insert(0, str(ROOT))

from ops.agents.tieout.run import (  # noqa: E402
    anchor_chain, two_axis_close,
)

DATA = ROOT / "app" / "data"


def _table(name: str) -> dict:
    p = DATA / f"{name}.json"
    if not p.exists():
        raise FileNotFoundError(
            f"{p} is missing. The bundle syncs app/data; if this fails in a "
            f"job and not locally, the sync excluded it.")
    return json.loads(p.read_text())


def main(argv: list[str] | None = None) -> int:
    failures: list[str] = []
    print("tieout, against the current tables")

    cats_t = _table("cost_categories")
    streams_t = _table("funding_streams")
    chain_t = _table("anchor_chain")

    # The total is read from the tables, not carried here. A constant in this
    # file would be a second copy of the figure and would agree with the page
    # right up until someone changed one of them.
    total = float(cats_t["total"])
    if abs(total - float(streams_t["total"])) > 1e-6:
        failures.append(f"the two tables disagree on the total before any check runs: "
                        f"{total:,.3f} against {float(streams_t['total']):,.3f}")

    cats = {r["name"]: float(r["value"]) for r in cats_t["rows"]}
    streams = {r["name"]: float(r["value"]) for r in streams_t["streams"]}

    r = two_axis_close(total, cats, streams)
    print(f"  [{'ok  ' if r.passed else 'FAIL'}] two-axis close on {total:,.3f} "
          f"({len(cats)} categories, {len(streams)} streams): {r.detail}")
    if not r.passed:
        failures.append(f"two-axis close: {r.detail}")

    chain = [(s["label"], float(s["delta"])) for s in chain_t["steps"]]
    r = anchor_chain(chain, total)
    print(f"  [{'ok  ' if r.passed else 'FAIL'}] anchor chain, {len(chain)} steps: {r.detail}")
    if not r.passed:
        failures.append(f"anchor chain: {r.detail}")

    # Each step's running total must equal the sum of the deltas before it.
    # The chain can sum correctly while a published cumulative figure in the
    # middle of it is wrong, and that is the number people quote.
    run = 0.0
    for step in chain_t["steps"]:
        run += float(step["delta"])
        cum = float(step["cum"])
        if abs(run - cum) > 1e-3:
            failures.append(f"anchor chain step '{step['label']}': "
                            f"cumulative {cum:,.3f} against {run:,.3f} from the deltas")

    print()
    if failures:
        print(f"{len(failures)} FAILED")
        for f in failures:
            print(f"  {f}")
        # Non-zero so the run goes red. A tie-out that reports a break and
        # exits clean is worse than no tie-out, because it trains people to
        # ignore the output.
        return 1
    print("tie-out holds on both axes and down the chain.")
    return 0


if __name__ == "__main__":
    # Do not call sys.exit() on success.
    #
    # A serverless task exec()s this file inside a notebook-style wrapper, and
    # that wrapper reports ANY SystemExit as a crashed workload. A clean run
    # came back as "SystemExit: 0 ... Task ingest FAILED", which is the worst
    # possible signal: the work succeeded and the board went red. Raise only
    # when there is something to fail about, and return normally otherwise.
    _rc = main(sys.argv[1:])
    if _rc:
        raise SystemExit(_rc)
