"""SI SDK: the primitives and the six-stage run engine.

The pattern is the one the CORAS CFO Mission Module demo runs (docs/
ORCHESTRATION_V2.md Part A), rebuilt for this stack and tightened where the
demo leaves room for a model to invent something:

  1 Trigger   a page button or chip names one task and one subject. There is
              no blank chat box behind a decision.
  2 Route     the Orchestrator looks the (task, subject kind) up in the task
              registry. An unknown pair is refused, not improvised.
  3 Pack      the task's packer reads the records with SQL. Code chooses the
              evidence; every figure the run may state is computed here, in
              Decimal, and becomes a Fact.
  4 Work      the task's code steps run first, then one specialist model
              explains what was packed. It may rewrite the WHY and PROPOSED
              text of the code's draft proposals and add flags. It cannot add
              a proposal, set an amount, or change the office a proposal goes
              to or the rule it cites.
  5 Check     two checkers with different methods, both shown:
                canvas            code recomputes the task conditions and
                                  grounds every number in every sentence
                                  against the packed Facts
                records checker   a second model reads the answer against the
                                  same Facts
              A proposal reaches the review modal only if the canvas passed
              and the records checker did not reject it.
  6 Decide    a person ticks proposals; authority is checked server side by
              the role that owns the proposal (router.py, store.py).

Nothing here does IO except through the callables on Ctx, so tests run the
whole engine with fakes.
"""
from __future__ import annotations

import hashlib
import json
import re
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

QueryFn = Callable[[str, dict], list[dict]]
SDK_VERSION = "si/1.0"


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def money(value) -> str:
    """Decimal -> '$4,519,300,323.83'. Separators only, every cent kept."""
    d = Decimal(str(value)).quantize(Decimal("0.01"))
    return f"{'-' if d < 0 else ''}${abs(d):,.2f}"


# ------------------------------------------------------------------- agents
@dataclass(frozen=True)
class Agent:
    key: str
    name: str
    kind: str                      # ORCHESTRATOR | SPECIALIST | CHECKER | CANVAS
    job: str
    never: tuple[str, ...] = ()
    rulebooks: tuple[str, ...] = ()

    def card(self) -> dict:
        return {"key": self.key, "name": self.name, "kind": self.kind, "job": self.job,
                "never": list(self.never), "rulebooks": list(self.rulebooks)}


ORCHESTRATOR = Agent(
    "orchestrator", "Orchestrator", "ORCHESTRATOR",
    "Reads the request, picks one specialist, packs only the records the task needs "
    "and returns proposals.",
    ("Never lets a model choose the records", "Never writes a record"))
RECORDS_CHECKER = Agent(
    "records_checker", "Records Checker", "CHECKER",
    "Reads the specialist's answer against the same packed records and says whether "
    "every stated fact matches one.",
    ("Never edits a proposal", "Never sees records the specialist did not"),
    ("Evidence and citation discipline",))
CANVAS = Agent(
    "canvas", "Canvas re-check", "CANVAS",
    "Recomputes every figure from the packed records in code, re-tests the task's "
    "conditions and grounds every number in every sentence.",
    ("Uses no model",))


# -------------------------------------------------------------------- facts
@dataclass
class Fact:
    """A value code computed from the packed records. The only numbers a run may state."""
    key: str
    label: str
    value: str | None              # decimal string, ISO date, or text
    unit: str                      # USD | COUNT | PERCENT | DATE | TEXT
    computation: str
    rule: str | None = None

    def number(self) -> Decimal | None:
        if self.unit not in ("USD", "COUNT", "PERCENT") or self.value is None:
            return None
        try:
            return Decimal(str(self.value))
        except InvalidOperation:
            return None

    def display(self) -> str:
        if self.value is None:
            return "unknown"
        if self.unit == "USD":
            return money(self.value)
        if self.unit == "COUNT":
            return f"{int(Decimal(self.value)):,}"
        if self.unit == "PERCENT":
            return f"{self.value}%"
        return str(self.value)

    def view(self) -> dict:
        return {"key": self.key, "label": self.label, "value": self.value, "unit": self.unit,
                "display": self.display(), "computation": self.computation, "rule": self.rule}


