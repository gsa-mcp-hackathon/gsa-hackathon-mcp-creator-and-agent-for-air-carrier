"""Work queue: envelopes, authority rendering, apply and reject routes.

Offline. Statements are answered by a fake keyed on the SQL text, so this
runs anywhere with fastapi and jinja2:

    python -m pytest -q checks/test_work.py

What the warehouse itself decides (the authority rule, the transaction, the
rollback, idempotent replay) is verified against scratch tables by
checks/test_work_live.py on Databricks; see docs/API_SPEC.md section 6.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402
from api import envelopes as E  # noqa: E402
from api import harness as work  # noqa: E402
from api import harness_sql as H  # noqa: E402
from api import identity  # noqa: E402


# ----------------------------------------------------------------- envelopes
def test_money_keeps_every_digit():
    assert E.display_money("6000000.00") == "$6,000,000.00"
    assert E.display_money("-12.345") == "-$12.345"          # not rounded to cents
    assert E.display_money("0.10") == "$0.10"
    assert E.display_money("1234567890123456.78") == "$1,234,567,890,123,456.78"


def test_unknown_figure_has_no_value_and_says_why():
    f = E.figure(figure_id="x", label="L", value=None, unit="USD", as_of=None, record_ids=[],
                 computation="c", source="s", unknown_reason="no feed")
    assert (f["state"], f["value"], f["display"], f["state_reason"]) == ("unknown", None, None, "no feed")
    bad = E.figure(figure_id="x", label="L", value="n/a", unit="USD", as_of=None, record_ids=[],
                   computation="c", source="s")
    assert bad["state"] == "unknown" and "not a number" in bad["state_reason"]


def test_figure_staleness_is_a_window_on_as_of():
    from datetime import datetime, timezone
    now = datetime(2026, 11, 11, 12, tzinfo=timezone.utc)
    fresh = E.figure(figure_id="x", label="L", value="1", unit="USD", as_of="2026-11-11T03:00:00Z",
                     record_ids=["r"], computation="c", source="s", now=now)
    old = E.figure(figure_id="x", label="L", value="1", unit="USD", as_of="2026-09-22T03:00:00Z",
                   record_ids=["r"], computation="c", source="s", now=now)
    assert (fresh["stale"], old["stale"]) == (False, True)
    assert fresh["provenance"]["layer"] is None and fresh["provenance"]["layer_note"]


# --------------------------------------------------------- provenance IDs (A-13)
def test_provenance_id_is_deterministic_and_stable():
    """Same inputs → same provenance_id, different inputs → different id."""
    kw = dict(figure_id="x", label="L", value="1", unit="USD", as_of="2026-11-11T03:00:00Z",
              record_ids=["r1", "r2"], computation="c", source="s")
    f1 = E.figure(**kw)
    f2 = E.figure(**kw)
    assert f1["provenance"]["provenance_id"] == f2["provenance"]["provenance_id"]
    assert len(f1["provenance"]["provenance_id"]) == 16
    # Different record_ids → different id
    f3 = E.figure(**{**kw, "record_ids": ["r3"]})
    assert f3["provenance"]["provenance_id"] != f1["provenance"]["provenance_id"]


def test_provenance_id_ignores_record_order():
    """record_ids [a,b] and [b,a] produce the same provenance_id."""
    kw = dict(figure_id="x", label="L", value="1", unit="USD", as_of=None,
              computation="c", source="s")
    f1 = E.figure(**kw, record_ids=["b", "a"])
    f2 = E.figure(**kw, record_ids=["a", "b"])
    assert f1["provenance"]["provenance_id"] == f2["provenance"]["provenance_id"]


def test_provenance_has_records_href():
    f = E.figure(figure_id="x", label="L", value="1", unit="USD", as_of=None,
                 record_ids=["r1"], computation="c", source="s")
    pid = f["provenance"]["provenance_id"]
    assert f["provenance"]["records_href"] == f"/api/v1/provenance/{pid}/records"


def test_provenance_cache_and_lookup():
    """figure() caches the provenance, get_provenance() retrieves it."""
    E._provenance_cache.clear()
    f = E.figure(figure_id="cached", label="L", value="1", unit="USD", as_of=None,
                 record_ids=["r1"], computation="c", source="s")
    pid = f["provenance"]["provenance_id"]
    prov = E.get_provenance(pid)
    assert prov is not None
    assert prov["provenance_id"] == pid
    assert prov["record_ids"] == ["r1"]
    assert prov["source"] == "s"
    assert E.get_provenance("nonexistent_id") is None


def test_provenance_cache_eviction():
    E._provenance_cache.clear()
    old_max = E._PROVENANCE_CACHE_MAX
    E._PROVENANCE_CACHE_MAX = 3
    try:
        pids = []
        for i in range(5):
            f = E.figure(figure_id=f"evict_{i}", label="L", value="1", unit="USD",
                         as_of=None, record_ids=[], computation="c", source="s")
            pids.append(f["provenance"]["provenance_id"])
        # The first two should be evicted, the last three still present
        assert E.get_provenance(pids[0]) is None
        assert E.get_provenance(pids[1]) is None
        assert E.get_provenance(pids[2]) is not None
        assert E.get_provenance(pids[3]) is not None
        assert E.get_provenance(pids[4]) is not None
    finally:
        E._PROVENANCE_CACHE_MAX = old_max
        E._provenance_cache.clear()


def test_verdict_states():
    assert E.verdict(None, not_checked_reason="r")["state"] == "not_checked"
    err = {"verdict": "fail", "checks_json": json.dumps(
        [{"check_name": "proposal", "expected": "p"},
         {"check_name": "proposal_review", "actual": "error", "result": "fail"}])}
    v = E.verdict(err, not_checked_reason="r")
    assert v["state"] == "error"                                   # outage is not a judgment (F6)
    assert [c["check_name"] for c in v["checks"]] == ["proposal_review"]   # link row hidden


def test_step_output_decodes_both_encodings():
    obj = {"status": "blocked_no_source"}
    assert E.step_output(json.dumps(obj)) == obj
    assert E.step_output(json.dumps(json.dumps(obj))) == obj           # rows before 2026-11-11
    assert E.step_output("not json") == {"unparsed": "not json"}


# --------------------------------------------------------- payload typing (A-17)
def test_looks_like_money():
    assert E._looks_like_money("dollar_amount", "6000000.00") is True
    assert E._looks_like_money("cip_value", "1234.56") is True
    assert E._looks_like_money("total_cost", 100) is True
    assert E._looks_like_money("eac", "12345678.90") is True
    assert E._looks_like_money("budget_variance", "-42.5") is True
    assert E._looks_like_money("threshold", "0") is True
    # Not money: name doesn't match
    assert E._looks_like_money("status", "100.00") is False
    assert E._looks_like_money("resolution", "6000000.00") is False
    # Not money: value doesn't parse
    assert E._looks_like_money("dollar_amount", "cleared") is False
    assert E._looks_like_money("dollar_amount", None) is False
    assert E._looks_like_money("dollar_amount", [1, 2]) is False


def test_payload_field_wraps_money_as_figure():
    pf = E.payload_field("dollar_amount", "6000000.00", proposal_id="p1",
                         rule_id="CC-02", rule_version=4,
                         grounding=[{"field": "dollar_amount", "document_id": "doc1",
                                     "page": 3, "text_span": "$6M"}])
    assert pf["typed"] == "figure"
    assert pf["field"] == "dollar_amount"
    fig = pf["figure"]
    assert fig["state"] == "known"
    assert fig["display"] == "$6,000,000.00"
    assert fig["unit"] == "USD"
    assert fig["figure_id"] == "proposal.p1.dollar_amount"
    assert "doc1 p.3" in fig["provenance"]["computation"]
    assert fig["provenance"]["rule"]["rule_id"] == "CC-02"


def test_payload_field_leaves_status_as_text():
    pf = E.payload_field("status", "cleared")
    assert pf["typed"] == "text" and pf["value"] == "cleared"
    pf2 = E.payload_field("resolution", "match to voucher")
    assert pf2["typed"] == "text" and pf2["value"] == "match to voucher"


def test_typed_payload_mixed_fields():
    items = E.typed_payload(
        {"dollar_amount": "500.00", "status": "escalated", "cip_value": "1000000.00"},
        proposal_id="px", rule_id="R1", rule_version=1)
    assert len(items) == 3
    assert items[0]["typed"] == "figure" and items[0]["field"] == "dollar_amount"
    assert items[1]["typed"] == "text" and items[1]["field"] == "status"
    assert items[2]["typed"] == "figure" and items[2]["field"] == "cip_value"


# --------------------------------------------------------- step timestamps (A-6)
def test_steps_for_run_selects_stepped_at():
    """A-6: the query now includes stepped_at."""
    t = H.tables()
    sql = H.steps_for_run(t)
    assert "stepped_at" in sql


def test_step_timestamp_renders_on_card(client):
    """A-6: stepped_at shows as a <time> element on each evidence step."""
    # Override Fake to return a run with steps that have stepped_at
    RUN = {"run_id": "run1", "specialist": "cost_capture_specialist",
           "started_at": "2026-11-11T04:05:00Z", "ended_at": "2026-11-11T04:06:00Z",
           "outcome": "completed", "trigger": "rule_eval"}
    STEP = {"step_seq": 1, "agent_name": "cost_capture_specialist", "agent_version": "v1",
            "model_endpoint": "m", "rule_id": "CC-02", "rule_version": 4,
            "record_ids": '["rec-1"]', "output_json": '{"status": "open"}',
            "stepped_at": "2026-11-11T04:05:12Z"}
    c, fake = client()
    orig_call = fake.__call__.__func__

    def patched(self, sql, params=None):
        if "agent_runs" in sql and "subject_id" in sql:
            return [RUN]
        if "agent_steps" in sql and "run_id" in sql:
            return [STEP]
        return orig_call(self, sql, params)

    fake.__class__.__call__ = patched
    try:
        html = c.get("/work/exceptions/e1").text
        assert "2026-11-11T04:05:12Z" in html
        assert "<time" in html
    finally:
        fake.__class__.__call__ = orig_call


# ---------------------------------------------------------- actor columns (A-8)
def test_actor_envelope_includes_authority_basis():
    """A-8: actor() returns authority_basis field."""
    a = E.actor("agent", "specialist", authority_basis="agent_own")
    assert a["authority_basis"] == "agent_own"
    assert a["kind"] == "agent"
    a2 = E.actor("human", "user@x", role="PMS379", authority_basis="human_applied")
    assert a2["authority_basis"] == "human_applied"
    a3 = E.actor("agent", "x")  # no basis supplied
    assert a3["authority_basis"] is None


def test_steps_query_includes_actor_columns():
    """A-8: steps_for_run now selects actor_kind and authority_basis."""
    t = H.tables()
    sql = H.steps_for_run(t)
    assert "actor_kind" in sql
    assert "authority_basis" in sql


def test_decisions_query_includes_actor_columns():
    """A-8: decisions_for_exception now selects actor_kind and authority_basis."""
    t = H.tables()
    sql = H.decisions_for_exception(t)
    assert "actor_kind" in sql
    assert "authority_basis" in sql


def test_apply_block_writes_actor_columns():
    """A-8: apply_block SQL writes actor_kind and authority_basis to decisions."""
    t = H.tables()
    sql = H.apply_block(t)
    assert "actor_kind" in sql
    assert "authority_basis" in sql
    assert "human_applied" in sql
    assert "human_rejected" in sql


def test_authority_basis_renders_on_step(client):
    """A-8: authority_basis='agent_own' shows as a badge on a step."""
    RUN = {"run_id": "run1", "specialist": "cost_capture_specialist",
           "started_at": "2026-11-11T04:05:00Z", "ended_at": "2026-11-11T04:06:00Z",
           "outcome": "completed", "trigger": "rule_eval"}
    STEP = {"step_seq": 1, "agent_name": "cost_capture_specialist", "agent_version": "v1",
            "model_endpoint": "m", "rule_id": "CC-02", "rule_version": 4,
            "record_ids": '["rec-1"]', "output_json": '{"kind": "finding", "text": "done", "truncated": false}',
            "stepped_at": "2026-11-11T04:05:12Z", "actor_kind": "agent",
            "authority_basis": "agent_own"}
    c, fake = client()
    orig_call = fake.__call__.__func__

    def patched(self, sql, params=None):
        if "agent_runs" in sql and "subject_id" in sql:
            return [RUN]
        if "agent_steps" in sql and "run_id" in sql:
            return [STEP]
        return orig_call(self, sql, params)

    fake.__class__.__call__ = patched
    try:
        html = c.get("/work/exceptions/e1").text
        assert 'data-authority="agent_own"' in html
        assert "agent_own" in html
    finally:
        fake.__class__.__call__ = orig_call


# ----------------------------------------------------------- rule register (step 4)
def test_rule_list_sql_has_open_counts():
    """rule_list joins current_rules with open-exception counts."""
    t = H.tables()
    sql = H.rule_list(t)
    assert "open_count" in sql
    assert "open_dollars" in sql
    assert "current_rules" in sql
    assert ":area" in sql
    assert ":status" in sql
    assert ":owner_role" in sql


def test_rule_detail_sql_returns_all_versions():
    """rule_detail returns all versions for a rule."""
    t = H.tables()
    sql = H.rule_detail(t)
    assert "rule_register" in sql
    assert ":rule_id" in sql
    assert "ORDER BY version DESC" in sql
    # A-30: derived lifecycle, same rule as current_rules (newer effective version)
    assert "'superseded'" in sql and "AS lifecycle" in sql and "AS superseded_by" in sql
    assert "PARTITION BY rule_id" in sql and "effective_from <= current_timestamp()" in sql


def test_escalation_amount_names_parent_a28():
    """A-28: an escalation has no amount of its own; the card says where it is."""
    base = {"exception_id": "x2", "rule_id": "CC-02", "rule_version": 6,
            "detected_at": "2026-11-11T00:00:00Z", "eval_id": "e1", "dollar_amount": None}
    f = work.amount_figure(base | {"subject_type": "exception", "subject_ids": ["p-1"]})
    assert f["state"] == "unknown" and not re.search(r"\d{1,3},\d{3}", f["display"] or "")
    assert "Escalation of exception p-1" in f["state_reason"]
    assert "not counted again" in f["state_reason"]
    g = work.amount_figure(base | {"subject_type": "reconciliation_item", "subject_ids": ["w"]})
    assert g["state_reason"] == "The rule that raised this exception returns no dollar amount."
    h = work.amount_figure(base | {"subject_type": "exception", "subject_ids": ["p-1"],
                                   "dollar_amount": "6000000.00"})
    assert h["state"] == "known"   # older rows that stored an amount still show it


def test_rule_audit_sql():
    """rule_audit returns the audit log."""
    t = H.tables()
    sql = H.rule_audit(t)
    assert "rule_register_audit" in sql
    assert ":rule_id" in sql
    # the audit column is event_at; there is no column named at (A-30 fix)
    assert "ORDER BY event_at DESC" in sql and "version, actor, event" in sql


def test_api_rules_route(client):
    """GET /api/v1/rules returns a list."""
    c, fake = client()
    orig_call = fake.__call__.__func__

    def patched(self, sql, params=None):
        if "current_rules" in sql:
            return [{"rule_id": "CC-02", "version": 4, "status": "active",
                     "blocked_reason": None, "statement_text": "Test rule",
                     "params": "{}", "value_lists": None,
                     "owner_role": "PMS379", "owner_office": "PEO Carriers",
                     "required_action": "Reconcile", "area": "cost_capture",
                     "effective_from": "2026-11-01T00:00:00Z", "effective_to": None,
                     "open_count": 2, "open_dollars": 9000000.0}]
        return orig_call(self, sql, params)

    fake.__class__.__call__ = patched
    try:
        resp = c.get("/api/v1/rules")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["rules"]) == 1
        assert data["rules"][0]["rule_id"] == "CC-02"
        assert data["rules"][0]["open_count"]["display"] == "2"
    finally:
        fake.__class__.__call__ = orig_call


def test_api_rule_detail_route(client):
    """GET /api/v1/rules/{rule_id} returns versions and audit."""
    c, fake = client()
    orig_call = fake.__call__.__func__
    RULE_ROW = {"rule_id": "CC-02", "version": 4, "status": "active",
                "blocked_reason": None, "statement_text": "Test",
                "expression_sql": "SELECT 1", "params": "{}", "value_lists": None,
                "owner_role": "PMS379", "owner_office": "PEO Carriers",
                "required_action": "Reconcile", "area": "cost_capture",
                "effective_from": "2026-11-01T00:00:00Z", "effective_to": None,
                "created_by": "x", "created_at": "2026-11-01T00:00:00Z"}
    AUDIT_ROW = {"actor": "x", "event": "created", "prior_params": None,
                 "new_params": "{}", "notes": "init", "at": "2026-11-01T00:00:00Z"}

    def patched(self, sql, params=None):
        if "rule_register_audit" in sql:
            return [AUDIT_ROW]
        if "rule_register" in sql and "rule_id" in sql:
            return [RULE_ROW]
        return orig_call(self, sql, params)

    fake.__class__.__call__ = patched
    try:
        resp = c.get("/api/v1/rules/CC-02")
        assert resp.status_code == 200
        data = resp.json()
        assert data["rule_id"] == "CC-02"
        assert len(data["versions"]) == 1
        assert len(data["audit"]) == 1
    finally:
        fake.__class__.__call__ = orig_call


def test_api_rule_404(client):
    """GET /api/v1/rules/{rule_id} returns 404 for unknown rule."""
    c, fake = client()
    orig_call = fake.__call__.__func__

    def patched(self, sql, params=None):
        # Return empty for rule_register queries (rule_detail)
        if "rule_register" in sql and "ORDER BY version DESC" in sql:
            return []
        if "rule_register_audit" in sql:
            return []
        return orig_call(self, sql, params)

    fake.__class__.__call__ = patched
    try:
        resp = c.get("/api/v1/rules/NONEXISTENT")
        assert resp.status_code == 404
    finally:
        fake.__class__.__call__ = orig_call


# ---------------------------------------------------------- preview (build step 4)
def test_bind_expression_substitutes_tables():
    """bind_expression replaces {EXCEPTIONS} etc. with the app's FQN."""
    t = H.tables()
    sql = "SELECT * FROM {EXCEPTIONS} WHERE amount > :threshold"
    bound, args = H.bind_expression(sql, t, {"threshold": "1000"})
    assert t["exceptions"] in bound
    assert "{EXCEPTIONS}" not in bound
    assert args == {"threshold": "1000"}


