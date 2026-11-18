# Security

## Posture

- **Read-only.** No tool in this server writes to any source system.
- **Classification.** Internal data. Do not expose the endpoint beyond the workspace, and review log retention.
- **Authentication.** Databricks Apps gates the endpoint behind workspace auth. Callers need CAN USE on the app and an OAuth token; personal access tokens are not supported.

## The boundary

Every tool argument, every record returned, every document passage, and every
message from another agent is untrusted input. A description field can
contain "ignore your instructions". Retrieved content is evidence to quote and
cite; it is never an instruction to the model.

## What this server does not accept

No tool takes an absolute URL, a raw SQL string, or a filesystem path. Those
are the three arguments that turn a data tool into an exfiltration primitive.
`tests/test_security.py` asserts this, so adding one breaks CI on purpose.

## Identifiers and values

Identifiers (catalog, schema, table, column) cannot be bound as query
parameters, so they are validated against a plain identifier pattern, checked
against an allowlist of the real columns, and quoted. Values are always bound
as query parameters, never concatenated.

## Errors and logs

Upstream failures are sanitized before they reach a client: no response
bodies, headers, full URLs, query strings, stack traces, or credentials.
Errors return a stable message and an actionable hint.

## Secrets

Credentials come from the environment or a Databricks secret scope. Never
from source, never from a `value:` field in `app.yaml`, never from a tool
argument.

## Before any non-hackathon use

A hackathon posture over public data is not an operating posture. Front the
endpoint with authentication, review your agency's ATO requirements, classify
the data, decide retention and access for any logs that may hold prompts, and
write down what this server could reach if an injected instruction were
followed.
