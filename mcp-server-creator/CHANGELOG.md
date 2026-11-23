# Changelog

MCP A Creator follows semantic versioning. Python packages use the PEP 440 form
(`1.0.0rc1`); the git tag and `server.json` use the semver form (`v1.0.0-rc1`).
Finding numbers refer to [FINDINGS.md](../docs/submission/FINDINGS.md).

## Unreleased (on `main` after the 1.0.0rc3 tag)

Installing from the tag `v1.0.0-rc3` gives 1.0.0rc3 as released. These changes
are on `main` and in the deployed app, and go into the next tag.

- "How many distinct recipients won awards?": a distinct count whose noun is
  followed by a verb and then the row's own noun is read as a distinct count,
  and the review agrees. Before, the later row noun turned it into a row count.
- A fifth worked example on the server's landing page and in
  `creator_list_library`: a weapon system cost analyst on a USAspending
  contract transactions table.
- `serverInfo.version` is the Creator's release. Before, an MCP client saw
  FastMCP's version there.
- Generated files are piped to ruff as UTF-8, so the suite passes on Windows.
- Every `creator_` tool declares a return model (`output_models.py`), so its
  MCP listing carries an output schema. Inputs, results and error bodies are
  unchanged; `contract/` walks one design through all ten tools and fails if
  an answer does not fit.
- A new resource, `creator://schema/server-spec`, is the JSON Schema of a
  specification. `spec_json` stays a string so any model can pass it; a
  `spec_json` that does not validate now names this resource.
- `scripts/check.sh creator` also runs mypy (`mypy.ini` at the repository
  root) and holds unit-test coverage at 80% or more; bandit scans `src` in
  CI (`scripts/check.sh quality`).

## 1.0.0rc3 (2026-11-22)

The caller can now correct how a question was read, the designer reads four
more unseen schemas, and stdout is clean over stdio. `creator_design_tools`
gains one optional parameter, `readings`; every other tool and parameter is
unchanged.

### Added

- **Readings.** Each tool that answers a recorded question comes back from
  `creator_design_tools` with its `question` and its `reading` (shape,
  aggregation, measure, group_by, filters). A caller that reads the question
  differently sends `readings`, one flat string per question:
  `<question> => shape=ranking; aggregation=sum; measure=<column>;
  group_by=<column>`. Every column is checked against the profiled source (it
  must exist, must not be personal, and a sum needs a numeric measure); a
  reading that does not fit is reported in `design_notes` and the designer's
  own reading is kept. `creator_review_server` compares the corrected tool
  with the question's own words, so a wrong reading is caught whoever wrote
  it. The parameter is a list of strings, so the schema stays flat.
- **Date window lists.** "Which awards expire in the next 90 days?" and "Which
  investments are scheduled to complete in 2027?" get a paged list bounded on
  the date the question names; the caller works the window out from today, so
  it moves. Before, the first was refused with a note to write it by hand.
- A bound on a year column: "built before 1960" adds `year_built_from` and
  `year_built_before`.
- Every free-text argument of a generated tool has a length cap (256
  characters; 32 for a date or year bound), so an oversized value is refused
  by validation. `mcp-bakehouse-sales` picked this up with
  `mcp-a-creator-upgrade --write`: six tool modules changed, nothing else.

### Fixed

- Over stdio the server printed one audit line per call to stdout, which is
  the protocol channel, so a client logged a JSON parse error after every
  call. Audit lines now go to stderr over stdio and stay on stdout over HTTP.
- A column named `agency_name`, `recipient_name` or `program_title` can be
  grouped, counted and filtered, and a rule that withholds individuals hides
  such a column with the keys. Before, a name column was free text and "which agencies" got one
  total.
- A whole word beats a shared stem: "states" is `state_name`, not `status`.
- "Look up an award by its PIID", "Find a property by its unique ID" and "Get
  a bridge by structure number" are lookups, and "List excess properties in a
  given city" is a list with a status filter. Before, each was a ranking or
  had no tool.
- The question's own words choose the filters: "small businesses",
  "underutilized buildings" and "high risk" select the columns that hold
  those values.
- "How many high risk investments" on a table of investments counts rows, not
  distinct risk levels. "Operations and maintenance" finds `om_spending`.
  "Average daily traffic" is a column, not a daily trend. "Sub-agency" and
  "month over month" read as written.
- "What share of awards were not competed?" is a ranking by the column that
  splits the rows, which returns each group's share.
- Reported instead of answered wrongly: a ratio ("cost per square foot"), an
  amount that names no column when the table has several, a quarterly step,
  and the single oldest or newest record.
- The review no longer flags a correct tool for "average number of offers per
  NAICS code" or "top 10 recipients by total award value", accepts either of
  two columns that fit a phrase equally, and now flags a list mapped to a "how
  many" question, a figure mapped to a list question, a trend mapped to a
  ranking question, a measure another column fits better, and a keyed list
  question that no reader takes the key for.
- Tool names over the length limit end on a word.

### Measured

Two schemas no earlier test used (federal contract awards, federal real
property; 19 questions) were written first and run on 1.0.0rc2: 5 of 19 got
the right tool. After the fixes above that those two motivated, two more
schemas written at the same time and kept aside (IT investments, a bridge
inventory; 19 questions) were run once: 10 of 19 right, and the review caught
none of the nine misses. Each miss was then fixed.

A second pass over this change found seven faults in it before release: "sales
per employee" was refused as a ratio though the table has an employee column;
a window question on a snapshot source, which has no paging, became a ranking
by amount; a rule that withholds individuals left their name column
groupable; the row's own noun picked the date ("which sales are due" bounded
the sale date); a list reading named its key twice; and two notes said a
table had no numeric column when it had. Each is fixed with a test.

A fifth schema written after every fix (federal grants, 8 questions) was then
run once: 6 right, none wrong. The other two named no column ("most funding",
"award size"); one had no note saying so, which is fixed, and a reading
answers both.

All five sets are regression tests (`tests/test_question_readings.py`): 40
questions get the tool they ask for and 6 get a stated reason.

The held-out result is the honest one: rules read about half of the phrasing
they have not seen. That is why this release adds readings and tightens the
review, instead of only adding rules.

### Known limits

- A year bound uses the year column the question names, or the only one. The
  designer cannot tell which of two dates a verb such as "delivered" means.
- No generated pattern divides one column by another, steps by quarter, or
  returns the earliest or latest record per group. These are reported.
- Filters chosen from a question's words need the column's values, which a
  pasted schema does not carry. Profile the table live to get them.

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
