# Known limitations, in full

The README keeps the five that matter most. This page keeps every limitation with its figures and
evidence, as of 2026-11-22.

- **The cost model is top-down until earned value data is loaded.** The cost-model
  specialist now runs a deterministic model (`ops/harness/cost_model.py`, `eac/v1`). With
  public data it computes an estimate-at-complete range from the program's own budget
  revisions since FY2013: for CVN-79, as of 2026-11-21 to the June 2028 work limit date,
  **$13,356M to $13,965M, mid $13,761M**, against the $13,409.970M PB2027 total. The whole
  range is above the $12,936M baseline in force. Five revisions make it a bracket, not a
  confidence interval. The earned value method (ACWP plus remaining work at CPI = 1, CPI and
  CPI x SPI) is built and tested, and runs once IPMDAR figures are supplied.
- **The Creator review reads words, not intent.** It now also catches a confident tool
  mapped to a different question (`tool_computes_its_question`): a sum where the question
  asks how many, an average where it asks for a ratio, a count that ignores the question's
  qualifier, a trend at the wrong time step. On the four README prompts that use sample
  tables it flags both such cases from the end-to-end run ("average fare per mile", "most
  negative reviews") and none of the correct tools. A question phrased so that none of these cues appear can still pass.
- **Injected instructions are now reported, by a fixed rule.** Every server adds a
  `source_notice` to any result holding text addressed to an AI assistant, and its
  instructions tell the model to report it; the q16 planted record comes back with the
  notice through the real ops server (`mcp-servers/test_source_notice.py`). The patterns
  match nothing in the 4.3 million characters of the corpus. Two limits: a phrasing outside
  the patterns is not flagged, and the delegation rounds have not been re-run to measure how
  often models pass the notice on.
- **Results depend on the model.** Round 4 with tools: Claude Sonnet 4.5 88.4%, GPT-5 mini
  78.7% (difference +9.7 points, CI +1.4 to +17.9). The gap is in premise traps (100% vs
  70%) and multi-source arithmetic (100% vs 58%); GPT-5 mini did better on decoys (92% vs
  50%). On an external evaluator's questions (round 5) the gap was wider: 83.3% vs
  63.3%, mostly multi-source and premise questions; both models got all 15 exhibit runs right.
  The gate, the tie-outs and the grounding checks are code and do not change with the
  model; the wording of an answer does.
- **Not yet built or measured, and stated as such.** The Creator has not been evaluated with a
  model driving its tools from a one-line intent, so there is no time-to-server figure yet
  (the bakehouse rebuild through its tools took 0.38 s of compute, not a person's time). The
  share of the ops server that is still unedited Creator output is not measured. The source
  notice is tested on the servers but not re-measured with models. Generated servers run as
  the app's own identity, so Unity Catalog row filters for the end user do not apply to them;
  each generated tool reads one source, with no joins; and deployed servers are not yet
  listed in a registry table.
- **Time saved is estimated, not measured.** From the scope of one CVN-79 pass (7,712
  tie-out checks, 1,875 contract actions, 17 variances, 259 collection requirements) the
  hand work is about **194 to 390 analyst hours, 5 to 10 weeks**, at stated minutes per item
  ([docs/TIME_ESTIMATE.md](TIME_ESTIMATE.md)). No analyst has been timed; the document
  says how to measure it.
- **3 budget-table checks still do not tie out, all within rounding.** The store measurement
  on 2026-11-21 over all 34 documents gave 7,703 of 7,712. Reading the nine failing pages
  found four causes: a number the PDF prints with a stray space ("5 .2", PB2006 p.167); a row
  whose wrapped label swallowed its $119.746M at the foot of a page (PB2022 p.376); pages
  never linked because the extractor split the same columns 26 and 21 ways (PB2022, PB2023);
  and rounding. It also found two defects nobody had seen: P-5 pages that open with a
  Resource Summary block had no unit, so their cost elements were never checked, and the
  joined-page retry could report a failure as passing under another row's figure. All
  fixed. Re-extracting the 22 SCN books with the docs server's own extractor:
  **7,690 of 7,693 checks pass**, and the 3 left (PB2008 p.122, PB2007 p.66) differ by $0.2M to $0.5M,
  inside the rounding bound of the printed figures; they are reported as
  `within_rounding_bound` and still count as failures. No check that passed before fails now
  ([evidence](submission/evidence/tieout_rerun_2026-11-21.json)). On the deployed
  store after the redeploy, all 34 PDFs: **7,743 of 7,746 pass**, the same 3 within rounding,
  nothing failing outside it ([evidence](submission/evidence/tieout_store_2026-11-22.json)).
- **The docs server's slow mode is gone.** It reloaded its 7,804-page corpus inside the
  request once the 30-minute cache expired (p50 12.6 s, max 20.2 s); it now refreshes in the
  background and loads at startup. Since that deploy: the probe, 24 of 24 known answers right
  at p50 1.18 s; a 234-call run on 2026-11-22 across a cache expiry, 233 right (one browser
  transport error), p50 1.18 s, p95 1.34 s, max 2.34 s at the reload
  ([evidence](submission/evidence/latency_2026-11-22.json)).
- **The One Hub server was deployed on 2026-11-21, so its probe history is short:** 23 of 23
  known answers right to 2026-11-22 04:25 UTC, p50 54 ms. Its
  HTTP form had refused every request behind the Apps proxy (421 Invalid Host header, the
  SDK's localhost guard); that is fixed and tested. It runs from `the-one-hub/ops-center`
  (`app.yaml`), and the probe's known answer is the held $13,529M baseline routed to human
  review. The shared workspace is capped at 100 apps, so it took the slot of the bakehouse
  demo, whose code and tests stay in the repository. Its 16 tools take 193 hostile
  arguments in its own suite: 131 refused, 62 answered, none leaked.
- **The Cost Limitation Baseline is under review** (E-17). $12,936M is the baseline the
  Secretary of the Navy notified to Congress in August 2023. It is the $11,398.0M statutory
  cap (10 U.S.C. 8692, FY2020 NDAA), plus the $1,300M the Navy added in August 2021 for
  contract overruns (GAO, quoted by CRS), plus $238M when post-shakedown availability work
  moved into construction in 2023 (derived as the difference; anchor chain in
  `app/data/anchor_chain.json`). The FY2027 MSAR (p. 8) says a
  December 2025 notification raised it to $13,529M. The hub keeps $12,936M in force until a
  person confirms the new figure under CAP-05, for two reasons: the figure comes from one
  MSAR sentence, not the notification, and $13,529M is also CVN-80's baseline since August
  2023, so a hull mix-up has to be ruled out. If confirmed, the $13,409.970M FY2027 budget
  is $119.03M under the baseline instead of $473.97M over.
- **Figures are the app's reading of the register, not a cleared position.** A cleared
  position is a figure the owning office (the program office, ASN(FM&C) or OUSD(C)) has
  approved for release as the Department's number. The app decides which of the four
  published figures to quote for which purpose, from the variance register (E-1, E-2,
  E-17). That is analysis to brief from, not the Navy's position. The front center says so
  where it shows a selection.
