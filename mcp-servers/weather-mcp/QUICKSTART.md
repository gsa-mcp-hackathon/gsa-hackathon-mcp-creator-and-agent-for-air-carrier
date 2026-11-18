# Quickstart

## 1. Install

```bash
pip install uv          # or: brew install uv
cp .env.example .env
uv sync
```

## 2. Format once

The generator emits readable code but does not run a formatter. Do it now so
CI's format check passes:

```bash
uv run ruff format .
```

## 3. Run

```bash
uv run python main.py
```

Stdio mode, waiting for a client. Nothing prints a URL, which is expected.

## 4. Connect a client

Add this to your client's MCP settings, with an absolute path:

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

Then ask it something this server is for:

> What is the current weather at my location?

## 5. Point it at real data

- Set `API_KEY` in `.env` if the API requires one.

## 6. Check it still works

```bash
uv sync --group dev
uv run pytest tests/ -v
uv run ruff check .
```

## 7. Deploy

[deploy/databricks/README.md](deploy/databricks/README.md).
