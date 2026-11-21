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

Needs the Databricks CLI (0.250 or later) signed in with a full user token,
on your machine or in the workspace web terminal. The Genie Code serverless
CLI cannot update apps (docs/DEPLOYMENT.md). Standard library only.

Two things stay outside an app deployment, and the script says when either
changed: job code (the dev jobs run from the workspace Git folder, so Pull it)
and bundle resources (resources/*.yml, databricks.yml: `bundle deploy -t dev`).
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
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


def _apps(profile):
    data = _cli(profile, "apps", "list")
    return data if isinstance(data, list) else data.get("apps", [])


def _under(path: str, folder: str) -> bool:
    folder = folder.strip("/")
    return not folder or path == folder or path.startswith(folder + "/")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("-p", "--profile", help="Databricks CLI profile")
    ap.add_argument("--app", action="append", help="only this app (repeatable)")
    ap.add_argument("--all", action="store_true", help="redeploy even if unchanged")
    ap.add_argument("--dry-run", action="store_true", help="show the plan, deploy nothing")
    ap.add_argument("--branch", default=BRANCH)
    a = ap.parse_args()

    if not shutil.which("databricks"):
        sys.exit("The Databricks CLI is not on PATH. Install it, then `databricks auth login`.")

    src = Source(a.branch)
    print(f"GitHub {REPO} {a.branch} is at {src.head[:7]} (read via {src.mode}).")

    ours = [x for x in _apps(a.profile) if _norm((x.get("git_repository") or {}).get("url")) == REPO]
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
            d = _cli(a.profile, "apps", "deploy", name, "--json", json.dumps(body))
        except (RuntimeError, subprocess.TimeoutExpired) as e:
            print(f"  FAILED: {e}")
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
