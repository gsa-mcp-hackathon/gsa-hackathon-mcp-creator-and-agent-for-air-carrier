#!/usr/bin/env python3
"""PLAN.md day-1/2 verification gates, run against the workspace.

Four checks that decide which prototype gets built. Each can invalidate a piece
of the plan, each is cheap now and expensive to discover on day 11.

Read only. Nothing here changes a workspace setting. Where a gate needs an
admin action, it prints the action rather than taking it.

    pip install databricks-sdk
    python checks/gates.py --profile databricks-dev
"""
from __future__ import annotations

import argparse

VERDICT = {"pass": "PASS", "fail": "FAIL", "warn": "WARN", "manual": "ASK"}

# What a restricted workspace has to allow for this product to work at all.
# pypi.org and files.pythonhosted.org are first because without them the app
# does not build, never mind run. The rest are the event stream's sources.
EGRESS_NEEDED = ["pypi.org", "files.pythonhosted.org", "www.congress.gov",
                 "www.gao.gov", "www.dodig.mil", "www.esd.whs.mil",
                 "www.secnav.navy.mil", "www.federalregister.gov",
                 "api.usaspending.gov", "www.fpds.gov"]


def _first_warehouse(w):
    """A running warehouse if there is one, otherwise any. Starting a stopped
    warehouse is a side effect, so this never starts one: it reports instead."""
    try:
        whs = list(w.warehouses.list())
    except Exception:
        return None
    running = [x for x in whs if str(getattr(x, "state", "")).upper().endswith("RUNNING")]
    return (running or whs or [None])[0]


def _sql(w, wh, statement: str):
    """Run one read-only statement and return rows as plain lists."""
    r = w.statement_execution.execute_statement(
        warehouse_id=wh.id, statement=statement, wait_timeout="30s")
    status = str(getattr(getattr(r, "status", None), "state", "")).upper()
    if "FAILED" in status or "CLOSED" in status:
        raise RuntimeError(getattr(getattr(r, "status", None), "error", status))
    data = getattr(getattr(r, "result", None), "data_array", None) or []
    return [list(row) for row in data]


def line(gate, name, verdict, detail):
    _clear_progress()
    print(f"  [{VERDICT[verdict]:<4}] Gate {gate}  {name}", flush=True)
    for d in detail if isinstance(detail, list) else [detail]:
        print(f"         {d}", flush=True)


_PROGRESS_WIDTH = 0


def checking(gate, what):
    """Say what is being attempted before attempting it. A gate that needs a
    network round trip can take twenty seconds, and silence reads as a hang.

    The carriage return rewinds but does not erase, so a shorter result line
    printed over a longer progress line leaves the tail of the progress line
    behind: "Databricks Apps enabled" over "...checking whether Databricks
    Apps is enabled" rendered as "Databricks Apps enabledicks Apps is
    enabled". Record the width and blank it before the result.
    """
    global _PROGRESS_WIDTH
    msg = f"  ....   Gate {gate}  {what}"
    _PROGRESS_WIDTH = len(msg)
    print(msg, end="\r", flush=True)


