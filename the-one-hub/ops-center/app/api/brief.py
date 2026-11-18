"""On-demand question brief for the Contribute page.

When a reader opens one open question, the page asks for its brief. Nothing
is pre-generated: the brief is built only for the question that was opened,
so a reader who opens one question costs one model call, not fifty-nine.

Two layers, kept apart on purpose:

  evidence  read by code from the same extracts the pages render: the gap
            row, the variance entries that cite it, the unattributed blocks
            it blocks, and the prime-contract transactions it names. Every
            figure here is a sum code computed, never model text.
  summary   a plain-language reading of that evidence by the 'agent' model
            chain (api.agent.role_models), returned as four short fields.
            The model sees only the evidence pack and is told to add no
            figures. If no model answers, the summary is assembled from the
            evidence and the response says so.

The summary is a lead for a reader, never a reported figure.
"""
from __future__ import annotations

import json
import re
import time
from collections import OrderedDict
from decimal import Decimal, InvalidOperation

from api import data, explore

# Only these two prime contracts are in the transaction extract.
_PIID = re.compile(r"N0*0024-?(\d{2})-?C-?(\d{4})", re.I)
_KEYWORDS = {
    "N0002409C2116": ("preparation contract", "construction preparation", "09-c-2116"),
    "N0002415C2114": ("dd&c", "detail design", "15-c-2114"),
}
_CACHE: "OrderedDict[str, dict]" = OrderedDict()
_CACHE_MAX = 128

SYSTEM = """You write a short brief about one open question in the CVN-79 (USS John F.
Kennedy) cost reconciliation, for a Navy financial manager who may be able to
answer it. Work only from the evidence pack in the user message.

Return one JSON object and nothing else:
{"what_it_is": str, "what_we_have": [str], "what_is_needed": [str],
 "how_you_can_help": str}

Rules, all binding:
1. what_it_is: two sentences at most, plain words, no internal jargon.
2. what_we_have: up to four bullets of what the evidence pack already holds.
3. what_is_needed: up to three bullets naming the specific fact, document or
   record that would close the question.
4. how_you_can_help: one sentence telling the reader what a useful answer looks
   like (for example "name the instruction and chapter" or "say which office
   records it").
5. Add no dollar figure, date or identifier that is not in the evidence pack.
   Never total figures yourself.
6. If the pack is thin, say so rather than guessing."""


def _gap(gap_id: str) -> dict | None:
    key = (gap_id or "").strip().upper()
    for r in (data.get("gaps") or {}).get("rows", []):
        if str(r.get("id", "")).upper() == key:
            return r
    return None


def _mentions(text: str, gid: str) -> bool:
    return bool(re.search(rf"\b{re.escape(gid)}\b", text or ""))


def _contracts(text: str) -> list[str]:
    low = (text or "").lower()
    found = {f"N00024{a}C{b}" for a, b in _PIID.findall(text or "")}
    for piid, words in _KEYWORDS.items():
        if any(w in low for w in words):
            found.add(piid)
    return sorted(p for p in found if p in _KEYWORDS)


def _transactions(piid: str) -> dict:
    r = explore.query("transactions", filters={"award_id_piid": piid},
                      sort="federal_action_obligation", desc=True, size=5)
    top = [{k: x.get(k) for k in ("modification_number", "action_date", "action_type",
                                   "federal_action_obligation", "transaction_description")}
           for x in r["rows"]]
    try:
        s = Decimal(r["sum"] or 0)
        display = f"${s:,.2f}"
    except (InvalidOperation, TypeError):
        display = str(r["sum"])
    return {"piid": piid, "actions": r["total"], "obligation_sum": r["sum"],
            "obligation_display": display, "largest": top,
            "href": f"/explore?ds=transactions&award_id_piid={piid}",
            "as_of": r.get("as_of")}


