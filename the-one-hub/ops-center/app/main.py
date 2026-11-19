"""Air Carrier front center.

FastAPI serves both the JSON API and the server-rendered pages. One process,
one port, which is what Databricks Apps wants. Jinja2 templates give the
Flask-style page composition; FastAPI gives the typed API and the OpenAPI
document that other consumers and the ops center read.

No CDN and no build step. Charts are server-rendered SVG that inherits the
page theme through CSS custom properties. A restricted IL5 workspace is
deny-by-default on egress, so anything loaded from a CDN renders nothing
after transfer.

    uvicorn main:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import os
import pathlib

from fastapi import FastAPI, Query, Request
from fastapi.responses import (HTMLResponse, JSONResponse, PlainTextResponse,
                               RedirectResponse, Response)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from api import charts, data, explore, live, rulebook
from api.sqlsafe import compose
from api import harness as work
from api import identity
from api.si import router as si_router
from api.si import store as si_store
from api.si import tasks as si_tasks

HERE = pathlib.Path(__file__).resolve().parent

app = FastAPI(
    title="Air Carrier",
    description="CVN-79 program cost. How it is reported, how it was recorded, "
                "where those diverge and why.",
    version="0.1.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
tpl = Jinja2Templates(directory=str(HERE / "templates"))


# ------------------------------------------------------- deployment inventory
# What the container actually received, reported by the container.
#
# This exists because of a failure that cost an afternoon of inference. Every
# page returned TemplateNotFound for overview.html while the CLI's own sync
# snapshot listed all eighteen templates as uploaded, the bundle deploy
# reported success, and a fresh app deployment started cleanly. From outside
# there was no way to tell whether the files were wrong in the workspace, lost
# on the way into the container, or present and unreadable. Each of those has
# a different fix and the evidence could not separate them.
#
# A process that cannot say what is on its own disk is a process that can only
# be debugged by guessing. This prints the inventory at startup, where it
# lands in the app log before the first request, and serves it at /api/_diag.
# It is cheap, it is read-only, and the one time it is needed it replaces an
# afternoon with a glance.
def _inventory() -> dict:
    tree: dict[str, dict] = {}
    for d in sorted([HERE] + [p for p in HERE.iterdir() if p.is_dir()]):
        try:
            files = [f for f in d.iterdir() if f.is_file()]
        except OSError as exc:
            tree[d.name if d != HERE else "."] = {"error": str(exc)}
            continue
        exts: dict[str, int] = {}
        for f in files:
            exts[f.suffix or "(none)"] = exts.get(f.suffix or "(none)", 0) + 1
        tree[d.name if d != HERE else "."] = {
            "files": len(files),
            "by_extension": dict(sorted(exts.items())),
            "sample": sorted(f.name for f in files)[:8],
        }
    return {
        "source_code_root": str(HERE),
        "template_dir": str(HERE / "templates"),
        "template_dir_exists": (HERE / "templates").is_dir(),
        "templates_found": sorted(
            p.name for p in (HERE / "templates").glob("*")
        ) if (HERE / "templates").is_dir() else [],
        "tree": tree,
    }


def _log_inventory() -> None:
    inv = _inventory()
    print("[aircarrier] source code root:", inv["source_code_root"], flush=True)
    for name, d in inv["tree"].items():
        if "error" in d:
            print(f"[aircarrier]   {name}/  ERROR {d['error']}", flush=True)
            continue
        print(f"[aircarrier]   {name}/  {d['files']} file(s)  "
              f"{d['by_extension']}", flush=True)
    if not inv["template_dir_exists"]:
        print("[aircarrier] NO templates/ DIRECTORY. Every page will fail. "
              "The deployment did not carry it.", flush=True)
    elif not inv["templates_found"]:
        print("[aircarrier] templates/ EXISTS BUT IS EMPTY. The directory "
              "survived the deployment and its contents did not.", flush=True)
    elif not any(n.endswith(".html") for n in inv["templates_found"]):
        print("[aircarrier] templates/ HAS NO .html FILES. Found instead: "
              f"{inv['templates_found'][:10]}. The names changed on the way "
              "in, which is what an import that treats .html as a notebook "
              "format does.", flush=True)


_log_inventory()


@app.get("/api/_diag")
def api_diag():
    """What this container has on disk. Read-only, no data, no secrets."""
    return _inventory()

# Fourteen top-level tabs is a list, not a navigation. Grouped into six, by
# the question a person arrives with rather than by how the code is organised:
# what is the headline, what is the ship, what is the evidence, how do I help,
# how is the build going.
#
# NAV_GROUPS drives the menu. NAV stays flat and derived, because the route
# tests, the active-page marking and the API all want a flat list and keeping
# two hand-maintained copies is how a page quietly stops appearing.
#
# 2026-11-09: Position is the PLAN section 4 screen and gets its own top-level
# link. Analyze groups the three working surfaces: the decision dashboard,
# the detail table and the agent. Delivery and Build progress were two pages
# about the same thing and are now one Program page; their old routes
# redirect.
#
# 2026-11-11: the Kennedy picture (/mission) is the page-triggered SI surface:
# every value recomputed from the records, every AI action a button that names
# its subject. The run log (/runs) keeps every run and every action.
#
# 2026-11-11: ten top-level items had crept back. Kennedy picture, Work queue
# and Run log are working surfaces and join Analyze; Program is about how the
# product is built and joins Method under Evidence. Top level is now the
# headline (Overview, Position), three menus, and Contribute as the call to
# action.
NAV_GROUPS = [
    ("Overview", "/", []),
    ("Position", "/position", []),
    ("Analyze", None, [
        ("/mission", "Kennedy picture"),
        ("/dashboard", "Decision dashboard"),
        ("/work", "Work queue"),
        ("/explore", "Detail table"),
        ("/ask", "Ask the evidence"),
        ("/runs", "Run log"),
    ]),
    ("The ship", None, [
        ("/kennedy", "USS John F. Kennedy (CVN-79)"),
        ("/cost", "Cost composition"),
        ("/execution", "Budget execution"),
        ("/baseline", "Baseline and caps"),
        ("/asset", "Asset and accounting"),
        ("/industrial", "Industrial base"),
    ]),
    ("Evidence", None, [
        ("/variances", "Variance register"),
        ("/gaps", "Gap register"),
        ("/knowledge", "Knowledge base"),
        ("/sources", "Sources"),
        ("/coverage", "Coverage map"),
        ("/method", "Method"),
        ("/rules", "Rule codes"),
        ("/program", "Build progress"),
    ]),
    ("Contribute", "/insight", []),
]

NAV = []
for _label, _href, _kids in NAV_GROUPS:
    if _href:
        NAV.append((_href, _label))
    NAV.extend(_kids)


def _group_for(path: str) -> str | None:
    """Which top-level menu owns this route, so the menu marks itself active
    when a child page is open."""
    for label, href, kids in NAV_GROUPS:
        if href == path or any(k == path for k, _ in kids):
            return label
    return None


GALLERY = ["cvn79-047", "cvn79-002", "cvn79-029", "cvn79-028",
           "cvn79-049", "cvn79-051", "cvn79-052", "cvn79-008", "cvn79-004"]


def si_t(task_id: str, subject: str, params: dict | None = None, label: str | None = None) -> dict:
    """A trigger: the button names its scope, and the server routes it."""
    tpl = si_tasks.TASKS[task_id]
    subject = si_tasks.normalize(task_id, subject)
    return {"task_id": task_id, "subject": subject, "params": params or {},
            "label": label or tpl.scoped_label(subject), "question": tpl.question}


# The specialist runs each page offers, in the page's own terms. The E-16
# trigger tests the figure the variance register records as mislabelled.
SI_TRIGGERS = {
    "/": [si_t("brief_readiness", "CVN-79", label="Check brief readiness for CVN-79")],
    "/variances": [
        si_t("reconcile_obligations", "N0002409C2116",
             {"reported_total": "4519300323.83", "reported_label": "N00024-15-C-2114"},
             label="Test E-16: $4,519,300,323.83 labelled N00024-15-C-2114"),
        si_t("reconcile_obligations", "N0002409C2116"),
        si_t("reconcile_obligations", "N0002415C2114")],
    "/position": [si_t("explain_residual", p) for p in
                  ("FY2021P03", "FY2020P09", "FY2020P12", "FY2020Q1")],
    "/execution": [si_t("explain_residual", "FY2021P03")],
    "/gaps": [si_t("investigate_gap", g) for g in ("G46", "G52", "G14")],
}
# A trigger the router would refuse is a build error, not a page that fails
# when someone presses the button.
for _p, _ts in SI_TRIGGERS.items():
    for _t in _ts:
        if _p not in si_tasks.TASKS[_t["task_id"]].pages:
            raise RuntimeError(f"SI trigger {_t['task_id']} is on {_p}, which the task "
                               "does not list in its pages (api/si/tasks.py)")


def page(request: Request, name: str, title: str, **ctx) -> HTMLResponse:
    # A missing template is a deployment fact, not a programming error, and a
    # 500 with a Jinja traceback says neither which file nor what the
    # container actually holds. Answer the question in the response.
    if not (HERE / "templates" / name).is_file():
        inv = _inventory()
        return HTMLResponse(status_code=503, content=(
            "<html><body style='font:14px ui-monospace,monospace;padding:2rem'>"
            f"<h2>{name} is not in this deployment</h2>"
            f"<p>Template directory: <code>{inv['template_dir']}</code><br>"
            f"Exists: <b>{inv['template_dir_exists']}</b><br>"
            f"Contains: <code>{inv['templates_found'] or 'nothing'}</code></p>"
            "<p>The application code is fine. The files did not arrive. "
            "Full inventory at <a href='/api/_diag'>/api/_diag</a>, and the "
            "same listing is printed in the app log at startup.</p>"
            f"<pre>{inv['tree']}</pre>"
            "</body></html>"))
    return tpl.TemplateResponse(
        request=request, name=name,
        context={"nav": NAV, "nav_groups": NAV_GROUPS,
                 "active": request.url.path,
                 "active_group": _group_for(request.url.path),
                 "page_title": title,
                 "backend": data.backend_info(), "C": charts, "fmt": charts.fmt,
                 "gallery": GALLERY,
                 "si_triggers": SI_TRIGGERS.get(request.url.path, []), **ctx})


# ---------------------------------------------------------------- work queue
# Exceptions, the exception card, and apply or reject through a confirmation
# page. The service and the authority rule live in api/harness.py and
# api/harness_sql.py; these routes only render them. /api/v1 is the same
# service as JSON.
app.include_router(work.router)
app.include_router(si_router.router)


# ---------------------------------------------------------------------- SI
def _bars(series: list[dict], w: int = 560, h: int = 120) -> dict:
    """Geometry for one contract's by-FY bars. Display only: heights are
    proportions of the server's own sums, and every label is its display string."""
    from decimal import Decimal
    vals = [Decimal(s["amount"]) for s in series] or [Decimal(0)]
    top, bot = max(max(vals), Decimal(0)), min(min(vals), Decimal(0))
    span = (top - bot) or Decimal(1)
    zero = float(top / span) * h
    n = max(len(series), 1)
    slot = w / n
    bw = max(slot * 0.72, 2)
    out = []
    for i, (s, v) in enumerate(zip(series, vals)):
        bh = max(abs(float(v / span)) * h, 1.0)
        y = zero - bh if v >= 0 else zero
        out.append({"fy": s["fy"], "x": round(i * slot + (slot - bw) / 2, 2), "y": round(y, 2),
                    "bw": round(bw, 2), "bh": round(bh, 2), "neg": v < 0,
                    "display": s["display"], "count": s["count"],
                    "label": n <= 14 or i % 2 == 0})
    return {"w": w, "h": h, "zero": round(zero, 2), "bars": out}


