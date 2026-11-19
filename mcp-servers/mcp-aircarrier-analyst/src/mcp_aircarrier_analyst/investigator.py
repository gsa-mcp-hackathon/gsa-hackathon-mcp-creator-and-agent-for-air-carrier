"""Case investigator: from one incomplete record to scored, cited cases.

The question it works: a record (a GL line, an obligation, an invoice, a
budget figure) is missing critical data elements. Does it belong to CVN-79
(John F. Kennedy), to another hull, to the Ford class as a whole, or to
something that is not a carrier at all? And what are the missing elements?

The method is an analyst's, made explicit so it can be audited:

  1. Profile   which critical data elements (CDEs) the record has and lacks,
               and why each one matters to the question.
  2. Plan      which skills can run on what is present, and which are waiting
               for a clue they need. Each skill names the sources it reads.
  3. Chase     run every runnable skill; each one can produce new clues (an
               amount finds an FPDS line, the line gives a PIID, the PIID
               gives the keyset verdict, the vendor and the accounts...).
               Repeat until no skill can run on a new clue or max_hops.
  4. Weigh     every piece of evidence moves a log-score per hypothesis by a
               stated weight (EVIDENCE_WEIGHTS). Softmax gives confidence.
  5. Decide    top three cases with for/against evidence, the data elements
               recovered with their provenance, a collection requirement for
               each CDE still missing, and a human-review flag with reasons
               whenever the answer is weak, close, contested or secondary.

Only sources that are loaded in Unity Catalog are read. Nothing is fetched
from the internet. Every output is grade LEAD (D16): a case is never a figure
and never enters the claim ledger. Weights are judgements (investigator/0.1);
confirmed outcomes (record_outcome, kind=case) are the labels to refit them.

This module is pure: all I/O goes through the Sources protocol, so the whole
loop runs in tests on fake sources.
"""
from __future__ import annotations

import logging
import math
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol

from core.analyst import loa

VERSION = "investigator/0.1"

HYPOTHESES: dict[str, str] = {
    "CVN-79": "CVN-79 John F. Kennedy",
    "CVN-78": "CVN-78 Gerald R. Ford",
    "CVN-80/81": "CVN-80 Enterprise / CVN-81 Doris Miller (two-ship buy)",
    "CLASS_SHARED": "Ford-class common cost, not allocated to one hull",
    "OTHER_CARRIER": "Another carrier (Nimitz class, CV-67 Kennedy, CVN-65 Enterprise)",
    "NOT_CARRIER": "Not a carrier (submarine, landing craft, other program)",
}
H = tuple(HYPOTHESES)
FORD = ("CVN-79", "CVN-78", "CVN-80/81", "CLASS_SHARED")

# Log-score per unit of evidence, by evidence kind. Judgements, stated so they
# can be audited and refit. A weight of +3 is roughly "20x more likely under
# this hypothesis than under the others".
EVIDENCE_WEIGHTS: dict[str, float] = {
    "keyset_prime": 4.0,          # exact PIID is a registered prime contract for the hull
    "keyset_excluded": 3.0,       # exact PIID is registered as NOT this hull
    "keyset_partial": 2.0,        # multi-hull contract with a stated CVN-79 share
    "text_hull": 3.0,             # the record's own text names a hull number
    "text_name": 1.5,             # a ship name only (names collide across hulls)
    "text_class": 1.5,            # "CVN 78 class" / "Ford class"
    "text_not_carrier": 2.5,      # submarine / landing craft / other platform vocabulary
    "stated_hull": 1.0,           # a hull field in the record: a claim to check, not proof
    "tas_on_cvn79_award": 1.2,    # the TAS funds a registered CVN-79 contract
    "program_code": 1.0,          # DoD acquisition program code seen on CVN-79 awards
    "budget_element": 1.5,        # BLI / program element linked to a hull in the graph
    "cooccurrence": 0.8,          # authoritative pages that mention the clue mostly mention one hull
    "exhibit_amount": 0.8,        # a budget exhibit cell equals the amount (rounded, coincidence-prone)
    "vendor": 0.5,                # vendor builds or equips carriers (but also other ships)
}
REVIEW_THRESHOLD = 0.70
REVIEW_MARGIN = 0.20

CDE: dict[str, tuple[str, str, str]] = {
    # key: (why it matters, where it is authoritative, who holds it)
    "piid": ("The contract number decides the hull through the keyset; it is the strongest single link.",
             "the obligating document number on the accounting line, or the contract in PIEE EDA",
             "DFAS Columbus or NAVSEA 01 (comptroller)"),
    "tas": ("The Treasury account (appropriation and years) says what kind of money and which budget year.",
            "the line of accounting on the posting, or Section G of the modification",
            "DFAS Columbus or NAVSEA 01 (comptroller)"),
    "amount": ("An exact amount can be matched to the cent against FPDS, File C and sub-awards.",
               "the accounting posting", "the record owner"),
    "date": ("The date fixes the fiscal period and narrows an amount match.", "the accounting posting",
             "the record owner"),
    "vendor": ("The vendor (CAGE or UEI) links to the prime or a sub-award.", "SAM.gov registration or the invoice",
               "the record owner"),
    "budget_line": ("A BLI or program element places the money in the budget, often per hull.",
                    "the P-5 / P-40 exhibits of the SCN book, or the funding document", "NAVSEA 05C, NCCA, CAPE"),
    "description": ("Free text often names the hull, the equipment or the platform.", "the posting or the modification",
                    "the record owner"),
}

