"""Measure tie-outs on the deployed docs server's store, every document.

Calls mcp-aircarrier-docs over MCP as you: docs_list_documents, then
docs_tieout_document for each document. Sums the checks, prints a table and
writes the result to docs/submission/evidence/tieout_store_<date>.json.

    python tools/measure_store_tieouts.py                  # default CLI profile
    python tools/measure_store_tieouts.py -p <profile>     # a named profile

Needs the databricks-sdk and requests packages and a Databricks CLI sign-in
that can use the app (`databricks auth login`), the same sign-in
deploy_from_github.py uses. Your user needs CAN_USE on mcp-aircarrier-docs.
Run it after the docs server is redeployed at the commit you want measured.
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "the-one-hub" / "ops-center" / "app" / "api"))

from mcp_host import TIMEOUT_S, McpHost, safe_mcp_url

APP = "mcp-aircarrier-docs"


def _rows(body: dict | list) -> list:
    """A list result arrives as structured content {'result': [...]}."""
    if isinstance(body, dict) and "error" in body:
        raise RuntimeError(body["error"])
    return body.get("result", []) if isinstance(body, dict) else body


def _commit(app) -> str | None:
    """The commit the app's active deployment runs, as deploy_from_github.py reads it."""
    try:
        d = app.as_dict().get("active_deployment") or {}
        return (d.get("git_source") or {}).get("resolved_commit")
    except AttributeError:
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("-p", "--profile", default=None, help="Databricks CLI profile")
    args = ap.parse_args()

    import requests
    from databricks.sdk import WorkspaceClient

    w = WorkspaceClient(profile=args.profile)
    app = w.apps.get(APP)

    def post(url: str, headers: dict, body: dict) -> tuple[int, str]:
        r = requests.post(safe_mcp_url(url), headers=headers, json=body,
                          timeout=max(TIMEOUT_S, 300), allow_redirects=False)
        return r.status_code, r.text

    host = McpHost(lambda _: app.url, w.config.authenticate, post, apps=[APP]).connect()
    if host.unreachable:
        print(f"{APP} unreachable: {host.unreachable[APP]}")
        return 1

    docs, _ = host.call("docs_list_documents", {})
    rows, totals = [], {"checks": 0, "passed": 0, "failed": 0,
                        "failed_within_rounding_bound": 0}
    for d in _rows(docs):
        r, extra = host.call("docs_tieout_document", {"artifact_id": d["artifact_id"]})
        if "error" in r:
            print(f"  {d['filename']}: {r['error']}")
            rows.append({"filename": d["filename"], "error": r["error"]})
            continue
        for k in totals:
            totals[k] += r[k]
        rows.append({"filename": d["filename"], "artifact_id": d["artifact_id"],
                     **{k: r[k] for k in totals}, "seconds": extra.get("ms", 0) / 1000,
                     "failures": [{k: f.get(k) for k in ("page", "row", "column", "printed", "computed",
                                                          "difference", "verdict")}
                                  for f in r.get("failures", [])]})
        print(f"  {d['filename'][:60]:60} {r['passed']:>5} of {r['checks']:<5}"
              f" failed {r['failed']} ({r['failed_within_rounding_bound']} within rounding)")

    today = datetime.date.today().isoformat()
    print(f"\n{len(rows)} documents: {totals['passed']:,} of {totals['checks']:,} checks pass; "
          f"{totals['failed']} fail, {totals['failed_within_rounding_bound']} of them within "
          "the rounding bound")
    out = ROOT / "docs" / "submission" / "evidence" / f"tieout_store_{today}.json"
    out.write_text(json.dumps({
        "what": "Tie-outs over every document in the deployed docs server's store",
        "date": today, "app": APP, "app_url": app.url,
        "commit": _commit(app),
        "documents": len(rows), **totals, "per_document": rows,
    }, indent=2) + "\n", encoding="utf-8")
    print(f"written: {out.relative_to(ROOT)}")
    return 0 if not any("error" in r for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
