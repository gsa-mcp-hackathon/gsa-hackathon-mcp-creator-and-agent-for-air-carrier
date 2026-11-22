"""Upload a CSV dataset to Phoenix.

Run inside the harness environment described in eval/README.md:

    python create_dataset.py --list
    python create_dataset.py --dataset-name bakehouse-eval-0 --dry-run
    python create_dataset.py --dataset-name bakehouse-eval-0
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas
import yaml
from dotenv import load_dotenv

load_dotenv()

HERE = Path(__file__).resolve().parent
REGISTRY = HERE / "datasets.yaml"


def load_registry() -> dict:
    return yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))["datasets"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--dataset-name")
    parser.add_argument("--phoenix-name")
    parser.add_argument("--csv-path")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    registry = load_registry()
    if args.list or not args.dataset_name:
        for name, entry in registry.items():
            print(f"{name}: {entry.get('description', '')}")
        return 0

    entry = registry.get(args.dataset_name)
    if entry is None:
        print(f"unknown dataset {args.dataset_name!r}")
        return 1

    csv_path = Path(args.csv_path or (HERE / entry["csv_path"]))
    frame = pandas.read_csv(csv_path)
    required = list(entry["input_keys"]) + list(entry["output_keys"])
    missing = [column for column in required if column not in frame.columns]
    if missing:
        print(f"{csv_path} is missing columns: {missing}")
        return 1

    unanswered = frame[frame["responses"].astype(str).str.startswith("TODO")]
    if len(unanswered):
        print(
            f"WARNING: {len(unanswered)} of {len(frame)} questions still have "
            "a TODO answer. Fill them from the answer key before trusting a "
            "correctness score."
        )

    print(f"{csv_path}: {len(frame)} rows, columns {list(frame.columns)}")
    if args.dry_run:
        print("dry run: nothing uploaded")
        return 0

    from phoenix.client import Client

    dataset = Client().datasets.create_dataset(
        name=args.phoenix_name or args.dataset_name,
        dataframe=frame,
        input_keys=entry["input_keys"],
        output_keys=entry["output_keys"],
    )
    print(f"uploaded: {dataset}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
