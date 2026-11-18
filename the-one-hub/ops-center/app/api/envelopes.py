"""The shapes every work-queue response is made of. Pure functions, no IO.

The UI renders these and nothing else:

  figure()    a value with its as-of time, staleness and provenance
  verdict()   the checker's result on an agent output, including "not checked"
  citation()  rule id, rule version and record ids of an agent output
  actor()     who made a step or decision: agent, human or system
  authority() whether the caller may act, and the sentence saying why not

Two rules hold throughout:

  * No arithmetic on values. display_money() inserts thousands separators
    into the decimal string the warehouse returned. It does not round, scale
    or convert. A value with no source is state "unknown" with a reason and
    no value at all, never a zero.
  * Provenance names its layer (L0 Reported .. L5 Evidence) only when the
    source records one. The rule register has no layer column yet, so
    exception amounts say so rather than guessing (docs/API_SPEC.md A-20).
"""
from __future__ import annotations

import hashlib
import json
import os
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

# How long a detected figure counts as current. The rule evaluation job runs
# daily, so a figure older than a day plus slack has missed at least one run.
WINDOW_HOURS = int(os.environ.get("AIRCARRIER_FIGURE_WINDOW_HOURS", "26"))

# ------------------------------------------------------------------ provenance
# A-13: every Figure gets a stable provenance_id derived from its identifying
# data. The server keeps a bounded LRU cache mapping id -> full provenance so
# the /api/v1/provenance/{id} endpoint can look it up without a database round
# trip. The cache is process-local and short-lived (last ~500 figures).

_PROVENANCE_CACHE_MAX = 500
_provenance_cache: OrderedDict[str, dict] = OrderedDict()


