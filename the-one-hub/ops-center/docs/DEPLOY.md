# Deploy

## The rule

Declarative Automation Bundles are the only deploy path. Nothing is created by
clicking in the workspace. Anything created outside the bundle does not
transfer, and transfer is the point.

```
databricks bundle validate -t dev
databricks bundle deploy   -t dev
databricks bundle run      -t dev aircarrier_tieout
databricks apps logs aircarrier-front-center-dev -p databricks-dev
```

Profile `databricks-dev`, host `https://dbc-aae0ba16-8727.cloud.databricks.com`.

## Two things that look like success and are not

Both of these were found against the real workspace, both reported a clean
deploy, and both are now handled by `deploy/Deploy-ToDatabricks.ps1`. They are
written down because the next person will otherwise spend the same afternoon.

### Deploying the app is not the same as deploying its files

`bundle deploy` uploads `app/` to the workspace. It does not hand those files
to the running app. An app is a long-lived process serving whatever source it
was last *deployed* with, and the CLI touches the app resource only when the
resource definition changes. Edit a template and nothing else, and the file
lands in the workspace while the container keeps serving the old tree.

What that looked like: every page returning 500 with
`jinja2.exceptions.TemplateNotFound: 'overview.html'`, while all eighteen
templates sat in `.bundle/aircarrier/dev/files/app/templates` the whole time.

`databricks apps start` does not fix it. Against an app that is already ACTIVE
it prints "already running", exits 0, and deploys nothing.

The fix is one command, and it must follow every deploy:

```
databricks bundle deploy -t dev <vars>
databricks bundle run aircarrier_front_center -t dev <vars>
```

`aircarrier_front_center` is the resource key in `resources/app.yml`, not the
deployed name `aircarrier-front-center-dev`. Pass the same `--var` flags: the
app's environment comes from `config.env`, which is resolved at that moment
and applied when the app starts.

### A serverless job entry point has no `__file__`

A serverless Python task does not run the file as a script. It reads the bytes
and `exec()`s them, so `__file__` is never bound and
`pathlib.Path(__file__).resolve().parents[2]` raises `NameError` at import
time, before `main()` is reached. The run aborts on a line that has nothing to
do with the work.

Every entry point takes `--root ${workspace.file_path}` from `resources/jobs.yml`
and resolves its root from that, falling back to `__file__` for a local run and
then to an upward walk from the working directory. Add the parameter whenever a
new entry point is added. `checks/` has a harness that executes an entry point
the way serverless does, with no `__file__` bound, which is the only way this
shows up before deployment.

## Targets

| Target | Workspace | State |
|---|---|---|
| `dev` | gsa-mcp-hackathon, commercial | active |
| `il5` | DoD Databricks | placeholder. Host, catalog and the three model services are supplied at transfer time |

Everything other than those four values is expected to be unchanged on
transfer. Nothing in `ops/` or `app/` should need editing.

## Workspace folder mapping

The repo uses clear names. The bundle deploys them into the workspace folders
already created:

| Repo | Workspace |
|---|---|
| `ops/` | `the-one-hub/the-ops-center` |
| `app/` | `the-one-hub/the-front-center` |

## The GitLab Dragon path

Advana FM requires its own GitLab repository with the Dragon pipeline to deploy
a Databricks App. That pipeline gets `app/` and nothing else, which is why
`app/` is a self-contained transfer unit and `core/` is vendored into it by
`tools/sync_core_to_app.py` before a build.

The bundle is what makes the pipeline a thin wrapper rather than a rewrite: the
CI job runs `databricks bundle deploy` against an accredited target, instead of
reconstructing the deployment in pipeline YAML.

Open items for that path, each a work item rather than a question:

1. The pipeline's required stages and hardened base image list, so the bundle
   is built against them rather than retrofitted.
2. Whether Databricks Apps is enabled in the target workspace and what the
   accreditation path for an App is.
3. The egress allowlist. Apps run on serverless compute and inherit serverless
   egress control. In a restricted workspace outbound is deny-by-default, and
   pypi.org plus files.pythonhosted.org must be allowlisted or the app build
   itself fails. Dependencies are vendored for this reason.

## Dependencies

`uv` manages the lock. The lock is what makes the build reproducible when
someone else redeploys it, and it is required at IL5 where PyPI is not
reachable at build time and wheels must be vendored.

```
uv sync
uv lock
```

## Platform constraints already verified

- Apps are reachable only by authenticated users in the same Databricks
  account. A sponsor without a workspace identity cannot open the link. Screen
  share plus static exports is the fallback.
- Apps run unprivileged. No system packages.
- Bind to `0.0.0.0` on `DATABRICKS_APP_PORT`. Support H2C. No custom TLS.
- A `*.databricksapps.mil` serving domain exists for AWS GovCloud DoD.

## Workspace risk

`gsa-mcp-hackathon` is a hackathon workspace. Prototyping there is fine. The
spine artifacts should not accumulate somewhere that may be reclaimed. Confirm
its lifespan and its Unity Catalog metastore before the claim ledger starts
carrying content that is expensive to rebuild.
