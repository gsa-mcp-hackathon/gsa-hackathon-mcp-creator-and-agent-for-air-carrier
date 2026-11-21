"""Redeploy every Databricks app that runs from this GitHub repo, after a push.

One command after `git push`. For each app whose Git repository is this repo:

1. Read the commit the app runs now (active deployment, resolved_commit).
2. Compare it with the head of the branch on GitHub, for the app's own source
   folder only (git_source.source_code_path).
3. If that folder changed, start a Git deployment of the branch and wait for it.
4. Check the new deployment succeeded and runs the commit that is on GitHub.

Apps whose folder did not change are left alone. Nothing is read from your
working folder: the deploy uses what is on GitHub, so push first.

    python tools/deploy_from_github.py                 # deploy what changed
    python tools/deploy_from_github.py --dry-run       # show what would deploy
    python tools/deploy_from_github.py --all           # redeploy every app
    python tools/deploy_from_github.py --app mcp-aircarrier-docs
    python tools/deploy_from_github.py -p databricks-dev   # CLI profile

In a Databricks notebook cell (uses the SDK and signs in as you):

    import runpy, sys
    sys.argv = ["deploy", "--dry-run"]        # or [] to deploy
    runpy.run_path("/Workspace/Users/<you>/gsa-hackathon-mcp-creator-and-agent-for-cvn/tools/deploy_from_github.py", run_name="__main__")

Needs the Databricks CLI (0.250 or later) signed in with a full user token,
on your machine or in the workspace web terminal, or the databricks-sdk package
(preinstalled in Databricks notebooks). The Genie Code serverless CLI cannot
update apps (docs/DEPLOYMENT.md). No other dependencies.

Two things stay outside an app deployment, and the script says when either
changed: job code (the dev jobs run from the workspace Git folder, so Pull it)
and bundle resources (resources/*.yml, databricks.yml: `bundle deploy -t dev`).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

REPO = "llmlocalai/gsa-hackathon-mcp-creator-and-agent-for-cvn"
BRANCH = "main"
# Changes here need `databricks bundle deploy -t dev` from the workspace Git
# folder, not an app deployment.
BUNDLE_PATHS = (
    "the-one-hub/ops-center/resources/",
    "the-one-hub/ops-center/databricks.yml",
)
# The dev jobs are source-linked: they run what the workspace Git folder has
# checked out, so a change here needs a Pull in that folder, nothing else.
JOB_PATHS = (
    "the-one-hub/ops-center/ops/",
    "the-one-hub/ops-center/etl/",
    "the-one-hub/notebooks/",
)


def _norm(url: str) -> str:
    u = (url or "").strip().lower().rstrip("/")
    u = u.removesuffix(".git")
    return u.split("github.com/")[-1]


def _gh(path: str):
    req = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}/{path}",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "deploy-from-github"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout.strip()


class Source:
    """Head commit and changed files, from the GitHub API or a local clone."""

    def __init__(self, branch: str):
        self.branch = branch
        self.mode = "github"
        try:
            self.head = _gh(f"commits/{branch}")["sha"]
        except (urllib.error.URLError, KeyError, TimeoutError) as e:
            if not shutil.which("git"):
                sys.exit(f"Cannot reach the GitHub API ({e}) and git is not installed.")
            self.mode = "git"
            _git("fetch", "-q", f"https://github.com/{REPO}.git", branch)
            self.head = _git("rev-parse", "FETCH_HEAD")
            if _git("rev-list", "--count", "FETCH_HEAD..HEAD") != "0":
                print(f"Note: your local {branch} has commits that are not on GitHub. "
                      "They will not deploy until you push.")

    def changed(self, base: str) -> list[str] | None:
        """Files changed from base to head, or None when base is unknown."""
        if not base:
            return None
        if base == self.head:
            return []
        try:
            if self.mode == "github":
                cmp = _gh(f"compare/{base}...{self.head}")
                if cmp.get("status") == "diverged" and not cmp.get("files"):
                    return None
                return [f["filename"] for f in cmp.get("files", [])]
            return _git("diff", "--name-only", base, self.head).splitlines()
        except (urllib.error.URLError, subprocess.CalledProcessError):
            return None


def _cli(profile: str | None, *args: str, timeout: int = 1500):
    cmd = ["databricks", *args, "-o", "json"]
    if profile:
        cmd += ["-p", profile]
    r = subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=timeout)
    if r.returncode:
        raise RuntimeError((r.stderr or r.stdout).strip()[:600])
    return json.loads(r.stdout) if r.stdout.strip() else {}


class CliBackend:
    """The Databricks CLI on your machine or in the workspace web terminal."""

    name = "Databricks CLI"

    def __init__(self, profile):
        self.profile = profile

    def list_apps(self):
        data = _cli(self.profile, "apps", "list")
        return data if isinstance(data, list) else data.get("apps", [])

    def deploy(self, name, body):
        return _cli(self.profile, "apps", "deploy", name, "--json", json.dumps(body))


class SdkBackend:
    """The Databricks SDK, for a Databricks notebook (it signs in as you there)
    or any machine without the CLI. Calls the Apps REST API directly, so an
    older SDK without Git deployment types still works."""

    name = "Databricks SDK"

    def __init__(self, profile):
        from databricks.sdk import WorkspaceClient
        self.w = WorkspaceClient(profile=profile) if profile else WorkspaceClient()

    def list_apps(self):
        out, token = [], None
        while True:
            r = self.w.api_client.do("GET", "/api/2.0/apps",
                                     query={"page_token": token} if token else None) or {}
            out += r.get("apps", [])
            token = r.get("next_page_token")
            if not token:
                return out

    def deploy(self, name, body, timeout_s=1500):
        d = self.w.api_client.do("POST", f"/api/2.0/apps/{name}/deployments", body=body) or {}
        dep, start = d.get("deployment_id"), time.monotonic()
        while dep and ((d.get("status") or {}).get("state") in (None, "IN_PROGRESS", "PENDING")):
            if time.monotonic() - start > timeout_s:
                raise RuntimeError(f"still in progress after {timeout_s}s (deployment {dep})")
            time.sleep(10)
            d = self.w.api_client.do("GET", f"/api/2.0/apps/{name}/deployments/{dep}") or {}
        return d


def _backend(profile, via):
    has_cli = bool(shutil.which("databricks"))
    in_databricks = bool(os.environ.get("DATABRICKS_RUNTIME_VERSION"))
    if via == "cli" or (via == "auto" and has_cli and not in_databricks):
        if not has_cli:
            sys.exit("The Databricks CLI is not on PATH. Install it, then `databricks auth login`.")
        return CliBackend(profile)
    try:
        return SdkBackend(profile)
    except ImportError:
        sys.exit("Neither the Databricks CLI nor the databricks-sdk package is available. "
                 "Install one: https://docs.databricks.com/dev-tools/cli/install.html")


def _auth_help(err: str, profile) -> str:
    low = err.lower()
    if "refresh token is invalid" in low or "auth login" in low or "unauthenticated" in low \
            or "invalid access token" in low or "401" in low:
        p = f" --profile {profile}" if profile else ""
        m = re.search(r"databricks auth login[^\n]*", err)
        cmd = m.group(0).strip() if m else f"databricks auth login{p}"
        return ("Your Databricks sign-in has expired. Sign in again, then rerun:\n"
                f"  {cmd}\n  python tools/deploy_from_github.py{p}")
    return f"Could not list apps: {err}"


def _under(path: str, folder: str) -> bool:
    folder = folder.strip("/")
    return not folder or path == folder or path.startswith(folder + "/")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("-p", "--profile", help="Databricks CLI profile")
    ap.add_argument("--via", choices=("auto", "cli", "sdk"), default="auto",
                    help="auto: the CLI on a machine, the SDK inside Databricks")
    ap.add_argument("--app", action="append", help="only this app (repeatable)")
    ap.add_argument("--all", action="store_true", help="redeploy even if unchanged")
    ap.add_argument("--dry-run", action="store_true", help="show the plan, deploy nothing")
    ap.add_argument("--branch", default=BRANCH)
    # In a notebook the kernel passes its own arguments (-f connection.json);
    # ignore what is not ours rather than stop.
    a, _unknown = ap.parse_known_args(argv)

    api = _backend(a.profile, a.via)
    src = Source(a.branch)
    print(f"GitHub {REPO} {a.branch} is at {src.head[:7]} (read via {src.mode}).")

    try:
        apps = api.list_apps()
    except (RuntimeError, subprocess.TimeoutExpired, OSError) as e:
        print(_auth_help(str(e), a.profile))
        return 2
    except Exception as e:  # noqa: BLE001 - SDK errors: say what failed, no traceback
        print(_auth_help(f"{type(e).__name__}: {e}", a.profile))
        return 2
    print(f"Using the {api.name}.")
    ours = [x for x in apps if _norm((x.get("git_repository") or {}).get("url")) == REPO]
    if a.app:
        ours = [x for x in ours if x["name"] in a.app]
    if not ours:
        print("No app here deploys from this repository. Check the profile (-p) and app names.")
        return 1

    plan, all_changed = [], set()
    for x in sorted(ours, key=lambda x: x["name"]):
        gs = ((x.get("active_deployment") or {}).get("git_source")) or {}
        folder = gs.get("source_code_path") or ""
        if not gs:
            print(f"  {x['name']:<30} skip: its active deployment is not from Git. Deploy it once "
                  "from the Apps UI (Deploy > From Git) so its source folder is known.")
            continue
        base = gs.get("resolved_commit") or ""
        files = src.changed(base)
        if files is not None:
            all_changed.update(files)
        mine = None if files is None else [f for f in files if _under(f, folder)]
        if a.all:
            why, go = "forced (--all)", True
        elif files is None:
            why, go = f"deployed commit {base[:7] or 'unknown'} not comparable", True
        elif mine:
            why, go = f"{len(mine)} file(s) changed in {folder}/", True
        else:
            why, go = "up to date" if base == src.head else f"no change in {folder}/", False
        pin = gs.get("commit") or gs.get("tag")
        if pin and not gs.get("branch"):
            # A deployment pinned to a commit or tag repeats that ref on every
            # redeploy from the UI, so the app never moves. Deploy the branch.
            why += f"; pinned to {'commit ' + pin[:7] if gs.get('commit') else 'tag ' + pin}, will deploy {a.branch}"
            go = go or base != src.head
        print(f"  {x['name']:<30} {base[:7] or '-------'} -> {src.head[:7]}  {why}")
        if go:
            plan.append((x["name"], folder, gs.get("branch") or a.branch))

    jobs = sorted(f for f in all_changed if f.startswith(JOB_PATHS))
    if jobs:
        print("\nJob code changed. The dev jobs run from the workspace Git folder: open it and "
              "Pull.\n  changed: " + ", ".join(jobs[:8]))
    bundle = sorted(f for f in all_changed if f.startswith(BUNDLE_PATHS))
    if bundle:
        print("\nBundle files changed (job or app resources). After a Pull, run from the "
              "workspace Git folder the-one-hub/ops-center:\n"
              "  databricks bundle deploy -t dev\n  changed: " + ", ".join(bundle[:8]))

    if a.dry_run or not plan:
        print("\nNothing deployed." if not plan else "\nDry run: nothing deployed.")
        return 0

    failed = []
    for name, folder, branch in plan:
        print(f"\nDeploying {name} from {branch}:{folder} ...", flush=True)
        body = {"git_source": {"branch": branch, "source_code_path": folder}}
        try:
            d = api.deploy(name, body)
        except (RuntimeError, subprocess.TimeoutExpired) as e:
            print(f"  FAILED: {e}")
            failed.append(name)
            continue
        except Exception as e:  # noqa: BLE001 - SDK errors name themselves
            print(f"  FAILED: {type(e).__name__}: {e}")
            failed.append(name)
            continue
        state = ((d.get("status") or {}).get("state")) or "?"
        got = ((d.get("git_source") or {}).get("resolved_commit")) or ""
        ok = state == "SUCCEEDED" and got == src.head
        print(f"  {state}, deployment {d.get('deployment_id', '?')}, commit {got[:7] or '?'}"
              + ("" if ok else f"  (expected SUCCEEDED at {src.head[:7]})"))
        if not ok:
            failed.append(name)

    print("\nDone." if not failed else f"\nNeeds a look: {', '.join(failed)}. "
          "`databricks apps logs <name>` shows why.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