@dataclass
class Pack:
    """What the packer read. Code chose every record; the model sees only this."""
    subject_kind: str
    subject_id: str
    noun: str                       # "FPDS actions", "File C rows" ...
    source: str                     # tables or files read
    records: list[dict]
    record_ids: list[str]
    facts: dict[str, Fact] = field(default_factory=dict)
    series: dict[str, list[dict]] = field(default_factory=dict)
    context: dict = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    read_at: str = field(default_factory=now_iso)
    live: bool = True

    def add(self, key: str, label: str, value, unit: str, computation: str,
            rule: str | None = None) -> Fact:
        v = None if value is None else (format(value, "f") if isinstance(value, Decimal)
                                        else str(value))
        f = Fact(key, label, v, unit, computation, rule)
        self.facts[key] = f
        return f

    def fact(self, key: str) -> Fact:
        return self.facts[key]

    def record_numbers(self) -> list[Decimal]:
        """Every number printed in a packed record. Quoting a record is grounded too."""
        if not hasattr(self, "_record_numbers"):
            vals: set[Decimal] = set()
            for r in self.records:
                for v in r.values():
                    if isinstance(v, (int, float, Decimal)) and not isinstance(v, bool):
                        vals.add(abs(Decimal(str(v))))
                    elif isinstance(v, str) and v:
                        try:
                            vals.add(abs(Decimal(v)))
                        except InvalidOperation:
                            vals.update(abs(t["value"]) for t in numbers_in(v))
            self._record_numbers = sorted(vals)
        return self._record_numbers

    def record_dates(self) -> set[str]:
        """Every ISO date printed in a packed record. No date may be invented."""
        if not hasattr(self, "_record_dates"):
            self._record_dates = {m for r in self.records for v in r.values()
                                  if isinstance(v, str) for m in _DATE.findall(v)}
        return self._record_dates

    def public_context(self) -> dict:
        return {k: v for k, v in self.context.items() if not k.startswith("_")}

    @property
    def provenance_id(self) -> str:
        key = json.dumps([self.subject_kind, self.subject_id, self.source,
                          sorted(self.record_ids)], separators=(",", ":"))
        return hashlib.sha256(key.encode()).hexdigest()[:16]

    def view(self, preview: int = 25) -> dict:
        return {"subject_kind": self.subject_kind, "subject_id": self.subject_id,
                "noun": self.noun, "source": self.source, "live": self.live,
                "record_count": len(self.record_ids), "provenance_id": self.provenance_id,
                "read_at": self.read_at, "facts": [f.view() for f in self.facts.values()],
                "series": self.series, "notes": self.notes,
                "preview": self.records[:preview]}


# ---------------------------------------------------------------- proposals
@dataclass
class Proposal:
    key: str                        # stable within a run: the model refers to it
    kind: str                       # variance_note | correction | collection_request ...
    title: str
    goes_to_role: str               # authority role that may apply it
    goes_to_office: str             # the office, in words
    proposed: str
    why: str
    rule: str
    fact_keys: list[str] = field(default_factory=list)
    marked_blanks: list[dict] = field(default_factory=list)   # {field, who_fills, why}
    flags: list[dict] = field(default_factory=list)           # {severity, text}
    proposal_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: str = "pending"         # pending | blocked | applied | rejected
    block_reason: str | None = None
    drafted_by: str = "code"
    grounding: list[dict] = field(default_factory=list)
    # For a request: the office the ask is sent to. goes_to is who decides
    # whether to send it; addressed_to is who receives it. Set by code only.
    addressed_to: str | None = None
    # A run loaded back from the harness tables has no pack, so its figures are
    # the ones stored with the proposal when the run was written (store.load_run).
    saved_figures: list[dict] = field(default_factory=list)

    def text(self) -> str:
        return f"{self.title}\n{self.proposed}\n{self.why}"

    def view(self, facts: dict[str, Fact] | None = None) -> dict:
        return {"proposal_id": self.proposal_id, "key": self.key, "kind": self.kind,
                "title": self.title, "goes_to": {"role": self.goes_to_role,
                                                  "office": self.goes_to_office},
                "addressed_to": self.addressed_to,
                "proposed": self.proposed, "why": self.why, "rule": self.rule,
                "figures": ([facts[k].view() for k in self.fact_keys if k in facts] if facts
                            else list(self.saved_figures)),
                "marked_blanks": self.marked_blanks, "flags": self.flags,
                "status": self.status, "block_reason": self.block_reason,
                "drafted_by": self.drafted_by, "grounding": self.grounding}