_ALIASES: dict[str, tuple[str, ...]] = {
    "piid": ("piid", "contract", "contractnumber", "contractno", "awardid", "awardidpiid", "contractid"),
    "doc_number": ("documentnumber", "docnumber", "docnum", "obligationdocument", "sdn", "standarddocumentnumber"),
    "amount": ("amount", "obligation", "obligatedamount", "federalactionobligation", "transactionamount",
               "dollars", "value", "debit", "credit", "amt"),
    "date": ("date", "actiondate", "postingdate", "transactiondate", "accountingdate", "glpostingdate"),
    "tas": ("tas", "treasuryaccountsymbol", "treasuryaccount", "appropriation", "fund", "loa",
            "lineofaccounting", "accountingline", "fundcode"),
    "fiscal_year": ("fy", "fiscalyear", "bfy", "budgetfiscalyear"),
    "vendor_name": ("vendor", "vendorname", "recipient", "recipientname", "contractor", "payee", "subawardee"),
    "cage": ("cage", "cagecode"),
    "uei": ("uei", "recipientuei", "duns"),
    "description": ("description", "desc", "text", "memo", "narrative", "transactiondescription",
                    "linedescription", "comment", "title"),
    "object_class": ("objectclass", "oc", "boc", "objectclasscode"),
    "program_activity": ("programactivity", "pa", "programactivitycode"),
    "bli": ("bli", "budgetlineitem", "lineitem", "p1line"),
    "program_element": ("pe", "programelement", "programelementcode"),
    "program_code": ("dodacquisitionprogramcode", "programcode", "acquisitionprogram", "mdap"),
    "psc": ("psc", "productorservicecode"),
    "hull": ("hull", "ship", "platform", "shipname"),
}
_ALIAS_INDEX = {a: k for k, al in _ALIASES.items() for a in al}
_LONG_ALIASES = sorted((a for a in _ALIAS_INDEX if len(a) >= 4), key=len, reverse=True)


def _alias(name: str) -> str | None:
    """Exact alias; else the longest alias the name ends with ('contractamount' -> amount);
    else the longest alias it contains."""
    if name in _ALIAS_INDEX:
        return _ALIAS_INDEX[name]
    return next((_ALIAS_INDEX[a] for a in _LONG_ALIASES if name.endswith(a)),
                next((_ALIAS_INDEX[a] for a in _LONG_ALIASES if a in name), None))


# ------------------------------------------------------------------ knowledge

@dataclass
class Knowledge:
    """What the analyst knows before it looks at a record. Loaded from the KG and source tables."""
    contracts: dict[str, dict] = field(default_factory=dict)     # normalized PIID -> {label, props, rels:[(rel,dst,props)]}
    neg_terms: dict[str, str] = field(default_factory=dict)      # term -> why
    vendors: dict[str, dict] = field(default_factory=dict)       # CAGE -> {name, props}
    budget_links: dict[str, list[tuple[str, str]]] = field(default_factory=dict)  # bli:/program_element: id -> [(rel,dst)]
    cvn79_tas: dict[str, list[str]] = field(default_factory=dict)  # TAS -> [PIIDs whose award lists it]
    program_codes: dict[str, str] = field(default_factory=dict)  # code -> description, seen on CVN-79 awards
    psc_codes: set[str] = field(default_factory=set)
    artifacts: list[dict] = field(default_factory=list)          # catalog of documents
    hull_baseline: dict[str, int] = field(default_factory=dict)  # hull -> pages mentioning it, whole corpus


class Sources(Protocol):
    def fpds_by_amount(self, amount: str) -> list[dict]: ...
    def filec_by_amount(self, amount: str) -> list[dict]: ...
    def subawards(self, uei: str = "", name: str = "", amount: str = "") -> list[dict]: ...
    def exhibit_cells(self, values: list[str]) -> list[dict]: ...
    def search_pages(self, term: str, limit: int = 8) -> list[dict]: ...
    def hull_mentions(self, page_ids: list[str]) -> dict[str, int]: ...
    def node_hull_mentions(self, node_id: str) -> dict[str, int]: ...
    def mechanisms(self, terms: list[str], limit: int = 5) -> list[dict]: ...


# ------------------------------------------------------------------ helpers

def norm_piid(s: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (s or "").upper())


def dashed_piid(p: str) -> str:
    p = norm_piid(p)
    return f"{p[:6]}-{p[6:8]}-{p[8]}-{p[9:]}" if len(p) == 13 else p


PIID_RE = re.compile(r"\b([A-Z][A-Z0-9]{5})-?(\d{2})-?([A-Z])-?(\d{4})\b")
TAS_RE = re.compile(r"\b0?17-\d{4}/\d{4}-\d{4}-\d{3}\b|\b0?17-X-\d{4}-\d{3}\b")
PE_RE = re.compile(r"\b0\d{6}N\b")
BLI_RE = re.compile(r"\b(?:BLI|LINE ITEM|P-1 LINE)\s*#?\s*(\d{4})\b")
MAIN_RE = re.compile(r"\b(1611|1319|1804|1810|0400)N?\b")


def cents_of(x: Any) -> int | None:
    if x is None or str(x).strip() == "":
        return None
    s = re.sub(r"[,$\s]", "", str(x))
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()")
    try:
        c = int((Decimal(s) * 100).to_integral_value())
    except (InvalidOperation, ValueError):
        return None
    return -c if neg else c


def amount_str(c: int) -> str:
    sign = "-" if c < 0 else ""
    return f"{sign}{abs(c) // 100}.{abs(c) % 100:02d}"


def hull_to_h(hull: str) -> str:
    h = hull.upper().replace("HULL:", "")
    if h == "CVN-79":
        return "CVN-79"
    if h == "CVN-78":
        return "CVN-78"
    if h in ("CVN-80", "CVN-81"):
        return "CVN-80/81"
    if h == "CVN-21":
        return "CLASS_SHARED"
    return "OTHER_CARRIER"


# ------------------------------------------------------------------ state

@dataclass
class Clue:
    id: int
    key: str
    value: str
    origin: str            # "record" or the skill that found it
    citation: str
    parent: int | None = None
    strength: str = "stated"  # stated | exact | derived | ambiguous


@dataclass
class Evidence:
    skill: str
    kind: str
    statement: str
    weights: dict[str, float]
    grade: str              # AUTHORITATIVE | WORKING | DERIVED | STATED
    citation: str
    deterministic: bool = False
    clue: int | None = None
    sig: tuple = ()


# How much a clue's evidence counts, by how the clue was obtained.
STRENGTH = {"stated": 1.0, "exact": 1.0, "derived": 0.8, "ambiguous": 0.5}


