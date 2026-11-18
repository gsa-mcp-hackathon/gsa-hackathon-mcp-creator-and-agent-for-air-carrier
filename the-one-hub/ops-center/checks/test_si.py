#!/usr/bin/env python3
"""Tests for the SI layer (app/api/si): routing, packing, both checkers, the
gate, authority and the decision receipt.

Offline by default: the packer reads the shipped transactions extract and the
models are faked, so the known answers below must come out exactly. The LIVE
section runs only when a Spark session exists; it reads (never writes) the UC
tables and checks the same answers plus the File C tie-out.

Known answers (recomputed 2026-11-11, cross-checked with SQL):
  N00024-09-C-2116  948 actions  $4,519,300,323.83
  N00024-15-C-2114  927 actions  $4,578,603,345.77
  File C: 4 of 8 periods tie; FY2021P03 residual $770,407,268.00

Run:
    PYTHONDONTWRITEBYTECODE=1 python3 checks/test_si.py
    in a notebook: runpy.run_path(<this file>, run_name="__main__")
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
sys.dont_write_bytecode = True
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))
os.environ.setdefault("AIRCARRIER_SI_PERSIST", "memory")

from api import data  # noqa: E402
from api.si import sdk, store, tasks  # noqa: E402

T2116 = ("$4,519,300,323.83", 948)
T2114 = ("$4,578,603,345.77", 927)


def reply(obj) -> dict:
    return {"choices": [{"message": {"content": json.dumps(obj)}, "finish_reason": "stop"}]}


def fake_models(specialist: dict | None, checker: dict | None):
    def call(endpoint, body):
        sys_msg = body["messages"][0]["content"]
        obj = checker if sys_msg.startswith("You are the Records Checker") else specialist
        if obj is None:
            raise RuntimeError(f"{endpoint} is down")
        return reply(obj)
    return call


def run(task, subject, params=None, call=None, q_app=None):
    subject = tasks.normalize(task, subject)
    tpl = tasks.route(task, subject)
    ctx = sdk.Ctx(q_app=q_app, data_get=data.get, call_model=call,
                  models=["spec-model"] if call else [], checker_models=["chk-model"] if call else [],
                  offices=dict(tasks.OFFICES))
    r = sdk.Run(tpl, subject, params or {}, page="/mission", asked_by="tester")
    return sdk.execute(r, ctx, tasks.RULEBOOK)


# ------------------------------------------------------------ offline tests
def test_known_totals_from_extract():
    for piid, (disp, n) in (("N00024-09-C-2116", T2116), ("n0002415c2114", T2114)):
        r = run("reconcile_obligations", piid)
        assert r.status == "ready", r.error
        assert r.pack.facts["total"].display() == disp
        assert r.pack.facts["count"].value == str(n)
        assert r.verdicts["canvas"].result == "pass"
        assert r.verdicts["records_checker"].result == "not_run"


def test_e16_mislabel_proposes_relabel():
    r = run("reconcile_obligations", "N00024-09-C-2116",
            {"reported_total": "4519300323.83", "reported_label": "N00024-15-C-2114"})
    kinds = {p.key: p for p in r.proposals}
    assert set(kinds) == {"baseline", "relabel"}
    assert kinds["relabel"].goes_to_role == "PMS379"
    assert T2114[0] in kinds["relabel"].proposed
    assert r.pack.facts["delta"].display() == "$0.00"


def test_reported_mismatch_proposes_correction_with_blank():
    r = run("reconcile_obligations", "N00024-15-C-2114", {"reported_total": "4578603345.78"})
    p = {p.key: p for p in r.proposals}["correct"]
    assert r.pack.facts["delta"].display() == "$0.01"
    assert p.marked_blanks and p.marked_blanks[0]["field"].startswith("As-of date")


def test_refusals():
    for task, subj in (("move_funds", "x"), ("reconcile_obligations", "N00024-16-C-2116"),
                       ("explain_residual", "2021"), ("investigate_gap", "E-16"),
                       ("brief_readiness", "CVN-80")):
        try:
            tasks.route(task, tasks.normalize(task, subj))
        except sdk.Refused:
            continue
        raise AssertionError(f"{task} {subj} was not refused")


def test_residual_offline_reads_shipped_extract():
    # Since 2026-11-12 pack_residual falls back to app/data/extracts/account_funding.json
    # when no warehouse is bound (offline / Advana demo). The pack must say so: live=False
    # and a note naming the extract, so an offline answer is never mistaken for a live one.
    r = run("explain_residual", "FY2021P03")
    assert r.status == "ready", (r.status, r.error)
    assert r.pack.live is False
    assert any("shipped extract" in n for n in r.pack.notes), r.pack.notes
    r = run("explain_residual", "FY2099P03")
    assert r.status == "failed" and "File C has no rows" in r.error, r.error


def test_model_invented_number_is_reverted():
    spec = {"steps": [{"text": "The total is $4,519,300,323.84.", "rule": "OB-01"}],
            "finding": "It is $4,519,300,323.84.",
            "proposals": [{"key": "baseline", "proposed": "Record $4,519,300,323.84 as the baseline."}]}
    r = run("reconcile_obligations", "N00024-09-C-2116",
            call=fake_models(spec, {"verdict": "SUPPORTED", "notes": []}))
    p = r.proposals[0]
    assert p.drafted_by == "code" and T2116[0] in p.proposed, p.proposed
    assert any(g.get("reverted") for g in p.grounding)
    assert any(f["by"] == "canvas" for f in r.flags)          # the finding is flagged
    assert r.verdicts["canvas"].result == "pass_with_notes"   # step text ungrounded
    assert p.status == "pending"                              # reverted text is grounded


def test_grounded_model_text_is_kept():
    spec = {"proposals": [{"key": "baseline",
                           "why": f"All 948 actions sum to {T2116[0]}."}],
            "finding": f"The FPDS total is {T2116[0]}."}
    r = run("reconcile_obligations", "N00024-09-C-2116",
            call=fake_models(spec, {"verdict": "SUPPORTED"}))
    assert r.proposals[0].drafted_by == "spec-model"
    assert r.verdicts["canvas"].result == "pass"
    assert r.verdicts["records_checker"].result == "pass"


def test_checker_not_supported_blocks():
    r = run("reconcile_obligations", "N00024-09-C-2116",
            call=fake_models({}, {"verdict": "NOT_SUPPORTED", "notes": ["x"]}))
    assert r.status == "blocked" and all(p.status == "blocked" for p in r.proposals)


def test_specialist_down_falls_back_to_code():
    r = run("reconcile_obligations", "N00024-09-C-2116",
            call=fake_models(None, {"verdict": "SUPPORTED"}))
    assert r.status == "ready" and r.proposals[0].drafted_by == "code"


def test_checker_never_shares_the_specialists_family():
    """B28.5: the checker chain drops the family that actually answered."""
    assert sdk.model_family("databricks-gpt-6-1-sol") == "gpt"
    assert sdk.model_family("databricks-gemini-3-8-flash") == "gemini"
    spec = {"finding": f"The FPDS total is {T2116[0]}."}

    def go(checker_models):
        seen = []
        base = fake_models(spec, {"verdict": "SUPPORTED"})

        def call(endpoint, body):
            seen.append(endpoint)
            return base(endpoint, body)
        subject = tasks.normalize("reconcile_obligations", "N00024-09-C-2116")
        ctx = sdk.Ctx(q_app=None, data_get=data.get, call_model=call,
                      models=["databricks-gpt-6-1-sol"], checker_models=checker_models,
                      offices=dict(tasks.OFFICES))
        r = sdk.Run(tasks.route("reconcile_obligations", subject), subject, {},
                    page="/mission", asked_by="tester")
        return sdk.execute(r, ctx, tasks.RULEBOOK), seen

    r, seen = go(["databricks-gpt-5-5", "databricks-gemini-3-8-flash"])
    assert r.models_used == {"specialist": "databricks-gpt-6-1-sol",
                             "records_checker": "databricks-gemini-3-8-flash"}, r.models_used
    assert "databricks-gpt-5-5" not in seen, seen
    r, seen = go(["databricks-gpt-5-5"])
    v = r.verdicts["records_checker"]
    assert v.result == "not_run" and "same family" in v.notes, (v.result, v.notes)
    assert seen == ["databricks-gpt-6-1-sol"], seen


def test_tampered_pack_fails_canvas():
    tpl = tasks.TASKS["reconcile_obligations"]
    pack = tpl.packer(sdk.Ctx(q_app=None, data_get=data.get), "N00024-09-C-2116", {})
    pack.facts["total"].value = "4519300323.84"                 # one cent
    checks = tpl.canvas(pack, [])
    bad = {c["name"] for c in checks if c["result"] == "fail"}
    assert "total recomputed in integer cents" in bad
    assert "fiscal-year series adds to the total" in bad
    assert "row count equals the packed record ids" not in bad


def test_labelled_contract_description_is_packed():
    r = run("reconcile_obligations", "N00024-09-C-2116",
            {"reported_total": "4519300323.83", "reported_label": "N00024-15-C-2114"})
    ctx = r.pack.public_context()
    assert ctx["description"] == "construction preparation"
    assert ctx["reported_label_description"] == "detail design and construction"


def test_specialist_cannot_cite_system_rules():
    seen = {}
    spec = {"steps": [{"text": "Checked the sum.", "rule": "EC-02"},
                      {"text": "Nothing saved.", "rule": "EC-01"},
                      {"text": "Summed per action.", "rule": "OB-01"},
                      {"text": "Left the books total blank.", "rule": "EC-03"}]}
    base = fake_models(spec, {"verdict": "SUPPORTED"})

    def call(ep, body):
        if not body["messages"][0]["content"].startswith("You are the Records Checker"):
            seen["rules"] = [x["id"] for x in json.loads(body["messages"][1]["content"])["rules"]]
        return base(ep, body)
    r = run("reconcile_obligations", "N00024-09-C-2116", call=call)
    assert "EC-01" not in seen["rules"] and "EC-02" not in seen["rules"]
    assert "OB-01" in seen["rules"] and "EC-03" in seen["rules"]
    tags = [e["rule"] for e in r.events if e["kind"] == "step" and e["by"] != "code"]
    assert tags == [None, None, "OB-01", "EC-03"], tags
    # the system's own events keep their rules
    assert any(e["rule"] == "EC-02" and e["kind"] == "verdict" for e in r.events)


def test_checker_note_is_cut_at_a_sentence():
    short = "The date 2016-03-04 is not in the Facts."
    long = ("First sentence is fine. " * 80) + "Tail words here"
    r = run("reconcile_obligations", "N00024-09-C-2116",
            call=fake_models({}, {"verdict": "SUPPORTED_WITH_NOTES", "notes": [short, long]}))
    notes = r.verdicts["records_checker"].notes
    assert notes.startswith(short)
    kept = notes[len(short) + 1:]
    assert "[note cut;" in kept and kept.split(" [note cut;")[0].endswith("fine.")
    assert len(kept) <= sdk.NOTE_CHARS + 60
    ev = [e for e in r.events if e["agent"] == "Records Checker"][-1]
    assert ev["text"].endswith("more characters not kept]")      # the event is not cut again


# Identifiers code writes into an answer. Each must be in what the Records
# Checker is sent, or a correct answer reads to it as invented (the FY2021P03
# run on 2026-11-11 was blocked by an unpacked PIID).
IDENT = {"piid": r"N\d{5}-\d{2}-[A-Z]-\d{4}", "gap": r"\bG\d{1,3}\b", "pq": r"PQ-[0-9a-f]{8}",
         "variance": r"\bE-\d{1,2}\b", "tas": r"\b\d{3}-\d{4}/\d{4}-\d{4}-\d{3}\b",
         "mod": r"\b[PA]\d{5}\b", "date": r"\b\d{4}-\d{2}-\d{2}\b",
         "period": r"\bFY\d{4}(?:P\d{2}|Q\d)\b", "role": r"\b(?:PMS379|NAVY_FMO|NAVY_FMC|OUSD_C_FMO)\b",
         "hull": r"\bCVN-\d{2}\b", "usd": r"-?\$[\d,]+\.\d{2}"}


def unpacked(task, subject, params=None, q_app=None) -> list[str]:
    """Run with the specialist silent, capture the checker's real brief, and list
    every code-written identifier or office that brief does not contain."""
    seen = {}

    def call(ep, body):
        if body["messages"][0]["content"].startswith("You are the Records Checker"):
            b = json.loads(body["messages"][1]["content"])
            b.pop("answer")
            seen["brief"] = json.dumps(b, ensure_ascii=False)
            return reply({"verdict": "SUPPORTED"})
        return reply({})
    r = run(task, subject, params, call=call, q_app=q_app)
    assert "brief" in seen, r.error
    brief = seen["brief"]
    texts = [e["text"] for e in r.events if e["kind"] == "step"]
    for p in r.proposals:
        texts += [p.title, p.proposed, p.why, p.goes_to_office, p.goes_to_role]
        texts += [f"{b['field']} {b['who_fills']}" for b in p.marked_blanks]
    missing = set()
    for t in texts:
        for rx in IDENT.values():
            missing |= {tok for tok in re.findall(rx, t or "") if tok not in brief}
        missing |= {o for o in tasks.OFFICES.values() if o in (t or "") and o not in brief}
    return sorted(missing)


def test_checker_sees_every_code_written_identifier():
    for task, subj, params in (("reconcile_obligations", "N00024-09-C-2116", {}),
                               ("reconcile_obligations", "N00024-09-C-2116",
                                {"reported_total": "4519300323.83", "reported_label": "N00024-15-C-2114"}),
                               ("reconcile_obligations", "N00024-15-C-2114", {"reported_total": "1.00"})):
        miss = unpacked(task, subj, params)
        assert not miss, f"{task} {subj}: {miss}"


def test_request_keeps_its_addressee():
    # offline stand-in for the residual request: same code path, a packed draft
    p = sdk.Proposal("request", "collection_request", "Request x", "PMS379", tasks.OFFICES["PMS379"],
                     f"Ask {tasks.OFFICES['NAVY_FMO']} for the detail.", "why", "TO-02",
                     addressed_to=tasks.OFFICES["NAVY_FMO"])
    v = p.view()
    assert v["addressed_to"] == "ASN(FM&C) Office of Financial Operations"
    assert v["goes_to"]["role"] == "PMS379"


def _live_addressee(q):
    """A model that re-addresses a request is put back to the code draft."""
    spec = {"proposals": [{"key": "request", "proposed": "Ask PEO Carriers for the detail."}]}
    r = run("explain_residual", "FY2021P03", q_app=q,
            call=fake_models(spec, {"verdict": "SUPPORTED"}))
    req = {p.key: p for p in r.proposals}["request"]
    assert req.addressed_to == tasks.OFFICES["NAVY_FMO"] and req.goes_to_role == "PMS379"
    assert req.drafted_by == "code" and req.addressed_to in req.proposed
    assert any(g.get("addressee_dropped") for g in req.grounding)
    assert r.verdicts["canvas"].result in ("pass", "pass_with_notes") and req.status == "pending"
    b = run("brief_readiness", "CVN-79", q_app=q)
    acc = {p.key: p for p in b.proposals}["access"]
    assert acc.addressed_to == tasks.ACCESS_TO and tasks.ACCESS_TO in acc.proposed
    assert {p.key: p for p in b.proposals}["draft"].addressed_to is None


def test_authority_decision():
    row = {"evaluated_for": "a@x", "roles": '["PMS379"]', "role_can_act": 1, "holders": 1}
    assert store.authority_decision(row, owner_role="PMS379", office="o", action="apply")["allowed"]
    d = store.authority_decision(dict(row, holders=0), owner_role="OUSD_C_FMO", office="OUSD",
                                 action="apply")
    assert d["reason_code"] == "not_owner" and "No one holds" in d["handoff"]["note"]
    assert store.authority_decision(None, owner_role="PMS379", office="o",
                                    action="apply")["reason_code"] == "no_identity"
    assert store.authority_decision(dict(row, roles="[]"), owner_role="PMS379", office="o",
                                    action="apply")["reason_code"] == "no_role"


def test_decide_receipt_and_refusal():
    r = run("reconcile_obligations", "N00024-09-C-2116",
            {"reported_total": "4519300323.83", "reported_label": "N00024-15-C-2114"})
    r.proposals[1].goes_to_role, r.proposals[1].goes_to_office = "OUSD_C_FMO", "OUSD"

    def q_user(sql, params):
        held = ["PMS379"]
        return [{"evaluated_for": "a@x", "roles": json.dumps(held), "role_can_act": 1,
                 "holders": 1 if params["owner_role"] in held else 0, "component": "PEO"}]
    st = store.Store()
    t = {"role_map": "t_role_map", "authority": "t_authority"}
    rec = store.decide(r, [p.proposal_id for p in r.proposals], "apply", None, q_user, t, st)
    assert rec["text"].startswith("1 of 2 proposals applied by a@x as PMS379")
    assert rec["refused"][0]["reason_code"] == "not_owner"
    assert r.proposals[0].status == "applied" and r.proposals[1].status == "pending"
    again = store.decide(r, [r.proposals[0].proposal_id], "apply", None, q_user, t, st)
    assert not again["done"]
    try:
        store.decide(r, [r.proposals[1].proposal_id], "reject", "", q_user, t, st)
        raise AssertionError("reject without a reason was accepted")
    except ValueError:
        pass
    nobody = store.decide(r, [r.proposals[1].proposal_id], "apply", None, None, t, st)
    assert nobody["refused"][0]["reason_code"] == "no_identity"


def _rows_as_written(r: sdk.Run) -> dict[str, list[dict]]:
    """The rows run_statements() would write, shaped as load_sql() reads them back."""
    t = {k: f"t_{k}" for k in ("agent_runs", "agent_steps", "checker_verdicts", "proposals",
                                "decisions")}
    out = {"run": [], "steps": [], "verdicts": [], "proposals": []}
    for sql, p in store.run_statements(r, t):
        if "t_agent_runs" in sql:
            out["run"].append({"run_id": p["run_id"], "trigger": p["trigger"], "triggered_by": "a@x",
                               "started_at": p["started_at"], "ended_at": p["ended_at"],
                               "subject_kind": p["subject_kind"], "subject_id": p["subject_id"],
                               "specialist": p["specialist"], "outcome": p["outcome"]})
        elif "t_agent_steps" in sql:
            out["steps"] = [{"step_seq": s["seq"], "agent_name": s["agent"], "model_endpoint": s["model"],
                             "rule_id": s["rule"], "output_json": s["output"],
                             "actor_kind": s["actor_kind"], "stepped_at": s["at"]}
                            for s in json.loads(p["steps"])]
        elif "t_checker_verdicts" in sql:
            out["verdicts"].append({"checker_agent": p["checker"], "verdict": p["verdict"],
                                    "checks": p["checks"], "notes": p["notes"],
                                    "model_endpoint": p["model"], "decided_at": p["at"]})
        elif "t_proposals" in sql:
            out["proposals"].append({"proposal_id": p["proposal_id"], "status": p["status"],
                                     "block_reason": p["block_reason"],
                                     "proposed_payload": p["payload"], "rule_id": p["rule_id"]})
    return out, t


def test_loaded_run_shows_decisions_read_on_the_callers_token():
    r = run("reconcile_obligations", "N00024-09-C-2116",
            {"reported_total": "4519300323.83", "reported_label": "N00024-15-C-2114"})
    rows, t = _rows_as_written(r)
    pid = rows["proposals"][0]["proposal_id"]
    rows["proposals"][0]["status"] = "applied"
    sqls = store.load_sql(t)
    got = store.get_run(r.run_id, lambda s, p: next(rows[k] for k, v in sqls.items() if v == s),
                        t, store.Store())
    seen = {}

    def q_user(sql, params):
        seen.update(sql=sql, params=params)
        return [{"decision_id": "d1", "proposal_id": pid, "actor": "u@x", "actor_role": "PMS379",
                 "action": "apply", "notes": None, "authority_basis": "human_applied",
                 "decided_at": "2026-11-12T13:29:33Z"}]
    assert store.load_decisions(got, q_user, t) is None
    assert t["decisions"] in seen["sql"] and json.loads(seen["params"]["proposal_ids"]) == \
        sorted(p.proposal_id for p in got.proposals)
    d = got.view(full=True)["decisions"][0]
    assert (d["action"], d["role"], d["at"], d["title"]) == (
        "apply", "PMS379", "2026-11-12T13:29:33Z", got.proposals[0].title)
    # No token, or a refused read: the page says so instead of showing no decisions.
    assert "your token" in store.load_decisions(got, None, t)
    assert "could not be read" in store.load_decisions(got, lambda s, p: 1 / 0, t)


def test_run_loads_back_from_tables_after_restart():
    r = run("reconcile_obligations", "N00024-09-C-2116",
            {"reported_total": "4519300323.83", "reported_label": "N00024-15-C-2114"})
    rows, t = _rows_as_written(r)
    sqls = store.load_sql(t)

    def q(sql, params):
        assert params == {"run_id": r.run_id}
        return next(rows[k] for k, s in sqls.items() if s == sql)
    st = store.Store()                                   # empty: as after a restart
    got = store.get_run(r.run_id, q, t, st)
    assert got is not None and st.get(r.run_id) is got   # listed in the run log
    a, b = r.view(full=True), got.view(full=True)
    assert b["status"] == a["status"] and b["label"] == a["label"] and b["page"] == a["page"]
    # error and not_run are not verdicts, so no row is written for them (store.py);
    # the step row still says so, and the loaded run shows only written verdicts.
    assert b["verdict_summary"] == {k: v for k, v in a["verdict_summary"].items()
                                    if v in store.VERDICT_TO_TABLE}
    assert [(e["seq"], e["kind"], e["text"]) for e in b["events"]] == \
        [(e["seq"], e["kind"], e["text"]) for e in a["events"]]
    for pa, pb in zip(a["proposals"], b["proposals"]):
        for k in ("proposal_id", "title", "goes_to", "proposed", "why", "status", "figures",
                  "addressed_to", "marked_blanks"):
            assert pa[k] == pb[k], k
    assert "Loaded from the harness tables" in b["persisted"]["note"]
    # A decision recorded elsewhere shows on the next read, not a cached 'pending'.
    rows["proposals"][0]["status"] = "applied"
    again = store.get_run(r.run_id, q, t, st)
    assert again is not got and again.proposals[0].status == "applied"
    # A run started in this process is never replaced by a table read.
    live_run = run("reconcile_obligations", "N00024-09-C-2116")
    st.add(live_run)
    assert store.get_run(live_run.run_id, lambda s, p: 1 / 0, t, st) is live_run
    assert store.get_run("nope", lambda s, p: [], t, st) is None
    assert store.get_run("nope", None, t, st) is None   # no warehouse: memory only


def test_run_statements_shape():
    r = run("reconcile_obligations", "N00024-09-C-2116")
    t = {k: f"t_{k}" for k in ("agent_runs", "agent_steps", "checker_verdicts", "proposals",
                               "decisions", "role_map", "authority")}
    stmts = store.run_statements(r, t)
    assert stmts[0][1]["trigger"] == "si:/mission:reconcile_obligations"
    assert sum(1 for s, _ in stmts if "t_proposals" in s) == len(r.proposals)
    assert "current_user()" in store.decision_statement(t)


def test_rows_satisfy_harness_constraints():
    """The harness tables' CHECK constraints, restated (read 2026-11-11 from
    SHOW TBLPROPERTIES). A run that breaks one fails its whole transaction."""
    cases = [run("reconcile_obligations", "N00024-09-C-2116"),
             run("reconcile_obligations", "N00024-15-C-2114",
                 call=fake_models(None, {"verdict": "SUPPORTED_WITH_NOTES", "notes": ["n"]})),
             run("reconcile_obligations", "N00024-09-C-2116",
                 call=fake_models({"steps": [{"text": "x", "rule": "EC-02"}]}, {"verdict": "??"}))]
    for r in cases:
        rows = store._step_rows(r)
        assert len(rows) == len(r.events)
        for s in rows:   # citation_complete
            assert s["agent"] == "orchestrator" or (s["rule"] and s["rule_version"] is not None
                                                    and s["digest"]), s
            assert s["agent"] == s["agent"].lower() and s["digest"]   # inputs_digest NOT NULL
        relayed = [s for s in rows if json.loads(s["output"]).get("uncited")]
        assert all(json.loads(s["output"])["reported_for"] != "orchestrator" for s in relayed)
        stmts = store.run_statements(r, {k: f"t_{k}" for k in ("agent_runs", "agent_steps",
                                                              "checker_verdicts", "proposals")})
        verdicts = [p["verdict"] for s, p in stmts if "t_checker_verdicts" in s]
        assert set(verdicts) <= {"pass", "pass_with_exception", "fail"}   # verdict_enum
        assert len(verdicts) == sum(v.result in store.VERDICT_TO_TABLE for v in r.verdicts.values())
        assert {p["status"] for s, p in stmts if "t_proposals" in s} <= {
            "pending", "applied", "rejected", "blocked"}                       # status_enum
    assert any(json.loads(s["output"]).get("uncited") for s in store._step_rows(cases[1]))
    assert "pass_with_exception" in [p["verdict"] for s, p in store.run_statements(
        cases[1], {k: f"t_{k}" for k in ("agent_runs", "agent_steps", "checker_verdicts",
                                         "proposals")}) if "t_checker_verdicts" in s]


def test_run_is_one_transaction():
    r = run("reconcile_obligations", "N00024-09-C-2116")
    stmts = store.run_statements(r, {k: f"t_{k}" for k in ("agent_runs", "agent_steps",
                                                          "checker_verdicts", "proposals")})
    sql, params = store.run_transaction(stmts)
    assert sql.startswith("BEGIN ATOMIC") and sql.rstrip().endswith("END")
    assert sql.count("INSERT INTO") == len(stmts)
    used = set(re.findall(r"(?<![:\w]):(\w+)", sql))
    assert used == set(params), (used ^ set(params))      # every placeholder bound, none spare
    assert sum(len(p) for _, p in stmts) == len(params)   # prefixes kept them apart
    assert "array<struct<seq:int" in sql                  # type strings were not rewritten


# ------------------------------------------------------------- live tests
def _spark():
    try:
        from pyspark.sql import SparkSession
        return SparkSession.getActiveSession()
    except Exception:  # noqa: BLE001
        return None


def live_q(spark):
    def q(sql, params=None):
        df = spark.sql(sql, args=params or {}).toPandas()
        out = []
        for rec in df.to_dict("records"):
            out.append({k: (None if v is None or (isinstance(v, float) and v != v)
                            else v if isinstance(v, (int, str)) else str(v)) for k, v in rec.items()})
        return out
    return q


def test_live(spark=None):
    if spark is None:  # under pytest: live check needs a Spark session
        import pytest
        pytest.skip("live check needs a Spark session; run this file as a script")
    os.environ.setdefault("AIRCARRIER_CATALOG", "users")
    os.environ.setdefault("AIRCARRIER_SCHEMA", "xiaobing_shang1_civ")
    q = live_q(spark)
    for piid, (disp, n) in (("N00024-09-C-2116", T2116), ("N00024-15-C-2114", T2114)):
        r = run("reconcile_obligations", piid, q_app=q)
        assert r.pack.live and r.pack.facts["total"].display() == disp and len(r.pack.records) == n
    r = run("explain_residual", "FY2021P03", q_app=q)
    assert r.pack.facts["residual"].display() == "$770,407,268.00", r.error
    assert run("explain_residual", "FY2019Q3", q_app=q).pack.facts["ties"].value == "yes"
    for task, subj in (("explain_residual", "FY2021P03"), ("explain_residual", "FY2019Q3"),
                       ("investigate_gap", "G46"), ("investigate_gap", "G52"),
                       ("brief_readiness", "CVN-79")):
        miss = unpacked(task, subj, q_app=q)
        assert not miss, f"{task} {subj}: {miss}"
    _live_addressee(q)
    from api.si import picture
    P = picture.build(q, data.get, store.Store())
    assert sum(1 for x in P["file_c"] if x["ties"]) == 4 and len(P["file_c"]) == 8
    assert P["sources"]["failed"] == []


if __name__ == "__main__":
    fails = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and not name.startswith("test_live"):
            try:
                fn()
                print("PASS", name)
            except Exception as exc:  # noqa: BLE001
                fails += 1
                print("FAIL", name, type(exc).__name__, exc)
    sp = _spark()
    if sp is None:
        print("SKIP test_live (no Spark session)")
    else:
        try:
            test_live(sp)
            print("PASS test_live")
        except Exception as exc:  # noqa: BLE001
            fails += 1
            print("FAIL test_live", type(exc).__name__, exc)
    print("failures:", fails)
    if fails:
        raise SystemExit(1)