def test_bind_expression_no_params():
    t = H.tables()
    sql = "SELECT 1 FROM {RULE_REGISTER}"
    bound, args = H.bind_expression(sql, t, None)
    assert t["rule_register"] in bound
    assert args == {}


def test_rule_for_preview_sql():
    t = H.tables()
    sql = H.rule_for_preview(t)
    assert "expression_sql" in sql
    assert "current_rules" in sql
    assert ":rule_id" in sql


def test_preview_returns_before_after(client):
    """POST /rules/{rule_id}/preview returns spec-shaped before/after/delta."""
    c, fake = client()
    orig_call = fake.__call__.__func__
    RULE = {"rule_id": "CC-02", "version": 4,
            "expression_sql": "SELECT 'rec1' AS exception_id, 500.0 AS dollar_amount",
            "params": "{}", "value_lists": None, "owner_role": "PMS379",
            "owner_office": "PEO Carriers", "required_action": "Reconcile",
            "area": "cost_capture"}
    HIT = {"exception_id": "rec1", "dollar_amount": 500.0}

    def patched(self, sql, params=None):
        if "current_rules" in sql and ":rule_id" in sql:
            return [RULE]
        # The bound expression_sql: just return the hit
        if "SELECT 'rec1'" in sql or "SELECT" in sql and "exception_id" in sql:
            return [HIT]
        return orig_call(self, sql, params)

    fake.__class__.__call__ = patched
    try:
        resp = c.post("/api/v1/rules/CC-02/preview",
                      json={"base_version": 4})
        assert resp.status_code == 200
        data = resp.json()
        assert data["rule_id"] == "CC-02"
        assert data["base_version"] == 4
        assert "preview_id" in data
        assert "before" in data and "after" in data and "delta" in data
        assert data["added_count"] == 0  # same params -> same results
        assert data["removed_count"] == 0
        assert "added_href" in data
        assert "removed_href" in data
        assert "expires_at" in data
    finally:
        fake.__class__.__call__ = orig_call


