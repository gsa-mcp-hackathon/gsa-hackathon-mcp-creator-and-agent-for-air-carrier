"""Unblind and score the blind review sheets (round 10, B3).

    python score_blind.py --seed "<the seed>" --hash <sha256 recorded before sending> \
        blind_sheet_AB.csv blind_sheet_CD.csv [...]

Checks the seed against the recorded hash, maps A and B back to "with servers"
and "without tools", and writes BLIND_RESULTS.md: each rater's mean per
criterion and per arm, how often each would rely on an answer, which side each
preferred, and agreement between every pair of raters as quadratic-weighted
Cohen's kappa on the 0 to 2 scores (both arms pooled, 20 items per criterion).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import statistics
import sys
from pathlib import Path

from build_blind_pack import servers_side

HERE = Path(__file__).parent
CRITERIA = ["correct_0_2", "cited_0_2", "usable_0_2"]


def weighted_kappa(x: list[int], y: list[int], k: int = 3) -> float | None:
    """Quadratic-weighted Cohen's kappa for ratings 0..k-1."""
    n = len(x)
    if n == 0:
        return None
    obs = [[0.0] * k for _ in range(k)]
    for a, b in zip(x, y):
        obs[a][b] += 1
    px = [sum(r) / n for r in obs]
    py = [sum(obs[i][j] for i in range(k)) / n for j in range(k)]
    w = [[(i - j) ** 2 / (k - 1) ** 2 for j in range(k)] for i in range(k)]
    o = sum(w[i][j] * obs[i][j] / n for i in range(k) for j in range(k))
    e = sum(w[i][j] * px[i] * py[j] for i in range(k) for j in range(k))
    return None if e == 0 else 1 - o / e


def unblind(path: Path, seed: str) -> dict:
    """{(qid, arm): {criterion: score, 'rely': bool}, ...} plus preferences."""
    scores, prefer = {}, {"with": 0, "without": 0, "none": 0}
    for row in csv.DictReader(path.open(encoding="utf-8")):
        s = servers_side(seed, row["qid"])
        arm = {s: "with", ("B" if s == "A" else "A"): "without"}
        for side in "AB":
            scores[(row["qid"], arm[side])] = {
                **{c: int(row[f"{side}_{c}"]) for c in CRITERIA},
                "rely": row[f"{side}_would_rely_Y_N"].strip().upper().startswith("Y")}
        pick = row.get("better_A_or_B", "").strip().upper()[:1]
        prefer[arm.get(pick, "none")] += 1
    return {"scores": scores, "prefer": prefer}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seed", required=True)
    ap.add_argument("--hash", required=True, help="the SHA-256 recorded before sending")
    ap.add_argument("sheets", nargs="+", type=Path)
    args = ap.parse_args()
    if hashlib.sha256(args.seed.encode()).hexdigest() != args.hash.lower():
        sys.exit("The seed does not match the recorded hash; nothing unblinded.")
    raters = {p.stem.replace("blind_sheet_", ""): unblind(p, args.seed) for p in args.sheets}

    lines = ["# Blind subject-matter review", "",
             (f"Raters: {len(raters)}. Ten answer pairs, shown as A and B; a seed recorded by "
             f"hash (`{args.hash[:16]}...`) before the sheets went out decided the sides. "
             "Tool-call markup and search narration were removed from both answers."), "",
             "| Rater | Arm | Correct | Cited | Usable | Total of 6 | Would rely | Preferred |",
             "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for name, r in raters.items():
        for arm in ("with", "without"):
            items = [v for (q, a), v in r["scores"].items() if a == arm]
            means = [statistics.mean(v[c] for v in items) for c in CRITERIA]
            rely = sum(v["rely"] for v in items)
            label = "with servers" if arm == "with" else "without tools"
            lines.append(f"| {name} | {label} | " + " | ".join(f"{m:.1f}" for m in means)
                         + f" | {sum(means):.1f} | {rely} of {len(items)} | {r['prefer'][arm]} |")
    if len(raters) > 1:
        lines += ["", "Agreement, quadratic-weighted Cohen's kappa (20 items per criterion):", "",
                  "| Raters | " + " | ".join(c.split("_")[0] for c in CRITERIA) + " |",
                  "| --- |" + " --- |" * len(CRITERIA)]
        for (n1, r1), (n2, r2) in itertools.combinations(raters.items(), 2):
            keys = sorted(set(r1["scores"]) & set(r2["scores"]))
            ks = [weighted_kappa([r1["scores"][k][c] for k in keys],
                                 [r2["scores"][k][c] for k in keys]) for c in CRITERIA]
            lines.append(f"| {n1} and {n2} | "
                         + " | ".join("n/a" if v is None else f"{v:.2f}" for v in ks) + " |")
    (HERE / "BLIND_RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
