# Manual deployment

The apps are deployed by hand from their workspace source folders. GitHub is only used for
version control; there is no CI/CD deployment. `~` below means
`/Workspace/Users/xiaobing.shang1.civ@mail.mil`.

## App map

| App | Deploys from (workspace) | Repo folder | Resources attached | User scopes |
| --- | --- | --- | --- | --- |
| `mcp-a-creator` | `~/mcp-server-creator` | `mcp-server-creator/` | SQL warehouse, UC volume `storage`, MLflow experiment, trace tables (8) | sql, workspace.workspace, apps |
| `mcp-aircarrier-docs` | `~/mcp-servers/mcp-aircarrier-docs` | `mcp-servers/mcp-aircarrier-docs/` | SQL warehouse, 3 UC tables (pdf-pages, pdf-tables, artifacts) | - |
| `mcp-aircarrier-analyst` | `~/mcp-servers/mcp-aircarrier-analyst` | `mcp-servers/mcp-aircarrier-analyst/` | SQL warehouse | - |
| `mcp-aircarrier-ops` | `~/mcp-servers/mcp-aircarrier-ops` | `mcp-servers/mcp-aircarrier-ops/` | SQL warehouse, 4 UC tables | - |
| `aircarrier-mcp-probe` | `~/mcp-servers/aircarrier-mcp-probe` | `mcp-servers/aircarrier-mcp-probe/` | none (UC volume grant on the SP) | - |
| `mcp-bakehouse-sales` | `~/mcp-servers/mcp-bakehouse-sales` | `mcp-servers/mcp-bakehouse-sales/` | SQL warehouse, 1 UC table | - |
| `mcp-weather` | `~/mcp-servers/weather-mcp` | `mcp-servers/weather-mcp/` | none | - |
| `aircarrier-front-center-dev` | `~/the-one-hub/the-ops-center/.bundle/aircarrier/dev/files/app` | `the-one-hub/ops-center/app/` | SQL warehouse, 4 serving endpoints (agent, reasoning, checker, fallback) | sql |

App names that start with `mcp-` appear in the Genie Code MCP connector picker; the probe is
named without the prefix on purpose.

## Deploy an MCP app

In the Apps UI: open the app, choose **Deploy**, and keep the source folder from the table.
Or with the CLI:

```
databricks apps deploy <app-name> --source-code-path /Workspace/Users/<you>/mcp-servers/<folder>
```

Notes:

* `app.yaml` in each folder sets the command and environment variables.
* Resources (warehouse, tables, volume, experiment) are attached to the app, not stored in
  the code. A `PATCH` on the app replaces the whole object, so always send the description and
  all resources together.
* `mcp-aircarrier-ops` and `aircarrier-mcp-probe` must be redeployed together whenever an ops
  tool is renamed, because the probe calls ops tools by name.

## Deploy the front UI (`aircarrier-front-center-dev`)

The app needs 15 environment variables, all defined in
`the-one-hub/ops-center/resources/app.yml` (`config.env`). `AIRCARRIER_SI_PERSIST` and
`AIRCARRIER_CAPTURE_VOLUME` were added there on 2026-11-18; before that a bundle deploy
dropped them.

* Bundle deploy (`databricks bundle deploy -t dev` from the bundle root) applies the variables in `app.yml`.
* A direct REST deployment (`POST /api/2.0/apps/<name>/deployments`) does **not** carry
  forward the previous deployment's variables. Pass all 15 `env_vars` explicitly, or the app
  starts with no warehouse, catalog or models.

The workspace copy of the bundle is the latest source. Do not run `bundle deploy` from an older
local clone; it would overwrite newer workspace files. To work locally, clone this GitHub
repository instead.

## Grants

Grant SQL lives in `the-one-hub/ops-center/deploy/` (`grants_*.sql`, `harness_authority.sql`).
Each app runs as its own service principal, so a live test as the owner can hide a missing
grant. Check the app's SP has `SELECT` on every table it reads.

## Keep this repository in sync

After deploying a change, run `tools/sync_from_workspace.py`, review the diff in the Git
folder, then commit and push.
