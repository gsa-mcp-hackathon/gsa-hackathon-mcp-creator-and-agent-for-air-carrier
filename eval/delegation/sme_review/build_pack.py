"""Build the blind review sheet from the exported round 4 answers.

Input: the CSV exported by export_answers.sql (run_id, model, mode, qid, passed, answer).
Output: review_sheet.csv, one row per question with two answers labelled A and B. Which one had
the servers is decided by a seeded coin flip per question and is not written anywhere; score.py
re-derives it after the scores are in. The reviewer scores each answer on the rubric in README.md.

    python build_pack.py answers.csv
"""
import csv
import random
import sys
from pathlib import Path

from choose_questions import SEED, choose

HERE = Path(__file__).parent
COLS = ["qid", "category", "question", "answer_A", "answer_B",
        "A_correct_0_2", "A_cited_0_2", "A_usable_0_2", "A_would_rely_Y_N",
        "B_correct_0_2", "B_cited_0_2", "B_usable_0_2", "B_would_rely_Y_N",
        "better_A_B_tie", "minutes_by_hand_estimate", "comment"]


def tools_is_a(qid: str) -> bool:
    return random.Random(f"{SEED}:{qid}").random() < 0.5


def main(path: str) -> None:
    with open(path, encoding="utf-8") as f:
        rows = {(r["qid"], r["mode"]): r for r in csv.DictReader(f)}
    out = []
    for q in choose():
        t = rows.get((q["qid"], "tools_rep1"))
        n = rows.get((q["qid"], "no_tools"))
        if not t or not n:
            sys.exit(f"missing answers for {q['qid']}: export both tools_rep1 and no_tools")
        ta, na = (t["answer"] or "(no answer)").strip(), (n["answer"] or "(no answer)").strip()
        a, b = (ta, na) if tools_is_a(q["qid"]) else (na, ta)
        out.append({"qid": q["qid"], "category": q["category"], "question": q["question"],
                    "answer_A": a, "answer_B": b})
    with open(HERE / "review_sheet.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(out)
    print(f"review_sheet.csv: {len(out)} questions")


if __name__ == "__main__":
    main(sys.argv[1])
