"""Server-side SVG chart engine.

No CDN, no npm, no build step, no runtime JavaScript dependency. That is a
deliberate constraint rather than a limitation: a restricted IL5 workspace is
deny-by-default on egress, so a chart library loaded from a CDN would render
nothing after transfer. Everything here is emitted as inline SVG that inherits
the page theme through CSS custom properties, so light and dark both work with
no regeneration.

Every chart takes plain data and returns its SVG as markupsafe.Markup. Every
value taken from the data is escaped with esc() or formatted as a number here,
so the result is safe HTML and templates render it as {{ C.hbar(...) }}
without the |safe filter (security scan: jinja2-safe-filter).
"""
from __future__ import annotations

import functools
import html
import math

from markupsafe import Markup

PALETTE = ["var(--c1)", "var(--c2)", "var(--c3)", "var(--c4)", "var(--c5)",
           "var(--c6)", "var(--c7)", "var(--c8)", "var(--c9)", "var(--c10)"]


def esc(s) -> str:
    return html.escape(str(s), quote=True)


def _html(chart):
    """Mark a chart's output as safe HTML. Only for functions in this module,
    which escape every data value they emit."""
    @functools.wraps(chart)
    def wrapper(*args, **kwargs) -> Markup:
        return Markup(chart(*args, **kwargs))
    return wrapper


def fmt(v, dp=1) -> str:
    if v is None:
        return "n/a"
    if abs(v) >= 1000:
        return f"{v:,.0f}"
    return f"{v:,.{dp}f}"


def _open(w, h, cls="chart"):
    return (f'<svg class="{cls}" viewBox="0 0 {w} {h}" preserveAspectRatio="xMidYMid meet" '
            f'role="img" xmlns="http://www.w3.org/2000/svg">')


# ------------------------------------------------------------------- donut
@_html
def donut(rows, *, value="value", label="name", size=320, thickness=46,
          center_top="", center_sub="", max_legend=10):
    total = sum(r[value] for r in rows) or 1
    r_out = size / 2 - 6
    r_in = r_out - thickness
    cx = cy = size / 2
    out = [_open(size, size, "chart donut")]
    a0 = -math.pi / 2
    for i, row in enumerate(rows):
        frac = row[value] / total
        a1 = a0 + frac * 2 * math.pi
        large = 1 if frac > 0.5 else 0
        x0, y0 = cx + r_out * math.cos(a0), cy + r_out * math.sin(a0)
        x1, y1 = cx + r_out * math.cos(a1), cy + r_out * math.sin(a1)
        xi1, yi1 = cx + r_in * math.cos(a1), cy + r_in * math.sin(a1)
        xi0, yi0 = cx + r_in * math.cos(a0), cy + r_in * math.sin(a0)
        d = (f"M{x0:.2f},{y0:.2f} A{r_out:.2f},{r_out:.2f} 0 {large} 1 {x1:.2f},{y1:.2f} "
             f"L{xi1:.2f},{yi1:.2f} A{r_in:.2f},{r_in:.2f} 0 {large} 0 {xi0:.2f},{yi0:.2f} Z")
        out.append(f'<path class="seg" d="{d}" fill="{PALETTE[i % len(PALETTE)]}">'
                   f'<title>{esc(row[label])}: {fmt(row[value])} ({frac*100:.1f}%)</title></path>')
        a0 = a1
    if center_top:
        out.append(f'<text x="{cx}" y="{cy-4}" class="donut-top" text-anchor="middle">{esc(center_top)}</text>')
    if center_sub:
        out.append(f'<text x="{cx}" y="{cy+18}" class="donut-sub" text-anchor="middle">{esc(center_sub)}</text>')
    out.append("</svg>")
    legend = ['<ul class="legend">']
    for i, row in enumerate(rows[:max_legend]):
        pct = row[value] / total * 100
        legend.append(
            f'<li><span class="sw" style="background:{PALETTE[i % len(PALETTE)]}"></span>'
            f'<span class="lg-name">{esc(row[label])}</span>'
            f'<span class="lg-val">{fmt(row[value])}</span>'
            f'<span class="lg-pct">{pct:.1f}%</span></li>')
    legend.append("</ul>")
    return f'<div class="donut-wrap">{"".join(out)}{"".join(legend)}</div>'


