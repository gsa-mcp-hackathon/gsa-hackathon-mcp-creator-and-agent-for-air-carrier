# Security Policy

As a U.S. Government agency, the General Services Administration (GSA) takes seriously our responsibility to protect the public's information, including financial and personal information, from unwarranted disclosure.

Software developed for the GSA MCP hackathon from the GSA template is subject to the [GSA Vulnerability Disclosure Policy](https://www.gsa.gov/vulnerability-disclosure-policy). Consult it for how to report a vulnerability, GSA's coordinated disclosure policy, and the legal and policy guidelines for security research.

This repository is a hackathon prototype. It uses publicly released data only and is not an authorized production system. To report a problem with this repository, open an issue on GitHub.

## Supported versions

| Branch | Supported |
| --- | --- |
| main | Yes |
| other | No |

## Posture across the repository

Each server's own `SECURITY.md` gives its detail:
[mcp-server-creator](mcp-server-creator/SECURITY.md),
[mcp-aircarrier-ops](mcp-servers/mcp-aircarrier-ops/SECURITY.md) and
[mcp-bakehouse-sales](mcp-servers/mcp-bakehouse-sales/SECURITY.md). The controls they share:

| Risk | Control | Where it is tested |
| --- | --- | --- |
| SQL injection | Identifiers are allow-listed and backtick-quoted; values are bound as parameters. No tool accepts a raw SQL string | Each server's `tests/test_security.py`; `mcp-servers/test_adversarial_arguments.py` sends bad arguments to every Air Carrier tool |
| Code injection into generated projects | Free text is made inert before it enters a generated literal, docstring, comment or constant | `mcp-server-creator/tests/test_injection_safety.py` compiles every generated file with warnings as errors |
| Path traversal | Volume and file reads are confined to configured roots; absolute paths and `..` are refused | Creator and docs server tests |
| Unwanted writes | The Air Carrier servers are read-only except one gated label write. Creator writes are dry runs by default, and a deploy needs an approval bound to the exact project files | Analyst server tests; `mcp-server-creator/tests/test_workspace_deploy.py` |
| Identity | Databricks Apps sign-in on every request. The docs, analyst and ops servers read as each app's own service principal, with grants on its own tables. MCP A Creator profiles tables, and the front center records decisions, under the signed-in user's own token | Probe and live identity tests |
| Internal detail in errors | An unexpected exception reaches a client by tool name and at most its error type. Its text can hold a path, a table name or a statement, so it stays in the server log. This holds on the five deployed servers and in every server the Creator generates | Docs and analyst server tests; `mcp-servers/test_error_contract.py`; `the-one-hub/ops-center/checks/test_mcp_server.py` and `checks/test_capture_ask.py` |
| Prompt injection | Retrieved text is data, never instructions, stated in every server's instructions | Golden-set items q16 and q17 in `mcp-servers/mcp-aircarrier-ops/eval/` |
| Secrets | No credentials in source; only `.env.example` files are committed | Repository review; `.gitignore` |

## Deployed posture

On Databricks Apps every `/mcp` endpoint sits behind workspace authentication: a caller needs `CAN USE` on the app and an OAuth token. An unauthenticated probe returning 302 or 401 is the app working. Before any use beyond the hackathon, review your agency's ATO requirements and decide retention and access for logs that may hold prompts.
