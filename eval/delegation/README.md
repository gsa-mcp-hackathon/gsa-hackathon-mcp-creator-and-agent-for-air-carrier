# Delegation evaluation: do real models pick the right tools?

All the Air Carrier tools are offered to a model at once, with no hint about which server
answers which question: 29 tools through round 2, 30 after the round 2 fixes (docs 11,
analyst 12, ops 7). A run passes when every grading pattern for the question matches the
model's final answer.

Every number below is re-derived from [`runs.csv`](runs.csv) by [`analyze.py`](analyze.py)
into [`RESULTS.md`](RESULTS.md), with 95% Wilson intervals. CI fails if they disagree.

## Results

| Question set | Tools | With tools (2 models x 3 repeats) | No tools |
| --- | --- | --- | --- |
| Round 1, strict held out (4 questions) | 29 | 20/24 = 83.3% (64.1 to 93.3) | 2/8 = 25.0% |
| Round 1, all 14 questions | 29 | 80/84 = 95.2% (88.4 to 98.1) | 2/28 = 7.1% |
| Round 2, 12 sealed questions, before the fixes | 29 | 31/72 = 43.1% (32.3 to 54.6) | 3/24 = 12.5% |
| Round 2 questions, re-run after the fixes (public by then) | 30 | 45/72 = 62.5% (51.0 to 72.8) | 3/24 = 12.5% |
| **Round 3, 12 new sealed questions, after the fixes** | 30 | **50/72 = 69.4% (58.0 to 78.9)** | 1/24 = 4.2% |

Round 3 by model: Claude Sonnet 4.5 28/36, GPT-5 mini 22/36.

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

## The seals

Rounds 2 and 3 were sealed: the questions, patterns and answer key went into one file
whose SHA-256 was committed before any model saw it. The file was published only after
its run.

| File | SHA-256 | Hash committed | First run | Published |
| --- | --- | --- | --- | --- |
| [`questions_h2.json`](questions_h2.json) | `4a742955ff78983dd4f1eebe267ff06d45fce1c566c4c6211ac3e42ae281eee0` | `fb08c46`, 2026-11-20 04:03 UTC | `rpt-cde6da6d`, 05:16 UTC | `6e6438e` |
| [`questions_h3.json`](questions_h3.json) | `0dc6bdf52665a101d79ebf85aba4126e95f7a3c246c17c3c601d9bcf04df5ec1` | `c36be35`, 19:24 UTC | `58dba7511ddc`, 20:03 UTC | `25b6797` |

The notebook refuses any question file whose hash is not in `SEALED_SHA256`, and before
calling a model it recomputes every SQL-backed answer from the warehouse (`verify_sql`
against `expect`) and stops on a mismatch. Check a file with
`sha256sum eval/delegation/questions_h3.json`.

Both sealed sets were written by the person who built the tools, and round 3 was written
after the round 2 fixes. A seal proves the questions did not change after the run; it does
not make the author independent. A set written by someone else would be a stronger test,
and the protocol takes one unchanged: seal it, add its hash to `SEALED_SHA256`, run.

## Files

| File | What it is |
| --- | --- |
| [`questions.csv`](questions.csv) | Round 1: 9 development questions (`dev`) and 5 held out (`fresh`) |
| [`questions_h2.json`](questions_h2.json), [`questions_h3.json`](questions_h3.json) | Rounds 2 and 3: questions, patterns, answer keys, SQL checks |
| [`runs.csv`](runs.csv) | Every logged run, exported from `users.xiaobing_shang1_civ.aircarrier_delegation_eval_runs`, without the trace and answer columns |
| [`hand_grades.csv`](hand_grades.csv) | Answers read by hand where the grader was wrong, with the reason |
| [`analyze.py`](analyze.py), [`RESULTS.md`](RESULTS.md) | The script and its generated output |

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
- **Limits:** grading is regex over the final answer; read the misses before quoting a rate.
  Answer quality beyond the expected value is not scored.

## Reproduce

```bash
python3 eval/delegation/analyze.py            # print the tables from runs.csv
python3 eval/delegation/analyze.py --write    # regenerate RESULTS.md
```

New runs: upload the sealed files to `/Volumes/users/xiaobing_shang1_civ/aircarrier_artifacts/`,
open the notebook from the Git folder, and run all cells. It appends to the Delta table.
Export the new rows to `runs.csv` (same columns) and run `analyze.py --write`.
