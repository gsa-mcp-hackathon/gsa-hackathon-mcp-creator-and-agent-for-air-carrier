# Subject-matter review of answer quality

The delegation rounds grade whether an answer carries the right figures. This review asks a
different question: would a federal financial management reviewer use the answer? The project
owner, a GS-15 DoD financial management portfolio manager (CDFM, DoD FM Level III), scores
ten round 4 answers with the servers and ten without, blind to which is which.

## Method

1. `choose_questions.py` picks ten round 4 questions by a fixed seed, across categories:
   two obligations, two exhibit, two document, one premise trap, one multi-source, one judgment,
   one regulation. Decoys are left out because they test refusals.
2. `export_answers.sql` pulls Claude Sonnet 4.5's answers to those ten from the round 4 runs table:
   repeat 1 with the servers, and the run without tools. Nothing is re-run.
3. `build_pack.py answers.csv` writes `review_sheet.csv` with each pair labelled A and B. A seeded
   coin flip per question decides which label had the servers; it is not written down.
4. The reviewer scores each answer on the rubric below, with the source documents open, and
   estimates how many minutes the question would take by hand.
5. `score.py review_sheet_scored.csv` re-derives the labels and writes `RESULTS.md`.

## Rubric (0 to 2 each, 6 in all)

| Score | Correct | Cited | Usable |
| --- | --- | --- | --- |
| 0 | A figure or fact is wrong, or a false premise is accepted | No source a reader could check | Could not go into a brief or memo |
| 1 | Right in substance with a minor error or omission | A source named, but not the page, table or record | Needs rework before use |
| 2 | Every figure and fact matches the source | Document and page, table or record named | Could go into a brief as written |

Also recorded per answer: would you rely on it (Y/N). Per question: which answer is better
(A, B or tie), minutes the question would take by hand (an estimate), and a comment.

## Limits

One reviewer, ten questions, and the reviewer is the project owner. The labels are blind but
the reviewer knows the system, and answers with citations may read as tool answers. The
minutes by hand are the reviewer's estimate, not a timed measurement.
