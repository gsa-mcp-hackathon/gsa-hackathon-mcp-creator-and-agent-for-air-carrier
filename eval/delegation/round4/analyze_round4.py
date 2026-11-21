"""Re-derive the round 4 delegation results from the logged runs, with 95% intervals.

    python3 eval/delegation/round4/analyze_round4.py            # prints RESULTS.md
    python3 eval/delegation/round4/analyze_round4.py --write    # rewrites RESULTS.md

runs_r4.csv is an export of run r4-4bb6a2a6 from
users.xiaobing_shang1_civ.aircarrier_delegation_eval_runs (552 rows), without the
answer and trace columns, plus the question's category and the grader checks that
failed. questions_h4.json is the sealed question file.

Two kinds of interval, because the three repeats of one question are not independent:

* Wilson score interval over runs: comparable with rounds 1-3, which reported it.
  It treats every run as independent, so it is too narrow.
* Question bootstrap: questions are resampled with replacement, each carrying all of
  its runs, 10,000 times with a fixed seed. This counts the uncertainty from having
  only 69 questions, and is the interval to quote.

Pure Python, no dependencies; the output is the same on every run.
"""
from __future__ import annotations

import csv
import json
import math
import random
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN_ID = "r4-4bb6a2a6"
Z = 1.959963984540054
BOOT = 10_000
SEED = 20261121
MODELS = {"databricks-claude-sonnet-4-5": "Claude Sonnet 4.5", "databricks-gpt-5-mini": "GPT-5 mini"}
SETS = {"h4-generated": "Generated (45)", "h4-reviewed": "Reviewed (24)"}