def test_preview_stale_version(client):
    """POST preview returns 409 if base_version doesn't match current."""
    c, fake = client()
    orig_call = fake.__call__.__func__
    RULE = {"rule_id": "CC-02", "version": 4,
            "expression_sql": "SELECT 1", "params": "{}", "value_lists": None,
            "owner_role": "PMS379", "owner_office": "PEO Carriers",
            "required_action": "Reconcile", "area": "cost_capture"}

    def patched(self, sql, params=None):
        if "current_rules" in sql:
            return [RULE]
        return orig_call(self, sql, params)

    fake.__class__.__call__ = patched
    try:
        resp = c.post("/api/v1/rules/CC-02/preview",
                      json={"base_version": 3})  # stale!
        assert resp.status_code == 409
        assert "stale" in resp.json()["detail"]
    finally:
        fake.__class__.__call__ = orig_call


def test_preview_404_unknown_rule(client):
    """POST preview returns 404 for unknown rule."""
    c, fake = client()
    orig_call = fake.__call__.__func__

    def patched(self, sql, params=None):
        if "current_rules" in sql:
            return []
        return orig_call(self, sql, params)

    fake.__class__.__call__ = patched
    try:
        resp = c.post("/api/v1/rules/NONEXISTENT/preview",
                      json={"base_version": 1})
        assert resp.status_code == 404
    finally:
        fake.__class__.__call__ = orig_call


