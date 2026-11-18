"""The detail table: filter, sort, page and export the records behind the
figures.

Four datasets ship as extracts (etl/build_extracts.py), so the table works at
every access level. Exhibit cells (144,610 rows) do not ship; they are read
live through api.live when the app has a warehouse, and the page says so when
it does not.

Every row keeps its locator (artifact, row hash, source file or page), which
is the drill-through requirement (D27): a figure on a page can be followed to
the record, and the record to the document.
"""
from __future__ import annotations

import csv
import functools
import io
import json
import pathlib
from decimal import Decimal, InvalidOperation

from api import live

X = pathlib.Path(__file__).resolve().parent.parent / "data" / "extracts"

# (field, label, kind). kind: text | usd | int | date | list
DATASETS: dict[str, dict] = {
    "transactions": {
        "label": "Contract transactions",
        "blurb": "Every prime action on both CVN-79 contracts, from USAspending. "
                 "Obligation is federal_action_obligation, the per-action amount. "
                 "The running total is deliberately not carried.",
        "cols": [("award_id_piid", "Contract", "text"),
                 ("modification_number", "Mod", "text"),
                 ("transaction_number", "Tx #", "text"),
                 ("action_date", "Action date", "date"),
                 ("action_date_fiscal_year", "FY", "text"),
                 ("action_type", "Action type", "text"),
                 ("federal_action_obligation", "Obligation", "usd"),
                 ("transaction_description", "Description", "text"),
                 ("type_of_contract_pricing", "Pricing type", "text"),
                 ("funding_office_name", "Funding office", "text"),
                 ("awarding_office_name", "Awarding office", "text"),
                 ("treasury_accounts_funding_this_award", "Treasury accounts", "text"),
                 ("federal_accounts_funding_this_award", "Federal accounts", "text"),
                 ("object_classes_funding_this_award", "Object classes", "text"),
                 ("program_activities_funding_this_award", "Program activities", "text"),
                 ("_source_locator", "Source", "text"),
                 ("_row_sha", "Row hash", "text")],
        "facets": ["award_id_piid", "action_date_fiscal_year", "action_type",
                   "type_of_contract_pricing", "funding_office_name"],
        "sum": "federal_action_obligation",
        "default_sort": "action_date",
    },
    "requirements": {
        "label": "Collection requirements",
        "blurb": "What each open gap needs, from whom, as the investigator wrote it. "
                 "Target office is the investigator's free text, shown as written.",
        "cols": [("gap_id", "Gap", "text"), ("pq_id", "Proposed as", "text"),
                 ("target_office", "Target office", "text"),
                 ("target_document", "Document", "text"),
                 ("target_system", "System", "text"),
                 ("period", "Period", "text"), ("account", "Account", "text"),
                 ("instruction", "Instruction", "text"),
                 ("hypothesis", "Hypothesis", "text"), ("cr_id", "ID", "text")],
        "facets": ["gap_id"],
        "default_sort": "gap_id",
    },
    "exhibits": {
        "label": "Budget exhibit tables",
        "blurb": "Every table the Reader extracted from the budget PDFs. Open one to "
                 "see its cells, read live from the cell store.",
        "cols": [("filename", "Document", "text"), ("page", "Page", "int"),
                 ("table_idx", "Table", "int"), ("exhibits", "Exhibit", "list"),
                 ("title", "Title block", "text"), ("n_rows", "Rows", "int"),
                 ("n_cols", "Cols", "int"), ("table_id", "Table ID", "text")],
        "facets": ["filename"],
        "default_sort": "filename",
    },
    "account_funding": {
        "label": "Federal account funding (File C)",
        "blurb": "USAspending File C: federal account funding for N00024-15-C-2114. "
                 "Each row is one account × submission period. Obligation is "
                 "transaction_obligated_amount; outlay is gross_outlay_amount_fyb_to_period_end.",
        "cols": [("award_id_piid", "Contract", "text"),
                 ("treasury_account_symbol", "TAS", "text"),
                 ("federal_account_symbol", "Federal account", "text"),
                 ("federal_account_name", "Account name", "text"),
                 ("object_class_code", "Object class", "text"),
                 ("object_class_name", "OC name", "text"),
                 ("program_activity_code", "Prog activity", "text"),
                 ("program_activity_name", "PA name", "text"),
                 ("submission_period", "Period", "text"),
                 ("transaction_obligated_amount", "Obligated", "usd"),
                 ("gross_outlay_amount_fyb_to_period_end", "Outlay (FYB-period)", "usd"),
                 ("direct_or_reimbursable_funding_source", "D/R", "text"),
                 ("beginning_period_of_availability", "Avail from", "text"),
                 ("ending_period_of_availability", "Avail to", "text"),
                 ("funding_office_name", "Funding office", "text"),
                 ("_source_locator", "Source", "text")],
        "facets": ["award_id_piid", "treasury_account_symbol", "object_class_code",
                   "program_activity_code", "submission_period",
                   "direct_or_reimbursable_funding_source"],
        "sum": "transaction_obligated_amount",
        "default_sort": "submission_period",
    },
    "leads": {
        "label": "Analyst leads",
        "blurb": "Ranked explanations the analyst engine proposed. Leads, not "
                 "findings (D16): each needs a person to accept or reject it.",
        "cols": [("question", "Question", "text"), ("rank", "Rank", "int"),
                 ("option", "Option", "text"), ("confidence", "Confidence", "text"),
                 ("none_of_these", "None of these", "text"),
                 ("status", "Status", "text"), ("piid", "Contract", "text"),
                 ("period", "Period", "text")],
        "facets": ["status", "piid"],
        "default_sort": "question",
    },
}


