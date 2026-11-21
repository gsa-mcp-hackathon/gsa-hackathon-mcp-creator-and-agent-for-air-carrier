"""Tests for grader v2. Run: python -m pytest eval/delegation/round4/test_grade.py

The three round 3 grading defects come first: each answer below is one the old
regex grader failed and a hand reading passed (eval/delegation/hand_grades.csv).
"""
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from grade import dates_in, grade, grade_legacy, numbers_in  # noqa: E402


def ok(answer, **expect):
    return grade(answer, expect)["passed"]


# ------------------------------------------------- the round 3 defects
def test_g07_rounded_key_and_exact_print_both_pass():
    e = {"numbers": [{"kind": "musd", "value": "13195.970"}]}
    assert ok("The PB 2026 P-5c prints a Total Ship Estimate of 13,195.970 ($M).", **e)
    assert ok("About $13,196 million.", **e)
    assert not grade_legacy("13,195.970", [r"13,?196(\.0)?"])  # the old key failed the exact print


def test_g07_too_coarse_or_wrong_figure_fails():
    e = {"numbers": [{"kind": "musd", "value": "13195.970"}]}
    assert not ok("About $13.2 billion.", **e)        # 3 significant digits
    assert not ok("13,409.970 ($M)", **e)             # the PB 2027 figure


def test_h06_share_at_stated_precision():
    e = {"numbers": [{"kind": "pct", "value": "63.11"}]}
    assert ok("Basic construction is 8,463.156, 63.11% of the total.", **e)
    assert ok("about 63.1 percent", **e)
    assert not ok("63.09%", **e)                       # the hand computation round 2 caught
    assert not ok("63.11", **e)                        # a share needs its percent sign


def test_h10_refusal_wording():
    e = {"refusal": True}
    for a in ("I cannot find any figure for that rework.", "There is no record of such a modification.",
              "No such modification appears in the FPDS data.", "That action does not exist in the records."):
        assert ok(a, **e), a
    assert not ok("The rework cost $45 million.", **e)


# ------------------------------------------------------------ numbers
@pytest.mark.parametrize("answer", ["$243,137,614.22", "243137614.22 dollars", "$243.1 million", "$243.14M"])
def test_usd_formats(answer):
    assert ok(answer, numbers=[{"kind": "usd", "value": "243137614.22"}])


@pytest.mark.parametrize("answer", ["$243 million", "$0.24 billion", "$243,137,641.22"])
def test_usd_too_coarse_or_wrong(answer):
    assert not ok(answer, numbers=[{"kind": "usd", "value": "243137614.22"}])


def test_deobligation_compared_in_absolute_value():
    e = {"numbers": [{"kind": "usd", "value": "-28247000.00"}]}
    assert ok("a deobligation of -$28,247,000.00", **e)
    assert ok("they deobligated $28.247 million", **e)


def test_short_key_needs_only_its_own_precision():
    assert ok("over $1.5 billion", numbers=[{"kind": "usd", "value": "1500000000"}])
    assert not ok("over $2 billion", numbers=[{"kind": "usd", "value": "1500000000"}])


def test_musd_printed_in_thousands():
    e = {"numbers": [{"kind": "musd", "value": "5995.429", "printed_thousands": True}]}
    assert ok("The book prints 5,995,429 (in thousands).", **e)
    assert ok("$5,995.429 million", **e)
    assert ok("about $5.995 billion", **e)
    assert not ok("5,995,429", numbers=[{"kind": "musd", "value": "5995.429"}])  # only when the book prints $K


def test_musd_spelled_out_in_dollars():
    assert ok("$13,409,970,000", numbers=[{"kind": "musd", "value": "13409.970"}])


def test_count_is_exact_and_bare():
    e = {"numbers": [{"kind": "count", "value": "95"}]}
    assert ok("There are 95 actions.", **e)
    for a in ("950 actions", "9.5", "95%", "$95 million"):
        assert not ok(a, **e), a


def test_identifiers_are_not_figures():
    vals = {str(n["v"]) for n in numbers_in("P00038 in FY2021 on N00024-15-C-2114, dated 2018-05-02")}
    assert not vals & {"38", "2021", "2114", "5", "2"}


def test_ratio():
    assert ok("a factor of 4.18", numbers=[{"kind": "num", "value": "4.18"}])
    assert not ok("a factor of 4.81", numbers=[{"kind": "num", "value": "4.18"}])


# -------------------------------------------------------------- dates
@pytest.mark.parametrize("answer", ["2018-05-02", "May 2, 2018", "2 May 2018", "05/02/2018", "May 2nd, 2018"])
def test_date_formats(answer):
    assert ok(answer, dates=["2018-05-02"])


def test_wrong_date_fails():
    assert not ok("May 20, 2018", dates=["2018-05-02"])
    assert not dates_in("February 30, 2020")


# ------------------------------------------------------- texts and traps
def test_every_check_must_pass():
    e = {"numbers": [{"kind": "usd", "value": "707617191.00"}], "texts": [r"\bP0*38\b"], "dates": ["2018-05-02"]}
    assert ok("P00038 obligated $707,617,191.00 on May 2, 2018.", **e)
    assert not ok("P00038 obligated $707,617,191.00.", **e)
    assert not ok("P00039 obligated $707,617,191.00 on May 2, 2018.", **e)


def test_premise_trap_needs_a_stated_reason():
    e = {"refusal": True, "reason_any": [r"submarine", r"columbia"]}
    assert ok("ACRU is a Columbia-class submarine system, not a carrier one.", **e)
    assert not ok("ACRU cost $12 million on CVN 79.", **e)


def test_missing_answer_fails_and_empty_key_is_an_error():
    assert not ok(None, texts=["x"])
    with pytest.raises(ValueError):
        grade("anything", {})
