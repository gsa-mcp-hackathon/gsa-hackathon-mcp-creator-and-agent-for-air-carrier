"""Build a blind review sheet from the same ten answer pairs (round 10, B3).

The first review was not blind: the sheet labelled which answer had the servers,
and answers without tools carry tool calls the model wrote out but never ran.
This sheet shows each pair as answer A and answer B. A secret seed decides which
side holds the answer with the servers, and the seed is not in the sheet or the
repository. Both answers lose tool-call markup and "Let me search" narration.
Nothing else is changed.

    python build_blind_pack.py answers.tsv --seed "<a phrase only you know>"

Prints the SHA-256 of the seed. Record it (commit it, or email it to a reviewer)
before you send the sheet; reveal the seed only after every score is back.
score_blind.py checks the seed against that hash before it unblinds anything.

Output: blind_sheet.csv (send one copy to each reviewer; they rename it
blind_sheet_<initials>.csv).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
from pathlib import Path

from build_pack import clean, load
from choose_questions import choose

HERE = Path(__file__).parent
SCORES = ["correct_0_2", "cited_0_2", "usable_0_2", "would_rely_Y_N"]
COLS = (["qid", "category", "question", "answer_A", "answer_B"]
        + [f"A_{s}" for s in SCORES] + [f"B_{s}" for s in SCORES]
        + ["better_A_or_B", "comment"])
# Lines that are tool-call markup the model wrote out, or narration of a search.
MARKUP = re.compile(r"^\s*</?[a-z_][\w-]*(\s+[^>]*)?>.*$|^\s*<parameter\b.*$", re.IGNORECASE)
NARRATION = re.compile(r"^\s*(let me (search|try|look)|i'?ll (search|look|check))\b", re.IGNORECASE)


def blind_text(text: str) -> str:
    """Drop markup and narration lines; collapse the blank lines they leave."""
    if text.startswith("(No answer"):
        # clean()'s placeholder names the tool limit, which only a run with tools hits.
        return "(No answer was returned.)"
    kept = [ln for ln in text.splitlines() if not (MARKUP.match(ln) or NARRATION.match(ln))]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip() or "(No answer text.)"


def servers_side(seed: str, qid: str) -> str:
    """'A' or 'B': the side that holds the answer with the servers."""
    return "A" if hashlib.sha256(f"{seed}|{qid}".encode()).digest()[0] % 2 == 0 else "B"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("answers")
    ap.add_argument("--seed", required=True, help="secret; reveal only after scoring")
    args = ap.parse_args()
    rows, out = load(args.answers), []
    for q in choose():
        t, n = rows[(q["qid"], "tools_rep1")], rows[(q["qid"], "no_tools")]
        with_s, without = blind_text(clean(t["answer"])), blind_text(clean(n["answer"]))
        a, b = (with_s, without) if servers_side(args.seed, q["qid"]) == "A" else (without, with_s)
        out.append({"qid": q["qid"], "category": q["category"], "question": q["question"],
                    "answer_A": a, "answer_B": b})
    with open(HERE / "blind_sheet.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(out)
    digest = hashlib.sha256(args.seed.encode()).hexdigest()
    print(f"blind_sheet.csv: {len(out)} pairs")
    print(f"seed SHA-256: {digest}")
    print("Record that hash now (commit it in SEAL_BLIND.md or email it). Keep the seed.")


if __name__ == "__main__":
    main()