def _provenance_id(figure_id: str, source: str, rule_id: str | None,
                   rule_version: int | None, as_of: str | None,
                   record_ids: list[str]) -> str:
    """Deterministic 16-hex-char id from the figure's provenance key."""
    key = json.dumps([
        figure_id, source, rule_id, rule_version, as_of,
        sorted(record_ids),
    ], separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def _cache_provenance(pid: str, prov: dict) -> None:
    _provenance_cache[pid] = prov
    _provenance_cache.move_to_end(pid)
    while len(_provenance_cache) > _PROVENANCE_CACHE_MAX:
        _provenance_cache.popitem(last=False)


def get_provenance(provenance_id: str) -> dict | None:
    """Look up a cached provenance block by its id. Returns None if evicted."""
    return _provenance_cache.get(provenance_id)


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        ts = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    # A date or a naive timestamp is read as UTC, so it compares with now.
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


def display_money(value: str) -> str:
    """'6000000.00' -> '$6,000,000.00'. Separators only; every digit is kept."""
    d = Decimal(value)
    sign = "-" if d < 0 else ""
    return f"{sign}${abs(d):,f}"


def figure(*, figure_id: str, label: str, value: str | None, unit: str,
           as_of: str | None, record_ids: list[str], rule_id: str | None = None,
           rule_version: int | None = None, computation: str, source: str,
           unknown_reason: str = "", layer: str | None = None,
           now: datetime | None = None) -> dict:
    """A Figure envelope. value is the decimal string from the warehouse or None."""
    now = now or datetime.now(timezone.utc)
    known = value is not None
    display = None
    if known:
        try:
            display = display_money(value) if unit == "USD" else f"{Decimal(value):,f}"
        except InvalidOperation:
            known, display = False, None
            unknown_reason = f"The source returned a value that is not a number: {value!r}"
    as_of_ts = _parse_ts(as_of)
    stale_after = (as_of_ts + timedelta(hours=WINDOW_HOURS)) if as_of_ts else None
    rids = list(record_ids or [])
    pid = _provenance_id(figure_id, source, rule_id, rule_version, as_of, rids)
    prov = {
        "provenance_id": pid,
        "record_ids": rids,
        "record_count": len(rids),
        "records_href": f"/api/v1/provenance/{pid}/records",
        "rule": ({"rule_id": rule_id, "rule_version": rule_version} if rule_id else None),
        "computation": computation,
        "source": source,
        "layer": layer,
        "layer_note": None if layer else "The rule register does not record an evidence layer for this rule.",
    }
    _cache_provenance(pid, prov)
    return {
        "figure_id": figure_id,
        "label": label,
        "state": "known" if known else "unknown",
        "state_reason": None if known else (unknown_reason or "No value was recorded."),
        "value": value if known else None,
        "unit": unit,
        "display": display,
        "as_of": as_of,
        "stale_after": stale_after.strftime("%Y-%m-%dT%H:%M:%SZ") if stale_after else None,
        "stale": bool(stale_after and now > stale_after),
        "provenance": prov,
    }


# ------------------------------------------------------------------ payload typing
# A-17: proposal payloads are free-form JSON. Fields that carry money must go
# through Figure; everything else is plain text. The typing is convention-based:
# field name patterns + decimal parse + grounding cross-reference.

_DOLLAR_KEYWORDS = frozenset([
    "amount", "value", "cost", "price", "total", "balance", "obligation",
    "charge", "cap", "eac", "budget", "funded", "unfunded", "variance",
    "headroom", "threshold", "increment", "decrement", "adjustment",
])


def _looks_like_money(field_name: str, value) -> bool:
    """True when a payload field should be typed as USD.

    Match on the field name (any dollar keyword anywhere in the underscore-split
    tokens) AND the value parses as a decimal. Both must hold: "dollar_amount"
    with value "cleared" is not money, and "status" with value "100.00" is not
    money either.
    """
    if not isinstance(value, (str, int, float)):
        return False
    tokens = set(field_name.lower().replace("-", "_").split("_"))
    if not tokens & _DOLLAR_KEYWORDS:
        return False
    try:
        Decimal(str(value))
        return True
    except InvalidOperation:
        return False


def payload_field(field_name: str, value, *, grounding: list[dict] | None = None,
                  proposal_id: str = "", rule_id: str | None = None,
                  rule_version: int | None = None) -> dict:
    """Wrap one key-value from proposed_payload as either a Figure or plain text.

    Returns {"typed": "figure", "field": name, "figure": Figure} for dollar
    fields, or {"typed": "text", "field": name, "value": str} for everything
    else. The template dispatches on .typed.
    """
    grounding = grounding or []
    field_grounds = [g for g in grounding if g.get("field") == field_name]
    if _looks_like_money(field_name, value):
        doc_refs = "; ".join(
            f"{g.get('document_id', '?')} p.{g.get('page', '?')}"
            for g in field_grounds) or "no grounding"
        return {
            "typed": "figure",
            "field": field_name,
            "figure": figure(
                figure_id=f"proposal.{proposal_id}.{field_name}",
                label=field_name.replace("_", " ").title(),
                value=str(value),
                unit="USD",
                as_of=None,
                record_ids=[],
                rule_id=rule_id,
                rule_version=rule_version,
                computation=f"Proposed by the agent for field '{field_name}'. "
                            f"Grounding: {doc_refs}.",
                source="proposed_payload",
                unknown_reason="The proposed value is not a number.",
            ),
        }
    return {"typed": "text", "field": field_name, "value": str(value)}


def typed_payload(payload: dict, *, grounding: list[dict] | None = None,
                  proposal_id: str = "", rule_id: str | None = None,
                  rule_version: int | None = None) -> list[dict]:
    """Type every field in a proposed_payload. Returns an ordered list."""
    return [payload_field(k, v, grounding=grounding, proposal_id=proposal_id,
                          rule_id=rule_id, rule_version=rule_version)
            for k, v in payload.items()]


VERDICT_STATES = ("pass", "pass_with_exception", "fail", "error", "not_checked")


def verdict(row: dict | None, *, not_checked_reason: str) -> dict:
    """A Verdict envelope from a checker_verdicts row, or the explicit not-checked state.

    The table stores a checker that could not run as 'fail' and keeps 'error'
    in the proposal_review check (F6). That check is read back here, so a
    checker outage is shown as an error rather than as a judgment.
    """
    if not row or not row.get("verdict"):
        return {"state": "not_checked", "reason": not_checked_reason, "checks": [],
                "notes": None, "checker_agent": None, "model_endpoint": None, "decided_at": None}
    checks = json.loads(row.get("checks_json") or "[]")
    state = row["verdict"]
    if any(c.get("check_name") == "proposal_review" and c.get("actual") == "error" for c in checks):
        state = "error"
    return {"state": state, "reason": None,
            "checks": [c for c in checks if c.get("check_name") != "proposal"],
            "notes": row.get("verdict_notes"), "checker_agent": row.get("checker_agent"),
            "model_endpoint": row.get("checker_model"), "decided_at": row.get("verdict_at")}


def citation(*, rule_id: str | None, rule_version: int | None, record_ids, run_id: str | None = None,
             step_seq: int | None = None) -> dict:
    """A Citation. complete is False when any part is missing, and the UI says so."""
    ids = list(record_ids or [])
    return {"rule_id": rule_id, "rule_version": rule_version, "record_ids": ids,
            "run_id": run_id, "step_seq": step_seq,
            "complete": bool(rule_id and rule_version is not None and ids)}


def actor(kind: str, ident: str | None, *, role: str | None = None,
          detail: str | None = None, authority_basis: str | None = None) -> dict:
    """kind is agent, human or system. role is the role a human acted under.
    authority_basis is agent_own, human_applied, human_rejected, rule, or none."""
    assert kind in ("agent", "human", "system")
    return {"kind": kind, "id": ident or "unknown", "role": role, "detail": detail,
            "authority_basis": authority_basis}


def authority(action: str, row: dict | None, *, missing_reason: str | None = None) -> dict:
    """An Authority from an authority_check row, or a refusal when it could not run."""
    if row is None:
        return {"action": action, "allowed": False, "reason_code": "not_evaluated",
                "reason": missing_reason or "Authority could not be evaluated.",
                "evaluated_for": None, "role_used": None}
    return {"action": action, "allowed": row["reason_code"] == "allowed",
            "reason_code": row["reason_code"], "reason": row["reason"],
            "evaluated_for": row.get("evaluated_for"), "role_used": row.get("role_used")}


def step_output(output_json: str | None):
    """Decode agent_steps.output_json. Rows before 2026-11-11 hold a JSON
    string wrapping JSON; both forms decode to the same object."""
    if output_json is None:
        return None
    try:
        out = json.loads(output_json)
        if isinstance(out, str):
            out = json.loads(out)
        return out
    except ValueError:
        return {"unparsed": output_json}