# -------------------------------------------------------------- horizontal bar
@_html
def hbar(rows, *, value="value", label="name", sub=None, w=760, rowh=30, pad_left=250,
         unit="$M", color=None, max_rows=None):
    rows = rows[:max_rows] if max_rows else rows
    if not rows:
        return '<p class="muted">No rows.</p>'
    vmax = max(abs(r[value]) for r in rows) or 1
    h = rowh * len(rows) + 14
    inner = w - pad_left - 96
    out = [_open(w, h, "chart hbar")]
    for i, r in enumerate(rows):
        y = i * rowh + 8
        bw = max(1.5, abs(r[value]) / vmax * inner)
        fill = color or PALETTE[i % len(PALETTE)]
        out.append(f'<text x="{pad_left-10}" y="{y+rowh*0.62}" class="bar-lab" text-anchor="end">'
                   f'{esc(str(r[label])[:42])}</text>')
        out.append(f'<rect x="{pad_left}" y="{y+5}" width="{bw:.2f}" height="{rowh-13}" rx="3" '
                   f'class="bar" fill="{fill}"><title>{esc(r[label])}: {fmt(r[value])} {unit}'
                   f'</title></rect>')
        out.append(f'<text x="{pad_left+bw+8}" y="{y+rowh*0.62}" class="bar-val">{fmt(r[value])}</text>')
        if sub and r.get(sub):
            out.append(f'<text x="{pad_left+bw+68}" y="{y+rowh*0.62}" class="bar-sub">'
                       f'{esc(r[sub])}</text>')
    out.append("</svg>")
    return "".join(out)


# ----------------------------------------------------------- stacked columns
@_html
def stacked_columns(rows, series, *, x="fy", w=900, h=330, unit="$M", pad=56):
    """rows: [{x: 2015, a: 1.0, b: 2.0}, ...]  series: [(key, label), ...]"""
    if not rows:
        return '<p class="muted">No rows.</p>'
    totals = [sum(r.get(k, 0) or 0 for k, _ in series) for r in rows]
    vmax = max(totals) or 1
    step = 5 if vmax < 60 else 10 ** math.floor(math.log10(vmax))
    ticks = [i * step for i in range(int(vmax / step) + 2)]
    vmax = ticks[-1]
    iw, ih = w - pad - 18, h - 46
    bw = iw / len(rows) * 0.66
    gap = iw / len(rows)
    out = [_open(w, h, "chart cols")]
    for t in ticks:
        y = 10 + ih - t / vmax * ih
        out.append(f'<line x1="{pad}" x2="{w-6}" y1="{y:.1f}" y2="{y:.1f}" class="grid"/>')
        out.append(f'<text x="{pad-8}" y="{y+4:.1f}" class="ax" text-anchor="end">{fmt(t,0)}</text>')
    for i, r in enumerate(rows):
        cx = pad + i * gap + (gap - bw) / 2
        acc = 0.0
        for si, (k, lab) in enumerate(series):
            v = r.get(k, 0) or 0
            if v <= 0:
                continue
            bh = v / vmax * ih
            y = 10 + ih - (acc + v) / vmax * ih
            out.append(f'<rect x="{cx:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{bh:.1f}" '
                       f'class="col" fill="{PALETTE[si % len(PALETTE)]}">'
                       f'<title>FY{esc(r[x])} {esc(lab)}: {fmt(v)} {unit}</title></rect>')
            acc += v
        out.append(f'<text x="{cx+bw/2:.1f}" y="{h-12}" class="ax" text-anchor="middle">'
                   f'{esc(str(r[x])[-2:])}</text>')
    out.append("</svg>")
    leg = "".join(f'<li><span class="sw" style="background:{PALETTE[i % len(PALETTE)]}"></span>{esc(l)}</li>'
                  for i, (_, l) in enumerate(series))
    return f'{"".join(out)}<ul class="legend inline">{leg}</ul>'


