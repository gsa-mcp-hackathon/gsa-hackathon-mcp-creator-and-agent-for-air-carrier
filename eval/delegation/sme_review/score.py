"""Total the filled review sheet and write RESULTS.md.

    python score.py review_sheet_scored.csv
"""
import csv
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).parent
PARTS = ("correct", "cited", "usable")


def num(v: str) -> float:
    return float(str(v).strip() or 0)


def side(row: dict, s: str) -> dict:
    d = {k: num(row[f"{s}_{k}_0_2"]) for k in PARTS}
    d["total"] = sum(d[k] for k in PARTS)
    d["rely"] = row[f"{s}_would_rely_Y_N"].strip().upper().startswith("Y")
    return d


def main(path: str) -> None:
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    res = [{"qid": r["qid"], "category": r["category"], "w": side(r, "with"), "x": side(r, "without"),
            "minutes": r.get("minutes_by_hand_estimate", "").strip(), "comment": r.get("comment", "").strip()}
           for r in rows]
    k = len(res)

    def mean(s: str, part: str) -> str:
        return f"{statistics.mean(x[s][part] for x in res):.1f}"

    lines = [
        "# Subject-matter review: results", "",
        f"{k} round 4 questions, Claude Sonnet 4.5, scored by the project owner on a 0 to 6 rubric",
        "(correct, cited, usable; 0 to 2 each). Not blind: see README.md.", "",
        "| | With the servers | Without tools |", "| --- | --- | --- |",
        f"| Total (of {6 * k}) | {sum(x['w']['total'] for x in res):.0f} | {sum(x['x']['total'] for x in res):.0f} |",
        f"| Mean score (of 6) | {mean('w', 'total')} | {mean('x', 'total')} |",
        f"| Mean correct (of 2) | {mean('w', 'correct')} | {mean('x', 'correct')} |",
        f"| Mean cited (of 2) | {mean('w', 'cited')} | {mean('x', 'cited')} |",
        f"| Mean usable (of 2) | {mean('w', 'usable')} | {mean('x', 'usable')} |",
        f"| Reviewer would rely on it | {sum(x['w']['rely'] for x in res)} of {k} | {sum(x['x']['rely'] for x in res)} of {k} |",
        "", "| Question | Category | With servers (of 6) | Without (of 6) | Comment |", "| --- | --- | --- | --- | --- |",
    ]
    lines += [f"| {x['qid']} | {x['category']} | {x['w']['total']:.0f} | {x['x']['total']:.0f} | "
              f"{x['comment'].replace('|', '/') or '-'} |" for x in res]
    (HERE / "RESULTS.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main(sys.argv[1])
