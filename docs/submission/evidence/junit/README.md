# JUnit XML from a full run

`JUNIT_DIR=out scripts/check.sh` on 2026-11-22 over the tree of this commit, each project in its own
uv environment, all nine projects passed. One file per pytest run. The One Hub's script suites
(`test_agents`, `test_gate`, `test_app` and the others) print their own summary and are not
pytest, so they are not in these files. The pytest total here counts the 59 evaluation tests in
`evidence-1.xml`; the headline 1,770 leaves them out.

| File | Tests | Failures | Errors | Skipped | Started (US Eastern) |
| --- | --- | --- | --- | --- | --- |
| [analyst-1.xml](analyst-1.xml) | 39 | 0 | 0 | 0 | 2026-11-22T16:47:02 |
| [bakehouse-1.xml](bakehouse-1.xml) | 21 | 0 | 0 | 0 | 2026-11-22T16:46:57 |
| [creator-1.xml](creator-1.xml) | 805 | 0 | 0 | 0 | 2026-11-22T16:45:58 |
| [docs-1.xml](docs-1.xml) | 55 | 0 | 0 | 0 | 2026-11-22T16:46:58 |
| [evidence-1.xml](evidence-1.xml) | 59 | 0 | 0 | 0 | 2026-11-22T16:47:40 |
| [mcp-local-1.xml](mcp-local-1.xml) | 23 | 0 | 0 | 0 | 2026-11-22T16:47:07 |
| [mcp-local-2.xml](mcp-local-2.xml) | 23 | 0 | 0 | 0 | 2026-11-22T16:47:08 |
| [mcp-local-3.xml](mcp-local-3.xml) | 9 | 0 | 0 | 0 | 2026-11-22T16:47:13 |
| [mcp-local-4.xml](mcp-local-4.xml) | 423 | 0 | 0 | 0 | 2026-11-22T16:47:16 |
| [one-hub-1.xml](one-hub-1.xml) | 325 | 0 | 0 | 5 | 2026-11-22T16:47:23 |
| [ops-1.xml](ops-1.xml) | 40 | 0 | 0 | 0 | 2026-11-22T16:46:51 |
| [probe-1.xml](probe-1.xml) | 12 | 0 | 0 | 0 | 2026-11-22T16:47:06 |
| **Total** | **1834** | 0 | 0 | 5 | |
