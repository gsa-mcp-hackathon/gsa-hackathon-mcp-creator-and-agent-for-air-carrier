"""Known-answer latency run against one deployed MCP server (round 10, B1).

Repeats the probe's known-answer call for the app (aircarrier-mcp-probe/probe.py
TARGETS), checks each answer with the probe's own check, and reports p50, p95,
p99 and max. 300 calls 6 s apart take 30 minutes, which crosses the docs
server's 30-minute cache expiry at least once: the case that used to take 12 s.

    python tools/latency_run.py --app mcp-aircarrier-docs
    python tools/latency_run.py --app mcp-aircarrier-hub --n 100 --interval 3 -p <profile>

Writes docs/submission/evidence/latency_<app>_<date>.json. Needs databricks-sdk
and requests, a Databricks CLI sign-in (`databricks auth login`) and CAN_USE on
the app.
"""

from __future__ import annotations

import argparse
import datetime
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "the-one-hub" / "ops-center" / "app" / "api"))
sys.path.insert(0, str(ROOT / "mcp-servers" / "aircarrier-mcp-probe"))

from mcp_host import McpHost, safe_mcp_url
from probe import TARGETS


def pct(values: list[float], q: float) -> float:
    s = sorted(values)
    return s[min(len(s) - 1, round(q * (len(s) - 1)))]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--app", required=True, choices=[t.app for t in TARGETS if t.tool])
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--interval", type=float, default=6.0, help="seconds between calls")
    ap.add_argument("-p", "--profile", default=None)
    args = ap.parse_args()
    target = next(t for t in TARGETS if t.app == args.app)

    import requests
    from databricks.sdk import WorkspaceClient

    w = WorkspaceClient(profile=args.profile)
    url = w.apps.get(args.app).url

    def post(u: str, headers: dict, body: dict) -> tuple[int, str]:
        r = requests.post(safe_mcp_url(u), headers=headers, json=body, timeout=120,
                          allow_redirects=False)
        return r.status_code, r.text

    host = McpHost(lambda _: url, w.config.authenticate, post, apps=[args.app]).connect()
    if host.unreachable:
        print(f"{args.app} unreachable: {host.unreachable[args.app]}")
        return 1

    calls = []
    for i in range(args.n):
        t0 = time.monotonic()
        body, _ = host.call(target.tool, target.args)
        ms = (time.monotonic() - t0) * 1000
        problem = body.get("error") if "error" in body else (target.check(body) if target.check else None)
        now = datetime.datetime.now(datetime.timezone.utc)  # noqa: UP017 - runs on Python 3.10
        calls.append({"i": i, "at": now.isoformat(timespec="seconds"), "ms": round(ms),
                      "ok": problem is None, "problem": problem})
        print(f"{i + 1:>4}/{args.n} {ms:8.0f} ms {'ok' if problem is None else problem}")
        time.sleep(max(0.0, args.interval - ms / 1000))

    ms = [c["ms"] for c in calls]
    summary = {"calls": len(calls), "right": sum(c["ok"] for c in calls),
               "p50_ms": statistics.median(ms), "p95_ms": pct(ms, 0.95),
               "p99_ms": pct(ms, 0.99), "max_ms": max(ms)}
    print(f"\n{args.app}: {summary['right']} of {summary['calls']} right; p50 {summary['p50_ms']:.0f} ms, "
          f"p95 {summary['p95_ms']} ms, p99 {summary['p99_ms']} ms, max {summary['max_ms']} ms")
    today = datetime.date.today().isoformat()
    out = ROOT / "docs" / "submission" / "evidence" / f"latency_{args.app}_{today}.json"
    out.write_text(json.dumps({"app": args.app, "tool": target.tool, "args": target.args,
                               "interval_s": args.interval, **summary, "per_call": calls},
                              indent=2) + "\n", encoding="utf-8")
    print(f"written: {out.relative_to(ROOT)}")
    return 0 if summary["right"] == summary["calls"] else 1


if __name__ == "__main__":
    sys.exit(main())
