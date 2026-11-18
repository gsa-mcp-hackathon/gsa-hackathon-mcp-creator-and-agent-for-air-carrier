"""Compute the answer key independently of the server under test.

This is the part most evaluations get wrong. An answer key produced by
calling the server's own tools proves only that the server equals itself.
Every function below must reach the data by its own route: a direct query, a
separate read of the snapshot, a hand count.

    uv run python eval/answer_key.py --list
    uv run python eval/answer_key.py --question q1

Fill each TODO with an independent query, then paste the results into the
dataset CSV's `responses` column.
"""

from __future__ import annotations

import argparse
from typing import Callable


def q1_example() -> str:
    """TODO: compute this answer with a query written from scratch.

    Do not import from weather_mcp. Write the SQL (or the snapshot read)
    yourself, run it, and return the answer as a string.
    """
    raise NotImplementedError(
        "write an independent query for q1 before trusting the correctness score"
    )


ANSWERS: dict[str, Callable[[], str]] = {
    "q1": q1_example,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--question")
    args = parser.parse_args()

    if args.list or not args.question:
        for key, function in ANSWERS.items():
            status = (
                "implemented"
                if function.__doc__ and "TODO" not in function.__doc__
                else "TODO"
            )
            print(f"{key}: {status}")
        return 0

    function = ANSWERS.get(args.question)
    if function is None:
        print(f"unknown question {args.question!r}")
        return 1
    print(function())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