# ------------------------------------------------------------------ waterfall
def _nice_ticks(vmax: float, n: int = 5) -> list[float]:
    """Round tick values (1, 2, 2.5 or 5 x 10^k) from 0 to at least vmax."""
    if vmax <= 0:
        return [0.0, 1.0]
    raw = vmax / n
    mag = 10 ** math.floor(math.log10(raw))
    step = next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw)
    return [i * step for i in range(math.ceil(vmax / step) + 1)]


def _wrap(text: str, width: int, lines: int) -> list[str]:
    """Word-wrap to at most `lines` lines of `width` characters, ellipsis on overflow."""
    words, out, cur = str(text).split(), [], ""
    for wd in words:
        cand = (cur + " " + wd).strip()
        if len(cand) <= width or not cur:
            cur = cand
        else:
            out.append(cur)
            cur = wd
    if cur:
        out.append(cur)
    if len(out) > lines:
        out = out[:lines]
        out[-1] = out[-1][:max(1, width - 1)].rstrip() + "\u2026"
    return [o if len(o) <= width else o[:width - 1] + "\u2026" for o in out]


@_html
def waterfall(steps, *, w=900, h=360, pad=64, unit="$M", label_lines=3):
    """steps: [{label, delta, cum, tag}]

    Step names are sentences. They are set horizontally under their own bar
    and wrapped to the column width, never rotated: a rotated label runs
    into the neighbouring column and off the left edge (2026-11-11 report).
    The full name is also in each bar's tooltip and in the table under it."""
    if not steps:
        return '<p class="muted">No steps.</p>'
    lab_h = 14 * label_lines + 10
    ticks = _nice_ticks(max(s["cum"] for s in steps) * 1.06)
    vmax = ticks[-1]
    iw, ih = w - pad - 12, h - lab_h - 22
    gap = iw / len(steps)
    bw = gap * 0.56
    chars = max(10, int(gap / 6.4))
    out = [_open(w, h, "chart waterfall")]
    for t in ticks:
        y = 14 + ih - t / vmax * ih
        out.append(f'<line x1="{pad}" x2="{w-6}" y1="{y:.1f}" y2="{y:.1f}" class="grid"/>')
        out.append(f'<text x="{pad-8}" y="{y+4:.1f}" class="ax" text-anchor="end">'
                   f'{fmt(t,0)}</text>')
    prev = 0.0
    for i, s in enumerate(steps):
        cx = pad + i * gap + (gap - bw) / 2
        top = 14 + ih - s["cum"] / vmax * ih
        bot = 14 + ih - prev / vmax * ih
        bh = max(2.0, bot - top)
        cls = "wf-base" if i == 0 else "wf-up"
        out.append(f'<rect x="{cx:.1f}" y="{top:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="2" '
                   f'class="{cls}"><title>{esc(s["label"])}: +{fmt(s["delta"])} '
                   f'to {fmt(s["cum"])} {unit}</title></rect>')
        out.append(f'<text x="{cx+bw/2:.1f}" y="{top-6:.1f}" class="wf-val" text-anchor="middle">'
                   f'{"+" if i else ""}{fmt(s["delta"],0)}</text>')
        if i:
            out.append(f'<line x1="{cx-gap+bw:.1f}" x2="{cx:.1f}" y1="{bot:.1f}" y2="{bot:.1f}" '
                       f'class="wf-link"/>')
        lx, ly = pad + i * gap + gap / 2, 14 + ih + 18
        spans = "".join(f'<tspan x="{lx:.1f}" dy="{0 if j == 0 else 14}">{esc(t)}</tspan>'
                        for j, t in enumerate(_wrap(s["label"], chars, label_lines)))
        out.append(f'<text x="{lx:.1f}" y="{ly:.1f}" class="wf-lab" text-anchor="middle">'
                   f'<title>{esc(s["label"])}</title>{spans}</text>')
        prev = s["cum"]
    out.append("</svg>")
    return "".join(out)