@dataclass
class Verdict:
    checker: str
    result: str                     # pass | pass_with_notes | fail | error | not_run
    checks: list[dict] = field(default_factory=list)  # {name, expected, actual, result}
    notes: str = ""
    model: str | None = None
    decided_at: str = field(default_factory=now_iso)

    def view(self) -> dict:
        return {"checker": self.checker, "result": self.result, "checks": self.checks,
                "notes": self.notes, "model": self.model, "decided_at": self.decided_at,
                "passed": sum(1 for c in self.checks if c.get("result") == "pass"),
                "total": len(self.checks)}


def check(name: str, expected, actual, ok: bool | None = None) -> dict:
    ok = (str(expected) == str(actual)) if ok is None else ok
    return {"name": name, "expected": str(expected), "actual": str(actual),
            "result": "pass" if ok else "fail"}


# ------------------------------------------------------------------ context
@dataclass
class Ctx:
    q_app: QueryFn | None
    data_get: Callable[[str], Any]
    call_model: Callable[[str, dict], dict] | None = None
    models: list[str] = field(default_factory=list)
    checker_models: list[str] = field(default_factory=list)
    asked_by: str | None = None
    page: str = ""
    # role -> office register. Routing is chosen by code, so the checker is
    # given the register to test an office or role named in an answer.
    offices: dict[str, str] = field(default_factory=dict)


# ----------------------------------------------------------------- templates
@dataclass(frozen=True)
class TaskTemplate:
    task_id: str
    label: str                      # "Reconcile {subject}": the button names its scope
    question: str                   # the one question this task answers
    specialist: Agent
    subject_kind: str
    rules: tuple[str, ...]
    pages: tuple[str, ...]
    packer: Callable[[Ctx, str, dict], Pack]
    steps: Callable[[Pack], list[tuple[str, str]]]
    draft: Callable[[Pack], list[Proposal]]
    canvas: Callable[[Pack, list[Proposal]], list[dict]]
    validate_subject: Callable[[str], bool] = lambda s: bool(s)
    examples: tuple[str, ...] = ()

    def scoped_label(self, subject: str) -> str:
        return self.label.format(subject=subject)

    def card(self) -> dict:
        return {"task_id": self.task_id, "label": self.label, "question": self.question,
                "specialist": self.specialist.card(), "subject_kind": self.subject_kind,
                "rules": list(self.rules), "pages": list(self.pages),
                "examples": [{"subject": s, "label": self.scoped_label(s)} for s in self.examples]}


class Refused(ValueError):
    """The orchestrator will not run this. The message is shown as is."""


# ----------------------------------------------------------------- grounding
# Identifiers that contain digits but are not figures: PIIDs, mods, periods,
# register ids, rule ids, hulls, dates. They are removed before numbers are read.
_IDENT = re.compile(
    r"(?<![\w$])(?:N\d{5}[-\w]*|P\d{5}\b|FY\s?\d{4}[A-Z]?\d*|\d{4}-\d{2}-\d{2}|"
    r"[A-Z]{1,8}(?:\([A-Z]+\))?[- ]?\d+[A-Za-z0-9-]*|[a-f0-9]{8,}|\d{3}-\d{4}/\d{4}-\d{4})")
_NUMBER = re.compile(
    r"(?<![\w.])(\(?-?\$?\(?-?)(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)\)?"
    r"(\s?(?:billion|million|thousand|bn|[BMK])\b)?(\s?%|\s?percent\b)?", re.I)
_SCALE = {"billion": Decimal(10) ** 9, "bn": Decimal(10) ** 9, "b": Decimal(10) ** 9,
          "million": Decimal(10) ** 6, "m": Decimal(10) ** 6,
          "thousand": Decimal(10) ** 3, "k": Decimal(10) ** 3}


def numbers_in(text: str) -> list[dict]:
    """Every figure-like token in text: {raw, value, decimals, scale, percent, money}."""
    out = []
    bare = _IDENT.sub(" ", text or "")
    for m in _NUMBER.finditer(bare):
        lead, digits, suffix, pct = m.group(1) or "", m.group(2), m.group(3), m.group(4)
        try:
            v = Decimal(digits.replace(",", ""))
        except InvalidOperation:
            continue
        dec = len(digits.split(".")[1]) if "." in digits else 0
        is_money = "$" in lead
        scale = _SCALE.get((suffix or "").strip().lower())
        # Plain small integers and years are dates, step numbers and ordinals.
        if not is_money and not scale and not pct and dec == 0 and "," not in digits:
            if v <= 31 or Decimal(1990) <= v <= Decimal(2040):
                continue
        out.append({"raw": m.group(0).strip(), "value": v, "decimals": dec, "scale": scale,
                    "percent": bool(pct), "money": is_money})
    return out


