# Round 5 seal

Round 5 is ten questions written by an external evaluator who is not a member of the project
development team and took no part in building the MCP servers or preparing the model responses,
without an AI assistant, before seeing the tool catalog (per the project owner, 2026-11-22). The author's
file arrived on 2026-11-22 at 01:08 ET and was hashed on receipt, before any tool or model saw
it. The author did not email a hash first, so this receipt hash is the seal.

| File | SHA-256 | What it is |
| --- | --- | --- |
| `questions_i5.csv` | `320f74e59b9b323db0843d0035bd4029c655a5eadf41a03413bdace1b13e898a` | The author's questions, answers and sources, byte-identical to what arrived |
| `questions_i5.json` | `eef64b36072f71749184c179d5b1f9864f36de162e39ecf1b66cad793d231d53` | The same questions with grader keys added by `build_round5.py`; the runner refuses any other bytes |

Author: Mr. Alpha Brax, PEO Office, 2026-11-22 (given by the project owner; the sealed file's
provenance column carries no name, so it is recorded here rather than edited into the file).
The sealed `questions_i5.json` calls the author "an independent author on the project owner's
team": that means the owner's office, not the development team. The sealed bytes stay as they are.

The blind review sheet also carries the initials AB. The project owner confirmed on 2026-11-22
that the blind reviewer is a different person from the Round 5 author, also external to the
development team. An earlier version of this file said one person might have done both; that
was a caution written before the owner confirmed, and it is withdrawn.

## Checks before the run

* Each key was written from the author's answer. `test_round5.py`: all 10 reference answers
  pass their keys, and 10 plausible wrong answers fail (a neighbouring figure, a rounded one,
  an accepted false premise, a missing reason).
* The author's figures were checked against the documents the servers read: I01 $880.078M
  (PB2020 book), I02 $11,397.712M (PB2021 p.70), I03 $588.5M and $125.0M with their reasons
  (PB2023 p.79), I04 $42.3M realignment and the 24-month extension (PB2024 p.74), I05 the
  $260M increase and its four uses (PB2026 p.76), I08 $13,195.970M (PB2026 p.75), all
  word-for-word matches. I06 and I07 cite DoD contract announcements and I09 and I10 cite CRS
  RS20643; those were taken as written.
