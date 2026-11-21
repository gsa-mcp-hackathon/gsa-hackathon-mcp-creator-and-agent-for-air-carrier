"""Grader v2 for the delegation eval: reads what an answer states, not how it is spelled.

Rounds 1-3 passed an answer when every regex matched. Three of round 3's grading
defects came from that (eval/delegation/README.md, "Grading defects"): a key built
on a rounded figure (G07), a pattern that could not match 63.11% (H06), and a
decoy pattern that did not accept "cannot find" (H10). This grader parses numbers
with their units, dates in the usual formats, and refusals, then compares values.

expect fields; every field present must pass:
  numbers     [{kind, value, printed_thousands?}]  kind: count | usd | musd | pct | num
  texts       [regex, ...]          each must match, case-insensitive
  dates       ["YYYY-MM-DD", ...]   each must be stated
  refusal     true                  the answer says the thing does not exist or cannot be found
  reason_any  [regex, ...]          with refusal: any one must match (premise traps)

A number matches when the figure as written rounds to the key: the difference is at
most half a unit in the last stated digit, and the figure keeps at least
min(MIN_SIG, significant digits of the key) significant digits, so "$13.2 billion"
does not pass for 13,195.970 $M but "13,196" does. Money is compared in absolute
value: "a deobligation of $28,247,000" matches -28247000.00.

Pure Python, no dependencies: eval/delegation/round4/test_grade.py runs offline.
"""
from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

MIN_SIG = 4
_UNIT = {"billion": 9, "bn": 9, "b": 9, "million": 6, "mn": 6, "mil": 6, "m": 6, "thousand": 3, "k": 3}
# A figure, optionally signed or in parentheses, then an optional unit or percent.
# The look-behind keeps digits inside identifiers (P00038, FY2021, 2018-05-02) out.
_NUM = re.compile(
    r"(?<![\w.\-/])(?P<sign>[-\u2212\u2013])?\(?\$?\s?(?P<int>\d{1,3}(?:,\d{3})+|\d+)(?:\.(?P<dec>\d+))?\)?"
    r"(?:\s*\$?\s*(?P<unit>billion|bn|million|mn|mil|thousand|[bmk](?![a-z])))?(?P<pct>\s*(?:%|percent))?",
    re.I)
_MONTHS = {m: i for i, ms in enumerate([
    ("jan", "january"), ("feb", "february"), ("mar", "march"), ("apr", "april"), ("may",), ("jun", "june"),
    ("jul", "july"), ("aug", "august"), ("sep", "sept", "september"), ("oct", "october"), ("nov", "november"),
    ("dec", "december")], 1) for m in ms}