@app.get("/mission", response_class=HTMLResponse)
def mission(request: Request, fresh: int = 0):
    P = si_router.api_picture(request, fresh=fresh)
    bars = {c["piid"]: _bars(c["series"]) for c in P["contracts"]}
    return page(request, "mission.html", "Kennedy picture", P=P, bars=bars,
                T={"brief": si_t("brief_readiness", "CVN-79",
                                 label="Check brief readiness for CVN-79")},
                runs=[r.view(full=False) for r in si_store.STORE.list(limit=8)])


@app.get("/runs", response_class=HTMLResponse)
def runs_page(request: Request):
    return page(request, "runs.html", "Run log", run=None,
                runs=[r.view(full=False) for r in si_store.STORE.list(limit=200)],
                activity=list(si_store.STORE.activity)[:300], mode=si_store.mode(),
                max_runs=si_store.STORE.max_runs)


@app.get("/runs/{run_id}", response_class=HTMLResponse)
def run_page(request: Request, run_id: str):
    # Memory first, then the harness tables (a run outlives an app restart).
    load_error = None
    try:
        r = si_router.find_run(run_id)
    except Exception as exc:  # noqa: BLE001 - the page says the load failed, and why
        r, load_error = None, str(exc)[:300]
    if r is None:
        return page(request, "runs.html", "Run log", run=None, runs=[],
                    activity=[], mode=si_store.mode(), max_runs=si_store.STORE.max_runs,
                    missing=run_id, load_error=load_error)
    decisions_error = None
    if getattr(r, "loaded_from_tables", False):
        _ident, _q_app, q_user = work.runners(request)
        decisions_error = si_store.load_decisions(r, q_user, work.H.tables())
    return page(request, "runs.html", f"Run {run_id[:8]}", run=r.view(full=True),
                decisions_error=decisions_error)

_WORK_FILTERS = [("area", "Area"), ("status", "Status"), ("owner_role", "Owner"), ("rule_id", "Rule")]


def _same_origin(request: Request) -> bool:
    """A form post must come from this app's own pages."""
    from urllib.parse import urlparse
    origin = request.headers.get("origin") or request.headers.get("referer")
    if not origin:
        return request.headers.get("sec-fetch-site") in (None, "same-origin")
    return urlparse(origin).netloc == request.headers.get("host", request.url.netloc)


