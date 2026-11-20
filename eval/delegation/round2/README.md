# Delegation evaluation, round 2: a sealed held-out set

Round 1 had 14 questions, 5 of them held out, so its strict held-out interval is
wide (64.1% to 93.3%), and all four tool-mode misses were one question (F4, finding
F7). Round 2 adds 12 new held-out questions, sealed before any model sees them, and
re-runs everything on the tool catalog that carries the F7 fix.

## The seal

The questions, the grading patterns and the answer key are in one file,
`questions_h2.json`. It is **not** in this repository. Its SHA-256 is:

```
4a742955ff78983dd4f1eebe267ff06d45fce1c566c4c6211ac3e42ae281eee0
```

This line was committed before any run. The order of events can be checked from Git
and from the run log alone:

1. The commit that adds this file predates every `h2` row in the runs table (`run_at`).
2. The delegation notebook refuses any question file whose SHA-256 differs from the
   value above (`SEALED_SHA256`), so the questions that were run are the questions
   that were sealed.
3. Before calling a model, the notebook recomputes every SQL-backed answer from the
   warehouse (`verify_sql` against `expect`) and stops on any mismatch, so the key
   is checked against the data, not against the tools.
4. After the run, `questions_h2.json` is committed here. Anyone can run
   `sha256sum questions_h2.json` and compare it with the line above.

## What the 12 questions test

| Category | Count | What a pass means |
| --- | --- | --- |
| Obligations | 2 | A fiscal-year count and total, and the largest action, to the cent |
| Coverage | 1 | A fiscal-year total on the DD&C contract, a cut no tool was built for by name |
| Contamination | 1 | The model notices a $54M action labelled CVN 79 that is Nimitz work |
| Exhibit | 2 | P-5c cost categories from the PB 2027 book |
| Documents | 2 | A contract number from the MSAR and a GAO finding |
| Variance | 2 | Two places where federal systems disagree, with the figure to use |
| Decoy | 1 | The right answer is that the figure is not public |
| Exclusion | 1 | A contract number that must not be counted |

The questions were written on 2026-11-20 against the tool catalog at commit
`2fdd474`. None was used to change a tool.

## Run it

In the workspace:

1. Upload `questions_h2.json` to a volume you can read, for example
   `/Volumes/users/xiaobing_shang1_civ/eval/questions_h2.json`.
2. Open `mcp-servers/Air Carrier Delegation Eval.py`, set `QUESTION_FILE` to that path,
   and run every cell. The report cell runs all 26 questions (dev, fresh and h2) on
   both models: three repeats with tools and one no-tool baseline each.
3. Export the new rows to `eval/delegation/runs.csv` (same columns as today), commit
   `questions_h2.json` beside this file, and run
   `python3 eval/delegation/analyze.py --write`. The round 2 section of `RESULTS.md`
   appears once `h2` rows exist.

## Honest limits

- 12 questions is still a small set. With 2 models and 3 repeats it gives 72 graded
  runs, enough to narrow the held-out interval but not to rank the two models.
- Grading is regex over the final answer, as in round 1. Read the answers of every
  failure in the notebook's inspect cell before quoting a pass rate.
- H02 asks for a cut that no tool exposes by name. A miss there is a coverage finding
  about the tools, and is reported as one.
