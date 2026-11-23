"""The grader, tested on whole question sets: a right answerer and a silent one.

round4/test_grade.py tests the grader's rules one at a time, and
round5/test_round5.py checks each round 5 key against its author's answer.
This asks the question a reader of the results asks first: if the grader is
handed the right answer to every sealed question, does it score 100%, and if
it is handed nothing, does it score 0%? A grader that fails either cannot
tell a server that helps from one that does not.

The sealed files are read as committed and are not changed. Pure Python:
    python -m pytest eval/delegation/test_grader_selftest.py
"""
from __future__ import annotations

import importlib.util
import json
from decimal import Decimal
from pathlib import Path

import pytest

HERE = Path(__file__).parent


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


G = _load("grade_v2_selftest", HERE / "round4" / "grade.py")
ROUND4 = json.loads((HERE / "round4" / "questions_h4.json").read_text(encoding="utf-8"))["questions"]
ROUND5 = json.loads((HERE / "round5" / "questions_i5.json").read_text(encoding="utf-8"))["questions"]

# Two premise traps ask for the reason the premise is wrong, which a key
# cannot state for itself. These are the reasons a right answer gives.
REASONS = {
    "R4-40": "That is the earlier USS John F. Kennedy, a different ship from CVN 79.",
    "R4-42": "0604112N is an RDT&E program element, not a procurement line.",
}
# What a model that knows nothing says.
SILENT = ["", "I do not know.", None]


def _figure(number: dict) -> str:
    value, kind = Decimal(number["value"]), number["kind"]
    if kind == "usd":
        return f"${abs(value):,.2f}"
    if kind == "musd":
        return f"${value:,} million"
    if kind == "pct":
        return f"{value}%"
    return f"{value}"  # count, num


def right_answer(question: dict) -> str:
    """The reviewed reference answer, or the key's own values written out."""
    if question.get("reference_answer"):
        return question["reference_answer"]
    expect = question["expect"]
    parts = [_figure(n) for n in expect.get("numbers", [])] + list(expect.get("dates", []))
    if expect.get("texts"):
        # A generated key names its modification in `source`: "<table>: AZ0064 3934550.00 on ...".
        parts.append("modification " + question["source"].split(": ", 1)[1].split()[0])
    if expect.get("refusal"):
        parts.append("I cannot find any such record.")
    parts.append(REASONS.get(question["qid"].split()[0], ""))
    return "; ".join(p for p in parts if p)


def _score(questions: list[dict], answer_for) -> list[str]:
    """The qids the grader passes."""
    return [q["qid"] for q in questions if G.grade(answer_for(q), q["expect"])["passed"]]


@pytest.mark.parametrize("name,questions,size", [("round 4", ROUND4, 69), ("round 5", ROUND5, 10)])
def test_the_right_answer_to_every_sealed_question_scores_100_percent(name, questions, size):
    assert len(questions) == size
    missed = sorted({q["qid"] for q in questions} - set(_score(questions, right_answer)))
    assert not missed, f"{name}: the grader fails a right answer on {missed}"


@pytest.mark.parametrize("name,questions", [("round 4", ROUND4), ("round 5", ROUND5)])
@pytest.mark.parametrize("silence", SILENT, ids=["empty", "do-not-know", "none"])
def test_a_silent_answerer_scores_zero(name, questions, silence):
    passed = _score(questions, lambda q: silence)
    assert not passed, f"{name}: the grader passes {silence!r} on {passed}"


def test_a_blanket_refusal_passes_only_the_questions_whose_answer_is_a_refusal():
    """Refusing everything must not beat answering: it earns the decoys and nothing else."""
    passed = set(_score(ROUND4 + ROUND5, lambda q: "I cannot find any such record."))
    refusals = {q["qid"] for q in ROUND4 + ROUND5 if q["expect"].get("refusal")}
    assert passed <= refusals
    assert len(passed) < len(ROUND4 + ROUND5) / 4