@app.get("/work", response_class=HTMLResponse)
def work_queue(request: Request, area: str = "", status: str = "open", owner_role: str = "",
               rule_id: str = "", sort: str = "detected_at", descending: bool = True,
               page_no: int = Query(1, alias="page", ge=1), view: str = ""):
    # The query parameter is ?page=, but the local is page_no: a local named
    # page would shadow page(), the function that renders every template.
    from urllib.parse import urlencode
    ident, q_app, q_user = work.runners(request)
    me = {"obo": q_user is not None, "email": ident.email,
          "reason": identity.obo_missing_reason()}
    if view != "table":
        # WORK_QUEUE_V2: the three lanes. ?view=table keeps the raw exception list.
        try:
            lanes, lane_error = work.lanes(q_app, q_user), None
        except Exception as exc:  # noqa: BLE001 - the page says what failed
            lanes, lane_error = None, str(exc)[:400]
        return page(request, "work_lanes.html", "Work queue", L=lanes, error=lane_error, me=me)
    filters = {"area": area, "status": status, "owner_role": owner_role, "rule_id": rule_id}
    result, error, options, status_counts = None, None, [], []
    try:
        result = work.list_exceptions(q_app, filters=filters, sort=sort,
                                      descending=descending, page=page_no)
        facet = q_app(compose(
            "SELECT collect_set(area) AS area, collect_set(status) AS status, "
            "collect_set(owner_role) AS owner_role, collect_set(rule_id) AS rule_id FROM {t}",
            t=work.H.tables()["exceptions"]), {})[0]
        # 2026-11-12: the default filter is status=open, but 'open' was only an
        # option when some row had it. With none, the select showed "Any" while
        # the list was filtered to open, so the page looked empty until Apply
        # sent status="". The active value is now always an option, and the
        # page shows a count per status so an empty queue says why.
        options = []
        for k, label in _WORK_FILTERS:
            vals = set(work._arr(facet[k]))
            if filters.get(k):
                vals.add(filters[k])
            if k == "status":
                vals.add("open")
            options.append((k, label, sorted(vals)))
        status_counts = [(r["status"], int(r["n"])) for r in q_app(compose(
            "SELECT status, count(*) AS n FROM {t} GROUP BY status ORDER BY n DESC",
            t=work.H.tables()["exceptions"]), {})]
    except Exception as exc:  # noqa: BLE001 - the page says what failed
        error = str(exc)[:400]
    base = {"view": "table", **{k: v for k, v in filters.items() if v}}

    def sort_href(key: str) -> str:
        desc = not descending if sort == key else True
        return "/work?" + urlencode({**base, "sort": key, "descending": str(desc).lower()})

    def page_href(n: int) -> str:
        return "/work?" + urlencode({**base, "sort": sort, "descending": str(descending).lower(),
                                     "page": n})

    def status_href(s: str) -> str:
        return "/work?" + urlencode({**{k: v for k, v in base.items() if k != "status"},
                                     "status": s})

    return page(request, "work.html", "Work queue", result=result, error=error,
                filter_options=options, sort_href=sort_href, page_href=page_href,
                status_counts=status_counts, status_href=status_href,
                status_total=sum(n for _s, n in status_counts),
                me={"obo": q_user is not None, "email": ident.email,
                    "reason": identity.obo_missing_reason()})


@app.get("/work/exceptions/{exception_id}", response_class=HTMLResponse)
def work_exception(request: Request, exception_id: str, req: str = ""):
    _ident, q_app, q_user = work.runners(request)
    card = work.exception_card(q_app, q_user, exception_id)
    if card is None:
        return page(request, "work.html", "Not found", result=None, filter_options=[],
                    error_title="Not found.",
                    error=f"No exception with id {exception_id}.", sort_href=str, page_href=str,
                    me={"obo": True})
    outcome = next((a for a in card["attempts"] if req and a.get("request_id") == req), None)
    return page(request, "exception.html", "Exception", card=card, outcome=outcome,
                obo_reason=identity.obo_missing_reason())


def _proposal_on_card(request: Request, proposal_id: str, exception_id: str):
    _ident, q_app, q_user = work.runners(request)
    card = work.exception_card(q_app, q_user, exception_id)
    if card is None:
        return None, None
    return card, next((p for p in card["proposals"] if p["proposal_id"] == proposal_id), None)


@app.get("/work/proposals/{proposal_id}/confirm", response_class=HTMLResponse)
def work_confirm(request: Request, proposal_id: str, action: str, exception_id: str):
    import uuid as _uuid
    if action not in ("apply", "reject"):
        return PlainTextResponse("action must be apply or reject", status_code=400)
    card, p = _proposal_on_card(request, proposal_id, exception_id)
    if p is None:
        return PlainTextResponse("no such proposal on this exception", status_code=404)
    return page(request, "confirm.html", "Confirm", card=card, p=p, action=action,
                request_id=str(_uuid.uuid4()))


@app.post("/work/proposals/{proposal_id}/{action}")
async def work_act(request: Request, proposal_id: str, action: str):
    """The form post from confirm.html. Authority is decided in the statement."""
    from urllib.parse import parse_qs, quote
    if action not in ("apply", "reject"):
        return PlainTextResponse("action must be apply or reject", status_code=400)
    if not _same_origin(request):
        return PlainTextResponse("cross-origin form posts are refused", status_code=403)
    form = parse_qs((await request.body()).decode("utf-8"), keep_blank_values=True)
    allowed_fields = {"confirmed_record_ids", "request_id", "exception_id", "notes"}
    if set(form) - allowed_fields:
        return PlainTextResponse("unexpected fields: " + ", ".join(sorted(set(form) - allowed_fields)),
                                 status_code=422)
    exception_id = (form.get("exception_id") or [""])[0]
    notes = (form.get("notes") or [""])[0].strip()
    if action == "reject" and not notes:
        return PlainTextResponse("a reason is required to reject", status_code=422)
    request_id = (form.get("request_id") or [""])[0][:64] or None
    _ident, _q_app, q_user = work.runners(request)
    try:
        work.act(q_user, proposal_id=proposal_id, action=action,
                 confirmed_record_ids=form.get("confirmed_record_ids", []),
                 notes=notes or None, request_id=request_id)
    except Exception as exc:  # noqa: BLE001 - the transaction rolled back; say so
        return page(request, "work.html", "Not recorded", result=None, filter_options=[],
                    sort_href=str, page_href=str, me={"obo": q_user is not None},
                    error_title="Not recorded.",
                    error=("Nothing was recorded. The transaction failed and rolled back, so no "
                           f"decision, determination or status change was written. {str(exc)[:300]}"))
    return RedirectResponse(f"/work/exceptions/{quote(exception_id)}?req={quote(request_id or '')}",
                            status_code=303)


# --------------------------------------------------------------------- pages
@app.get("/", response_class=HTMLResponse)
def overview(request: Request):
    return page(request, "overview.html", "Overview",
                program=data.get("program"), attribution=data.get("attribution"),
                layers=data.get("layers"), gaps=data.get("gaps"),
                cost=data.get("cost_categories"), contracts=data.get("contracts"),
                industrial=data.get("industrial"))


