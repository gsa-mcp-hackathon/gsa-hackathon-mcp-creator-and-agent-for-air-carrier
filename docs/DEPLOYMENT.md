# Manual deployment

The MCP apps are deployed by hand from their workspace source folders. The front UI
(`aircarrier-front-center-dev`) is deployed from this GitHub repository (since 2026-11-20).
There is no CI/CD deployment: CI only runs the test suites. `~` below means
`/Workspace/Users/xiaobing.shang1.civ@mail.mil`.

## App map

| App | Deploys from | Repo folder | Resources attached | User scopes |
| --- | --- | --- | --- | --- |
| `mcp-a-creator` | `~/mcp-server-creator` | `mcp-server-creator/` | SQL warehouse, UC volume `storage`, MLflow experiment, trace tables (8) | sql, workspace.workspace, apps |
| `mcp-aircarrier-docs` | `~/mcp-servers/mcp-aircarrier-docs` | `mcp-servers/mcp-aircarrier-docs/` | SQL warehouse, 3 UC tables (pdf-pages, pdf-tables, artifacts) | - |
| `mcp-aircarrier-analyst` | `~/mcp-servers/mcp-aircarrier-analyst` | `mcp-servers/mcp-aircarrier-analyst/` | SQL warehouse | - |
| `mcp-aircarrier-ops` | `~/mcp-servers/mcp-aircarrier-ops` | `mcp-servers/mcp-aircarrier-ops/` | SQL warehouse, 6 UC tables (2114 transactions and the variance register added 2026-11-20; see its `deploy/databricks/grants.sql`) | - |
| `aircarrier-mcp-probe` | `~/mcp-servers/aircarrier-mcp-probe` | `mcp-servers/aircarrier-mcp-probe/` | none (UC volume grant on the SP) | - |
| `mcp-bakehouse-sales` | `~/mcp-servers/mcp-bakehouse-sales` | `mcp-servers/mcp-bakehouse-sales/` | SQL warehouse, 1 UC table | - |
| `mcp-weather` | `~/mcp-servers/weather-mcp` | `mcp-servers/weather-mcp/` | none | - |
| `aircarrier-front-center-dev` | GitHub `main`, `the-one-hub/ops-center/app` (Git source) | `the-one-hub/ops-center/app/` | SQL warehouse, 4 serving endpoints (agent, reasoning, checker, fallback) | sql |

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

### Source: GitHub, through the bundle

The app code comes from GitHub, not from workspace files. `resources/app.yml` sets
`git_repository` (this repo, public, so the app service principal needs no Git credential) and
`git_source` (branch `main`, path `the-one-hub/ops-center/app`). The app reads only `app/`.
`auto_deploy` is off on purpose: a deploy that skips `config.env` starts the app on the
`app.yaml` defaults.

The bundle root is the Git folder `~/gsa-hackathon-mcp-creator-and-agent-for-cvn/the-one-hub/ops-center`.
The `dev` target sets `catalog: users` and `schema: xiaobing_shang1_civ`, so no `--var` flags
are needed.

To release a change:

1. Commit and push to `main`. The deploy uses what is on GitHub, not your uncommitted files.
2. From the Git folder: `databricks bundle deploy -t dev`, then
   `databricks bundle run aircarrier_front_center -t dev`.
3. Run the checks in the warning below.

Deploy from a CLI with a full user token (local machine or the workspace web terminal). From
the Genie Code serverless CLI, the app update fails with `Invalid delegation claim present in
Ctx` (400); the jobs still update. The fallback is a REST deployment with `git_source` and all
15 `env_vars` (see Environment variables below). That is how `01f1e478b83d` (2026-11-20, commit `f85836f`) was made.

The jobs are source-linked in dev mode: their task files and `--root` point at the Git folder,
so a job runs whatever the Git folder has checked out, including uncommitted edits. Anything a
job writes under `--root` (for example `app/data/rules.json` from `etl/build_rules.py`) shows up
as a change in the Git folder; commit it.

The old workspace copy (`~/the-one-hub/the-ops-center/.bundle/aircarrier/dev/files`) was moved
to trash on 2026-11-20; this Git folder is the only source. The bundle state still lives at
`~/the-one-hub/the-ops-center/.bundle/aircarrier/dev/state` (`root_path` comes from `ops_root`).
Do not delete it: without it the next `bundle deploy` creates duplicate jobs.

Rollback: a REST deployment with `git_source` pinned to an earlier `commit` (same
`source_code_path` `the-one-hub/ops-center/app`) and all 15 `env_vars`.

### Environment variables

* Bundle deploy applies the variables in `app.yml`.
* A direct REST deployment (`POST /api/2.0/apps/<name>/deployments`) does **not** carry
  forward the previous deployment's variables. Pass all 15 `env_vars` explicitly, or the app
  starts with no warehouse, catalog or models.

> **Warning: a deploy without the 15 variables still reports SUCCEEDED.** The app then falls
> back to the local defaults in `app/app.yaml` (`AIRCARRIER_DATA_BACKEND=files`, catalog
> `aircarrier.default`, no `DATABRICKS_WAREHOUSE_ID`, run history kept in memory only). It does
> not fail; it quietly gives wrong answers. This happened on 2026-11-12 and again on 2026-11-19
> (deployments `01f1e3bb1063` and `01f1e3bc00c0`): Brief readiness for CVN-79 reported 0 claims
> instead of 32, and the run was not saved. Fixed by deployment `01f1e3d515d1`, the last
> deployment from the workspace source.
>
> Only `bundle deploy` applies `resources/app.yml`. Treat `databricks apps deploy` and the
> **Deploy** button in the Apps UI as unsafe until proven otherwise, and run the checks below
> after using them.
>
> After any front-center deploy, check:
>
> 1. `GET /api/2.0/apps/aircarrier-front-center-dev/deployments/<id>` lists 15 `env_vars`
>    (names only; values are not returned).
> 2. The run log has no "No warehouse is bound" note, and Brief readiness counts the live
>    CVN-79 claims (32 as of 2026-11-19), not 0.
> 3. For a Git deployment, `git_source.resolved_commit` on the deployment is the commit you
>    pushed, and the app log shows `Cloning git repository`.

The Git folder (`main`) is the source of truth for the ops center and the front UI. To work
locally, clone this GitHub repository and pull before you deploy.

## Grants

Grant SQL lives in `the-one-hub/ops-center/deploy/` (`grants_*.sql`, `harness_authority.sql`).
Each app runs as its own service principal, so a live test as the owner can hide a missing
grant. Check the app's SP has `SELECT` on every table it reads.

## Keep this repository in sync

For the MCP apps and the creator, which still deploy from workspace folders: after deploying a
change, run `tools/sync_from_workspace.py`, review the diff in the Git folder, then commit and
push. Do not use it for `the-one-hub/ops-center`: the Git folder is now that project's source,
and syncing from the old bundle copy would overwrite newer repository files.