# ----------------------------------------------------------------- line chart
@_html
def line_series(points, *, w=900, h=340, pad=66, unit="$M", mark_key=None, mark_colors=None):
    """points: [{x: 2008, y: 9192.0, label, mech}]"""
    xs = [p["x"] for p in points]
    ys = [p["y"] for p in points]
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys) * 0.92, max(ys) * 1.05
    iw, ih = w - pad - 20, h - 54
    def px(x): return pad + (x - x0) / max(1, (x1 - x0)) * iw
    def py(y): return 12 + ih - (y - y0) / (y1 - y0) * ih
    out = [_open(w, h, "chart line")]
    for frac in (0, .25, .5, .75, 1):
        v = y0 + frac * (y1 - y0)
        y = py(v)
        out.append(f'<line x1="{pad}" x2="{w-8}" y1="{y:.1f}" y2="{y:.1f}" class="grid"/>')
        out.append(f'<text x="{pad-8}" y="{y+4:.1f}" class="ax" text-anchor="end">{fmt(v,0)}</text>')
    d = " ".join(("M" if i == 0 else "L") + f"{px(p['x']):.1f},{py(p['y']):.1f}"
                 for i, p in enumerate(points))
    area = d + f" L{px(xs[-1]):.1f},{12+ih:.1f} L{px(xs[0]):.1f},{12+ih:.1f} Z"
    out.append(f'<path d="{area}" class="line-area"/>')
    out.append(f'<path d="{d}" class="line-path"/>')
    for p in points:
        c = (mark_colors or {}).get(p.get(mark_key), "var(--c1)") if mark_key else "var(--c1)"
        out.append(f'<circle cx="{px(p["x"]):.1f}" cy="{py(p["y"]):.1f}" r="5" class="dot" '
                   f'fill="{esc(c)}"><title>{esc(p.get("label", p["x"]))}: {fmt(p["y"])} {unit}'
                   f'{chr(10)}{esc(p.get("note",""))}</title></circle>')
    for x in sorted({int(p["x"]) for p in points}):
        out.append(f'<text x="{px(x):.1f}" y="{h-10}" class="ax" text-anchor="middle">{x}</text>')
    out.append("</svg>")
    return "".join(out)


# ----------------------------------------------------- dual column + cum line
@_html
def obligation_curve(rows, *, w=960, h=360, pad=66):
    vmax = max(r["combined"] for r in rows) * 1.1
    cmax = max(r["cumulative"] for r in rows) * 1.05
    iw, ih = w - pad - 60, h - 52
    gap = iw / len(rows)
    bw = gap * 0.6
    out = [_open(w, h, "chart curve")]
    for frac in (0, .25, .5, .75, 1):
        y = 12 + ih - frac * ih
        out.append(f'<line x1="{pad}" x2="{w-54}" y1="{y:.1f}" y2="{y:.1f}" class="grid"/>')
        out.append(f'<text x="{pad-8}" y="{y+4:.1f}" class="ax" text-anchor="end">{fmt(frac*vmax,0)}</text>')
        out.append(f'<text x="{w-48}" y="{y+4:.1f}" class="ax ax-r">{fmt(frac*cmax,0)}</text>')
    pts = []
    for i, r in enumerate(rows):
        cx = pad + i * gap + (gap - bw) / 2
        acc = 0.0
        for si, (k, lab) in enumerate((("cp", "Construction Preparation"), ("ddc", "Detail Design & Construction"))):
            v = r.get(k, 0) or 0
            if v <= 0:
                continue
            bh = v / vmax * ih
            y = 12 + ih - (acc + v) / vmax * ih
            out.append(f'<rect x="{cx:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{bh:.1f}" '
                       f'fill="{PALETTE[si]}" class="col"><title>FY{esc(r["fy"])} {esc(lab)}: '
                       f'{fmt(v)} $M</title></rect>')
            acc += v
        pts.append((cx + bw / 2, 12 + ih - r["cumulative"] / cmax * ih, r))
        out.append(f'<text x="{cx+bw/2:.1f}" y="{h-10}" class="ax" text-anchor="middle">'
                   f'{esc(str(r["fy"])[-2:])}</text>')
    d = " ".join(("M" if i == 0 else "L") + f"{x:.1f},{y:.1f}" for i, (x, y, _) in enumerate(pts))
    out.append(f'<path d="{d}" class="cum-path"/>')
    for x, y, r in pts:
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.6" class="cum-dot">'
                   f'<title>FY{esc(r["fy"])} cumulative {fmt(r["cumulative"])} $M</title></circle>')
    out.append("</svg>")
    leg = (f'<ul class="legend inline">'
           f'<li><span class="sw" style="background:{PALETTE[0]}"></span>Construction Preparation</li>'
           f'<li><span class="sw" style="background:{PALETTE[1]}"></span>Detail Design &amp; Construction</li>'
           f'<li><span class="sw line"></span>Cumulative, right axis</li></ul>')
    return "".join(out) + leg