@app.get("/kennedy", response_class=HTMLResponse)
def kennedy(request: Request):
    return page(request, "kennedy.html", "Kennedy",
                program=data.get("program"), timeline=data.get("timeline"))


def _stream_rows(streams: dict) -> list[dict]:
    """Pivot the funding streams into one row per fiscal year for the stacked chart."""
    years: dict[int, dict] = {}
    for s in streams["streams"]:
        for y, v in s["by_year"].items():
            years.setdefault(int(y), {"fy": int(y)})[s["name"]] = v
    return [years[y] for y in sorted(years)]


@app.get("/cost", response_class=HTMLResponse)
def cost(request: Request):
    streams = data.get("funding_streams")
    return page(request, "cost.html", "Cost decomposition",
                cost=data.get("cost_categories"), streams=streams,
                stream_rows=_stream_rows(streams),
                stream_series=[(s["name"], s["name"]) for s in streams["streams"]],
                attribution=data.get("attribution"), equipment=data.get("equipment"),
                program=data.get("program"))


@app.get("/execution", response_class=HTMLResponse)
def execution(request: Request):
    return page(request, "execution.html", "Program execution",
                contracts=data.get("contracts"), obl=data.get("obligations"),
                accounts=data.get("federal_accounts"), subs=data.get("subawards"))


MECH_COLOR = {"estimate": "var(--c1)", "statute": "var(--c3)", "overrun": "var(--c4)",
              "scope": "var(--c2)", "reclass": "var(--c9)"}


@app.get("/baseline", response_class=HTMLResponse)
def baseline(request: Request):
    hist = data.get("estimate_history")
    pts = [{"x": r["y"], "y": r["value"], "label": r["as_of"],
            "mech": r["mech"], "note": r["what"]} for r in hist["rows"]]
    return page(request, "baseline.html", "Baseline and cost growth",
                hist=hist, points=pts, mech_color=MECH_COLOR,
                caps=data.get("cap_history"),
                anchor=data.get("anchor_chain"), program=data.get("program"))


@app.get("/industrial", response_class=HTMLResponse)
def industrial(request: Request):
    return page(request, "industrial.html", "Industrial base",
                ind=data.get("industrial"), eq=data.get("equipment"),
                subs=data.get("subawards"), program=data.get("program"))


@app.get("/asset", response_class=HTMLResponse)
def asset(request: Request):
    return page(request, "asset.html", "Asset valuation",
                asset=data.get("asset"), program=data.get("program"))


@app.get("/variances", response_class=HTMLResponse)
def variances(request: Request):
    return page(request, "variances.html", "Variance register", v=data.get("variances"))


CLOS_W = {"zero_access": 1.00, "query": 0.80, "access_required": 0.35,
          "sme": 0.25, "terminal": 0.05, "unknown": 0.50}


@app.get("/gaps", response_class=HTMLResponse)
def gaps(request: Request):
    g = data.get("gaps")
    bub = []
    # Only scored gaps are plotted. y is ignorance, and an unscored gap carries
    # the 0.5 placeholder, so it has no honest position. Plotting the 37 gaps
    # adopted on 2026-11-09 at that placeholder stacked them in the
    # access_required column past what the layout can separate. They stay in
    # the table, and the page says how many are not plotted and why.
    unsized = [r for r in g["rows"]
               if not r["closed"] and not r.get("scored", True)]
    for r in g["rows"]:
        if r["closed"] or not r.get("scored", True):
            continue
        w = CLOS_W.get(r["closability"], 0.5)
        cls = "free" if w >= 0.8 else ("hot" if r["exposure_usd_m"] > 1000 else "")
        bub.append({"id": r["id"], "x": w, "y": r["ignorance"],
                    "r": max(r["exposure_usd_m"], 40.0), "cls": cls,
                    "label": f"{r['id']} {r['title']} · "
                             f"${r['exposure_usd_m']:,.0f}M · {r['closability']}"})
    # The page's own headline is "the discovery queue", so the table opens in
    # queue order rather than identifier order: open gaps by priority, closed
    # ones last. Sorting by ID put G1, G2 and G3 at the top, which are three of
    # the least urgent rows in the register, and made the table look like a
    # list of everything rather than a plan.
    ranked = sorted(g["rows"], key=lambda r: (r["closed"], -r["priority"], r["id"]))
    return page(request, "gaps.html", "Gap register", g=g, bub=bub, ranked=ranked,
                unsized=unsized)


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    """The executive view. One screen that answers: where does the ship stand,
    what is the position against the ceilings, how much is explained, what is
    unresolved, and what should happen next."""
    from api.insights import derive, by_kind

    names = ["program", "cost_categories", "funding_streams", "anchor_chain",
             "attribution", "contracts", "obligations", "gaps", "variances",
             "cap_history", "estimate_history", "corpus", "subawards"]
    d = {n: data.get(n) for n in names}
    items = by_kind(derive(d))

    cost, attr = d["cost_categories"], d["attribution"]
    caps = {c["name"]: float(c["value"]) for c in d["cap_history"].get("three_ceilings", [])}
    total = float(cost["total"])
    stat = caps.get("Statutory cost cap", 0.0)
    clb = caps.get("SECNAV Cost Limitation Baseline", 0.0)

    est = d["estimate_history"].get("rows", [])
    gap_rows = [r for r in d["gaps"]["rows"] if not r["closed"]]

    # Exposure against confidence. Confidence is 1 - ignorance, so right is
    # better understood and the top right corner is the dangerous quadrant:
    # large, unexplained, and not even well characterised.
    mx = max([float(r.get("exposure_usd_m") or 0) for r in gap_rows] + [1.0])
    risk_items = [{
        "x": 1.0 - float(r.get("ignorance") or 0.5),
        "y": (float(r.get("exposure_usd_m") or 0) / mx) ** 0.5,
        "label": r["id"],
        "title": f"{r['id']}: {r['title']} \u00b7 ${r.get('exposure_usd_m', 0):,.0f}M",
        "cls": "free" if r.get("closability") in ("zero_access", "query") else
               ("hot" if float(r.get("exposure_usd_m") or 0) > 1000 else ""),
    } for r in gap_rows if float(r.get("exposure_usd_m") or 0) > 0]

    return page(request, "dashboard.html", "Decision dashboard",
                d=d, items=items, total=total, stat=stat, clb=clb, caps=caps,
                attr=attr, est=est, risk_items=risk_items,
                live_var=[r for r in d["variances"]["rows"] if r["status"] == "live"],
                tie=explore.extract("tieout"), pipe=_pipeline(),
                asks=_asks(d["gaps"]), leads=_leads(), xmeta=explore.meta())


