"""The in-app agent behind /ask.

A tool-calling loop on the reasoning role's serving endpoint. The model never
answers from memory: it has six tools over the same data the pages render,
and every figure in an answer has to come from a tool result it can cite.

Tables are never read from chunks. Chunked text loses a table's column headers
and units, so search_documents only locates pages: on a page that holds an
extracted table it returns the table ids with the figures masked, and the
figures come from get_exhibit_cells, which reads the lossless cell store with
every cell's row label, column header chain and resolved unit.

What it is not. Its answers are leads (zone L, D16), never reported figures,
and the response says so. It cannot write anything: SQL goes through
api.live.guard (one read-only SELECT over the allowlisted tables) and the
service principal holds SELECT only.

Degrades in steps (D11). No warehouse: run_sql reports why and the other
tools still work from the shipped extracts. No model reachable: the request
is answered with document search hits and the page says so.

Model chains. This module is the app's one place for them: the /ask loop
uses the 'agent' role, and api/si uses 'reasoning' (specialist) and
'checker'. Defaults mirror seed/models.yaml (the app snapshot cannot read
seed/, and checks/test_app.py fails if they drift); resources/app.yml sets
the deployed values through AIRCARRIER_<ROLE>_MODEL / _FALLBACKS. The GPT-6
family is not in the agent chain: it rejects function tools on chat
completions while reasoning is on (probed 2026-11-11).
"""
from __future__ import annotations

import json
import os
import re
import time
from decimal import Decimal

from api import data, explore, live

MAX_STEPS = 6
MAX_TOOL_CHARS = 7000


# role -> (primary, fallbacks). Keep equal to seed/models.yaml.
DEFAULT_CHAINS: dict[str, tuple[str, tuple[str, ...]]] = {
    "agent": ("databricks-gpt-5-5", ("databricks-gemini-3-8-flash", "databricks-grok-4-7")),
    "reasoning": ("databricks-gpt-6-1-sol", ("databricks-grok-4-7", "databricks-gemini-3-8-flash")),
    "checker": ("databricks-gemini-3-8-flash", ("databricks-grok-4-7",)),
}


def role_models(role: str) -> list[str]:
    """Primary then fallbacks for a role; env overrides; de-duplicated in order."""
    primary, fallbacks = DEFAULT_CHAINS[role]
    key = f"AIRCARRIER_{role.upper()}"
    first = os.environ.get(f"{key}_MODEL") or primary
    rest = os.environ.get(f"{key}_FALLBACKS", ",".join(fallbacks))
    return list(dict.fromkeys([first] + [m.strip() for m in rest.split(",") if m.strip()]))


def models() -> list[str]:
    """The /ask tool loop's chain (role 'agent')."""
    return role_models("agent")


SYSTEM = """You answer questions about the cost of CVN-79 (USS John F. Kennedy) for
financial managers. You work only from tool results; you have no other source.

Rules, all of them binding:
1. Every figure you state comes from a tool result in this conversation. Cite it
   inline in square brackets: a document as [file p.N], a transaction as
   [contract mod], a register entry as [G12] or [E-1], a query as [sql].
2. If the tools do not answer the question, say so, and name the gap that blocks
   it if one does (lookup_register finds gaps by id).
3. Contract obligations are federal_action_obligation summed per action. Never
   sum total_dollars_obligated; it is a running total.
4. N00024-09-C-2116 (construction preparation) and N00024-16-C-2116 are
   different contracts. Only the first is CVN-79.
5. Three cost ceilings are in circulation and all three are correct for their
   own purpose. Never call one of them "the" cost cap.
6. Be brief: a direct answer first, then the evidence. Use a small table when
   comparing figures.
7. Figures from a budget exhibit or any table come only from get_exhibit_cells,
   with the unit it returns. search_documents locates the page and its table ids;
   never quote a number from search text. Cite a cell as [file p.N table_id rRcC].
   A cell whose unit is UNKNOWN is stated with that caveat, never converted.
Your answer is a lead for a person to verify, not a reportable figure."""

