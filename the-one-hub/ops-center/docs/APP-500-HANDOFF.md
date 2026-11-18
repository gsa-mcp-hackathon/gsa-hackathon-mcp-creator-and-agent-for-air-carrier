# Handoff: the app returns 500 on every page

Written 2026-11-08 after two failed fixes. Status is honest: one real bug was
found and fixed, a second remains, and I could not reach the workspace to
close it. Everything below is either evidence or a labelled hypothesis.

## The symptom

Every page returns 500. The traceback is the same every time:

```
jinja2.exceptions.TemplateNotFound: 'overview.html'
  not found in search path: '/app/python/source_code/templates'
```

Latest occurrence: deployment `01f1dbbb…`, 2026-11-08 16:33 EST, on an app
that was deleted and recreated an hour earlier.

## What is proven

1. **The templates exist locally and the bundle sends them.** The CLI's sync
   snapshot (`.databricks/bundle/dev/sync-snapshots/`) tracks 209 files,
   including all 18 of `app/templates/*.html`, each mapped to an identical
   remote name. They are excluded by neither `sync.exclude` nor `.gitignore`.

2. **The app code is correct.** Served with the container's own layout
   (`uvicorn main:app`, working directory = source root), all 21 pages return
   200 and `/api/search` returns 8 hits. `test_gate.py`, `test_agents.py` and
   `test_app.py` all pass.

3. **The container receives some of `app/`, not all of it.** It has `main.py`
   (it imported), `api/` (`from api import charts, data` succeeded) and
   `static/` (`StaticFiles(directory=...)` raises at import when the
   directory is absent, and the app started). It does not have
   `templates/*.html`. The failure is specific to one directory.

4. **The missing `bundle run` was a real bug and is fixed.** `bundle deploy`
   uploads files and does not restart the app, and `apps start` against an
   ACTIVE app is a no-op. The deploy script now runs
   `bundle run aircarrier_front_center`, and the log confirms it works:
   `Preparing source code for new app deployment` → `Downloading source code
   from …/src/01f1dbb3…` → `App started successfully`. That step was genuinely
   absent before and is genuinely present now. **It was not the whole cause.**

5. **The app environment is now correct.** Bundle state shows
   `AIRCARRIER_CATALOG=users`, `AIRCARRIER_SCHEMA=xiaobing_shang1_civ`,
   `AIRCARRIER_KB_DIR=/Volumes/users/xiaobing_shang1_civ/aircarrier_extracted/kb`.
   Previously these read `aircarrier`, `default`, and a volume path that
   existed in no deployment.

## What is ruled out

| Ruled out | Why |
|---|---|
| Stale app deployment | The app was deleted and recreated. Deployment `01f1dbbb…` is new and still fails. |
| Templates not uploaded | Present in the CLI sync snapshot with their extensions intact. |
| `sync.exclude` / `.gitignore` | Neither matches `app/templates`. Verified by reading both against the snapshot. |
| Per-file size limit | Databricks Apps rejects files over 10 MB **with a deployment error**. The largest file here is `app/data/kb/lexical.json` at 5.6 MB, and the deployment succeeded. |
| Wrong `source_code_path` | Bundle state records `…/.bundle/aircarrier/dev/files/app`, which is correct. |
| Application bug | Same code, same layout, 21/21 pages green locally. |

## What is still open

Two hypotheses survive the evidence. They have different fixes, so guessing
is expensive.

**A. The `.html` files are NOTEBOOK objects in the workspace, not FILE
objects.** Databricks treats `.html` as a notebook import format, and the
Databricks SDK documents that when a path is imported as a notebook *the
item's extension is automatically removed*. That would make `overview.html`
a notebook named `overview`, which never reaches the container as a template.
This is the only hypothesis that explains why `.py`, `.css`, `.js`, `.svg`,
`.jpg` and `.json` all survive and `.html` alone does not.

Against it: CLI 1.23.0 reverted bundle uploads to the legacy
`/workspace-files/import-file` endpoint, which should create plain files, and
1.24.0 is what you are running.

