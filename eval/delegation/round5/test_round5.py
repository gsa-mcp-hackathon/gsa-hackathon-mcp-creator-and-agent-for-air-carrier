"""Round 5 keys: every reference answer passes, and plausible wrong answers fail."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

HERE = Path(__file__).parent


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


G = _load("grade_v2_r5", HERE.parent / "round4" / "grade.py")
B = _load("build_round5", HERE / "build_round5.py")
DOC = B.build()
BY_ID = {q["qid"].split()[0]: q for q in DOC["questions"]}

# Wrong answers a model could plausibly give: a neighbouring figure, a rounded one,
# the premise accepted, a missing reason.
WRONG = {
    "I01": "The PB 2020 P-5c shows Plan Costs of $898.865 million for CVN 79.",
    "I02": "The PB 2021 Total Ship Estimate for CVN 79 is $11,398.0 million, the cost cap.",
    "I03": "Basic Construction rose $588.5 million and Change Orders rose $56.8 million.",
    "I04": "The Navy realigned $42.3 million into Basic Construction to pay for a new propulsion plant.",
    "I05": "The increase supports EMALS software upgrades and crew training.",
    "I06": "$16.1 million was obligated from Operation and Maintenance, Navy funds.",
    "I07": "The modifications were $274,041,192 and $119,213,388, and all of it was obligated at award.",
    "I08": "The estimate rose from $11,397.712 million to $13,195.970 million, about $1.8 billion; CRS agrees.",
    "I09": "The Navy attributed about $3.9 billion of block-buy savings to CVN 79.",
    "I10": "Yes. $13,196.0 million minus $11,398.0 million is $1,798.0 million over the cap.",
}


def test_the_csv_is_the_sealed_file():
    assert hashlib.sha256((HERE / "questions_i5.csv").read_bytes()).hexdigest() == B.CSV_SHA256


def test_the_committed_json_is_what_the_builder_writes():
    blob = (json.dumps(DOC, indent=1, ensure_ascii=False) + "\n").encode("utf-8")
    assert (HERE / "questions_i5.json").read_bytes() == blob


@pytest.mark.parametrize("qid", list(BY_ID))
def test_the_authors_answer_passes_its_key(qid):
    q = BY_ID[qid]
    result = G.grade(q["reference_answer"], q["expect"])
    assert result["passed"], (qid, result["checks"])


@pytest.mark.parametrize("qid", list(WRONG))
def test_a_plausible_wrong_answer_fails(qid):
    result = G.grade(WRONG[qid], BY_ID[qid]["expect"])
    assert not result["passed"], (qid, result["checks"])


def test_the_round4_runner_accepts_the_sealed_file_and_refuses_a_changed_one(tmp_path):
    r5 = _load("run_round5_under_test", HERE / "run_round5.py")
    r4 = r5._round4(str(HERE.parents[2]))
    doc = r4["load_questions"](str(HERE / "questions_i5.json"))
    assert doc["question_set"] == "i5" and len(doc["questions"]) == 10
    changed = tmp_path / "questions_i5.json"
    changed.write_bytes((HERE / "questions_i5.json").read_bytes().replace(b"880.078", b"880.079"))
    with pytest.raises(RuntimeError, match="not the sealed hash"):
        r4["load_questions"](str(changed))