def _matches(tok: dict, fact_value: Decimal) -> bool:
    fv = abs(fact_value)
    v = tok["value"]
    q = Decimal(1).scaleb(-tok["decimals"])
    if tok["scale"]:
        return (fv / tok["scale"]).quantize(q) == v
    if v == fv:
        return True
    # "$4.52 billion" is handled above; "$4,519,300,324" (rounded to the dollar) here.
    return tok["decimals"] == 0 and "," in tok["raw"] and fv.quantize(Decimal(1)) == v


_DATE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")


def ungrounded(text: str, facts: dict[str, Fact],
               extra: list[Decimal] | None = None,
               dates: set[str] | None = None) -> list[str]:
    """The numbers in text that match no packed Fact (or, with extra, no number
    printed in a packed record), and, when dates is given, the ISO dates that
    are in no Fact or record. Empty means grounded."""
    values = [f.number() for f in facts.values() if f.number() is not None]
    values += list(extra or [])
    bad = []
    for tok in numbers_in(text):
        if not any(_matches(tok, fv) for fv in values):
            bad.append(tok["raw"])
    if dates is not None:
        known = dates | {f.value for f in facts.values() if f.unit == "DATE" and f.value}
        bad += [d for d in _DATE.findall(text or "") if d not in known]
    return bad


# ---------------------------------------------------------------------- runs
class Run:
    """One run of one task on one subject. Events are appended as it works, so a
    page can poll them and draw the steps while they happen."""

    def __init__(self, tpl: TaskTemplate, subject: str, params: dict, *, page: str,
                 asked_by: str | None):
        self.run_id = str(uuid.uuid4())
        self.tpl = tpl
        self.task_id = tpl.task_id
        self.subject = subject
        self.params = dict(params or {})
        self.page = page
        self.asked_by = asked_by
        self.label = tpl.scoped_label(subject)
        self.status = "queued"     # queued routing packing working checking ready blocked failed decided
        self.events: list[dict] = []
        self.proposals: list[Proposal] = []
        self.verdicts: dict[str, Verdict] = {}
        self.pack: Pack | None = None
        self.finding: str | None = None
        self.flags: list[dict] = []
        self.decisions: list[dict] = []
        self.error: str | None = None
        self.models_used: dict[str, str | None] = {}
        self.started_at = now_iso()
        self.ended_at: str | None = None
        self.persisted: dict = {"mode": "memory", "ok": None, "error": None}
        self._lock = threading.Lock()

    # -- events
    def emit(self, agent: Agent, kind: str, text: str, *, rule: str | None = None,
             data: dict | None = None, actor_kind: str = "agent",
             by: str = "code") -> dict:
        with self._lock:
            ev = {"seq": len(self.events) + 1, "at": now_iso(), "agent": agent.name,
                  "agent_key": agent.key, "agent_kind": agent.kind, "kind": kind,
                  "text": text, "rule": rule, "data": data or {},
                  "actor_kind": actor_kind, "by": by}
            self.events.append(ev)
            return ev

    def team(self) -> list[dict]:
        return [ORCHESTRATOR.card(), self.tpl.specialist.card(), RECORDS_CHECKER.card(),
                CANVAS.card()]

    def reviewable(self) -> list[Proposal]:
        return [p for p in self.proposals if p.status == "pending"]

    def view(self, after: int = 0, full: bool = True) -> dict:
        facts = self.pack.facts if self.pack else {}
        out = {"run_id": self.run_id, "task_id": self.task_id, "label": self.label,
               "question": self.tpl.question, "subject": self.subject, "page": self.page,
               "asked_by": self.asked_by, "status": self.status, "error": self.error,
               "started_at": self.started_at, "ended_at": self.ended_at,
               "team": self.team(), "rules": list(self.tpl.rules),
               "events": [e for e in self.events if e["seq"] > after],
               "last_seq": len(self.events),
               "done": self.status in ("ready", "blocked", "failed", "decided"),
               "models": self.models_used, "persisted": self.persisted,
               "verdict_summary": {k: v.result for k, v in self.verdicts.items()},
               "counts": {"proposals": len(self.proposals),
                          "reviewable": len(self.reviewable()),
                          "applied": sum(p.status == "applied" for p in self.proposals),
                          "rejected": sum(p.status == "rejected" for p in self.proposals),
                          "blocked": sum(p.status == "blocked" for p in self.proposals)}}
        if full:
            out.update({"pack": self.pack.view() if self.pack else None,
                        "proposals": [p.view(facts) for p in self.proposals],
                        "verdicts": {k: v.view() for k, v in self.verdicts.items()},
                        "finding": self.finding, "flags": self.flags,
                        "decisions": self.decisions})
        return out


