"""The analyst's library: what it can read, and how it reads it.

Everything here is SQL over Unity Catalog through warehouse.run, with values
bound as parameters. Three jobs:

  * load the Knowledge the investigator starts from (keyset contracts and their
    hull verdicts, negative vocabulary, vendors, budget-line links, the
    accounts that fund CVN-79 awards, program codes);
  * implement investigator.Sources (amount matches, document search, graph
    co-occurrence, mechanism rules);
  * answer the catalog tools: list sources, search documents, trace an entity.
"""
from __future__ import annotations

import json
import re
import threading
import time

from core import catalog
from core.analyst import loa, sources
from mcp_aircarrier_analyst import investigator as inv
from mcp_aircarrier_analyst import warehouse
from mcp_aircarrier_analyst.warehouse import render as Q

S = catalog.STORE_SCHEMA
NODES, EDGES = f"{S}.aircarrier_kg_nodes", f"{S}.aircarrier_kg_edges"
PAGES, CELLS, TABLES = f"{S}.aircarrier_pdf_pages", f"{S}.aircarrier_pdf_cells", f"{S}.aircarrier_pdf_tables"
MECH, SUBAWARDS = f"{S}.aircarrier_mechanism", f"{S}.aircarrier_src_2114_subawards"
REGISTRY = f"{S}.aircarrier_src_registry"
TTL = 900

CATEGORIES = (
    ("regulation", r"5200\.45|DCMA_MAN|SUPSHIP"),
    ("budget_justification", r"SCN_Book|J-?Book"),
    ("program_report", r"\bM?SAR\b|_SAR_|MSAR"),
    ("oversight_and_research", r"^gao|RS20643|NPS-"),
    ("spending_records", r"\.csv$"),
    ("data_dictionary", r"Crosswalk|readme"),
    ("working_notes", r"\.md$"),
    ("imagery", r"\.(jpg|jpeg|png)$"),
)


def category(filename: str) -> str:
    for name, pat in CATEGORIES:
        if re.search(pat, filename or "", re.I):
            return name
    return "other"


def _like(term: str) -> str:
    return "%" + re.sub(r"([%_\\])", r"\\\1", term) + "%"


def _props(s) -> dict:
    try:
        return json.loads(s) if isinstance(s, str) and s else (s or {})
    except ValueError:
        return {}


# ------------------------------------------------------------------ knowledge

_lock = threading.Lock()
_cache: dict = {}


def load_knowledge() -> inv.Knowledge:
    k = inv.Knowledge()
    rels: dict[str, list] = {}
    for r in warehouse.run(Q("SELECT src, rel, dst, props FROM {edges} "
                             "WHERE src LIKE 'contract:%' OR src LIKE 'bli:%' OR src LIKE 'program_element:%'",
                             tables={"edges": EDGES})):
        rels.setdefault(r["src"], []).append((r["rel"], r["dst"], _props(r["props"])))
    for r in warehouse.run(Q("SELECT node_id, node_type, label, props, grade FROM {nodes} "
                             "WHERE node_type IN ('contract','negative_term','vendor','artifact')",
                             tables={"nodes": NODES})):
        p = _props(r["props"])
        nid = r["node_id"]
        if r["node_type"] == "contract":
            k.contracts[inv.norm_piid(nid.split(":", 1)[1])] = {"label": r["label"], "props": p, "rels": rels.get(nid, [])}
        elif r["node_type"] == "negative_term":
            k.neg_terms[nid.split(":", 1)[1]] = p.get("why", "")
        elif r["node_type"] == "vendor":
            k.vendors[nid.split("CAGE-")[-1]] = {"name": r["label"], **p}
        elif r["node_type"] == "artifact" and p.get("bucket") != "imagery" and not p.get("superseded"):
            k.artifacts.append({"artifact_id": nid.split(":", 1)[1], "document": r["label"], "grade": r["grade"],
                                "category": category(r["label"]), "establishes": p.get("establishes", ""),
                                "pages": p.get("pages")})
    k.budget_links = {s: [(a, b) for a, b, _ in v] for s, v in rels.items() if not s.startswith("contract:")}
    for piid, tbl in sources.TX_TABLES.items():
        for r in warehouse.run(Q("SELECT DISTINCT treasury_accounts_funding_this_award a, "
                                 "dod_acquisition_program_code c, dod_acquisition_program_description d, "
                                 "product_or_service_code s FROM {tx} WHERE award_id_piid = ?",
                                 tables={"tx": tbl}), [piid]):
            for t in loa.split_list(r["a"]):
                k.cvn79_tas.setdefault(t, [])
                if piid not in k.cvn79_tas[t]:
                    k.cvn79_tas[t].append(piid)
            if r["c"]:
                k.program_codes[r["c"]] = r["d"] or ""
            if r["s"]:
                k.psc_codes.add(r["s"])
    for r in warehouse.run(Q("SELECT dst, count(DISTINCT src) n FROM {edges} WHERE rel = 'mentions' "
                             "AND dst LIKE 'hull:%' AND src LIKE 'page:%' GROUP BY dst",
                             tables={"edges": EDGES})):
        k.hull_baseline[r["dst"]] = int(r["n"])
    for piid, tbl in sources.FC_TABLES.items():
        for r in warehouse.run(Q("SELECT DISTINCT treasury_account_symbol t FROM {fc} WHERE award_id_piid = ?",
                                 tables={"fc": tbl}), [piid]):
            k.cvn79_tas.setdefault(r["t"], [])
            if piid not in k.cvn79_tas[r["t"]]:
                k.cvn79_tas[r["t"]].append(piid)
    return k


