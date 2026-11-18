"""Job entrypoint: evaluate all active rules (task 8, C1).

Runs as a serverless job task. Called on-demand by:
  * POST /rules (after a rule_register insert)
  * A scheduled evaluation cadence
  * Manual trigger from the dispatcher

Usage:
    spark-submit ops/entrypoints/eval_job.py [--rule CC-02 --rule CM-01] [--root <repo>]
"""
import argparse
import json
import pathlib
import sys


def _root() -> pathlib.Path:
    """Repository root without relying on __file__ (serverless exec()s the file unbound).

    Order: --root, then __file__, then an upward walk from the working directory.
    The full rationale is in ops/entrypoints/tieout_job._root.
    """
    argv = sys.argv
    if "--root" in argv and argv.index("--root") + 1 < len(argv):
        return pathlib.Path(argv[argv.index("--root") + 1])
    here = globals().get("__file__")
    if here:
        return pathlib.Path(here).resolve().parents[2]
    start = pathlib.Path.cwd().resolve()
    for base in (start, *start.parents):
        if (base / "ops" / "entrypoints").is_dir():
            return base
    raise RuntimeError(f"cannot locate the repository root from {start}; "
                       "pass --root ${workspace.file_path} in the job definition")


ROOT = _root()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ops.harness.evaluate import evaluate  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Evaluate active rules")
    parser.add_argument("--rule", action="append", dest="rule_ids",
                        help="Evaluate only these rule_ids (repeatable). Default: all.")
    parser.add_argument("--trigger", default="job",
                        help="Trigger source (job | api | manual)")
    parser.add_argument("--triggered-by", default="eval_job.py",
                        help="Who or what triggered this run")
    parser.add_argument("--root", default=None,
                        help="repository root; consumed by _root() at import")
    args = parser.parse_args()

    result = evaluate(
        trigger=args.trigger,
        triggered_by=args.triggered_by,
        rule_ids=args.rule_ids,
    )

    print(json.dumps(result, indent=2, default=str))
    # Exit 1 if any rule errored
    if any(r["status"] == "error" for r in result["rules_evaluated"]):
        sys.exit(1)


if __name__ == "__main__":
    main()
