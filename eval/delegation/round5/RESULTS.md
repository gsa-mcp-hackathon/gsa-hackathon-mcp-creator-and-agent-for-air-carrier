# Round 5 results: questions from an independent author

Run `r5-0b1c2d3e`, 2026-11-22 06:34 UTC, in a Databricks notebook from the workspace Git folder
at `main` `9413d10`: the sealed `questions_i5.json` (hash checked by the runner), the round 4
runner, grader v2, 30 tools, catalog `5df1f1b1ecd75cb6`. 80 rows saved to the runs table. Every
row is in [runs_r5.csv](runs_r5.csv). Round 4's `save` labels the rows' question set
`h4-independent`; the run id is what marks them as round 5.

| Model | With tools (3 repeats) | 95% CI | Without tools |
| --- | --- | --- | --- |
| Claude Sonnet 4.5 | **25 of 30 (83.3%)** | 66.4 to 92.7 | 1 of 10 |
| GPT-5 mini | **19 of 30 (63.3%)**; 21 of 30 (70.0%) read by hand | 45.5 to 78.1 | 1 of 10 |

The score is reported as graded. Both no-tool passes are I10, a reasoning question that needs
no figure.

## Per question, runs passed with tools (of 3)

| Question | Category | Claude | GPT-5 mini |
| --- | --- | --- | --- |
| I01 PB2020 P-5c Plan Costs | exhibit | 3 | 3 |
| I02 PB2021 Total Ship Estimate | exhibit | 3 | 3 |
| I03 PB2023 changes and reasons | exhibit | 3 | 3 |
| I04 PB2024 realignment and extension | exhibit | 3 | 3 |
| I05 PB2026 $260M increase | exhibit | 3 | 3 |
| I06 March 2023 modification obligation | contract obligation | 1 | 0 |
| I07 June 2023 modifications | contract obligation | 0 | 0 |
| I08 PB2021 to PB2026 change vs CRS | multi-source | 3 | 1 |
| I09 block-buy premise | premise | 3 | 0 |
| I10 cost-cap premise | premise | 3 | 3 |

## Every miss, read by hand

| Model | Question | Runs | Cause |
| --- | --- | --- | --- |
| Claude | I06 | 2 | Stopped at the eight-turn tool limit with no answer |
| Claude | I07 | 3 | The servers hold FPDS/USAspending records, where these actions are modification PZ0002 dated June 26, 2023 with $0 obligated; the answers say so correctly. The two announced values ($274,041,192 and $119,213,388) come from the DoD contract announcement, which is not in the servers' data |
| GPT-5 mini | I06 rep 1, 3 | 2 | Right figure ($16,068,211, modification A00404) but named the funding office, not the appropriation |
| GPT-5 mini | I06 rep 2 | 1 | **Grader defect.** Right figure and appropriation ("017-1611, Shipbuilding & Conversion, Navy"); the key accepted only "and" |
| GPT-5 mini | I07 | 3 | Two runs stopped at the eight-turn limit; one listed nearby June 26 to 29 actions. Same data gap as Claude's |
| GPT-5 mini | I08 rep 1, 3 | 2 | Found both P-5c totals and the change; did not find the CRS figure, and one run gave an invented one |
| GPT-5 mini | I09 rep 1 | 1 | **Grader defect.** Rejected the premise ("did not attribute any... applying to CVN-80/CVN-81"); the answer used the non-breaking hyphen U+2011 and a slash, which the key did not match. eval/delegation/README.md had already noted that GPT-5 mini writes U+2011 |
| GPT-5 mini | I09 rep 2, 3 | 2 | Gave the $4 billion CVN-80/81 savings without saying CVN-79 was not part of the block buy |

## What it shows

On the five exhibit questions, an outside author's questions drew 30 of 30 runs right for both
models. The misses cluster where the author used a source the servers do not hold (DoD contract
announcements) or where a run hit the eight-turn limit. The grader defects are published, not
fixed after the fact: the keys stay as sealed, and the hand-read count is reported beside the
graded one.
