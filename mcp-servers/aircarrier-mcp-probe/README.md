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
work register records above zero. MCP A Creator is checked through `tools_list` only,
because its other tools write and deploy.

A failed step stops that target's sweep, and every step is one row in the results volume,
so a failure says where it broke. No token, header or payload is written.

## Results

238 sweeps over seven days: 99.83% of 3,568 checks ok, and 709 of 709 known-answer checks
right ([evaluation report](../../docs/submission/evaluation-report.pdf), section 4).

## Why it matters beyond this hub

When a user's agent reports "Failed to generate OAuth token", the probe tells the two causes
apart. A green probe means the app, the platform's OAuth path for a non-human caller, the
server code and its data are healthy, so the fault is that user's connector. Any agency
running MCP servers in production needs this evidence, and an hourly log of known answers
is continuous-monitoring evidence for an authority to operate.

## Safety

The probe sends its bearer token only to `https://<host>.databricksapps.com/mcp`: no
credentials in the URL, no other port, path, query or fragment (`safe_mcp_url`, tested in
`test_probe.py`).

## Run the tests

```
python -m pytest -q test_probe.py
```