def gather(gap_id: str) -> dict | None:
    """Everything code can say about one gap. No model involved."""
    g = _gap(gap_id)
    if g is None:
        return None
    gid = g["id"]
    variances = [{"id": v.get("id"), "title": v.get("title"), "status": v.get("status")}
                 for v in (data.get("variances") or {}).get("rows", [])
                 if _mentions(json.dumps(v, default=str), gid)]
    attr = data.get("attribution") or {}
    blocks = [{"label": r.get("label"), "usd_m": r.get("usd_m")}
              for r in attr.get("residual_contents", []) if r.get("gap") == gid]
    text = " ".join(str(g.get(k) or "") for k in ("title", "note"))
    tx = [_transactions(p) for p in _contracts(text)]
    exposure = g.get("exposure_usd_m")
    return {
        "gap": {k: g.get(k) for k in ("id", "title", "status", "type", "executor",
                                      "closability", "exposure_usd_m", "note", "decay")},
        "exposure_display": (f"${exposure:,.0f}M" if exposure else "not sized"),
        "variances": variances,
        "unattributed_blocks": blocks,
        "transactions": tx,
        "links": {"register": f"/gaps#{gid}", "ask": f"/ask?q=What+is+known+about+{gid}"},
    }


def _fallback(ev: dict, reason: str) -> dict:
    g = ev["gap"]
    have = []
    if g.get("note"):
        have.append(g["note"][:240])
    for v in ev["variances"]:
        have.append(f"Variance {v['id']}: {v['title']}")
    for t in ev["transactions"]:
        have.append(f"{t['actions']} prime-contract actions on {t['piid']}, "
                    f"{t['obligation_display']} obligated")
    for b in ev["unattributed_blocks"]:
        have.append(f"Unattributed block: {b['label']}")
    return {"what_it_is": g["title"],
            "what_we_have": have[:4] or ["Only the question itself is recorded so far."],
            "what_is_needed": [f"An answer from {g.get('executor') or 'whoever holds the record'}."],
            "how_you_can_help": "Say what you know and how you know it; a pointer to where it is "
                                "written is as useful as the answer.",
            "generated_by": "code", "reason": reason}


def _parse(text: str) -> dict | None:
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
    except ValueError:
        return None
    keys = ("what_it_is", "what_we_have", "what_is_needed", "how_you_can_help")
    if not all(k in obj for k in keys):
        return None
    out = {"what_it_is": str(obj["what_it_is"])[:600],
           "what_we_have": [str(x)[:300] for x in obj["what_we_have"]][:4],
           "what_is_needed": [str(x)[:300] for x in obj["what_is_needed"]][:3],
           "how_you_can_help": str(obj["how_you_can_help"])[:400]}
    return out


def brief(gap_id: str, call=None, fresh: bool = False) -> dict | None:
    """Evidence plus summary for one gap, cached per gap for the process."""
    from api import agent
    key = (gap_id or "").strip().upper()
    if not fresh and key in _CACHE:
        _CACHE.move_to_end(key)
        return _CACHE[key] | {"cached": True}
    ev = gather(key)
    if ev is None:
        return None
    call = call or agent._call_model
    t0, errors = time.time(), []
    pack = json.dumps(ev, default=str, ensure_ascii=False)[:9000]
    summary, model = None, None
    for m in agent.role_models("agent"):
        try:
            r = call(m, {"messages": [{"role": "system", "content": SYSTEM},
                                      {"role": "user", "content": "Evidence pack:\n" + pack}],
                         "max_tokens": 700})
            summary = _parse(agent._text(r["choices"][0]["message"].get("content")))
            if summary:
                model = m
                summary["generated_by"] = "model"
                break
            errors.append(f"{m}: reply was not the requested JSON")
        except Exception as exc:  # noqa: BLE001 - next model, reason kept
            errors.append(f"{m}: {str(exc)[:160]}")
    if summary is None:
        summary = _fallback(ev, "No model answered, so this summary is assembled from the "
                                "register by code. " + " | ".join(errors)[:400])
    out = {"gap_id": key, "evidence": ev, "summary": summary, "model": model,
           "grade": "lead", "seconds": round(time.time() - t0, 1), "cached": False}
    # Only a model brief is cached. A code fallback is cheap to rebuild, and
    # caching it would keep serving it after the model is reachable again.
    if model:
        _CACHE[key] = out
    while len(_CACHE) > _CACHE_MAX:
        _CACHE.popitem(last=False)
    return out


__all__ = ["brief", "gather"]
