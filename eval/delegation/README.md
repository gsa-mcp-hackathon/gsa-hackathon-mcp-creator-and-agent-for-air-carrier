# Delegation evaluation: do real models pick the right tools?

All 29 One Hub tools (docs 11, analyst 12, ops 6) are offered to a model at once, with
no hint about which server answers which question. A run passes when the model's final
answer matches the expected answer for that question.

**Results with 95% confidence intervals: [RESULTS.md](RESULTS.md).** The headline:

| | With the 29 tools | No tools |
|---|---|---|
| Strict held-out (4 questions x 2 models x 3 repeats) | 20/24 = 83.3% (64.1 to 93.3) | 2/8 = 25.0% (7.1 to 59.1) |
| All 14 questions | 80/84 = 95.2% (88.4 to 98.1) | 2/28 = 7.1% (2.0 to 22.6) |

## Files

| File | What it is |
|---|---|
| [questions.csv](questions.csv) | The 14 questions: 9 development (`dev`), 5 held-out (`fresh`) |
| [runs.csv](runs.csv) | Every logged run (224 rows), exported from the Delta table `users.xiaobing_shang1_civ.aircarrier_delegation_eval_runs`; trace and answer columns omitted |
| [analyze.py](analyze.py) | Re-derives every number in RESULTS.md from runs.csv. CI fails if they disagree |
| [RESULTS.md](RESULTS.md) | Generated output |

The harness is the notebook [`mcp-servers/Air Carrier Delegation Eval.py`](../../mcp-servers/Air%20Carrier%20Delegation%20Eval.py).
Each row records the SHA-256 of the exact tool catalog it measured (`tool_catalog_sha`), so a
result is tied to one tool surface.

## Method

- **Models:** Databricks-served Claude Sonnet 4.5 and GPT-5 mini.
- **Modes:** `tools_rep1..3` (all 29 tools, three independent repeats), `no_tools` (same
  model, same question, no tools), and, in an earlier run, `instr` / `no_instr` (with and
  without each server's instructions in the system prompt).
- **Question design:** two decoys (Q8, F3) whose correct answer is that the data does not
  exist; an exclusion trap (Q5, a contract number that belongs to CVN 80/81); a premise
  that only a governed source can settle (Q1, the Cost Limitation Baseline in force).
- **Honest limits:** the held-out set is small (5 questions). F1 exposed a missing
  fiscal-year filter in the first run and the tool was fixed, so the strict row excludes
  it. All four remaining misses are one question (F4, a prior-year budget book), on both
  models. Answer quality beyond the expected value was not scored.

## Reproduce

```bash
python3 eval/delegation/analyze.py            # print the tables from runs.csv
python3 eval/delegation/analyze.py --write    # regenerate RESULTS.md
```

To produce new runs, open the notebook in the workspace, point it at the deployed MCP apps,
and run all cells; it appends to the Delta table above.
