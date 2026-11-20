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
   `sha256sum questions_h2.json` and compare it with the line above. It was
   published in commit `6e6438e`, after the run.

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

## What the sealed run found (2026-11-20)

Runs `rpt-cde6da6d` and `166621165979`, tool catalog `1143a3c17536b7bd`, Delta job run
749141653255923. Both models, three repeats with the 29 tools and one no-tool baseline.

**31 of 72 with tools (43.1%, 95% CI 32.3 to 54.6) against 3 of 24 without (12.5%).**
This is the official score. It is reported as graded, and nothing below changes it.

The answers of every miss were read in the notebook's inspect cell. The 41 misses fall
into four groups:

| Group | Questions | Misses | Cause | Fix (branch `fix/round2-findings`) |
| --- | --- | --- | --- | --- |
| Tool coverage | H02, H04, H09 | 17 | No tool read the obligations on the DD&C contract N00024-15-C-2114; only 2116 had one | `carrier_search_obligations` takes a required `contract` and reads either prime contract |
| Tool coverage | H03 | 5 | Obligations came back in date order only, so "largest" needed every page | `order`: `largest_first` or `smallest_first`, sorted in SQL on the decimal amount |
| Tool coverage | H08, H09 | 6 (H08) | The FPDS-NG figure lives only in variance E-16, and no tool searched the variance register | New tool `carrier_search_variances` over E-1 to E-17 |
| Exhibit reading | H05, H06 | 7 | The P-5c has one column per ship, headed by its full-funding fiscal year. Models read the CVN-80 column (FY 2018) for CVN-79 (FY 2013), and one computed 63.09% for 63.11% | `docs_get_table` labels each P-5c cell with `ship_fy`, `hull` and `share_of_total_ship_estimate_pct`, computed on the server to 0.01 |
| Grader | H10 | 5 | The decoy pattern accepts "not public" and similar, but not "cannot find" or "could not find". Some answers that refused correctly were graded as misses | None to the official score. See the hand reading below |
| Other | H07 | 1 | One run named the right contract but not the command | None |

The F7 fix itself failed: F4 went 0 of 6. The `budget_cycle` reader needed a separator
before `PB`, and the real file names are `SCN_BookPB2024.pdf` and `SCN_Bookpb2006.pdf`,
so 21 of 22 books got no cycle and the PB 2024 filter returned nothing. The unit tests
used names with a separator, so they passed. The reader now accepts the real names (the
tests use them) and falls back to the most frequent `PB 20xx` header in the book's
first 60 pages.

### The H10 hand reading

The regex grade stands. A person's reading of the same answers is recorded apart, in
`hand_grades.csv` beside this file, and `analyze.py` prints it under the official table
with its own label. To fill it, read the six tool-mode answers and two baselines:

```sql
SELECT run_id, model, mode, passed, answer
FROM users.xiaobing_shang1_civ.aircarrier_delegation_eval_runs
WHERE qid = 'H10 decoy rework' AND run_id IN ('rpt-cde6da6d', '166621165979')
ORDER BY model, mode
```

and write one row per answer:

```csv
run_id,model,mode,qid,regex_passed,hand_passed,note
```

`hand_passed` is 1 only when the answer says the figure is not found or not public and
gives no dollar amount for CVN-79 rework. A dollar figure, even a hedged one, is a 0.

### What happens next

These 12 questions are public now. A run of them on the fixed tools is reported as a
post-fix re-run, under its own heading, and is not a held-out score. A new sealed set of
12, `h3`, was written after the fixes and before any run of them:
[`../round3/README.md`](../round3/README.md).

## Run it

In the workspace:

1. Upload `questions_h2.json` to a volume you can read, for example
   `/Volumes/users/xiaobing_shang1_civ/aircarrier_artifacts/questions_h2.json`.
2. Open `mcp-servers/Air Carrier Delegation Eval.py`, put that path in `QUESTION_FILES`,
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
