<#
.SYNOPSIS
    Put the Air Carrier build into a Databricks workspace.

.DESCRIPTION
    Three routes, because they are for different things and mixing them is the
    usual cause of a deployment that half works:

      Corpus     Uploads the 38MB of documents to the Unity Catalog volume
                 and then builds the knowledge base from them. Separate from
                 Bundle because it moves bytes rather than definitions, it is
                 idempotent, and you do not want it on every code deploy.
      Bundle     The real one. Deploys the Declarative Automation Bundle in
                 databricks.yml: schemas, volumes, jobs, and the app. This is
                 what IL5 will run through the Dragon pipeline.
      Workspace  A plain file copy into your user folder. For poking at
                 notebooks and for showing someone the code. Creates no jobs
                 and no app.
      GitFolder  Points a Databricks Git folder at the GitHub remote and pulls
                 it. Needs the commit pushed to GitHub first.

    Read only until you pass -Execute. Nothing here prints, stores or asks for
    a token: authentication comes from your CLI profile.

.PARAMETER DbProfile
    CLI profile name, passed as -Profile. Default databricks-dev.

.PARAMETER Mode
    Bundle | Workspace | GitFolder | All

.PARAMETER Target
    Bundle target from databricks.yml. dev or il5. Default dev.

.PARAMETER Catalog
    Unity Catalog catalog to deploy into. Created if missing and you hold
    CREATE CATALOG. Pass an existing one to create nothing.

.PARAMETER Schema
    Schema the stores live in. Not created by the bundle. Point it at one you
    can already write to.

.PARAMETER StorePrefix
    Prefixed to every table, view and volume the build owns.

.PARAMETER Execute
    Actually do it. Without this the script prints the plan and stops.

.EXAMPLE
    .\deploy\Deploy-ToDatabricks.ps1 -Mode Bundle
    .\deploy\Deploy-ToDatabricks.ps1 -Mode Bundle -Execute
    .\deploy\Deploy-ToDatabricks.ps1 -Mode Workspace -Execute
#>
[CmdletBinding()]
param(
    # Deliberately not named Profile. $PROFILE is a PowerShell automatic
    # variable holding the path to the user's profile script, and shadowing
    # it inside a script works until it does not. The alias keeps -Profile
    # working on the command line.
    [Alias("Profile")]
    [string] $DbProfile = "databricks-dev",
    [ValidateSet("Bundle", "Corpus", "Workspace", "GitFolder", "All")]
    [string] $Mode = "Bundle",
    [ValidateSet("dev", "il5")]
    [string] $Target = "dev",
    # Point at an existing catalog instead of creating one. Everything
    # downstream is parameterised, so this is a flag and never an edit.
    [string] $Catalog = "aircarrier",
    # The schema the stores live in. The bundle does not create it, for the
    # same reason it does not create the catalog. Point it at something you
    # can already write to; a personal schema under users works.
    [string] $Schema = "default",
    # Prefixed to every table, view and volume, so the seven logical stores
    # stay distinguishable inside one shared schema.
    [string] $StorePrefix = "aircarrier_",
    [string] $GitUrl = "https://github.com/icetonges/AirCarrier.git",
    [string] $Branch = "main",
    [switch] $Execute
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

function Say([string]$m, [string]$c = "Gray") { Write-Host $m -ForegroundColor $c }
function Head([string]$m) { Write-Host ""; Write-Host $m -ForegroundColor Cyan }

function Invoke-Db {
    # Runs the CLI and fails loudly.
    #
    # Two PowerShell traps here, both seen in real output.
    #
    # One: PowerShell does not stop on a non-zero exit code from a native
    # command, so every call has to check $LASTEXITCODE or a failed deploy
    # reports success.
    #
    # Two: with $ErrorActionPreference = "Stop", redirecting a native
    # command's stderr with 2>&1 makes PowerShell throw on the FIRST stderr
    # line, before $LASTEXITCODE is ever read. The CLI writes its errors to
    # stderr, so the script's own handling never ran and the user got a
    # NativeCommandError stack trace pointing at this line instead of the
    # actual Databricks error. Dropping to Continue for the duration of the
    # call is what lets the real message through.
    param([string[]] $DbArgs, [switch] $AllowFail)
    Say ("  would run: databricks " + ($DbArgs -join " ")) "DarkGray"
    if (-not $Execute) { return $null }

    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $out = & databricks @DbArgs 2>&1
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $prev
    }

    if ($code -ne 0 -and -not $AllowFail) {
        Write-Host ""
        Say "  databricks $($DbArgs[0]) $($DbArgs[1]) failed (exit $code):" "Red"
        $out | ForEach-Object { Say ("    " + $_.ToString()) "Red" }
        throw "databricks $($DbArgs[0]) failed with exit code $code"
    }
    return $out
}