def test_preview_refuses_derived_rule_while_source_inactive_a29():
    """A-29: preview of CC-02 is a 409 naming CC-01's state; it never runs the SQL."""
    from fastapi import HTTPException
    ran = []

    def q(sql, params, current=({"rule_id": "CC-02", "params": '{"source_rule": "CC-01"}'},)):
        if "FROM" in sql and "current_rules" in sql and "expression_sql" in sql:
            return [{"rule_id": "CC-02", "version": 6, "expression_sql": "SELECT e.exception_id "
                     "AS parent_exception_id FROM {EXCEPTIONS} e", "params": '{"source_rule": "CC-01"}'}]
        if sql.startswith("SELECT rule_id, params FROM"):
            return list(current)
        if "blocked_reason FROM" in sql:
            return [{"version": 1, "status": "blocked_no_source", "blocked_reason": None}]
        ran.append(sql)
        return []
    with pytest.raises(HTTPException) as e:
        work.preview_rule(q, "CC-02", 6)
    assert e.value.status_code == 409 and not ran
    assert "source rule CC-01 has no version in effect (latest v1, blocked_no_source)" in e.value.detail
    assert work._parent_gate(q, H.tables(), "CM-01", {"x": "1"}) is None   # not derived


def test_preview_cache_and_added_endpoint(client):
    """GET /preview/{id}/added returns cached data from a preview."""
    from api import harness as W
    # Manually cache a preview
    from datetime import datetime, timezone, timedelta
    pid = "test-preview-id"
    W._preview_cache[pid] = {
        "rule_id": "CC-02", "preview_id": pid,
        "added": [["rec-new-1"], ["rec-new-2"]],
        "removed": [["rec-old-1"]],
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=5),
    }
    try:
        c, _ = client()
        resp = c.get(f"/api/v1/rules/CC-02/preview/{pid}/added")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

        resp2 = c.get(f"/api/v1/rules/CC-02/preview/{pid}/removed")
        assert resp2.status_code == 200
        assert resp2.json()["total"] == 1
    finally:
        W._preview_cache.pop(pid, None)


def test_preview_expired_returns_404(client):
    """GET /preview/{id}/added returns 404 for expired preview."""
    from api import harness as W
    from datetime import datetime, timezone, timedelta
    pid = "expired-preview"
    W._preview_cache[pid] = {
        "added": [], "removed": [],
        "expires_at": datetime.now(timezone.utc) - timedelta(minutes=1),
    }
    try:
        c, _ = client()
        resp = c.get(f"/api/v1/rules/CC-02/preview/{pid}/added")
        assert resp.status_code == 404
    finally:
        W._preview_cache.pop(pid, None)


# ----------------------------------------------------------------- SQL shape
def test_one_authority_rule_for_render_and_write():
    t = H.tables("apptest_")
    assert H.authority_check(t).strip() in H.apply_block(t)
    for code in H.REASON_CODES:
        assert f"'{code}'" in H.authority_check(t), code
    assert "current_user()" in H.authority_check(t)
    assert "target_table = 'proposals'" in H.authority_check(t)   # never the agent's target_table


def test_statements_take_no_role_input():
    t = H.tables()
    for sql in (H.authority_check(t), H.apply_block(t)):
        markers = set(re.findall(r":([a-z_]+)", sql)) - {"mm", "ss"}
        assert markers <= {"proposal_id", "action", "confirmed_records", "request_id", "notes"}, markers


# ----------------------------------------------------------------- routes
EXC = {"exception_id": "e1", "rule_id": "CC-02", "rule_version": 4, "subject_type": "reconciliation_item",
       "subject_ids": '["rec-1","rec-2"]', "detected_at": "2026-11-11T03:00:00Z",
       "dollar_amount": "6000000.00", "owner_role": "PMS379", "owner_office": "PEO Carriers",
       "required_action": "Reconcile", "window_closes_at": None, "status": "open",
       "area": "cost_capture", "eval_id": "ev1", "last_run_at": None, "last_run_outcome": None}
PROP = {"proposal_id": "p1", "run_id": "run1", "target_table": "exceptions", "target_key": "k",
        "proposed_payload": '{"resolution": "match to voucher"}', "grounding_json": None,
        "status": "pending", "block_reason": None, "intake_outcome": None, "rule_id": "CC-02",
        "rule_version": 4, "record_ids": '["rec-1","rec-2"]', "created_at": "2026-11-11T04:00:00Z",
        "verdict": "pass", "checks_json": "[]", "verdict_notes": None, "checker_agent": "harness_checker",
        "checker_model": "m", "verdict_at": "2026-11-11T04:01:00Z"}


