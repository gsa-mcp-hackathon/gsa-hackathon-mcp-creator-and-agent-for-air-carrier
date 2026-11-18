"""What a document is and how it is laid out.

A J-book page is identified by its exhibit (P-40, P-5c, P-27, P-8a, P-35,
P-10 ...), its P-1 line item number and title, its appropriation and its date,
all printed in the page header. A SAR is identified by its section headings
and dollar bases, a CRS or GAO report by its numbered tables and figures. The
document map is the run-length encoding of those labels over the pages, so a
reader can go straight to "LI 2001, Exhibit P-5c" without the other 500 pages.
"""
from __future__ import annotations

import re

KINDS = (
    ("budget_justification", re.compile(r"SCN_Book|J-?Book|Justification Book|_Book\b", re.I)),
    ("selected_acquisition_report", re.compile(r"\bM?SAR\b|_SAR_|MSAR", re.I)),
    ("crs_report", re.compile(r"^RS\d+|^R\d{5}|\bCRS\b", re.I)),
    ("gao_report", re.compile(r"^gao", re.I)),
    ("thesis_or_study", re.compile(r"^NPS", re.I)),
    ("regulation_or_manual", re.compile(r"MAN_|Manual|5200\.45|Instruction|OPNAVINST|DoDI|FMR", re.I)),
)
EXHIBIT = re.compile(r"Exhibit\s+([PRO]-\d+[a-z]?)\s*,?\s*([^\n:]*?)(?::\s*(PB\s*\d{4}[^\n]*))?\s*$", re.M)
LINE_ITEM = re.compile(r"(?:LI|P-1 Line Item Number / Title:?)\s*\n?\s*(\d{4})\s*[-/]\s*([^\n]+)")
APPROP = re.compile(r"Appropriation\s*/\s*Budget Activity[^:]*:\s*\n?\s*([0-9A-Z]{4,6}N?)\s*/\s*(\d+)(?:\s*/\s*(\d+))?")
DATE = re.compile(r"\bDate:\s*([A-Z][a-z]+ \d{4})")
SAR_SECTION = re.compile(
    r"^\s*(Program Information|Responsible Office|References|Mission and Description|Executive Summary|"
    r"Threshold Breaches|Schedule|Performance|Track to Budget|Cost and Funding|Low Rate Initial Production|"
    r"Foreign Military Sales|Nuclear Costs|Unit Cost|Cost Variance|Contracts|Deliveries and Expenditures|"
    r"Operating and Support Cost)\s*$", re.M)
NUMBERED = re.compile(r"^\s*(Table|Figure)\s+(\d+[A-Z]?)\.\s+([^\n]+)", re.M)
SAR_DOLLARS = re.compile(r"\b(BY\s?\d{4}\s*\$[MK]|TY\s*\$[MK])\b")


def doc_kind(filename: str, first_page_text: str = "") -> str:
    for kind, pat in KINDS:
        if pat.search(filename or ""):
            return kind
    head = (first_page_text or "")[:2000]
    if "Selected Acquisition Report" in head:
        return "selected_acquisition_report"
    if "Congressional Research Service" in head:
        return "crs_report"
    if "Justification Book" in head or "Exhibit P-40" in head:
        return "budget_justification"
    if "GAO" in head:
        return "gao_report"
    return "other"


def label_page(kind: str, text: str) -> dict:
    """The structural labels printed on one page."""
    t = text or ""
    lab: dict = {}
    if kind == "budget_justification":
        e = EXHIBIT.search(t)
        if e:
            lab["exhibit"] = e.group(1)
            lab["exhibit_title"] = " ".join(e.group(2).split()).rstrip(",")
        li = LINE_ITEM.search(t)
        if li:
            lab["line_item"] = li.group(1)
            lab["line_item_title"] = " ".join(li.group(2).replace("UNCLASSIFIED", "").split())[:80]
        a = APPROP.search(t)
        if a:
            lab["appropriation"] = a.group(1)
            lab["budget_activity"] = a.group(2)
        d = DATE.search(t)
        if d:
            lab["date"] = d.group(1)
    elif kind == "selected_acquisition_report":
        s = SAR_SECTION.findall(t)
        if s:
            lab["section"] = s[0].strip()
        dl = SAR_DOLLARS.findall(t)
        if dl:
            lab["dollars"] = sorted({" ".join(x.split()) for x in dl})
    nums = NUMBERED.findall(t)
    if nums:
        lab["captions"] = [f"{k} {n}. {' '.join(title.split())[:90]}" for k, n, title in nums]
    return lab


def document_map(kind: str, pages: list[tuple[int, str]]) -> list[dict]:
    """Run-length encode the page labels. A SAR section carries forward over
    pages that do not reprint its heading."""
    runs: list[dict] = []
    carry: dict = {}
    for page, text in pages:
        lab = label_page(kind, text)
        caps = lab.pop("captions", [])
        if kind == "selected_acquisition_report" and "section" not in lab and carry.get("section"):
            lab["section"] = carry["section"]
        key = {k: lab.get(k) for k in ("exhibit", "line_item", "section")}
        if runs and runs[-1]["key"] == key:
            runs[-1]["last_page"] = page
            runs[-1]["captions"] += caps
        else:
            runs.append({"key": key, "first_page": page, "last_page": page, "labels": lab, "captions": list(caps)})
        carry = lab
    out = []
    for r in runs:
        d = {"pages": [r["first_page"], r["last_page"]], **{k: v for k, v in r["labels"].items() if v}}
        if r["captions"]:
            d["captions"] = r["captions"][:12]
        out.append(d)
    return out
