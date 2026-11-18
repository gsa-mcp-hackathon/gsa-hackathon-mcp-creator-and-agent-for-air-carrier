#!/usr/bin/env bash
# Idempotent deploy of this MCP server to Databricks Apps.
#
#   cp deploy/databricks/.env.example deploy/databricks/.env
#   # edit it, then:
#   set -a; source deploy/databricks/.env; set +a
#   bash deploy/databricks/deploy.sh
set -euo pipefail

APP_NAME="${APP_NAME:-mcp-bakehouse-sales}"
SOURCE_CODE_PATH="${SOURCE_CODE_PATH:-}"
PROFILE_ARGS=()
if [[ -n "${DATABRICKS_CONFIG_PROFILE:-}" ]]; then
  PROFILE_ARGS=(--profile "${DATABRICKS_CONFIG_PROFILE}")
fi

if ! command -v databricks >/dev/null 2>&1; then
  echo "The Databricks CLI is not installed." >&2
  echo "See https://docs.databricks.com/dev-tools/cli/install.html" >&2
  exit 1
fi

if ! databricks "${PROFILE_ARGS[@]}" current-user me >/dev/null 2>&1; then
  echo "Not authenticated. Run:" >&2
  echo "  databricks auth login --host https://<workspace-host>" >&2
  echo "Then set DATABRICKS_CONFIG_PROFILE to the profile name it saved." >&2
  echo "List profiles with: databricks auth profiles" >&2
  exit 1
fi

if [[ "${APP_NAME}" != mcp-* ]]; then
  echo "APP_NAME must start with 'mcp-' or AI Playground will not" >&2
  echo "recognize this app as an MCP server. Got: ${APP_NAME}" >&2
  exit 1
fi

if [[ -z "${SOURCE_CODE_PATH}" ]]; then
  ME="$(databricks "${PROFILE_ARGS[@]}" current-user me --output json)"
  USER_NAME="$(printf '%s' "${ME}" \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["userName"])')"
  SOURCE_CODE_PATH="/Workspace/Users/${USER_NAME}/${APP_NAME}"
  echo "SOURCE_CODE_PATH not set; using ${SOURCE_CODE_PATH}"
fi

if [[ ! -f app.yaml ]]; then
  echo "app.yaml must be at the repository root: Databricks reads it from" >&2
  echo "the deployed source root." >&2
  exit 1
fi

echo "==> Ensuring the app exists"
if databricks "${PROFILE_ARGS[@]}" apps get "${APP_NAME}" >/dev/null 2>&1; then
  echo "    ${APP_NAME} already exists; reusing it"
else
  databricks "${PROFILE_ARGS[@]}" apps create "${APP_NAME}"
fi

echo "==> Syncing source to ${SOURCE_CODE_PATH}"
databricks "${PROFILE_ARGS[@]}" sync . "${SOURCE_CODE_PATH}"

echo "==> Deploying"
databricks "${PROFILE_ARGS[@]}" apps deploy "${APP_NAME}" \
  --source-code-path "${SOURCE_CODE_PATH}"

echo "==> Deployed"
databricks "${PROFILE_ARGS[@]}" apps get "${APP_NAME}" --output json \
  | python3 -c 'import json,sys;print("URL:", json.load(sys.stdin).get("url"))' \
  || true
echo
echo "Next:"
echo "  1. Apply deploy/databricks/grants.sql to the app service principal."
echo "  2. Smoke test:  bash deploy/databricks/smoke-test.sh <app-url>"
echo "  3. Register it: Unity Gateway > MCPs, or"
echo "     ug mcp add --names \"app:${APP_NAME}\""
