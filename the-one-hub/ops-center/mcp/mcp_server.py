"""Air Carrier ops center, exposed over the Model Context Protocol.

Runnable two ways:
  python -m mcp_server                                   stdio, for a local agent
  uvicorn mcp_server:http_app --host 0.0.0.0 --port 8000 HTTP, as a Databricks App

Design rules carried from the ops center and enforced here:
  - every figure returned carries its tag, confidence and source
  - check_claim is the only route to a promotion decision, and it never
    promotes on its own: it returns a routing decision and the reason
  - no tool writes to a trusted table
"""
from __future__ import annotations

import json
import pathlib
import sys
from typing import Any

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.contracts import Claim, Coordinate, Tag, Zone
from core.policy.decisions import evaluate
from core.policy.gate import route
from ops.agents.challenger.run import challenge
from ops.agents.tieout.run import anchor_chain, residual_is_finding, two_axis_close

DATA = ROOT / "app" / "data"
SEED = ROOT / "seed"


def _json(name: str) -> Any:
    # name can come straight from a tool argument (get_table), so it must
    # resolve inside DATA: '../../x' would otherwise read any .json file.
    p = (DATA / f"{name}.json").resolve()
    if not p.is_relative_to(DATA.resolve()):
        return {}
    return json.loads(p.read_text()) if p.exists() else {}


def _yaml(name: str) -> Any:
    p = SEED / f"{name}.yaml"
    return yaml.safe_load(p.read_text()) if p.exists() else {}


# --------------------------------------------------------------- tool bodies
def list_tables() -> dict:
    """Every table the ops center serves, with a one-line description."""
    return {"tables": sorted(p.stem for p in DATA.glob("*.json")),
            "note": "Each table carries a 'source' field naming the document and "
                    "section it was transcribed or computed from."}


def get_table(name: str) -> dict:
    """One table by name. Returns its rows and its source attribution."""
    t = _json(name)
    if not t:
        return {"error": f"no table '{name}'", "available": list_tables()["tables"]}
    return t


def search_mechanisms(query: str, limit: int = 8) -> dict:
    """Search the mechanism store: rules about how carrier money works.

    A mechanism is not a figure. It is what tells an agent where to look, when
    a value is impossible, and why two layers differ. Query before interpreting
    any document.
    """
    q = query.lower()
    hits = []
    for src in ("layers", "asset", "industrial", "clue_map", "sources", "variances"):
        blob = _json(src)
        for line in json.dumps(blob, indent=1).splitlines():
            if q in line.lower() and len(line.strip()) > 40:
                hits.append({"store": src, "text": line.strip().strip('",')})
    dd = _yaml("decisions.index")
    for d in dd.get("decisions", []):
        if q in d.get("topic", "").lower():
            hits.append({"store": "decisions", "id": d["id"], "text": d["topic"],
                         "enforced": d.get("enforced")})
    return {"query": query, "hits": hits[:limit],
            "home": "ring0/RING0_CVN79.md, BACKGROUND.md and LOG.md Part I own the full text"}


def get_keyset(section: str = "") -> dict:
    """The selector registry: the identifiers that isolate this hull.

    Sections: ship, budget, contracts, collisions, vendor, ledger, scope_boundary.
    Read `collisions` before building any contract query.
    """
    ks = _yaml("keyset")
    if section:
        return {section: ks.get(section, f"no section '{section}'"),
                "sections": [k for k in ks if k != "source"]}
    return ks


def exhibit_hazards(exhibit: str = "") -> dict:
    """Known traps for a budget or acquisition exhibit.

    Every extraction from an exhibit inherits these. Checking them is cheaper
    than rediscovering them: two of the three recorded errors in this program
    are hazards on this list.
    """
    ex = _yaml("exhibits").get("exhibits", {})
    if exhibit:
        return {exhibit: ex.get(exhibit, f"no registry entry for '{exhibit}'"),
                "known": list(ex)}
    return {"exhibits": ex}


def rank_gaps(limit: int = 10, free_only: bool = False) -> dict:
    """The discovery queue, ranked on exposure x ignorance x closability.

    Discovery ranks differently from publication. High closability gets worked
    because it is free; high exposure with low closability becomes the access
    ask rather than the work queue.
    """
    g = _json("gaps")
    rows = [r for r in g.get("rows", []) if not r["closed"]]
    if free_only:
        rows = [r for r in rows if r["closability"] in ("zero_access", "query")]
    rows.sort(key=lambda r: -r["priority"])
    return {"ranking": g.get("ranking"), "open": len(rows),
            "rows": rows[:limit]}


def get_gap(gap_id: str) -> dict:
    """One gap with its type, executor, exposure and what it blocks."""
    for r in _json("gaps").get("rows", []):
        if r["id"].upper() == gap_id.upper():
            return r
    return {"error": f"no gap '{gap_id}'"}