def knowledge() -> inv.Knowledge:
    with _lock:
        hit = _cache.get("k")
        if hit and time.time() - hit[0] < TTL:
            return hit[1]
    k = load_knowledge()
    with _lock:
        _cache["k"] = (time.time(), k)
    return k


# ------------------------------------------------------------------ sources

TX_OUT = ("contract_transaction_unique_key", "award_id_piid", "modification_number", "action_date",
          "federal_action_obligation", "transaction_description", "treasury_accounts_funding_this_award",
          "cage_code", "recipient_name", "dod_acquisition_program_code", "product_or_service_code", "_row_num")
FC_OUT = ("award_id_piid", "submission_period", "treasury_account_symbol", "object_class_code",
          "program_activity_code", "transaction_obligated_amount", "_row_num")
SUB_OUT = ("prime_award_piid", "subawardee_name", "subawardee_uei", "subaward_number", "subaward_amount",
           "subaward_action_date", "subaward_description", "_row_num")


# Subaward lookups: one constant statement per search key, no WHERE assembly.
SUB_SQL = {
    "uei": "SELECT {cols} FROM {subs} WHERE subawardee_uei = ? OR subawardee_parent_uei = ? LIMIT 20",
    "name": "SELECT {cols} FROM {subs} WHERE subawardee_name ILIKE ? OR subawardee_parent_name ILIKE ? LIMIT 20",
    "amount": ("SELECT {cols} FROM {subs} "
               "WHERE CAST(subaward_amount AS DECIMAL(20,2)) = CAST(? AS DECIMAL(20,2)) LIMIT 20"),
}