@functools.lru_cache(maxsize=32)
def _read(path: str, _mtime_ns: int):
    return json.loads(pathlib.Path(path).read_text())


def _file(name: str) -> dict:
    p = X / f"{name}.json"
    if not p.exists():
        return {}
    return _read(str(p), p.stat().st_mtime_ns)


def meta() -> dict:
    return _file("meta")


def extract(name: str) -> dict:
    """Raw extract by name (tieout, pipeline, leads, ...), {} if absent."""
    return _file(name)


def _cell(v, kind: str) -> str:
    if v is None:
        return ""
    if kind == "list":
        return ", ".join(dict.fromkeys(str(x) for x in v)) if isinstance(v, list) else str(v)
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False)
    return str(v)


def rows(ds: str) -> list[dict]:
    spec = DATASETS[ds]
    src = _file(ds).get("rows", [])
    return [{f: _cell(r.get(f), k) for f, _l, k in spec["cols"]} for r in src]


def _key(kind: str):
    def k(v: str):
        if kind in ("usd", "int"):
            try:
                return (0, Decimal(v))
            except (InvalidOperation, ValueError):
                return (1, Decimal(0))
        return (0, v.lower())
    return k


def query(ds: str, q: str = "", filters: dict | None = None, sort: str | None = None,
          desc: bool = False, page: int = 1, size: int = 50) -> dict:
    if ds not in DATASETS:
        raise KeyError(ds)
    spec = DATASETS[ds]
    kinds = {f: k for f, _l, k in spec["cols"]}
    allr = rows(ds)
    filters = {k: v for k, v in (filters or {}).items() if k in kinds and v != ""}
    needle = (q or "").strip().lower()

    def keep(r):
        if any(r.get(k) != v for k, v in filters.items()):
            return False
        return not needle or any(needle in (r[f] or "").lower() for f in kinds)

    hit = [r for r in allr if keep(r)]
    sort = sort if sort in kinds else spec.get("default_sort")
    if sort:
        hit.sort(key=lambda r: _key(kinds[sort])(r[sort]), reverse=bool(desc))
    size = max(1, min(int(size), 500))
    pages = max(1, -(-len(hit) // size))
    page = max(1, min(int(page), pages))
    total_sum = None
    if spec.get("sum"):
        s = Decimal(0)
        for r in hit:
            try:
                s += Decimal(r[spec["sum"]] or 0)
            except InvalidOperation:
                pass
        total_sum = format(s, "f")
    # Facet counts within the current filter, except for the facet's own
    # value, so a chosen facet still shows its siblings.
    facets = {}
    for fct in spec.get("facets", []):
        sub = {k: v for k, v in filters.items() if k != fct}
        cnt: dict[str, int] = {}
        for r in allr:
            if any(r.get(k) != v for k, v in sub.items()):
                continue
            if needle and not any(needle in (r[f] or "").lower() for f in kinds):
                continue
            cnt[r[fct]] = cnt.get(r[fct], 0) + 1
        facets[fct] = sorted(cnt.items(), key=lambda kv: (-kv[1], kv[0]))[:40]
    return {"dataset": ds, "label": spec["label"], "blurb": spec["blurb"],
            "columns": [{"field": f, "label": lab, "kind": k} for f, lab, k in spec["cols"]],
            "total": len(hit), "of": len(allr), "page": page, "pages": pages,
            "size": size, "sort": sort, "desc": bool(desc),
            "sum": total_sum, "sum_field": spec.get("sum"),
            "facets": facets, "filters": filters, "q": q or "",
            "rows": hit[(page - 1) * size: page * size],
            "mode": "extract", "as_of": meta().get("built_at")}


def to_csv(ds: str, **kw) -> str:
    kw.update(page=1, size=500)
    first = query(ds, **kw)
    buf = io.StringIO()
    wr = csv.writer(buf)
    wr.writerow([c["field"] for c in first["columns"]])
    for p in range(1, first["pages"] + 1):
        kw["page"] = p
        for r in query(ds, **kw)["rows"]:
            wr.writerow([r[c["field"]] for c in first["columns"]])
    return buf.getvalue()


def cells(table_id: str) -> dict:
    """One exhibit table as a grid, read live. Without a warehouse, says why
    and points at the document page, which is still a valid drill-through."""
    idx = {r["table_id"]: r for r in _file("exhibits").get("rows", [])}
    t = idx.get(table_id)
    if not t:
        return {"error": f"no exhibit table {table_id}"}
    base = {"table_id": table_id, "filename": t["filename"], "page": t["page"],
            "title": t.get("title"), "n_rows": t["n_rows"], "n_cols": t["n_cols"]}
    st = live.status()
    if not st["live"]:
        return base | {"mode": "extract", "grid": None, "reason": st["reason"]}
    try:
        _c, rs = live.query(
            f"SELECT row_idx, col_idx, value, value_kind, is_header "
            f"FROM {live.fqn('pdf_cells')} WHERE table_id = :t "
            "ORDER BY row_idx, col_idx", {"t": table_id}, row_limit=20000)
    except live.LiveError as exc:
        return base | {"mode": "extract", "grid": None, "reason": str(exc)}
    nr = max([r["row_idx"] for r in rs] + [-1]) + 1
    nc = max([r["col_idx"] for r in rs] + [-1]) + 1
    grid = [[""] * nc for _ in range(nr)]
    head = [False] * nr
    for r in rs:
        grid[r["row_idx"]][r["col_idx"]] = r["value"] or ""
        if str(r.get("is_header")).lower() == "true":
            head[r["row_idx"]] = True
    return base | {"mode": "live", "grid": grid, "header_rows": head}