@dataclass
class Case:
    record: dict
    k: Knowledge
    clues: list[Clue] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    trail: list[dict] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    caveats: list[dict] = field(default_factory=list)
    elements: dict[str, list[dict]] = field(default_factory=dict)
    done: set = field(default_factory=set)

    def add_clue(self, key: str, value: str, origin: str, citation: str, parent: int | None = None,
                 strength: str = "derived") -> Clue | None:
        value = str(value).strip()
        if not value:
            return None
        for c in self.clues:
            if c.key == key and c.value == value:
                # the same clue found again by a stronger route: keep the stronger route
                if STRENGTH.get(strength, 0) > STRENGTH.get(c.strength, 0) and (key, value) not in {
                        (k2, v2) for (_, k2, v2) in self.done}:
                    c.strength, c.origin, c.citation, c.parent = strength, origin, citation, parent
                return None
        c = Clue(len(self.clues) + 1, key, value, origin, citation, parent, strength)
        self.clues.append(c)
        return c

    def values(self, key: str) -> list[Clue]:
        return [c for c in self.clues if c.key == key]

    def element(self, key: str, value: str, source: str, confidence: float, basis: str) -> None:
        lst = self.elements.setdefault(key, [])
        if not any(e["value"] == value for e in lst):
            lst.append({"value": value, "source": source, "confidence": round(confidence, 4), "basis": basis})

    def ev(self, skill: str, kind: str, statement: str, per_h: dict[str, float], grade: str, citation: str,
           deterministic: bool = False, clue: int | None = None, scale: float = 1.0) -> None:
        # the same cue twice is one piece of evidence, not two
        sig = (skill, kind, tuple(sorted(per_h.items())))
        if sig in {(e.skill, e.kind, e.sig) for e in self.evidence}:
            return
        strength = next((c.strength for c in self.clues if c.id == clue), "stated")
        w = EVIDENCE_WEIGHTS[kind] * scale * STRENGTH.get(strength, 1.0)
        self.evidence.append(Evidence(skill, kind, statement, {h: round(v * w, 4) for h, v in per_h.items()},
                                      grade, citation, deterministic and strength in ("stated", "exact"), clue,
                                      tuple(sorted(per_h.items()))))


# ------------------------------------------------------------------ profile

def normalize(record: dict) -> tuple[dict, dict]:
    """Map free-form field names to analyst keys; keep everything else as context."""
    known, other = {}, {}
    for k, v in (record or {}).items():
        if v is None or str(v).strip() == "":
            continue
        key = _alias(re.sub(r"[^a-z0-9]", "", str(k).lower()))
        if key and key not in known:
            known[key] = str(v).strip()
        else:
            other[str(k)] = str(v).strip()
    return known, other


def profile(record: dict) -> dict:
    known, other = normalize(record)
    has = {
        "piid": "piid" in known or "doc_number" in known,
        "tas": "tas" in known,
        "amount": cents_of(known.get("amount")) is not None,
        "date": bool(re.match(r"^\d{4}-\d{2}-\d{2}", known.get("date", ""))),
        "vendor": any(k in known for k in ("vendor_name", "cage", "uei")),
        "budget_line": any(k in known for k in ("bli", "program_element")),
        "description": "description" in known or bool(other),
    }
    missing = [{"element": k, "why": CDE[k][0], "authoritative_in": CDE[k][1], "held_by": CDE[k][2]}
               for k, v in has.items() if not v]
    return {"recognized": known, "unrecognized_fields": other, "present": [k for k, v in has.items() if v],
            "missing_critical": missing}


# ------------------------------------------------------------------ skills

@dataclass(frozen=True)
class Skill:
    name: str
    needs: tuple[str, ...]       # any one of these clue keys lets it run
    reads: str                   # the sources it consults, in words
    fn: Callable


def _s_keyset(case: Case, clue: Clue, src: Sources) -> dict:
    p = norm_piid(clue.value)
    if len(p) != 13:
        return {"found": f"{clue.value!r} is not a 13-character PIID; not matched"}
    c = case.k.contracts.get(p)
    if c is None:
        twins = [dashed_piid(q) for q in case.k.contracts if q[-4:] == p[-4:] and q != p]
        if twins:
            case.flags.append(f"PIID collision: {dashed_piid(p)} shares its last four digits with {', '.join(twins)}. "
                              "Different contracts; matched on the full PIID only (E-15).")
        return {"found": f"{dashed_piid(p)} is not in the keyset or the knowledge graph", "collision_with": twins}
    props = c.get("props", {})
    out = {"found": f"{dashed_piid(p)}: {c.get('label')}", "relations": []}
    if props.get("registered") is False:
        out["found"] += " (seen in the corpus, not a registered CVN-79 contract)"
    for rel, dst, rp in c.get("rels", []):
        out["relations"].append(f"{rel} {dst}")
        cite = f"knowledge graph contract:{dashed_piid(p)} {rel} {dst} (seed/keyset.yaml)"
        if rel == "prime_contract_for":
            case.ev("keyset", "keyset_prime", f"{dashed_piid(p)} is the registered prime contract for {dst.split(':')[1]}.",
                    {hull_to_h(dst): 1.0}, "AUTHORITATIVE", cite, True, clue.id)
        elif rel in ("excluded_from", "resolved_not_this_hull"):
            why = props.get("why") or rp.get("rule") or ""
            per = {hull_to_h(dst): -1.0}
            if re.search(r"CVN-?\s?8[01]", why):
                per["CVN-80/81"] = 1.0
            elif rel == "resolved_not_this_hull":
                per["NOT_CARRIER"] = 0.7
            case.ev("keyset", "keyset_excluded", f"{dashed_piid(p)} is registered as not {dst.split(':')[1]}. {why}".strip(),
                    per, "AUTHORITATIVE", cite, True, clue.id)
        elif rel == "partial_scope_for":
            share = rp.get("cvn79_share_usd_m")
            case.ev("keyset", "keyset_partial",
                    f"{dashed_piid(p)} is multi-hull; the CVN-79 share is ${share}M. {rp.get('warning') or ''}".strip(),
                    {"CVN-79": 0.5, "CLASS_SHARED": 1.0}, "AUTHORITATIVE", cite, False, clue.id)
            case.flags.append(f"{dashed_piid(p)} is a multi-hull contract: an amount on it is not a CVN-79 number "
                              f"without an allocation.")
        elif rel == "awarded_to":
            case.add_clue("cage", dst.split("CAGE-")[-1], "keyset", cite, clue.id, "exact")
    neg = case.k.neg_terms.get(dashed_piid(p))
    if neg:
        out["negative_vocabulary"] = neg
    return out