class SqlSources:
    """investigator.Sources over Unity Catalog."""

    def fpds_by_amount(self, amount: str) -> list[dict]:
        out = []
        for tbl in sources.TX_TABLES.values():
            sql = Q("SELECT {cols}, ? AS _table FROM {tx} "
                    "WHERE CAST(federal_action_obligation AS DECIMAL(20,2)) = CAST(? AS DECIMAL(20,2)) LIMIT 20",
                    tables={"tx": tbl}, cols={"cols": TX_OUT})
            out += warehouse.run(sql, [tbl.split(".")[-1], amount])
        return out

    def filec_by_amount(self, amount: str) -> list[dict]:
        out = []
        for tbl in sources.FC_TABLES.values():
            sql = Q("SELECT {cols}, ? AS _table FROM {fc} "
                    "WHERE CAST(transaction_obligated_amount AS DECIMAL(20,2)) = CAST(? AS DECIMAL(20,2)) LIMIT 20",
                    tables={"fc": tbl}, cols={"cols": FC_OUT})
            out += warehouse.run(sql, [tbl.split(".")[-1], amount])
        return out

    def subawards(self, uei: str = "", name: str = "", amount: str = "") -> list[dict]:
        if uei:
            key, p = "uei", [uei, uei]
        elif name:
            key, p = "name", [_like(name), _like(name)]
        elif amount:
            key, p = "amount", [amount]
        else:
            return []
        return warehouse.run(Q(SUB_SQL[key], tables={"subs": SUBAWARDS}, cols={"cols": SUB_OUT}), p)

    def exhibit_cells(self, values: list[str]) -> list[dict]:
        if not values:
            return []
        sql = Q("SELECT c.artifact_id, CAST(c.page AS STRING) page, c.row_header, c.col_header, c.value, "
                "t.title_block, t.filename FROM {cells} c LEFT JOIN {tables} t ON t.table_id = c.table_id "
                "WHERE c.value_num IS NOT NULL AND TRY_CAST(c.value_num AS DECIMAL(20,3)) IN ({marks}) LIMIT 20",
                tables={"cells": CELLS, "tables": TABLES},
                repeat={"marks": ("CAST(? AS DECIMAL(20,3))", len(values), ", ")})
        return warehouse.run(sql, list(values))

    def search_pages(self, term: str, limit: int = 8) -> list[dict]:
        sql = Q("SELECT artifact_id, filename, CAST(page AS INT) page, grade, "
                "substr(text, greatest(1, instr(upper(text), upper(?)) - 160), 420) AS snippet "
                "FROM {pages} WHERE text ILIKE ? ORDER BY CASE grade WHEN 'AUTHORITATIVE' THEN 0 ELSE 1 END, "
                "filename, page LIMIT {limit}",
                tables={"pages": PAGES}, ints={"limit": limit})
        return warehouse.run(sql, [term, _like(term)])

    def hull_mentions(self, page_ids: list[str]) -> dict[str, int]:
        if not page_ids:
            return {}
        sql = Q("SELECT dst, count(DISTINCT src) n FROM {edges} WHERE rel = 'mentions' "
                "AND dst LIKE 'hull:%' AND src IN ({marks}) GROUP BY dst",
                tables={"edges": EDGES}, repeat={"marks": ("?", len(page_ids), ", ")})
        return {r["dst"]: int(r["n"]) for r in warehouse.run(sql, page_ids)}

    def node_hull_mentions(self, node_id: str) -> dict[str, int]:
        sql = Q("WITH p AS (SELECT src AS page FROM {edges} WHERE dst = ? AND src LIKE 'page:%' "
                "UNION SELECT h.src FROM {edges} h JOIN {edges} t ON t.src = h.dst "
                "WHERE h.rel = 'has_table' AND t.dst = ?) "
                "SELECT e.dst, count(DISTINCT e.src) n FROM {edges} e JOIN p ON e.src = p.page "
                "WHERE e.rel = 'mentions' AND e.dst LIKE 'hull:%' GROUP BY e.dst",
                tables={"edges": EDGES})
        return {r["dst"]: int(r["n"]) for r in warehouse.run(sql, [node_id, node_id])}

    def mechanisms(self, terms: list[str], limit: int = 5) -> list[dict]:
        terms = [t for t in terms if t][:6]
        if not terms:
            return []
        params = [x for t in terms for x in (_like(t),) * 3]
        sql = Q("SELECT statement, consequence, citation, review_state FROM {mech} "
                "WHERE superseded_by IS NULL AND ({cond}) ORDER BY confidence DESC LIMIT {limit}",
                tables={"mech": MECH}, ints={"limit": limit},
                repeat={"cond": ("(statement ILIKE ? OR consequence ILIKE ? OR passage ILIKE ?)", len(terms), " OR ")})
        return warehouse.run(sql, params)


# ------------------------------------------------------------------ catalog tools

def list_sources(k: inv.Knowledge) -> dict:
    by: dict[str, list] = {}
    for a in k.artifacts:
        by.setdefault(a["category"], []).append({x: a[x] for x in ("document", "grade", "establishes", "pages")})
    tables = warehouse.run(Q("SELECT table_name, rows_in_source, source_locator FROM {registry}",
                             tables={"registry": REGISTRY}))
    return {
        "documents_by_category": by,
        "structured_sources": tables,
        "knowledge_graph": {"contracts": len(k.contracts), "negative_terms": len(k.neg_terms),
                            "vendors": len(k.vendors), "accounts_on_cvn79_awards": len(k.cvn79_tas),
                            "program_codes": k.program_codes},
        "skills": [{"skill": s.name, "runs_on": list(s.needs), "reads": s.reads} for s in inv.SKILLS],
        "not_loaded": ["Navy ERP / GL postings", "PIEE EDA conformed contracts (Section G)", "DFAS reports",
                       "Advana", "any internet source"],
        "grades": {"AUTHORITATIVE": "may support a figure after the claim gate",
                   "WORKING": "project notes: leads only", "ILLUSTRATION": "never evidence"},
    }


