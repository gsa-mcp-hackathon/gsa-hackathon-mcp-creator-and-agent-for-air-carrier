# Deploy

```powershell
cd C:\Users\Peter-HP\git\AirCarrier\dbrepo
.\deploy\Deploy-ToDatabricks.ps1 -Mode Bundle            # prints the plan, changes nothing
.\deploy\Deploy-ToDatabricks.ps1 -Mode Bundle -Execute   # applies it
```

Nothing runs until you pass `-Execute`. The script never prints, stores or
asks for a token. Authentication comes from your CLI profile.

## Three modes, for three different things

**`-Mode Bundle`** is the real one. Deploys `databricks.yml`: schemas, volumes,
jobs and the app. This is the path IL5 will take through the Dragon pipeline,
so keep it working even when a file copy would be quicker.

**`-Mode Workspace`** copies files into `/Workspace/Users/<you>/AirCarrier`. For
reading code in the browser. Creates no jobs and no app. It deliberately does
not target `/Repos/...`, because importing into a Git-folder-managed path is
unsupported and fails silently, leaving a stale copy that looks current.

**`-Mode GitFolder`** points a Databricks Git folder at the GitHub remote and
pulls. Push to GitHub first or nothing arrives. A Git folder created from the
CLI must be linked to a remote; one created in the browser need not be, which
is why the two behave differently.

## First run

```powershell
winget install Databricks.DatabricksCLI
databricks auth login --host https://dbc-aae0ba16-8727.cloud.databricks.com --profile databricks-dev
databricks current-user me --profile databricks-dev
```

The `databricks` pip package is not this CLI. It is a different and older
thing, and having it installed does not give you `databricks bundle`.

Get CLI 0.287 or newer. Asset Bundles were renamed Declarative Automation
Bundles at that version. Older CLIs still accept `bundle` but drift from what
`databricks.yml` expects.

## After deploying

```powershell
databricks apps start aircarrier -p databricks-dev
python checks\gates.py --profile databricks-dev
```

A bundle deploy creates the app. It does not start it.

## IL5

`-Target il5` exists in `databricks.yml` as a placeholder and is not wired to a
real host. The transfer boundary is `core/adapters/il5/`, where every method
raises `NotImplementedError`. That is the checklist, written as code that fails
loudly rather than as a document that goes stale. The serving domain for AWS
GovCloud DoD is `*.databricksapps.mil`.