TOOLS = [
    {"type": "function", "function": {
        "name": "search_documents",
        "description": "Search the CVN-79 document corpus (budget exhibits, SARs, GAO and "
                       "CRS reports, statute) to LOCATE pages. Returns file, page and, on "
                       "pages holding a table, the table ids with figures masked: read "
                       "those figures with get_exhibit_cells.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string"}, "k": {"type": "integer", "default": 6}},
            "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "get_exhibit_cells",
        "description": "Read numeric cells from the lossless PDF table store (budget "
                       "exhibits P-1, P-5, P-5c, P-8a, P-10, P-35, P-40 and other tables). "
                       "Each cell has its verbatim value, row label, column header chain, "
                       "unit and citation. Give at least one filter.",
        "parameters": {"type": "object", "properties": {
            "exhibit": {"type": "string", "description": "e.g. P-5c, P-40"},
            "line_item": {"type": "string", "description": "4-digit P-1 line item, e.g. 2001"},
            "fiscal_year": {"type": "string", "description": "4-digit FY in the column header"},
            "row_contains": {"type": "string", "description": "substring of the row label"},
            "table_id": {"type": "string", "description": "from search_documents"},
            "page": {"type": "integer"},
            "limit": {"type": "integer", "default": 60}}}}},
    {"type": "function", "function": {
        "name": "find_transactions",
        "description": "Filter the prime contract transactions (both CVN-79 contracts). "
                       "Returns matching rows, the count and the exact obligation sum.",
        "parameters": {"type": "object", "properties": {
            "contract": {"type": "string", "description": "N0002409C2116 or N0002415C2114"},
            "fiscal_year": {"type": "string"},
            "action_type": {"type": "string"},
            "text": {"type": "string", "description": "substring in any field"},
            "largest_first": {"type": "boolean"},
            "limit": {"type": "integer", "default": 15}}}}},
    {"type": "function", "function": {
        "name": "lookup_register",
        "description": "Look up a gap (G1-G65) or a variance (E-1 to E-16) by id, or list "
                       "them with id 'gaps' or 'variances'.",
        "parameters": {"type": "object", "properties": {"id": {"type": "string"}},
                       "required": ["id"]}}},
    {"type": "function", "function": {
        "name": "get_facts",
        "description": "Curated program facts. topic is one of: headline, ceilings, "
                       "anchor_chain, attribution, tieout, pipeline.",
        "parameters": {"type": "object", "properties": {"topic": {"type": "string"}},
                       "required": ["topic"]}}},
    {"type": "function", "function": {
        "name": "run_sql",
        "description": "One read-only Databricks SQL SELECT over these tables only: "
                       + ", ".join(live.allowed_tables().values())
                       + ". Results are capped at 200 rows. Use only when the other tools "
                         "cannot answer.",
        "parameters": {"type": "object", "properties": {"sql": {"type": "string"}},
                       "required": ["sql"]}}},
]


# --------------------------------------------------------------------- tools
def _clip(obj) -> str:
    s = json.dumps(obj, default=str, ensure_ascii=False)
    return s if len(s) <= MAX_TOOL_CHARS else s[:MAX_TOOL_CHARS] + '..."(truncated)"'


# A figure: optional sign, $, parens, digits with commas/decimals. Four-digit years
# (19xx/20xx) and footnote markers stay, so the passage still says what it is about.
_FIGURE = re.compile(r"\(?-?\$?\d[\d,]*(?:\.\d+)?\)?")
_YEAR = re.compile(r"^\(?(19|20)\d{2}\)?$")


def mask_figures(text: str) -> str:
    return _FIGURE.sub(lambda m: m.group(0) if _YEAR.match(m.group(0)) or len(
        m.group(0).strip("()")) <= 2 else "#", text or "")


def _page_tables() -> dict[tuple[str, int], list[dict]]:
    """(artifact_id, page) -> the tables the store extracted there, from the
    shipped exhibit index, so locating works with no warehouse."""
    idx: dict[tuple[str, int], list[dict]] = {}
    for r in explore._file("exhibits").get("rows", []):
        idx.setdefault((r["artifact_id"], int(r["page"])), []).append(
            {"table_id": r["table_id"], "exhibits": r.get("exhibits") or []})
    return idx


