"""Job entrypoint: run orchestrator + checker on open exceptions (task 9, C1).

Runs as a serverless job task. For each open exception:
  1. Orchestrator selects specialist, runs tool-calling loop, writes proposals
  2. Checker re-reads each proposal with a different model family, writes verdict
  3. Exit 1 if any orchestrator run errored

Usage:
    spark-submit ops/entrypoints/harness_job.py [--exception-id <id>] [--dry-run] [--root <repo>]
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

from ops.harness.orchestrator import run_exception  # noqa: E402
from ops.harness import catalog as C                # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Run harness on open exceptions")
    parser.add_argument("--exception-id", dest="exception_ids", action="append",
                        help="Process only these exception ids (repeatable). Default: all open.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Run the loop but don't write to tables.")
    parser.add_argument("--skip-checker", action="store_true",
                        help="Skip the independent checker step.")
    parser.add_argument("--root", default=None,
                        help="repository root; consumed by _root() at import")
    args = parser.parse_args()

    from pyspark.sql import SparkSession
    spark = SparkSession.getActiveSession() or SparkSession.builder.getOrCreate()

    # Get exception ids to process
    if args.exception_ids:
        exc_ids = args.exception_ids
    else:
        rows = spark.sql(f"""
            SELECT exception_id FROM {C.EXCEPTIONS}
            WHERE status = 'open'
            ORDER BY detected_at
        """).collect()
        exc_ids = [r.exception_id for r in rows]

    print(f"Processing {len(exc_ids)} exception(s)")
    results = []
    had_error = False

    for exc_id in exc_ids:
        print(f"\n--- Orchestrator: {exc_id} ---")
        # The checker runs inside run_exception (invariant 4); --skip_checker turns it off.
        orch_result = run_exception(exc_id, dry_run=args.dry_run,
                                    check=not args.skip_checker)
        results.append(orch_result)
        print(json.dumps(orch_result, indent=2, default=str))

        if orch_result["status"] == "error":
            had_error = True
            continue

        for check_result in orch_result.get("verdicts", []):
            print(f"\n--- Checker: {check_result.get('proposal_id')} ---")
            print(json.dumps(check_result, indent=2, default=str))

    print(f"\n=== Summary ===")
    print(f"Exceptions processed: {len(results)}")
    print(f"Completed: {sum(1 for r in results if r['status'] == 'completed')}")
    print(f"Errors: {sum(1 for r in results if r['status'] == 'error')}")
    # A-34: refused by the code-only pre-check; no model was called.
    print(f"Not run (pre-check): {sum(1 for r in results if r['status'] == 'precheck_blocked')}")
    total_proposals = sum(len(r.get('proposals', [])) for r in results)
    print(f"Proposals staged: {total_proposals}")
    if args.dry_run:
        skipped = sum(r.get("dry_run_proposals", 0) for r in results)
        print(f"Proposals not staged (dry run): {skipped}")

    if had_error:
        sys.exit(1)


if __name__ == "__main__":
    main()