# ---------------------------------------------------------------- preflight
Head "Preflight"

$cli = Get-Command databricks -ErrorAction SilentlyContinue
if (-not $cli) {
    Say "  databricks CLI not found on PATH." "Red"
    Say "  Install:  winget install Databricks.DatabricksCLI" "Yellow"
    Say "  The 'databricks' pip package is NOT the CLI. It is a different, older thing." "Yellow"
    exit 1
}
$ver = (& databricks --version) -join " "
Say "  CLI        $ver"
# The CLI went 0.x -> 1.x, so a check that only understood 0.287 silently
# passed every 1.x build and would have warned on nothing.
if ($ver -match "v(\d+)\.(\d+)\.") {
    $maj = [int]$Matches[1]
    $min = [int]$Matches[2]
    if ($maj -lt 1 -and $min -lt 294) {
        Say "  CLI is older than 0.294. serverless environment_version needs 0.294+," "Yellow"
        Say "  and bundles were renamed Declarative Automation Bundles at 0.287." "Yellow"
        Say "  Update it:  winget upgrade Databricks.DatabricksCLI" "Yellow"
    }
}

Say "  Profile    $DbProfile"
$who = & databricks current-user me --profile $DbProfile --output json 2>&1
if ($LASTEXITCODE -ne 0) {
    Say "  Cannot authenticate with profile '$DbProfile'." "Red"
    Say "  Run:  databricks auth login --host https://dbc-aae0ba16-8727.cloud.databricks.com --profile $DbProfile" "Yellow"
    exit 1
}
$me = ($who | ConvertFrom-Json).userName
Say "  Identity   $me" "Green"

if (-not (Test-Path (Join-Path $repo "databricks.yml"))) { throw "databricks.yml not found in $repo" }
Say "  Repo       $repo"

if (-not $Execute) {
    Say ""
    Say "  DRY RUN. Nothing will be changed. Add -Execute to apply." "Yellow"
}

# Variable overrides, shared by every mode that shells out to the CLI.
$vars = @("--var=catalog=$Catalog", "--var=schema=$Schema",
          "--var=store_prefix=$StorePrefix")

# ---------------------------------------------------------------- catalog
# The bundle declares seven schemas and two volumes, and every one of them
# fails with CATALOG_DOES_NOT_EXIST on a first deploy into a fresh workspace.
# Seven identical 404s read like a broken bundle; they are one missing
# precondition. Check it first and say so in one line.
if ($Mode -eq "Bundle" -or $Mode -eq "Corpus" -or $Mode -eq "All") {
    Head "Target: $Catalog.$Schema"
    Say "  would run: python tools\ensure_catalog.py --catalog $Catalog --schema $Schema --profile $DbProfile" "DarkGray"
    if ($Execute) {
        python tools\ensure_catalog.py --catalog $Catalog --schema $Schema --profile $DbProfile
        if ($LASTEXITCODE -ne 0) {
            Say ""
            Say "  Stopping before the bundle. Deploying into a catalog that does not" "Red"
            Say "  exist produces one 404 per schema and leaves a half-created bundle." "Red"
            throw "catalog '$Catalog' is not available"
        }
    }
}

# ---------------------------------------------------------------- bundle
if ($Mode -eq "Bundle" -or $Mode -eq "All") {
    Head "Bundle -> target '$Target'"
    Say "  Validate first. A bundle that validates can still fail to deploy, but"
    Say "  one that does not validate always does, and the error is clearer here."
    # --var=key=value as one token. The space-separated form usually parses
    # too, but PowerShell array splatting plus two levels of = is exactly
    # where a quoting surprise would land, and this form is unambiguous.
    Invoke-Db (@("bundle", "validate", "-t", $Target, "-p", $DbProfile) + $vars)
    Invoke-Db (@("bundle", "deploy", "-t", $Target, "-p", $DbProfile) + $vars)
    if ($Execute) {
        Say "  Deployed. Resources land under /Workspace/Users/$me/.bundle/aircarrier/$Target" "Green"
    }

    # bundle deploy puts the app's files in the workspace. It does not give
    # them to the running app, and this is the single most expensive thing to
    # get wrong here, because every signal says success.
    #
    # An app is a long-lived process serving whatever source it was last
    # deployed with. bundle deploy touches the app resource only when the
    # resource definition changes, so editing a template and nothing else
    # uploads the file and leaves the container on the old tree. That is what
    # produced "jinja2.exceptions.TemplateNotFound: overview.html" against a
    # deploy that reported success, with all eighteen templates sitting in the
    # workspace the whole time.
    #
    # 'databricks apps start' does not fix it. On an app that is already
    # ACTIVE it prints "already running", exits 0, and deploys nothing. That
    # is what the previous version of this script told people to run.
    #
    # 'bundle run' against the app's RESOURCE KEY, aircarrier_front_center,
    # not the deployed name aircarrier-front-center-dev, creates a new code
    # deployment from the synced source and restarts the app on it. It is
    # also the only thing that applies config.env, because environment
    # variables are read at start. $vars has to come along: without it the
    # app would be started with the default catalog and schema rather than
    # the ones this deploy used.
    Head "App -> new code deployment and restart"
    Say "  Uploading files is not deploying the app. Without this the app"
    Say "  keeps serving the previous source and the deploy looks clean."
    Invoke-Db (@("bundle", "run", "aircarrier_front_center", "-t", $Target, "-p", $DbProfile) + $vars)
    if ($Execute) {
        Say "  App restarted on the code just deployed." "Green"
    }
}