def check_claim(hull: str, layer: str, element: str, period: str,
                value: float | None = None, tag: str = "UNKNOWN",
                confidence: float = 0.0, source_system: str | None = None,
                exhibit: str | None = None, column_header_chain: list | None = None,
                page_legends: list | None = None, neighborhood: str = "",
                notes: str = "") -> dict:
    """Evaluate a candidate figure against the decision log and the gate.

    This is the only route to a promotion decision, and it never promotes on
    its own. It returns the policy violations (each naming its D-number), the
    risk flags the challenger set, and the routing decision with its reason.
    """
    import datetime
    c = Claim(claim_id="adhoc", hull=hull, layer=layer, element=element, period=period,
              value=value, discovered_at=datetime.datetime.now(datetime.timezone.utc),
              tag=Tag[tag.upper()] if tag.upper() in Tag.__members__ else Tag.UNKNOWN,
              confidence=confidence, zone=Zone.RAW, source_system=source_system,
              notes=notes,
              coordinate=Coordinate("adhoc", exhibit=exhibit,
                                    column_header_chain=column_header_chain or [],
                                    page_legends=page_legends or [],
                                    neighborhood=neighborhood))
    for flag, tell in challenge(c, subject=hull):
        c.risk_flags.add(flag)
    violations = evaluate(c)
    r = route(c, violations)
    return {
        "decision": r.decision.value, "rule": r.rule, "reason": r.reason,
        "exposure_share": round(r.exposure_share, 4),
        "risk_flags": r.flags,
        "policy_violations": [{"decision": v.decision, "message": v.message} for v in violations],
        "tells": [t for _f, t in challenge(c, subject=hull)],
        "note": "A routing decision, not a promotion. A person or a deterministic "
                "rule acts on it. D13.",
    }


def challenge_text(text: str, subject: str = "CVN-79") -> dict:
    """Run the falsification vocabulary over a passage before trusting it.

    Catches the error classes already recorded: wrong platform, wrong hull,
    identifier collision, announcement-derived figures, unusable outlay fields.
    """
    import datetime
    c = Claim(claim_id="adhoc", hull=subject, layer="", element="", period="",
              discovered_at=datetime.datetime.now(datetime.timezone.utc),
              coordinate=Coordinate("adhoc", neighborhood=text), notes=text)
    tells = challenge(c, subject=subject)
    return {"subject": subject, "flags": sorted({f.value for f, _ in tells}),
            "tells": [{"flag": f.value, "why": t} for f, t in tells],
            "clean": not tells}


def tie_out(total: float, axis_a: dict, axis_b: dict) -> dict:
    """Deterministic reconciliation. No model.

    One axis closing is arithmetic. Two independent decompositions closing on
    the same total is evidence. A residual above the floor is a finding.
    """
    close = two_axis_close(total, axis_a, axis_b)
    resid = residual_is_finding(close.residual)
    return {"passed": close.passed, "detail": close.detail,
            "residual": round(close.residual, 6),
            "residual_verdict": resid.detail}


def check_anchor_chain(steps: list, expected_total: float) -> dict:
    """Each increment named and attributable, ending at the published total.

    steps: [[label, delta], ...]
    """
    res = anchor_chain([(s[0], float(s[1])) for s in steps], expected_total)
    return {"passed": res.passed, "detail": res.detail, "residual": round(res.residual, 6)}


def collection_requirement(lead: str, gap_id: str = "", target_document: str = "",
                           target_system: str = "", target_office: str = "",
                           period: str = "", account: str = "") -> dict:
    """Turn a lead into a Collection Requirement.

    A lead's only legitimate output. Not a figure: a specific actionable
    instruction naming what to retrieve, from where, for which period and
    account.
    """
    if not any([target_document, target_system, target_office]):
        return {"error": "a Collection Requirement must name a document, a system "
                         "or an office. A lead with no target is not a requirement."}
    return {"instruction": lead, "gap_id": gap_id or None,
            "target_document": target_document or None,
            "target_system": target_system or None,
            "target_office": target_office or None,
            "period": period or None, "account": account or None,
            "zone": "L", "note": "Enters as a graded lead. No join path to canonical data."}


def plan_gap(gap_id: str) -> dict:
    """What to do about a gap: candidate explanations and where each is settled.

    Returns Collection Requirements, never figures. A requirement with no named
    target does not come back, because the investigator drops it (D16). The plan
    is produced without a model here, which is the floor: the gap's own type
    decides the retrieval channel and its executor is the target. A model widens
    the hypothesis set in the pipeline; it is not needed for a plan to exist.
    """
    row = get_gap(gap_id)
    if "error" in row:
        return row

    from core.contracts import Gap, GapType
    from ops.agents.investigator.run import run as plan

    try:
        gt = GapType[row.get("type") or "DOCUMENT"]
    except KeyError:
        gt = GapType.DOCUMENT

    g = Gap(gap_id=row["id"], question=row.get("title") or row.get("note", ""),
            gap_type=gt, executor=row.get("executor", ""),
            exposure_usd_m=row.get("exposure_usd_m", 0.0),
            ignorance=row.get("ignorance", 0.5),
            closability=row.get("closability", "unknown"),
            decay_risk=row.get("decay", "unknown") or "unknown")

    wp = plan(g)
    return {
        "gap_id": g.gap_id,
        "question": g.question,
        "terminal": wp.is_empty,
        "requirements": [
            {"cr_id": r.cr_id, "instruction": r.instruction,
             "target_document": r.target_document, "target_system": r.target_system,
             "target_office": r.target_office, "period": r.period,
             "account": r.account, "exposure_usd_m": r.exposure_usd_m}
            for r in wp.requirements
        ],
        "hypotheses": [{"statement": h.statement, "mechanisms": h.mechanism_ids,
                        "prior": h.prior} for h in wp.hypotheses],
        "dropped": [{"statement": h.statement, "because": h.rejected_because}
                    for h in wp.dropped],
        "notes": wp.notes,
        "rule": "A lead's only legitimate output is a Collection Requirement. "
                "Never a figure, and never a gap assigned back to the sponsor.",
    }


