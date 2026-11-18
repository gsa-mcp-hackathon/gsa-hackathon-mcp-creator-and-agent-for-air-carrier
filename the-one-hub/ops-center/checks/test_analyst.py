"""Analyst engine checks on synthetic cases with known answers."""
import math

import pytest

from core.analyst import backtest, engine, learn, loa, residual

P = "N0000000C0001"
SCN18 = "017-2018/2022-1611-000"
SCN16 = "017-2016/2020-1611-000"
RDT19 = "017-2019/2020-1319-000"
RDT21 = "017-2021/2022-1319-000"
OLD = "017-2009/2013-1611-000"
ALL = (SCN18, SCN16, RDT19, RDT21, OLD)


def tx(mod, date, dollars, desc=""):
    return engine.Tx(key=f"{P}:{mod}", piid=P, date=date, mod=mod, amount=dollars * 100, desc=desc,
                     award_tas=ALL, award_oc=("31.0: Equipment",), award_pa=("0002: SHIPBUILDING",))


def fc(period, tas, dollars):
    return engine.FCRow(period=period, piid=P, tas=tas, oc="31.0", pa="0002", amount=dollars * 100)


@pytest.fixture(autouse=True)
def _clear():
    engine.clear_cache()


def corpus():
    t = [tx("P1", "2019-04-10", 90, "SCN FUNDING"), tx("P2", "2019-05-01", 10),
         tx("P3", "2020-01-15", 40, "RDT&E FUNDING"), tx("P4", "2020-08-01", 5)]
    f = [fc("FY2019Q3", SCN18, 90), fc("FY2019Q3", RDT19, 10), fc("FY2020Q4", SCN18, 50)]
    return engine.Corpus(t, f)


def test_period_window_and_fiscal():
    assert loa.period_window("FY2019Q3") == (2019, 7, 9)
    assert loa.period_window("FY2020P09") == (2020, 7, 9)
    assert loa.fiscal("2020-03-10") == (2020, 6)
    assert loa.fiscal("2019-10-01") == (2020, 1)


def test_availability_excludes_unavailable_and_cancelled():
    c = corpus()
    cands, excl = engine.candidates(c, c.get(f"{P}:P1"))
    reasons = {e["tas"]: e["reason"] for e in excl}
    assert RDT21 in reasons and "unavailable" in reasons[RDT21]
    assert OLD in reasons and "cancelled" in reasons[OLD]
    assert SCN18 in cands and RDT21 not in cands


def test_lp_proves_majority_account():
    c = corpus()
    labels = learn.deduced_labels(c, P)
    got = {(lb["mod"], lb["truth"]) for lb in labels}
    assert ("P1", SCN18) in got  # 90 into rows 90/10: at least 80 must be SCN18
    assert not any(m == "P2" for m, _ in got)  # 10 can sit in either row


def test_guaranteed_respects_sign():
    assert engine.guaranteed(80, 90, 90) == 80
    assert engine.guaranteed(-90, -80, -90) == 80
    assert engine.guaranteed(-90, 0, -90) == 0


def test_posterior_sums_to_one_with_none():
    c = corpus()
    r = engine.investigate_tx(c, f"{P}:P1")
    total = sum(r["posterior_all"].values()) + r["none_of_these"]
    assert math.isclose(total, 1.0, abs_tol=1e-3)
    assert len(r["options"]) <= 3 and r["grade"] == "LEAD"
    assert r["options"][0]["loa"]["tas"] == SCN18 and r["options"][0]["deductive"]


def test_hidden_period_still_ranks_by_other_evidence():
    c = corpus().without_period("FY2019Q3")
    r = engine.investigate_tx(c, f"{P}:P1")
    assert r["context"]["file_c_period"] is None
    assert r["options"][0]["loa"]["tas"] == SCN18  # text cue + history + recency
    assert not r["options"][0]["deductive"]


def test_text_cue_moves_rdte():
    c = corpus()
    r = engine.investigate_tx(c, f"{P}:P3")
    assert r["options"][0]["loa"]["colour"] == "RDTEN"


