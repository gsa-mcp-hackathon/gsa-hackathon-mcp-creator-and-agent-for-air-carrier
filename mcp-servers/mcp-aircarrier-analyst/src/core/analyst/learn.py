"""Labels, refitting and calibration: how the analyst improves itself.

Where labels come from, strongest first:
  * deduced: linear-programming bounds on a period whose File C ties to the
    cent prove that at least half of a transaction came from one account.
    That is arithmetic, not opinion (assumption: allocations keep the
    transaction's sign).
  * confirmed: an outcome recorded against an authoritative document
    (Section G accounting data, an ERP posting). Recorded in UC, never here.

Refit: maximum likelihood of the true option under the engine's
conditional logit, with an L2 pull toward the expert priors. With few labels
the weights barely move; each confirmed outcome moves them a little more.
That is the self-improvement loop, and its size is honest about n.
"""
from __future__ import annotations

import math

from core.analyst import engine


def deduced_labels(corpus: engine.Corpus, piid: str) -> list[dict]:
    """Transactions whose primary account is proven by LP in a tied period."""
    out = []
    for label in corpus.periods(piid):
        if not corpus.tied(piid, label):
            continue
        b = engine.allocation_bounds(corpus.tx_in(piid, label), corpus.rows(piid, label))
        if not b:
            continue
        by_tx: dict[str, dict[str, tuple[int, int]]] = {}
        for (key, tas), lohi in b.items():
            by_tx.setdefault(key, {})[tas] = lohi
        for key, accts in by_tx.items():
            t = corpus.get(key)
            if not t.amount:
                continue
            g = {s: engine.guaranteed(lo, hi, t.amount) for s, (lo, hi) in accts.items()}
            cap = {s: max(abs(lo), abs(hi)) for s, (lo, hi) in accts.items()}
            for s in accts:
                rule = None
                if g[s] * 2 >= abs(t.amount):
                    rule = "majority"  # at least half must come from s
                elif g[s] > 0 and all(g[s] > cap[k] for k in accts if k != s):
                    rule = "dominant"  # s's floor beats every other account's ceiling
                if rule:
                    out.append({
                        "key": key, "piid": piid, "mod": t.mod, "date": t.date, "period": label,
                        "truth": s, "min_share": round(g[s] / abs(t.amount), 4),
                        "source": f"deduced:lp-bounds:{rule}",
                    })
    return out


def period_labels(corpus: engine.Corpus, piid: str) -> list[dict]:
    """For each File C period, the account carrying the largest share."""
    out = []
    for label in corpus.periods(piid):
        acct: dict[str, int] = {}
        for r in corpus.rows(piid, label):
            acct[r.tas] = acct.get(r.tas, 0) + abs(r.amount)
        tot = sum(acct.values()) or 1
        best = max(acct, key=acct.get)
        out.append({"period": label, "truth": best, "truth_share": round(acct[best] / tot, 4),
                    "accounts": {k: round(v / tot, 4) for k, v in acct.items()},
                    "tied": corpus.tied(piid, label)})
    return out


def _case(corpus: engine.Corpus, key: str, truth: str | None):
    t = corpus.get(key)
    cands, _ = engine.candidates(corpus, t)
    return engine.features(corpus, t, cands), (truth if truth in cands else None)


def fit(cases: list[tuple[dict, str | None]], prior: dict[str, float] | None = None,
        lam: float = 2.0, steps: int = 400, lr: float = 0.05) -> dict[str, float]:
    """Refit weights on (features, truth) cases. truth None means none-of-these."""
    w0 = dict(prior or engine.PRIOR_WEIGHTS)
    w = dict(w0)
    if not cases:
        return w
    for _ in range(steps):
        g = {k: 0.0 for k in w}
        for feats, truth in cases:
            post, none = engine.posterior(feats, w)
            # observed minus expected feature counts
            obs = feats[truth] if truth else {}
            for k, v in obs.items():
                g[k] = g.get(k, 0.0) + v
            if truth is None:
                g["none_bias"] += 1.0
            for c, p in post.items():
                for k, v in feats[c].items():
                    g[k] = g.get(k, 0.0) - p * v
            g["none_bias"] -= none
        for k in w:
            w[k] += lr * (g.get(k, 0.0) - lam * (w[k] - w0[k])) / len(cases)
    return {k: round(v, 4) for k, v in w.items()}


def calibration(preds: list[tuple[float, bool]], bins: int = 5) -> dict:
    """Brier score and expected calibration error of top-1 confidences."""
    if not preds:
        return {"n": 0}
    brier = sum((p - (1.0 if y else 0.0)) ** 2 for p, y in preds) / len(preds)
    ece, table = 0.0, []
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        sel = [(p, y) for p, y in preds if lo <= p < hi or (b == bins - 1 and p == 1.0)]
        if not sel:
            continue
        conf = sum(p for p, _ in sel) / len(sel)
        acc = sum(1 for _, y in sel if y) / len(sel)
        ece += len(sel) / len(preds) * abs(conf - acc)
        table.append({"bin": f"{lo:.1f}-{hi:.1f}", "n": len(sel), "mean_conf": round(conf, 3), "accuracy": round(acc, 3)})
    return {"n": len(preds), "brier": round(brier, 4), "ece": round(ece, 4), "bins": table}


def log_loss(preds: list[float]) -> float:
    return round(-sum(math.log(max(p, 1e-9)) for p in preds) / max(1, len(preds)), 4)