# ------------------------------------------------------------------ models
def _text(content) -> str:
    if isinstance(content, list):
        return "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in content)
    return content or ""


def parse_json_obj(text: str) -> dict | None:
    s = (text or "").strip()
    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", s)
    i, j = s.find("{"), s.rfind("}")
    if i < 0 or j <= i:
        return None
    try:
        obj = json.loads(s[i:j + 1])
    except ValueError:
        return None
    return obj if isinstance(obj, dict) else None


def model_family(endpoint: str | None) -> str:
    """Family of a serving endpoint name: 'databricks-gpt-5-5' -> 'gpt'."""
    return (endpoint or "").removeprefix("databricks-").split("-", 1)[0]


def independent_chain(chain: list[str], answered_by: str | None) -> list[str]:
    """The checker chain without any model of the family that answered (B28.5)."""
    if not answered_by:
        return list(chain)
    fam = model_family(answered_by)
    return [m for m in chain if model_family(m) != fam]


def model_json(ctx: Ctx, chain: list[str], system: str, user: str,
               max_tokens: int = 1800) -> tuple[dict | None, str | None, str | None]:
    """(object, model, error). Tries each model in the chain; never raises."""
    if ctx.call_model is None or not chain:
        return None, None, "no model is configured for this app"
    errs: list[str] = []
    for m in chain:
        try:
            r = ctx.call_model(m, {"messages": [{"role": "system", "content": system},
                                                {"role": "user", "content": user}],
                                   "max_tokens": max_tokens})
            choice = r["choices"][0]
            obj = parse_json_obj(_text(choice["message"]["content"]))
            if obj is None:
                errs.append(f"{m} returned no JSON object (finish_reason "
                            f"{choice.get('finish_reason')})")
                continue
            # On success err names the models that failed first, so a fallback is visible.
            return obj, m, "; ".join(errs) or None
        except Exception as exc:  # noqa: BLE001 - next model, reason kept
            errs.append(f"{m}: {str(exc)[:200]}")
    return None, None, "; ".join(errs) or "no model answered"


SPECIALIST_SYSTEM = """You are the {name} on the Air Carrier SI team, working for the
CVN-79 (USS John F. Kennedy) program office and its financial managers.
Your one job: {job}

You receive records that code packed, Facts that code computed from them, and draft
proposals that code wrote. You explain; you do not decide and you do not compute.

Binding rules:
1. State no number that is not a Fact's display string, copied exactly. No rounding,
   no new totals, no percentages that are not Facts.
2. You may rewrite only the "why" and "proposed" text of a draft proposal, by its key.
   You cannot add, remove or re-address a proposal, or change its rule. goes_to is the
   office that decides; addressed_to, when set, is the office a request is sent to, and
   your "proposed" text must name it.
3. Where the records are silent, say so and leave the blank; never fill it.
4. Name the rule id (in the rules list) behind each step.
5. Plain words a Navy financial manager uses. Short sentences.

Return one JSON object and nothing else:
{{"steps": [{{"text": "...", "rule": "RULE-ID"}}],
 "finding": "two to four sentences",
 "proposals": [{{"key": "...", "why": "...", "proposed": "..."}}],
 "flags": [{{"severity": "high|medium|low", "text": "..."}}]}}"""

CHECKER_SYSTEM = """You are the Records Checker on the Air Carrier SI team. You check;
you never write or fix. You receive Facts that code computed from the packed records,
and an answer another agent wrote. Test every factual statement in the answer
(amounts, counts, dates, contract numbers, offices) against the Facts and records.

Return one JSON object and nothing else:
{"verdict": "SUPPORTED" | "SUPPORTED_WITH_NOTES" | "NOT_SUPPORTED",
 "notes": ["each statement that is unsupported or needs a caveat, quoted"]}
SUPPORTED means every stated fact matches a Fact or record.
The subject, source, context, rules, routing and offices sections were set by code
from the same records; a statement that matches one of them is supported."""


# Rules the system enforces on the specialist's answer, not rules the specialist
# works under: EC-01 is the gate, EC-02 the canvas and checker. A specialist step
# tagged with one of them is mislabelled, so they are neither offered nor accepted.
SYSTEM_RULES = frozenset({"EC-01", "EC-02"})
NOTE_CHARS = 1200        # per checker note; a note cut mid-sentence misleads


