# Deploying Bakehouse Sales to Databricks Apps

- **Transport:** MCP over streamable HTTP at `/mcp`, health at `/health`
- **Port:** Databricks injects `DATABRICKS_APP_PORT`; `app.py` reads it
- **App name:** `mcp-bakehouse-sales` — the `mcp-` prefix is what makes AI Playground
  and Unity Gateway treat this as an MCP server

## 1. Prerequisites

```bash
databricks --version          # need v0.205+, v0.298+ for bundles
databricks auth login --host https://<workspace-host>
databricks current-user me
```

The profile name `databricks auth login` saves defaults to the workspace
host, **not** `DEFAULT`. Set `DATABRICKS_CONFIG_PROFILE` to the name it
actually saved; `databricks auth profiles` lists them.

Databricks Apps must be enabled on the workspace. If `apps` commands fail
with a feature error, ask a workspace admin.

## 2. Configure

```bash
cp deploy/databricks/.env.example deploy/databricks/.env
# edit APP_NAME, DATABRICKS_HOST, DATABRICKS_CONFIG_PROFILE
set -a; source deploy/databricks/.env; set +a
```

No secrets live in that file. Authentication comes from your CLI login.

## 3. Deploy

```bash
bash deploy/databricks/deploy.sh
```

The script refuses to proceed if the app name lacks the `mcp-` prefix or if
`app.yaml` is not at the repository root. The first deploy builds a container
and takes a few minutes.

With the bundle instead:

```bash
databricks bundle validate
databricks bundle deploy --var="warehouse_id=<warehouse-id>"
```

## 4. Grant the service principal

This server reads governed data, so grants are required.

Open the app's page, find the service principal under **App Authorization**,
then apply [grants.sql](grants.sql) with that application id.

This is the most common cause of a deployed server returning nothing.

## 5. Smoke test

```bash
bash deploy/databricks/smoke-test.sh https://<app-url>

DATABRICKS_TOKEN="$(databricks auth token --output json | jq -r .access_token)" \
  bash deploy/databricks/smoke-test.sh https://<app-url>
```

An unauthenticated 302 or 401 is the app working, not failing.

## 6. Register and connect

- **Workspace UI:** Unity Gateway, then MCPs, then + MCP.
- **Coding agents:** `ug mcp add --names "app:mcp-bakehouse-sales"`.
- **Python agents:** pass `https://<app-url>/mcp` to the framework's MCP
  client.
- **Other clients:** register an OAuth client with its redirect URL and the
  app's user authorization scopes, then configure the MCP URL.

Callers need `CAN USE` on the app and an OAuth token. Personal access tokens
are not supported.

## Troubleshooting

| Symptom | First thing to check |
|---|---|
| Playground does not list the app | Name is missing the `mcp-` prefix |
| Tools return nothing, fine locally | Service principal lacks the grant |
| App will not start | No `requirements.txt`, or bound to 127.0.0.1 |
| `ModuleNotFoundError` in app logs | `PYTHONPATH` not set in `command` |
| Warehouse id empty at runtime | `valueFrom` key does not match the resource |
| Client cannot authenticate | Using a PAT; OAuth is required |

Read the app's own logs from its page before changing code.

## Teardown

```bash
databricks apps delete mcp-bakehouse-sales
databricks workspace delete "${SOURCE_CODE_PATH}" --recursive
```
