# mcp/ — the ops center as tools

A custom MCP server exposing the four stores and the deterministic checks, so
any agent can use the ops center without reimplementing it: Claude Code at the
terminal, an Agent Bricks custom agent, the front center, or a coding agent
routed through Unity Gateway.

This is the seam that makes the ops center a platform rather than a pipeline.
The agents in `ops/agents/` call the same functions directly; everything
outside this repository calls them through here.

## Beyond CVN-79

Any office that lets an agent draft numbers needs a control between the draft and the
record. `check_claim` is that control for any figure on any program: it returns the routing
decision and the reason and never promotes on its own. The gate's materiality floor is a
share of the subject total, so the same rules move to another hull or program. The gap
queue works like an auditor's request list, ranked by exposure, ignorance and closability.

## Run

```
# stdio, for a local agent
python -m mcp_server

# streamable HTTP, for hosting as a Databricks App
uvicorn mcp_server:http_app --host 0.0.0.0 --port 8000
```

Hosting it as a Databricks App puts it behind Unity Catalog permissions and
Unity Gateway governance, which is how an MCP server becomes available to the
workspace rather than to one laptop.

## Tools

| Tool | What it does | Why an agent needs it |
|---|---|---|
| `list_tables` / `get_table` | the 20 serving tables | the facts, with their sources |
| `search_mechanisms` | rules with their establishing passage | tells an agent what to ask of a document it has never seen |
| `get_keyset` | the selector registry | the identifiers that isolate this hull |
| `exhibit_hazards` | per-exhibit known traps | inherited by every extraction from that exhibit |
| `rank_gaps` | the discovery queue | exposure x ignorance x closability |
| `get_gap` | one gap with its executor | what to work and who works it |
| `check_claim` | policy evaluation plus gate routing | before anything is treated as a figure |
| `challenge_text` | negative-vocabulary falsification | catches the recorded error classes |
| `tie_out` | two-axis close, anchor chain, residual | deterministic, no model |
| `collection_requirement` | draft a CR from a lead | a lead's only legitimate output |

## The rule these tools enforce

Every tool that returns a figure returns its tag, its confidence and its
source. `check_claim` is the only path to a promotion decision and it never
promotes on its own: it returns the routing decision and the reason, and a
human or a deterministic rule acts on it. No tool here writes to a trusted
table.
