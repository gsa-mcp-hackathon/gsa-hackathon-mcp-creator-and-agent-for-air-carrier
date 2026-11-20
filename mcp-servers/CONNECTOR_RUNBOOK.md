# MCP connector runbook (Air Carrier servers)

Servers: mcp-aircarrier-docs, mcp-aircarrier-analyst, mcp-aircarrier-ops (and
mcp-a-creator, which has no fallback on purpose). Each is a Databricks App;
Genie Code reaches it through a Custom MCP Server connector that mints a
per-user OAuth token for the app.

## Three layers, three different failures

| Layer | What fails | Symptom | Who fixes |
| --- | --- | --- | --- |
| 1. Connector auth (client side) | The user's token for the app cannot be minted (authorization expired or revoked, or scopes changed) | Every tool on every server fails with "Failed to generate OAuth token"; no request reaches the app | The user: re-authenticate the connector |
| 2. App platform | App stopped, crashed, deploy failed | "Failed to fetch", 502/503, tools missing | App owner: start or redeploy |
| 3. Server code or data | Tool raises, SQL fails, grants missing | Tool returns an error message from the server | App owner: fix and redeploy |

Tell them apart in this order:

1. Does every server fail with the same message? Then it is layer 1.
2. App status (GET /api/2.0/apps/<name>): RUNNING and the last deployment
   SUCCEEDED rules out layer 2.
3. Did the request arrive? mcp-a-creator writes a span for every tool call to
   users.xiaobing_shang1_civ.mcp_a_creator_otel_spans. If there is no new span
   after a failed call, the request never reached the app (layer 1).
4. Run the same tool in-process (below). If it works, the server code and data
   are fine (not layer 3).

Incident 2026-11-11 (layer 1): all 4 servers returned "Failed to generate
OAuth token". All 4 apps were RUNNING, unchanged since 2026-11-08/10, and the
owner had CAN_MANAGE. The last creator span was 2026-11-09 01:54, so nothing
from that day's calls arrived. In-process, all 29 tools on docs, analyst and ops
listed. The read tools called (docs status, search, find_figure; analyst
model_status, list_sources, search_documents; ops totals) answered, and the ops
totals matched direct SQL (12,173 records, 65 gaps, 31 artifacts).
Genie Code's documentation says it does not warn when a connection's
authentication expires, and that re-authenticating resolves it.

## Fix for layer 1

Genie Code > Settings > Connectors. For each Air Carrier server, remove and
re-add it, or choose re-authenticate if offered, and complete the consent
screen. Then call one read tool on each (docs_status, analyst_model_status,
carrier_work_register_counts) to confirm.

No agent can do this step: it is an interactive consent in the user's
browser. Do not work around it by putting a token in code.

## Keep working meanwhile: in-process fallback

`mcp_local.py` (this folder) loads the server's own package and calls its tools
through FastMCP's in-memory client. It uses the caller's Spark session and
Unity Catalog grants, refuses writes by default, and labels every result with
`_mcp.transport = in-process`, the identity, and the app's active deployment id.

    %pip install "fastmcp>=2.14,<3" "mcp>=1.24,<2"   # once per session
    import sys; sys.path.insert(0, "/Workspace/Users/xiaobing.shang1.civ@mail.mil/gsa-hackathon-mcp-creator-and-agent-for-cvn/mcp-servers")
    import mcp_local
    mcp_local.call("docs", "docs_find_figure", value_musd="13529")

Limits, stated so nobody over-trusts it:

* It runs the workspace source folder. If that folder has changed since the
  last deploy, the answers can differ from the app's. Compare the
  deployment_id with the source before quoting a result as "the server's".
* Writes (analyst lead log, record_outcome) are refused, so analyst answers
  come back with lead_logged false. That is deliberate: the audit trail should
  name the app's service principal, not the person.
* It is a fallback, not a second production path. The connector stays the
  supported route.

Tests: `python -m pytest -q test_mcp_local.py` (offline, 23 tests).

## Synthetic probe (built 2026-11-11)

App `aircarrier-mcp-probe` (source: `aircarrier-mcp-probe/` in this folder) runs
as its own service principal, `app-2vrjmx aircarrier-mcp-probe` (client id
89a35bc5-a29a-44ca-b483-2f648114d2a3). The platform injects and rotates its
credentials, so no person holds a secret. Every 15 minutes it calls, on each
app: resolve, initialize, tools/list, and one known-answer read tool:

| App | Known answer |
| --- | --- |
| mcp-aircarrier-docs | docs_find_figure(13529) finds "$13.529 billion" on CVN_78_MSAR_FY2027_PBv2.pdf p. 8 (guards the 3-decimal fix) |
| mcp-aircarrier-analyst | analyst_model_status returns an analyst/ engine |
| mcp-aircarrier-ops | carrier_work_register_counts returns more than 0 records |
| mcp-a-creator | tools/list only; it writes and deploys, so no tool is called |

Each sweep is one JSON-lines file in
`/Volumes/users/xiaobing_shang1_civ/aircarrier_mcp_probe_runs/<date>/`. It is
written with the Files API, not a SQL warehouse, so the probe does not share
the servers' warehouse dependency. The alert "Air Carrier MCP probe - failing
or silent" runs every 15 minutes, and `problems` > 0 fires it. `problems` is
the number of failing apps in the latest sweep, or 100 when there has been no
sweep for 40 minutes, which covers a dead probe.

Why an app, not a job: a job would need a service principal with an OAuth
secret, and only a workspace admin can create one. An app gets a dedicated
service principal automatically.

Permissions it holds: CAN_USE on the four MCP apps, and READ/WRITE VOLUME on
the probe volume. Nothing else.

Reading it: green probe plus a user's "Failed to generate OAuth token" means
layer 1 (re-authenticate). A red probe names the app and the step that broke.
The probe cannot see any one user's connector authorization.

Self-test leftover: `_selftest/old.jsonl` in the volume was used to test the
alert query. The alert's `20*/` glob excludes it, so it is safe to delete.