**B. The Apps source copy is dropping part of the tree.** `app/` is 14 MB,
9.7 MB of it `app/data/kb/`, and `templates/` sorts last alphabetically among
its directories. A truncated copy would lose exactly what is missing. No
documented aggregate limit supports this, which is why it is second.

## How to close it in one deploy

Two instruments were added for this. Both are read-only.

### 1. The container reports its own disk

`app/main.py` now prints an inventory at startup, before the first request,
and serves it at `/api/_diag`. Deploy and read the app log. One of three
lines will appear and each names a different cause:

| Log line | Means | Fix |
|---|---|---|
| `NO templates/ DIRECTORY` | the directory never arrived | hypothesis B. Go to step 3. |
| `templates/ EXISTS BUT IS EMPTY` | directory arrived, contents did not | hypothesis B. Go to step 3. |
| `templates/ HAS NO .html FILES. Found instead: [...]` | the names changed in transit | hypothesis A confirmed, and the listed names prove it. Go to step 4. |

A missing template now returns a readable 503 naming the directory and its
contents instead of a Jinja traceback, so the browser tells you the same
thing.

### 2. The workspace reports its object types

```
python tools\diagnose_app_deploy.py --profile databricks-dev
```

Lists every object under the app's `source_code_path` with its
`object_type`, compares to local, and prints a verdict. `NOTEBOOK` against
any template confirms hypothesis A outright. This needs only read access.

### 3. If hypothesis B

Take the 9.7 MB knowledge-base index out of the app source. It is the
largest thing there by far, and the design already says it belongs in a
volume: `AIRCARRIER_KB_DIR` points at
`/Volumes/users/xiaobing_shang1_civ/aircarrier_extracted/kb`, which the
ingest job writes. It ships inside `app/` only as a degraded fallback.

In `databricks.yml`:

```yaml
sync:
  exclude:
    - corpus/reference/**
    - corpus/imagery/**
    - app/_preview/**
    - app/data/kb/**        # 9.7MB. The volume is its home.
```

That takes `app/` from 14 MB to 4 MB. Redeploy and read `/api/_diag`. If
`templates/` appears, the copy was lossy and this is the fix.

### 4. If hypothesis A

Rename the templates off the `.html` extension. Jinja does not care about
the extension; the workspace does.

- `app/templates/*.html` → `app/templates/*.html.j2`
- the 20 `page(request, "x.html", …)` calls in `app/main.py`
- `{% extends %}` and `{% include %}` references inside the templates

This also protects the IL5 transfer, where the same import path runs. Say the
word and I will do the rename and test all 21 routes before you deploy.

## What I could not do

I could not reach `dbc-aae0ba16-8727.cloud.databricks.com` from this session.
The sandbox proxy refuses it (`403 from proxy after CONNECT`) and the Chrome
extension is not connected, so I had no way to list the workspace directory
or read the app's filesystem directly. Every statement above about the
workspace is inferred from the CLI's local state files and from your logs.
That inference took me to the right answer once and to a wrong one once.
The two instruments exist so the next step is observed rather than inferred.

## Current state of the repo

Changed and verified locally today:

| File | Change |
|---|---|
| `ops/entrypoints/ingest_job.py`, `tieout_job.py` | root resolved without `__file__`, which serverless does not bind |
| `resources/jobs.yml` | both tasks pass `--root ${workspace.file_path}` |
| `deploy/Deploy-ToDatabricks.ps1` | `bundle run` after every deploy |
| `resources/app.yml` | `config.env` bound to bundle variables |
| `app/app.yaml` | removed the dead `AIRCARRIER_KB_DIR` volume path |
| `app/main.py` | startup inventory, `/api/_diag`, readable 503, resilient `/api/search` |
| `checks/test_serverless_entrypoints.py` | new. Executes entry points the way serverless does |
| `tools/diagnose_app_deploy.py` | new. Workspace object-type diff |

The ingest job no longer raises `NameError`. Confirm its run finished and
wrote to the volume.
