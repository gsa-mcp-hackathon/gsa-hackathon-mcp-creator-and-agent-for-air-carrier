"""Investigator. Owns the work register.

Decides what gets worked next and, for a gap, what could account for it and
where each candidate would be confirmed. It never produces a figure. Its only
legitimate output is a ranked queue and a set of Collection Requirements (D16).

Prohibitions, enforced in code below rather than in a prompt:
  - never emits a value. There is no value field on anything it returns.
  - never emits a hypothesis with no named target. Dropped by validate().
  - never assigns a gap back to the sponsor. Executors come from the register.
  - never calls another agent. It writes rows; the orchestrator moves them.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from core.contracts import CollectionRequirement, Gap, GapType, Mechanism

CLOSABILITY_WEIGHT = {
    "zero_access": 1.00,     # readable today with nothing but effort
    "query": 0.80,           # a system we can already reach
    "access_required": 0.35, # waits on sponsorship
    "sme": 0.25,             # waits on a person, and decays
    "terminal": 0.05,        # IRREDUCIBLE
    "unknown": 0.50,
}

# Decay multiplies the queue position of an SME gap and nothing else. A low
# dollar question whose answer retires next year can outrank a high dollar one
# still answerable in three. That is the only argument for moving now that does
# not depend on anyone's enthusiasm.
DECAY_WEIGHT = {"high": 1.6, "medium": 1.2, "low": 1.0, "unknown": 1.0}

# Where an answer of each type is retrieved from. Deterministic, no model.
# Keeps the agent useful at zero access and gives the model a frame rather than
# a blank page.
CHANNEL = {
    GapType.DOCUMENT: ("retrieve and read", "target_document"),
    GapType.DATA:     ("query", "target_system"),
    GapType.SME:      ("ask, and record the answer before it retires", "target_office"),
    GapType.CATALOG:  ("enumerate from inside the environment", "target_system"),
    GapType.IRREDUCIBLE: ("state the limit in the product", None),
}


@dataclass
class Hypothesis:
    statement: str
    mechanism_ids: list[str]
    confirms_at: CollectionRequirement
    prior: float
    rejected_because: str = ""

    @property
    def actionable(self) -> bool:
        return not self.rejected_because


@dataclass
class WorkPlan:
    gap_id: str
    hypotheses: list[Hypothesis] = field(default_factory=list)
    requirements: list[CollectionRequirement] = field(default_factory=list)
    dropped: list[Hypothesis] = field(default_factory=list)
    notes: str = ""

    @property
    def is_empty(self) -> bool:
        """An empty plan is a finding. It means the gap is mis-typed, or the
        mechanism store has nothing to say about it, and either way a person
        should look rather than the queue quietly skipping it."""
        return not self.requirements


# ---------------------------------------------------------------- ranking

def rank(gaps: list[Gap]) -> list[tuple[Gap, float]]:
    """exposure x ignorance x closability, descending, decay for SME.

    Deliberately not a composite risk score (D26). This ranks a work queue, it
    does not grade a claim. The three terms stay visible on the row so a reader
    sees why a gap is where it is.
    """
    scored = []
    for g in gaps:
        if g.closed_at:
            continue
        if g.gap_type == GapType.IRREDUCIBLE:
            # Terminal by type, whatever its closability field says. run()
            # refuses to plan it, so ranking it puts a row in the queue that
            # nobody can ever work. It belongs in the product's stated limits.
            continue
        w = CLOSABILITY_WEIGHT.get(g.closability, 0.5)
        d = DECAY_WEIGHT.get(g.decay_risk, 1.0) if g.gap_type == GapType.SME else 1.0
        scored.append((g, max(g.exposure_usd_m, 1.0) * g.ignorance * w * d))
    return sorted(scored, key=lambda t: -t[1])


def free_now(gaps: list[Gap]) -> list[Gap]:
    """The gaps that cost nothing but effort. Work these before asking anyone
    for anything, because an access request is more persuasive after the free
    work is visibly done."""
    return [g for g, _ in rank(gaps) if g.closability in ("zero_access", "query")]


# ---------------------------------------------------------------- validation

def validate(h: Hypothesis) -> Hypothesis:
    """Structural enforcement of D16. A hypothesis with no named target is not
    work, it is an opinion, and it does not enter the plan."""
    cr = h.confirms_at
    if not cr.instruction.strip():
        h.rejected_because = "no instruction"
    elif not (cr.target_document or cr.target_system or cr.target_office):
        h.rejected_because = "no named target. A lead with no target is not a requirement"
    elif not h.mechanism_ids:
        h.rejected_because = "ungrounded. No mechanism says this is even possible"
    elif _looks_like_a_figure(h.statement):
        h.rejected_because = "states a value. The investigator does not produce figures"
    return h


def _looks_like_a_figure(text: str) -> bool:
    """Cheap guard, not a parser. Catches the common failure where a model
    answers the question instead of saying where the answer lives."""
    import re
    return bool(re.search(r"(?:\$\s?[\d,]{4,}|\b\d[\d,]{5,}\b|\b\d+(?:\.\d+)?\s*(?:million|billion|M\b|B\b))", text))


# ---------------------------------------------------------------- generation

SYSTEM = """You are an intelligence analyst working an unknown in a Navy shipbuilding cost dossier.