def work_rules(rules: dict[str, str]) -> dict[str, str]:
    return {k: v for k, v in rules.items() if k not in SYSTEM_RULES}


def _brief(pack: Pack, proposals: list[Proposal], rules: dict[str, str]) -> dict:
    return {"subject": {"kind": pack.subject_kind, "id": pack.subject_id},
            "source": pack.source, "record_count": len(pack.record_ids),
            "facts": [{"key": f.key, "label": f.label, "display": f.display(),
                       "computation": f.computation} for f in pack.facts.values()],
            "context": pack.public_context(), "records_preview": pack.records[:12],
            "rules": [{"id": r, "text": rules.get(r, "")} for r in rules],
            "draft_proposals": [{"key": p.key, "kind": p.kind, "title": p.title,
                                 "goes_to": p.goes_to_office, "addressed_to": p.addressed_to,
                                 "proposed": p.proposed,
                                 "why": p.why, "rule": p.rule,
                                 "marked_blanks": p.marked_blanks} for p in proposals]}


# ------------------------------------------------------------------ engine
def execute(run: Run, ctx: Ctx, rulebook: dict[str, str],
            on_done: Callable[[Run], None] | None = None) -> Run:
    """Run the six stages. Never raises: a failure is a run state with a reason."""
    tpl, spec = run.tpl, run.tpl.specialist
    rules = {r: rulebook.get(r, "") for r in tpl.rules}
    try:
        # 2 route
        run.status = "routing"
        run.emit(ORCHESTRATOR, "route",
                 f"Asked: {run.label}. One specialist does this job: the {spec.name}.",
                 data={"task_id": tpl.task_id, "specialist": spec.key})
        # 3 pack
        run.status = "packing"
        pack = tpl.packer(ctx, run.subject, run.params)
        run.pack = pack
        run.emit(ORCHESTRATOR, "pack",
                 f"Routed to the {spec.name} with {len(pack.record_ids):,} {pack.noun} "
                 f"from {pack.source}.",
                 data={"record_count": len(pack.record_ids), "provenance_id": pack.provenance_id,
                       "live": pack.live, "read_at": pack.read_at, "series": list(pack.series)})
        for note in pack.notes:
            run.emit(ORCHESTRATOR, "note", note)
        # 4 work: code steps, code draft, then the model explains
        run.status = "working"
        for text, rule in tpl.steps(pack):
            run.emit(spec, "step", text, rule=rule)
        proposals = tpl.draft(pack)
        drafts = {p.key: (p.why, p.proposed) for p in proposals}
        obj, model, err = model_json(
            ctx, ctx.models, SPECIALIST_SYSTEM.format(name=spec.name, job=spec.job),
            json.dumps(_brief(pack, proposals, work_rules(rules)), default=str, ensure_ascii=False),
            max_tokens=6000)
        run.models_used["specialist"] = model
        if obj is not None and err:
            run.emit(spec, "note", f"Answered by the fallback model {model}. {err}",
                     data={"fallback": err})
        if obj is None:
            run.emit(spec, "note", "The specialist model did not answer, so the code draft "
                     f"stands as written. ({err})", data={"error": err})
        else:
            for s in (obj.get("steps") or [])[:8]:
                if isinstance(s, dict) and s.get("text"):
                    rule = s.get("rule") if s.get("rule") in work_rules(rules) else None
                    run.emit(spec, "step", str(s["text"])[:600], rule=rule, by=model)
            by_key = {p.key: p for p in proposals}
            for mp in obj.get("proposals") or []:
                p = by_key.get((mp or {}).get("key")) if isinstance(mp, dict) else None
                if p is None:
                    continue
                if isinstance(mp.get("why"), str) and mp["why"].strip():
                    p.why = mp["why"].strip()[:900]
                    p.drafted_by = model
                if isinstance(mp.get("proposed"), str) and mp["proposed"].strip():
                    p.proposed = mp["proposed"].strip()[:900]
                    p.drafted_by = model
            for fl in (obj.get("flags") or [])[:6]:
                if isinstance(fl, dict) and fl.get("text"):
                    sev = fl.get("severity") if fl.get("severity") in ("high", "medium", "low") \
                        else "medium"
                    run.flags.append({"severity": sev, "text": str(fl["text"])[:400],
                                      "by": model})
            if isinstance(obj.get("finding"), str):
                run.finding = obj["finding"].strip()[:1500]
        run.proposals = proposals
        # 5 check
        run.status = "checking"
        _canvas(run, pack, drafts)
        _records_checker(run, ctx, pack, rules)
        # gate
        cv, mv = run.verdicts["canvas"], run.verdicts["records_checker"]
        for p in run.proposals:
            if p.status != "pending":
                continue
            if cv.result == "fail":
                p.status, p.block_reason = "blocked", "The canvas re-check failed for this run."
            elif mv.result == "fail":
                p.status, p.block_reason = "blocked", ("The Records Checker did not support "
                                                       "the answer.")
        n_ok = len(run.reviewable())
        run.status = "ready" if n_ok else "blocked"
        run.emit(ORCHESTRATOR, "done",
                 f"{n_ok} of {len(run.proposals)} proposals are ready for a person. "
                 "Nothing is saved until a person applies it.", rule="EC-01",
                 data={"reviewable": n_ok, "proposals": len(run.proposals)})
    except Refused as exc:
        run.status, run.error = "failed", str(exc)
        run.emit(ORCHESTRATOR, "refused", str(exc))
    except Exception as exc:  # noqa: BLE001 - a run state, shown to the reader
        run.status, run.error = "failed", f"{type(exc).__name__}: {str(exc)[:400]}"
        run.emit(ORCHESTRATOR, "error", f"The run stopped: {run.error}")
    finally:
        run.ended_at = now_iso()
        if on_done:
            try:
                on_done(run)
            except Exception as exc:  # noqa: BLE001 - the run itself stands
                run.persisted.update(ok=False, error=str(exc)[:300])
    return run


