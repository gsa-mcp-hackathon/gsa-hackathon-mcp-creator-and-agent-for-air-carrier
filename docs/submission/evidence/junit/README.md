# JUnit XML from a clean-clone run

`JUNIT_DIR=out scripts/check.sh` on a fresh `git clone`, 2026-11-21, Python 3.13 under uv, all nine
projects passed. One file per pytest run. The One Hub's script suites (`test_agents`, `test_gate`,
`test_app` and the others) print their own summary and are not pytest, so they are not in these files.

| File | Tests | Failures | Errors | Skipped | Started (US Eastern) |
| --- | --- | --- | --- | --- | --- |
| [analyst-1.xml](analyst-1.xml) | 39 | 0 | 0 | 0 | 2026-11-21T13:40:36 |
| [bakehouse-1.xml](bakehouse-1.xml) | 21 | 0 | 0 | 0 | 2026-11-21T13:40:29 |
| [creator-1.xml](creator-1.xml) | 259 | 0 | 0 | 1 | 2026-11-21T13:39:46 |
| [docs-1.xml](docs-1.xml) | 42 | 0 | 0 | 0 | 2026-11-21T13:40:31 |
| [evidence-1.xml](evidence-1.xml) | 36 | 0 | 0 | 0 | 2026-11-21T13:41:24 |
| [mcp-local-1.xml](mcp-local-1.xml) | 23 | 0 | 0 | 0 | 2026-11-21T13:40:43 |
| [mcp-local-2.xml](mcp-local-2.xml) | 422 | 0 | 0 | 0 | 2026-11-21T13:40:47 |
| [one-hub-1.xml](one-hub-1.xml) | 301 | 0 | 0 | 5 | 2026-11-21T13:41:02 |
| [ops-1.xml](ops-1.xml) | 40 | 0 | 0 | 0 | 2026-11-21T13:40:22 |
| [probe-1.xml](probe-1.xml) | 10 | 0 | 0 | 0 | 2026-11-21T13:40:41 |
| **Total** | **1193** | 0 | 0 | 6 | |