def wilson(k: int, n: int) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + Z**2 / n
    centre = (p + Z**2 / (2 * n)) / denom
    half = Z * math.sqrt(p * (1 - p) / n + Z**2 / (4 * n**2)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def _pct(lo: float, hi: float) -> str:
    return f"{100 * lo:.1f} to {100 * hi:.1f}"


def bootstrap(groups: list[tuple[int, int]], seed: int = SEED) -> tuple[float, float]:
    """95% percentile interval of the pooled pass rate, resampling questions (k, n per question)."""
    if not groups:
        return (0.0, 0.0)
    rng, stats = random.Random(seed), []
    for _ in range(BOOT):
        pick = [groups[rng.randrange(len(groups))] for _ in groups]
        stats.append(sum(k for k, _ in pick) / sum(n for _, n in pick))
    stats.sort()
    return (stats[int(0.025 * BOOT)], stats[int(0.975 * BOOT) - 1])


def boot_diff(a: dict, b: dict, seed: int = SEED) -> tuple[float, float, float]:
    """Paired difference a - b in pass rate over the same questions (dicts qid -> (k, n))."""
    qids = sorted(set(a) & set(b))
    point = sum(a[q][0] for q in qids) / sum(a[q][1] for q in qids) - \
        sum(b[q][0] for q in qids) / sum(b[q][1] for q in qids)
    rng, stats = random.Random(seed), []
    for _ in range(BOOT):
        pick = [qids[rng.randrange(len(qids))] for _ in qids]
        stats.append(sum(a[q][0] for q in pick) / sum(a[q][1] for q in pick)
                     - sum(b[q][0] for q in pick) / sum(b[q][1] for q in pick))
    stats.sort()
    return (point, stats[int(0.025 * BOOT)], stats[int(0.975 * BOOT) - 1])


def load() -> list[dict]:
    with open(HERE / "runs_r4.csv", newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["run_id"] == RUN_ID]
    for r in rows:
        r["passed"] = r["passed"].lower() in ("true", "1")
        r["tools"] = r["mode"].startswith("tools_rep")
    return rows


def per_question(rows: list[dict]) -> dict[str, tuple[int, int]]:
    g: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for r in rows:
        g[r["qid"]][0] += r["passed"]
        g[r["qid"]][1] += 1
    return {q: (k, n) for q, (k, n) in g.items()}


def cell(rows: list[dict]) -> str:
    if not rows:
        return "-"
    k, n = sum(r["passed"] for r in rows), len(rows)
    return f"{k}/{n} = {100 * k / n:.1f}% ({interval(rows)})"


def interval(rows: list[dict]) -> str:
    """Question bootstrap; at 0% or 100% it has no width, so the Wilson interval is shown, marked *."""
    k, n = sum(r["passed"] for r in rows), len(rows)
    if k in (0, n):
        return _pct(*wilson(k, n)) + "*"
    return _pct(*bootstrap(list(per_question(rows).values())))


def cell_both(rows: list[dict]) -> tuple[str, str, str]:
    k, n = sum(r["passed"] for r in rows), len(rows)
    return (f"{k}/{n} = {100 * k / n:.1f}%", _pct(*bootstrap(list(per_question(rows).values()))), _pct(*wilson(k, n)))


def sel(rows, **m) -> list[dict]:
    return [r for r in rows if all(r[k] == v for k, v in m.items())]


def median(xs: list[float]) -> float:
    xs = sorted(xs)
    n = len(xs)
    return (xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2) if xs else 0.0


def report() -> str:
    rows = load()
    doc = json.loads((HERE / "questions_h4.json").read_text(encoding="utf-8"))
    qs = doc["questions"]
    order = {q["qid"]: i for i, q in enumerate(qs)}
    tl, nt = [r for r in rows if r["tools"]], [r for r in rows if not r["tools"]]
    out = [
        "# Round 4 delegation results",
        "",
        f"Generated by `analyze_round4.py` from `runs_r4.csv` ({len(rows)} rows of run `{RUN_ID}`, "
        f"tool catalog `{rows[0]['tool_catalog_sha']}`, 30 tools offered at once). Questions: the sealed "
        "[`questions_h4.json`](questions_h4.json), hash committed before any model saw it ([SEAL.md](SEAL.md)). "
        "Graded by [grader v2](grade.py).",
        "",
        "Each model answered every question three times with the tools and once without (same prompt). "
        "Percentages are pass rates over runs. **Intervals are 95% question-bootstrap intervals**: the 69 "
        "questions are resampled with all their runs, so the interval reflects how few questions there are. "
        "The Wilson interval used in rounds 1-3 treats the three repeats as independent and is narrower; it "
        "is given in the second table for comparison.",
        "",
        "## Headline",
        "",
        "| Model | Set | With tools (3 repeats) | No tools |",
        "|---|---|---|---|",
    ]
    for m, mn in MODELS.items():
        for s, sn in SETS.items():
            out.append(f"| {mn} | {sn} | {cell(sel(tl, model=m, question_set=s))} | {cell(sel(nt, model=m, question_set=s))} |")
        out.append(f"| {mn} | **All 69** | **{cell(sel(tl, model=m))}** | {cell(sel(nt, model=m))} |")
    out.append(f"| Both | All 69 | {cell(tl)} | {cell(nt)} |")

    out += ["", "Interval comparison, with tools, all 69 questions:", "",
            "| Model | Pass rate | Question bootstrap | Wilson over runs |", "|---|---|---|---|"]
    for m, mn in MODELS.items():
        a, b, c = cell_both(sel(tl, model=m))
        out.append(f"| {mn} | {a} | {b} | {c} |")

    a = per_question(sel(tl, model="databricks-claude-sonnet-4-5"))
    b = per_question(sel(tl, model="databricks-gpt-5-mini"))
    d, lo, hi = boot_diff(a, b)
    lift = {m: boot_diff(per_question(sel(tl, model=m)), per_question(sel(nt, model=m))) for m in MODELS}
    out += ["", "Paired differences over the same questions (question bootstrap):", ""]
    out.append(f"* Claude minus GPT-5 mini, with tools: {100 * d:+.1f} points (95% CI {100 * lo:+.1f} to {100 * hi:+.1f}).")
    for m, (d, lo, hi) in lift.items():
        out.append(f"* Tools minus no tools, {MODELS[m]}: {100 * d:+.1f} points (95% CI {100 * lo:+.1f} to {100 * hi:+.1f}).")

    out += ["", "Consistency (pass^3: all three tool runs of a question pass):", ""]
    for m, mn in MODELS.items():
        pq = per_question(sel(tl, model=m))
        all3 = sum(1 for k, n in pq.values() if k == n)
        none = sum(1 for k, _ in pq.values() if k == 0)
        out.append(f"* {mn}: {all3} of {len(pq)} questions pass all three; {none} pass none; "
                   f"{len(pq) - all3 - none} are inconsistent.")

    out += ["", "## By category, with tools", "", "| Category | Questions | Claude Sonnet 4.5 | GPT-5 mini |", "|---|---|---|---|"]
    cats = defaultdict(set)
    for q in qs:
        cats[q["category"]].add(q["qid"])
    for c in sorted(cats, key=lambda c: (-len(cats[c]), c)):
        cells = [cell([r for r in sel(tl, model=m) if r["category"] == c]) for m in MODELS]
        out.append(f"| {c} | {len(cats[c])} | {cells[0]} | {cells[1]} |")
    out += ["", "Category intervals rest on 2 to 20 questions each and are wide; read them as where to look, "
            "not as measured differences."]

    cut = [r for r in tl if r["error"]]
    by_cut = defaultdict(int)
    for r in cut:
        by_cut[(MODELS[r["model"]], r["qid"])] += 1
    out += ["", "## Runs that ended without an answer", "",
            f"{len(cut)} of {len(tl)} tool runs hit the 8-turn limit (`MAX_STEPS`) and are graded as failures. "
            "No run failed on a serving error, and no call needed a retry.", ""]
    for (mn, q), n in sorted(by_cut.items(), key=lambda x: (x[0][0], order[x[0][1]])):
        out.append(f"* {mn}, {q}: {n} of 3")

    out += ["", "## Cost per tool run (median)", "", "| Model | Tool calls | Tool output | Prompt tokens | Seconds |",
            "|---|---|---|---|---|"]
    for m, mn in MODELS.items():
        s = sel(tl, model=m)
        out.append(f"| {mn} | {median([int(r['calls']) for r in s]):.0f} | "
                   f"{median([int(r['tool_output_bytes']) for r in s]) / 1000:.1f} KB | "
                   f"{median([int(r['prompt_tokens']) for r in s]):,.0f} | {median([float(r['seconds']) for r in s]):.1f} |")

    out += ["", "## Every question", "",
            "Tool runs passed out of 3 per model, and the no-tools run (C = Claude, G = GPT-5 mini).", "",
            "| Question | Set | Category | Claude, tools | GPT-5 mini, tools | No tools C / G | Failed checks (tool runs) |",
            "|---|---|---|---|---|---|---|"]
    for q in qs:
        qid = q["qid"]
        c, g = sel(tl, model="databricks-claude-sonnet-4-5", qid=qid), sel(tl, model="databricks-gpt-5-mini", qid=qid)
        n0 = [sel(nt, model=m, qid=qid) for m in MODELS]
        fails = defaultdict(int)
        for r in c + g:
            for chk in (json.loads(r["failed_checks"]) if r["failed_checks"] else []):
                fails[chk] += 1
        fl = "; ".join(f"{k.replace('|', '/')} x{v}" for k, v in sorted(fails.items())) or ""
        out.append(f"| {qid} | {q['set']} | {q['category']} | {sum(r['passed'] for r in c)}/{len(c)} | "
                   f"{sum(r['passed'] for r in g)}/{len(g)} | {sum(r['passed'] for r in n0[0])} / {sum(r['passed'] for r in n0[1])} | "
                   f"{fl} |")

    np = [r for r in nt if r["passed"]]
    easy = sum(1 for r in np if r["category"] in ("premise", "decoy"))
    out += [
        "",
        "\\* At 0% or 100% a bootstrap interval has no width, so these cells show the Wilson interval over runs.",
        "",
        "## How to read this",
        "",
        "* **Not independent of the tools.** Genie Code wrote the generator's templates and drafted the 24 "
        "reviewed questions, and has seen the tools; the project owner reviewed and edited the 24. The "
        "generator removes hand-picking of subjects (a fixed seed drew them from the source tables), not "
        "authorship. A set written by someone who has not used the tools would be a stronger test.",
        "* **Not comparable point-for-point with rounds 2 and 3** (43.1% and 69.4% with tools). Round 4 has "
        "different questions, a different mix (more single-figure lookups in the generated set) and a "
        "different grader (v2 parses numbers, units, dates and refusals; rounds 1-3 used regexes).",
        "* **What changed between seal and run:** only the runner (checkpointing and retries, after the first "
        "attempt outlasted the command time limit and saved nothing). No tool, server or grader code changed. "
        "One unsaved timing probe ran the 69 questions once on GPT-5 mini before the official run; nothing "
        "was changed after it. See [SEAL.md](SEAL.md).",
        "* **The no-tools baseline** is the same model with the same prompt and no tools. "
        f"{easy} of its {len(np)} passes are premise traps or non-existent modifications, where saying a "
        "thing cannot be found is the right answer.",
        "",
    ]
    return "\n".join(out)


if __name__ == "__main__":
    text = report()
    if "--write" in sys.argv:
        (HERE / "RESULTS.md").write_text(text + "\n", encoding="utf-8")
    print(text)  # same bytes as RESULTS.md, so check.sh can diff the two
