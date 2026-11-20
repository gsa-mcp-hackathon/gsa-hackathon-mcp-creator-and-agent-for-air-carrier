# Delegation evaluation, round 3: a second sealed held-out set

Round 2's 12 questions became public when they ran, and the fixes that followed were
made with their misses in view. A re-run of them shows whether the fixes work. It
cannot show how the tools do on questions nobody tuned for. Round 3 is that test.

## The seal

The questions, the grading patterns and the answer key are in `questions_h3.json`. It
is **not** in this repository. Its SHA-256 is:

```
0dc6bdf52665a101d79ebf85aba4126e95f7a3c246c17c3c601d9bcf04df5ec1
```

The same four checks as round 2 apply ([`../round2/README.md`](../round2/README.md)):
this line predates every `h3` row in the runs table; the notebook refuses any file with
another hash (`SEALED_SHA256["h3"]`); it recomputes every SQL-backed answer from the
warehouse before calling a model; and the file is committed here after the run.

## What the 12 questions test

| Category | Count | What a pass means |
| --- | --- | --- |
| Obligations | 4 | A fiscal-year count and total and the largest action on the DD&C contract; the largest deobligation and the count of deobligations on Construction Preparation |
| Exhibit | 3 | A P-5c cost category, a share of the Total Ship Estimate, and the estimate printed in an earlier book |
| Variance | 2 | Two places where public sources disagree, with both figures |
| Documents | 1 | A rating printed in the MSAR |
| Decoy | 1 | The premise is false; the right answer says so |
| Exclusion | 1 | A multi-platform contract whose total is not CVN-79 cost |

Four of the questions touch the round 2 fixes (both prime contracts, ordering by
amount, the variance register, P-5c shares). The rest do not. The decoy pattern accepts
a plain "cannot find" as well as "not public", the lesson of round 2's H10.

## Who wrote it, and what that means

The questions were written on 2026-11-20 by the same author as the fixes, against the
tool catalog at commit `030ed21`, and no model has seen them. A seal proves the
questions did not change after the run. It does not make the author independent. A
held-out set written by someone who did not build the tools would be a stronger test,
and the protocol takes one without changes: seal it the same way and add its hash to
`SEALED_SHA256`.

## Run it

1. Upload `questions_h3.json` to
   `/Volumes/users/xiaobing_shang1_civ/aircarrier_artifacts/`.
2. In `mcp-servers/Air Carrier Delegation Eval.py`, keep both files in `QUESTION_FILES`
   to run the round 2 re-run and round 3 together, and run every cell.
3. Export the new rows to `eval/delegation/runs.csv`, commit `questions_h3.json`
   beside this file, and run `python3 eval/delegation/analyze.py --write`.
