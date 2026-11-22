# Delegation evaluation: do real models pick the right tools?

All the Air Carrier tools are offered to a model at once, with no hint about which server
answers which question: 29 tools through round 2, 30 after the round 2 fixes (docs 11,
analyst 12, ops 7). A run passes when every grading pattern for the question matches the
model's final answer (rounds 1-3), or when grader v2 finds every expected value in it
(round 4).

Rounds 1-3 are re-derived from [`runs.csv`](runs.csv) by [`analyze.py`](analyze.py) into
[`RESULTS.md`](RESULTS.md), with 95% Wilson intervals. Round 4 is re-derived from
[`round4/runs_r4.csv`](round4/runs_r4.csv) by [`round4/analyze_round4.py`](round4/analyze_round4.py)
into [`round4/RESULTS.md`](round4/RESULTS.md), with question-bootstrap intervals. CI fails
if either page disagrees with its runs.

## Results

| Question set | Tools | With tools (2 models x 3 repeats) | No tools |
| --- | --- | --- | --- |
| Round 1, strict held out (4 questions) | 29 | 20/24 = 83.3% (64.1 to 93.3) | 2/8 = 25.0% |
| Round 1, all 14 questions | 29 | 80/84 = 95.2% (88.4 to 98.1) | 2/28 = 7.1% |
| Round 2, 12 sealed questions, before the fixes | 29 | 31/72 = 43.1% (32.3 to 54.6) | 3/24 = 12.5% |
| Round 2 questions, re-run after the fixes (public by then) | 30 | 45/72 = 62.5% (51.0 to 72.8) | 3/24 = 12.5% |
| **Round 3, 12 new sealed questions, after the fixes** | 30 | **50/72 = 69.4% (58.0 to 78.9)** | 1/24 = 4.2% |

Round 3 by model: Claude Sonnet 4.5 28/36, GPT-5 mini 22/36.

**Round 4** (run `r4-4bb6a2a6`, 30 tools, catalog `7e0d0a2a69214945`) is larger, graded
differently and reported per model. Its intervals resample the 69 questions, because the
three repeats of one question are not independent; Wilson over runs would be narrower.

| Round 4, 69 sealed questions | With tools (3 repeats) | No tools |
| --- | --- | --- |
| Claude Sonnet 4.5, generated (45) | 116/135 = 85.9% (76.3 to 94.1) | 6/45 |
| Claude Sonnet 4.5, reviewed (24) | 67/72 = 93.1% (83.3 to 100.0) | 4/24 |
| **Claude Sonnet 4.5, all 69** | **183/207 = 88.4% (81.2 to 94.7)** | 10/69 = 14.5% |
| GPT-5 mini, generated (45) | 109/135 = 80.7% (69.6 to 89.6) | 1/45 |
| GPT-5 mini, reviewed (24) | 54/72 = 75.0% (61.1 to 87.5) | 0/24 |
| **GPT-5 mini, all 69** | **163/207 = 78.7% (70.0 to 86.5)** | 1/69 = 1.4% |

Claude minus GPT-5 mini: +9.7 points (+1.4 to +17.9, paired over the same questions).
Round 4 is not a point-for-point comparison with round 3: the questions, the mix (more
single-figure lookups) and the grader all differ. Category, cut-off, cost and per-question
tables: [`round4/RESULTS.md`](round4/RESULTS.md).

**Grading defects stay in these scores.** Three were found by reading every miss. Each is
listed per answer in [`hand_grades.csv`](hand_grades.csv), and `analyze.py` prints the hand
reading under the official table, labelled:

| Question | Defect | Answers affected |
| --- | --- | --- |
| G07 | Answer-key error by the author: the key used 13,196 (rounded, from the estimate history); the PB 2026 P-5c prints 13,195.970 | 5 of 6 gave 13,195.970 |
| H06 | The pattern `63(\.1)?\s?%` cannot match 63.11%, the share the server computes since the fixes | 6 of 6 gave 8,463.156 and 63.11% |
| H10 | The decoy pattern does not accept "cannot find" | 4 of 6 refused and gave no figure |