def t_search_documents(kb, query: str, k: int = 6):
    """Locate pages. Chunk text is a pointer, not a source of figures: on a page
    holding an extracted table the figures are masked and the table ids returned."""
    if kb is None or not getattr(kb, "available", False):
        return {"error": "document search is not available in this deployment"}, []
    hits = kb.search(query, k=max(1, min(int(k or 6), 10)))
    tables = _page_tables()
    out, cites = [], []
    for h in hits:
        # KnowledgeBase hits carry filename, page and a ready citation string.
        label = h.get("citation") or f"{h.get('filename')} p.{h.get('page')}"
        on_page = tables.get((h.get("artifact_id"), int(h.get("page") or 0)), [])
        text = (h.get("text") or "")[:700]
        hit = {"cite": label, "grade": h.get("grade"), "page": h.get("page"),
               "filename": h.get("filename")}
        if on_page or h.get("exhibits"):
            hit |= {"kind": "table_page", "text": mask_figures(text),
                    "table_ids": [t["table_id"] for t in on_page],
                    "exhibits": sorted({e for t in on_page for e in t["exhibits"]}
                                       | set(h.get("exhibits") or [])),
                    "read_with": "get_exhibit_cells(table_id=...) or (page=..., exhibit=...)"}
        else:
            hit |= {"kind": "prose", "text": text}
        out.append(hit)
        cites.append({"kind": "document", "label": label})
    return {"hits": out}, cites


_EXH = re.compile(r"^P-\d{1,2}[a-z]?$", re.I)
_D4 = re.compile(r"^\d{4}$")


def t_get_exhibit_cells(exhibit=None, line_item=None, fiscal_year=None, row_contains=None,
                        table_id=None, page=None, limit=60):
    """Numeric body cells from the cell store, each with its coordinate and unit.
    The unit is the claim ledger's (reader exhibit/0.3 resolve_unit), so the agent
    and the Reader cannot disagree on it; the printed headers come back too."""
    where, params = ["c.value_kind = 'number'", "NOT c.is_header", "c.col_idx > 0"], {}
    if exhibit:
        if not _EXH.match(str(exhibit).strip()):
            return {"error": f"exhibit must have the form P-5c or P-40, not {exhibit!r}"}, []
        params["exh"] = "(?i)\\bExhibit " + re.escape(str(exhibit).strip()) + "\\b"
        where.append("t.title_block RLIKE :exh")
    if line_item:
        if not _D4.match(str(line_item).strip()):
            return {"error": "line_item is a 4-digit P-1 line number"}, []
        params["bli"] = "Line Item Number / Title:\\s*" + str(line_item).strip() + "\\b"
        where.append("t.title_block RLIKE :bli")
    if fiscal_year:
        if not _D4.match(str(fiscal_year).strip()):
            return {"error": "fiscal_year is 4 digits, e.g. 2027"}, []
        params["fy"] = "FY\\s?" + str(fiscal_year).strip() + "\\b"
        where.append("c.col_header RLIKE :fy")
    if row_contains:
        params["rc"] = "%" + str(row_contains)[:80] + "%"
        where.append("c.row_header ILIKE :rc")
    if table_id:
        params["tid"] = str(table_id)[:60]
        where.append("t.table_id = :tid")
    if page is not None:
        try:
            params["pg"] = int(page)
        except (TypeError, ValueError):
            return {"error": "page is an integer"}, []
        where.append("t.page = :pg")
    if not params:
        return {"error": "give at least one of exhibit, line_item, fiscal_year, "
                          "row_contains, table_id, page"}, []
    n = max(1, min(int(limit or 60), 200))
    st = live.status()
    if not st["live"]:
        idx = explore._file("exhibits").get("rows", [])
        hits = [r for r in idx
                if (not table_id or r["table_id"] == table_id)
                and (page is None or int(r["page"]) == params.get("pg"))
                and (not exhibit or re.search(params["exh"], r.get("title") or ""))][:20]
        return {"error": "cell values need the live cell store: " + st["reason"],
                "tables": [{k: r.get(k) for k in ("table_id", "filename", "page", "exhibits")}
                           for r in hits],
                "note": "Name the table and page; do not state its figures."}, []
    sql = ("SELECT t.table_id, t.filename, t.page, t.extractor, t.title_block, "
           "c.row_idx, c.col_idx, c.value, c.row_header, c.col_header, "
           "coalesce(k.unit, 'UNKNOWN') AS unit "
           f"FROM {live.fqn('pdf_tables')} t JOIN {live.fqn('pdf_cells')} c USING (table_id) "
           f"LEFT JOIN {live.fqn('claim')} k ON k.claim_id = "
           "concat(t.table_id, ':r', c.row_idx, 'c', c.col_idx) AND k.superseded_by IS NULL "
           "WHERE " + " AND ".join(where) +
           " ORDER BY t.table_id, c.row_idx, c.col_idx")
    try:
        _cols, rows = live.query(sql, params, row_limit=n + 1)
    except live.LiveError as exc:
        return {"error": str(exc)}, []
    out, cites = [], []
    for r in rows[:n]:
        try:
            title = json.loads(r.get("title_block") or "[]")
        except ValueError:
            title = []
        cite = f"{r['filename']} p.{r['page']} {r['table_id']} r{r['row_idx']}c{r['col_idx']}"
        out.append({"cite": cite, "value": r["value"], "unit": r["unit"],
                    "row": r["row_header"], "column": r["col_header"],
                    "title": " | ".join(title[:4]),
                    "reconstructed_headers": r["extractor"] != "pdfplumber-lines/v1"})
        cites.append({"kind": "exhibit_cell", "label": cite})
    return {"cells": out, "shown": len(out), "truncated": len(rows) > n,
            "source": "PDF cell store (pdfplumber), unit from the claim ledger"}, cites[:12]


