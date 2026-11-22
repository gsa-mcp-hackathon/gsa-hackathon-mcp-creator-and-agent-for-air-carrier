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
    "bakehouse-sales": {
      "command": "uv",
      "args": ["run", "bakehouse-sales"],
      "cwd": "/absolute/path/to/bakehouse-sales"
    }
  }
}
```

Then ask it something this server is for:

> Which franchises had the highest total revenue between two dates?

## 5. Point it at real data

- Set `DATABRICKS_HOST`, `DATABRICKS_WAREHOUSE_ID`, and `DATABRICKS_TOKEN` in `.env`, then confirm with `databricks current-user me`.

## 6. Check it still works

```bash
uv sync --group dev
uv run pytest tests/ -v
uv run ruff check .
```

## 7. Deploy

[deploy/databricks/README.md](deploy/databricks/README.md).
