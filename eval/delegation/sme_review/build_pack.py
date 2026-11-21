"""Build the review sheet from the exported round 4 answers.

Input: the export of export_answers.sql (CSV, or TSV as pasted from the SQL editor).
Output: review_sheet.csv, one row per question with the answer from the run with the servers
and the answer from the run without tools, labelled, and empty score columns. The review was
not blind (see README.md), so the labels are shown.

    python build_pack.py answers.tsv
"""
import csv
import sys
from pathlib import Path

from choose_questions import choose

HERE = Path(__file__).parent
SCORES = ["correct_0_2", "cited_0_2", "usable_0_2", "would_rely_Y_N"]
COLS = (["qid", "category", "question", "answer_with_servers", "answer_without"]
        + [f"with_{s}" for s in SCORES] + [f"without_{s}" for s in SCORES]
        + ["better", "minutes_by_hand_estimate", "comment"])


def load(path: str) -> dict:
    csv.field_size_limit(10**7)
    with open(path, encoding="utf-8") as f:
        delim = "\t" if f.readline().count("\t") else ","
        f.seek(0)
        return {(r["qid"], r["mode"]): r for r in csv.DictReader(f, delimiter=delim)}


def clean(text: str | None) -> str:
    text = (text or "").strip()
    if text in ("", "null"):
        return "(No answer: the run stopped at the eight-turn tool limit.)"
    # The SQL editor export decoded UTF-8 as Windows-1252; restore the two characters it broke.
    return text.replace("â€”", "—").replace("Ã·", "÷")


def main(path: str) -> None:
    rows, out = load(path), []
    for q in choose():
        t, n = rows.get((q["qid"], "tools_rep1")), rows.get((q["qid"], "no_tools"))
        if not t or not n:
            sys.exit(f"missing answers for {q['qid']}: export both tools_rep1 and no_tools")
        out.append({"qid": q["qid"], "category": q["category"], "question": q["question"],
                    "answer_with_servers": clean(t["answer"]), "answer_without": clean(n["answer"])})
    with open(HERE / "review_sheet.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(out)
    print(f"review_sheet.csv: {len(out)} questions")


if __name__ == "__main__":
    main(sys.argv[1])