Read by hand, round 3 and the round 2 re-run are each 55/72 (76.4%).

## What the misses showed, and what changed

**Round 1.** All four tool-mode misses were F4, a question about the PB 2024 book: file
names say `PB2024`, questions say "the PB 2024 book", and no tool joined them. F1 exposed a
missing fiscal-year filter, fixed during round 1 and excluded from the strict row.

**Round 2, before the fixes (catalog `1143a3c17536b7bd`).** The 41 misses:

| Cause | Questions | Misses | Fix |
| --- | --- | --- | --- |
| No tool read obligations on the DD&C contract N00024-15-C-2114 | H02, H04, H09 | 17 | `carrier_search_obligations` takes a required `contract` and reads either prime contract |
| Obligations came back in date order only | H03 | 5 | `order`: `largest_first` or `smallest_first`, sorted in SQL on the decimal amount |
| The FPDS-NG figure lives only in the variance register, which no tool searched | H08 | 6 | New tool `carrier_search_variances` over E-1 to E-17 |
| P-5c cells carried no hull, so models read the CVN-80 column; one share was computed by hand as 63.09% | H05, H06 | 7 | `docs_get_table` labels each P-5c cell with ship fiscal year, hull and share of the Total Ship Estimate |
| Grader rejected "cannot find" | H10 | 5 | None to the score |
| Incomplete answer | H07 | 1 | None |

The first F7 fix also failed (F4: 0 of 6). The budget-cycle reader needed a separator before
`PB`; the real names (`SCN_BookPB2024.pdf`, `SCN_Bookpb2006.pdf`) have none, and the tests
had used invented names. The reader now matches the real names, falls back to the most
frequent `PB 20xx` page header, and the tests use the real names.

**After the fixes (catalog `7e0d0a2a69214945`).** H02, H03 and H05 went to 6/6, H08 to 3/6,
F4 to 4/6, and round 3's questions on both contracts, sorting by amount and P-5c shares
(G01, G02, G03, G05, G06) are 6/6. The real misses that remain:

| Question | With tools | Cause |
| --- | --- | --- |
| G04, count of deobligations on 2116 | 0/6 | No tool counts by sign. Sonnet counted a page by eye (71 or 73 against 68); GPT-5 mini ran out of turns |
| H04, P00154 is Nimitz work | 0/6 | The finding is in the One Hub's exhibit seed and the Ring 0 dossier, which none of the 30 tools read |
| G09, two life-cycle savings figures | 1/6 | $5B is only in variance E-6; GPT-5 mini stopped at $4B from CRS, two Sonnet runs ran out of turns |
| G12, a multi-platform contract | 3/6 | GPT-5 mini did not search the knowledge graph in two runs |
| H09, which award figure to use | 1/6 | Five runs named the transaction sum without stating its value |
| G08, announced modifications | 4/6 | GPT-5 mini summed obligations instead of reading variance E-13 in two runs |

**Round 4 (catalog `7e0d0a2a69214945`, no tool changed since round 3).** The misses, from
[`round4/RESULTS.md`](round4/RESULTS.md):

