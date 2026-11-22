#!/usr/bin/env bash
# Version matrix for MCP A Creator (round 10, D3).
#
#   scripts/check_compat.sh 3.4.11    # the floor every pin allows
#   scripts/check_compat.sh 4.2.4     # current FastMCP, MCP SDK 2.x, protocol 2026-07-28
#
# For the given FastMCP version: the Creator's full suite, the generated
# bakehouse project's suite, and an interop call from the MCP SDK 1.x client
# the deployed servers use today to a server on that version. Prints the
# protocol each side speaks. The version is forced with a uv override, so this
# tests a range wider than the deployed pins on purpose.
set -euo pipefail

VERSION="${1:?usage: scripts/check_compat.sh <fastmcp version>}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'pkill -f "$ROOT/scripts/compat/interop_server.py" 2>/dev/null || true; rm -rf "$WORK"' EXIT
echo "fastmcp==$VERSION" > "$WORK/override.txt"

venv() {  # venv <name> <pip args...>
  local name="$1"; shift
  uv venv -q "$WORK/$name" --python 3.12
  uv pip install -q -p "$WORK/$name" --override "$WORK/override.txt" "$@"
}

echo "== MCP A Creator on FastMCP $VERSION"
venv creator -e "$ROOT/mcp-server-creator" pytest pytest-asyncio "databricks-sdk>=0.30.0" bandit
"$WORK/creator/bin/python" -c "import fastmcp, mcp.types as t; print('fastmcp', fastmcp.__version__, '| server protocol', t.LATEST_PROTOCOL_VERSION)"
(cd "$ROOT/mcp-server-creator" && PATH="$WORK/creator/bin:$PATH" "$WORK/creator/bin/python" -m pytest -q -p no:cacheprovider)

echo "== generated project (bakehouse) on FastMCP $VERSION"
venv bakehouse -e "$ROOT/mcp-servers/mcp-bakehouse-sales" pytest pytest-asyncio
(cd "$ROOT/mcp-servers/mcp-bakehouse-sales" && "$WORK/bakehouse/bin/python" -m pytest -q -p no:cacheprovider)

echo "== interop: SDK 1.x client against a FastMCP $VERSION server"
"$WORK/creator/bin/python" -I "$ROOT/scripts/compat/interop_server.py" > "$WORK/server.log" 2>&1 &
for _ in $(seq 1 30); do grep -q "Uvicorn running" "$WORK/server.log" && break; sleep 1; done
uv run --quiet --no-project --with "mcp>=1.24,<2" python -I "$ROOT/scripts/compat/interop_client.py"
echo "PASS compat $VERSION"