# The register's executor field is free text, one phrasing per gap (57
# spellings for 59 open gaps on 2026-11-09), so grouping on it verbatim
# answers nothing. These patterns fold it onto the offices a sponsor can
# actually introduce someone to. A gap naming several offices is counted
# under each, because any of them could close it; rows therefore overlap and
# the page says so. A gap matching none is listed as unrecognised, never
# dropped.
OFFICES = [
    ("PEO Aircraft Carriers (PMS 378)", r"PEO\s*(Aircraft\s*)?Carriers|PMS\s*378|program office"),
    ("NAVSEA", r"NAVSEA|SEA\s*0?1\b|SUPSHIP"),
    ("ASN(FM&C) / FMB / FMO", r"FM&C|\bFMB\b|\bFMO\b|Financial Operations|Navy budget"),
    ("ASN(RD&A)", r"ASN\s*\(?\s*RD&?A|ASN\s*\(?\s*RDA"),
    ("OUSD(Comptroller)", r"OUSD\s*\(\s*C\s*\)|Comptroller"),
    ("OSD CAPE", r"\bCAPE\b"),
    ("USD(A&S) / MDA", r"USD\s*\(\s*A&S|Milestone Decision"),
    ("DCMA", r"\bDCMA\b"),
    ("DFAS", r"\bDFAS\b|MOCAS"),
    ("Naval Reactors / DOE", r"Naval Reactors|Department of Energy|\bDOE\b"),
    ("DOT&E", r"DOT&E"),
    ("Navy OGC", r"\bOGC\b|General Counsel"),
    ("Shipbuilder (HII)", r"\bHII\b|Huntington|shipbuilder|Newport News"),
    ("GAO / CRS / IG", r"\bGAO\b|\bCRS\b|Inspector General|\bDoDIG\b|\bIG\b"),
    ("Advana data product owners", r"Advana"),
    ("NCCA / OPNAV", r"\bNCCA\b|Naval Center for Cost Analysis|OPNAV"),
    ("NAVAIR", r"NAVAIR|\bPMA\s*\d+"),
    ("Navy Legislative Affairs", r"Legislative Affairs|\bOLA\b"),
]


def offices_for(executor: str) -> list[str]:
    import re as _re
    hit = [name for name, pat in OFFICES if _re.search(pat, executor or "", _re.I)]
    return hit or ["Unrecognised office"]


def _asks(g: dict) -> list[dict]:
    """Open gaps grouped by who can close them, which is the sponsor's
    question: whose door does an introduction open. Executor is the gap
    register's own field, folded onto canonical offices by OFFICES; scored
    exposure counts only gaps that have one."""
    reqs = explore.extract("requirements").get("rows", [])
    n_req: dict[str, int] = {}
    for r in reqs:
        if r.get("gap_id"):
            n_req[r["gap_id"]] = n_req.get(r["gap_id"], 0) + 1
    by: dict[str, dict] = {}
    for r in g.get("rows", []):
        if r.get("closed"):
            continue
        for ex in offices_for(r.get("executor") or ""):
            b = by.setdefault(ex, {"executor": ex, "gaps": [], "exposure": 0.0,
                                   "scored": 0, "requirements": 0, "access": 0, "free": 0})
            b["gaps"].append(r["id"])
            b["requirements"] += n_req.get(r["id"], 0)
            if float(r.get("exposure_usd_m") or 0):
                b["exposure"] += float(r["exposure_usd_m"])
                b["scored"] += 1
            if r.get("closability") == "access_required":
                b["access"] += 1
            if r.get("closability") in ("zero_access", "query"):
                b["free"] += 1
    # Most gaps moved first: that is what an introduction buys. Unrecognised
    # goes last whatever its size, so it reads as a to-do, not an office.
    return sorted(by.values(), key=lambda b: (b["executor"] == "Unrecognised office",
                                              -len(b["gaps"]), -b["exposure"], b["executor"]))


def _pipeline() -> dict:
    p = explore.extract("pipeline")
    if not p:
        return {}
    gate = {r["outcome"]: r["n"] for r in p.get("gate", [])}
    gated = sum(gate.values())
    return p | {"gate_map": gate, "gated": gated,
                "human": gate.get("human_review", 0),
                "human_pct": round(100.0 * gate.get("human_review", 0) / gated, 1) if gated else 0}


def _leads() -> list[dict]:
    """One row per question: the top-ranked option, its confidence and the
    engine's own 'none of these' mass, which is how sure it is that the
    answer is in the list at all."""
    best: dict[str, dict] = {}
    for r in explore.extract("leads").get("rows", []):
        k = (r.get("question"), r.get("piid"), r.get("period"), r.get("kind"))
        if k not in best or (r.get("rank") or 99) < (best[k].get("rank") or 99):
            best[k] = r
    return sorted(best.values(), key=lambda r: -(r.get("confidence") or 0))


# ----------------------------------------------------------- the one screen
@app.get("/position", response_class=HTMLResponse)
def position(request: Request):
    """PLAN section 4. Four published figures, why each pair differs, and the
    difference that cannot yet be explained, with the gap and the access."""
    caps = data.get("cap_history").get("three_ceilings", [])
    var = {r["id"]: r for r in data.get("variances").get("rows", [])}
    est = data.get("estimate_history").get("rows", [])
    e2 = next((r for r in est if abs(float(r.get("value") or 0) - 11341.4) < 1.0), None)
    figs = []
    if e2:
        figs.append({"name": "FY2019 budget estimate", "value": float(e2["value"]),
                     "basis": e2.get("as_of") or "FY2019 President's Budget",
                     "what": "A dated estimate in then-year dollars. Not a total, not a cap.",
                     "var": "E-2"})
    for c in caps:
        figs.append({"name": c["name"], "value": float(c["value"]), "basis": c.get("basis"),
                     "what": c.get("note") or "", "var": c.get("var") or "E-1"})
    figs.sort(key=lambda f: f["value"])
    for i, f in enumerate(figs):
        f["n"] = i + 1
        f.update(FIG_KIND.get(f["name"], {}))
    g = {r["id"]: r for r in data.get("gaps").get("rows", [])}
    anchor = data.get("anchor_chain")
    hist = data.get("estimate_history")
    from api import ladder as _ladder
    lad = _ladder.build()
    lad_sum = _ladder.summary(lad)
    return page(request, "position.html", "Four figures", figs=figs, var=var,
                anchor=anchor, attr=data.get("attribution"),
                g12=g.get("G12"), g22=g.get("G22"), gaps=g,
                ladder=lad, ladder_summary=lad_sum,
                **_position_drill(figs, caps, anchor, hist, var))


# What kind of object each figure is. Words, not numbers: every dollar value
# on the page is still read from the data bundle. The readings follow E-1,
# E-2 and the cap history; they are the app's, not a cleared position.
FIG_KIND = {
    "FY2019 budget estimate": {
        "kind": "Dated estimate", "cls": "est",
        "set_by": "Navy, in the FY2019 President's Budget",
        "binds": "Nothing. Superseded by every later submission.",
        "use": "Showing how the estimate moved over time",
        "avoid": "The cost of the ship, or a cap"},
    "Statutory cost cap": {
        "kind": "Limit in law", "cls": "law",
        "set_by": "Congress (10 U.S.C. 8692, as set by the FY2020 NDAA)",
        "binds": "Procurement cost, after the adjustments and exclusions the statute allows (which apply is G12)",
        "use": "Compliance with the statute",
        "avoid": "Expected cost, or the limit the Navy manages to"},
    "SECNAV Cost Limitation Baseline": {
        "kind": "Adjusted limit, notified", "cls": "adm",
        "set_by": "Secretary of the Navy, notification to Congress",
        "binds": "The limit the program manages to after the adjustments were notified",
        "use": "Program performance against its adjusted limit",
        "avoid": "The statutory cap"},
    "Budget submission total": {
        "kind": "Request and estimate to complete", "cls": "req",
        "set_by": "Navy, in the FY2027 President's Budget",
        "binds": "Nothing by itself. Money still has to be appropriated.",
        "use": "Current expected total procurement cost",
        "avoid": "A limit"},
}


