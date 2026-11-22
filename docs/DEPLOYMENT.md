# Deployment

Every app deploys from this GitHub repository (branch `main`). There is no CI/CD deployment:
CI only runs the test suites. Databricks offers auto deploy on push only for private
repositories with the Databricks GitHub app, and this repository is public, so a deploy is one
command after the push. `~` below means `/Workspace/Users/xiaobing.shang1.civ@mail.mil`.

## Release a change

1. Commit and push to `main`.
2. Run, from a clone of this repository (or anywhere with Python and the Databricks CLI):

   ```
   python tools/deploy_from_github.py              # add -p <profile> if you use one
   ```

   It finds every app whose Git repository is this repo, compares the commit each app runs
   with `main` on GitHub for that app's own source folder, deploys only the apps whose folder
   changed, waits, and checks each new deployment succeeded at the pushed commit.
   `--dry-run` shows the plan; `--all` redeploys every app; `--app <name>` limits it.
   If the CLI's sign-in has expired, the script says so and prints the
   `databricks auth login` command to run. Inside a Databricks notebook it uses the
   Databricks SDK and your notebook sign-in instead of the CLI; the script's docstring has the
   two-line cell to run it there.
3. If the script reports job code changed, open the workspace Git folder
   `~/gsa-hackathon-mcp-creator-and-agent-for-cvn` and Pull (the dev jobs run from it). If it
   reports bundle files changed, then also run `databricks bundle deploy -t dev` from
   `the-one-hub/ops-center` in that folder.

Use a CLI with a full user token (your machine or the workspace web terminal). From the Genie
Code serverless CLI, app updates fail with `Invalid delegation claim present in Ctx` (400).

## App map

| App | Source folder in this repo | Resources attached | User scopes |
| --- | --- | --- | --- |
| `mcp-a-creator` | `mcp-server-creator/` | SQL warehouse, UC volume `storage`, MLflow experiment, trace tables (8) | sql, workspace.workspace, apps |
| `mcp-aircarrier-docs` | `mcp-servers/mcp-aircarrier-docs/` | SQL warehouse, 3 UC tables (pdf-pages, pdf-tables, artifacts) | - |
| `mcp-aircarrier-analyst` | `mcp-servers/mcp-aircarrier-analyst/` | SQL warehouse | - |
| `mcp-aircarrier-ops` | `mcp-servers/mcp-aircarrier-ops/` | SQL warehouse, 6 UC tables (2114 transactions and the variance register added 2026-11-20; see its `deploy/databricks/grants.sql`) | - |
| `aircarrier-mcp-probe` | `mcp-servers/aircarrier-mcp-probe/` | none (UC volume grant on the SP) | - |
| `mcp-bakehouse-sales` (app deleted 2026-11-21 for the hub's slot) | `mcp-servers/mcp-bakehouse-sales/` | SQL warehouse, 1 UC table | - |
| `aircarrier-front-center-dev` | `the-one-hub/ops-center/app/` | SQL warehouse, 4 serving endpoints (agent, reasoning, checker, fallback) | sql |
| `mcp-aircarrier-hub` | `the-one-hub/ops-center/` (its `app.yaml` runs `mcp/mcp_server.py`) | none: it reads the shipped files in `app/data`, `seed` and `core` | - |

The script reads each app's source folder from its active deployment, so the table is a
reference, not configuration. App names that start with `mcp-` appear in the Genie Code MCP
connector picker; the probe is named without the prefix on purpose.

### First deployment of `mcp-aircarrier-hub`

Done on 2026-11-21. The shared workspace is capped at 100 apps and was full, so the
`mcp-bakehouse-sales` app was deleted and the hub created in the same notebook cell, so the
slot was never left open. In a workspace with room, the steps are:

The script deploys apps that already exist. The hub is created once, with its Git source,
then `deploy_from_github.py` keeps it current like the others:

```
databricks apps create mcp-aircarrier-hub --json '{
  "description": "One Hub: the CVN-79 gate, policy checks, gap queue and cited corpus search as 16 read-only MCP tools",
  "git_repository": {"url": "https://github.com/llmlocalai/gsa-hackathon-mcp-creator-and-agent-for-cvn", "provider": "gitHub"}}'
databricks apps deploy mcp-aircarrier-hub --json '{"git_source": {"branch": "main", "source_code_path": "the-one-hub/ops-center"}}'
```

Then grant the probe's service principal `CAN_USE` on the app (Apps, `mcp-aircarrier-hub`,
Permissions). The probe lists it as a target, with `hub_check_claim` on the held $13,529M
baseline as its known answer (it must come back `human_review`).

Notes:

* `app.yaml` in each source folder sets the command and environment variables. A Git
  deployment with no `env_vars` runs on it.
* Resources (warehouse, tables, volume, experiment) are attached to the app, not stored in
  the code, and stay attached across deployments. A `PATCH` on the app replaces the whole
  object, so always send the description and all resources together.
