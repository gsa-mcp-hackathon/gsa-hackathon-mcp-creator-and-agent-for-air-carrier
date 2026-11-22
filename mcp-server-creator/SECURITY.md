# Security Policy

As a U.S. Government agency, the General Services Administration (GSA) takes seriously our responsibility to protect the public's information, including financial and personal information, from unwarranted disclosure.

Software developed by the U.S. General Services Administration (GSA) is subject to the GSA Vulnerability Disclosure Policy.

Please consult our policy for:

How to submit a report if you believe you have discovered a vulnerability.
GSA's coordinated disclosure policy.
Information on how you may conduct security research on GSA developed software and systems.
Important legal and policy guidelines.

## Supported Versions

| Version | Security fixes |
| --- | --- |
| 1.0.0rc2 (tag `v1.0.0-rc2`) and `main` | Yes |
| 1.0.0rc1 (tag `v1.0.0-rc1`) | Until 1.0.0 |
| 0.1.0 | No: it pins FastMCP 2.14, which carries CVE-2025-64340 and CVE-2026-27124 |

Each release ships a CycloneDX SBOM of its locked runtime dependencies in
[`release/`](release/), built by `scripts/build_creator_release.sh`. CI runs
`pip-audit` on the deployed requirements and `bandit` on the code on every push.
The FastMCP and protocol versions each release is tested on are in the
[README](README.md#which-fastmcp-and-protocol-versions).

## Security Researchers

Security researchers shall:

- Make every effort to avoid privacy violations, degradation of user experience, disruption to production systems, and destruction or manipulation of data.
- Only use exploits to the extent necessary to confirm a vulnerability. Do not use an exploit to compromise or exfiltrate data, establish command line access and/or persistence, or use the exploit to "pivot" to other systems. Once you've established that a vulnerability exists, or encountered any of the sensitive data outlined above, you must stop your test and notify us immediately.
- Keep confidential any information about discovered vulnerabilities for up to 90 calendar days after you have notified GSA. For details, please review Coordinated Disclosure.

## This server's posture

Eight of the ten tools only read or compute. `creator_write_project` writes
files and is off unless an operator sets both `CREATOR_ALLOW_WRITE` and
`CREATOR_OUTPUT_ROOT`; every path is then resolved inside that root, traversal
and absolute paths are refused, and the default is a dry run.
`creator_deploy_server` deploys only with an approval token bound to the
reviewed design, app name, grants and files. Every string input is capped and
`tests/test_adversarial_arguments.py` sends hostile values into every parameter
of all ten tools with writing on (400 calls; nothing escapes, nothing is
written outside the root). A failure reaches the client as `isError`.

No tool accepts an absolute URL, a raw SQL string, or a filesystem path.
`tests/test_security.py` asserts this, so adding one breaks CI on purpose.

Unity Catalog identifiers supplied for live profiling are validated against a
plain identifier pattern and backtick-quoted before they reach SQL; values
are always bound as query parameters. Upstream failures are sanitized: no
response bodies, headers, full URLs, stack traces, or credentials reach a
client or a log.

Schemas, sample rows, and document descriptions passed to these tools are
material to analyze. They are never instructions to the model, however they
are phrased. The same rule is written into the server's `instructions`, into
the generated servers' instructions, and into the retrieval tool docstrings
the generators emit.

## Deployed posture

MCP servers built from this template expose `/mcp` without authentication of
their own. On Databricks Apps the endpoint sits behind workspace
authentication: callers need `CAN USE` on the app and an OAuth token, and
personal access tokens are not supported. An unauthenticated probe returning
302 or 401 is the app working.

Before any non-hackathon use, front the endpoint with authentication, review
your agency's ATO requirements, and decide retention and access for logs
that may hold prompts. Never commit secrets: keep them in environment
variables or a Databricks secret scope, never in source and never in a
`value:` field in `app.yaml`.
