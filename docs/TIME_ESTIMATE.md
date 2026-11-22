# Analyst time for one CVN-79 reconciliation pass: an estimate from the scope of work

Written 2026-11-21. [Back to the README](../README.md#known-limitations).

**This is an estimate, not a measurement.** The counts below are what the One Hub works
through in one pass on CVN-79, each read from a file in this repository. The minutes per
item are assumptions about doing the same item by hand. They are stated so they can be
replaced by timed observation (method at the end). No analyst has been timed.

## The work in one pass

| Task done by hand today | Items in one pass | Count from | Minutes per item (low to high, assumed) | Analyst hours |
| --- | --- | --- | --- | --- |
| Find a budget exhibit table, key its cells, add the rows and compare with the printed subtotal or total | 7,733 tie-out checks on 34 PDFs, 7,804 pages (measured 2026-11-21) | docs server store, `docs_tieout_document` on every document ([docs README](../mcp-servers/mcp-aircarrier-docs/README.md)) | 0.5 to 1 (a table's columns are added together once its cells are keyed) | 64 to 129 |
| Pull a contract's actions from USAspending and FPDS, match each to the award summary, classify it and net the deobligations | 1,875 actions on N00024-09-C-2116 and N00024-15-C-2114 | `the-one-hub/ops-center/app/data/extracts/transactions.json` | 1 to 2 | 31 to 63 |
| Find where two sources disagree about the same figure, read both, and write down which is right for what | 17 variances (E-1 to E-17) | `app/data/variances.json` | 120 to 240 | 34 to 68 |
| Write the request for a missing record: what to ask for, from which office, and why | 259 collection requirements on 59 ranked open gaps | `app/data/extracts/requirements.json`, `app/data/gaps.json` | 15 to 30 | 65 to 130 |
| **Total for one hull** | | | | **194 to 390 hours, about 5 to 10 analyst-weeks** |

Weeks are 40 hours. The hub does the same pass in minutes of machine time; the probe's
median known-answer times are 0.9 s (ops), 4.5 s (analyst) and 1.2 s (docs, after the
2026-11-21 cache fix) per call
([EVALUATION.md](submission/EVALUATION.md) section 2.2).

## What the estimate leaves out

- **Review time stays.** Every figure the gate routes to `human_review`, every proposal and
  every variance still needs a person. The estimate counts the preparation the hub removes,
  not the decisions it routes to people.
- **Repeat passes cost less by hand.** An analyst who did last quarter's pass reuses most of
  it. The hub's advantage on a repeat is that it reruns everything, so a changed source shows
  up as a failed tie-out or a new variance instead of being missed.
- **Learning the program.** The first pass on a new hull by hand also needs the key set
  (appropriations, line items, contracts, CAGE). The hub needs the same key set once
  (Part G of the [Ring 0 dossier](../the-one-hub/ops-center/corpus/dossier/RING0_CVN79.md)),
  so that time is the same either way and is not counted.
- **The Ford class.** CVN-80 and CVN-81 have their own exhibits and contracts. The per-hull
  counts are of the same order, so the class is roughly three times one hull; that is a
  scaling assumption, not a count.

## How to measure it

1. Draw 20 items of each task at random, with a fixed seed, from the files above.
2. Time an analyst who has not seen the hub's output doing each item by hand, with the
   source documents open.
3. Time a second analyst checking the hub's output for the same items.
4. Report the difference per item with its spread, and scale by the counts above.

Until that is done, use the range above as the expected order of magnitude and say it is
an estimate.