| Area | Claude Sonnet 4.5 | GPT-5 mini | What the runs show |
| --- | --- | --- | --- |
| P-5c figures (13 questions) | 28/39 | 26/39 | Four questions come from older books that print in thousands (R4-26, -27, -31, -35). Claude ran out of its 8 turns on 11 of their 12 runs. In several GPT-5 mini misses it said the book was not loaded (R4-26, R4-27, R4-30, R4-31, R4-35), though other runs read the PB 2015 and PB 2020 books; two R4-26 runs gave the BASIC CONST/CONVERSION figure 3,642,159 from PB 2015 p.60 instead of the key's |
| Non-existent modifications (4) | 6/12 | 11/12 | Claude ran out of turns on three runs; in three more it reported a similarly numbered modification instead (A00172 for P00172, A00179 for P00179, or P00179 on the other contract) |
| Premise traps (10) | 30/30 | 21/30 | GPT-5 mini: U18 (an overhaul of a ship not yet delivered) 0/3, R4-43 0/3, U19 2/3, R4-40 2/3, R4-45 2/3. In R4-43 it said it found no matching records (2 runs) or that the tool could not search that contract (1 run), in words the key does not accept |
| Multi-source and hard sums (6) | 18/18 | 10/18 | GPT-5 mini read the FY 2020 column for U21 (1 run), missed U22 twice (one run added the six lines to 1,987.300 instead of 2,087.300), and failed a check on U11 (2 runs) and U12 (3 runs); the failed checks are in `round4/RESULTS.md` |
| Obligations (20) | 58/60 | 53/60 | GPT-5 mini missed R4-12 in 3 runs (at least two counted 8 deobligations where there are 9), mis-totalled R4-11 once ($11,879 against $12,879) and missed R4-14 in 3 runs (answers seen give a count of 7 or a total of -$5,612,063). Claude counted R4-14 right but totalled it $11,000 short (2 runs) |
| Judgment (4) | 9/12 | 9/12 | Claude said U15's three figures are one cap adjusted over time, not two caps (3 runs) |

The causes above come from reading the official run's answers of the misses; they are not
yet sorted per answer into tool, grader, model and key error as in `hand_grades.csv`.

**One grading defect found, kept in the score.** GPT-5 mini writes a non-breaking hyphen
(U+2011) in 121 of its 275 round 4 answers (Claude in 1), as in `CVN‑79` and `as‑of`. The
key patterns expect an ASCII hyphen. Re-grading every failed answer with hyphens
normalised turns exactly two into passes: GPT-5 mini R4-40 rep 1 and U17 rep 2. With
hyphens normalised, GPT-5 mini would be 165/207 with tools, against the reported 163/207;
no other miss has been re-read by hand yet. Grader v2
should normalise hyphens before round 5.

## The seals

Rounds 2, 3 and 4 were sealed: the questions, patterns and answer key went into one file
whose SHA-256 was committed before any model saw it. The file was published only after
its run.

| File | SHA-256 | Hash committed | First run | Published |
| --- | --- | --- | --- | --- |
| [`questions_h2.json`](questions_h2.json) | `4a742955ff78983dd4f1eebe267ff06d45fce1c566c4c6211ac3e42ae281eee0` | `fb08c46`, 2026-11-20 04:03 UTC | `rpt-cde6da6d`, 05:16 UTC | `6e6438e` |
| [`questions_h3.json`](questions_h3.json) | `0dc6bdf52665a101d79ebf85aba4126e95f7a3c246c17c3c601d9bcf04df5ec1` | `c36be35`, 19:24 UTC | `58dba7511ddc`, 20:03 UTC | `25b6797` |
| [`round4/questions_h4.json`](round4/questions_h4.json) | `f806640cb94139be5928a0be0a63096ba74f17cef9b8396b793a7534cdebf5a8` | `f4fb7c1`, 2026-11-21 04:49 UTC | `r4smoke-183e02` (smoke, 3 questions), 04:55 UTC; `r4-4bb6a2a6`, 05:59 UTC | `449f73b` |

The notebook refuses any question file whose hash is not in `SEALED_SHA256`, and before
calling a model it recomputes every SQL-backed answer from the warehouse (`verify_sql`
against `expect`) and stops on a mismatch. Check a file with
`sha256sum eval/delegation/questions_h3.json`. Round 4's runner
([`round4/run_round4.py`](round4/run_round4.py)) refuses a file whose hash differs from the
one in [`round4/SEAL.md`](round4/SEAL.md); its keys were checked a second way before
sealing (see SEAL.md), and an unsaved timing run on GPT-5 mini preceded the official run.

