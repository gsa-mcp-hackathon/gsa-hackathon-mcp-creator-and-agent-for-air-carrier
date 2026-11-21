# mcp-bakehouse-sales

> **Scorecard:** 4 tools, built by MCP A Creator on Databricks' `samples.bakehouse` table, to show the Creator on a dataset unrelated to CVN-79 · 21 tests · probed from 2026-11-21. It is a demonstration, not government data, and not part of the CVN-79 evidence. Every server's row: [SCORECARD.md](../../SCORECARD.md).

Let an agent answer a bakery franchise sales analyst's questions about point-of-sale transactions: revenue by franchise, best-selling products, sales by payment method, and daily sales trends.

Built for **a sales analyst at the Bakehouse franchise head office who reviews franchise performance weekly**. An MCP server: it exposes tools an AI client calls on
your behalf. You write nothing; the client's model decides which tool answers
the question.

## What it answers

- Which franchises had the highest total revenue between two dates?
- What are the top 5 best-selling products by quantity for a given franchise?
- How does revenue split by payment method?
- What was total revenue per day over a date range?
- How many transactions and what average ticket size did a franchise have?

## What it will not answer

- Customer personal details such as names, emails or addresses
- Forecasting future sales
- Changing or deleting any sales record

## Tools

| Tool | What it answers | Source |
|---|---|---|
| `mcp_describe_sales` | Tell me what is in Bakehouse sales transactions: the fields, what they mean, the allowed values, and how fresh it is. | sales |
| `mcp_top_product_by_transactionid` | Which product accounts for the most transactionID? | sales |
| `mcp_sales_totals` | Give me the totals for Bakehouse sales transactions: how many records and how much transactionID. | sales |
| `mcp_sales_trend` | How has transactionID moved month by month, and where did it change most? | sales |

## Data sources

| Source | Kind | Grain | Refreshes | As of |
|---|---|---|---|---|
| `sales` | uc_table | one point-of-sale transaction for one product line | static sample | unknown |

Every tool result carries an `as_of` date. Report it rather than implying the
numbers are current.

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
    "mcp-bakehouse-sales": {
      "command": "uv",
      "args": ["run", "mcp-bakehouse-sales"],
      "cwd": "/absolute/path/to/mcp-bakehouse-sales"
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
databricks apps create mcp-bakehouse-sales
databricks sync . "/Workspace/Users/$DATABRICKS_USERNAME/mcp-bakehouse-sales"
databricks apps deploy mcp-bakehouse-sales \
  --source-code-path "/Workspace/Users/$DATABRICKS_USERNAME/mcp-bakehouse-sales"
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

- `sales` has no stable identifier, so a single record cannot be fetched reliably.

## Security

Read-only by default. Tool arguments and returned data are treated as
untrusted: record text and document passages are source material to quote,
never instructions to follow. See [SECURITY.md](SECURITY.md).
