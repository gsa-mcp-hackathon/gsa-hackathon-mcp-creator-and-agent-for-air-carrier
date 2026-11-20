# Transferring to Databricks, step by step

Written for a workspace that has nothing yet. Every step says what it does,
what it needs, and what it looks like when it fails. Run from the repo root.

```powershell
cd the-one-hub\ops-center          # from the root of your clone
```

---

## Step 0. Prerequisites, once per machine

```powershell
winget install Databricks.DatabricksCLI
pip install databricks-sdk
databricks auth login --host https://dbc-aae0ba16-8727.cloud.databricks.com --profile databricks-dev
databricks current-user me --profile databricks-dev
```

The `databricks` **pip** package is not the CLI and does not give you
`databricks bundle`. Check you have the real one, 0.287 or newer:

```powershell
databricks --version
```

---

## Step 1. Where it lands

The build needs a **catalog and a schema it can write to**. It creates
neither. Both are provisioned objects with storage and grants attached, and
in a governed workspace neither is a deployment's to make. What the build
owns is tables, views, volumes and jobs, all prefixed, all inside a schema
you point it at.

Find one you can write to:

```powershell
python tools\ensure_catalog.py --catalog users --schema <your.name> --profile databricks-dev
```

A personal schema under the `users` catalog is often the only thing a new
user owns outright, and it is enough. Then every later step carries the same
two flags:

```powershell
.\deploy\Deploy-ToDatabricks.ps1 -Mode Bundle -Catalog users -Schema <your.name> -Execute
```

Everything the build creates is prefixed `aircarrier_`, so it sits beside
whatever else is already in that schema without colliding. Change the prefix
with `-StorePrefix`.

### If you do own a catalog

Create one if you have `CREATE CATALOG`:

```powershell
python tools\ensure_catalog.py --catalog aircarrier --profile databricks-dev
```

It tries REST, then `CREATE CATALOG` over SQL, which is the route that works
on an account using Default Storage where the REST call fails with
`Metastore storage root URL does not exist`. If you have neither, the UI can
still do it: Catalog → Create → Catalog → Default Storage.

With a catalog of your own you can also use the seven-schema layout, which is
the cleaner model because the leads firewall becomes a grant rather than a
naming convention:

```powershell
Copy-Item resources-optional\schemas.yml resources\
```

That needs `CREATE SCHEMA` on the catalog.

---

## Step 2. The bundle: schemas, volumes, jobs, the app

```powershell
.\deploy\Deploy-ToDatabricks.ps1 -Mode Bundle              # prints the plan, changes nothing
.\deploy\Deploy-ToDatabricks.ps1 -Mode Bundle -Execute     # applies it
```

Creates two volumes, four jobs and the app definition. No schemas: see Step 1. Three
of the four jobs are paused on purpose: `aircarrier_events` and
`aircarrier_dispatcher` call entry points that still raise
`NotImplementedError`, and `aircarrier_ingest` runs on demand. Only
`aircarrier_tieout` is scheduled, because it is implemented.

This step does **not** move the documents and does **not** start the app.

---

## Step 3. The documents

```powershell
.\deploy\Deploy-ToDatabricks.ps1 -Mode Corpus -Execute
```

Uploads 38MB to `/Volumes/<catalog>/<schema>/<prefix>artifacts`, addressed by
sha256, then triggers the ingest job to build the index. Idempotent: each file
is checked by size and skipped if already there, so re-running after a partial
transfer costs nothing.

To see what would move without moving it:

```powershell
python tools\upload_corpus.py --dry-run
```

---

## Step 4. Start the app

```powershell
databricks apps start aircarrier-front-center-dev -p databricks-dev
databricks apps list -p databricks-dev
```

To rebuild the index on its own, without re-uploading:

```powershell
databricks bundle run aircarrier_ingest -t dev -p databricks-dev `
  --var=catalog=users --var=schema=<your.name> --var=store_prefix=aircarrier_
```

`databricks jobs run-now` takes a numeric `JOB_ID` and has no `--job-name`.
`bundle run` takes the resource key out of `databricks.yml`, which is stable
across the job being recreated.

A bundle deploy creates an app. It does not start one. The first start also
provisions a service principal and needs Unity Catalog grants, so budget
calendar time for it rather than minutes.

---

## Step 5. Check it

```powershell
python checks\gates.py --profile databricks-dev
```

Four gates: whether Apps is enabled, what the egress policy allows, whether
the sponsor can open it, whether budget execution is reachable. Read only, and
where a gate needs an admin action it prints the action instead of taking it.

Then open the app URL from `databricks apps list`. The pages to look at first
are `/dashboard`, `/gaps` and `/knowledge`.

---

## All of it in one go

Only once each step has worked separately at least once:

```powershell
.\deploy\Deploy-ToDatabricks.ps1 -Mode All -Execute
```

Order is Preflight → Catalog → Bundle → Corpus → Workspace → Git folder.

---

## Errors you may actually hit

| What it says | What it means | What to do |
|---|---|---|
| `The token '&&' is not a valid statement separator` | PowerShell 5.1 has no `&&` | use `;` or two lines |
| `Metastore storage root URL does not exist` | account uses Default Storage; REST cannot provision it | Step 1 SQL route, or 1a in the UI |
| `CATALOG_DOES_NOT_EXIST`, once per schema | Step 1 was skipped | run Step 1 |
| `does not have CREATE CATALOG on Metastore` | normal in a governed workspace | deploy into a catalog you have: `-Catalog users -Schema <your.name>` |
| `does not have CREATE SCHEMA on Catalog`, seven times | the seven-schema layout is opt-in and you do not have the grant | leave `resources-optional/schemas.yml` where it is; the default layout creates no schemas |
| `unknown field: description` / `expected bool, found string` | a key landed at the wrong indentation in `databricks.yml` | fixed; the line and column in the warning point straight at it |
| `Missing required cluster or environment settings` | a task has no serverless environment | fixed; if it returns, the task is missing `environment_key` |
| environment version rejected | this workspace offers different versions | change `serverless_env_version` in `databricks.yml` to one the error names |
| `Pattern X does not match any files` | a `sync.exclude` entry matches nothing | delete that entry; `.gitignore` is already honoured |
| app starts but search finds nothing | the index is in a volume the app cannot read | check `AIRCARRIER_KB_DIR` in `app/app.yaml` against the real volume path |
| `unknown flag: --job-name` | that flag does not exist; `jobs run-now` wants a JOB_ID | use `databricks bundle run aircarrier_ingest -t dev` |
| ingest reports every document MISSING | the volume is content addressed, `artifact_id/filename` | fixed; it tries both layouts. If it returns, compare a path in the volume against `corpus/MANIFEST.json` |
| gate output has garbled run-together words | a progress line was overwritten without being cleared | fixed |
| `PERMISSION_DENIED` on a schema | no `CREATE SCHEMA` in that catalog | use `-Catalog` with one you own |

---

## Dropping this into a different Databricks environment

Same five steps. Only three things change, and all three are flags or
variables rather than edits:

1. `--profile`, or `workspace.host` in `databricks.yml` for a new target.
2. `-Catalog`, `-Schema` and `-StorePrefix`.
3. For IL5: the three model service names and `serverless_env_version` in the
   `il5` target, and the adapter selection. `core/adapters/il5/` raises
   `NotImplementedError` from every method by design. That is the transfer
   checklist, written as code that fails loudly rather than as a document that
   goes stale.

Nothing in `ops/` or `app/` should need editing to move environments. If it
does, that is a finding worth recording rather than a patch worth making.
