# Subject-matter review of answer quality

The delegation rounds grade whether an answer carries the right figures. This review asks a
different question: would a federal financial management reviewer use the answer? The project
owner, a GS-15 DoD financial management portfolio manager (CDFM, DoD FM Level III), scored
ten round 4 answers with the servers and ten without, for the same questions.

Result: with the servers 54 of 60 (mean 5.4 of 6), without tools 16 of 60 (1.6); the reviewer
would rely on 9 of 10 answers with the servers and 1 of 10 without. Per question: [RESULTS.md](RESULTS.md).

## Method

1. `choose_questions.py` picked ten round 4 questions by a fixed seed, before any answer was
   read, across categories: two obligations, two exhibit, two document, one premise trap, one
   multi-source, one judgment, one regulation. Decoys are left out because they test refusals.
2. `export_answers.sql` pulled Claude Sonnet 4.5's answers to those ten from the round 4 runs
   table: repeat 1 with the servers, and the run without tools. Nothing was re-run. The export
   is [answers.tsv](answers.tsv).
3. `build_pack.py answers.tsv` lays the pairs out with empty score columns. The reviewer scored
   them on 2026-11-21 in a shared document, against the source documents, with the round 4
   answer key beside each question.
4. `score.py review_sheet_scored.csv` totals the scores and writes `RESULTS.md`.

## Rubric (0 to 2 each, 6 in all)

| Score | Correct | Cited | Usable |
| --- | --- | --- | --- |
| 0 | A figure or fact is wrong, or a false premise is accepted | No source a reader could check | Could not go into a brief or memo |
| 1 | Right in substance with a minor error or omission | A source named, but not the page, table or record | Needs rework before use |
| 2 | Every figure and fact matches the source | Document and page, table or record named | Could go into a brief as written |

Also recorded per answer: would the reviewer rely on it (Y/N).

## Blind second review (round 10 kit)

For raters who did not build the servers, and for the owner to re-score without labels:

1. `python build_blind_pack.py answers.tsv --seed "<a phrase only you know>"` writes
   `blind_sheet.csv`: the same ten pairs as answer A and answer B. The seed decides which side
   holds the answer with the servers; it is in neither the sheet nor the repository. Tool-call
   markup, "Let me search" narration and the tool-limit placeholder are removed from both sides.
2. Record the printed SHA-256 of the seed in `SEAL_BLIND.md` and commit it before any sheet goes
   out.
3. Each rater scores a copy, saved as `blind_sheet_<initials>.csv`, with the rubric below and the
   round 4 answer key, against the source documents. About an hour.
4. When every sheet is back: `python score_blind.py --seed "<seed>" --hash <recorded hash>
   blind_sheet_*.csv` checks the seed against the hash, unblinds, and writes `BLIND_RESULTS.md`
   with each rater's means per arm and quadratic-weighted Cohen's kappa for every pair of raters.

Blinding is partial: an answer that says it could not find a source reads differently from
one that cites a page, and that difference is part of what is being judged.

## Limits

- Not blind. The export showed which run had the servers, and answers without tools contain
  tool calls the model wrote out but never ran, so the two kinds are easy to tell apart.
- One reviewer, ten questions, and the reviewer is the project owner.
- One correction after scoring: U01 without tools was first entered as 2/2/2 and "rely: yes".
  That answer invents a GAO quote (July 2025, EMALS and the arresting gear, "page 16"); the
  source says March 2027 and an elevator and a landing subsystem (PDF p.145). The reviewer
  confirmed a mis-click and it was changed to 0/0/0 and "no". With the first entry the totals
  would be 54 and 22 of 60.
- The reviewer did not record minutes by hand, so this review measures answer quality, not
  time saved.
