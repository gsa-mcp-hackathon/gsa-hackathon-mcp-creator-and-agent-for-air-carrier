# Changelog

MCP A Creator follows semantic versioning. Python packages use the PEP 440 form
(`1.0.0rc1`); the git tag and `server.json` use the semver form (`v1.0.0-rc1`).
Finding numbers refer to [FINDINGS.md](../docs/submission/FINDINGS.md).

## 1.0.0rc2 (2026-11-22)

The designer now reads analyst phrasing it had not seen, and the review checks
each tool against the question's own words instead of re-running the designer.
Tools and parameters are unchanged; designs can change for questions that use
the phrasings below.

### Fixed

- "per state", "in each fiscal year" and "by X" group by X, including a period
  column such as year. Before, "per" and "each" gave one total.
- "how many disasters" and "distinct counties" count distinct values of the
  column; "how many projects" on a table of projects still counts rows.
- "show ... for a given X" builds a paged list of every record for one X. Before,
  it got a count, or no tool once the eight-tool limit cut the lookup.
- A specific word names the measure ("obligated amount" is
  federalShareObligated, not projectAmount).
- A place in the question ("in Texas") becomes a filter on the place column, and
  a grouped tool still gets two real filters.
- Plurals match columns ("cities" meets borrower_city).
- A generated lookup reads the column its parameter names; before, it read the
  first identifier profiled.

### Changed

- The review's tool_computes_its_question and every_question_has_a_tool read
  the question itself: its grouping, distinct count and list request, matched to
  columns by their own names. A tool the designer maps to a question still fails
  if it does not compute what the question asks. Before, the review re-ran the
  designer, so a designer misreading passed (finding N1, round 11).
- A tool that is the only answer to a recorded question is never cut by the
  eight-tool limit, and the dictionary tool stays; a design over the limit gets a
  note to split it.
- `count_distinct` is a new aggregation for rank, total and trend tools.

### Measured

Three schemas no earlier test used (FEMA public assistance, NOAA storm events,
SBA PPP loans), 25 questions. Before the fix, FEMA got 5 of 9 right. After it,
the storm events set got 6 of 8 and the PPP set 7 of 8 on their first runs; each
miss was fixed and all three sets are now regression tests
(`tests/test_unseen_phrasing.py`). A fourth unseen set would measure the rules
honestly again.

## 1.0.0rc1 (2026-11-21)

The first release candidate. The ten tools and their parameters are unchanged
from 0.1.0, so a client that worked with 0.1.0 works with this release, except
that a failed call now sets `isError` and an over-long argument is refused.

### Added

- Every generated project carries `.mcp-creator/`: the specification it came
  from, a lock with the Creator version and the SHA-256 of every generated file,
  the list of files the Creator owns, and `check_drift.py`. Generated CI runs the
  drift check, so a hand edit to a generated file is reported, never silently
  overwritten by the next generation.
- `scripts/check_compat.sh` and a CI job prove the Creator and a generated
  project on FastMCP 3.4.11 (protocol 2025-11-25) and 4.2.4 (protocol
  2026-07-28), and check that an MCP SDK 1.x client still reaches a 4.2 server
  (finding 28).
- A hostile-input sweep of all ten tools: 400 calls with writing switched on,
  nothing escaped, nothing written outside the project root, no workspace reached.
  The sweep writes `tests/adversarial_summary.json` (finding 20).
- `bandit` and `pip-audit` in the Creator's dev group and CI, and in the CI that
  every generated project ships with.
- `mcp-a-creator-upgrade` regenerates a generated project with the current
  release from its own `spec.json`: unedited files take the new templates,
  files in `owned.txt` are kept, and an undeclared edit over a changed
  template stops the upgrade before anything is written.
- `mcp-a-creator --help` and `--version`.

### Changed

- FastMCP 3.4 or later, which closes CVE-2025-64340 and CVE-2026-27124 in 2.14
  (finding 18). The package allows `fastmcp>=3.4,<5`; generated projects pin
  `>=3.4,<4` until 4.x is proven on Databricks Apps.
- A tool that returns an error body now sets `isError: true` on the MCP result,
  through `ErrorContractMiddleware`, in the Creator and in every generated project
  (finding 19).
- Every string parameter has a length cap, `design_id` and `repo_url` have
  patterns, and list parameters have size caps (finding 20).
- Generated output is byte-identical across processes, not only within one: the
  generated test file no longer lists tool names in hash-seed order (finding 25).

### Fixed

- "How many units" designed a count of records; it now sums the quantity measure
  the question names, and the review flags a count tool whose question names a
  measure.
- Ranking questions written with hyphens ("top-5") were missed, and a ranking
  question answered by an aggregate tool passed review (finding 24).
- Profile summaries and the closed-set check treated ID and measure columns as
  categories (finding 24).

### Known limits

- No model-in-the-loop evaluation of builds yet; the time from intent to server
  is measured only on the bakehouse rebuild (0.38 s through the tools).
- The designer reads questions by rules. A phrasing outside its cues can still
  get a wrong tool; the review catches a wrong grouping, distinct count or list
  request from the question's words, not every possible misreading.
- Generated servers run as the app's service principal. On-behalf-of the user,
  so that Unity Catalog row filters and column masks apply, is planned.
- A generated tool reads one table; declared joins are planned.

## 0.1.0

The version entered in the GSA MCP Server and AI Agent Government Hackathon:
ten tools across seven phases (profile, design, review, generate, write, deploy,
evaluate), eight bundled skills, deterministic generators, a review rubric, and a
deploy gate bound by hash to the reviewed files. Free text is inert in generated
code (finding 1).