def next_work(limit: int = 5) -> dict:
    """The queue with a plan attached to each row. One call answers 'what now'.

    Separates the free work from the access ask, because the two are different
    conversations: the first is effort, the second needs a sponsor, and doing
    the free work first is what makes the second ask persuasive.
    """
    q = rank_gaps(limit=limit)
    out = []
    for r in q["rows"]:
        pl = plan_gap(r["id"])
        out.append({"id": r["id"], "title": r["title"], "priority": r["priority"],
                    "closability": r["closability"], "type": r["type"],
                    "first_step": (pl.get("requirements") or [{}])[0].get("instruction"),
                    "target": next((v for k, v in (pl.get("requirements") or [{}])[0].items()
                                    if k.startswith("target_") and v), None)})
    FREE = ("zero_access", "query")
    free = [r for r in out if r["closability"] in FREE]
    return {"open": q["open"], "work_now": free,
            "access_ask": [r for r in out if r["closability"] not in FREE],
            "rule": "Work the free queue first. An access request lands better "
                    "after the work that needed no access is visibly done."}


def search_corpus(query: str, k: int = 6, authoritative_only: bool = True,
                  artifact_id: str | None = None, figures_only: bool = False) -> dict:
    """Search the document knowledge base. Every hit carries its page citation.

    authoritative_only defaults to TRUE and should stay true for anything that
    could become a measure. With it off, the analyst's own dossier outranks the
    documents it summarises on nearly every query, because a summary written in
    the asker's vocabulary always out-matches its source. Citing the summary is
    how a lead silently becomes a figure, which D16 exists to prevent.

    figures_only restricts to chunks that actually contain dollar amounts.
    """
    from ops.ingest.search import KnowledgeBase
    kb = KnowledgeBase()
    if not kb.available:
        return {"error": "no knowledge base built",
                "fix": "python3 ops/entrypoints/ingest_job.py"}
    hits = kb.search(query, k=k, grade="AUTHORITATIVE" if authoritative_only else None,
                     artifact_id=artifact_id, with_money=figures_only)
    return {
        "query": query,
        "authoritative_only": authoritative_only,
        "hits": [{"citation": h["citation"], "grade": h["grade"], "zone": h["zone"],
                  "page": h["page"], "artifact_id": h["artifact_id"],
                  "legends": h["legends"], "exhibits": h["exhibits"],
                  "text": h["text"][:1200], "score": h["score"]} for h in hits],
        "rule": "A passage is a lead until it is read in place. Open the cited "
                "page before using any figure from it, and capture the full "
                "coordinate: exhibit, column header chain, row label, page, "
                "and every legend printed on that page.",
    }


def corpus_status() -> dict:
    """What the knowledge base actually holds, and what it does not."""
    import json as _json

    from ops.ingest.search import KnowledgeBase
    out = {"index": KnowledgeBase().stats()}
    man = ROOT / "corpus" / "MANIFEST.json"
    if man.exists():
        m = _json.loads(man.read_text())
        out["corpus"] = {"artifacts": m["count"],
                         "bytes": m["bytes"],
                         "by_bucket": m["by_bucket"],
                         "by_route": m["by_route"]}
        out["note"] = ("route 'table' artifacts are structured data, queried with "
                       "SQL rather than embedded. route 'asset' are images. "
                       "Neither is in the index, by design.")
    sm = ROOT / "app" / "data" / "kb" / "summary.json"
    if sm.exists():
        out["built"] = _json.loads(sm.read_text())
    return out


TOOLS = [search_corpus, corpus_status,
         list_tables, get_table, search_mechanisms, get_keyset, exhibit_hazards,
         rank_gaps, get_gap, plan_gap, next_work, check_claim, challenge_text,
         tie_out, check_anchor_chain, collection_requirement]


# ------------------------------------------------------------------ servers
def build():
    """Build the FastMCP server. Imported lazily so the module stays testable
    without the mcp package installed."""
    from mcp.server.fastmcp import FastMCP
    srv = FastMCP("aircarrier-ops")
    for fn in TOOLS:
        srv.tool()(fn)
    return srv


def http_app():
    return build().streamable_http_app()


if __name__ == "__main__":
    build().run()