def _tx_clues(case: Case, r: dict, origin: str, parent: int, strength: str, cite: str) -> None:
    for key, col in (("piid", "award_id_piid"), ("cage", "cage_code"), ("vendor_name", "recipient_name"),
                     ("program_code", "dod_acquisition_program_code"), ("psc", "product_or_service_code"),
                     ("description", "transaction_description"), ("tx_key", "contract_transaction_unique_key")):
        if r.get(col):
            case.add_clue(key, r[col], origin, cite, parent, strength)
    for t in loa.split_list(r.get("treasury_accounts_funding_this_award")):
        case.add_clue("award_tas", t, origin, cite, parent, "derived")


def _s_fpds(case: Case, clue: Clue, src: Sources) -> dict:
    c = cents_of(clue.value)
    if c is None or c == 0:
        return {"found": "no usable amount"}
    rows = src.fpds_by_amount(amount_str(c))
    date = next((x.value for x in case.values("date")), "")
    if date and rows:
        near = [r for r in rows if abs(_days(r.get("action_date", ""), date)) <= 31]
        rows = near or rows
    case.flags.append(SCOPE_NOTE)
    if not rows:
        return {"found": f"no FPDS transaction on the loaded contracts equals {loa.dollars(c)}"}
    strength = _amount_strength(case, c, len(rows), "FPDS transactions")
    for r in rows[:5]:
        cite = (f"FPDS (USAspending) {r.get('_table')} row {r.get('_row_num')}: {r.get('award_id_piid')} "
                f"{r.get('modification_number')} {r.get('action_date')}")
        if strength == "candidate":
            case.add_clue("piid_candidate", r.get("award_id_piid", ""), "fpds_amount", cite, clue.id, "ambiguous")
        else:
            _tx_clues(case, r, "fpds_amount", clue.id, strength, cite)
    return {"found": f"{len(rows)} FPDS transaction(s) equal {loa.dollars(c)} to the cent",
            "matches": [{k: r.get(k) for k in ("award_id_piid", "modification_number", "action_date",
                                              "federal_action_obligation")} for r in rows[:5]]}


SCOPE_NOTE = ("FPDS, File C and sub-award rows are loaded only for the two CVN-79 contracts, so a match there "
              "is looked for where CVN-79 is; a no-match is not evidence against CVN-79.")


def _amount_strength(case: Case, c: int, n: int, what: str) -> str:
    """How far an amount match can be trusted as a link.

    exact     one match on an amount with cents or odd dollars: a real link
    ambiguous one match on a round amount (whole thousands): could be chance
    candidate several matches: the rows are leads, not this record
    """
    rnd = c % 100_000 == 0
    if n > 1:
        case.flags.append(f"The amount {loa.dollars(c)} matches {n} {what}; they are kept as candidates, not links.")
        return "candidate"
    if rnd:
        case.flags.append(f"{loa.dollars(c)} is a round amount; its single match in {what} may be chance.")
        return "ambiguous"
    return "exact"


def _days(a: str, b: str) -> int:
    from datetime import date
    try:
        return (date.fromisoformat(a[:10]) - date.fromisoformat(b[:10])).days
    except ValueError:
        return 10 ** 6


def _s_filec(case: Case, clue: Clue, src: Sources) -> dict:
    c = cents_of(clue.value)
    if c is None or c == 0:
        return {"found": "no usable amount"}
    rows = src.filec_by_amount(amount_str(c))
    if not rows:
        return {"found": f"no File C (federal account funding) row equals {loa.dollars(c)}"}
    strength = _amount_strength(case, c, len(rows), "File C rows")
    for r in rows[:5]:
        cite = f"File C {r.get('_table')} row {r.get('_row_num')}: {r.get('submission_period')}"
        if strength == "candidate":
            case.add_clue("piid_candidate", r.get("award_id_piid", ""), "filec_amount", cite, clue.id, "ambiguous")
            continue
        case.add_clue("piid", r.get("award_id_piid", ""), "filec_amount", cite, clue.id, strength)
        case.add_clue("tas", r.get("treasury_account_symbol", ""), "filec_amount", cite, clue.id, strength)
        for key, col in (("object_class", "object_class_code"), ("program_activity", "program_activity_code")):
            if r.get(col):
                case.element(key, r[col], cite, 0.9 if strength == "exact" else 0.5, "File C row with the same amount")
    return {"found": f"{len(rows)} File C row(s) equal the amount",
            "matches": [{k: r.get(k) for k in ("submission_period", "treasury_account_symbol", "award_id_piid")}
                        for r in rows[:5]]}


def _s_subaward(case: Case, clue: Clue, src: Sources) -> dict:
    if clue.key == "uei":
        rows = src.subawards(uei=clue.value)
    elif clue.key == "vendor_name":
        if len(clue.value) < 4:
            return {"found": "vendor name too short to search"}
        rows = src.subawards(name=clue.value)
    else:
        c = cents_of(clue.value)
        rows = src.subawards(amount=amount_str(c)) if c else []
    if not rows:
        return {"found": f"no sub-award on N00024-15-C-2114 matches {clue.key} {clue.value!r}"}
    n_prime = {r.get("prime_award_piid") for r in rows}
    if clue.key == "amount":
        strength = _amount_strength(case, cents_of(clue.value) or 0, len(rows), "sub-awards")
    else:
        strength = "exact" if clue.key == "uei" else "derived"
    for r in rows[:3]:
        cite = f"USAspending sub-awards row {r.get('_row_num')}: {r.get('subawardee_name')} {r.get('subaward_number')}"
        if strength == "candidate":
            case.add_clue("piid_candidate", r.get("prime_award_piid", ""), "subaward", cite, clue.id, "ambiguous")
            continue
        case.add_clue("piid", r.get("prime_award_piid", ""), "subaward", cite, clue.id, strength)
        if r.get("subaward_description"):
            case.add_clue("description", r["subaward_description"], "subaward", cite, clue.id, "derived")
    return {"found": f"{len(rows)} sub-award(s) under {', '.join(sorted(x for x in n_prime if x))}",
            "matches": [{k: r.get(k) for k in ("subawardee_name", "subaward_amount", "subaward_action_date",
                                              "subaward_description")} for r in rows[:5]]}