* `mcp-aircarrier-ops` and `aircarrier-mcp-probe` must be redeployed together whenever an ops
  tool is renamed, because the probe calls ops tools by name (`--app` twice, or `--all`).

## The front UI (`aircarrier-front-center-dev`)

**Ask the evidence as an MCP host (from 2026-11-21).** With `AIRCARRIER_ASK_VIA_MCP=1` (set in
`app.yaml`) the `/ask` agent lists the tools of `mcp-aircarrier-docs`, `mcp-aircarrier-ops` and
`mcp-aircarrier-hub` and calls them over MCP as the front center's service principal
(`app/api/mcp_host.py`). Grant that service principal `CAN_USE` on each of the three apps
(Apps, the app, Permissions), as for the probe. Until the grants exist, every answer says
"in-app tools (MCP servers unreachable: ...)" and uses the in-app tools, so nothing breaks.
Check after deploying: ask one question; the tool-call line should read "via MCP: ..." and
each step should name its server.

Since 2026-11-20 `the-one-hub/ops-center/app/app.yaml` holds the full deployed set of 17
environment variables, equal to `config.env` in `the-one-hub/ops-center/resources/app.yml`
for the dev target. `checks/test_deploy_config.py` resolves `config.env` with the dev
variables and fails if the two disagree. So a plain Git deployment (the script, the Apps UI
Deploy button, or `databricks apps deploy`) starts the app on the live backend. A laptop run
does not read `app.yaml`: `uvicorn main:app` with nothing set uses the code defaults (files
backend, shipped extracts).

The bundle path still works and is the transfer path (il5 or another schema): `bundle deploy`
then `bundle run aircarrier_front_center`, which applies `config.env` over `app.yaml`. When
the catalog, schema or models change, change the bundle variables and `app.yaml` together.

The bundle root is the Git folder `~/gsa-hackathon-mcp-creator-and-agent-for-cvn/the-one-hub/ops-center`.
The `dev` target sets `catalog: users` and `schema: xiaobing_shang1_civ`, so no `--var` flags
are needed. The jobs are source-linked in dev mode: their task files and `--root` point at the
Git folder, so a job runs whatever the Git folder has checked out, including uncommitted edits.
Anything a job writes under `--root` (for example `app/data/rules.json` from
`etl/build_rules.py`) shows up as a change in the Git folder; commit it.

The bundle state lives at `~/the-one-hub/the-ops-center/.bundle/aircarrier/dev/state`
(`root_path` comes from `ops_root`). Do not delete it: without it the next `bundle deploy`
creates duplicate jobs.

Rollback: `python tools/deploy_from_github.py` cannot pin a commit; use
`databricks apps deploy <app> --json '{"git_source": {"commit": "<sha>", "source_code_path": "<folder>"}}'`.

### Environment variables

* Bundle deploy applies the variables in `app.yml`.
* A direct deployment (`POST /api/2.0/apps/<name>/deployments`, the CLI, the UI) does **not**
  carry forward the previous deployment's variables. With no `env_vars` it runs on
  `app/app.yaml`, which since 2026-11-20 holds the deployed values.

> **History: before 2026-11-20 a deploy without the 15 variables still reported SUCCEEDED.** The app then falls
> back to the local defaults in `app/app.yaml` (`AIRCARRIER_DATA_BACKEND=files`, catalog
> `aircarrier.default`, no `DATABRICKS_WAREHOUSE_ID`, run history kept in memory only). It does
> not fail; it quietly gives wrong answers. This happened on 2026-11-12 and again on 2026-11-19
> (deployments `01f1e3bb1063` and `01f1e3bc00c0`): Brief readiness for CVN-79 reported 0 claims
> instead of 32, and the run was not saved. Fixed by deployment `01f1e3d515d1`, the last
> deployment from the workspace source.
>
> `app/app.yaml` now carries the deployed values, so that fallback is the live backend. Still
> run the checks below after a deploy.
>
> After any front-center deploy, check:
>
> 1. `tools/deploy_from_github.py` reports SUCCEEDED at the pushed commit.
> 2. The run log has no "No warehouse is bound" note, and Brief readiness counts the live
>    CVN-79 claims (32 as of 2026-11-19), not 0.
> 3. The app log shows `Cloning git repository`, and the page footer reads
>    "Data backend: uc".

The Git folder (`main`) is the source of truth for the ops center and the front UI. To work
locally, clone this GitHub repository and pull before you deploy.

## Grants

Grant SQL lives in `the-one-hub/ops-center/deploy/` (`grants_*.sql`, `harness_authority.sql`).
Each app runs as its own service principal, so a live test as the owner can hide a missing
grant. Check the app's SP has `SELECT` on every table it reads.

## Keep this repository in sync

The apps and jobs deploy from this repository, so edit here and push. Only the Genie Code
skills still live in the workspace (`~/.assistant/skills`); `tools/sync_from_workspace.py`
copies those into the Git folder for review and commit.
