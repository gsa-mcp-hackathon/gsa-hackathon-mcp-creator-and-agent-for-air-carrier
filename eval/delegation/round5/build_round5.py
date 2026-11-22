"""Build questions_i5.json for round 5 from the independent author's questions_i5.csv.

The author wrote the ten questions, answers and sources; this file adds only the
grader keys (eval/delegation/round4/grade.py, v2), each written from the author's
answer. test_round5.py checks that every reference answer passes its key and a
plausible wrong answer fails.

    python build_round5.py        # writes questions_i5.json and prints its SHA-256
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).parent
CSV = HERE / "questions_i5.csv"
OUT = HERE / "questions_i5.json"
CSV_SHA256 = "320f74e59b9b323db0843d0035bd4029c655a5eadf41a03413bdace1b13e898a"

# One key per question, from the author's answer. Numbers are compared as values
# (grade.py), texts as case-insensitive regexes; every field must pass.
KEYS = {
    "I01": {"numbers": [{"kind": "musd", "value": "880.078"}]},
    "I02": {"numbers": [{"kind": "musd", "value": "11397.712"}]},
    "I03": {"numbers": [{"kind": "musd", "value": "588.5"}, {"kind": "musd", "value": "125.0"}],
            "texts": ["overrun", "rollover|roll-over"]},
    "I04": {"numbers": [{"kind": "musd", "value": "42.3"}],
            "texts": ["radar", r"JSF|F-35|Joint Strike Fighter"]},
    "I05": {"texts": ["water twister", r"weapons elevator|\bAWE\b"]},
    "I06": {"numbers": [{"kind": "usd", "value": "16068211"}],
            "texts": [r"\bSCN\b|shipbuilding and conversion"]},
    "I07": {"numbers": [{"kind": "usd", "value": "274041192"}, {"kind": "usd", "value": "119213388"}],
            "texts": [r"no funds|nothing (was )?obligated|not obligated|\$\s?0\b(?![.,]\d)|zero|none (was|were) obligated"]},
    "I08": {"numbers": [{"kind": "musd", "value": "11397.712"}, {"kind": "musd", "value": "13195.970"},
                        {"kind": "musd", "value": "1798.258"}, {"kind": "musd", "value": "13196.0"}]},
    "I09": {"texts": [(r"not (part|included|covered|procured)|(premise|assumption) (is )?(incorrect|wrong|false|mistaken)"
                      r"|(cover(s|ed)?|for|of) (only )?CVN[- ]?80 and (CVN[- ]?)?81")]},
    "I10": {"texts": [r"\bno\b|does not|doesn't|cannot|not by itself|not (proof|enough|sufficient|a valid)",
                      r"inflation|adjust"]},
}


def build() -> dict:
    data = CSV.read_bytes()
    if hashlib.sha256(data).hexdigest() != CSV_SHA256:
        raise RuntimeError("questions_i5.csv is not the sealed file")
    rows = list(csv.DictReader(data.decode("utf-8-sig").splitlines()))
    assert [r["qid"] for r in rows] == list(KEYS), "keys and questions out of step"
    return {
        "question_set": "i5",
        "written": "2026-11-22",
        "written_against": "nothing: written by a teammate who did not build the tools, without an AI assistant, "
                           "before seeing the tool catalog (per the project owner)",
        "grader": "eval/delegation/round4/grade.py (v2)",
        "sets": {"independent": {"count": len(rows), "csv_sha256": CSV_SHA256,
                                 "written_by": "an independent author on the project owner's team"}},
        "scoring": "A run passes when grade(answer, expect)['passed'] is true. Every field in expect must pass.",
        "questions": [{"qid": f"{r['qid']} {r['category']}", "template": None, "category": r["category"],
                       "question": r["question"], "expect": KEYS[r["qid"]], "source": r["source"],
                       "reference_answer": r["answer"], "set": "independent"} for r in rows],
    }


if __name__ == "__main__":
    blob = (json.dumps(build(), indent=1, ensure_ascii=False) + "\n").encode("utf-8")
    OUT.write_bytes(blob)
    print(f"{OUT.name}: SHA-256 {hashlib.sha256(blob).hexdigest()}")