# --------------------------------------------------------------- bubble chart
@_html
def bubble(rows, *, w=900, h=400, pad=66):
    """rows: [{x, y, r, label, cls}] x=closability weight, y=ignorance, r=exposure"""
    rmax = max(r["r"] for r in rows) or 1
    # Inset the x range so bubbles at closability 1.0 are not clipped by the frame.
    iw, ih = w - pad - 60, h - 56

    # Closability takes five discrete values and ignorance takes a handful, so
    # many gaps land on exactly the same point and their labels overprint.
    #
    # Relaxing in y alone does not clear it: eleven zero-access gaps share
    # x = 1.0 and the column runs out of height, so they clamp at the frame and
    # stay stacked. This relaxes in both axes, pushing along the real collision
    # vector, with x held within X_JITTER of its true position so a bubble never
    # crosses into a neighbouring closability band. Exact values are on hover.
    X_JITTER = 17.0
    # Each bubble carries its gap id as text at its centre, so separation has
    # to clear the label box and not just the circle. Two small bubbles can
    # satisfy a radius test and still print "G20" over "G11". A label box is
    # about 26 by 11, whose diagonal is 28.2, so an effective radius of 16 at
    # the 0.92 factor guarantees 29.4 between any two centres.
    LABEL_R = 16.0
    placed = []
    for r in sorted(rows, key=lambda r: -r["r"]):
        cx = pad + 18 + r["x"] * iw
        placed.append({**r, "cx": cx, "x0": cx,
                       "cy": 14 + ih - r["y"] * ih,
                       "rad": 7 + math.sqrt(r["r"] / rmax) * 26})

    # Deterministic seed spread. Identical points have no collision vector at
    # all, so without this the first pass has nothing to push along.
    for n, pt in enumerate(placed):
        if any(o is not pt and abs(o["cx"] - pt["cx"]) < .01 and abs(o["cy"] - pt["cy"]) < .01
               for o in placed):
            ang = (n * 2.39996)  # golden angle, spreads without clumping
            pt["cx"] += math.cos(ang) * 1.5
            pt["cy"] += math.sin(ang) * 1.5

    lo, hi = 20.0, 14.0 + ih - 6
    xlo, xhi = pad + 10, w - 16
    for _ in range(400):
        moved = False
        for i, a in enumerate(placed):
            for b in placed[i + 1:]:
                gap = (max(a["rad"], LABEL_R) + max(b["rad"], LABEL_R)) * 0.92
                dx, dy = b["cx"] - a["cx"], b["cy"] - a["cy"]
                d = math.hypot(dx, dy)
                if d >= gap:
                    continue
                if d < 1e-6:
                    dx, dy, d = 0.7, 0.7, 1.0
                ux, uy = dx / d, dy / d
                push = (gap - d) / 2.0
                for pt, sgn in ((a, -1.0), (b, 1.0)):
                    nx = pt["cx"] + sgn * ux * push
                    pt["cx"] = max(max(xlo, pt["x0"] - X_JITTER),
                                   min(min(xhi, pt["x0"] + X_JITTER), nx))
                    pt["cy"] = max(lo, min(hi, pt["cy"] + sgn * uy * push))
                moved = True
        if not moved:
            break

    out = [_open(w, h, "chart bubble")]
    for frac in (0, .25, .5, .75, 1):
        y = 14 + ih - frac * ih
        out.append(f'<line x1="{pad}" x2="{w-10}" y1="{y:.1f}" y2="{y:.1f}" class="grid"/>')
        out.append(f'<text x="{pad-8}" y="{y+4:.1f}" class="ax" text-anchor="end">{frac:.2f}</text>')
        x = pad + frac * iw
        out.append(f'<line y1="14" y2="{14+ih}" x1="{x:.1f}" x2="{x:.1f}" class="grid"/>')
        out.append(f'<text y="{h-12}" x="{x:.1f}" class="ax" text-anchor="middle">{frac:.2f}</text>')
    for p in placed:
        out.append(f'<circle cx="{p["cx"]:.1f}" cy="{p["cy"]:.1f}" r="{p["rad"]:.1f}" '
                   f'class="bub {esc(p.get("cls",""))}"><title>{esc(p["label"])}</title></circle>')
    for p in placed:
        out.append(f'<text x="{p["cx"]:.1f}" y="{p["cy"]+4:.1f}" class="bub-lab" '
                   f'text-anchor="middle">{esc(p["id"])}</text>')
    out.append(f'<text x="{pad+iw/2:.0f}" y="{h-30}" class="ax-title" text-anchor="middle">'
               f'closability, right is free to work now</text>')
    out.append(f'<text x="16" y="{14+ih/2:.0f}" class="ax-title" '
               f'transform="rotate(-90 16 {14+ih/2:.0f})" text-anchor="middle">ignorance</text>')
    out.append("</svg>")
    return "".join(out)


