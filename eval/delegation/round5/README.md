# Round 5: questions from an independent author

Ten questions, answers and sources written by an external evaluator who is not a member of the
project development team and took no part in building the MCP servers or preparing the model
responses (`questions_i5.csv`, sealed in [SEAL.md](SEAL.md)), run through the round 4 runner, grader,
tools, models and repeats without changing them.

| File | Purpose |
| --- | --- |
| `questions_i5.csv` | The author's file, byte-identical to what arrived |
| `build_round5.py` | Adds the grader keys and writes `questions_i5.json` |
| `test_round5.py` | Each reference answer passes its key; a plausible wrong answer fails; the runner refuses a changed file |
| `run_round5.py` | Registers the sealed hash with `round4/run_round4.py` and runs it on `questions_i5.json` |

Results: [RESULTS.md](RESULTS.md) (run `r5-0b1c2d3e`: Claude 25/30, GPT-5 mini 19/30 with tools, 1/10 each without).

Run it in a Databricks notebook from the workspace Git folder (the docstring of
`run_round5.py` has the three lines). Results go to the same runs table as round 4 with
`question_set` `i5` and a run id starting `r5-`.