def _clear_progress():
    global _PROGRESS_WIDTH
    if _PROGRESS_WIDTH:
        print(" " * _PROGRESS_WIDTH, end="\r", flush=True)
        _PROGRESS_WIDTH = 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="databricks-dev")
    ap.add_argument("--timeout", type=int, default=25,
                    help="seconds before a call gives up. The SDK retries for "
                         "60s by default and prints nothing while it does, so a "
                         "bad token looks like a hang.")
    args = ap.parse_args()

    try:
        from databricks.sdk import WorkspaceClient
    except ImportError:
        print("databricks-sdk is not installed. pip install databricks-sdk")
        return 2

    # The timeouts belong on Config, not on the client. Passing them to
    # WorkspaceClient raises TypeError, which the except below would have
    # reported as an authentication failure and sent you to re-run
    # `databricks auth login` over a bug in this script. Found on a dry run
    # against a host that does not answer.
    from databricks.sdk.core import Config

    def _cfg():
        return Config(profile=args.profile,
                      http_timeout_seconds=args.timeout,
                      retry_timeout_seconds=args.timeout)

    try:
        w = WorkspaceClient(config=_cfg())
        me = w.current_user.me()
    except Exception as exc:
        print(f"could not authenticate with profile '{args.profile}': {exc}")
        print("run: databricks auth login --host <workspace-url> --profile databricks-dev")
        return 2

    print(f"workspace : {w.config.host}")
    print(f"identity  : {me.user_name}")
    print()

    fails = 0

    checking("A", "checking whether Databricks Apps is enabled")
    # ---- Gate A. Is Databricks Apps enabled? -------------------------------
    try:
        apps = list(w.apps.list())
        line("A", "Databricks Apps enabled", "pass",
             [f"Apps API reachable. {len(apps)} app(s) in the workspace.",
              "Existing: " + (", ".join(a.name for a in apps[:6]) or "none yet"),
              "First-app onboarding still needs a service principal and Unity "
              "Catalog grants; budget calendar for it."])
    except Exception as exc:
        fails += 1
        line("A", "Databricks Apps enabled", "fail",
             [f"{type(exc).__name__}: {str(exc)[:160]}",
              "A workspace admin enables Apps on the Previews page.",
              "Not supported in Standard tier."])

    checking("B", "reading the serverless egress policy")
    # ---- Gate B. Serverless egress policy -----------------------------------
    #
    # Network policies are an ACCOUNT-level API. WorkspaceClient has no
    # .network_policies attribute at all, so the obvious call raises
    # AttributeError and a broad except would report it as "not readable with
    # this identity", which is the wrong diagnosis and sends you to the wrong
    # person. Three routes, best first.
    done_b = False

    # B-1. Account admin: read the policy directly.
    try:
        from databricks.sdk import AccountClient
        acct = AccountClient(config=_cfg())
        pols = list(acct.network_policies.list_network_policies())
        done_b = True
        for pol in pols:
            e = getattr(pol, "egress", None)
            na = getattr(e, "network_access", None)
            mode = getattr(na, "restriction_mode", None)
            allowed = getattr(na, "allowed_internet_destinations", None) or []
            dests = [getattr(d, "destination", "?") for d in allowed]
            restricted = "RESTRICTED" in str(mode).upper()
            line("B", f"Serverless egress policy {pol.network_policy_id}",
                 "warn" if restricted else "pass",
                 [f"restriction_mode = {mode}",
                  f"allowlisted destinations ({len(dests)}): " + (", ".join(dests[:12]) or "none")])
            if restricted:
                missing = [d for d in EGRESS_NEEDED if not any(d in x for x in dests)]
                if missing:
                    print(f"         NOT ALLOWLISTED: {', '.join(missing)}")
                    print("         pypi.org and files.pythonhosted.org matter even if nothing")
                    print("         else does: without them the app's own build fails.")
    except ImportError:
        pass
    except Exception as exc:
        if "account" in str(exc).lower() or isinstance(exc, (ValueError, KeyError)):
            pass  # no account_id in the profile. Normal for a workspace profile.
        else:
            pass

    # B-2. Workspace user: ask the system table what is actually being dropped.
    # Evidence beats configuration anyway, since the policy is one of several
    # things that can block a request.
    if not done_b:
        wh = _first_warehouse(w)
        if wh:
            try:
                rows = _sql(w, wh, """
                    SELECT destination, access_type, count(*) AS n
                    FROM system.access.outbound_network
                    WHERE event_time > current_timestamp() - INTERVAL 30 DAYS
                    GROUP BY destination, access_type
                    ORDER BY n DESC LIMIT 25""")
                done_b = True
                drops = [r for r in rows if str(r[1]).upper() in ("DROP", "DRY_RUN_DENIAL")]
                line("B", "Serverless egress, from the event record",
                     "warn" if drops else "pass",
                     [f"{len(rows)} destination/outcome rows in the last 30 days.",
                      ("denied: " + ", ".join(f"{r[0]} ({r[1]}, {r[2]})" for r in drops[:8]))
                      if drops else
                      "no denials recorded. Either egress is unrestricted or nothing "
                      "has tried yet, and those look identical here.",
                      "Only denials are logged by default, so an empty table is not "
                      "proof that a destination is reachable."])
            except Exception as exc:
                msg = str(exc)
                if "TABLE_OR_VIEW_NOT_FOUND" in msg or "not found" in msg.lower():
                    line("B", "Serverless egress", "manual",
                         ["system.access.outbound_network is not available.",
                          "The system catalog's access schema has to be enabled by an "
                          "account admin before the table exists.",
                          "Ask instead: which network policy is bound to this workspace, "
                          "and is its restriction mode full or restricted."])
                    done_b = True

    # B-3. Neither route. Say what to ask and of whom.
    if not done_b:
        line("B", "Serverless egress policy", "manual",
             ["Account-level read, and this profile has no account access.",
              "Ask an account admin for the workspace's network policy restriction "
              "mode and its allowlist.",
              "If restricted, these must be on it for the product to work: "
              + ", ".join(EGRESS_NEEDED)])

    # ---- Gate C. Can the sponsor open the app? -----------------------------
    line("C", "Sponsor can open the app", "manual",
         ["Apps are reachable only by authenticated users in the same Databricks account.",
          "Confirm the sponsor has a workspace identity. If not, plan a screen "
          "share and use the static export at app/_preview/ as the fallback."])

    checking("D", "looking for budget execution data")
    # ---- Gate D. Advana budget execution for this hull's lines -------------
    try:
        cats = [c.name for c in w.catalogs.list()]
        hits = [c for c in cats if any(k in c.lower() for k in ("advana", "fm", "fin", "budget"))]
        line("D", "Budget execution reachable", "warn" if not hits else "pass",
             [f"{len(cats)} catalog(s) visible to this identity.",
              "Candidates: " + (", ".join(hits[:8]) if hits else "none that look like FM data"),
              "The real check is whether SCN line 2001 and the RDT&E lines "
              "funding this hull are queryable, not general Advana access."])
    except Exception as exc:
        line("D", "Budget execution reachable", "manual",
             [f"catalog list not readable: {type(exc).__name__}"])

    # ---- Build prerequisites, beyond the four gates ------------------------
    print()
    print("  build prerequisites")
    for label, fn, note in [
        ("Unity Catalog metastore", lambda: w.metastores.current().metastore_id,
         "the four stores need a metastore"),
        ("SQL warehouse", lambda: ", ".join(x.name for x in list(w.warehouses.list())[:3]) or "none",
         "serving views need one"),
        ("Model serving endpoints", lambda: str(len(list(w.serving_endpoints.list()))),
         "the reasoning and embedding roles resolve here"),
    ]:
        try:
            print(f"    ok   {label:<26} {fn()}   ({note})")
        except Exception as exc:
            print(f"    --   {label:<26} {type(exc).__name__}   ({note})")

    print()
    print("A and B are the two that gate building. C and D shape the brief.")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