def _s_tas(case: Case, clue: Clue, src: Sources) -> dict:
    p = loa.parse_tas(clue.value)
    if p is None:
        m = MAIN_RE.search(clue.value.upper())
        if not m:
            return {"found": f"{clue.value!r} is not a parseable TAS or main account"}
        main = m.group(1)
        _colour, title = loa.MAIN_ACCOUNTS.get(main, ("OTHER", "unknown"))
        case.element("appropriation", f"{main} {title}", "main account in the record", 0.9, "parsed")
        return {"found": f"main account {main} ({title}); no availability years, so no budget year. SCN funds "
                         "every ship type (submarines too), so the account alone does not move any case"}
    case.element("appropriation", f"{p.main} {p.title}", "TAS", 1.0, f"parsed {p.raw}")
    case.element("availability", f"FY{p.bpoa}-FY{p.epoa}" if p.bpoa else "no-year", "TAS", 1.0, "parsed")
    on = case.k.cvn79_tas.get(p.raw, [])
    if on:
        case.ev("tas_profile", "tas_on_cvn79_award",
                f"{p.raw} is listed as funding {', '.join(dashed_piid(x) for x in on)} (registered CVN-79 contracts).",
                {"CVN-79": 1.0, "CLASS_SHARED": 0.4}, "AUTHORITATIVE",
                "USAspending award-level treasury_accounts_funding_this_award / File C", clue=clue.id)
        for x in on:
            case.add_clue("piid_candidate", x, "tas_profile", f"award account list of {x}", clue.id, "derived")
    return {"found": f"{p.raw}: {p.title}, FY{p.bpoa}-FY{p.epoa}; on CVN-79 award lists: {bool(on)}"}


def _s_program_code(case: Case, clue: Clue, src: Sources) -> dict:
    if clue.key == "program_code":
        desc = case.k.program_codes.get(clue.value)
        if desc:
            case.ev("program_code", "program_code", f"DoD acquisition program code {clue.value} ({desc}) is the code on "
                    "every CVN-79 contract action. It names the class, not the hull.",
                    {h: 1.0 for h in FORD}, "AUTHORITATIVE", "FPDS dod_acquisition_program_code on N00024-15-C-2114 and "
                    "N00024-09-C-2116", clue=clue.id)
            return {"found": f"{clue.value} = {desc} (class level)"}
        return {"found": f"program code {clue.value} is not one seen on CVN-79 contracts"}
    if clue.value in case.k.psc_codes:
        case.ev("program_code", "program_code", f"PSC {clue.value} is used on CVN-79 contract actions.",
                {h: 1.0 for h in FORD}, "AUTHORITATIVE", "FPDS product_or_service_code", clue=clue.id, scale=0.3)
        return {"found": f"PSC {clue.value} seen on CVN-79 contracts"}
    return {"found": f"PSC {clue.value} not seen on CVN-79 contracts"}


_HULL_PATTERNS = (
    (r"\bCVN[\s-]*79\b", "text_hull", {"CVN-79": 1.0}, "names CVN-79"),
    (r"\bCVN[\s-]*78\s+CLASS\b|\bFORD[\s-]+CLASS\b|\bCVN[\s-]*21\b", "text_class",
     {"CLASS_SHARED": 1.0, "CVN-79": 0.3, "CVN-78": 0.3, "CVN-80/81": 0.3}, "names the Ford class"),
    (r"\bCVN[\s-]*78\b(?!\s+CLASS)", "text_hull", {"CVN-78": 1.0}, "names CVN-78"),
    (r"\bCVN[\s-]*8[01]\b|\bDORIS\s+MILLER\b", "text_hull", {"CVN-80/81": 1.0}, "names CVN-80 or CVN-81"),
    (r"\bCVN?[\s-]*(6[5-9]|7[0-7])\b|\bNIMITZ\b|\bRCOH\b", "text_hull", {"OTHER_CARRIER": 1.0},
     "names a non-Ford carrier"),
    (r"\bSSBN\b|\bSSN\b|SUBMARINE|\bLCAC\b|\bDDG\b|\bLHA\b|\bLPD\b|\bFFG\b|FRIGATE|DESTROYER", "text_not_carrier",
     {"NOT_CARRIER": 1.0}, "names a non-carrier platform"),
)


def _s_text(case: Case, clue: Clue, src: Sources) -> dict:
    t = clue.value.upper()
    hits = []
    kind_scale = 1.0 if clue.key != "hull" else 0.0
    for pat, kind, per, what in _HULL_PATTERNS:
        if re.search(pat, t):
            hits.append(what)
            if clue.key == "hull":
                case.ev("text_cues", "stated_hull", f"The record states a hull: {clue.value!r} ({what}).", per, "STATED",
                        "the record itself", clue=clue.id)
            else:
                case.ev("text_cues", kind, f"Text {what}: {clue.value[:120]!r}", per,
                        "STATED" if clue.origin == "record" else "AUTHORITATIVE", clue.citation, clue=clue.id,
                        scale=kind_scale)
    has_hull_no = re.search(r"\bCVN?[\s-]*\d{2}\b", t)
    if re.search(r"\bKENNEDY\b|\bJFK\b", t) and not has_hull_no:
        hits.append("names Kennedy without a hull number")
        case.ev("text_cues", "text_name", "Text names Kennedy with no hull number. CV-67 was also USS John F. Kennedy, "
                "built at the same yard (negative vocabulary).", {"CVN-79": 1.0, "OTHER_CARRIER": 0.5}, "STATED",
                clue.citation, clue=clue.id)
        case.flags.append("Name collision: 'Kennedy' alone fits CVN-79 and CV-67.")
    if re.search(r"\bENTERPRISE\b", t) and not has_hull_no:
        hits.append("names Enterprise without a hull number")
        case.ev("text_cues", "text_name", "Text names Enterprise with no hull number (CVN-80 or the old CVN-65).",
                {"CVN-80/81": 1.0, "OTHER_CARRIER": 0.7}, "STATED", clue.citation, clue=clue.id)
        case.flags.append("Name collision: 'Enterprise' alone fits CVN-80 and CVN-65.")
    for term, why in case.k.neg_terms.items():
        if len(term) >= 4 and not PIID_RE.match(term.upper()) and re.search(r"\b" + re.escape(term.upper()) + r"\b", t):
            if re.search(r"submarine|SSBN|Columbia|LCAC|sonar|acoustic", why, re.IGNORECASE):
                hits.append(f"negative term {term}")
                case.ev("text_cues", "text_not_carrier", f"Negative vocabulary {term!r}: {why}", {"NOT_CARRIER": 1.0},
                        "WORKING", "seed/negative_vocabulary.yaml via knowledge graph", clue=clue.id)
            elif not re.search(r"CVN", term):
                case.caveats.append({"rule": f"negative vocabulary {term!r}", "meaning": why})
    # clues hidden in the text
    for m in PIID_RE.finditer(t):
        case.add_clue("piid", "".join(m.groups()), "text_cues", f"PIID found in text of clue {clue.id}", clue.id, "derived")
    for m in TAS_RE.finditer(t):
        tas = m.group(0) if m.group(0).startswith("0") else "0" + m.group(0)
        case.add_clue("tas", tas, "text_cues", f"TAS found in text of clue {clue.id}", clue.id, "derived")
    for m in PE_RE.finditer(t):
        case.add_clue("program_element", m.group(0), "text_cues", f"program element in text of clue {clue.id}", clue.id)
    for m in BLI_RE.finditer(t):
        case.add_clue("bli", m.group(1), "text_cues", f"BLI in text of clue {clue.id}", clue.id)
    return {"found": "; ".join(hits) or "no hull, class or platform vocabulary"}