def _position_drill(figs, caps, anchor, hist, var):
    """Everything below the four cards, derived from the bundle."""
    import re as _re
    steps = anchor.get("steps", [])
    rows = hist.get("rows", [])
    mech_lab = {m["id"]: m for m in hist.get("mechanisms", [])}
    cap0 = steps[0]["cum"] if steps else None

    # SECNAV's own adjustment authority, read from the cap note, not typed
    refs = []
    for c in caps:
        m = _re.findall(r"\$([\d,]+(?:\.\d+)?)M", c.get("note") or "")
        if c["name"].startswith("Statutory") and m:
            refs.append({"value": float(m[-1].replace(",", "")), "label": "SECNAV authority"})

    # each step of the chain, with the mechanism recorded for the estimate it lands on
    bridge = []
    for i, s in enumerate(steps[1:], 1):
        hit = next((r for r in rows if abs(float(r["value"]) - s["cum"]) < 0.01), None)
        mech = hit["mech"] if hit else None
        bridge.append({**s, "from": steps[i - 1]["cum"], "as_of": hit and hit["as_of"],
                       "authority": hit and hit["authority"], "what": hit and hit["what"],
                       "mech": mech, "mech_label": mech_lab.get(mech, {}).get("label", "not recorded"),
                       "mech_note": mech_lab.get(mech, {}).get("note", ""),
                       "contested": "E-7" if hit and hit.get("y") == 2027 and "E-7" in var else None})
    above = anchor.get("above_cap") or 0.0

    def split(key, label):
        acc = {}
        for b in bridge:
            k = b.get(key) or "not recorded"
            acc[k] = acc.get(k, 0.0) + b["delta"]
        return [{"key": k, "label": label(k), "usd_m": round(v, 2),
                 "pct": round(100 * v / above, 1) if above else 0.0}
                for k, v in sorted(acc.items(), key=lambda kv: -kv[1])]
    by_tag = split("tag", lambda k: k)
    by_mech = split("mech", lambda k: mech_lab.get(k, {}).get("label", k))
    contested = sum(b["delta"] for b in bridge if b["contested"])

    # every pair, not just neighbours
    pairs = {}
    for a in figs:
        for b in figs:
            if b["value"] <= a["value"]:
                continue
            if "E-2" in (a["var"], b["var"]):
                status, cls = "Different objects", "b-mut"
            else:
                inside = [s for s in bridge if s["cum"] > a["value"] + 0.001 and s["cum"] <= b["value"] + 0.001]
                tags = {s["tag"] for s in inside}
                status, cls = (("Bridged, read from documents", "b-ok") if tags == {"VERIFIED"} else
                               ("Bridged, partly derived", "b-warn") if inside else ("No bridge", "b-bad"))
            d = b["value"] - a["value"]
            pairs[(a["n"], b["n"])] = {"diff": round(d, 2), "pct": round(100 * d / a["value"], 1),
                                       "status": status, "cls": cls}

    # the estimate's own history, with where it sat against the statutory cap
    pts = [{"x": r["y"], "y": r["value"], "label": r["as_of"], "mech": r["mech"], "note": r["what"]}
           for r in rows]
    hist_rows = [{**r, "vs_cap": round(float(r["value"]) - cap0, 2) if cap0 else None} for r in rows]
    nl_points = [{"label": f["name"], "value": f["value"], "cls": f.get("cls", "")} for f in figs]
    bands = ([{"lo": cap0, "hi": figs[-1]["value"], "label": "above the statutory cap"}]
             if cap0 and figs and figs[-1]["value"] > cap0 else [])
    spread = round(figs[-1]["value"] - figs[0]["value"], 2) if figs else 0.0
    return {"bridge": bridge, "by_tag": by_tag, "by_mech": by_mech, "contested": round(contested, 2),
            "pairs": pairs, "points": pts, "mech_color": MECH_COLOR, "hist_rows": hist_rows,
            "mechanisms": hist.get("mechanisms", []), "net_movement_pct": hist.get("net_movement_pct"),
            "nl": charts.number_line(nl_points, bands=bands, refs=refs), "spread": spread,
            "spread_pct": round(100 * spread / figs[0]["value"], 1) if figs else 0.0,
            "secnav_ref": refs[0] if refs else None}


# ------------------------------------------------------------- detail table
@app.get("/explore", response_class=HTMLResponse)
def explore_page(request: Request, ds: str = "transactions"):
    if ds not in explore.DATASETS:
        ds = "transactions"
    return page(request, "explore.html", "Detail table", ds=ds,
                datasets=explore.DATASETS, xmeta=explore.meta(), live=live.status())


def _qargs(request: Request) -> dict:
    qp = dict(request.query_params)
    spec = explore.DATASETS.get(request.path_params.get("ds"), {})
    fields = {f for f, _l, _k in spec.get("cols", [])}
    return {"q": qp.get("q", ""), "sort": qp.get("sort"),
            "desc": qp.get("desc") in ("1", "true"),
            "filters": {k[2:]: v for k, v in qp.items() if k.startswith("f.") and k[2:] in fields}}


@app.get("/api/explore/{ds}", tags=["data"])
def api_explore(request: Request, ds: str, page_: int = 1, size: int = 50):
    """One page of a detail dataset. Filters are f.<field>=value."""
    if ds not in explore.DATASETS:
        return JSONResponse({"error": f"no dataset {ds}",
                             "available": sorted(explore.DATASETS)}, status_code=404)
    p = int(request.query_params.get("page", page_))
    return explore.query(ds, page=p, size=size, **_qargs(request))