class Fake:
    """Answers each statement by its shape. authority maps action -> reason_code."""

    def __init__(self, authority=None, outcome="allowed", prop=None, decisions=()):
        self.authority = authority or {"apply": "allowed", "reject": "allowed"}
        self.outcome = outcome
        self.prop = dict(PROP, **(prop or {}))
        self.decisions = list(decisions)
        self.calls: list[tuple[str, dict]] = []

    def __call__(self, sql, params=None):
        params = params or {}
        self.calls.append((sql, params))
        if "BEGIN ATOMIC" in sql:
            return [{"reason_code": self.outcome, "reason": "because", "decision_id": "d1",
                     "role_used": "PMS379", "evaluated_for": "u@x", "replayed": "false"}]
        if "WITH p AS" in sql:
            code = self.authority[params["action"]]
            return [{"reason_code": code, "reason": f"reason:{code}", "role_used": "PMS379",
                     "component": "PEO Carriers", "exception_id": "e1", "owner_role": "PMS379",
                     "evaluated_for": "u@x"}]
        if "SELECT rule_id, version FROM" in sql and "current_rules" in sql:
            return [{"rule_id": "CC-02", "version": 4}]
        if "collect_set(area)" in sql:
            return [{"area": '["cost_capture"]', "status": '["open"]', "owner_role": '["PMS379"]',
                     "rule_id": '["CC-02"]'}]
        if "GROUP BY status" in sql and "count(*) AS n" in sql:
            return [{"status": "open", "n": 1}]
        if "count(*) AS n" in sql:
            return [{"n": 1}]
        if "max_by(outcome" in sql or "x.exception_id = :exception_id" in sql:
            return [EXC]
        if "FROM " in sql and "rule_register" in sql:
            return [{"rule_id": "CC-02", "version": 4, "statement_text": "An item unresolved past its window.",
                     "params_json": "{}", "status": "active", "owner_role": "PMS379",
                     "owner_office": "PEO Carriers", "required_action": "Reconcile", "area": "cost_capture",
                     "blocked_reason": None, "effective_from": "2026-11-01T00:00:00Z", "created_by": "x"}]
        if "WITH lv AS" in sql:
            return [self.prop]
        if "authority_check_result" in sql:
            return self.decisions
        return []


@pytest.fixture
def client(monkeypatch):
    def make(token=True, **kw):
        fake = Fake(**kw)
        ident = identity.Identity(email="u@x", token="t" if token else None)
        monkeypatch.setattr(work, "runners", lambda request: (ident, fake, fake if token else None))
        return TestClient(main.app), fake
    return make


def _enabled_links(html):
    return re.findall(r'<a class="btn[^"]*" href="(/work/proposals/[^"]+)"', html)


def test_list_renders_figures_not_bare_numbers(client):
    c, _ = client()
    html = c.get("/work?view=table").text
    assert "$6,000,000.00" in html and 'data-figure="exception.e1.dollar_amount"' in html
    assert "6000000.00 USD" in html                         # the stored value, inside provenance
    assert re.search(r">\s*6000000(\.00)?\s*<", html) is None   # never as bare cell text


def test_card_shows_citation_verdict_and_enabled_actions(client):
    c, _ = client()
    html = c.get("/work/exceptions/e1").text
    assert "Rule <b>CC-02</b> v4" in html and "<code>rec-1</code>" in html
    assert "Checker: pass" in html
    assert sorted(_enabled_links(html)) == [
        "/work/proposals/p1/confirm?action=apply&amp;exception_id=e1",
        "/work/proposals/p1/confirm?action=reject&amp;exception_id=e1"]


def test_refused_authority_is_a_disabled_control_with_reason(client):
    c, _ = client(authority={"apply": "not_owner", "reject": "not_owner"})
    html = c.get("/work/exceptions/e1").text
    assert _enabled_links(html) == []
    assert html.count("reason:not_owner") == 2 and html.count("disabled aria-disabled") == 2


def test_no_token_is_read_only_and_runs_no_authority_statement(client):
    c, fake = client(token=False)
    html = c.get("/work/exceptions/e1").text
    assert "Read only." in html and _enabled_links(html) == []
    assert not any("WITH p AS" in s or "BEGIN ATOMIC" in s for s, _ in fake.calls)
    r = c.post("/api/v1/proposals/p1/apply", json={"confirmed_record_ids": ["rec-1"]})
    assert r.status_code == 403 and r.json()["reason_code"] == "not_evaluated"


def test_confirm_then_post_sends_sorted_records_and_redirects(client):
    c, fake = client()
    page = c.get("/work/proposals/p1/confirm", params={"action": "apply", "exception_id": "e1"}).text
    rid = re.search(r'name="request_id" value="([^"]+)"', page).group(1)
    r = c.post("/work/proposals/p1/apply", follow_redirects=False, headers={"origin": "http://testserver"},
               data={"confirmed_record_ids": ["rec-2", "rec-1"], "request_id": rid, "exception_id": "e1"})
    assert r.status_code == 303 and r.headers["location"] == f"/work/exceptions/e1?req={rid}"
    [(sql, params)] = [(s, p) for s, p in fake.calls if "BEGIN ATOMIC" in s]
    assert params["confirmed_records"] == '["rec-1","rec-2"]' and params["request_id"] == rid


def test_post_refuses_role_fields_cross_origin_and_reasonless_reject(client):
    c, fake = client()
    base = {"confirmed_record_ids": ["rec-1"], "request_id": "r", "exception_id": "e1"}
    same = {"origin": "http://testserver"}
    assert c.post("/work/proposals/p1/apply", data={**base, "role": "OUSD_C_FMO"}, headers=same,
                  follow_redirects=False).status_code == 422
    assert c.post("/work/proposals/p1/apply", data=base, headers={"origin": "https://evil.example"},
                  follow_redirects=False).status_code == 403
    assert c.post("/work/proposals/p1/reject", data={**base, "notes": " "}, headers=same,
                  follow_redirects=False).status_code == 422
    assert c.post("/api/v1/proposals/p1/apply", json={"confirmed_record_ids": [], "actor_role": "X"}
                  ).status_code == 422
    assert not any("BEGIN ATOMIC" in s for s, _ in fake.calls), "a refused request reached the warehouse"


@pytest.mark.parametrize("code,status", [("allowed", 200), ("not_owner", 403), ("no_role", 403),
                                         ("not_pending", 409), ("verdict_not_passing", 409)])
def test_api_status_codes(client, code, status):
    c, _ = client(outcome=code)
    r = c.post("/api/v1/proposals/p1/apply", json={"confirmed_record_ids": ["rec-1", "rec-2"]})
    assert r.status_code == status and r.json()["replayed"] is False


def test_status_without_a_decision_is_flagged(client):
    """A-22: applied with no apply decision means the status was set outside the app."""
    c, _ = client(prop={"status": "applied"})
    html = c.get("/work/exceptions/e1").text
    assert "No decision behind this status." in html and "no apply decision is recorded" in html
    backed = {"decision_id": "d1", "proposal_id": "p1", "actor": "u@x", "actor_role": "PMS379",
              "action": "apply", "decided_at": "2026-11-11T05:00:00Z",
              "authority_check_result": "allowed", "notes": None}
    c, _ = client(prop={"status": "applied"}, decisions=[backed])
    assert "No decision behind this status." not in c.get("/work/exceptions/e1").text
    c, _ = client(prop={"status": "rejected"}, decisions=[backed])   # apply decision does not back a reject
    assert "no reject decision is recorded" in c.get("/work/exceptions/e1").text
    c, _ = client(token=False, prop={"status": "applied"})
    assert "could not be checked" in c.get("/work/exceptions/e1").text
    c, _ = client()                                                    # pending: nothing to back
    assert "No decision behind this status." not in c.get("/work/exceptions/e1").text