def _canvas(run: Run, pack: Pack, drafts: dict[str, tuple[str, str]]) -> None:
    checks = list(run.tpl.canvas(pack, run.proposals))
    extra = pack.record_numbers()
    dates = pack.record_dates()
    # Ground every sentence. A model sentence with an invented number is put back
    # to the code draft, and the replacement is a recorded check, not a silent fix.
    for p in run.proposals:
        # A request whose model text drops or changes its addressee goes back to
        # the code draft, which names it.
        if (p.addressed_to and p.drafted_by != "code" and p.key in drafts
                and p.addressed_to not in p.proposed):
            p.why, p.proposed = drafts[p.key]
            p.drafted_by = "code"
            p.grounding.append({"reverted": True, "addressee_dropped": p.addressed_to})
            checks.append(check(f"{p.key}: model text reverted to code draft",
                                f"names {p.addressed_to}", "addressee missing", ok=True))
        if p.addressed_to:
            checks.append(check(f"{p.key}: names the office it is addressed to",
                                p.addressed_to, "named" if p.addressed_to in p.proposed
                                else "not named", ok=p.addressed_to in p.proposed))
        bad = ungrounded(p.text(), pack.facts, extra, dates)
        if bad and p.drafted_by != "code" and p.key in drafts:
            p.grounding.append({"reverted": True, "ungrounded": bad})
            p.why, p.proposed = drafts[p.key]
            p.drafted_by = "code"
            checks.append(check(f"{p.key}: model text reverted to code draft",
                                "every number is a packed Fact", ", ".join(bad), ok=True))
            bad = ungrounded(p.text(), pack.facts, extra, dates)
        p.grounding.append({"ungrounded": bad})
        checks.append(check(f"{p.key}: every number is a packed record value",
                            "0 ungrounded", f"{len(bad)} ungrounded" + (
                                f" ({', '.join(bad)})" if bad else ""), ok=not bad))
        if bad:
            p.status = "blocked"
            p.block_reason = f"States {', '.join(bad)}, which is in no packed record."
    finding_bad = ungrounded(run.finding or "", pack.facts, extra, dates)
    if finding_bad:
        run.flags.append({"severity": "high", "by": "canvas",
                          "text": "The finding states " + ", ".join(finding_bad)
                                  + ", which is in no packed record. Read it as unverified."})
    step_bad = [b for e in run.events if e["kind"] == "step" and e["by"] != "code"
                for b in ungrounded(e["text"], pack.facts, extra, dates)]
    checks.append(check("finding and steps: every number is a packed record value",
                        "0 ungrounded", f"{len(finding_bad) + len(step_bad)} ungrounded",
                        ok=not (finding_bad or step_bad)))
    task_fail = [c for c in checks if c["result"] == "fail" and ":" not in c["name"]
                 and not c["name"].startswith("finding and steps")]
    any_fail = any(c["result"] == "fail" for c in checks)
    result = "fail" if task_fail else ("pass_with_notes" if any_fail else "pass")
    v = Verdict("canvas", result, checks,
                notes=("Recomputed from the packed records in code. " +
                       ("A task condition failed." if task_fail else
                        "Every task condition re-tested; results match.")))
    run.verdicts["canvas"] = v
    run.emit(CANVAS, "verdict",
             f"Record check by the canvas: {result.replace('_', ' ').upper()}. "
             f"{v.view()['passed']} of {len(checks)} conditions re-tested pass.",
             rule="EC-02", data=v.view(), actor_kind="system")