You do not answer the question. You enumerate what could account for it and say exactly where each
candidate would be confirmed or killed.

Rules:
- Every hypothesis names at least one mechanism from the supplied mechanism list. A hypothesis no
  mechanism permits is not a hypothesis, it is a guess, and it will be discarded.
- Every hypothesis carries one specific retrieval instruction: which document, which system, or which
  office, for which period and which account. "Check the budget documents" is not an instruction.
- Never state a dollar figure, a percentage of a total, or any value. If you find yourself writing a
  number that answers the question, you have left your lane.
- Prefer the hypothesis that would be cheapest to kill. A cheap disconfirmation outranks an expensive
  confirmation.
- An inherited label is a hypothesis, not a fact. If the gap rests on a vendor name, a scope
  description or an attribution that arrived with the question, make testing that label one of the
  hypotheses, and say which source asserted it. Three of the recorded errors in this program were
  inherited labels nobody had tested."""

PROMPT_VERSION = "investigator/hypotheses@3"

SCHEMA = {
    "type": "object",
    "required": ["hypotheses"],
    "properties": {"hypotheses": {"type": "array", "items": {
        "type": "object",
        "required": ["statement", "mechanism_ids", "instruction", "prior"],
        "properties": {
            "statement": {"type": "string"},
            "mechanism_ids": {"type": "array", "items": {"type": "string"}},
            "instruction": {"type": "string"},
            "target_document": {"type": ["string", "null"]},
            "target_system": {"type": ["string", "null"]},
            "target_office": {"type": ["string", "null"]},
            "period": {"type": ["string", "null"]},
            "account": {"type": ["string", "null"]},
            "prior": {"type": "number"},
        }}}},
}


def run(gap: Gap, mechanisms: list[Mechanism] | None = None, llm=None,
        max_hypotheses: int = 6) -> WorkPlan:
    """Generate candidate explanations and where each would be confirmed.

    Works with no model at all: the deterministic channel below produces one
    requirement from the gap's own type and executor, which is what the hand-run
    equivalent in Part F did. A model widens the hypothesis set; it is not load
    bearing for the plan existing.
    """
    plan = WorkPlan(gap_id=gap.gap_id)
    verb, target_field = CHANNEL.get(gap.gap_type, ("investigate", None))

    # --- floor: the gap's own type and executor, always present -------------
    if gap.gap_type == GapType.IRREDUCIBLE:
        plan.notes = ("terminal. No record, no living memory. The product states the limit; "
                      "the queue does not carry it.")
        return plan

    base = CollectionRequirement(
        cr_id=f"{gap.gap_id}-CR0",
        instruction=f"{verb}: {gap.question}",
        target_office=gap.executor if target_field == "target_office" else None,
        target_system=gap.executor if target_field == "target_system" else None,
        target_document=gap.executor if target_field == "target_document" else None,
        originating_lead_id=gap.gap_id,
        exposure_usd_m=gap.exposure_usd_m,
    )
    plan.requirements.append(base)

    if llm is None:
        plan.notes = "deterministic plan only. No model supplied."
        return plan

    # --- model widens the hypothesis set ------------------------------------
    mechanisms = mechanisms or []
    catalog = "\n".join(
        f"- {m.mechanism_id}: {m.statement}" for m in mechanisms
    ) or "- (none supplied. Say so in your hypotheses rather than inventing a mechanism.)"

    user = (
        f"GAP {gap.gap_id} ({gap.gap_type.value}, closability {gap.closability})\n"
        f"QUESTION: {gap.question}\n"
        f"BLOCKS: {gap.blocks or 'unstated'}\n"
        f"EXPOSURE: {gap.exposure_usd_m} USD millions left unexplained\n"
        f"NAMED EXECUTOR: {gap.executor}\n\n"
        f"MECHANISMS IN FORCE:\n{catalog}\n\n"
        f"Return at most {max_hypotheses} hypotheses, cheapest to kill first."
    )

    res = llm.complete(SYSTEM, user, role="reasoning",
                       prompt_version=PROMPT_VERSION, json_schema={"name": "hypotheses", "schema": SCHEMA})
    # No temperature: the reasoning-role endpoints accept only the default (probed
    # 2026-11-11), so temperature=0.2 would send every call down the fallback chain to fail.

    import json
    try:
        payload = json.loads(res.text)
    except json.JSONDecodeError:
        plan.notes = f"model returned unparseable output. trace {res.trace_id}. Deterministic plan stands."
        return plan

    known = {m.mechanism_id for m in mechanisms}
    for n, h in enumerate(payload.get("hypotheses", [])[:max_hypotheses], start=1):
        cr = CollectionRequirement(
            cr_id=f"{gap.gap_id}-CR{n}",
            instruction=(h.get("instruction") or "").strip(),
            target_document=h.get("target_document") or None,
            target_system=h.get("target_system") or None,
            target_office=h.get("target_office") or None,
            period=h.get("period") or None,
            account=h.get("account") or None,
            originating_lead_id=gap.gap_id,
            exposure_usd_m=gap.exposure_usd_m,
        )
        hyp = validate(Hypothesis(
            statement=(h.get("statement") or "").strip(),
            mechanism_ids=[m for m in (h.get("mechanism_ids") or []) if not known or m in known],
            confirms_at=cr,
            prior=float(h.get("prior") or 0.0),
        ))
        if hyp.actionable:
            plan.hypotheses.append(hyp)
            plan.requirements.append(cr)
        else:
            plan.dropped.append(hyp)

    plan.notes = (f"{len(plan.hypotheses)} actionable, {len(plan.dropped)} dropped. "
                  f"trace {res.trace_id}. prompt {PROMPT_VERSION}")
    return plan


# ---------------------------------------------------------------- post-mortem

def postmortem(gap: Gap, plan: WorkPlan, resolution: str) -> dict:
    """Run when a gap closes. Records whether any hypothesis predicted the
    answer, because a plan that never predicts anything is a plan that is
    generating plausible text.

    G27 is the worked example: the gap was framed as a completeness question
    about two contracts and closed as an attribution error in the source that
    supplied them. No hypothesis about scope would have predicted that. The
    hypothesis that would have is "the inherited label is wrong", which is now
    a standing instruction in the prompt above rather than a lesson in a log.
    """
    text = resolution.lower()
    hit = [h.statement for h in plan.hypotheses
           if any(w in text for w in _keywords(h.statement))]
    return {
        "gap_id": gap.gap_id,
        "closed_at": (gap.closed_at or datetime.now(timezone.utc)).isoformat(),
        "hypotheses_offered": len(plan.hypotheses),
        "hypotheses_dropped": len(plan.dropped),
        "predicted": hit,
        "surprise": not hit,
        "resolution": resolution,
        "lesson_required": not hit and len(plan.hypotheses) > 0,
    }


def _keywords(statement: str) -> list[str]:
    stop = {"the", "a", "an", "is", "are", "of", "for", "to", "in", "on", "and",
            "or", "this", "that", "it", "be", "may", "might", "was", "were",
            "hull", "contract", "cost", "which", "whether", "from", "with"}
    return [w for w in
            (t.strip(".,;:()").lower() for t in statement.split())
            if len(w) > 4 and w not in stop][:8]
