#!/usr/bin/env python3
"""Front center route and integrity suite.

Checks every page renders, every chart emits, every referenced asset exists,
every image carries alt text, and the nav marks the active page.

    pip install fastapi jinja2 httpx
    python3 checks/test_app.py
"""
import pathlib
import re
import sys
from pathlib import Path

ROOT = pathlib.Path(__file__).resolve().parents[1]
APP = ROOT / "app"
sys.path.insert(0, str(APP))

from fastapi.testclient import TestClient  # noqa: E402
import main  # noqa: E402

FAIL: list[str] = []


def main_() -> int:
    c = TestClient(main.app, raise_server_exceptions=False)
    print("routes")
    for route, _label in main.NAV:
        r = c.get(route)
        ok = r.status_code == 200 and "{{" not in r.text and "{%" not in r.text
        print(f"  [{'ok  ' if ok else 'FAIL'}] {route:<16} {r.status_code} {len(r.text):>8,} bytes")
        if not ok:
            FAIL.append(f"{route} -> {r.status_code}")

    print("\napi")
    for route, want in [("/healthz", 200), ("/api/tables", 200),
                        ("/api/table/program", 200), ("/api/table/nope", 404),
                        ("/api/openapi.json", 200)]:
        r = c.get(route)
        ok = r.status_code == want
        print(f"  [{'ok  ' if ok else 'FAIL'}] {route:<24} {r.status_code}")
        if not ok:
            FAIL.append(f"{route} -> {r.status_code}, wanted {want}")
    p = c.post("/api/capture", json={"kind": "pointer", "body": "t"})
    print(f"  [{'ok  ' if p.status_code == 200 else 'FAIL'}] POST /api/capture       {p.status_code}")
    if p.status_code != 200:
        FAIL.append("capture")

    print("\nintegrity")
    charts = 0
    for route, _ in main.NAV:
        h = c.get(route).text
        charts += len(re.findall(r'<svg class="chart', h))
        for m in re.findall(r'(?:src|href|data-full)="(/static/[^"]+)"', h):
            if not (APP / m.lstrip("/")).exists():
                FAIL.append(f"{route}: missing asset {m}")
        for img in re.findall(r"<img\b[^>]*>", h):
            if "alt=" not in img:
                FAIL.append(f"{route}: img without alt")
        if len(re.findall(r"<h1[ >]", h)) != 1:
            FAIL.append(f"{route}: not exactly one h1")
        if 'aria-current="page"' not in h:
            FAIL.append(f"{route}: nav does not mark the active page")
    print(f"  [{'ok  ' if not FAIL else 'FAIL'}] assets, alt text, headings, active nav")
    print(f"  [ok  ] {charts} SVG charts rendered across {len(main.NAV)} pages")

    print("\n  regressions")

    def reg(name, ok, detail=""):
        print(f"  [{'ok  ' if ok else 'FAIL'}] {name}")
        if detail:
            print(f"         {detail}")
        if not ok:
            FAIL.append(name)

    # The app cached every table for the life of the process, so a rebuilt
    # table, or an insight captured through the product, never appeared and
    # nothing looked wrong. Found by a rendered page disagreeing with the JSON
    # behind it.
    import json as _json
    import time as _time
    from api import data as _data
    probe = _data.DATA / "_cache_probe.json"
    try:
        probe.write_text(_json.dumps({"v": 1}))
        first = _data.get("_cache_probe")
        _time.sleep(0.01)
        probe.write_text(_json.dumps({"v": 2}))
        second = _data.get("_cache_probe")
        reg("a rebuilt table is served without a restart",
            first.get("v") == 1 and second.get("v") == 2,
            f"read {first.get('v')} then {second.get('v')}")
        reg("an unchanged table is not re-parsed",
            _data.get("_cache_probe") is second,
            "same object back, so the cache still earns its place")
    finally:
        probe.unlink(missing_ok=True)

    # Many gaps share a closability weight and land on one x. Relaxing in y
    # alone left eleven of them stacked against the frame with their labels
    # printed over each other.
    import math as _math
    from api.charts import bubble as _bubble
    g = _data.get("gaps")
    rows = [{"id": r["id"], "x": main.CLOS_W.get(r["closability"], 0.5),
             "y": r["ignorance"], "r": max(r["exposure_usd_m"], 40.0),
             "cls": "", "label": r["id"]}
            for r in g["rows"] if not r["closed"] and r.get("scored", True)]
    # Same population the page plots: open and scored. Unscored gaps carry a
    # placeholder ignorance and are listed, not plotted (see main.gaps).
    svg = _bubble(rows)
    txt = [(float(a), float(b), c) for a, b, c in
           re.findall(r'<text x="([\d.]+)" y="([\d.]+)"[^>]*>(G\d+)</text>', svg)]
    clash = [(a[2], b[2]) for i, a in enumerate(txt) for b in txt[i + 1:]
             if abs(a[0] - b[0]) < 26 and abs(a[1] - b[1]) < 11]
    reg("every bubble label is readable", not clash,
        f"{len(txt)} labels placed; clashes: {clash or 'none'}")
    pts = [(float(a), float(b), float(c)) for a, b, c in
           re.findall(r'<circle cx="([\d.]+)" cy="([\d.]+)" r="([\d.]+)"', svg)]
    deep = [round(r1 + r2 - _math.hypot(x2 - x1, y2 - y1), 1)
            for i, (x1, y1, r1) in enumerate(pts) for x2, y2, r2 in pts[i + 1:]
            if _math.hypot(x2 - x1, y2 - y1) < (r1 + r2) * 0.75]
    reg("no bubble is buried inside another", not deep,
        f"deep overlaps: {deep or 'none'}")

    # The page headline is "the discovery queue", so the table opens in queue
    # order. Identifier order put G1, G2 and G3 at the top, three of the least
    # urgent rows in the register.
    ids = re.findall(r'<span class="b b-(?:ok|warn)">(G\d+)</span>', c.get("/gaps").text)
    reg("the gap table opens in queue order", ids[0] == "G14", f"first row: {ids[0]}")
    reg("closed gaps sink to the bottom", "G27" in ids[-8:],
        "G27 closed 2026-11-08 and leaves the working queue")

    # Readability is a property that regresses silently: someone picks a
    # nicer grey and nobody notices until a figure is unreadable on a
    # projector. Measured here so it cannot.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
    # ---- 2026-11-09: position, detail table, live guard, agent, program ----
    for old in ("/delivery", "/progress"):
        r = c.get(old, follow_redirects=False)
        reg(f"{old} redirects to /program", r.status_code == 308
            and r.headers.get("location") == "/program", f"{r.status_code} {r.headers.get('location')}")

    html = c.get("/position").text
    seen = [m for m in ("$11,341.4M", "$11,398.0M", "$12,936.0M", "$13,409.97M") if m in html]
    order = [html.find(m) for m in seen]
    reg("/position shows the four figures, ascending", len(seen) == 4 and order == sorted(order),
        f"found {seen}")
    reg("/position names G12 as the unexplained difference", "G12" in html and "cannot yet be explained" in html)

    r = c.get("/api/explore/transactions", params={"f.award_id_piid": "N0002409C2116"}).json()
    reg("detail table: 2116 is 948 rows, $4,519,300,323.83 exactly",
        r["total"] == 948 and r["sum"] == "4519300323.83", f"{r['total']} {r['sum']}")
    r = c.get("/api/explore/transactions", params={"f.award_id_piid": "N0002415C2114"}).json()
    reg("detail table: 2114 is 927 rows, $4,578,603,345.77 exactly",
        r["total"] == 927 and r["sum"] == "4578603345.77", f"{r['total']} {r['sum']}")
    cols = {x["field"] for x in r["columns"]}
    reg("detail table never carries the running total", "total_dollars_obligated" not in cols)
    csvt = c.get("/api/explore/transactions/csv", params={"f.award_id_piid": "N0002415C2114"}).text
    reg("CSV export carries every filtered row, not one page", csvt.count("\n") == 928,
        f"{csvt.count(chr(10))} lines")
    reg("unknown dataset is a 404", c.get("/api/explore/nope").status_code == 404)
    reg("unknown exhibit table is a 404", c.get("/api/exhibit/nope").status_code == 404)
    lv = c.get("/api/live").json()
    reg("no warehouse bound: live is false and says why",
        lv["live"] is False and "warehouse" in lv["reason"].lower(), lv.get("reason", "")[:80])

    from api import agent, live  # noqa: E402
    t = live.fqn("transactions_2114")
    bad = {"DROP TABLE x": "keyword", f"SELECT 1 FROM {t}; SELECT 2": "one statement",
           "SELECT * FROM system.access.audit": "allowlist", f"UPDATE {t} SET a=1": "SELECT",
           f"SELECT * FROM {t} t JOIN other.s.x y ON 1=1": "allowlist",
           # a table hidden inside the FROM-masking: must still be seen
           f"SELECT extract(year FROM (SELECT d FROM secret.s.t)) FROM {t}": "allowlist",
           f"SELECT trim(BOTH FROM (SELECT max(x) FROM other.s.y)) FROM {t}": "allowlist"}
    rejected = 0
    for sql in bad:
        try:
            live.guard(sql)
        except ValueError:
            rejected += 1
    reg("SQL guard rejects writes, multiple statements and other tables",
        rejected == len(bad), f"{rejected}/{len(bad)}")
    try:
        ok = live.guard(f"WITH a AS (SELECT * FROM {t}) SELECT extract(year FROM current_date()) y, "
                        f"count(*) FROM a").startswith("SELECT * FROM (")
    except ValueError as exc:
        ok = False
        print("   guard refused a valid read:", exc)
    reg("SQL guard accepts a read over the allowlist, CTEs and EXTRACT included", ok)

    grants = (Path(__file__).resolve().parents[1] / "deploy/grants_front_center.sql").read_text()
    # TABLE or VIEW: source data is granted through the srcv_ views (B29).
    granted = set(re.findall(r"GRANT SELECT ON (?:TABLE|VIEW) [\w]+\.[\w]+\.(\w+)", grants))
    allowed = {live.PREFIX + v for v in live.TABLES.values()}
    reg("every allowlisted table is granted, and nothing else", granted == allowed,
        f"missing {sorted(allowed - granted)} extra {sorted(granted - allowed)}")

    # Agent loop with a stub model: one tool call, then an answer.
    calls = []

    def fake(model, body):
        calls.append(model)
        if len([m for m in body["messages"] if m.get("role") == "tool"]) == 0 and body.get("tools"):
            return {"choices": [{"message": {"role": "assistant", "content": [{"type": "reasoning", "summary": []}],
                    "tool_calls": [{"id": "t1", "type": "function", "function": {
                        "name": "find_transactions",
                        "arguments": '{"contract": "N0002409C2116", "largest_first": true, "limit": 3}'}}]}}]}
        return {"choices": [{"message": {"role": "assistant", "content": [
            {"type": "reasoning", "summary": []}, {"type": "text", "text": "948 actions [N0002409C2116]"}]}}]}
    real = agent._call_model
    agent._call_model = fake
    try:
        r = c.post("/api/ask", json={"question": "How many actions on 2116?"}).json()
    finally:
        agent._call_model = real
    reg("agent: tool loop runs, answer is text parts only, graded lead",
        r.get("mode") == "agent" and r.get("answer") == "948 actions [N0002409C2116]"
        and r.get("grade") == "lead", str(r)[:160])
    reg("agent: citations come from the tool results",
        any(x["kind"] == "transaction" and "N0002409C2116" in x["label"] for x in r.get("citations", [])))

    def broken(model, body):
        raise RuntimeError("endpoint down")
    agent._call_model = broken
    try:
        r = c.post("/api/ask", json={"question": "cost cap"}).json()
    finally:
        agent._call_model = real
    reg("agent: no model reachable falls back to search and says so",
        r.get("mode") == "search-only" and "endpoint down" in r.get("reason", ""), str(r)[:120])
    reg("agent: empty question is a 400", c.post("/api/ask", json={"question": " "}).status_code == 400)
    # 2026-11-11 model routing: app defaults, seed/models.yaml, bundle variables
    # and app resources must name the same endpoints, and no chain uses Claude.
    import yaml
    chains = agent.DEFAULT_CHAINS
    seed_roles = yaml.safe_load((ROOT / "seed" / "models.yaml").read_text())["roles"]
    bvars = {k: v.get("default") for k, v in
             yaml.safe_load((ROOT / "databricks.yml").read_text())["variables"].items()}
    app_yml = (ROOT / "resources" / "app.yml").read_text()
    flat = {m for p, fb in chains.values() for m in (p, *fb)}
    reg("models: app defaults equal seed/models.yaml",
        all((seed_roles[r]["primary"], tuple(seed_roles[r]["fallbacks"])) == c
            for r, c in chains.items()), str(chains)[:120])
    reg("models: bundle variables equal app defaults",
        all(bvars[f"{r}_model"] == p and bvars[f"{r}_fallbacks"] == ",".join(fb)
            for r, (p, fb) in chains.items()))
    res_vars = ("agent_model", "reasoning_model", "checker_model", "fallback_model")
    reg("models: every chain endpoint has a CAN_QUERY resource",
        flat <= {bvars[v] for v in res_vars}
        and all(f"name: ${{var.{v}}}" in app_yml for v in res_vars),
        str(sorted(flat - {bvars[v] for v in res_vars})))
    reg("models: no Claude endpoint in any chain", not any("claude" in m for m in flat))
    reg("models: agent chain has no GPT-6 (no function tools on chat)",
        not any(m.startswith("databricks-gpt-6") for m in agent.models()), str(agent.models()))

    # 2026-11-09: tables come from the cell store, chunks only locate pages.
    masked = agent.mask_figures("FY 2027 total $13,409.970 (1,234.5) and 11,398")
    reg("search masks figures, keeps years",
        "13,409" not in masked and "1,234" not in masked and "11,398" not in masked
        and "2027" in masked, masked)
    names = [t["function"]["name"] for t in agent.TOOLS]
    reg("agent has get_exhibit_cells", "get_exhibit_cells" in names, str(names))
    reg("exhibit cells: needs a filter, validates exhibit",
        "error" in agent.t_get_exhibit_cells()[0]
        and "error" in agent.t_get_exhibit_cells(exhibit="DROP TABLE x")[0])
    off = agent.t_get_exhibit_cells(exhibit="P-5c", page=96)[0]
    reg("exhibit cells offline: says why, names the table, no figures",
        "live cell store" in off.get("error", "")
        and any(t["table_id"] == "bb2e90fd1d91a0bc:0096:00" for t in off.get("tables", []))
        and "cells" not in off, str(off)[:160])
    seen = {}
    real_q, real_s = live.query, live.status
    live.status = lambda max_age_s=120: {"live": True, "reason": ""}
    live.query = lambda sql, params=None, **kw: (seen.update(sql=sql, p=params) or ([], []))
    try:
        agent.t_get_exhibit_cells(exhibit="P-5c", line_item="2001", fiscal_year="2013")
    finally:
        live.query, live.status = real_q, real_s
    reg("exhibit cells SQL is parameterised and joins the ledger unit",
        ":exh" in seen.get("sql", "") and ":bli" in seen["sql"] and ":fy" in seen["sql"]
        and "P-5c" not in seen["sql"] and live.fqn("claim") in seen["sql"]
        and "superseded_by IS NULL" in seen["sql"], seen.get("sql", "")[:120])
    kbx = main._kb()
    reg("shipped KB is available for the search check", getattr(kbx, "available", False))
    if getattr(kbx, "available", False):
        hits = agent.t_search_documents(kbx, "P-5c Ship Cost Analysis Carrier Replacement", 6)[0]["hits"]
        tp = [h for h in hits if h["kind"] == "table_page"]
        reg("search on exhibit pages returns table ids with figures masked",
            tp and all(h["table_ids"] or h["exhibits"] for h in tp)
            and not any(re.search(r"\d{1,3}(?:,\d{3})+|\d+\.\d+", h["text"]) for h in tp),
            f"{len(tp)} table pages")

    css_all = (Path(__file__).resolve().parents[1] / "app/static/css/app.css").read_text()
    defined = set(re.findall(r"(--[a-z0-9-]+)\s*:", css_all))
    used = set(re.findall(r"var\((--[a-z0-9-]+)", css_all))
    tpl_dir = Path(__file__).resolve().parents[1] / "app/templates"
    for p in tpl_dir.glob("*.html"):
        used |= set(re.findall(r"var\((--[a-z0-9-]+)", p.read_text()))
    reg("every CSS variable used is defined", used <= defined, f"undefined {sorted(used - defined)}")

    # Who can close what: free-text executors fold onto real offices. If
    # this regresses to one row per gap the panel answers nothing.
    asks = main._asks(main.data.get("gaps"))
    unrec = [a for a in asks if a["executor"] == "Unrecognised office"]
    n_open = sum(1 for r in main.data.get("gaps")["rows"] if not r.get("closed"))
    reg("asks: open gaps fold onto at most 25 offices", len(asks) <= 25, f"{len(asks)} rows for {n_open} gaps")
    reg("asks: no more than 3 gaps name no recognisable office",
        not unrec or len(unrec[0]["gaps"]) <= 3, str(unrec[0]["gaps"]) if unrec else "none")
    reg("asks: every open gap appears at least once",
        len({gid for a in asks for gid in a["gaps"]}) == n_open)

    from contrast import palette, ratio as cratio  # noqa: E402
    css = (Path(__file__).resolve().parents[1] / "app/static/css/app.css").read_text()
    worst, worst_pair = 99.0, ""
    for theme, sel in [("light", ":root {"), ("dark", 'html[data-theme="dark"] {')]:
        pal = palette(css, sel)
        for f in ("fg", "fg-2", "fg-3", "mut", "accent", "ok", "warn", "bad", "info"):
            for b in ("bg", "bg-2", "bg-3", "bg-sunk"):
                if f in pal and b in pal:
                    r = cratio(pal[f], pal[b])
                    if r < worst:
                        worst, worst_pair = r, f"{theme} --{f} on --{b}"
    reg("no text colour is under 4.5:1 on any background", worst >= 4.5,
        f"worst is {worst:.2f}:1 ({worst_pair})")

    print()
    if FAIL:
        for f in FAIL:
            print("FAILURE:", f)
        return 1
    print("all checks pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main_())