def search_documents(query: str, cat: str = "", limit: int = 10) -> dict:
    rows = SqlSources().search_pages(query, 60)
    hits = [{**r, "category": category(r["filename"])} for r in rows]
    if cat:
        hits = [h for h in hits if h["category"] == cat]
    return {"query": query, "n": len(hits), "hits": hits[:limit],
            "note": "Exact substring search over the full text of every loaded PDF page."}


def _resolve(entity: str) -> list[str]:
    e = entity.strip()
    p = inv.norm_piid(e)
    if inv.PIID_RE.fullmatch(e.upper()) or (len(p) == 13 and re.match(r"^[A-Z]", p)):
        return [f"contract:{inv.dashed_piid(p)}"]
    m = re.fullmatch(r"(?i)CVN?[\s-]*(\d{2})", e)
    if m:
        return [f"hull:{'CV' if e.upper().startswith('CV-') or e.upper().startswith('CV ') else 'CVN'}-{m.group(1)}"]
    if re.fullmatch(r"[0-9A-Z]{5}", e.upper()):
        return [f"vendor:CAGE-{e.upper()}", f"bli:{e}"]
    if re.fullmatch(r"\d{4}", e):
        return [f"bli:{e}"]
    if ":" in e:
        return [e]
    return _by_label(e)


def _by_label(e: str) -> list[str]:
    rows = warehouse.run(Q("SELECT node_id FROM {nodes} WHERE label ILIKE ? OR node_id ILIKE ? LIMIT 5",
                           tables={"nodes": NODES}), [_like(e), _like(e)])
    return [r["node_id"] for r in rows]


def trace_entity(entity: str) -> dict:
    out = []
    ids = _resolve(entity)
    found = warehouse.run(Q("SELECT node_id FROM {nodes} WHERE node_id IN ({marks})",
                            tables={"nodes": NODES}, repeat={"marks": ("?", len(ids), ", ")}), ids) \
        if ids else []
    if not found:
        ids = _by_label(entity.strip())
    for nid in ids:
        node = warehouse.run(Q("SELECT node_id, node_type, label, props, grade, source_locator FROM {nodes} "
                               "WHERE node_id = ?", tables={"nodes": NODES}), [nid])
        if not node:
            continue
        n = node[0]
        links = warehouse.run(Q(
            "SELECT src, rel, dst, props, evidence_text FROM {edges} WHERE (src = ? OR dst = ?) "
            "AND NOT (src LIKE 'page:%' AND rel = 'mentions') LIMIT 60", tables={"edges": EDGES}), [nid, nid])
        docs = warehouse.run(Q(
            "SELECT split(e.src, ':')[1] artifact_id, max(p.filename) document, count(*) pages, "
            "slice(sort_array(collect_set(CAST(p.page AS INT))), 1, 8) sample_pages FROM {edges} e "
            "JOIN {pages} p ON e.src = concat('page:', p.artifact_id, ':', lpad(CAST(p.page AS STRING), 4, '0')) "
            "WHERE e.dst = ? AND e.rel = 'mentions' GROUP BY 1 ORDER BY pages DESC LIMIT 15",
            tables={"edges": EDGES, "pages": PAGES}), [nid])
        out.append({"node": {**n, "props": _props(n["props"])},
                    "links": [{"from": r["src"], "rel": r["rel"], "to": r["dst"], "props": _props(r["props"]),
                               "evidence": (r.get("evidence_text") or "")[:200]} for r in links],
                    "mentioned_in": docs,
                    "hull_cooccurrence": SqlSources().node_hull_mentions(nid)})
    return {"entity": entity, "resolved": [o["node"]["node_id"] for o in out], "results": out,
            "note": "Knowledge graph edges are navigation, never a figure (D27)."}
