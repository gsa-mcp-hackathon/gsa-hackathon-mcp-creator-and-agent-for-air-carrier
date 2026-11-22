"""Export the front center as a static, read-only site for GitHub Pages.

The deployed apps sit behind Databricks sign-in, so a reviewer cannot open
them. This script renders every page of the front center from the extracts
shipped in the repository (the same snapshot mode `uvicorn main:app` runs in
locally), rewrites links to relative paths, and writes the result to
docs/site/. Features that need a signed-in user (Ask the evidence, specialist
runs, decisions, Answer a question) are answered by a small shim with a
message that points to the live gallery: screenshots from the deployed app and
the demo video.

    cd the-one-hub/ops-center
    uv run --with beautifulsoup4 python ../../tools/export_static_site.py     # writes docs/site/
    uv run --with beautifulsoup4 python ../../tools/export_static_site.py --out DIR

It runs in the front center's own environment, plus BeautifulSoup for the link rewrite.
GitHub Pages serves the result from the main branch, /docs folder.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

REPO = Path(__file__).resolve().parents[1]
APP = REPO / "the-one-hub" / "ops-center" / "app"
SKIP = ("/api", "/static", "/healthz", "/docs", "/openapi.json", "/redoc")
START = ["/stack", "/impact", "/brief", "/kennedy", "/position", "/cost", "/baseline", "/execution",
         "/gaps", "/variances", "/asset", "/industrial", "/ask", "/work", "/runs", "/explore",
         "/sources", "/method", "/rules", "/coverage", "/mission", "/insight"]
NOTE = ("Read-only snapshot: this needs the deployed app behind Databricks sign-in. "
        "The live gallery shows it working.")

LIVE = [  # screenshots from the deployed app, in docs/screenshots
    ("live-databricks-apps.jpg", "Seven apps, live", "The probe, the front center and five MCP servers, each deployed from the GitHub repository."),
    ("live-agent-run-steps.jpg", "A specialist run streams its steps", "The Account Analyst works a File C period; each step is labeled code or model."),
    ("live-role-check.jpg", "Role check", "The user holds PMS 379. The residual lead belongs to the Office of Financial Operations, so the app refuses to apply it."),
    ("live-agent-review-decide.jpg", "Review and decide", "The Gap Investigator's requests for gap G52, each addressed to the office that holds the records. Nothing is saved until a person applies it."),
    ("live-agent-run-checks.jpg", "Code re-checks the run", "Every condition of the run is tested again by code: 11 of 11."),
    ("live-agent-reconcile.jpg", "Obligation Reconciler", "927 actions summed in exact decimals; 8 of 8 conditions re-tested."),
    ("live-work-queue.jpg", "Work queue", "Every item in one lane by code: decide, unblock or system."),
    ("live-run-log.jpg", "Run log", "Every agent run and every action by every person, exportable."),
    ("live-brief-readiness.jpg", "Brief readiness", "13 of 32 CVN-79 figures tie to source records today."),
    ("live-ask-via-mcp.jpg", "Ask the evidence, as an MCP host", "One question, four tool calls across mcp-aircarrier-docs, mcp-aircarrier-hub and mcp-aircarrier-ops; each step names the server that answered, and the answer is marked as a lead."),
    ("live-ask.jpg", "Ask the evidence, before round 10", "The same page before it called the MCP servers: one in-app tool call, the total, the largest action and every modification it rests on."),
]

SHIM = """<script>
(function () {
  var root = document.querySelector('meta[name="snapshot-root"]').content;
  var note = %s;
  var real = window.fetch.bind(window);
  window.fetch = function (url, opts) {
    var u = String(url);
    var m = u.match(/^\\/api\\/gaps\\/([A-Za-z0-9-]+)\\/brief/);
    if (m) return real(root + 'api/gaps/' + m[1] + '/brief.json');
    if (u.charAt(0) === '/') {
      return Promise.resolve(new Response(JSON.stringify({ error: note, detail: note }),
        { status: 403, headers: { 'Content-Type': 'application/json' } }));
    }
    return real(url, opts);
  };
  document.addEventListener('submit', function (e) {
    if ((e.target.method || 'get').toLowerCase() === 'post') { e.preventDefault(); alert(note); }
  }, true);
})();
</script>"""

BANNER = """<div style="background:#0b1a33;color:#fff;font:500 14px/1.45 Inter,system-ui,sans-serif;padding:9px 18px;text-align:center">
Read-only snapshot of the front center, rendered from the extracts in the repository on {day}.
Ask the evidence, specialist runs, decisions and Answer a question need Databricks sign-in:
<a href="{root}live/" style="color:#9cc3ff;font-weight:600">see them in the live gallery and demo</a> ·
<a href="https://github.com/llmlocalai/gsa-hackathon-mcp-creator-and-agent-for-cvn" style="color:#9cc3ff">repository</a>
</div>"""


def file_for(path: str) -> str:
    path = path.rstrip("/") or "/stack"
    return path.lstrip("/") + "/index.html"


def rel(target: str, depth: int) -> str:
    """Rewrite an absolute app URL to a path relative to a page `depth` folders deep."""
    if not target.startswith("/") or target.startswith("//"):
        return target
    parts = urlsplit(target)
    up = "../" * depth
    frag = f"#{parts.fragment}" if parts.fragment else ""
    if parts.path.startswith("/static/"):
        return up + parts.path.lstrip("/")
    if parts.path.startswith(SKIP):
        return target
    page = parts.path.rstrip("/") or "/stack"
    return up + page.lstrip("/") + "/" + frag


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=str(REPO / "docs" / "site"))
    args, _ = ap.parse_known_args()
    out = Path(args.out)

    os.chdir(APP)
    sys.path.insert(0, str(APP))
    import main as app_main
    from fastapi.testclient import TestClient

    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    shutil.copytree(APP / "static", out / "static")
    for css in (out / "static").rglob("*.css"):  # css lives in static/css/, so /static/x is ../x
        css.write_text(re.sub(r"url\((['\"]?)/static/", r"url(\1../", css.read_text()))
    day = date.today().isoformat()

    seen, queue, pages = set(), list(START), []
    with TestClient(app_main.app) as client:
        while queue:
            path = queue.pop(0)
            if path in seen or path.startswith(SKIP):
                continue
            seen.add(path)
            r = client.get(path, follow_redirects=False)
            depth = (path.rstrip("/") or "/stack").count("/")
            dest = out / file_for(path)
            dest.parent.mkdir(parents=True, exist_ok=True)
            if r.status_code in (301, 302, 307, 308):
                loc = rel(r.headers["location"], depth)
                dest.write_text(f'<!doctype html><meta http-equiv="refresh" content="0; url={loc}">'
                                f'<a href="{loc}">{loc}</a>')
                target = urlsplit(r.headers["location"]).path
                if target not in seen:
                    queue.append(target)
                continue
            if r.status_code != 200 or "text/html" not in r.headers.get("content-type", ""):
                print(f"skip {path} ({r.status_code})")
                continue
            soup = BeautifulSoup(r.text, "html.parser")
            for tag in soup.find_all(True):
                for attr, v in list(tag.attrs.items()):  # data-full and the like carry asset paths
                    if attr not in ("href", "src", "action") and isinstance(v, str) and v.startswith("/static/"):
                        tag[attr] = rel(v, depth)
                for attr in ("href", "src", "action"):
                    v = tag.get(attr)
                    if not v or not v.startswith("/") or v.startswith("//"):
                        continue
                    p = urlsplit(v).path
                    if attr == "href" and tag.name == "a" and not p.startswith(SKIP):
                        nxt = p.rstrip("/") or "/stack"
                        if nxt not in seen:
                            queue.append(nxt)
                    tag[attr] = rel(v, depth)
            up = "../" * depth
            head = soup.head
            head.insert(0, BeautifulSoup(f'<meta name="snapshot-root" content="{up}">', "html.parser"))
            first_script = soup.find("script", src=True)
            shim = BeautifulSoup(SHIM % json.dumps(NOTE), "html.parser")
            (first_script.insert_before(shim) if first_script else soup.body.append(shim))
            soup.body.insert(0, BeautifulSoup(BANNER.format(day=day, root=up), "html.parser"))
            dest.write_text(str(soup))
            pages.append(path)

        briefs = 0
        for gid in sorted({m for p in pages for m in re.findall(
                r'data-answer="([A-Za-z0-9-]+)"', (out / file_for(p)).read_text())}):
            r = client.get(f"/api/gaps/{gid}/brief")
            if r.status_code == 200:
                d = out / "api" / "gaps" / gid
                d.mkdir(parents=True, exist_ok=True)
                brief = r.json()
                brief.pop("model_errors", None)  # workspace auth errors from this machine; not for readers
                (d / "brief.json").write_text(json.dumps(brief))
                briefs += 1

    write_gallery(out, day)
    redirect = '<!doctype html><meta http-equiv="refresh" content="0; url={0}"><a href="{0}">{0}</a>'
    (out / "index.html").write_text(redirect.format("stack/"))
    docs = out.parent
    (docs / "index.html").write_text(redirect.format(f"{out.name}/stack/"))
    (docs / ".nojekyll").write_text("")
    print(f"{len(pages)} pages, {briefs} gap briefs, gallery -> {out}")


def write_gallery(out: Path, day: str) -> None:
    """The live gallery: the demo video and screenshots from the deployed app."""
    shell = BeautifulSoup((out / "stack" / "index.html").read_text(), "html.parser")
    main_el = shell.find("main")
    cards = "".join(
        f'<figure style="margin:0 0 28px"><a href="../../screenshots/{f}"><img src="../../screenshots/{f}" alt="{t}" '
        f'style="width:100%;border:1px solid #d8e0ec;border-radius:10px"></a>'
        f'<figcaption style="margin-top:8px"><b>{t}.</b> {c}</figcaption></figure>' for f, t, c in LIVE)
    main_el.clear()
    main_el.append(BeautifulSoup(f"""
<div class="wrap" style="max-width:1100px;margin:0 auto;padding:28px 20px">
<h1>Live gallery</h1>
<p>The front center deployed in the Databricks workspace, on 2026-11-21. Everything here needs a signed-in
user, so the read-only snapshot cannot run it. Authority to apply a proposal is decided inside Unity Catalog
under the signed-in user's own token.</p>
<h2>Two-minute demo</h2>
<video controls preload="metadata" poster="../../demo/air-carrier-two-minute-demo.jpg" style="width:100%;border-radius:10px">
<source src="../../demo/air-carrier-two-minute-demo.mp4" type="video/mp4"></video>
<p class="muted">1:55, narrated and subtitled. Snapshot built {day}.</p>
<h2>Screens from the deployed app</h2>
{cards}
</div>""", "html.parser"))
    d = out / "live"
    d.mkdir(exist_ok=True)
    (d / "index.html").write_text(str(shell))


if __name__ == "__main__":
    main()
