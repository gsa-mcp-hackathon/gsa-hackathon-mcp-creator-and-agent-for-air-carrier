# JUnit XML from a full run

`JUNIT_DIR=out scripts/check.sh` on 2026-11-22 on a fresh clone of `main` at `91c0c73`, each project
in its own uv environment. All nine projects passed, and so did the `quality` target that the
evidence project ends with. One file per pytest run: for a server, `-1` is its unit tests and `-2`
its contract tests, which call every tool through the MCP client and check the answer against the
tool's output schema. The One Hub's script suites (`test_agents`, `test_gate`, `test_app` and the
others) print their own summary and are not pytest, so they are not in these files.

The pytest total here is 1,890. It counts the 5 skipped One Hub tests, the 59 evaluation tests in
`evidence-1.xml`, the 47 contract tests and the 9 grader self-tests in `quality-1.xml`; the
headline 1,770 leaves all of those out.

| File | Tests | Failures | Errors | Skipped | Started (US Eastern) |
| --- | --- | --- | --- | --- | --- |
| [analyst-1.xml](analyst-1.xml) | 39 | 0 | 0 | 0 | 2026-11-22T23:30:37 |
| [analyst-2.xml](analyst-2.xml) | 17 | 0 | 0 | 0 | 2026-11-22T23:30:49 |
| [bakehouse-1.xml](bakehouse-1.xml) | 21 | 0 | 0 | 0 | 2026-11-22T23:29:46 |
| [creator-1.xml](creator-1.xml) | 805 | 0 | 0 | 0 | 2026-11-22T23:27:37 |
| [creator-2.xml](creator-2.xml) | 4 | 0 | 0 | 0 | 2026-11-22T23:28:52 |
| [docs-1.xml](docs-1.xml) | 55 | 0 | 0 | 0 | 2026-11-22T23:30:06 |
| [docs-2.xml](docs-2.xml) | 15 | 0 | 0 | 0 | 2026-11-22T23:30:10 |
| [evidence-1.xml](evidence-1.xml) | 59 | 0 | 0 | 0 | 2026-11-22T23:32:26 |
| [mcp-local-1.xml](mcp-local-1.xml) | 23 | 0 | 0 | 0 | 2026-11-22T23:31:22 |
| [mcp-local-2.xml](mcp-local-2.xml) | 23 | 0 | 0 | 0 | 2026-11-22T23:31:23 |
| [mcp-local-3.xml](mcp-local-3.xml) | 9 | 0 | 0 | 0 | 2026-11-22T23:31:30 |
| [mcp-local-4.xml](mcp-local-4.xml) | 423 | 0 | 0 | 0 | 2026-11-22T23:31:34 |
| [one-hub-1.xml](one-hub-1.xml) | 325 | 0 | 0 | 5 | 2026-11-22T23:31:53 |
| [ops-1.xml](ops-1.xml) | 40 | 0 | 0 | 0 | 2026-11-22T23:29:18 |
| [ops-2.xml](ops-2.xml) | 11 | 0 | 0 | 0 | 2026-11-22T23:29:23 |
| [probe-1.xml](probe-1.xml) | 12 | 0 | 0 | 0 | 2026-11-22T23:31:12 |
| [quality-1.xml](quality-1.xml) | 9 | 0 | 0 | 0 | 2026-11-22T23:32:34 |
| **Total** | **1890** | 0 | 0 | 5 | |
