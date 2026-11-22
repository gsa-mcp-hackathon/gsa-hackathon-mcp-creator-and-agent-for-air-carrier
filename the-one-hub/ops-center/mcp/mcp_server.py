"""Air Carrier ops center, exposed over the Model Context Protocol.

Runnable two ways, from the ops-center folder:
  python mcp/mcp_server.py   stdio, for a local agent
  python mcp/mcp_server.py   stateless streamable HTTP at /mcp when DATABRICKS_APP_PORT
                             (or PORT) is set: the Databricks App mcp-aircarrier-hub,
                             deployed from the-one-hub/ops-center (app.yaml there)

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
from typing import Annotated, Any, Literal

import yaml
from pydantic import Field

try:  # the tool bodies run without the mcp package; only the MCP surface needs it
    from mcp.server.fastmcp.exceptions import ToolError
except ImportError:  # pragma: no cover
    class ToolError(Exception):
        """Stand-in so the module imports where mcp is not installed."""

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))  # source_notice

from hub_models import (
    AnchorChainResult,
    ChallengeTextResult,
    CheckClaimResult,
    CollectionRequirementResult,
    CorpusStatusResult,
    GapRow,
    HazardsResult,
    KeysetResult,
    MechanismsResult,
    NextWorkResult,
    PlanGapResult,
    RankGapsResult,
    SearchCorpusResult,
    TableListResult,
    TableResult,
    TieOutResult,
)

from core.contracts import Claim, Coordinate, Tag, Zone
from core.contracts.risk import RiskFlag
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
                notes: str = "", page: int | None = None,
                row_label: str | None = None) -> dict:
    """Evaluate a candidate figure against the decision log and the gate.

    This is the only route to a promotion decision, and it never promotes on
    its own. It returns the policy violations (each naming its D-number), the
    risk flags the challenger set, and the routing decision with its reason.

    The caller sets the tag, so a VERIFIED tag is taken as a claim about the
    figure, not as proof: without a source and a locator (a page for a
    document, a row label for a record) it carries a METHOD flag and goes to
    review.
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
                                    neighborhood=neighborhood, page=page,
                                    row_label=row_label or None))
    tells = challenge(c, subject=hull)
    if c.tag is Tag.VERIFIED and not (source_system and (page is not None or row_label)):
        tells.append((RiskFlag.METHOD,
                      ("VERIFIED asserted without a source and a locator: name the "
                       "source system and the page or record the figure was read from")))
    for flag, _tell in tells:
        c.risk_flags.add(flag)
    violations = evaluate(c)
    r = route(c, violations)
    return {
        "decision": r.decision.value, "rule": r.rule, "reason": r.reason,
        "exposure_share": round(r.exposure_share, 4),
        "risk_flags": r.flags,
        "policy_violations": [{"decision": v.decision, "message": v.message} for v in violations],
        "tells": [t for _f, t in tells],
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

    steps: [[label, delta], ...]. Deltas may be strings as printed; the check
    keeps them as exact decimals.
    """
    res = anchor_chain([(s[0], s[1]) for s in steps], expected_total)
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


# ------------------------------------------------------------- MCP surface
# The functions above are the Python API: the agents, the front center and the
# tests call them directly. The MCP surface below is what an agent sees. Each
# tool validates its arguments with Pydantic before the body runs, takes only
# scalars, enums and lists of strings (no dicts, no nullable unions: the
# Creator's portability rule, which keeps the schema readable by every model
# behind an AI gateway), raises ToolError instead of returning an error dict,
# and is marked read-only. Names carry a hub_ prefix so they cannot collide with
# another server's list_tables or get_table in a multi-server client.

SERVER_NAME = "mcp-aircarrier-hub"
INSTRUCTIONS = (
    "The CVN-79 One Hub: the governed stores, the gap queue and the deterministic checks. "
    "Start a cost question with hub_search_mechanisms and hub_get_keyset (read the "
    "collisions section before any contract query). Check a candidate figure with "
    "hub_check_claim before treating it as a figure: it returns a routing decision, never "
    "a promotion. Reconcile with hub_tie_out and hub_check_anchor_chain; they use exact "
    "decimals and no model. A lead's only output is a Collection Requirement "
    "(hub_collection_requirement or hub_plan_gap). No tool writes anything."
)
READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True,
             "openWorldHint": False}

NUMBER = r"^-?\d{1,12}(\.\d{1,6})?$"
NUMBER_OR_EMPTY = r"^$|^-?\d{1,12}(\.\d{1,6})?$"
TableName = Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[a-z0-9_]+$",
                                 description="A table name from hub_list_tables, e.g. gaps.")]
GapId = Annotated[str, Field(min_length=2, max_length=4, pattern=r"^[Gg]\d{1,3}$",
                             description="A gap id, e.g. G14.")]
Amount = Annotated[str, Field(min_length=1, max_length=20, pattern=NUMBER,
                              description="An amount in $M as printed, e.g. 13409.970.")]
Labels = Annotated[list[Annotated[str, Field(max_length=120)]],
                   Field(min_length=1, max_length=40, description="One label per line.")]
Amounts = Annotated[list[Annotated[str, Field(max_length=20, pattern=NUMBER)]],
                    Field(min_length=1, max_length=40,
                          description="One amount in $M per label, in the same order.")]
Short = Annotated[str, Field(max_length=200)]
KeysetSection = Literal["", "ship", "budget", "contracts", "collisions", "vendor", "ledger",
                        "scope_boundary"]
TagName = Literal["VERIFIED", "DERIVED", "ESTIMATE", "UNKNOWN", "REJECTED"]


def _ok(result: dict) -> dict:
    """An answer, or a ToolError when the body reported one."""
    if isinstance(result, dict) and "error" in result:
        extra = {k: v for k, v in result.items() if k != "error"}
        raise ToolError(result["error"] + (f" {json.dumps(extra, default=str)}" if extra else ""))
    return result


def _pairs(labels: list[str], amounts: list[str], what: str) -> dict[str, str]:
    if len(labels) != len(amounts):
        raise ToolError(f"{what}: {len(labels)} labels but {len(amounts)} amounts; give one amount "
                        "per label, in the same order.")
    if len(set(labels)) != len(labels):
        raise ToolError(f"{what}: each label must be unique.")
    return dict(zip(labels, amounts, strict=True))


def hub_list_tables() -> TableListResult:
    """Every table the One Hub serves: program, cost_categories, funding_streams,
    obligations, contracts, gaps, variances, cap_history and more. Each carries a
    'source' field naming the document and section it comes from."""
    return list_tables()


def hub_get_table(name: TableName) -> TableResult:
    """One table with its rows and its source attribution, e.g. cost_categories
    (the P-5c decomposition) or cap_history (the statutory cap and its increments)."""
    table = _ok(get_table(name))
    # A few tables are stored as a bare list (timeline); every table answers
    # as an object, so the output schema holds for all of them.
    return {"rows": table} if isinstance(table, list) else table


def hub_search_mechanisms(
    query: Annotated[str, Field(min_length=2, max_length=200,
                                description="A word or phrase, e.g. 'outlay' or 'change orders'.")],
    limit: Annotated[int, Field(ge=1, le=50, description="Most rules to return.")] = 8,
) -> MechanismsResult:
    """Rules about how carrier money works: where to look, when a value is
    impossible, why two layers differ. Not figures. Query before interpreting
    a document you have not read before."""
    return search_mechanisms(query, limit)


def hub_get_keyset(section: Annotated[KeysetSection, Field(description=(
        "One section, e.g. collisions; empty for all."))] = "") -> KeysetResult:
    """The identifiers that isolate CVN-79: hull, budget lines, contracts, vendor,
    ledger, scope boundary. Read 'collisions' before building any contract query:
    some contract numbers differ from CVN-79's by one digit and belong to other hulls."""
    return get_keyset(section)


def hub_exhibit_hazards(
    exhibit: Annotated[str, Field(max_length=32, pattern=r"^[A-Za-z0-9 .\-]*$",
                                  description="An exhibit, e.g. P-5 or P-8a; empty for all.")] = "",
) -> HazardsResult:
    """Known traps for a budget or acquisition exhibit (P-1, P-5, P-8a, P-10, P-21,
    the MSAR contract table, USAspending transactions). Every extraction from that
    exhibit inherits them."""
    return exhibit_hazards(exhibit)


def hub_rank_gaps(
    limit: Annotated[int, Field(ge=1, le=100, description="Most gaps to return.")] = 10,
    free_only: Annotated[bool, Field(description="Only gaps that need no access to close.")] = False,
) -> RankGapsResult:
    """The open questions blocking the CVN-79 number, ranked by exposure,
    ignorance and closability. High-exposure gaps that need access are the
    access ask; the free ones are the work queue."""
    return rank_gaps(limit, free_only)


def hub_get_gap(gap_id: GapId) -> GapRow:
    """One gap: its question, type, the office that can close it, its dollar
    exposure and what it blocks."""
    return _ok(get_gap(gap_id))


def hub_plan_gap(gap_id: GapId) -> PlanGapResult:
    """What to do about one gap: candidate explanations and, for each, a Collection
    Requirement naming the document, system or office that settles it. Never a figure."""
    return _ok(plan_gap(gap_id))


def hub_next_work(limit: Annotated[int, Field(ge=1, le=20, description=(
        "Most items per list (work now, access to ask for)."))] = 5) -> NextWorkResult:
    """The top of the gap queue with a first step for each, split into work that
    needs no access and the access to ask for."""
    return next_work(limit)


def hub_check_claim(
    hull: Annotated[str, Field(min_length=3, max_length=16, pattern=r"^[A-Za-z]{2,4}[- ]?\d{1,3}$",
                               description="The hull, e.g. CVN-79.")],
    layer: Annotated[str, Field(min_length=1, max_length=60,
                                description="The layer, e.g. budget, obligation, outlay, asset.")],
    element: Annotated[str, Field(min_length=1, max_length=120,
                                  description="What the figure measures, e.g. Total Ship Estimate.")],
    period: Annotated[str, Field(min_length=1, max_length=40, description="e.g. FY2027 PB.")],
    value_musd: Annotated[str, Field(max_length=20, pattern=NUMBER_OR_EMPTY,
                                     description="The figure in $M as printed; empty if none.")] = "",
    tag: Annotated[TagName, Field(description=(
        "Your tag for the figure. VERIFIED counts only with source_system and a "
        "page or row_label; UNKNOWN becomes a gap."))] = "UNKNOWN",
    confidence: Annotated[float, Field(ge=0.0, le=1.0, description=(
        "Your confidence in the figure, 0 to 1."))] = 0.0,
    source_system: Annotated[Short, Field(description=(
        "Where the figure was read, e.g. 'PB2027 SCN J-book' or 'USAspending'."))] = "",
    exhibit: Annotated[str, Field(max_length=40, description=(
        "The exhibit, e.g. P-5c; empty for a record."))] = "",
    page: Annotated[int, Field(ge=0, le=100000, description=(
        "PDF page the figure is printed on; 0 if not from a document."))] = 0,
    row_label: Annotated[str, Field(max_length=200, description=(
        "The row label as printed, or the record id for a table row."))] = "",
    column_header_chain: Annotated[list[Annotated[str, Field(max_length=200)]],
                                   Field(max_length=12, description="Column headers, outermost first.")] = (),
    page_legends: Annotated[list[Annotated[str, Field(max_length=200)]],
                            Field(max_length=12, description="Every legend printed on the page, "
                                                             "e.g. 'Dollars in Millions'.")] = (),
    neighborhood: Annotated[str, Field(max_length=4000, description="The text around the figure.")] = "",
    notes: Annotated[str, Field(max_length=2000, description=(
        "Anything else about how the figure was found."))] = "",
) -> CheckClaimResult:
    """Check a candidate figure against the decision log and the gate before it is
    treated as a figure. Returns the policy violations (each naming its D-number),
    the risk flags and the routing decision with its reason. Never promotes: a
    person or a deterministic rule acts on the decision."""
    return check_claim(hull, layer, element, period,
                       value=float(value_musd) if value_musd else None, tag=tag,
                       confidence=confidence, source_system=source_system or None,
                       exhibit=exhibit or None, column_header_chain=list(column_header_chain),
                       page_legends=list(page_legends), neighborhood=neighborhood, notes=notes,
                       page=page or None, row_label=row_label or None)


def hub_challenge_text(
    text: Annotated[str, Field(min_length=1, max_length=20000,
                               description="A passage to test before trusting it.")],
    subject: Annotated[str, Field(min_length=3, max_length=16, description=(
        "The hull the passage should be about; other hulls are flagged."))] = "CVN-79",
) -> ChallengeTextResult:
    """Run the falsification vocabulary over a passage: wrong platform, wrong hull,
    identifier collision, announcement-derived figures, unusable outlay fields."""
    return challenge_text(text, subject)


def hub_tie_out(
    total: Amount,
    axis_a_labels: Labels, axis_a_amounts: Amounts,
    axis_b_labels: Labels, axis_b_amounts: Amounts,
) -> TieOutResult:
    """Close one total on two independent decompositions, e.g. the P-5c by cost
    category (axis a) and by funding stream (axis b). Exact decimals, no model;
    passes only when both close to the exhibit's rounding ($500 on a $M exhibit)."""
    return tie_out(total, _pairs(axis_a_labels, axis_a_amounts, "axis a"),
                   _pairs(axis_b_labels, axis_b_amounts, "axis b"))


def hub_check_anchor_chain(step_labels: Labels, step_amounts: Amounts,
                           expected_total: Amount) -> AnchorChainResult:
    """Check that named increments, starting from an anchor such as the statutory
    cap, add up exactly to a published total."""
    pairs = _pairs(step_labels, step_amounts, "steps")
    return check_anchor_chain([[k, v] for k, v in pairs.items()], expected_total)


def hub_collection_requirement(
    lead: Annotated[str, Field(min_length=3, max_length=2000,
                               description="What to retrieve, in one instruction.")],
    gap_id: Annotated[str, Field(max_length=4, pattern=r"^$|^[Gg]\d{1,3}$", description=(
        "The gap it serves, e.g. G14; empty if none."))] = "",
    target_document: Annotated[Short, Field(description=(
        "The document that settles it, e.g. 'PB2027 SCN J-book'."))] = "",
    target_system: Annotated[Short, Field(description=(
        "The system that holds it, e.g. 'DCAS' or 'Navy ERP'."))] = "",
    target_office: Annotated[Short, Field(description=(
        "The office that can answer, e.g. 'PMS 379'."))] = "",
    period: Annotated[str, Field(max_length=40, description="e.g. FY2016 or 'Q3 FY2025'.")] = "",
    account: Annotated[str, Field(max_length=60, description=(
        "A Treasury account or line item, e.g. 017-1611."))] = "",
) -> CollectionRequirementResult:
    """Draft a Collection Requirement from a lead: what to retrieve, from which
    document, system or office, for which period and account. At least one target
    is required. Drafts only; nothing is stored."""
    return _ok(collection_requirement(lead, gap_id, target_document, target_system,
                                      target_office, period, account))


def hub_search_corpus(
    query: Annotated[str, Field(min_length=2, max_length=300, description=(
        "Words to find, e.g. 'Cost Limitation Baseline'."))],
    k: Annotated[int, Field(ge=1, le=20, description="Most passages to return.")] = 6,
    authoritative_only: Annotated[bool, Field(description=(
        "Keep true for anything that could become a figure: with it off, summaries "
        "outrank the documents they summarise."))] = True,
    artifact_id: Annotated[str, Field(max_length=64, pattern=r"^[A-Za-z0-9_.\-]*$", description=(
        "Search one document only, by its id from a previous hit."))] = "",
    figures_only: Annotated[bool, Field(description="Only passages that contain dollar amounts.")] = False,
) -> SearchCorpusResult:
    """Search the document knowledge base. Every hit carries its page citation; a
    passage is a lead until it is read in place on the cited page."""
    return _ok(search_corpus(query, k, authoritative_only, artifact_id or None, figures_only))


def hub_corpus_status() -> CorpusStatusResult:
    """What the knowledge base holds and what it leaves out by design (structured
    tables and images)."""
    return corpus_status()


TOOLS = [hub_search_corpus, hub_corpus_status,
         hub_list_tables, hub_get_table, hub_search_mechanisms, hub_get_keyset,
         hub_exhibit_hazards, hub_rank_gaps, hub_get_gap, hub_plan_gap, hub_next_work,
         hub_check_claim, hub_challenge_text, hub_tie_out, hub_check_anchor_chain,
         hub_collection_requirement]


# ------------------------------------------------------------------ servers
def build(http: bool = False):
    """Build the FastMCP server. Imported lazily so the module stays testable
    without the mcp package installed.

    http=True is the hosted form: stateless streamable HTTP, like the other
    servers, and bound to all interfaces. The SDK turns on DNS-rebinding
    protection for its default host 127.0.0.1 and then refuses any Host header
    but localhost, so behind the Databricks Apps proxy every request failed.
    The proxy authenticates every request before it reaches the app."""
    from mcp.server.fastmcp import FastMCP
    from mcp.types import ToolAnnotations
    from source_notice import INSTRUCTION
    kw = {"host": "0.0.0.0", "stateless_http": True} if http else {}  # nosec B104
    srv = FastMCP(SERVER_NAME, instructions=INSTRUCTIONS + INSTRUCTION, **kw)
    for fn in TOOLS:
        title = fn.__name__.removeprefix("hub_").replace("_", " ").capitalize()
        srv.tool(name=fn.__name__,
                 annotations=ToolAnnotations(title=title, **READ_ONLY))(_noticed(fn))
    if http:
        import os

        from starlette.responses import JSONResponse

        @srv.custom_route("/", methods=["GET"])
        async def landing(request):
            # A person who opens the app's link sees what it is, as with the
            # other servers, instead of a bare 404. MCP clients use /mcp.
            return JSONResponse({
                "service": SERVER_NAME, "status": "running",
                "description": INSTRUCTIONS.split(". ")[0] + ".",
                "tools": [fn.__name__ for fn in TOOLS], "read_only": True,
                "owner": os.environ.get("APP_OWNER", ""),
                "mcp_endpoint": "/mcp", "transport": "streamable-http (stateless)"})

        @srv.custom_route("/health", methods=["GET"])
        async def health(request):
            return JSONResponse({"status": "healthy", "service": SERVER_NAME,
                                 "tools": len(TOOLS)})
    return srv


def _noticed(fn):
    """The tool, with source_notice added to its result when the result holds
    text addressed to an AI assistant (mcp-servers/test_source_notice.py)."""
    import functools

    from source_notice import annotate_dict

    @functools.wraps(fn)
    def wrapped(*args, **kwargs):
        return annotate_dict(fn(*args, **kwargs))
    return wrapped


def http_app():
    return build(http=True).streamable_http_app()


def main() -> None:
    import os
    port = os.getenv("DATABRICKS_APP_PORT") or os.getenv("PORT")
    if not port:
        build().run()
        return
    import uvicorn
    uvicorn.run(http_app(), host="0.0.0.0", port=int(port))  # nosec B104 - behind the Apps proxy


if __name__ == "__main__":
    main()
