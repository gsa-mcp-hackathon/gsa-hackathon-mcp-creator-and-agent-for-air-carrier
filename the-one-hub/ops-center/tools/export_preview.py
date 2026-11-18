#!/usr/bin/env python3
"""Render every page to static HTML for offline review.

Not a deployment path. The app serves itself through FastAPI. This exists so
the pages can be opened from the filesystem with no server, which is also the
static-export fallback PLAN names for the sponsor brief if the workspace link
is not reachable in the room.
"""
import pathlib
import re
import shutil
import sys

APP = pathlib.Path(__file__).resolve().parents[1] / "app"
OUT = APP / "_preview"
sys.path.insert(0, str(APP))

from fastapi.testclient import TestClient  # noqa: E402
import main  # noqa: E402

FILE = {p: ("index.html" if p == "/" else p.strip("/") + ".html") for p, _ in main.NAV}


def localize(html: str) -> str:
    html = html.replace('href="/static/', 'href="static/').replace('src="/static/', 'src="static/')
    html = html.replace('data-full="/static/', 'data-full="static/')
    for route, fname in FILE.items():
        html = html.replace(f'href="{route}"', f'href="{fname}"')
    html = re.sub(r'href="/api/docs"', 'href="#"', html)
    return html


def main_() -> int:
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT).mkdir(parents=True)
    shutil.copytree(APP / "static", OUT / "static")
    c = TestClient(main.app)
    for route, fname in FILE.items():
        r = c.get(route)
        (OUT / fname).write_text(localize(r.text), encoding="utf-8")
        print(f"  {fname:<22} {len(r.text):>8,}")
    print(f"\n{OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main_())