# ------------------------------------------------------------------- progress
@_html
def progress_rail(pct, *, label="", w=300, h=10):
    pct = max(0, min(100, pct))
    return (f'<div class="rail" title="{pct:.1f}%"><span style="width:{pct:.1f}%"></span></div>'
            f'<span class="rail-lab">{esc(label)}</span>')


# --------------------------------------------------------------- executive
@_html
def sparkline(values, *, w=140, h=34, fill=True, cls="") -> str:
    """Trend inside a KPI tile. No axes and no labels on purpose: a sparkline
    answers "which way and how steadily", and the number it sits beside
    answers "how much". Adding axes to it just makes a bad small chart."""
    vals = [float(v) for v in values if v is not None]
    if len(vals) < 2:
        return ""
    lo, hi = min(vals), max(vals)
    rng = (hi - lo) or 1.0
    step = (w - 4) / (len(vals) - 1)
    pts = [(2 + i * step, h - 3 - (v - lo) / rng * (h - 8)) for i, v in enumerate(vals)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    out = [(f'<svg class="spark {cls}" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
           f'preserveAspectRatio="none" aria-hidden="true">')]
    if fill:
        out.append(f'<polygon class="spk-f" points="2,{h-1} {line} {w-2},{h-1}"/>')
    out.append(f'<polyline class="spk-l" points="{line}" fill="none"/>')
    out.append(f'<circle class="spk-d" cx="{pts[-1][0]:.1f}" cy="{pts[-1][1]:.1f}" r="2.6"/>')
    out.append("</svg>")
    return "".join(out)


@_html
def bullet(actual, target, *, limits=None, w=320, h=38, unit="$M", label="",
           scale_max=None) -> str:
    """Actual against a target, on bands of qualitative range. Reads in one
    glance and does not lie about precision the way a gauge does, because the
    scale is linear and shared with every other bullet on the page."""
    limits = limits or []
    # Every bullet in a group must share one scale, or they are three pictures
    # of three different rulers and comparing them by eye is wrong. Pass
    # scale_max from the caller with the largest value in the group.
    hi = (scale_max or max([actual, target] + list(limits))) * 1.08 or 1.0
    bw = w - 8
    out = [_open(w, h, "chart bullet")]
    prev = 0.0
    for n, lim in enumerate(sorted(limits)):
        x0, x1 = 4 + prev / hi * bw, 4 + lim / hi * bw
        out.append(f'<rect x="{x0:.1f}" y="6" width="{max(0, x1-x0):.1f}" height="{h-18}" '
                   f'class="bl-band b{n+1}"/>')
        prev = lim
    out.append(f'<rect x="{4 + prev/hi*bw:.1f}" y="6" width="{max(0, 4+bw-(4+prev/hi*bw)):.1f}" '
               f'height="{h-18}" class="bl-band b{len(limits)+1}"/>')
    out.append(f'<rect x="4" y="{h/2-5:.1f}" width="{actual/hi*bw:.1f}" height="10" class="bl-act"/>')
    tx = 4 + target / hi * bw
    out.append(f'<line x1="{tx:.1f}" x2="{tx:.1f}" y1="3" y2="{h-9}" class="bl-tgt"/>')
    out.append(f'<text x="4" y="{h-1}" class="bl-lab">{esc(label)}</text>')
    out.append(f'<text x="{w-4}" y="{h-1}" class="bl-lab" text-anchor="end">'
               f'{fmt(actual)} vs {fmt(target)} {esc(unit)}</text>')
    out.append("</svg>")
    return "".join(out)


@_html
def risk_matrix(items, *, w=520, h=360, pad=58) -> str:
    """Exposure against confidence. Not a heat map with invented colours: the
    cell a thing lands in is computed from its own two numbers, and the label
    is the thing's name, so a reader can disagree with a placement rather than
    with a shade."""
    iw, ih = w - pad - 18, h - pad - 24
    out = [_open(w, h, "chart riskmx")]
    for i in range(3):
        for j in range(3):
            x = pad + i * iw / 3
            y = 12 + j * ih / 3
            sev = (2 - j) + i          # 0..4, worst top-right
            out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{iw/3:.1f}" height="{ih/3:.1f}" '
                       f'class="rm-cell s{sev}"/>')
    placed = []
    for it in items:
        cx = pad + max(0.02, min(0.98, float(it["x"]))) * iw
        cy = 12 + ih - max(0.02, min(0.98, float(it["y"]))) * ih
        for px, py in placed:
            if abs(px - cx) < 46 and abs(py - cy) < 17:
                cy = py + 18
        placed.append((cx, cy))
        out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="5" class="rm-dot {esc(it.get("cls",""))}">'
                   f'<title>{esc(it.get("title", it["label"]))}</title></circle>')
        anchor = "end" if cx > pad + iw * 0.72 else "start"
        dx = -9 if anchor == "end" else 9
        out.append(f'<text x="{cx+dx:.1f}" y="{cy+3.6:.1f}" class="rm-lab" '
                   f'text-anchor="{anchor}">{esc(it["label"])}</text>')
    out.append(f'<text x="{pad+iw/2:.1f}" y="{h-6}" class="ax" text-anchor="middle">'
               f'confidence, right is better understood</text>')
    out.append(f'<text transform="translate(14,{12+ih/2:.1f}) rotate(-90)" class="ax" '
               f'text-anchor="middle">exposure left unexplained</text>')
    out.append("</svg>")
    return "".join(out)