# ---------------------------------------------------------------- corpus
if ($Mode -eq "Corpus" -or $Mode -eq "All") {
    Head "Corpus -> Unity Catalog volume"
    Say "  38MB of PDFs, zips and photographs. Content addressed by sha256, so"
    Say "  re-running skips anything already there."
    Say "  would run: python tools\upload_corpus.py --profile $DbProfile" "DarkGray"
    if ($Execute) {
        python tools\upload_corpus.py --profile $DbProfile --volume "/Volumes/$Catalog/$Schema/${StorePrefix}artifacts"
        if ($LASTEXITCODE -ne 0) { throw "corpus upload failed with exit code $LASTEXITCODE" }
        Say "  Uploaded. Now build the index from it:" "Green"
        # bundle run takes the resource key from databricks.yml. jobs run-now
        # takes a numeric JOB_ID and has no --job-name, and the id changes
        # whenever the job is recreated, so the key is the stable handle.
        Invoke-Db (@("bundle", "run", "aircarrier_ingest", "-t", $Target, "-p", $DbProfile) + $vars) -AllowFail
    }
}

# ---------------------------------------------------------------- workspace
if ($Mode -eq "Workspace" -or $Mode -eq "All") {
    Head "Workspace file copy"
    $dest = "/Workspace/Users/$me/AirCarrier"
    Say "  Destination $dest"
    Say "  Not /Repos/... on purpose: importing into a Git-folder-managed path"
    Say "  is unsupported and fails silently, leaving a stale copy behind."
    Invoke-Db @("workspace", "mkdirs", $dest, "-p", $DbProfile) -AllowFail
    Invoke-Db @("workspace", "import-dir", ".", $dest, "--overwrite", "-p", $DbProfile)
    if ($Execute) { Say "  Copied." "Green" }
}

# ---------------------------------------------------------------- git folder
if ($Mode -eq "GitFolder" -or $Mode -eq "All") {
    Head "Git folder"

    $dirty = & git -C $repo status --porcelain
    if ($LASTEXITCODE -eq 0 -and $dirty) {
        Say "  Uncommitted changes in the working tree:" "Yellow"
        $dirty | Select-Object -First 8 | ForEach-Object { Say ("    " + $_) "Yellow" }
        Say "  A Git folder pulls from GitHub, so anything not pushed will not arrive." "Yellow"
    }
    $local = (& git -C $repo rev-parse --short HEAD 2>$null)
    if ($LASTEXITCODE -eq 0) { Say "  Local HEAD  $local" }

    $path = "/Repos/$me/AirCarrier"
    Say "  Folder      $path"
    $existing = & databricks repos list --path-prefix $path -p $DbProfile --output json 2>&1
    $found = $false
    if ($LASTEXITCODE -eq 0) {
        try { $found = (($existing | ConvertFrom-Json).repos | Measure-Object).Count -gt 0 } catch { $found = $false }
    }
    if ($found) {
        Say "  Exists. Pulling branch '$Branch'."
        Invoke-Db @("repos", "update", $path, "--branch", $Branch, "-p", $DbProfile)
    } else {
        Say "  Does not exist. Creating, linked to $GitUrl."
        Say "  A Git folder created from the CLI must be linked to a remote. One"
        Say "  created in the browser need not be, which is why they behave differently."
        Invoke-Db @("repos", "create", $GitUrl, "gitHub", "--path", $path, "-p", $DbProfile)
    }
}

Head "Next"
if (-not $Execute) {
    Say "  Re-run with -Execute to apply."
} else {
    Say "  Verify the gates:  python checks\gates.py --profile $DbProfile" "Green"
    if ($Mode -eq "Bundle" -or $Mode -eq "All") {
        Say "  Open the app:      databricks apps list -p $DbProfile" "Green"
        Say "  If a page 500s, read the app log before redeploying. A stale app" "Gray"
        Say "  is no longer possible from this script, so a 500 now means code." "Gray"
    }
}
