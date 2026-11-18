#!/usr/bin/env bash
# Check a deployed app answers /health and /mcp.
#
#   bash deploy/databricks/smoke-test.sh https://<app-url>
#
# Without a token, 302 or 401 is the CORRECT result: Databricks Apps sit
# behind workspace authentication. For an authenticated check:
#
#   DATABRICKS_TOKEN="$(databricks auth token --output json | jq -r .access_token)" \
#     bash deploy/databricks/smoke-test.sh https://<app-url>
set -euo pipefail

APP_URL="${1:-}"
if [[ -z "${APP_URL}" ]]; then
  echo "usage: $0 https://<app-url>" >&2
  exit 1
fi
APP_URL="${APP_URL%/}"

AUTH_ARGS=()
if [[ -n "${DATABRICKS_TOKEN:-}" ]]; then
  AUTH_ARGS=(-H "Authorization: Bearer ${DATABRICKS_TOKEN}")
  echo "Using a bearer token."
else
  echo "No DATABRICKS_TOKEN set; expect 302 or 401 (that is the app working)."
fi

echo "==> GET ${APP_URL}/health"
curl -sS -o /dev/null -w "    HTTP %{http_code}\n" "${AUTH_ARGS[@]}" \
  "${APP_URL}/health"

echo "==> POST ${APP_URL}/mcp (tools/list)"
curl -sS -o /tmp/mcp-smoke.json -w "    HTTP %{http_code}\n" \
  "${AUTH_ARGS[@]}" \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' \
  "${APP_URL}/mcp"

if [[ -s /tmp/mcp-smoke.json ]]; then
  echo "    response head:"
  head -c 400 /tmp/mcp-smoke.json
  echo
fi
