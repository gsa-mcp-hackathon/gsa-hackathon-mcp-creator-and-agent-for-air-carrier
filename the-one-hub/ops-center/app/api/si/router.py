"""/api/v1/si: start a run from a page, watch it, review it, decide.

  GET  /si/tasks                     what a page may ask (?page=/mission)
  POST /si/runs                      start one; returns at once, the run works in the background
  GET  /si/runs                      recent runs (?page=, ?limit=)
  GET  /si/runs/{id}                 the run; ?after=N returns only events after seq N
  GET  /si/runs/{id}/stream          the same events as text/event-stream
  GET  /si/runs/{id}/authority       per proposal: may I apply it, and if not who can
  POST /si/runs/{id}/decide          apply or reject the ticked proposals
  GET  /si/picture                   the Kennedy picture (cached 60 s; ?fresh=1)
  GET  /si/obligations               a contract's obligations over a FY range, computed here
  GET  /si/activity                  every action by every person and agent, newest first
  GET  /si/rules                     the SI rule book

No endpoint accepts a figure from the browser except the reported figure a
person is testing, and that one only ever appears labelled as reported.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from decimal import Decimal
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from .. import data, harness, live
from .. import harness_sql as H
from . import picture as PIC
from . import sdk, store, tasks

router = APIRouter(prefix="/api/v1/si", tags=["si"])


def model_chains() -> tuple[list[str], list[str]]:
    """(specialist chain, checker chain): the 'reasoning' and 'checker' roles.
    The specialist answers in JSON with no tools; the checker chain holds a
    different family, and sdk drops any checker of the family that answered."""
    from .. import agent
    return agent.role_models("reasoning"), agent.role_models("checker")


def _ctx(request: Request) -> tuple[sdk.Ctx, object]:
    from .. import agent
    ident, q_app, q_user = harness.runners(request)
    spec, chk = model_chains()
    no_model = os.environ.get("AIRCARRIER_SI_MODELS", "on") == "off"
    ctx = sdk.Ctx(q_app=q_app if live.WAREHOUSE else None, data_get=data.get,
                  call_model=None if no_model else agent._call_model,
                  models=[] if no_model else spec, checker_models=[] if no_model else chk,
                  asked_by=ident.email, page=None, offices=dict(tasks.OFFICES))
    return ctx, q_user


def _hosts(request: Request) -> set[str]:
    """The names this app answers to. Behind the Databricks Apps proxy the Host
    header can be the container's own address while the browser's Origin is the
    public app URL, which the proxy passes as X-Forwarded-Host."""
    out = {request.headers.get("host", ""), request.url.netloc}
    for h in (request.headers.get("x-forwarded-host") or "").split(","):
        out.add(h.strip())
    app_url = os.environ.get("DATABRICKS_APP_URL")
    if app_url:
        out.add(urlparse(app_url if "//" in app_url else "//" + app_url).netloc)
    return {h.lower() for h in out if h}


def _same_origin(request: Request) -> bool:
    origin = request.headers.get("origin") or request.headers.get("referer")
    if not origin:
        return request.headers.get("sec-fetch-site") in (None, "same-origin")
    return urlparse(origin).netloc.lower() in _hosts(request)


def _refuse_origin(request: Request, what: str):
    origin = request.headers.get("origin") or request.headers.get("referer") or "none"
    seen = ", ".join(sorted(_hosts(request))) or "none"
    print(f"[si] refused {what}: origin {urlparse(origin).netloc or origin} not in {seen}",
          flush=True)
    raise HTTPException(403, f"{what} is started from this app's own pages. This request "
                             f"came from {urlparse(origin).netloc or origin}; the app "
                             f"answers to {seen}.")


def _app_query(sql: str, params: dict | None = None) -> list[dict]:
    return live.query(sql, params)[1]


def find_run(run_id: str) -> sdk.Run | None:
    """The run from this process, else loaded from the harness tables as the app
    principal (it holds SELECT on agent_runs, agent_steps, checker_verdicts and
    proposals). Without a warehouse only memory is searched."""
    return store.get_run(run_id, _app_query if live.WAREHOUSE else None, H.tables())


def _run_or_404(run_id: str) -> sdk.Run:
    try:
        run = find_run(run_id)
    except Exception as exc:  # noqa: BLE001 - the reader is told the load failed
        raise HTTPException(503, f"The run could not be loaded from the harness tables: "
                                 f"{str(exc)[:240]}") from None
    if run is None:
        raise HTTPException(404, "No run with that id is in this app process or in the "
                                 "harness tables.")
    return run


# ------------------------------------------------------------------- tasks
@router.get("/tasks")
def api_tasks(page: str | None = None):
    cards = tasks.for_page(page) if page else [t.card() for t in tasks.TASKS.values()]
    return {"page": page, "tasks": cards}


@router.get("/rules")
def api_rules():
    return {"rules": [{"rule_id": k, "text": v} for k, v in tasks.RULEBOOK.items()],
            "offices": tasks.OFFICES}


# -------------------------------------------------------------------- runs
class StartBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task_id: str = Field(min_length=1, max_length=64)
    subject: str = Field(min_length=1, max_length=64)
    page: str = Field(default="/mission", max_length=64)
    params: dict = Field(default_factory=dict)


_PARAMS = {"reconcile_obligations": {"reported_total", "reported_label"}}


@router.post("/runs", status_code=202)
def api_start(request: Request, body: StartBody):
    if not _same_origin(request):
        _refuse_origin(request, "A run")
    extra = set(body.params) - _PARAMS.get(body.task_id, set())
    if extra:
        raise HTTPException(422, f"{body.task_id} takes no parameter {sorted(extra)}.")
    rep = body.params.get("reported_total")
    if rep not in (None, "") and not re.fullmatch(r"-?\$?\d{1,3}(,\d{3})*(\.\d{1,2})?|-?\$?\d+(\.\d{1,2})?",
                                                   str(rep).strip()):
        raise HTTPException(422, "The reported figure must be dollars and cents, like "
                                 "4,519,300,323.83.")
    subject = tasks.normalize(body.task_id, body.subject)
    try:
        tpl = tasks.route(body.task_id, subject)
    except sdk.Refused as exc:
        store.STORE.log(actor=None, actor_kind="human", action="run_refused", run_id=None,
                        detail=str(exc))
        raise HTTPException(422, str(exc)) from None
    if body.page not in tpl.pages:
        raise HTTPException(422, f"{tpl.label.format(subject=subject)} is not started from "
                                 f"{body.page}. Pages: {', '.join(tpl.pages)}.")
    ctx, q_user = _ctx(request)
    ctx.page = body.page
    run = sdk.Run(tpl, subject, body.params, page=body.page, asked_by=ctx.asked_by)
    store.STORE.add(run)
    store.STORE.log(actor=ctx.asked_by, actor_kind="human", action="run_started",
                    run_id=run.run_id, detail=run.label)

    def on_done(r: sdk.Run) -> None:
        try:
            store.persist_run(r, q_user, H.tables())
        except Exception as exc:  # noqa: BLE001 - said on the run, never lost silently
            r.persisted = {"mode": store.mode(), "ok": False, "error": str(exc)[:300]}
        store.STORE.log(actor="si", actor_kind="agent", action=f"run_{r.status}",
                        run_id=r.run_id, detail=f"{r.label}: {len(r.reviewable())} proposals "
                                                f"ready")

    sdk.start(run, ctx, tasks.RULEBOOK, on_done=on_done, background=True)
    return {"run_id": run.run_id, "run": run.view()}


@router.get("/runs")
def api_runs(page: str | None = None, limit: int = 50):
    rs = store.STORE.list(limit=min(max(limit, 1), 200), page=page)
    return {"mode": store.mode(), "runs": [r.view(full=False) for r in rs]}


@router.get("/runs/{run_id}")
def api_run(run_id: str, after: int = 0, full: int = 0):
    run = _run_or_404(run_id)
    # While it works, a poll carries only the new events; the pack, proposals and
    # verdicts come once, when it is done.
    return run.view(after=after, full=bool(full) or run.status in (
        "ready", "blocked", "failed", "decided"))


@router.get("/runs/{run_id}/stream")
async def api_stream(run_id: str, after: int = 0):
    run = _run_or_404(run_id)

    async def gen():
        seen = after
        for _ in range(900):                       # at most ~6 minutes
            new = [e for e in run.events if e["seq"] > seen]
            for e in new:
                seen = e["seq"]
                yield f"id: {seen}\nevent: step\ndata: {json.dumps(e, default=str)}\n\n"
            if run.status not in ("queued", "running"):
                yield (f"event: done\ndata: "
                       f"{json.dumps(run.view(after=seen), default=str)}\n\n")
                return
            await asyncio.sleep(0.4)
        yield "event: timeout\ndata: {}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/runs/{run_id}/authority")
def api_run_authority(request: Request, run_id: str, action: str = "apply"):
    run = _run_or_404(run_id)
    _ident, _q_app, q_user = harness.runners(request)
    out, cache = {}, {}
    for p in run.proposals:
        if p.goes_to_role not in cache:
            try:
                cache[p.goes_to_role] = store.check_authority(
                    q_user, H.tables(), p.goes_to_role, p.goes_to_office, action)
            except Exception as exc:  # noqa: BLE001 - unknown is not allowed
                cache[p.goes_to_role] = {"allowed": False, "reason_code": "check_failed",
                                         "reason": f"The authority check failed: {exc}"[:300],
                                         "handoff": None}
        out[p.proposal_id] = cache[p.goes_to_role]
    return {"run_id": run_id, "action": action, "authority": out}


class DecideBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    proposal_ids: list[str] = Field(min_length=1, max_length=50)
    action: str = Field(pattern="^(apply|reject)$")
    notes: str | None = Field(default=None, max_length=2000)


@router.post("/runs/{run_id}/decide")
def api_decide(request: Request, run_id: str, body: DecideBody):
    if not _same_origin(request):
        _refuse_origin(request, "A decision")
    run = _run_or_404(run_id)
    if run.status in ("queued", "running"):
        raise HTTPException(409, "The run is still working. Decide when it is ready.")
    _ident, _q_app, q_user = harness.runners(request)
    try:
        receipt = store.decide(run, body.proposal_ids, body.action, body.notes, q_user,
                               H.tables())
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    _PICTURE.clear()
    return receipt


# ----------------------------------------------------------------- picture
_PICTURE: dict = {}


@router.get("/picture")
def api_picture(request: Request, fresh: int = 0):
    import time
    hit = _PICTURE.get("v")
    if hit and not fresh and time.time() - hit[0] < 60:
        return hit[1]
    _ident, q_app, _q_user = harness.runners(request)
    out = PIC.build(q_app if live.WAREHOUSE else _no_warehouse, data.get, store.STORE)
    _PICTURE["v"] = (time.time(), out)
    return out


def _no_warehouse(sql: str, params: dict | None = None) -> list[dict]:
    raise live.LiveError("no SQL warehouse is bound to this app")


@router.get("/obligations")
def api_obligations(request: Request, contract: str, fy_from: str | None = None,
                    fy_to: str | None = None):
    """The brush on the obligations chart asks here; the browser never adds."""
    key = tasks.piid(contract)
    if key not in tasks.CONTRACTS:
        raise HTTPException(422, f"{contract} is not a CVN-79 prime contract here.")
    ctx, _q_user = _ctx(request)
    rows, is_live = tasks._tx_rows(ctx, key, [])
    sel = [r for r in rows if (not fy_from or str(r["fy"]) >= fy_from)
           and (not fy_to or str(r["fy"]) <= fy_to)]
    total = sum((Decimal(str(r["amount"] or 0)) for r in sel), Decimal(0))
    disp = tasks.CONTRACTS[key]["display"]
    rng = f"FY{fy_from or 'first'} to FY{fy_to or 'last'}"
    return {"contract": disp, "fy_from": fy_from, "fy_to": fy_to, "live": is_live,
            "count": len(sel),
            "total": PIC._fig(f"{key}.range", f"Obligations, {disp}, {rng}", total, "USD",
                              f"sum of federal_action_obligation over {len(sel)} actions "
                              f"dated in {rng} (OB-01)", f"FPDS prime transactions {disp}",
                              as_of=sdk.now_iso()),
            "top": [{"mod": r.get("mod"), "action_date": r.get("action_date"),
                     "amount": r.get("amount"), "display": sdk.money(r.get("amount") or 0),
                     "description": r.get("description")}
                    for r in sorted(sel, key=lambda r: -abs(Decimal(str(r["amount"] or 0))))[:8]]}


@router.get("/activity")
def api_activity(limit: int = 200):
    return {"mode": store.mode(), "activity": list(store.STORE.activity)[:min(limit, 2000)]}
