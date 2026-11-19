"""Fail when a relative link in a Markdown file points at nothing.

The README once linked an evaluation report and six screenshots that were
never committed. This check runs in CI so that cannot happen again.

    python3 scripts/check_links.py
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
SKIP = ("http://", "https://", "mailto:", "#")


def markdown_files() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "*.md"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.split()
    return [ROOT / p for p in out]


def main() -> int:
    broken = []
    checked = 0
    for md in markdown_files():
        in_code = False
        for n, line in enumerate(md.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("```"):
                in_code = not in_code
            if in_code:
                continue
            for target in LINK.findall(line):
                if target.startswith(SKIP) or "{{" in target:
                    continue
                path = unquote(target.split("#", 1)[0])
                if not path:
                    continue
                checked += 1
                if not (md.parent / path).exists():
                    broken.append(f"{md.relative_to(ROOT)}:{n}: {target}")
    for b in broken:
        print("BROKEN", b)
    print(f"{checked} relative links checked, {len(broken)} broken")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