def t_find_transactions(contract=None, fiscal_year=None, action_type=None, text=None,
                        largest_first=False, limit=15):
    f = {k: v for k, v in {"award_id_piid": contract, "action_date_fiscal_year": fiscal_year,
                           "action_type": action_type}.items() if v}
    r = explore.query("transactions", q=text or "", filters=f,
                      sort="federal_action_obligation" if largest_first else "action_date",
                      desc=bool(largest_first), size=max(1, min(int(limit or 15), 40)))
    keep = ["award_id_piid", "modification_number", "action_date", "action_type",
            "federal_action_obligation", "transaction_description"]
    rows = [{k: x[k] for k in keep} for x in r["rows"]]
    cites = [{"kind": "transaction",
              "label": f"{x['award_id_piid']} {x['modification_number']} {x['action_date']}"}
             for x in rows[:8]]
    return {"matching_rows": r["total"], "obligation_sum": r["sum"],
            "shown": len(rows), "rows": rows,
            "source": "USAspending prime transactions, extract " + str(r["as_of"])}, cites


def t_lookup_register(id: str):
    key = (id or "").strip().upper()
    g, v = data.get("gaps") or {}, data.get("variances") or {}
    if key == "GAPS":
        return {"gaps": [{k: r.get(k) for k in ("id", "title", "status", "executor",
                                                 "closability", "exposure_usd_m")}
                         for r in g.get("rows", []) if not r.get("closed")]}, \
            [{"kind": "register", "label": "gap register"}]
    if key == "VARIANCES":
        return {"variances": [{k: r.get(k) for k in ("id", "status", "title")}
                              for r in v.get("rows", [])]}, \
            [{"kind": "register", "label": "variance register"}]
    for r in g.get("rows", []) + v.get("rows", []):
        if str(r.get("id", "")).upper() == key:
            return r, [{"kind": "register", "label": r["id"]}]
    return {"error": f"no register entry {id}"}, []


def t_get_facts(topic: str):
    t = (topic or "").lower()
    src = {"headline": lambda: data.get("program"),
           "ceilings": lambda: (data.get("cap_history") or {}).get("three_ceilings"),
           "anchor_chain": lambda: data.get("anchor_chain"),
           "attribution": lambda: data.get("attribution"),
           "tieout": lambda: explore.extract("tieout"),
           "pipeline": lambda: explore.extract("pipeline")}
    if t not in src:
        return {"error": f"unknown topic {topic}; one of {sorted(src)}"}, []
    return src[t](), [{"kind": "facts", "label": t}]


