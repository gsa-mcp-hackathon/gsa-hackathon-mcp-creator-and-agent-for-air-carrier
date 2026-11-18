"""Backtest: hide what we know, ask the analyst, score it.

Three tests, each run with the answer's own File C period hidden so the
engine cannot read the answer back:

  oracle    the period visible. Sanity only: deduced labels must come top-1.
  tx        transaction-level primary account, labels from LP deduction.
  period    period-level primary account, labels from File C itself.
  split     period-level, the whole account split rather than the top pick:
            total variation distance from the File C split and log loss of
            the File C plurality account, engine against the baseline.
  refit     leave-one-period-out: refit on the other periods, test on the
            held-out one, compare log loss with the expert priors.

n is small. Every report carries n so nobody reads a 1.0 off four cases.

Known limit: the baseline and the engine's history feature both read File C
periods later than the one under test (look-ahead, same for both).
"""
from __future__ import annotations

import math

from core.analyst import engine, learn, loa

NONE_KEY = "(none of these)"
BASELINE_ALPHA = 0.25  # same smoothing the engine's history feature uses


def _abs_split(rows) -> dict[str, float]:
    """Share of absolute File C money by account."""
    acct: dict[str, int] = {}
    for r in rows:
        acct[r.tas] = acct.get(r.tas, 0) + abs(r.amount)
    tot = sum(acct.values())
    return {k: v / tot for k, v in acct.items()} if tot else {}


def tvd(p: dict[str, float], q: dict[str, float]) -> float:
    """Total variation distance: 0 is the same split, 1 shares nothing."""
    return 0.5 * sum(abs(p.get(k, 0.0) - q.get(k, 0.0)) for k in set(p) | set(q))


def smooth(p: dict[str, float], truth: str, alpha: float = BASELINE_ALPHA) -> float:
    """Probability a split gives the truth after mixing in a uniform share."""
    k = len(set(p) | {truth})
    return (1 - alpha) * p.get(truth, 0.0) + alpha / k


def _ll(p: float) -> float:
    return -math.log(max(p, 1e-9))


def _truth_rank(result: dict, truth: str, key: str = "tas") -> tuple[int | None, float]:
    for o in result["options"]:
        tas = o["loa"]["tas"] if "loa" in o else o[key]
        if tas == truth:
            return o["rank"], o.get("confidence", o.get("expected_share", 0.0))
    # outside the top 3: report the probability it still got, not zero
    return None, result.get("posterior_all", {}).get(truth, 0.0)