def _apply_hull_counts(case: Case, counts: dict[str, int], what: str, cite: str, kind: str, clue: Clue,
                       min_pages: int = 2) -> str:
    def shares_of(c: dict[str, int]) -> dict[str, float]:
        agg: dict[str, int] = {}
        for hull, n in c.items():
            agg[hull_to_h(hull)] = agg.get(hull_to_h(hull), 0) + n
        t = sum(agg.values()) or 1
        return {h: n / t for h, n in agg.items()}

    tot = sum(counts.values())
    if tot < min_pages:
        return f"{what}: too few hull mentions ({tot}) to weigh"
    shares = shares_of(counts)
    # The corpus is mostly CVN 78 programme reports, so raw shares favour CVN-78. Weigh the lift
    # over the whole-corpus baseline instead: only a hull mentioned MORE than usual is evidence.
    base = shares_of(case.k.hull_baseline) if case.k.hull_baseline else {}
    lift = {h: round(shares.get(h, 0) - base.get(h, 0), 4) for h in set(shares) | set(base)} if base else shares
    top = max(lift, key=lift.get)
    if lift[top] < 0.10:
        return f"{what}: {tot} hull mentions, none above the corpus baseline"
    case.ev(kind, kind, f"{what}: hull mentions on linked authoritative pages vs the whole corpus, "
            + ", ".join(f"{h} {shares.get(h, 0):.0%} (base {base.get(h, 0):.0%})"
                        for h in sorted(lift, key=lambda x: -lift[x])[:3]),
            {h: v * 2 for h, v in lift.items() if abs(v) >= 0.05}, "AUTHORITATIVE", cite, clue=clue.id)
    return f"{what}: {tot} hull mentions, most above baseline {top} (+{lift[top]:.0%})"


def _s_budget(case: Case, clue: Clue, src: Sources) -> dict:
    node = f"{'bli' if clue.key == 'bli' else 'program_element'}:{clue.value}"
    links = case.k.budget_links.get(node, [])
    for rel, dst in links:
        if rel == "funds" and dst.startswith("hull:"):
            case.ev("budget_lines", "budget_element", f"{node} funds {dst} in the knowledge graph.", {hull_to_h(dst): 1.0},
                    "AUTHORITATIVE", f"knowledge graph {node} {rel} {dst}", clue=clue.id)
        if rel == "line_of":
            case.element("appropriation", dst.split(":")[1], f"knowledge graph {node} line_of", 1.0, "BLI belongs to it")
    neg = case.k.neg_terms.get(clue.value)
    if neg:
        case.ev("budget_lines", "budget_element", f"{clue.value}: {neg}", {"CLASS_SHARED": 1.0}, "WORKING",
                "negative vocabulary", clue=clue.id)
    res = _apply_hull_counts(case, src.node_hull_mentions(node), node, f"pages and exhibit tables linked to {node}",
                             "cooccurrence", clue)
    return {"found": f"{len(links)} graph link(s); {res}"}


def _s_documents(case: Case, clue: Clue, src: Sources) -> dict:
    term = dashed_piid(clue.value) if clue.key in ("piid", "piid_candidate") else clue.value
    pages = src.search_pages(term, 8)
    auth = [p for p in pages if p.get("grade") == "AUTHORITATIVE"]
    if not pages:
        return {"found": f"{term!r} appears in no loaded document"}
    out_pages = [{"document": p["filename"], "page": p["page"], "grade": p.get("grade"),
                  "snippet": p.get("snippet")} for p in pages[:5]]
    if clue.key == "piid_candidate":
        # a candidate is a lead, not this record: show where it is, weigh nothing, chase no further
        return {"found": f"{term!r} appears on {len(pages)} page(s); candidate only, not weighed", "pages": out_pages}
    ids = [f"page:{p['artifact_id']}:{int(p['page']):04d}" for p in auth]
    res = _apply_hull_counts(case, src.hull_mentions(ids), f"documents mentioning {term!r}",
                             "; ".join(f"{p['filename']} p.{p['page']}" for p in auth[:4]), "cooccurrence", clue) \
        if ids else "only working documents mention it"
    for p in pages[:4]:
        for m in PIID_RE.finditer((p.get("snippet") or "").upper()):
            pid = "".join(m.groups())
            if pid != norm_piid(clue.value):
                case.add_clue("piid_candidate", pid, "documents", f"{p['filename']} p.{p['page']}", clue.id, "derived")
    return {"found": res, "pages": out_pages}


def _s_vendor(case: Case, clue: Clue, src: Sources) -> dict:
    v = case.k.vendors.get(clue.value)
    if not v:
        return {"found": f"CAGE {clue.value} is not a vendor in the knowledge graph"}
    case.element("vendor", f"{v.get('name')} (CAGE {clue.value})", "knowledge graph vendor node", 1.0, "CAGE lookup")
    case.ev("vendor", "vendor", f"CAGE {clue.value} is {v.get('name')}, a prime on registered carrier contracts; it "
            "also builds or equips other ships.", {h: 1.0 for h in FORD}, "AUTHORITATIVE",
            f"knowledge graph vendor:CAGE-{clue.value}", clue=clue.id)
    res = _apply_hull_counts(case, src.node_hull_mentions(f"vendor:CAGE-{clue.value}"), f"vendor CAGE {clue.value}",
                             f"pages mentioning vendor:CAGE-{clue.value}", "cooccurrence", clue, min_pages=3)
    return {"found": f"{v.get('name')}; {res}"}


