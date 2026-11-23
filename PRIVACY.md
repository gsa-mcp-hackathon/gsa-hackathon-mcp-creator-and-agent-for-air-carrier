# Privacy Policy

Last updated: 2026-11-23

This policy covers the software in this repository: MCP A Creator, the Air Carrier MCP servers (docs, analyst, ops, hub), the bakehouse demonstration server, the front center app, the probe, and the read-only site on GitHub Pages.

This is a hackathon prototype built on publicly released records. It is not an official Department position and not an authorized production system.

## Who holds the data

Whoever deploys this software runs it in their own Databricks workspace. Everything it reads and writes stays in that workspace, in Unity Catalog tables and volumes the deployer owns and controls.

The author operates no service that receives data from anyone else's deployment. The code sends no telemetry, analytics or usage reports to the author or to any third party.

## What the software reads

The servers read public records loaded into the deployer's workspace: Navy shipbuilding budget books, Selected Acquisition Reports, GAO and CRS reports, regulations, and FPDS and USAspending contract data. None of the tools needs personal information to work. Do not submit personal data, controlled unclassified information or classified information to them.

## What each component records

| Component | What it records | Where |
| --- | --- | --- |
| Docs server | Nothing. `docs_parse_pdf` reads a PDF from an allowed volume and stores nothing | Not applicable |
| Ops server | Nothing. Every tool is read-only | Not applicable |
| Analyst server | Each answer from the four investigate and explain tools is appended as a lead: the ranked options, the contract number, the fiscal period and a hash-derived key for the submitted record. `analyst_record_outcome` stores the confirmed answer, the evidence locator, the confirming office, an optional note and the caller's sign-in name | `aircarrier_analyst_leads` and `aircarrier_analyst_outcomes` in the deployer's schema |
| MCP A Creator | One audit line per tool call: tool name, caller's sign-in name, whether the call ran as the user or the app, duration and outcome. Audit lines never contain arguments or results. If the deployer sets `MLFLOW_EXPERIMENT_ID`, each call also becomes an MLflow trace with clipped inputs and outputs. `CREATOR_MLFLOW_CAPTURE=metadata` keeps inputs and outputs out of the traces. Design documents are kept in memory, a local directory or a volume, as configured | The app log, the deployer's trace volume and MLflow experiment, the deployer's design store |
| Front center and hub | Decisions on proposals with the deciding user, role, action, time and notes. Files a user chooses to capture. Agent runs send their prompts to a model serving endpoint in the same workspace | The deployer's schema, volume and serving endpoint |
| Probe | One file per sweep: target, step, pass or fail, HTTP status, latency, a short reason and the deployment id. It never writes a token, header or payload | The deployer's probe volume |

## Identity

On Databricks Apps the platform authenticates every request and passes the caller's sign-in name and, where enabled, an on-behalf-of token in request headers. MCP A Creator and the front center use the token to act as the caller under Unity Catalog grants. The docs, analyst and ops servers read as the app's own service principal. No component stores or logs the token. The sign-in name is recorded only where the table above says so.

## Error messages

When a tool fails for an unexpected reason, the reply names the tool and at most the error type. The error text is withheld because it can hold a path, a table name or a statement.

## Network destinations

Deployed servers contact only the deployer's own Databricks workspace: the SQL warehouse, the Files API, the Apps API and model serving. The probe sends its service principal token only to `https` Databricks Apps hosts at the path `/mcp`.

Two developer tools reach other hosts and are not part of any deployed server. `tools/deploy_from_github.py` reads this repository through `api.github.com`. The interoperability test server in `scripts/compat/` listens on `127.0.0.1:8765`.

## Retention and deletion

The deployer decides how long the tables, volumes, logs and traces are kept and who can read them. To delete recorded data, delete the rows or files named in the table above. The software has no hidden copy.

## The read-only site

The site on GitHub Pages is static. It sets no cookies, runs no analytics and has no forms. Fonts are served from the site itself. GitHub hosts the pages and may log requests under the [GitHub Privacy Statement](https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement).

## Changes and contact

Changes to this policy are made by commit to this file. To ask a question or report a privacy problem, open an issue on GitHub. Security reports follow [SECURITY.md](SECURITY.md).
