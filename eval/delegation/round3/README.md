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
warehouse before calling a model; and the file is committed here after the run. It was
published with the results, after run `rpt-5153ac3f`.

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

## Result (2026-11-20)

Run `rpt-5153ac3f` (and the instructions ablation `58dba7511ddc`), tool catalog
`7e0d0a2a69214945`, 30 tools, both models, three repeats and one no-tool baseline.

**50 of 72 with the tools (69.4%, CI 58.0 to 78.9), 1 of 24 without (4.2%).** Sonnet 4.5
28/36, GPT-5 mini 22/36. This is the official score.

| Question | With tools | Notes |
| --- | --- | --- |
| G01, G02, G03, G05, G06, G10, G11 | 6/6 each | Both prime contracts, sorting by amount, P-5c shares, the decoy, the MSAR |
| G08 announced mods | 4/6 | GPT-5 mini summed the obligations instead of reading variance E-13 in two runs |
| G12 EASR share | 3/6 | GPT-5 mini did not search the knowledge graph in two runs; one gave 110.075 without saying the contract is multi-platform |
| G09 life-cycle savings | 1/6 | $5B is only in variance E-6; GPT-5 mini stopped at the $4B in CRS, two Sonnet runs ended without an answer |
| G04 deobligations | 0/6 | No tool counts by sign; Sonnet counted a page by eye (71, 73 against 68), GPT-5 mini ended without an answer |
| G07 PB2026 estimate | 0/6 | **Answer-key error.** The key used 13,196 from the estimate history. The PB 2026 P-5c prints 13,195.970, and 5 of 6 answers gave exactly that |

The key error is the author's. The official score keeps it as graded. Read by hand, with
G07 corrected, the score is 55/72 (76.4%); the per-answer verdicts are in
[`../hand_grades.csv`](../hand_grades.csv), and `analyze.py` prints them under the
official table.


## Run it

1. Upload `questions_h3.json` to
   `/Volumes/users/xiaobing_shang1_civ/aircarrier_artifacts/`.
2. In `mcp-servers/Air Carrier Delegation Eval.py`, keep both files in `QUESTION_FILES`
   to run the round 2 re-run and round 3 together, and run every cell.
3. Export the new rows to `eval/delegation/runs.csv`, commit `questions_h3.json`
   beside this file, and run `python3 eval/delegation/analyze.py --write`.