The round 2 and 3 sets were written by the person who built the tools, and round 3 was written
after the round 2 fixes. Round 4's 45 generated questions draw their subjects at random
from the source tables with templates Genie Code wrote; its 24 reviewed questions were
drafted by Genie Code and reviewed and edited by the project owner. A seal proves the questions did not change after the run; it does
not make the author independent. A set written by someone else would be a stronger test,
and the protocol takes one unchanged: seal it, add its hash to `SEALED_SHA256`, run. Round 5 is
that test: ten questions written by an external evaluator who is not a member of the project
development team and took no part in building the MCP servers or preparing the model responses
([round5/](round5/README.md)).

## Files

| File | What it is |
| --- | --- |
| [`questions.csv`](questions.csv) | Round 1: 9 development questions (`dev`) and 5 held out (`fresh`) |
| [`questions_h2.json`](questions_h2.json), [`questions_h3.json`](questions_h3.json) | Rounds 2 and 3: questions, patterns, answer keys, SQL checks |
| [`runs.csv`](runs.csv) | Every logged run, exported from `users.xiaobing_shang1_civ.aircarrier_delegation_eval_runs`, without the trace and answer columns |
| [`hand_grades.csv`](hand_grades.csv) | Answers read by hand where the grader was wrong, with the reason |
| [`analyze.py`](analyze.py), [`RESULTS.md`](RESULTS.md) | The script and its generated output |
| [`round4/`](round4/SEAL.md) | Round 4: the seal record, `questions_h4.json`, the seeded generator, grader v2 and its tests, the reviewed questions' source files, the runner and its tests, `runs_r4.csv`, `analyze_round4.py` and `RESULTS.md` |

## Method

- **Harness:** the notebook [`mcp-servers/Air Carrier Delegation Eval.py`](../../mcp-servers/Air%20Carrier%20Delegation%20Eval.py).
  It loads the three servers in-process from its own folder, so a run measures the code in
  that folder, not the deployed apps. Every row carries the SHA-256 of the tool catalog it
  measured (`tool_catalog_sha`).
- **Models:** Databricks-served Claude Sonnet 4.5 and GPT-5 mini.
- **Modes:** `tools_rep1..3` (all tools, three independent repeats), `no_tools` (same
  question, no tools), and `instr` / `no_instr` (with and without each server's
  instructions in the system prompt).
- **Question design:** decoys whose right answer is that the figure does not exist,
  exclusion traps (contract numbers that belong to other hulls), a contamination case, and
  figures that only a governed source can settle.
- **Round 4 harness:** [`round4/run_round4.py`](round4/run_round4.py) keeps the notebook's
  agent loop, prompt and limits (8 tool turns, 60,000 characters per tool result), runs
  calls in parallel, checkpoints every finished row and resumes by run id, and retries
  transient serving errors (none were needed). It has no `instr` mode.
- **Limits:** rounds 1-3 grade by regex over the final answer; round 4's grader v2
  ([`round4/grade.py`](round4/grade.py)) parses numbers with units, dates and refusals.
  Read the misses before quoting a rate. Answer quality beyond the expected value is not scored.

## Reproduce

```bash
python3 eval/delegation/analyze.py            # print the tables from runs.csv
python3 eval/delegation/analyze.py --write    # regenerate RESULTS.md
```

New runs: upload the sealed files to `/Volumes/users/xiaobing_shang1_civ/aircarrier_artifacts/`,
open the notebook from the Git folder, and run all cells. It appends to the Delta table.
Export the new rows to `runs.csv` (same columns) and run `analyze.py --write`.

Round 4:

```bash
sha256sum eval/delegation/round4/questions_h4.json         # must equal SEAL.md
python3 eval/delegation/round4/analyze_round4.py            # print the tables from runs_r4.csv
python3 -m pytest -q eval/delegation/round4/test_grade.py eval/delegation/round4/test_runner.py
```
