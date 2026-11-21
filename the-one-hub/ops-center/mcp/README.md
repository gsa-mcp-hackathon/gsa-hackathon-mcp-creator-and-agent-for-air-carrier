# mcp/: the One Hub as tools (`mcp-aircarrier-hub`)

> **Scorecard:** 16 read-only tools · 25 server tests (schema portability, refusals, tie-out, gate, HTTP behind the Apps proxy) · 193 hostile arguments, none leaked · ready to deploy, probe target added. Every server's row: [SCORECARD.md](../../../SCORECARD.md).

A custom MCP server exposing the four stores and the deterministic checks, so
any agent can use the ops center without reimplementing it: Claude Code at the
terminal, an Agent Bricks custom agent, the front center, or a coding agent
routed through Unity Gateway.

This is the seam that makes the ops center a platform rather than a pipeline.
The agents in `ops/agents/` call the same functions directly; everything
outside this repository calls them through here.

## Beyond CVN-79

Any office that lets an agent draft numbers needs a control between the draft and the
record. `hub_check_claim` is that control for any figure on any program: it returns the routing
decision and the reason and never promotes on its own. The gate's materiality floor is a
share of the subject total, so the same rules move to another hull or program. The gap
queue works like an auditor's request list, ranked by exposure, ignorance and closability.

## Run

From `the-one-hub/ops-center`:

```
# stdio, for a local agent
python mcp/mcp_server.py

# stateless streamable HTTP at /mcp, as the Databricks App (set the port to try it locally)
DATABRICKS_APP_PORT=8000 python mcp/mcp_server.py
```

The app's source folder is `the-one-hub/ops-center`, not `mcp/`, because the server reads
`core/`, `ops/agents/`, `seed/` and `app/data/`; its `app.yaml` and `requirements.txt` are in
that folder. First deployment: [docs/DEPLOYMENT.md](../../../docs/DEPLOYMENT.md#first-deployment-of-mcp-aircarrier-hub).
Before 2026-11-21 the HTTP form used the SDK's default host, 127.0.0.1, which turns on a
localhost-only Host check: behind the Apps proxy every request got 421 Invalid Host header.
`checks/test_mcp_server.py` now posts `initialize` and `tools/list` with a Databricks Apps
host. Every result that holds text addressed to an AI assistant carries a `source_notice`.

Hosting it as a Databricks App puts it behind Unity Catalog permissions and
Unity Gateway governance, which is how an MCP server becomes available to the
workspace rather than to one laptop.

## Tools

Sixteen tools, all read-only (`readOnlyHint`), all prefixed `hub_` so they cannot collide
with another server's names in a multi-server client. Arguments are validated by Pydantic
before a tool runs; every parameter is a string, number, boolean, enum or list of strings,
so the schema stays readable by every model behind an AI gateway (the Creator's
portability rule, checked in `checks/test_mcp_server.py`). A bad argument or an empty
result comes back as a tool error with the reason, not as an error inside a result.

| Tool | What it does | Why an agent needs it |
|---|---|---|
| `hub_list_tables` / `hub_get_table` | the serving tables with their sources | the facts, each with the document it comes from |
| `hub_search_mechanisms` | rules with their establishing passage | tells an agent what to ask of a document it has never seen |
| `hub_get_keyset` | the selector registry | the identifiers that isolate this hull; read `collisions` first |
| `hub_exhibit_hazards` | per-exhibit known traps | inherited by every extraction from that exhibit |
| `hub_rank_gaps` / `hub_get_gap` | the discovery queue and one gap | exposure x ignorance x closability, and who can close it |
| `hub_plan_gap` / `hub_next_work` | a plan of Collection Requirements per gap | what to retrieve, from where, never a figure |
| `hub_check_claim` | policy evaluation plus gate routing | before anything is treated as a figure; never promotes |
| `hub_challenge_text` | negative-vocabulary falsification | catches the recorded error classes |
| `hub_tie_out` / `hub_check_anchor_chain` | two-axis close, anchor chain | exact decimals, closes only to the exhibit's rounding, no model |
| `hub_collection_requirement` | draft a CR from a lead | a lead's only legitimate output |
| `hub_search_corpus` / `hub_corpus_status` | cited search over the document knowledge base | every hit carries its page |

`hub_tie_out` takes each axis as two parallel lists (labels and amounts as printed, for
example `["Plan Costs", "Basic Construction"]` and `["1234.567", "8901.234"]`), not a
dictionary. The Python functions without the prefix (`check_claim`, `tie_out`, ...) are
the same checks for code in this repository; the agents and the front center call those.

## The rule these tools enforce

Every tool that returns a figure returns its tag, its confidence and its
source. `hub_check_claim` is the only path to a promotion decision and it never
promotes on its own: it returns the routing decision and the reason, and a
human or a deterministic rule acts on it. No tool here writes to a trusted
table.
