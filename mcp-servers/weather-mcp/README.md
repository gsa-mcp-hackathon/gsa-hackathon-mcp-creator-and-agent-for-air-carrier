# Weather Mcp

Let an AI agent look up current weather conditions and forecasts for any US location using the NWS (weather.gov) REST API

Built for **anyone who needs current weather or forecast data for a US location**. An MCP server: it exposes tools an AI client calls on
your behalf. You write nothing; the client's model decides which tool answers
the question.

## What it answers

- What is the current weather at my location?
- What is the forecast for a given city or coordinates?
- What weather alerts are active in my area?

## What it will not answer

- (none recorded)

## Tools

| Tool | What it answers | Source |
|---|---|---|
| `weather_describe_nws` | Tell me what is in NWS Weather API (weather.gov): the fields, what they mean, the allowed values, and how fresh it is. | nws |

## Data sources

| Source | Kind | Grain | Refreshes | As of |
|---|---|---|---|---|
| `nws` | rest_api | one HTTP response per NWS API call; each forecast endpoint returns a list of forecast periods | live — data is fresh at call time | unknown |

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
    "weather-mcp": {
      "command": "uv",
      "args": ["run", "weather-mcp"],
      "cwd": "/absolute/path/to/weather-mcp"
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
databricks apps create mcp-weather
databricks sync . "/Workspace/Users/$DATABRICKS_USERNAME/mcp-weather"
databricks apps deploy mcp-weather \
  --source-code-path "/Workspace/Users/$DATABRICKS_USERNAME/mcp-weather"
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

- `nws` has no numeric measure, so it supports no totals, averages, or rankings by value.
- `nws` has no date field, so it supports no trends, aging, or expiring-soon questions.
- `nws` has no stable identifier, so a single record cannot be fetched reliably.

## Security

Read-only by default. Tool arguments and returned data are treated as
untrusted: record text and document passages are source material to quote,
never instructions to follow. See [SECURITY.md](SECURITY.md).