def _clip(text: str, n: int) -> str:
    """Cut at a sentence or word end and say so, never mid-word."""
    text = text.strip()
    if len(text) <= n:
        return text
    cut = text[:n]
    end = max(cut.rfind(". "), cut.rfind("; "))
    cut = cut[:end + 1] if end > n // 2 else cut[:cut.rfind(" ")] if " " in cut else cut
    return cut.rstrip() + f" [note cut; {len(text) - len(cut):,} more characters not kept]"


def _records_checker(run: Run, ctx: Ctx, pack: Pack, rules: dict[str, str]) -> None:
    answer = {"finding": run.finding,
              "steps": [e["text"] for e in run.events if e["kind"] == "step"],
              "proposals": [{"title": p.title, "proposed": p.proposed, "why": p.why,
                             "goes_to": p.goes_to_office, "addressed_to": p.addressed_to,
                             "rule": p.rule}
                            for p in run.proposals]}
    # The checker gets what the specialist got, so a name the code supplied
    # (subject, source, routing, rule text) never reads as invented.
    brief = {"subject": {"kind": pack.subject_kind, "id": pack.subject_id},
             "source": pack.source, "record_count": len(pack.record_ids),
             "facts": [{"label": f.label, "display": f.display()} for f in pack.facts.values()],
             "records_preview": pack.records[:12], "context": pack.public_context(),
             "rules": [{"id": r, "text": t} for r, t in rules.items()],
             "routing": [{"proposal": p.title, "goes_to_office": p.goes_to_office,
                          "goes_to_role": p.goes_to_role, "addressed_to": p.addressed_to,
                          "set_by": "code"}
                         for p in run.proposals],
             "offices": [{"role": k, "office": v} for k, v in ctx.offices.items()],
             "answer": answer}
    chain = independent_chain(ctx.checker_models, run.models_used.get("specialist"))
    if ctx.checker_models and not chain:
        obj, model, err = None, None, ("every checker model is the same family as the "
                                       "specialist that answered, so none can check it")
    else:
        obj, model, err = model_json(ctx, chain, CHECKER_SYSTEM,
                                     json.dumps(brief, default=str, ensure_ascii=False), 3000)
    run.models_used["records_checker"] = model
    if obj is None:
        v = Verdict("records_checker", "not_run", [], notes=f"Not run: {err}")
    else:
        raw = str(obj.get("verdict", "")).upper().replace(" ", "_")
        result = {"SUPPORTED": "pass", "SUPPORTED_WITH_NOTES": "pass_with_notes",
                  "NOT_SUPPORTED": "fail"}.get(raw, "error")
        notes = [_clip(str(n), NOTE_CHARS) for n in (obj.get("notes") or []) if n][:8]
        v = Verdict("records_checker", result,
                    [check("answer against the packed records", "SUPPORTED", raw or "none",
                           ok=result in ("pass", "pass_with_notes"))],
                    notes=" ".join(notes), model=model)
    run.verdicts["records_checker"] = v
    label = {"pass": "SUPPORTED. Every stated fact matches a record.",
             "pass_with_notes": "SUPPORTED WITH NOTES.", "fail": "NOT SUPPORTED.",
             "error": "Returned no verdict it could map.",
             "not_run": "Not run."}[v.result]
    run.emit(RECORDS_CHECKER, "verdict", f"{label} {v.notes}".strip(),
             rule="EC-02", data=v.view(), by=model or "none")


def start(run: Run, ctx: Ctx, rulebook: dict[str, str],
          on_done: Callable[[Run], None] | None = None, background: bool = True) -> Run:
    if not background:
        return execute(run, ctx, rulebook, on_done)
    threading.Thread(target=execute, args=(run, ctx, rulebook, on_done),
                     name=f"si-{run.run_id[:8]}", daemon=True).start()
    return run
