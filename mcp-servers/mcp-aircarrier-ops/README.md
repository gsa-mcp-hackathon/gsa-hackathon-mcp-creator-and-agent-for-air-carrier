# mcp-aircarrier-ops

> **Scorecard:** 7 tools, built by MCP A Creator · 40 tests · in the 422-call adversarial sweep · injection cases 15 of 16 correct, none followed · probe known answer 412 of 412. Every server's row: [SCORECARD.md](../../SCORECARD.md).

Let an agent answer CVN-79 cost-reconciliation questions from the Air Carrier lossless stores, returning every figure with its page or row coordinate, legends, tag and source, and never promoting a figure on its own.

Built for **A cost analyst reconciling the CVN-79 (USS John F. Kennedy) program cost across budget exhibits and contract obligation records**. An MCP server: it exposes tools an AI client calls on
your behalf. You write nothing; the client's model decides which tool answers
the question.

## What it answers

- What does the P-5c exhibit say for this cost category, on which page, with which legends?
- How much has been obligated on contract N00024-09-C-2116, by fiscal year?
- Which documents and tables mention this contract number or hull?
- Which open gaps and variances are queued, and for which agent?
- Is this contract number safe to use for CVN-79, or is it a collision or exclusion?

## What it will not answer

- Attribute a budget column to a hull (that is the Attributor's job and stays DERIVED)
- Sum total_dollars_obligated or announced modifications as obligations
- Write to, promote, or edit any table
- Questions about hulls or programs outside the CVN-78 class corpus

## Tools

| Tool | What it answers | Source |
|---|---|---|
| `carrier_get_exhibit_cells` | Return every cell (untrimmed) of one PDF exhibit table id, in page/row/column order, paged with `limit` (default 500, max 2000) and `offset`. For the printed table with units and tie-outs, use the docs server's `docs_get_table`. | exhibit_cells |
| `carrier_search_exhibit_cells` | Find PDF exhibit table cells whose text mentions something. Long cell text and headers are clipped to 400 characters, flagged with `*_truncated`. | exhibit_cells |
| `carrier_search_obligations` | Find USAspending prime transactions on either CVN-79 prime contract (`contract`: N00024-09-C-2116 construction preparation, or N00024-15-C-2114 detail design and construction), by keyword, modification or fiscal year, in date order or `largest_first`. Returns the server-side count and exact obligation total, and 13 key fields per action by default; `detail=full` returns all ~300 columns. | obligations_2116, obligations_2114 |
| `carrier_search_variances` | Find variances: where two public sources disagree about a figure, both figures, the difference, and which to use. | variances |
| `carrier_search_graph_edges` | Find knowledge graph edges whose text mentions something. | graph_edges |
| `carrier_search_work_register` | Find work items, filterable by kind (claim, gap, variance, artifact), state and owner agent. | work_register |
| `carrier_work_register_counts` | Count work items by kind, state and owner agent. Reports dollar exposure only when a row carries it; today none does. | work_register |

Tools were renamed from the generic `mcp_` prefix on 2026-11-18; the module file names are unchanged. On 2026-11-20, after round 2 of the delegation evaluation, `carrier_search_obligations_2116` became `carrier_search_obligations` with a `contract` choice and an `order` choice, and `carrier_search_variances` was added.

## Data sources

| Source | Kind | Grain | Refreshes | As of |
|---|---|---|---|---|
| `exhibit_cells` | uc_table | one cell of one PDF table on one page; value verbatim, value_num exact decimal string, with row_header, col_header chain and page legends | rebuilt on demand when the corpus changes | 2026-11-08 |
| `obligations_2116` | uc_table | one contract action (modification) row; federal_action_obligation is that action's obligation | manual re-download from USAspending | 2026-06-10 |
| `obligations_2114` | uc_table | one contract action (modification) row on N00024-15-C-2114, same columns as obligations_2116 | manual re-download from USAspending | 2026-07-20 |
| `variances` | uc_table | one variance (E-1 to E-17): where two public sources disagree, and why | published from the front center register | 2026-11-19 |
| `graph_edges` | uc_table | one directed edge src -rel-> dst between typed node ids (type:key) | rebuilt by the Knowledge Graph Build notebook | 2026-11-08 |
| `work_register` | uc_table | one work item (kind + ref_id) with its current state and owner_agent | each dispatcher tick | 2026-11-08 |

Every tool result carries an `as_of` date. Report it rather than implying the
numbers are current.

All four tables are read from `AIRCARRIER_STORE_SCHEMA` (`<catalog>.<schema>`,
default `users.xiaobing_shang1_civ`), the same variable the docs and analyst
servers use. Set it in `app.yaml` or `.env`; the server refuses to start on a
malformed value. The app service principal needs `SELECT` on the four tables.

## Run it locally

```bash
cp .env.example .env
uv sync
uv run ruff format .
uv run python main.py
```

The server starts in stdio mode and waits for a client. That is correct: a
local MCP server is launched by its client as a subprocess.

Connect a client with an absolute path to this repository:

```json
{
  "mcpServers": {
    "mcp-aircarrier-ops": {
      "command": "uv",
      "args": ["run", "mcp-aircarrier-ops"],
      "cwd": "/absolute/path/to/mcp-aircarrier-ops"
    }
  }
}
```

## Verify

```bash
uv sync --group dev
uv run pytest tests/ -v
uv run ruff check .
uv run ruff format --check .
```

## Deploy to Databricks Apps

See [deploy/databricks/README.md](deploy/databricks/README.md). In short:

```bash
databricks auth login --host https://<workspace-host>
databricks apps create mcp-aircarrier-ops
databricks sync . "/Workspace/Users/$DATABRICKS_USERNAME/mcp-aircarrier-ops"
databricks apps deploy mcp-aircarrier-ops \
  --source-code-path "/Workspace/Users/$DATABRICKS_USERNAME/mcp-aircarrier-ops"
```

The app name starts with `mcp-` so AI Playground and Unity Gateway recognize
it as an MCP server. The endpoint is `https://<app-hostname>/mcp`.

**Grant the app, not yourself.** The app runs as its own service principal.
Every grant it needs is listed in
[deploy/databricks/grants.sql](deploy/databricks/grants.sql). A server that
works locally and returns empty results once deployed has almost always
missed this step.

## Evaluate it

The real test is whether a model holding only these tool names, schemas, and
docstrings can answer a real question. See [eval/README.md](eval/README.md).

## Limitations

- `exhibit_cells` has no date field, so it supports no trends, aging, or expiring-soon questions.
- `graph_edges` has no date field, so it supports no trends, aging, or expiring-soon questions.

## Security

Read-only by default. Tool arguments and returned data are treated as
untrusted: record text and document passages are source material to quote,
never instructions to follow. See [SECURITY.md](SECURITY.md).