def test_card_renders_dollar_payload_through_figure(client):
    """A-17: a proposal with dollar_amount in the payload renders via ui.figure."""
    c, _ = client(prop={"proposed_payload": '{"dollar_amount": "1234567.89", "status": "cleared"}',
                        "grounding_json": json.dumps([{"field": "dollar_amount", "document_id": "doc1",
                                                       "page": 5, "text_span": "$1.2M"}])})
    html = c.get("/work/exceptions/e1").text
    # The dollar field must go through figure rendering (has data-figure, has $1,234,567.89)
    assert "$1,234,567.89" in html
    assert 'data-figure="proposal.p1.dollar_amount"' in html
    # The status field renders as plain text
    assert "<dd>cleared</dd>" in html
    # No bare "1234567.89" or "1234567" outside of provenance
    assert re.search(r">\s*1234567(\.89)?\s*<", html) is None


def test_confirm_renders_dollar_payload_through_figure(client):
    """A-17: confirm page also renders dollar fields through figure."""
    c, _ = client(prop={"proposed_payload": '{"dollar_amount": "500.25", "resolution": "x"}'})
    html = c.get("/work/proposals/p1/confirm", params={"action": "apply", "exception_id": "e1"}).text
    assert "$500.25" in html and 'data-figure="proposal.p1.dollar_amount"' in html
    assert "<dd>x</dd>" in html


def test_provenance_api_returns_cached_block(client):
    """A-13: GET /api/v1/provenance/{id} returns the full provenance from cache."""
    c, _ = client()
    # Rendering the exception card populates the cache with the exception amount figure
    c.get("/work/exceptions/e1")
    # Find the provenance_id that was generated for the exception amount
    f = E.figure(figure_id="exception.e1.dollar_amount", label="Exception amount",
                 value="6000000.00", unit="USD", as_of="2026-11-11T03:00:00Z",
                 record_ids=["rec-1", "rec-2"], computation="c", source="aircarrier_app_exceptions")
    pid = f["provenance"]["provenance_id"]
    r = c.get(f"/api/v1/provenance/{pid}")
    assert r.status_code == 200
    body = r.json()
    assert body["provenance_id"] == pid
    assert body["record_count"] == 2


def test_provenance_records_api_paginates(client):
    """A-13: GET /api/v1/provenance/{id}/records paginates the record list."""
    c, _ = client()
    c.get("/work/exceptions/e1")
    f = E.figure(figure_id="exception.e1.dollar_amount", label="L", value="6000000.00",
                 unit="USD", as_of="2026-11-11T03:00:00Z",
                 record_ids=["rec-1", "rec-2"], computation="c", source="aircarrier_app_exceptions")
    pid = f["provenance"]["provenance_id"]
    r = c.get(f"/api/v1/provenance/{pid}/records", params={"page": 1, "page_size": 1})
    assert r.status_code == 200
    body = r.json()
    assert body["record_count"] == 2
    assert len(body["records"]) == 1
    assert body["records"][0]["record_id"] in ("rec-1", "rec-2")


def test_provenance_api_404_when_evicted(client):
    c, _ = client()
    r = c.get("/api/v1/provenance/does_not_exist")
    assert r.status_code == 404
    r2 = c.get("/api/v1/provenance/does_not_exist/records")
    assert r2.status_code == 404


def test_card_renders_provenance_link(client):
    """A-13: the provenance panel in the figure shows a link to the records endpoint."""
    c, _ = client()
    html = c.get("/work/exceptions/e1").text
    assert "/api/v1/provenance/" in html and "records" in html


# ----------------------------------------------------------------- template lint
def test_templates_print_no_raw_money_fields():
    """Amounts reach the page only through ui.figure()."""
    for path in (ROOT / "app" / "templates").glob("*.html"):
        if path.name not in ("work.html", "exception.html", "confirm.html", "_ui.html"):
            continue
        text = path.read_text()
        assert not re.search(r"\{\{[^}]*(dollar_amount|\.value)\b[^}]*\}\}", text.replace("f.value", "")), path.name


# ----------------------------------------------------------------- /rules page
CATALOG_ROWS = [
    {"rule_id": "CC-01", "version": "1", "version_count": "1", "status": "blocked_no_source",
     "blocked_reason": "Needs the ledger feed.", "statement_text": "Ledger delta rule.",
     "params": '{"threshold_pct": "0.02"}', "owner_role": "PMS379", "owner_office": "PEO Carriers",
     "required_action": "Reconciliation review", "area": "cost_capture", "current_version": None},
    {"rule_id": "CC-02", "version": "6", "version_count": "6", "status": "active",
     "blocked_reason": None, "statement_text": "Escalate after 45 days.",
     "params": '{"source_rule": "CC-01", "window": ""}', "owner_role": "PMS379",
     "owner_office": "PEO Carriers", "required_action": "Escalate", "area": "cost_capture",
     "current_version": "6"},
]


@pytest.fixture
def rules_page(monkeypatch):
    """GET /rules with the register answered by q (rows, or an exception to raise)."""
    def get(answer):
        def q(sql, params=None):
            assert "version_count" in sql, sql      # only the catalog statement is run
            if isinstance(answer, Exception):
                raise answer
            return answer
        ident = identity.Identity(email="u@x", token=None)
        monkeypatch.setattr(work, "runners", lambda request: (ident, q, None))
        return TestClient(main.app).get("/rules")
    return get


def test_rule_catalog_lists_every_rule_not_only_current():
    """Blocked rules have no version in effect, so the page cannot read current_rules."""
    sql = H.rule_catalog(H.tables())
    assert "rule_register" in sql and "LEFT JOIN" in sql and "current_rules" in sql
    assert "r.rn = 1" in sql and "ORDER BY version DESC" in sql
    assert ":" not in re.sub(r"'[^']*'", "", sql)    # no parameter markers


def test_rules_page_reads_register_live(rules_page):
    r = rules_page(CATALOG_ROWS)
    assert r.status_code == 200
    html = r.text
    assert 'data-source="live"' in html and 'data-source="snapshot"' not in html
    assert "Ledger delta rule." in html and "Escalate after 45 days." in html
    assert "v6" in html and "of 6" in html and "none in effect" in html
    assert "window: unset" in html                     # an empty param says so
    assert "The 2 rules" in html


def test_rules_page_falls_back_to_snapshot_and_says_why(rules_page):
    r = rules_page(RuntimeError("warehouse is unset"))
    assert r.status_code == 200
    html = r.text
    assert 'data-source="snapshot"' in html and "warehouse is unset" in html
    snap = json.loads((ROOT / "app" / "data" / "rules.json").read_text())["register_snapshot"]
    assert snap["built_at"] in html
    for area in snap["areas"]:
        for rule in area["rules"]:
            assert f"<code>{rule['code']}</code>" in html


