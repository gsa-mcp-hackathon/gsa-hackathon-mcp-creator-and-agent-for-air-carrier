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
    "mcp-aircarrier-ops": {
      "command": "uv",
      "args": ["run", "mcp-aircarrier-ops"],
      "cwd": "/absolute/path/to/mcp-aircarrier-ops"
    }
  }
}
```

Then ask it something this server is for:

> What does the P-5c exhibit say for this cost category, on which page, with which legends?

## 5. Point it at real data

- Set `DATABRICKS_HOST`, `DATABRICKS_WAREHOUSE_ID`, and `DATABRICKS_TOKEN` in `.env`, then confirm with `databricks current-user me`.
- Set `AIRCARRIER_STORE_SCHEMA=<catalog>.<schema>` if the `aircarrier_*` tables live somewhere other than `users.xiaobing_shang1_civ`. It moves all four sources at once; a malformed value stops the server at start-up.

## 6. Check it still works

```bash
uv sync --group dev
uv run pytest tests/ -v
uv run ruff check .
```

## 7. Deploy

[deploy/databricks/README.md](deploy/databricks/README.md).
