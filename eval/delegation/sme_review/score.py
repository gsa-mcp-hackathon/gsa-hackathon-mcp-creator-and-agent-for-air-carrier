"""Unblind the filled review sheet and write RESULTS.md.

    python score.py review_sheet_scored.csv
"""
import csv
import statistics
import sys
from pathlib import Path

from build_pack import tools_is_a

HERE = Path(__file__).parent


def num(v: str) -> float:
    return float(str(v).strip() or 0)


def scores(row: dict, side: str) -> dict:
    return {k: num(row[f"{side}_{k}_0_2"]) for k in ("correct", "cited", "usable")}


def main(path: str) -> None:
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    res = []
    for r in rows:
        t, n = ("A", "B") if tools_is_a(r["qid"]) else ("B", "A")
        ts, ns = (scores(r, s) for s in (t, n))
        better = r["better_A_B_tie"].strip().upper()
        res.append({"qid": r["qid"], "category": r["category"], "tools": ts, "none": ns,
                        "tools_total": sum(ts.values()), "none_total": sum(ns.values()),
                        "rely_tools": r[f"{t}_would_rely_Y_N"].strip().upper().startswith("Y"),
                        "rely_none": r[f"{n}_would_rely_Y_N"].strip().upper().startswith("Y"),
                        "prefer": ("tools" if better == t else "no tools" if better == n else "tie"),
                        "minutes": r["minutes_by_hand_estimate"].strip(), "comment": r["comment"].strip()})
    k = len(res)
    mean = lambda f: statistics.mean(f(x) for x in res)
    lines = [
        "# Subject-matter review: results", "",
        f"{k} questions, scored blind on a 0 to 6 rubric (correct, cited, usable; 0 to 2 each).", "",
        "| | With the servers | Without |", "| --- | --- | --- |",
        f"| Mean score (of 6) | {mean(lambda x: x['tools_total']):.1f} | {mean(lambda x: x['none_total']):.1f} |",
        f"| Mean correct (of 2) | {mean(lambda x: x['tools']['correct']):.1f} | {mean(lambda x: x['none']['correct']):.1f} |",
        f"| Mean cited (of 2) | {mean(lambda x: x['tools']['cited']):.1f} | {mean(lambda x: x['none']['cited']):.1f} |",
        f"| Mean usable (of 2) | {mean(lambda x: x['tools']['usable']):.1f} | {mean(lambda x: x['none']['usable']):.1f} |",
        f"| Reviewer would rely on it | {sum(x['rely_tools'] for x in res)} of {k} | {sum(x['rely_none'] for x in res)} of {k} |",
        f"| Preferred | {sum(x['prefer'] == 'tools' for x in res)} | {sum(x['prefer'] == 'no tools' for x in res)} (ties {sum(x['prefer'] == 'tie' for x in res)}) |",
        "", "| Question | Category | With servers | Without | Preferred | Minutes by hand (estimate) | Comment |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    lines += [f"| {x['qid']} | {x['category']} | {x['tools_total']:.0f} | {x['none_total']:.0f} | {x['prefer']} | "
              f"{x['minutes'] or '-'} | {x['comment'].replace('|', '/')} |" for x in res]
    (HERE / "RESULTS.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[:12]))


if __name__ == "__main__":
    main(sys.argv[1])
