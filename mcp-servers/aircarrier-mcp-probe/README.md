# aircarrier-mcp-probe

A synthetic monitor for the deployed MCP servers. It is a Databricks App, not an MCP
server, and is named without the `mcp-` prefix so it stays out of the connector picker.

## What one sweep checks

For each target app, in order, as the probe's own service principal:

| Step | Passes when |
| --- | --- |
| `resolve` | The app exists and has an active deployment |
| `initialize` | `POST /mcp` initialize returns a result |
| `tools_list` | `tools/list` returns at least the expected number of tools |
| `known_answer` | One read-only tool returns an answer known in advance |

The known answers: the docs server finds $13,529M printed on page 8 of the FY2027 MSAR (a
regression check on a fixed defect); the analyst reports its engine; the ops server counts
work register records above zero; MCP A Creator returns its 8 packaged skills from the
read-only `creator_list_library` (it is never asked to design, write or deploy). The One Hub
server (`mcp-aircarrier-hub`) must route the held $13,529M baseline to `human_review` through
`hub_check_claim`. That check takes about 50 to 60 ms because the gate is deterministic rules
over the decision log and per-hull totals held in memory: no model and no warehouse call.

Each target app must grant the probe's service principal `CAN_USE`. The hub became a target
on 2026-11-21. The bakehouse server was a target that day too, until its app was deleted to
free the slot for the hub (the shared workspace is capped at 100 apps); its check is kept as
`BAKEHOUSE` in `probe.py`.

A failed step stops that target's sweep, and every step is one row in the results volume,
so a failure says where it broke. No token, header or payload is written.

## Results

413 sweeps from 2026-11-12 to 2026-11-20, four targets: 99.90% of 6,193 checks ok, and
1,234 of 1,234 known-answer checks right, with latency per server and step in
[EVALUATION.md](../../docs/submission/EVALUATION.md), section 2.2.

## Why it matters beyond this hub

When a user's agent reports "Failed to generate OAuth token", the probe tells the two causes
apart. A green probe means the app, the platform's OAuth path for a non-human caller, the
server code and its data are healthy, so the fault is that user's connector. Any agency
running MCP servers in production needs this evidence, and a log of known answers every 15 minutes
is continuous-monitoring evidence for an authority to operate.

## Safety

The probe sends its bearer token only to `https://<host>.databricksapps.com/mcp`: no
credentials in the URL, no other port, path, query or fragment (`safe_mcp_url`, tested in
`test_probe.py`).

## Run the tests

```
python -m pytest -q test_probe.py
```
