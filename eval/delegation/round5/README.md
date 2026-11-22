# Round 5: questions from an independent author

Ten questions, answers and sources written by a teammate who did not build the tools
(`questions_i5.csv`, sealed in [SEAL.md](SEAL.md)), run through the round 4 runner, grader,
tools, models and repeats without changing them.

| File | Purpose |
| --- | --- |
| `questions_i5.csv` | The author's file, byte-identical to what arrived |
| `build_round5.py` | Adds the grader keys and writes `questions_i5.json` |
| `test_round5.py` | Each reference answer passes its key; a plausible wrong answer fails; the runner refuses a changed file |
| `run_round5.py` | Registers the sealed hash with `round4/run_round4.py` and runs it on `questions_i5.json` |

Run it in a Databricks notebook from the workspace Git folder (the docstring of
`run_round5.py` has the three lines). Results go to the same runs table as round 4 with
`question_set` `i5` and a run id starting `r5-`.