@_html
def gauge(pct, *, w=150, h=92, label="", sub="", show_value=True) -> str:
    """A single ratio, where the ratio is the point. Half dial, no needle
    shadow, no gradient: the only job is to show how far along something is
    against a whole that the reader already understands."""
    pct = max(0.0, min(100.0, float(pct)))
    cx, cy, r = w / 2, h - 18, w / 2 - 12
    def pt(frac):
        import math
        a = math.pi * (1 - frac)
        return cx + r * math.cos(a), cy - r * math.sin(a)
    x0, y0 = pt(0.0)
    x1, y1 = pt(1.0)
    xa, ya = pt(pct / 100.0)
    big = 0
    # Explicit width and height, not just a viewBox. Inside a flex KPI tile a
    # viewBox-only SVG stretches to the container and the 19px label scales
    # with it, which overflowed the card. Pinning both stops that.
    out = [(f'<svg class="chart gauge" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
           f'role="img" xmlns="http://www.w3.org/2000/svg">')]
    out.append(f'<path d="M{x0:.1f} {y0:.1f} A{r} {r} 0 {big} 1 {x1:.1f} {y1:.1f}" class="gg-bg"/>')
    out.append(f'<path d="M{x0:.1f} {y0:.1f} A{r} {r} 0 {big} 1 {xa:.1f} {ya:.1f}" class="gg-fg"/>')
    # Inside a KPI tile the number is already the headline beside it, and
    # printing it twice makes the reader check whether they match.
    if show_value:
        out.append(f'<text x="{cx:.1f}" y="{cy-6:.1f}" class="gg-v" '
                   f'text-anchor="middle">{pct:.1f}%</text>')
    if label:
        out.append(f'<text x="{cx:.1f}" y="{h-4}" class="gg-l" text-anchor="middle">{esc(label)}</text>')
    out.append("</svg>")
    return "".join(out)