_MON = r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sept?(?:ember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
_DATES = [
    (re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b"), lambda g: (int(g[0]), int(g[1]), int(g[2]))),
    (re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b"), lambda g: (int(g[2]), int(g[0]), int(g[1]))),
    (re.compile(_MON + r"\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b", re.I),
     lambda g: (int(g[2]), _MONTHS[g[0].lower()], int(g[1]))),
    (re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+" + _MON + r"\.?,?\s+(\d{4})\b", re.I),
     lambda g: (int(g[2]), _MONTHS[g[1].lower()], int(g[0]))),
]
REFUSAL = re.compile(
    r"(cannot|can't|could not|couldn't|was unable to|unable to|did not|didn't) (find|locate|identify|see)"
    r"|\bno (such|record|records|action|actions|modification|transaction|transactions|data|entry|entries|evidence|matching)\b"
    r"|not (found|present|listed|recorded|in the (data|records|dataset|available))"
    r"|does(n't| not) (exist|appear)|there (is|are) no\b|isn't (any|in)\b|is not (in|present|listed)\b",
    re.I)


def _sig(digits: str, has_dec: bool) -> int:
    s = digits.lstrip("0")
    return len(s if has_dec else s.rstrip("0")) or 1


def numbers_in(answer: str) -> list[dict]:
    """Every figure in the answer: value as written, decimals, unit power, percent, significant digits."""
    out = []
    for m in _NUM.finditer(answer or ""):
        i, d = m.group("int").replace(",", ""), m.group("dec") or ""
        out.append({"v": Decimal(f"{i}.{d}" if d else i), "k": len(d), "pow": _UNIT.get((m.group("unit") or "").lower(), 0),
                    "has_unit": bool(m.group("unit")), "pct": bool(m.group("pct")), "sig": _sig(i + d, bool(d)),
                    "text": m.group(0).strip()})
    return out


def dates_in(answer: str) -> set[date]:
    out = set()
    for rx, parts in _DATES:
        for m in rx.finditer(answer or ""):
            try:
                out.add(date(*parts(m.groups())))
            except (ValueError, KeyError):
                pass
    return out


def _close(stated: Decimal, scale: Decimal, k: int, key: Decimal) -> bool:
    """stated * scale rounds to key at the stated precision."""
    return abs(stated * scale - key) <= Decimal("0.5") * Decimal(10) ** -k * scale


def number_matches(n: dict, kind: str, key: str, printed_thousands: bool = False) -> bool:
    kv = Decimal(key)
    ks = str(abs(kv)).replace(".", "")
    need = min(MIN_SIG, _sig(ks, "." in str(abs(kv)) and not str(abs(kv)).endswith(".00")))
    if kind == "count":
        return not (n["pct"] or n["has_unit"]) and n["k"] == 0 and n["v"] == kv
    if kind == "pct":
        return n["pct"] and _close(n["v"], Decimal(1), n["k"], kv)
    if kind == "num":
        return not (n["pct"] or n["has_unit"]) and _close(n["v"], Decimal(1), n["k"], kv)
    if n["pct"] or n["sig"] < need:
        return False
    key_abs = abs(kv)
    if kind == "usd":
        return _close(n["v"], Decimal(10) ** n["pow"], n["k"], key_abs)
    if kind == "musd":
        if n["has_unit"]:
            return _close(n["v"], Decimal(10) ** (n["pow"] - 6), n["k"], key_abs)
        scales = [Decimal(1)]                      # printed in $M, the exhibit convention
        if printed_thousands:
            scales.append(Decimal("0.001"))        # older books print $K
        if n["v"] >= 10 ** 6:
            scales.append(Decimal(10) ** -6)       # spelled out in dollars
        return any(_close(n["v"], s, n["k"], key_abs) for s in scales)
    raise ValueError(f"unknown number kind {kind!r}")


def grade(answer: str | None, expect: dict) -> dict:
    """{passed, checks: [{check, ok}]}. A missing answer fails."""
    if not answer:
        return {"passed": False, "checks": [{"check": "answer present", "ok": False}]}
    checks = []
    nums = numbers_in(answer)
    for e in expect.get("numbers", []):
        ok = any(number_matches(n, e["kind"], e["value"], e.get("printed_thousands", False)) for n in nums)
        checks.append({"check": f"{e['kind']} {e['value']}", "ok": ok})
    for p in expect.get("texts", []):
        checks.append({"check": f"text /{p}/", "ok": bool(re.search(p, answer, re.I))})
    stated = dates_in(answer)
    for d in expect.get("dates", []):
        checks.append({"check": f"date {d}", "ok": date.fromisoformat(d) in stated})
    if expect.get("refusal"):
        reasons = expect.get("reason_any")
        ok = any(re.search(p, answer, re.I) for p in reasons) if reasons else bool(REFUSAL.search(answer))
        checks.append({"check": "premise rejected" if reasons else "says it does not exist", "ok": ok})
    if not checks:
        raise ValueError("expect has nothing to check")
    return {"passed": all(c["ok"] for c in checks), "checks": checks}


def grade_legacy(answer: str | None, patterns: list[str]) -> bool:
    """Rounds 1-3: every regex must match."""
    return all(re.search(p, answer or "", re.I) for p in patterns)