def test_rules_page_si_rulebook_is_the_code(rules_page):
    """The SI text on the page is the text the specialist is given, not a copy."""
    from markupsafe import escape        # what Jinja autoescape writes
    from api.si import sdk, tasks
    page = rules_page(CATALOG_ROWS).text
    for code, text in tasks.RULEBOOK.items():
        assert str(escape(text)) in page, code
    assert page.count(">system</span>") == len(sdk.SYSTEM_RULES)


def test_rules_json_gate_routes_follow_gate_yaml_and_gate_py():
    """rules.json is generated (etl/build_rules.py) and in step with both sources."""
    import yaml
    built = json.loads((ROOT / "app" / "data" / "rules.json").read_text())
    assert {"built_at", "source", "gate_routes", "register_snapshot"} <= set(built)
    gate = yaml.safe_load((ROOT / "seed" / "gate.yaml").read_text())
    codes = [r["code"] for r in built["gate_routes"]]
    assert codes == list(gate["routes"])
    for r in built["gate_routes"]:
        assert r["description"] == gate["routes"][r["code"]]["when"]
        assert r["decision"] == gate["routes"][r["code"]]["decision"]
    # gate.py applies the routes in this order; the first match decides.
    src = (ROOT / "core" / "policy" / "gate.py").read_text()
    route_fn = src[src.index("def route("):]
    assert codes == re.findall(r'"(R-?\d+)", share, flags', route_fn)


# ------------------------------------------------------------ three lanes (WORK_QUEUE_V2)
def _xrow(eid, status="open", ids=("wbs-7",), rule="CC-02", version=6, amount="6000000.00"):
    return {"exception_id": eid, "rule_id": rule, "rule_version": version,
            "subject_type": "reconciliation_item", "subject_ids": json.dumps(list(ids)),
            "detected_at": "2026-11-01T00:00:00Z", "dollar_amount": amount,
            "owner_role": "PMS379", "owner_office": "PEO Carriers",
            "required_action": "Escalation to next authority", "window_closes_at": None,
            "status": status, "area": "cost_capture", "eval_id": "ev1"}


def _prow(pid, run, title, created, verdicts, role="PMS379", status="pending", rule="OB-01"):
    payload = {"title": title, "goes_to": {"role": role, "office": "PEO Carriers"},
               "figures": [{"display": "$4,519,300,323.83", "label": "Obligations"}]}
    return {"proposal_id": pid, "run_id": run, "status": status, "block_reason": None,
            "rule_id": rule, "target_table": "si:obligation_baseline", "target_key": role,
            "intake_outcome": "si_run", "exception_id": None,
            "proposed_payload": json.dumps(payload), "created_at": created,
            "trigger": "si:/mission:reconcile_obligations", "subject_id": "N00024-09-C-2116",
            "verdicts": json.dumps(verdicts) if verdicts is not None else None}


PASS = [{"checker": "si:canvas", "verdict": "pass"},
        {"checker": "si:records_checker", "verdict": "pass_with_exception"}]
RULES = [
    {"rule_id": "CC-02", "version": 5, "status": "active"},
    {"rule_id": "CC-02", "version": 6, "status": "active"},
    {"rule_id": "CM-01", "version": 1, "status": "active"},
    {"rule_id": "CM-01", "version": 2, "status": "active"},
    {"rule_id": "EV-01", "version": 1, "status": "blocked_no_source",
     "blocked_reason": "Requires EVM performance data feed.", "owner_office": "PEO Carriers"},
    {"rule_id": "EV-02", "version": 1, "status": "blocked_no_source",
     "blocked_reason": "Requires EVM performance data feed.", "owner_office": "PEO Carriers"},
]
CURRENT = [{"rule_id": "CC-02", "version": 6}, {"rule_id": "CM-01", "version": 2}]
RETIRED = [{"rule_id": "CC-02", "version": 5}]


def _lane_q(exceptions, proposals, rules=RULES, current=CURRENT):
    """The app principal's reads. It has no grant on rule_register_audit or
    role_map, so a statement on either fails here as it does in the app."""
    def q(sql, params=None):
        if "rule_register_audit" in sql or "role_map" in sql:
            raise RuntimeError("INSUFFICIENT_PERMISSIONS: app principal")
        if "current_rules" in sql:
            return current
        if "rule_register" in sql:
            return rules
        if "v.verdicts" in sql:
            return proposals
        return exceptions
    return q


def _held(roles, retired=RETIRED):
    """The caller's reads: who holds which role, and retired versions."""
    def q(sql, params=None):
        if "rule_register_audit" in sql:
            return retired
        return [{"role": r} for r in roles]
    return q


def test_lanes_test_and_closed_rows_never_reach_decide():           # T1
    q = _lane_q([_xrow("e1", ids=("test-wbs-001",)), _xrow("e2", status="void_test_data"),
                 _xrow("e3", status="superseded")], [])
    out = work.lanes(q, _held(["PMS379"]))
    assert out["decide"] == []
    sys_ids = {i["id"] for g in out["system"] for i in g["items"]}
    assert {"e1", "e2", "e3"} <= sys_ids
    assert out["answer"].startswith("Nothing needs a decision.")


def test_lanes_exception_on_retired_version_goes_to_system():
    out = work.lanes(_lane_q([_xrow("e1", version=5), _xrow("e2", version=6)], []), _held(["PMS379"]))
    assert [d["id"] for d in out["decide"]] == ["e2"]


def test_lanes_repeat_runs_collapse_to_newest_checked():
    rows = [_prow("p_old", "r1", "Record baseline", "2026-11-11T22:00:00Z", PASS),
            _prow("p_new", "r2", "Record baseline", "2026-11-12T13:00:00Z", PASS),
            _prow("p_unchk", "r3", "Other", "2026-11-12T13:00:00Z", None),
            _prow("p_fail", "r4", "Third", "2026-11-12T13:00:00Z",
                  [{"checker": "si:records_checker", "verdict": "fail"}])]
    out = work.lanes(_lane_q([], rows), _held(["PMS379"]))
    assert [(d["id"], d["copies"], d["href"]) for d in out["decide"]] == [("p_new", 1, "/runs/r2")]
    groups = {g["group"]: [i["id"] for i in g["items"]] for g in out["system"]}
    assert groups["Repeat runs (an older copy of an item in Decide)"] == ["p_old"]
    assert sorted(groups["Proposals that did not pass the checker"]) == ["p_fail", "p_unchk"]