@app.get("/api/explore/{ds}/csv", tags=["data"])
def api_explore_csv(request: Request, ds: str):
    if ds not in explore.DATASETS:
        return JSONResponse({"error": f"no dataset {ds}"}, status_code=404)
    return Response(explore.to_csv(ds, **_qargs(request)), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="aircarrier_{ds}.csv"'})


@app.get("/api/exhibit/{table_id}", tags=["data"])
def api_exhibit(table_id: str):
    """One budget exhibit table as a grid, read live from the cell store."""
    r = explore.cells(table_id)
    return JSONResponse(r, status_code=404 if "error" in r else 200)


@app.get("/api/live", tags=["data"])
def api_live():
    """Whether live Unity Catalog reads work from this deployment, and why not."""
    return live.status() | {"extracts": explore.meta()}


# -------------------------------------------------------------------- agent
@app.get("/ask", response_class=HTMLResponse)
def ask_page(request: Request):
    from api import agent
    return page(request, "ask.html", "Ask the evidence", models=agent.models(),
                live=live.status(), xmeta=explore.meta())


@app.post("/api/ask", tags=["agent"])
async def api_ask(request: Request):
    """The agent. Answers are leads, cited to the tool results they rest on."""
    from api import agent
    body = await request.json()
    q = (body.get("question") or "").strip()
    if not q:
        return JSONResponse({"error": "question is required"}, status_code=400)
    import anyio
    return await anyio.to_thread.run_sync(
        lambda: agent.ask(q, body.get("history") or [], kb=_kb()))


@app.get("/knowledge", response_class=HTMLResponse)
def knowledge(request: Request):
    """What the document corpus holds, what is indexed and what is not."""
    import json as _json
    corpus = data.get("corpus")
    kb = {}
    kbp = pathlib.Path(__file__).resolve().parent / "data" / "kb" / "summary.json"
    if kbp.exists():
        kb = _json.loads(kbp.read_text())
    rows = corpus.get("rows", []) if corpus else []
    return page(request, "knowledge.html", "Knowledge base",
                corpus=corpus, kb=kb,
                embed=[r for r in rows if r["route"] == "embed"],
                table=[r for r in rows if r["route"] == "table"],
                asset=[r for r in rows if r["route"] == "asset"])


# ------------------------------------------------------------------ search
# Retrieval lives in ops.ingest.search, which is not part of the app.
# source_code_path is app/, so the deployed container holds app/ and nothing
# above it. The import that works from a clone raises ModuleNotFoundError in
# the workspace, and an unhandled one is a 500 on a search box, which is how
# a working page reports a deployment fact as a crash.
#
# Resolve the package once, from whichever root actually holds it, and when
# none does say that in the response. The front end already renders .error,
# so "retrieval is not deployed here" reaches the person. A 500 leaves them
# on "searching..." for ever.
_KB = None
_KB_ERROR: str | None = None


def _kb_dir() -> pathlib.Path:
    """Where to read the index from.

    AIRCARRIER_KB_DIR points at the volume the ingest job writes. Prefer it,
    but only once it holds an index: pointing at a volume that exists and is
    empty used to report "no index built", which reads as "the job has not
    run" and is indistinguishable from "the path is wrong". Falling back to
    the copy that ships beside the app means a smaller index rather than no
    search, at every access level including zero.
    """
    shipped = HERE / "data" / "kb"
    env = os.environ.get("AIRCARRIER_KB_DIR")
    if env:
        p = pathlib.Path(env)
        try:
            if (p / "chunks.json").exists():
                return p
        except OSError:
            pass
    return shipped


def _kb():
    global _KB, _KB_ERROR
    if _KB is not None or _KB_ERROR is not None:
        return _KB
    import sys as _sys
    for root in (HERE.parent, HERE / "_ops"):
        if (root / "ops" / "ingest" / "search.py").is_file():
            if str(root) not in _sys.path:
                _sys.path.insert(0, str(root))
            break
    else:
        _KB_ERROR = ("Retrieval is not available in this deployment: the app "
                     "ships app/ only, and ops.ingest.search is above it. The "
                     "corpus catalogue and the page citations are unaffected.")
        return None
    from ops.ingest.search import KnowledgeBase
    _KB = KnowledgeBase(_kb_dir())
    return _KB


@app.get("/api/search")
def api_search(q: str, k: int = 8, authoritative: bool = True):
    """Retrieval over the knowledge base, as JSON. Every hit cites its page."""
    kbs = _kb()
    if kbs is None:
        return {"query": q, "count": 0, "hits": [], "error": _KB_ERROR}
    if not kbs.available:
        return {"query": q, "count": 0, "hits": [],
                "error": f"No index at {kbs.dir}.",
                "fix": "Run the aircarrier ingest job, or "
                       "python3 ops/entrypoints/ingest_job.py locally."}
    hits = kbs.search(q, k=min(k, 20),
                      grade="AUTHORITATIVE" if authoritative else None)
    return {"query": q, "count": len(hits),
            "hits": [{kk: v for kk, v in h.items() if kk != "text"} |
                     {"text": h["text"][:900]} for h in hits]}


@app.get("/program", response_class=HTMLResponse)
def program_page(request: Request):
    """How the build itself is going. Counted from the repository rather than
    typed, because a hand-maintained status page is wrong by the second week
    and this one is pointed at a sponsor. Delivery dashboard and Build
    progress were two pages about this; merged 2026-11-09."""
    dv = data.get("delivery")
    comps = dv.get("components", [])
    return page(request, "program.html", "Program", dv=dv,
                counts=dv.get("counts", {}),
                built=[c for c in comps if c["status"] == "done"],
                partial=[c for c in comps if c["status"] in ("partial", "by design")],
                todo=[c for c in comps if c["status"] == "not started"])


@app.get("/coverage", response_class=HTMLResponse)
def coverage(request: Request):
    return page(request, "coverage.html", "Coverage map",
                layers=data.get("layers"), clue=data.get("clue_map"),
                gaps=data.get("gaps"))


@app.get("/sources", response_class=HTMLResponse)
def sources(request: Request):
    return page(request, "sources.html", "Sources", s=data.get("sources"))


@app.get("/insight", response_class=HTMLResponse)
def insight(request: Request):
    """The one page written for someone who is not on this team.

    Questions are ordered by how answerable they are by a person, not by how
    much money they carry. A reader who opens this and sees a $9bn question
    they cannot help with closes the tab; one who sees a question they can
    answer in two sentences answers it.
    """
    g = data.get("gaps")
    rows = [r for r in g.get("rows", []) if not r.get("closed")]

    # Who is most likely to be able to answer, from the gap type. The label
    # is for the reader, so it says what kind of knowledge is wanted rather
    # than repeating the internal type name.
    ASK = {
        "SME":      ("Someone who was there", "You remember how it worked. "
                     "No document needs to exist."),
        "DOCUMENT": ("Someone who knows where it is written",
                     "A report, instruction or exhibit that answers it."),
        "DATA":     ("Someone with the system open",
                     "A query against a system you already have."),
        "CATALOG":  ("Someone inside the environment",
                     "A list only visible from the inside."),
    }
    # Effort as the reader experiences it, which is not the same as the
    # internal closability: an SME question is free for the person who knows
    # the answer and impossible for everyone else.
    EFFORT = {"SME": 0, "DOCUMENT": 1, "CATALOG": 2, "DATA": 3}

    for r in rows:
        who, how = ASK.get(r.get("type"), ("Anyone who knows", ""))
        r["ask_who"] = who
        r["ask_how"] = how
        r["effort"] = EFFORT.get(r.get("type"), 4)
        r["two_minutes"] = r.get("type") in ("SME", "DOCUMENT")

    rows.sort(key=lambda r: (r["effort"], -float(r.get("priority") or 0)))
    # 2026-11-11: quick used to be cut at [:8], so the page said "59 open
    # questions" and listed 27; the other 32 answerable ones were nowhere.
    # Every open question is listed now; the page filters them in place.
    quick = [r for r in rows if r["two_minutes"]]
    rest = [r for r in rows if not r["two_minutes"]]
    assert len(quick) + len(rest) == len(rows)
    return page(request, "insight.html", "Contribute", g=g, rows=rows,
                quick=quick, rest=rest,
                types=sorted({r.get("type") or "OTHER" for r in rows}),
                max_mb=CAPTURE_MAX_MB, max_files=CAPTURE_MAX_FILES,
                store_on=bool(os.environ.get("AIRCARRIER_CAPTURE_VOLUME")))


@app.get("/api/ladder", tags=["recon"])
def api_ladder():
    """The reconciliation ladder: every rung from appropriation to EVM."""
    from api import ladder
    rungs = ladder.build()
    return {"rungs": rungs, "summary": ladder.summary(rungs),
            "layers": (data.get("layers") or {}).get("layers", [])}


@app.get("/api/gaps/{gap_id}/brief", tags=["capture"])
async def api_gap_brief(gap_id: str, fresh: bool = False):
    """A brief for one open question, built when it is opened, never in advance.

    Evidence (register row, variances, unattributed blocks, transactions) is
    read by code; the four-field summary is the agent model's reading of it,
    or a code-built summary when no model answers. Always a lead."""
    from api import brief as _brief
    import anyio
    out = await anyio.to_thread.run_sync(lambda: _brief.brief(gap_id, fresh=fresh))
    if out is None:
        return JSONResponse({"error": f"no gap {gap_id}"}, status_code=404)
    return out


@app.get("/method", response_class=HTMLResponse)
def method(request: Request):
    return page(request, "method.html", "Method", layers=data.get("layers"))


@app.get("/rules", response_class=HTMLResponse)
def rules(request: Request):
    """Every code the product uses, each read from where it is defined
    (api/rulebook.py). The rule register is read live on every request."""
    _ident, q_app, _q_user = work.runners(request)
    return page(request, "rules.html", "Rule codes", **rulebook.page_context(q_app))


@app.get("/delivery", include_in_schema=False)
@app.get("/progress", include_in_schema=False)
def old_program_routes():
    """Old links, bookmarks and the brief notes keep working."""
    return RedirectResponse("/program", status_code=308)


# ----------------------------------------------------------------------- API
@app.get("/api/tables", tags=["data"])
def api_tables():
    """Every table the front center serves."""
    return {"backend": data.backend_info(), "tables": data.available()}


@app.get("/api/table/{name}", tags=["data"])
def api_table(name: str):
    """One table by name. Same shape the pages render from."""
    obj = data.get(name)
    if not obj:
        return JSONResponse({"error": f"no table '{name}'",
                             "available": data.available()}, status_code=404)
    return obj


CAPTURE_MAX_MB = 10
CAPTURE_MAX_FILES = 3
_CAPTURE_TYPES = {".pdf", ".docx", ".doc", ".xlsx", ".xls", ".csv", ".txt", ".pptx",
                  ".png", ".jpg", ".jpeg", ".msg", ".eml"}


def _store_capture(record: dict, files: list[tuple[str, bytes]]) -> tuple[bool, str, list[str]]:
    """Write the capture and its attachments to a UC volume, if one is configured.

    AIRCARRIER_CAPTURE_VOLUME is a /Volumes/... directory. The app service
    principal needs WRITE VOLUME on it. Unset means nothing is stored and
    the response says so."""
    import io
    import json as _json
    import re
    import uuid as _u
    from datetime import datetime, timezone
    root = os.environ.get("AIRCARRIER_CAPTURE_VOLUME", "").rstrip("/")
    if not root:
        return False, "No capture volume is configured (AIRCARRIER_CAPTURE_VOLUME).", []
    from databricks.sdk import WorkspaceClient
    w = WorkspaceClient()
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    cid = _u.uuid4().hex[:12]
    base = f"{root}/{day}/{cid}"
    paths = []
    try:
        for name, blob in files:
            safe = re.sub(r"[^A-Za-z0-9._-]+", "_", name)[:120] or "file"
            p = f"{base}/{safe}"
            w.files.upload(p, io.BytesIO(blob), overwrite=False)
            paths.append(p)
        record = record | {"capture_id": cid, "attachments": paths,
                           "captured_at": datetime.now(timezone.utc).isoformat()}
        w.files.upload(f"{base}/capture.json",
                       io.BytesIO(_json.dumps(record, indent=1).encode()), overwrite=False)
    except Exception as exc:  # noqa: BLE001 - say what failed
        return False, f"Could not write to {root}: {str(exc)[:200]}", paths
    return True, f"Stored as {cid}.", paths


@app.post("/api/capture", tags=["capture"])
async def api_capture(request: Request):
    """Insight capture.

    The app writes evidence and intent, never facts. An SME assertion is a
    high-reliability lead contributing a selector, and it enters through the
    same grading machinery as any other source. Append only: corrections are
    new rows that supersede. Writes are attributed to the authenticated user
    rather than to the app service principal, because in an attestation
    context an audit log showing that the app wrote the row is worth little.
    """
    import base64
    body = await request.json()
    user = (request.headers.get("X-Forwarded-Email")
            or request.headers.get("X-Forwarded-Preferred-Username") or "unauthenticated")
    # Attachments arrive as base64 in the JSON body: the app has no multipart
    # parser (python-multipart is not in the vendored IL5 requirements).
    files, refused = [], []
    for a in (body.get("attachments") or [])[:CAPTURE_MAX_FILES]:
        name = str(a.get("name") or "file")
        ext = pathlib.Path(name).suffix.lower()
        if ext not in _CAPTURE_TYPES:
            refused.append(f"{name}: type {ext or 'none'} is not accepted")
            continue
        try:
            blob = base64.b64decode(a.get("b64") or "", validate=True)
        except ValueError:
            refused.append(f"{name}: could not be read")
            continue
        if len(blob) > CAPTURE_MAX_MB * 1024 * 1024:
            refused.append(f"{name}: larger than {CAPTURE_MAX_MB} MB")
            continue
        files.append((name, blob))
    if not (body.get("body") or "").strip() and not files:
        return JSONResponse({"error": "Write an answer or attach a document."}, status_code=400)
    record = {"submitted_by": user, "zone": "L", "status": "candidate",
              "gap_id": body.get("gap_id"), "kind": body.get("kind"),
              "body": body.get("body"), "source": body.get("source"),
              "reliability": body.get("reliability"), "credibility": body.get("credibility"),
              "refer": body.get("refer"), "contact": body.get("contact"),
              "files": [{"name": n, "bytes": len(b)} for n, b in files]}
    import anyio
    stored, note, paths = await anyio.to_thread.run_sync(lambda: _store_capture(record, files))
    return {"accepted": True, "stored": stored, "note": note, "refused": refused,
            "attachments": paths, "record": record}


@app.get("/healthz", response_class=PlainTextResponse, include_in_schema=False)
def healthz():
    return "ok"