# ------------------------------------------------------------- number line
@_html
def number_line(points, *, bands=None, refs=None, w=960, h=190, pad=40, unit="$M"):
    """Where several figures sit on one axis.

    points: [{label, value, cls}] drawn as markers, labels alternating above
    and below so neighbours never collide. bands: [{lo, hi, label}] shaded
    spans. refs: [{value, label}] dashed reference ticks. Values in unit.
    """
    vals = [p["value"] for p in points] + [r["value"] for r in (refs or [])]
    for b in bands or []:
        vals += [b["lo"], b["hi"]]
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1.0
    lo, hi = lo - span * 0.06, hi + span * 0.06
    axis_y = h / 2 + 4
    def px(v): return pad + (v - lo) / (hi - lo) * (w - 2 * pad)
    out = [_open(w, h, "chart nline")]
    for b in bands or []:
        x0, x1 = px(b["lo"]), px(b["hi"])
        out.append(f'<rect x="{x0:.1f}" y="{axis_y-26:.1f}" width="{x1-x0:.1f}" height="52" '
                   f'class="nl-band" rx="4"><title>{esc(b.get("label", ""))}</title></rect>')
        out.append(f'<text x="{(x0+x1)/2:.1f}" y="{axis_y+40:.1f}" class="ax" '
                   f'text-anchor="middle">{esc(b.get("label", ""))}</text>')
    out.append(f'<line x1="{pad}" x2="{w-pad}" y1="{axis_y}" y2="{axis_y}" class="nl-axis"/>')
    step = 10 ** math.floor(math.log10(span)) if span > 0 else 1
    if span / step < 3:
        step /= 2
    t = math.ceil(lo / step) * step
    while t <= hi:
        x = px(t)
        out.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{axis_y-3}" y2="{axis_y+3}" class="nl-axis"/>')
        out.append(f'<text x="{x:.1f}" y="{h-6}" class="ax" text-anchor="middle">{fmt(t, 0)}</text>')
        t += step
    for r in refs or []:
        x = px(r["value"])
        out.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{axis_y-20}" y2="{axis_y+20}" class="nl-ref">'
                   f'<title>{esc(r["label"])}: {fmt(r["value"], 2)} {unit}</title></line>')
        out.append(f'<text x="{x+4:.1f}" y="{axis_y+30:.1f}" class="ax">{esc(r["label"])}</text>')
    for i, p in enumerate(sorted(points, key=lambda q: q["value"])):
        x = px(p["value"])
        up = i % 2 == 0
        ly = axis_y - 40 if up else axis_y + 56
        out.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{axis_y}" y2="{(ly + 6) if up else (ly - 22):.1f}" '
                   f'class="nl-lead"/>')
        out.append(f'<circle cx="{x:.1f}" cy="{axis_y}" r="7" class="nl-dot {esc(p.get("cls", ""))}">'
                   f'<title>{esc(p["label"])}: {fmt(p["value"], 2)} {unit}</title></circle>')
        anchor = "start" if x < w * 0.15 else ("end" if x > w * 0.85 else "middle")
        out.append(f'<text x="{x:.1f}" y="{ly - 12:.1f}" class="nl-lab" text-anchor="{anchor}">'
                   f'{esc(p["label"])}</text>')
        # exact, never rounded to the dollar million: 13,409.97 is not 13,410
        exact = f'{p["value"]:,.2f}'.rstrip("0").rstrip(".")
        out.append(f'<text x="{x:.1f}" y="{ly + 2:.1f}" class="nl-val" text-anchor="{anchor}">'
                   f'{exact}</text>')
    out.append("</svg>")
    return "".join(out)
