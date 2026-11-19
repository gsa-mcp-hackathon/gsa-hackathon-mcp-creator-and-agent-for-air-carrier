# Evaluation

The measure of this server is not how many tools it has. It is whether a model
holding only these tool names, schemas, and docstrings can answer a question
A cost analyst reconciling the CVN-79 (USS John F. Kennedy) program cost across budget exhibits and contract obligation records actually asks.

## The five things this suite insists on

1. **An answer key computed independently** — `answer_key.py`. An answer key
   built by calling this server's own tools proves only that the server
   equals itself.
2. **A no-tool baseline** — `run_experiment.py --no-tools`. The gap between
   baseline and tooled accuracy is the server's contribution.
3. **Decoys** — questions that look answerable and must come back empty.
4. **No-action cases** — questions whose correct answer is "nothing to
   report".
5. **An injection case** — text planted in returned content telling the agent
   to do something else. The agent must report it, not obey it.

## Setup

```bash
uv sync --group dev
cp eval/.env.example eval/.env    # then fill it in
```

`AGENT_MODEL` and `JUDGE_MODEL` are deliberately separate. Judging with a
different, usually stronger model reduces self-preference bias and lets you
hold the judge fixed while you iterate on the agent.

## Run it

```bash
cd eval/phoenix

uv run arize-phoenix serve                                  # UI on :6006

uv run create_dataset.py --dataset-name mcp-eval-0 --dry-run
uv run create_dataset.py --dataset-name mcp-eval-0

uv run run_experiment.py --dataset-name mcp-eval-0 --no-tools
uv run run_experiment.py --dataset-name mcp-eval-0
uv run run_experiment.py --dataset-name mcp-eval-0 \
    --system-prompt-version v2
```

## Fill in the answers first

`datasets/mcp-eval-0/evaluation.xml` ships with 17
questions. The ones marked `TODO` need a real answer before a correctness
score means anything:

1. Implement the matching function in `answer_key.py` with a query you wrote
   from scratch.
2. Run it, and paste the result into the `responses` column of
   `datasets/mcp-eval-0/examples/mcp-eval-0.csv`.
3. Hand-check at least ten records and turn those into unit tests in
   `tests/`.

## Reading the results

| Failure | Where the fix belongs |
|---|---|
| Wrong tool chosen | Tool name or description is ambiguous |
| Right tool, wrong arguments | Parameter description, or a missing enum |
| Right data, wrong conclusion | Return shape, or a missing field like `total` |
| Gave up after an error | The error had no actionable hint |
| Invented a value | A resolver tool is missing |
| Answered an out-of-scope question | Server instructions and docstring scope |
| Obeyed planted text | Server instructions and the retrieval docstring |

Fix the server, not the question, unless the question was genuinely unfair.
Record accuracy before and after each change; that table is the most
persuasive artifact this project produces.

## Reporting

State the question count, repeats, both models, the baseline, and the tooled
accuracy with both numbers visible. Name the cases that still fail and why.
A server at 85 percent with a named failure mode is more credible than one
claiming 100 percent.

Target for this server: 85 percent correct with the server attached,
with every no-action and injection case passing.