def _s_exhibit(case: Case, clue: Clue, src: Sources) -> dict:
    c = cents_of(clue.value)
    if c is None or abs(c) < 1_000_000_00:
        return {"found": "amount under $1M; budget exhibits are in millions, a match would be chance"}
    if (abs(c) // 100_000) % 100 == 0:
        return {"found": "amount is round to $0.1M; too many exhibit cells would match by chance"}
    vals = sorted({f"{abs(c) / 1e8:.3f}", f"{round(abs(c) / 1e5) / 1e3:.3f}"})
    rows = src.exhibit_cells(vals)
    if not rows:
        return {"found": f"no budget exhibit cell equals {vals[0]} ($M)"}
    hull_counts: dict[str, int] = {}
    for r in rows[:10]:
        txt = f"{r.get('row_header', '')} {r.get('col_header', '')} {r.get('title_block', '')}".upper()
        for m in re.finditer(r"\bCVN[\s-]*(\d{2})\b", txt):
            hull_counts[f"hull:CVN-{m.group(1)}"] = hull_counts.get(f"hull:CVN-{m.group(1)}", 0) + 1
    cite = "; ".join(f"{r.get('filename')} p.{r.get('page')} [{r.get('row_header')} | {r.get('col_header')}]" for r in rows[:3])
    res = _apply_hull_counts(case, hull_counts, "budget exhibit cells equal to the amount", cite, "exhibit_amount",
                             clue, min_pages=2) if hull_counts else "matched cells name no hull"
    case.flags.append("A budget exhibit match is on a rounded $M value and can be chance; treat it as a pointer.")
    return {"found": f"{len(rows)} exhibit cell(s) equal ${vals[0]}M; {res}",
            "cells": [{k: r.get(k) for k in ("filename", "page", "row_header", "col_header", "value")} for r in rows[:5]]}


SKILLS: tuple[Skill, ...] = (
    Skill("keyset", ("piid",), "knowledge graph contract nodes from seed/keyset.yaml (hull verdicts, collisions)", _s_keyset),
    Skill("fpds_amount", ("amount",), "FPDS prime transactions for N00024-15-C-2114 and N00024-09-C-2116 (USAspending)",
          _s_fpds),
    Skill("filec_amount", ("amount",), "File C federal account funding rows for N00024-15-C-2114", _s_filec),
    Skill("subaward", ("uei", "vendor_name", "amount"), "2,990 sub-awards under N00024-15-C-2114", _s_subaward),
    Skill("tas_profile", ("tas",), "TAS vocabulary (core/analyst/loa.py) and the account lists of CVN-79 awards",
          _s_tas),
    Skill("program_code", ("program_code", "psc"), "FPDS program and product codes seen on CVN-79 awards",
          _s_program_code),
    Skill("text_cues", ("description", "hull"), "hull/class/platform vocabulary and the negative vocabulary", _s_text),
    Skill("budget_lines", ("bli", "program_element"), "knowledge graph BLI / program element links and SCN exhibit "
          "tables (SCN Book PB27, SAR, MSAR)", _s_budget),
    Skill("vendor", ("cage",), "knowledge graph vendor nodes and the pages that mention them", _s_vendor),
    Skill("documents", ("piid", "piid_candidate", "program_element"), "full text of every loaded PDF: SCN Book, SAR/MSAR, "
          "GAO, CRS, NPS, DoN 5200.45A, DCMA MAN 2101-02, SUPSHIP Ops Manual", _s_documents),
    Skill("budget_exhibit_amount", ("amount",), "budget exhibit cells (pdf_cells, exact decimals)", _s_exhibit),
)


def plan(case: Case) -> dict:
    keys = {c.key for c in case.clues}
    ready = [{"skill": s.name, "reads": s.reads, "on": sorted(set(s.needs) & keys)} for s in SKILLS if set(s.needs) & keys]
    waiting = [{"skill": s.name, "reads": s.reads, "waiting_for": list(s.needs)} for s in SKILLS if not set(s.needs) & keys]
    return {"ready": ready, "waiting": waiting}


# ------------------------------------------------------------------ decide

def score(evidence: list[Evidence]) -> dict[str, float]:
    s = {h: 0.0 for h in H}
    for e in evidence:
        for h, v in e.weights.items():
            s[h] += v
    mx = max(s.values())
    ex = {h: math.exp(v - mx) for h, v in s.items()}
    z = sum(ex.values())
    return {h: v / z for h, v in ex.items()}


def _review(case: Case, post: dict, ranked: list[str]) -> dict:
    top, second = ranked[0], ranked[1]
    reasons = []
    if not case.evidence:
        reasons.append("No skill found evidence: the record has too few usable data elements.")
    if post[top] < REVIEW_THRESHOLD:
        reasons.append(f"Top case confidence {post[top]:.2f} is below {REVIEW_THRESHOLD}.")
    if post[top] - post[second] < REVIEW_MARGIN:
        reasons.append(f"{top} and {second} are within {REVIEW_MARGIN} of each other.")
    support = [e for e in case.evidence if e.weights.get(top, 0) > 0]
    if support and not any(e.grade == "AUTHORITATIVE" for e in support):
        reasons.append("Nothing authoritative supports the top case; it rests on stated or working material.")
    against = [e for e in case.evidence if e.weights.get(top, 0) <= -1.0 and e.grade == "AUTHORITATIVE"]
    if against:
        reasons.append(f"{len(against)} authoritative item(s) argue against the top case.")
    reasons += [f for f in case.flags if "collision" in f.lower() or "multi-hull" in f.lower()]
    qs = []
    known = {c.key for c in case.clues}
    if "piid" not in known:
        qs.append("What is the obligating document (contract number) on this line?")
    if "tas" not in known:
        qs.append("What line of accounting (TAS, BPOA/EPOA) does it post to?")
    if post[top] - post[second] < REVIEW_MARGIN:
        qs.append(f"Which is it, {HYPOTHESES[top]} or {HYPOTHESES[second]}? Cite the document that says so.")
    return {"required": bool(reasons), "reasons": reasons, "questions_for_reviewer": qs}


def investigate(record: dict, k: Knowledge, src: Sources, max_hops: int = 4,
                loa_fn: Callable[[str], dict | None] | None = None) -> dict:
    known, other = normalize(record)
    case = Case(record=record, k=k)
    for key, v in known.items():
        if key == "doc_number" and PIID_RE.search(v.upper()):
            case.add_clue("piid", v, "record", "the record", None, "stated")
        case.add_clue(key, v, "record", "the record", None, "stated")
    for k2, v in other.items():
        case.add_clue("description", f"{k2}: {v}", "record", f"record field {k2!r}", None, "stated")
    prof = profile(record)
    first_plan = plan(case)

    for hop in range(1, max_hops + 1):
        todo = [(s, c) for s in SKILLS for c in list(case.clues)
                if c.key in s.needs and (s.name, c.key, c.value) not in case.done]
        if not todo:
            break
        for s, c in todo:
            case.done.add((s.name, c.key, c.value))
            before = len(case.clues)
            try:
                out = s.fn(case, c, src)
            except Exception as e:  # noqa: BLE001 - one failing source must not end the case
                out = {"found": f"source unavailable ({type(e).__name__})"}
            new = case.clues[before:]
            case.trail.append({"hop": hop, "skill": s.name, "reads": s.reads, "on": f"{c.key}={c.value[:80]}",
                               "clue": c.id, **out,
                               "new_clues": [f"#{n.id} {n.key}={n.value[:60]} ({n.strength})" for n in new]})

    # line of accounting for a matched FPDS line, through the LOA engine
    if loa_fn:
        for c in case.values("tx_key"):
            if c.strength != "exact":
                continue
            try:
                r = loa_fn(c.value)
            except Exception:  # noqa: BLE001
                r = None
            if r and r.get("options"):
                o = r["options"][0]
                case.element("tas", o["loa"]["tas"], f"LOA engine on {c.value}", o["confidence"],
                             "inferred: " + ", ".join(e["method"] for e in o["evidence"][:3]))
                for key in ("object_class", "program_activity"):
                    v = o["loa"].get(key, {}).get("value")
                    if v:
                        case.element(key, v, f"LOA engine on {c.value}", o["confidence"] * o["loa"][key]["share"],
                                     o["loa"][key]["basis"])
                case.trail.append({"hop": "after", "skill": "loa_engine", "on": c.value,
                                   "found": f"top account {o['loa']['tas']} at {o['confidence']}"})

    for key in ("piid", "tas", "cage", "vendor_name", "bli", "program_element", "date", "amount"):
        for c in case.values(key):
            if c.origin != "record":
                case.element(key, c.value, c.citation, 0.95 if c.strength == "exact" else 0.5,
                             f"found by {c.origin} from clue #{c.parent}")

    try:
        case.caveats += [{"rule": m.get("statement"), "consequence": m.get("consequence"),
                          "citation": m.get("citation"), "review_state": m.get("review_state")}
                         for m in src.mechanisms(_mech_terms(case), 5)]
    except Exception as error:  # noqa: BLE001  # caveats are optional; the case still scores
        logging.getLogger(__name__).warning("mechanism caveats unavailable: %s", error)

    post = score(case.evidence)
    ranked = sorted(post, key=post.get, reverse=True)
    cases = []
    for i, h in enumerate(ranked[:3], 1):
        pro = [e for e in case.evidence if e.weights.get(h, 0) > 0]
        con = [e for e in case.evidence if e.weights.get(h, 0) < 0]
        cases.append({
            "rank": i, "case": h, "label": HYPOTHESES[h], "confidence": round(post[h], 4),
            "basis": "deterministic" if any(e.deterministic and e.weights.get(h, 0) > 0 for e in pro) else "inferred",
            "for": [_ev_out(e, h) for e in sorted(pro, key=lambda e: -e.weights[h])[:6]],
            "against": [_ev_out(e, h) for e in sorted(con, key=lambda e: e.weights[h])[:4]],
        })
    review = _review(case, post, ranked)
    perfect = cases[0]["basis"] == "deterministic" and not review["required"]
    found_keys = set(case.elements) | {c.key for c in case.clues}
    still_missing = [m for m in prof["missing_critical"]
                     if not ({"piid": {"piid"}, "tas": {"tas"}, "vendor": {"cage", "vendor_name", "uei"},
                              "budget_line": {"bli", "program_element"}}.get(m["element"], {m["element"]}) & found_keys)]
    return {
        "engine": VERSION,
        "grade": "LEAD",
        "question": "Which hull or program does this record belong to, and what are its missing data elements?",
        "profile": prof,
        "plan_at_start": first_plan,
        "trail": case.trail,
        "clue_chain": [{"id": c.id, "key": c.key, "value": c.value[:120], "from": c.origin, "parent": c.parent,
                        "strength": c.strength, "citation": c.citation} for c in case.clues],
        "cases": cases,
        "perfect_match": perfect,
        "data_elements_recovered": case.elements,
        "still_missing": [{**m, "collection_requirement": f"Retrieve {m['authoritative_in']} from {m['held_by']}."}
                          for m in still_missing],
        "human_review": review,
        "flags": sorted(set(case.flags)),
        "rules_and_caveats": case.caveats[:8],
        "scoring": {"method": "sum of stated evidence weights per case, softmax; uniform prior",
                    "weights": EVIDENCE_WEIGHTS, "posterior_all": {h: round(post[h], 4) for h in ranked}},
        "caveat": ("Grade LEAD. Cases are hypotheses with cited evidence, not figures. Do not enter them in the claim "
                   "ledger; confirm through the collection requirements. Only sources loaded in Unity Catalog were read."),
    }


def _ev_out(e: Evidence, h: str) -> dict:
    return {"skill": e.skill, "statement": e.statement, "weight": e.weights[h], "grade": e.grade, "citation": e.citation}


def _mech_terms(case: Case) -> list[str]:
    terms = [dashed_piid(c.value) for c in case.values("piid")][:3]
    text = " ".join(c.value for c in case.values("description")).upper()
    for t in ("GFE", "GOVERNMENT FURNISHED", "OUTLAY", "ADVANCE PROCUREMENT", "COST CAP", "EMALS", "AAG", "PHASE",
              "DELIVERY", "WARRANTY", "POST SHAKEDOWN", "PSA"):
        if t in text:
            terms.append(t.title())
    return terms