def run(corpus: engine.Corpus, piid: str, weights: dict | None = None) -> dict:
    engine.clear_cache()
    tx_labels = learn.deduced_labels(corpus, piid)
    per_labels = learn.period_labels(corpus, piid)
    rep: dict = {"piid": piid, "engine": engine.ENGINE_VERSION, "n_tx_labels": len(tx_labels),
                 "n_period_labels": len(per_labels)}

    oracle = []
    for lab in tx_labels:
        r = engine.investigate_tx(corpus, lab["key"], weights)
        oracle.append(_truth_rank(r, lab["truth"])[0] == 1)
    rep["oracle_top1"] = f"{sum(oracle)}/{len(oracle)}"

    rows, cal, probs = [], [], []
    for lab in tx_labels:
        hid = corpus.without_period(lab["period"])
        r = engine.investigate_tx(hid, lab["key"], weights)
        rank, conf = _truth_rank(r, lab["truth"])
        top = r["options"][0]
        cal.append((top["confidence"], rank == 1))
        probs.append(conf)
        rows.append({"mod": lab["mod"], "date": lab["date"], "period": lab["period"], "truth": lab["truth"],
                     "min_share": lab["min_share"], "rank": rank, "p_truth": conf,
                     "top1": top["loa"]["tas"], "p_top1": top["confidence"]})
    rep["tx"] = {"rows": rows,
                 "top1": f"{sum(1 for x in rows if x['rank'] == 1)}/{len(rows)}",
                 "top3": f"{sum(1 for x in rows if x['rank'])}/{len(rows)}",
                 "log_loss": learn.log_loss(probs), "calibration": learn.calibration(cal)}

    # baseline: the split of File C money in the other periods; its top-1 is
    # always the account with the most money elsewhere. The engine has to beat
    # this to claim any skill.
    prow, pcal, srow = [], [], []
    base_hits = 0
    for lab in per_labels:
        per = lab["period"]
        hid = corpus.without_period(per)
        fy, lo, hi = loa.period_window(per)
        r = engine.investigate_window(hid, piid, fy, lo, hi, weights, label=per)
        rank, share = _truth_rank(r, lab["truth"])
        pcal.append((r["options"][0]["expected_share"] if r["options"] else 0.0, rank == 1))
        prow.append({"period": per, "tied": lab["tied"], "truth": lab["truth"],
                     "truth_share_in_file_c": lab["truth_share"], "rank": rank,
                     "predicted_share": share,
                     "top1": r["options"][0]["tas"] if r["options"] else None})

        base = _abs_split(x for x in corpus.fc if x.piid == piid and x.period != per)
        base_hits += int(bool(base) and max(base, key=base.get) == lab["truth"])
        truth_split = _abs_split(corpus.rows(piid, per))
        eng = {**r.get("posterior_all", {}), NONE_KEY: r.get("none_of_these", 0.0)}
        srow.append({
            "period": per, "truth": lab["truth"],
            "tvd_engine": round(tvd(eng, truth_split), 4),
            "tvd_baseline": round(tvd(base, truth_split), 4),
            "p_truth_engine": round(eng.get(lab["truth"], 0.0), 6),
            "p_truth_baseline": round(base.get(lab["truth"], 0.0), 6),
            "p_truth_baseline_smoothed": round(smooth(base, lab["truth"]), 6),
        })
    rep["period_baseline_top1"] = f"{base_hits}/{len(per_labels)}"
    rep["period"] = {"rows": prow,
                     "top1": f"{sum(1 for x in prow if x['rank'] == 1)}/{len(prow)}",
                     "top3": f"{sum(1 for x in prow if x['rank'])}/{len(prow)}",
                     "calibration": learn.calibration(pcal)}
    n = len(srow) or 1
    rep["split"] = {
        "n": len(srow),
        "rows": srow,
        "mean_tvd_engine": round(sum(x["tvd_engine"] for x in srow) / n, 4),
        "mean_tvd_baseline": round(sum(x["tvd_baseline"] for x in srow) / n, 4),
        "engine_closer": f"{sum(1 for x in srow if x['tvd_engine'] < x['tvd_baseline'])}/{len(srow)}",
        "log_loss_engine": round(sum(_ll(x["p_truth_engine"]) for x in srow) / n, 4),
        "log_loss_baseline": round(sum(_ll(x["p_truth_baseline"]) for x in srow) / n, 4),
        "log_loss_baseline_smoothed": round(sum(_ll(x["p_truth_baseline_smoothed"]) for x in srow) / n, 4),
        "baseline_alpha": BASELINE_ALPHA,
        "reading": ("Lower is better for both. tvd compares the whole split with File C (the engine's "
                    "none-of-these share counts as error); log loss scores the probability given to the "
                    "File C plurality account. Compare with the smoothed baseline, the raw one is "
                    "overconfident by construction."),
    }

    # leave-one-period-out refit on tx labels
    folds = []
    for held in sorted({lab["period"] for lab in tx_labels}):
        train = [learn._case(corpus.without_period(lb["period"]), lb["key"], lb["truth"])
                 for lb in tx_labels if lb["period"] != held]
        w_fit = learn.fit(train, {**engine.PRIOR_WEIGHTS, **(weights or {})})
        test = [lb for lb in tx_labels if lb["period"] == held]
        p_prior, p_fit = [], []
        for lb in test:
            hid = corpus.without_period(held)
            p_prior.append(_truth_rank(engine.investigate_tx(hid, lb["key"], weights), lb["truth"])[1])
            p_fit.append(_truth_rank(engine.investigate_tx(hid, lb["key"], w_fit), lb["truth"])[1])
        folds.append({"held_out": held, "n_train": len(train), "n_test": len(test),
                      "log_loss_prior": learn.log_loss(p_prior), "log_loss_refit": learn.log_loss(p_fit)})
    rep["refit"] = folds
    all_cases = [learn._case(corpus.without_period(lb["period"]), lb["key"], lb["truth"]) for lb in tx_labels]
    rep["weights_refit_all"] = learn.fit(all_cases, {**engine.PRIOR_WEIGHTS, **(weights or {})})
    return rep
