#!/usr/bin/env python3
"""Headline figures say one thing everywhere (round 10, C1).

On 2026-11-21 the live front center and the published site still said
"1,094 passed" and "814 of 818" after both had changed, because each figure
was typed into each document by hand. docs/numbers.yaml now lists the current
figures, the retired ones, and where to look. This fails when a checked file
carries a retired figure, or a required file no longer states the current one.

    python3 scripts/check_numbers.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    spec = yaml.safe_load((ROOT / "docs" / "numbers.yaml").read_text(encoding="utf-8"))
    problems = []
    for rel in spec["checked"]:
        text = (ROOT / rel).read_text(encoding="utf-8")
        for phrase in spec["retired"]:
            if phrase in text:
                problems.append(f"{rel}: retired figure '{phrase}'")
    for rel, phrases in spec["required"].items():
        text = (ROOT / rel).read_text(encoding="utf-8")
        for phrase in phrases:
            if phrase not in text:
                problems.append(f"{rel}: missing current figure '{phrase}'")
    if problems:
        print("Figures out of step with docs/numbers.yaml:")
        print("\n".join(f"  {p}" for p in problems))
        return 1
    print(f"figures: {len(spec['checked'])} files free of {len(spec['retired'])} retired "
          f"figures; {sum(len(v) for v in spec['required'].values())} required figures present")
    return 0


if __name__ == "__main__":
    sys.exit(main())
