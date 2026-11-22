#!/usr/bin/env python3
"""Contrast audit of the palette, both themes.

Readability is the first consideration when choosing a font colour, so this
is a check rather than an opinion. WCAG AA is 4.5:1 for body text and 3.0:1
for large text. This product is read by people deciding whether to believe a
number, often on a projector in a lit room, so the floor here is 4.5 for
everything that carries meaning, including the text that calls itself muted.
"""
from __future__ import annotations

import pathlib
import re
import sys

CSS = pathlib.Path(__file__).resolve().parents[1] / "app" / "static" / "css" / "app.css"
FLOOR = 4.5


def rgb(h: str):
    h = h.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def lum(c):
    def ch(v):
        v /= 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(x) for x in c)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(a: str, b: str) -> float:
    la, lb = lum(rgb(a)), lum(rgb(b))
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def palette(css: str, selector: str) -> dict:
    i = css.index(selector)
    block = css[i:css.index("}", i)]
    return dict(re.findall(r"--([a-z0-9-]+)\s*:\s*(#[0-9a-fA-F]{3,8})", block))


def audit(name: str, p: dict) -> int:
    bad = 0
    bgs = [("page", p.get("bg")), ("card", p.get("bg-2")), ("sunk", p.get("bg-3"))]
    fgs = [k for k in ("fg", "fg-2", "fg-3", "mut", "accent", "ok", "warn", "bad", "info")
           if k in p]
    print(f"\n{name}")
    print(f"  {'':<8}" + "".join(f"{b:>12}" for b, _ in bgs))
    for f in fgs:
        row = f"  {f:<8}"
        for _, bg in bgs:
            if not bg:
                row += f"{'-':>12}"
                continue
            r = ratio(p[f], bg)
            mark = " " if r >= FLOOR else "!"
            if r < FLOOR:
                bad += 1
            row += f"{r:>10.2f}{mark} "
        print(row + f"  {p[f]}")
    return bad


def audit_brand(p: dict) -> int:
    """The navy surface (top bar, the solution plate) is the same in both themes."""
    bad = 0
    bgs = [("navy", p.get("navy")), ("navy-2", p.get("navy-2"))]
    print(f"\nBRAND  (floor {FLOOR}:1)")
    print(f"  {'':<10}" + "".join(f"{b:>12}" for b, _ in bgs))
    for f in ("on-navy", "on-navy-2", "brass", "teal", "violet"):
        row = f"  {f:<10}"
        for _, bg in bgs:
            r = ratio(p[f], bg)
            bad += r < FLOOR
            row += f"{r:>10.2f}{' ' if r >= FLOOR else '!'} "
        print(row + f"  {p[f]}")
    r = ratio(p["navy"], p["brass"])           # the brass button carries navy text
    bad += r < FLOOR
    print(f"  {'navy on brass':<14}{r:>8.2f}{' ' if r >= FLOOR else '!'}")
    return bad


def main() -> int:
    css = CSS.read_text(encoding="utf-8")
    light = palette(css, ":root {")
    dark = palette(css, 'html[data-theme="dark"] {')
    bad = audit(f"LIGHT  (floor {FLOOR}:1)", light) + audit(f"DARK   (floor {FLOOR}:1)", dark)
    bad += audit_brand(light)
    print(f"\n{bad} combination(s) below {FLOOR}:1" if bad else
          f"\nevery combination clears {FLOOR}:1")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
