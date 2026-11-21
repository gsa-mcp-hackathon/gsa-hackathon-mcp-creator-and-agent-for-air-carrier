"""Derived insight, recommended action and risk, for the executive dashboard.

Every item here is computed from the tables and carries the rule that
produced it and the figure it rests on. None of it is written by a model and
none of it is decoration.

That is a deliberate constraint, not a limitation waiting to be lifted. A
dashboard that shows a model's prose next to a number invites the reader to
trust the prose at the number's confidence level, and in this programme the
numbers carry explicit trust states that the prose would quietly launder. A
model is useful here for phrasing and for drafting the narrative around these
items. It is not what decides that an item appears.

Each item: severity, what, so_what, now_what, and the evidence it stands on.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class Item:
    kind: str                     # insight | action | risk
    severity: str                 # high | medium | low
    title: str
    body: str
    evidence: list[str] = field(default_factory=list)
    rule: str = ""
    link: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


def _m(v) -> str:
    return f"${v:,.0f}M" if abs(v) >= 1 else f"${v*1000:,.0f}K"


def derive(d: dict) -> list[Item]:
    """d: the loaded tables, keyed by name."""
    out: list[Item] = []

    cost = d.get("cost_categories", {})
    attr = d.get("attribution", {})
    gaps = d.get("gaps", {})
    var = d.get("variances", {})
    caps = d.get("cap_history", {})
    con = d.get("contracts", {})

    total = float(cost.get("total") or 0)

    # --- the cap position ------------------------------------------------
    ceilings = {c["name"]: float(c["value"]) for c in caps.get("three_ceilings", [])}
    stat = ceilings.get("Statutory cost cap")
    if stat and total:
        over = total - stat
        out.append(Item(
            kind="insight", severity="high" if over > 0 else "low",
            title=f"The ship is {_m(over)} above the statutory cap",
            body=(f"Current total ship estimate {_m(total)} against a statutory cap of "
                  f"{_m(stat)}, {over / stat * 100:.1f} per cent over. The cap is not a "
                  f"budget line and exceeding it is not an overrun by itself: the "
                  f"legislation excludes defined categories, and which categories are "
                  f"excluded is still an open question (G12). Until that closes, the "
                  f"gap between these two figures cannot be read as cost growth."),
            evidence=[f"cost_categories.total = {total:,.3f}",
                      f"cap_history: {stat:,.1f}, 10 U.S.C. 8692"],
            rule="total ship estimate vs statutory ceiling",
            link="/baseline"))

    if len(ceilings) >= 3:
        out.append(Item(
            kind="risk", severity="high",
            title=f"{len(ceilings)} different cost caps are in circulation, all correct",
            body=("Statutory cap, SECNAV Cost Limitation Baseline and the budget "
                  "submission are three different numbers for three different "
                  "purposes. Any product that shows one of them as the cost cap will "
                  "be wrong for two audiences, and the reader will not know which."),
            evidence=[f"{n}: {_m(v)}" for n, v in list(ceilings.items())[:3]],
            rule="more than one ceiling in cap_history", link="/baseline"))

    # --- attribution ------------------------------------------------------
    pct = float(attr.get("attributed_pct") or 0)
    resid = float(attr.get("residual_usd_m") or 0)
    if pct:
        was = attr.get("improved_from_pct")
        out.append(Item(
            kind="insight", severity="medium" if pct < 90 else "low",
            title=f"{pct:.1f} per cent of the hull is attributed to a named contract",
            body=(f"{_m(resid)} is not yet traceable to a contract number. "
                  + (f"This moved from {was:.1f} per cent in one pass, by replacing an "
                     f"announcement-derived figure with the obligation record rather "
                     f"than by finding new money. " if was else "")
                  + "The remainder is where the next hour of work pays."),
            evidence=[f"attribution.attributed_pct = {pct}",
                      f"residual = {resid:,.1f}"],
            rule="attribution coverage against 100 per cent", link="/cost"))

    # --- the work queue ---------------------------------------------------
    rows = [r for r in gaps.get("rows", []) if not r.get("closed")]
    free = [r for r in rows if r.get("closability") in ("zero_access", "query")]
    if free:
        top = sorted(free, key=lambda r: -float(r.get("priority") or 0))[:3]
        exposure = sum(float(r.get("exposure_usd_m") or 0) for r in free)
        out.append(Item(
            kind="action", severity="high",
            title=f"{len(free)} open questions need no access at all",
            body=(f"They carry {_m(exposure)} of unexplained exposure between them and "
                  f"cost nothing but effort. Working these before asking anyone for "
                  f"anything is also what makes the access request persuasive: an ask "
                  f"that arrives after the free work is visibly done is a different "
                  f"conversation. Start with "
                  + ", ".join(r["id"] for r in top) + "."),
            evidence=[f"{r['id']}: {r['title'][:68]}" for r in top],
            rule="open gaps with closability zero_access or query", link="/gaps"))

    waiting = [r for r in rows if r.get("closability") == "access_required"]
    if waiting:
        exp = sum(float(r.get("exposure_usd_m") or 0) for r in waiting)
        out.append(Item(
            kind="risk", severity="high" if exp > 1000 else "medium",
            title=f"{_m(exp)} of exposure is waiting on access, not on analysis",
            body=(f"{len(waiting)} gaps cannot be closed from outside the environment "
                  f"at any level of effort. These are the access ask, and they belong "
                  f"in a sponsor conversation rather than in the work queue."),
            evidence=[f"{r['id']}: {r.get('executor','')[:54]}" for r in waiting[:3]],
            rule="open gaps with closability access_required", link="/gaps"))

    decaying = [r for r in rows if r.get("closability") == "sme"
                and str(r.get("decay", "")).lower().startswith("high")]
    if decaying:
        out.append(Item(
            kind="risk", severity="medium",
            title=f"{len(decaying)} answer(s) leave on a retirement schedule",
            body=("Institutional memory about a system cutover does not wait for the "
                  "project plan. A low-dollar question whose answer retires next year "
                  "can outrank a high-dollar one still answerable in three, and that "
                  "is the only argument for moving now that does not depend on "
                  "anyone's enthusiasm."),
            evidence=[f"{r['id']}: {r['title'][:68]}" for r in decaying[:3]],
            rule="open SME gaps with high decay", link="/gaps"))

    # --- disagreements between sources ------------------------------------
    live = [r for r in var.get("rows", []) if r.get("status") == "live"]
    method = [r for r in live if r.get("flag") == "METHOD"]
    if method:
        out.append(Item(
            kind="risk", severity="high",
            title=f"{len(method)} unresolved disagreement(s) between authoritative sources",
            body=("Two systems report different totals for the same contract. The "
                  "differences are immaterial to any total, which is exactly why they "
                  "matter: each is small enough to pass every reasonableness check a "
                  "reviewer would apply. Cite the system by name with every obligation "
                  "figure and never present one as if it had a single value."),
            evidence=[f"{r['id']}: {r['title'][:72]}" for r in method[:3]],
            rule="live variances flagged METHOD", link="/variances"))

    # --- outlay coverage ---------------------------------------------------
    cov = con.get("outlay_coverage_pct")
    if cov is not None and float(cov) < 5:
        out.append(Item(
            kind="risk", severity="high",
            title=f"Award-level outlay reporting covers {float(cov):.2f} per cent of obligations",
            body=("The public spending record carries obligations for this hull but "
                  "almost no outlays. This is the Fund Balance with Treasury weakness "
                  "showing up in public data rather than in an audit report. No cost "
                  "product may take outlays for this hull from that source until it "
                  "closes."),
            evidence=[f"contracts.outlay_coverage_pct = {cov}", "G25"],
            rule="outlay coverage below 5 per cent", link="/execution"))

    # --- what the corpus can and cannot answer ----------------------------
    corpus = d.get("corpus", {})
    if corpus:
        routes = corpus.get("by_route", {})
        out.append(Item(
            kind="insight", severity="low",
            title=f"{routes.get('embed', 0)} documents are searchable, "
                  f"{routes.get('table', 0)} are queryable",
            body=("The knowledge base indexes prose and the tables inside documents. "
                  "Structured extracts are not embedded: semantic search answers a "
                  "question about a transaction worse than a WHERE clause does, and "
                  "embedding them swamps the index with rows. Ask the corpus for "
                  "meaning and the tables for numbers."),
            evidence=[(f"{corpus.get('count', corpus.get('artifacts', 0))} artifacts, "
                      f"{corpus.get('bytes', 0) / 1048576:.0f}MB catalogued")],
            rule="corpus manifest routing", link="/sources#search"))

    order = {"high": 0, "medium": 1, "low": 2}
    out.sort(key=lambda i: (order.get(i.severity, 3), i.kind))
    return out


def by_kind(items: list[Item]) -> dict:
    return {k: [i for i in items if i.kind == k] for k in ("insight", "action", "risk")}