def t_run_sql(sql: str):
    st = live.status()
    if not st["live"]:
        return {"error": "SQL is not available: " + st["reason"]}, []
    try:
        stmt = live.guard(sql)
    except ValueError as exc:
        return {"error": f"rejected: {exc}"}, []
    try:
        cols, rows = live.query(stmt, row_limit=200)
    except live.LiveError as exc:
        return {"error": str(exc)}, []
    return {"columns": cols, "rows": rows, "n": len(rows)}, [{"kind": "query", "label": sql}]


def run_tool(name: str, args: dict, kb=None):
    fns = {"search_documents": lambda a: t_search_documents(kb, **a),
           "get_exhibit_cells": lambda a: t_get_exhibit_cells(**a),
           "find_transactions": lambda a: t_find_transactions(**a),
           "lookup_register": lambda a: t_lookup_register(**a),
           "get_facts": lambda a: t_get_facts(**a),
           "run_sql": lambda a: t_run_sql(**a)}
    if name not in fns:
        return {"error": f"unknown tool {name}"}, []
    try:
        return fns[name](args or {})
    except TypeError as exc:
        return {"error": f"bad arguments for {name}: {exc}"}, []


# --------------------------------------------------------------------- model
def _call_model(endpoint: str, body: dict) -> dict:
    from databricks.sdk import WorkspaceClient
    return WorkspaceClient().api_client.do(
        "POST", f"/serving-endpoints/{endpoint}/invocations", body=body)


def _text(content) -> str:
    """Message content is a string, or a list of parts on reasoning models."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(p.get("text", "") for p in content
                       if isinstance(p, dict) and p.get("type") == "text")
    return ""


def ask(question: str, history: list[dict] | None = None, kb=None, call=None) -> dict:
    call = call or _call_model
    t0 = time.time()
    msgs = [{"role": "system", "content": SYSTEM}]
    for h in (history or [])[-8:]:
        if h.get("role") in ("user", "assistant") and isinstance(h.get("content"), str):
            msgs.append({"role": h["role"], "content": h["content"][:4000]})
    msgs.append({"role": "user", "content": question[:4000]})

    trace, cites, errors = [], [], []
    for model in models():
        m_msgs = list(msgs)
        try:
            for _step in range(MAX_STEPS):
                r = call(model, {"messages": m_msgs, "tools": TOOLS, "max_tokens": 1800})
                msg = r["choices"][0]["message"]
                tcs = msg.get("tool_calls") or []
                if not tcs:
                    return _done(_text(msg.get("content")), model, cites, trace, t0)
                m_msgs.append(msg)
                for tc in tcs:
                    name = tc["function"]["name"]
                    try:
                        args = json.loads(tc["function"].get("arguments") or "{}")
                    except ValueError:
                        args = {}
                    res, c = run_tool(name, args, kb)
                    cites.extend(c)
                    trace.append({"tool": name, "args": args,
                                  "ok": not (isinstance(res, dict) and "error" in res),
                                  "note": res.get("error") if isinstance(res, dict) else None})
                    m_msgs.append({"role": "tool", "tool_call_id": tc["id"],
                                   "content": _clip(res)})
            m_msgs.append({"role": "user", "content": "Answer now from what you have."})
            r = call(model, {"messages": m_msgs, "max_tokens": 1500})
            return _done(_text(r["choices"][0]["message"].get("content")), model,
                         cites, trace, t0)
        except Exception as exc:  # noqa: BLE001 - next model, reason kept
            errors.append(f"{model}: {str(exc)[:240]}")
            continue

    # No model reachable: answer with search hits, and say so.
    res, c = t_search_documents(kb, question, 6)
    return {"mode": "search-only", "answer": None, "hits": res.get("hits", []),
            "reason": "No reasoning model was reachable. " + " | ".join(errors),
            "citations": c, "trace": [], "model": None, "grade": "lead",
            "seconds": round(time.time() - t0, 1)}


def _done(text, model, cites, trace, t0) -> dict:
    seen, uniq = set(), []
    for c in cites:
        k = (c["kind"], c["label"])
        if k not in seen:
            seen.add(k)
            uniq.append(c)
    return {"mode": "agent", "answer": text, "citations": uniq, "trace": trace,
            "model": model, "grade": "lead", "seconds": round(time.time() - t0, 1),
            "data_mode": "live" if live.status()["live"] else "extract"}


__all__ = ["ask", "run_tool", "models", "TOOLS", "Decimal", "mask_figures"]
