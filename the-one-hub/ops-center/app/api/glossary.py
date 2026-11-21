"""One glossary for the codes a page shows as chips.

Register codes are defined by their own registers, so a chip never disagrees
with the row it points at: G14 reads gaps.json, E-17 reads variances.json, and
a rule code such as CAP-05 reads the rule register. Everything else (P-5c,
CIP, FBwT) comes from data/curated/glossary.json. An unknown code still
renders, with no definition, so a typo is visible rather than fatal.
"""
from __future__ import annotations

import functools
import json
import logging
import pathlib
import re

from api import data

log = logging.getLogger(__name__)
HERE = pathlib.Path(__file__).resolve().parent.parent
GAP = re.compile(r"^G\d+$")
VAR = re.compile(r"^E-\d+$")
RULE = re.compile(r"^[A-Z]{2,4}-\d{2}$")


@functools.lru_cache(maxsize=1)
def _terms() -> dict:
    return json.loads((HERE / "data" / "curated" / "glossary.json").read_text())["terms"]


def _rules() -> dict:
    out = {}

    def walk(o):
        if isinstance(o, dict):
            if isinstance(o.get("code"), str) and o.get("description"):
                out.setdefault(o["code"], o["description"])
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    try:
        walk(data.get("rules"))
    except Exception as exc:  # noqa: BLE001 - a chip without a definition is fine
        log.info("glossary: rule register not readable (%s); rule chips show no definition", exc)
    return out


def define(code: str) -> dict:
    """{"code", "text", "href", "kind"} for a chip. kind is register, rule or term."""
    code = (code or "").strip()
    try:
        if GAP.match(code):
            row = next((r for r in data.get("gaps").get("rows", []) if r.get("id") == code), {})
            state = "closed" if row.get("closed") else "open"
            text = f"Gap {code} ({state}): {row['title']}" if row else ""
            return {"code": code, "text": text, "href": f"/gaps#{code}", "kind": "register"}
        if VAR.match(code):
            row = next((r for r in data.get("variances").get("rows", [])
                        if r.get("id") == code), {})
            text = f"Variance {code} ({row.get('status')}): {row['title']}" if row else ""
            return {"code": code, "text": text, "href": f"/variances#{code}", "kind": "register"}
    except Exception:  # noqa: BLE001
        return {"code": code, "text": "", "href": "", "kind": "register"}
    if code in _terms():
        t = _terms()[code]
        return {"code": code, "text": t["text"], "href": t.get("href", ""), "kind": "term"}
    if RULE.match(code):
        text = _rules().get(code, "")
        return {"code": code, "text": f"Rule {code}: {text}" if text else "",
                "href": "/rules", "kind": "rule"}
    return {"code": code, "text": "", "href": "", "kind": "term"}