def test_every_option_names_a_confirmer():
    r = engine.investigate_tx(corpus(), f"{P}:P2")
    for o in r["options"]:
        cr = o["collection_requirement"]
        assert cr["target_office"] and cr["target_document"] and cr["account"] == o["loa"]["tas"]


def test_fit_moves_toward_truth_and_holds_without_labels():
    c = corpus().without_period("FY2019Q3")
    case = learn._case(c, f"{P}:P2", RDT19)
    w0 = dict(engine.PRIOR_WEIGHTS)
    assert learn.fit([], w0) == w0
    w = learn.fit([case] * 5, w0, lam=0.1, steps=300, lr=0.2)
    p0 = engine.posterior(case[0], w0)[0][RDT19]
    p1 = engine.posterior(case[0], w)[0][RDT19]
    assert p1 > p0


def test_calibration_math():
    cal = learn.calibration([(0.9, True), (0.9, False)])
    assert cal["n"] == 2 and math.isclose(cal["brier"], (0.01 + 0.81) / 2, abs_tol=1e-4)
    assert math.isclose(cal["ece"], 0.4, abs_tol=1e-4)


def test_residual_timing_exact_and_sized():
    # FY2020 P04-P06 has no File C period; its 1000 shows up in FY2020Q4
    t = [tx("A", "2020-02-01", 1000), tx("B", "2020-08-01", 5)]
    f = [fc("FY2020Q1", SCN18, 0), fc("FY2020Q4", SCN18, 1005)]
    r = residual.explain(engine.Corpus(t, f), P, "FY2020Q4")
    top = r["options"][0]
    assert top["cause"] == "timing" and top["exact_to_cent"]
    # a tiny gap is not explained by a large uncovered month
    f2 = [fc("FY2020Q1", SCN18, 0), fc("FY2020Q4", SCN18, 6)]
    r2 = residual.explain(engine.Corpus(t, f2), P, "FY2020Q4")
    timing = [o for o in r2["options"] if o["cause"] == "timing"]
    assert not timing or timing[0]["fraction_explained"] < 0.01


def test_residual_tied_period_has_no_options():
    r = residual.explain(corpus(), P, "FY2019Q3")
    assert r["gap"] == "$0.00" and r["options"] == []


def test_window_posterior_all_covers_every_candidate():
    c = corpus().without_period("FY2019Q3")
    r = engine.investigate_window(c, P, 2019, 7, 9)
    pa = r["posterior_all"]
    assert math.isclose(sum(pa.values()) + r["none_of_these"], 1.0, abs_tol=1e-3)
    # every candidate gets a share, not just the top 3 options
    cands = set().union(*(engine.candidates(c, t)[0] for t in c.tx_in(P, "FY2019Q3")))
    assert set(pa) == cands
    for o in r["options"]:
        assert math.isclose(pa[o["tas"]], o["expected_share"], abs_tol=1e-4)


def test_split_metrics_known_answers():
    assert backtest.tvd({"a": 0.5, "b": 0.5}, {"a": 1.0}) == 0.5
    assert backtest.tvd({"a": 1.0}, {"a": 1.0}) == 0.0
    assert math.isclose(backtest.smooth({"a": 1.0}, "b", 0.25), 0.125)  # 0.75*0 + 0.25/2
    assert math.isclose(backtest.smooth({"a": 1.0}, "a", 0.25), 1.0)  # 0.75*1 + 0.25/1
    assert math.isclose(backtest.smooth({"a": 0.5, "b": 0.5}, "c", 0.25), 0.25 / 3)


def test_backtest_split_reads_window_posterior():
    rep = backtest.run(corpus(), P)
    s = rep["split"]
    assert s["n"] == rep["n_period_labels"] == len(s["rows"])
    by = {r["period"]: r for r in rep["period"]["rows"]}
    for row in s["rows"]:
        assert 0.0 <= row["tvd_engine"] <= 1.0 and 0.0 <= row["tvd_baseline"] <= 1.0
        if by[row["period"]]["rank"] is None:
            assert by[row["period"]]["predicted_share"] == row["p_truth_engine"]
