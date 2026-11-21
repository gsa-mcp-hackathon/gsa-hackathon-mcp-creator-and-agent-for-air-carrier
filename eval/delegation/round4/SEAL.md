# Round 4 seal

The round 4 question file was written and hashed on 2026-11-21, before any model saw it.
This commit records the hash. The file itself is published after its run, as in rounds 2 and 3.

| File | SHA-256 | Questions | Written against |
| --- | --- | --- | --- |
| `questions_h4.json` | `f806640cb94139be5928a0be0a63096ba74f17cef9b8396b793a7534cdebf5a8` | 69 | tool catalog at `264d9d7` |

Check it with `sha256sum questions_h4.json`. Until it is published it is held at
`/Volumes/users/xiaobing_shang1_civ/aircarrier_artifacts/questions_h4.json`.

## What is in it

| Set | Questions | Who chose them |
| --- | --- | --- |
| generated | 45 | [`generate.py`](generate.py) with seed `20261121`: templates written by Genie Code, every subject drawn at random from the source tables. Subjects named in rounds 1-3 are excluded. |
| reviewed | 24 | Drafted by Genie Code from the source documents, then reviewed and edited by the project owner, who changed wording and two categories and kept every value. |

Neither set is independent of the tools: Genie Code has seen them. The generator removes
hand-picking of subjects; the review adds a second reader. A set written by someone who has
not used the tools would still be the stronger test.

Generated set, by template: obligations by fiscal year 6, one modification 6, largest action
in a fiscal year 4, deobligations 4, modifications that do not exist 4, P-5c printed line 10,
Total Ship Estimate change 3, premise traps 8.

## Checks run before sealing

* Every generated key passed a second, independent check (`key_checks` in the file); none was
  dropped. Obligation totals were re-derived with USAspending's own fiscal-year field; every
  P-5c value was found printed on its cited page.
* The generator gives the same output twice for the same seed.
* Every reviewed reference answer passes its own key, and 14 plausible wrong answers fail.
* Every generated key can be passed by an answer that states the key's values; every premise
  trap passes with the knowledge graph's own reason.

## Grader v2

[`grade.py`](grade.py) reads numbers with their units, dates in common formats and refusals,
and compares values at the precision the answer states. [`test_grade.py`](test_grade.py): 27
tests, including the three round 3 grading defects (G07, H06, H10).

Re-grading round 3's 144 saved answers: grader v2 agrees with the hand reading on 144, the
round 1-3 regex grader on 135. For that count, the documented G07 key error was applied to
all six modes; `hand_grades.csv` records it only for the three `tools_rep` modes, and on that
narrower reading grader v2 agrees on 140.