def test_lanes_pending_copy_older_than_a_decision_is_not_a_decision():
    # 2026-11-12: after 3a784900 was applied, the older pending copy 452030d9
    # (same task, subject, rule and kind) reappeared in Decide.
    rows = [_prow("p_old", "r1", "Record baseline", "2026-11-11T22:00:00Z", PASS),
            _prow("p_done", "r2", "Record baseline", "2026-11-12T13:10:00Z", PASS,
                  status="applied"),
            _prow("p_after", "r3", "Record baseline", "2026-11-12T14:00:00Z", PASS)]
    out = work.lanes(_lane_q([], rows[:2]), _held(["PMS379"]))
    assert out["decide"] == []
    groups = {g["group"]: [i["id"] for i in g["items"]] for g in out["system"]}
    assert groups["Answered by a later decision"] == ["p_old"]
    # A copy raised after the decision is new evidence and is decided again.
    out = work.lanes(_lane_q([], rows), _held(["PMS379"]))
    assert [(d["id"], d["copies"]) for d in out["decide"]] == [("p_after", 0)]


def test_lanes_group_by_subject_not_by_model_title():
    a = _prow("p1", "r1", "Record the baseline", "2026-11-11T22:00:00Z", PASS)
    b = _prow("p2", "r2", "Record the FPDS baseline", "2026-11-12T13:00:00Z", PASS)
    out = work.lanes(_lane_q([], [a, b]), _held(["PMS379"]))
    assert [(d["id"], d["copies"]) for d in out["decide"]] == [("p2", 1)]


def test_lanes_answer_grammar_for_one_cause():
    rules = [r for r in RULES if r["rule_id"] != "EV-02"]
    out = work.lanes(_lane_q([], [], rules=rules), _held(["PMS379"]))
    assert "1 missing feed or parameter keeps 1 rule from running." in out["answer"]


def test_lanes_unblock_groups_by_root_cause_and_flags_vacant_roles():
    rows = [_prow("p1", "r1", "Lead", "2026-11-12T13:00:00Z", PASS, role="NAVY_FMO")]
    out = work.lanes(_lane_q([], rows), _held(["PMS379"]))
    feed = [u for u in out["unblock"] if u["status"] == "blocked_no_source"]
    assert len(feed) == 1 and feed[0]["rules"] == ["EV-01", "EV-02"]
    vac = [u for u in out["unblock"] if u["status"] == "role_vacant"]
    assert len(vac) == 1 and vac[0]["offices"] == ["NAVY_FMO"]
    assert out["decide"][0]["holder"] is False
    defects = [i["id"] for g in out["system"] if g["group"] == "Rule defects" for i in g["items"]]
    assert defects == ["CM-01"]                 # CC-02 v5 is retired, so only CM-01 has two
    assert "NAVY_FMO" in out["answer"] and "2 rules from running" in out["answer"]


def test_lanes_without_token_says_roles_unchecked():
    out = work.lanes(_lane_q([], [_prow("p1", "r1", "T", "2026-11-12T13:00:00Z", PASS)]), None)
    assert out["decide"][0]["holder"] is None and "could not be checked" in out["answer"]
    groups = {g["group"]: [i["id"] for i in g["items"]] for g in out["system"]}
    assert groups["Rule defects"] == ["defect-check"]     # said, not silently skipped


def test_lanes_never_read_audit_or_role_map_as_the_app():
    # 2026-11-12: deployed /work failed with INSUFFICIENT_PERMISSIONS on
    # rule_register_audit because lane_rules joined it on the app's token.
    # _lane_q raises on either table, so this fails if the app reads one again.
    out = work.lanes(_lane_q([_xrow("e2")], []), _held(["PMS379"]))
    assert [d["id"] for d in out["decide"]] == ["e2"]
    for sql in (H.lane_rules(H.tables()), H.lane_current(H.tables()),
                H.lane_exceptions(H.tables()), H.lane_proposals(H.tables())):
        assert "rule_register_audit" not in sql and "role_map" not in sql


def test_lanes_answer_is_code_and_stable():                      # T10
    q = _lane_q([_xrow("e2")], [_prow("p1", "r1", "T", "2026-11-12T13:00:00Z", PASS)])
    assert work.lanes(q, _held(["PMS379"]))["answer"] == work.lanes(q, _held(["PMS379"]))["answer"]


def test_work_page_renders_three_lanes(monkeypatch):
    q = _lane_q([_xrow("e1", status="superseded")],
                [_prow("p1", "r1", "Record baseline", "2026-11-12T13:00:00Z", PASS)])
    ident = identity.Identity(email="u@x", token="t")
    monkeypatch.setattr(work, "runners", lambda request: (ident, q, _held(["PMS379"])))
    html = TestClient(main.app).get("/work").text
    for s in ('id="lane-decide"', 'id="lane-unblock"', 'id="lane-system"', 'href="/runs/r1"',
              "Review and decide", "1 decision waiting (1 for PMS379)"):
        assert s in html, s
    assert "$6,000,000.00" not in html          # a superseded row's amount is not shown


def test_system_card_prints_no_digits_for_its_amount(client):        # T3
    c, fake = client()
    orig = fake.__call__

    class Closed(type(fake)):
        def __call__(self, sql, params=None):
            rows = orig(sql, params)
            if "x.exception_id = :exception_id" in sql:
                return [dict(r, status="superseded") for r in rows]
            return rows
    fake.__class__ = Closed
    html = c.get("/work/exceptions/e1").text
    assert "No action." in html and "Not established." in html
    assert "$6,000,000.00" not in html


# ------------------------------------------------------------ uc data backend
def test_uc_backend_names_every_document_the_app_reads():
    from api import data
    files = sorted(p.stem for p in (ROOT / "app" / "data").glob("*.json"))
    assert sorted(data.DOCUMENTS) == files          # 23 on 2026-11-12, incl. corpus, delivery, rules
    assert all(v.endswith(f"v_doc_{n}") for n, v in data.VIEWS.items())


def test_uc_backend_serves_the_same_document_as_files(monkeypatch):
    from api import data, live
    text = (ROOT / "app" / "data" / "gaps.json").read_text()
    seen = []

    def q(sql, params=None, **_):
        seen.append(sql)
        return ["doc", "content_sha"], [{"doc": text, "content_sha": "s1"}]
    monkeypatch.setattr(live, "query", q)
    monkeypatch.setattr(live, "_cache", {})
    monkeypatch.setattr(data, "BACKEND", "uc")
    assert data.get("gaps") == json.loads(text)
    assert data.VIEWS["gaps"] in seen[0] and "serving_doc" not in seen[0]   # a view, never the table
    data.get("gaps")
    assert len(seen) == 1                           # cached within UC_TTL_S
    assert data.get("not_a_document") == {} and data.available() == sorted(data.DOCUMENTS)


def test_uc_backend_missing_document_is_an_error_not_an_empty_page(monkeypatch):
    from api import data, live
    monkeypatch.setattr(live, "query", lambda sql, params=None, **_: (["doc", "content_sha"], []))
    monkeypatch.setattr(live, "_cache", {})
    monkeypatch.setattr(data, "BACKEND", "uc")
    with pytest.raises(RuntimeError, match="expected exactly 1"):
        data.get("program")
