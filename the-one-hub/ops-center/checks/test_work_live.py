#!/usr/bin/env python3
"""Work queue, live: the authority rule and the apply transaction on a warehouse.

Runs the statements in app/api/harness_sql.py, unchanged, against scratch
copies of the app tables (users.xiaobing_shang1_civ.aircarrier_apptest_*),
through the same Statement Execution path the app uses. Run on Databricks
serverless or a cluster, as the schema owner:

    python3 checks/test_work_live.py

Every run seeds rows under a fresh suffix and reads back only those, so it
never deletes and never depends on an earlier run. The real app tables are
not touched.

What it proves, each with a known expected answer:
  * every reason code fires on the case built for it, and only there
  * reject is not gated on the checker verdict; apply is
  * a stale record set is refused
  * apply writes attempt + decision + determination + status, together
  * a refusal writes only the attempt
  * a replayed request_id returns the first outcome and writes nothing
  * a failure after the first insert rolls the whole block back
"""
from __future__ import annotations

import os
import sys
import uuid

WAREHOUSE = os.environ.get("DATABRICKS_WAREHOUSE_ID", "50d2bd4ddf65e0f5")
os.environ.update(AIRCARRIER_CATALOG="users", AIRCARRIER_SCHEMA="xiaobing_shang1_civ",
                  AIRCARRIER_STORE_PREFIX="aircarrier_", AIRCARRIER_APP_INFIX="apptest_",
                  DATABRICKS_WAREHOUSE_ID=WAREHOUSE)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))

from databricks.sdk.runtime import spark  # noqa: E402

from api import harness as work  # noqa: E402
from api import harness_sql as H  # noqa: E402
from api import live  # noqa: E402

S = "users.xiaobing_shang1_civ"
T = H.tables()
FAIL: list[str] = []


def check(name: str, ok: bool, detail="") -> None:
    print(f"  [{'ok  ' if ok else 'FAIL'}] {name}" + (f"  {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def q(sql: str, params: dict | None = None) -> list[dict]:
    return live.query(sql, params)[1]


def setup() -> str:
    for n in ("proposals", "exceptions", "checker_verdicts", "decisions", "determinations",
              "role_map", "authority", "agent_runs", "agent_steps", "rule_register"):
        spark.sql(f"CREATE TABLE IF NOT EXISTS {T[n]} LIKE {S}.aircarrier_app_{n} "
                  "TBLPROPERTIES ('delta.feature.catalogManaged'='supported')")
    spark.sql(f"CREATE TABLE IF NOT EXISTS {T['decision_attempts']} LIKE {S}.aircarrier_app_decision_attempts "
              "TBLPROPERTIES ('delta.feature.catalogManaged'='supported')")
    # A determinations table that refuses every row: the rollback case writes here.
    rb = T["determinations"] + "_rb"
    if not spark.catalog.tableExists(rb):
        spark.sql(f"CREATE TABLE {rb} LIKE {T['determinations']} "
                  "TBLPROPERTIES ('delta.feature.catalogManaged'='supported')")
        spark.sql(f"ALTER TABLE {rb} ADD CONSTRAINT always_fail CHECK (component = 'never')")
    me = spark.sql("SELECT current_user()").first()[0]
    spark.sql(f"""MERGE INTO {T['role_map']} t USING (SELECT :me AS uc_group, 'PMS379' AS role) s
        ON t.uc_group = s.uc_group AND t.role = s.role AND t.effective_to IS NULL
        WHEN NOT MATCHED THEN INSERT (uc_group, role, component, effective_from, effective_to, created_by)
        VALUES (s.uc_group, s.role, 'PEO Carriers', TIMESTAMP'2026-01-01', NULL, 'test_work_live')""",
              args={"me": me})
    spark.sql(f"""MERGE INTO {T['authority']} t USING (SELECT * FROM VALUES
        ('PMS379','proposals','apply','component'), ('PMS379','proposals','reject','component')
        AS v(role, target_table, action, scope)) s
        ON t.role = s.role AND t.target_table = s.target_table AND t.action = s.action
        WHEN NOT MATCHED THEN INSERT *""")
    return uuid.uuid4().hex[:8]


def seed(sfx: str) -> dict[str, str]:
    e = {k: f"{k}_{sfx}" for k in ("e_own", "e_other", "e_closed")}
    spark.sql(f"""INSERT INTO {T['exceptions']} SELECT * FROM VALUES
      (:a,'CC-02',4,'reconciliation_item',array('rec-1','rec-2'),current_timestamp(),CAST(6000000.00 AS DECIMAL(20,2)),'PMS379','PEO Carriers','Reconcile',NULL,'open','cost_capture','ev'),
      (:b,'AV-06',1,'acceptance_event',array('acc-1'),current_timestamp(),NULL,'NAVY_FMO','Navy FM&C','Determine',NULL,'open','valuation','ev'),
      (:c,'CC-02',3,'reconciliation_item',array('rec-9'),current_timestamp(),CAST(1.00 AS DECIMAL(20,2)),'PMS379','PEO Carriers','Reconcile',NULL,'superseded','cost_capture','ev')""",
              args={"a": e["e_own"], "b": e["e_other"], "c": e["e_closed"]})
    cases = {  # name: (exception key, rule_version, intake, verdict)
        "ok": ("e_own", 4, None, "pass"), "fail": ("e_own", 4, None, "fail"),
        "unchecked": ("e_own", 4, None, None), "other": ("e_other", 1, None, "pass"),
        "nolin": (None, None, None, "pass"), "blocked": ("e_own", 4, "blocked", "pass"),
        "closed": ("e_closed", 3, None, "pass"), "mismatch": ("e_own", 3, None, "pass"),
        "rej": ("e_own", 4, None, "fail"), "rb": ("e_own", 4, None, "pass"),
    }
    ids = {}
    for name, (ek, rv, intake, verdict) in cases.items():
        pid = ids[name] = f"p_{name}_{sfx}"
        rule = None if ek is None else ("AV-06" if ek == "e_other" else "CC-02")
        spark.sql(f"""INSERT INTO {T['proposals']} (proposal_id, run_id, target_table, target_key,
            proposed_payload, grounding, schema_validation, status, block_reason, exception_id, rule_id,
            rule_version, record_ids, created_at, intake_outcome)
          SELECT :p, concat('run_', :p), 'exceptions', 'k', '{{"r":1}}', NULL, NULL, 'pending',
                 IF(:i = 'blocked', 'duplicate unresolved', NULL), :e, :rule, CAST(:rv AS INT),
                 array('rec-2','rec-1'), current_timestamp(), :i""",
                  args={"p": pid, "e": e.get(ek) if ek else None, "rule": rule, "rv": rv, "i": intake})
        if verdict:
            spark.sql(f"""INSERT INTO {T['checker_verdicts']} SELECT concat('run_', :p), 1, :v,
                array(named_struct('check_name','proposal','expected',:p,'actual',:p,'result','recorded')),
                NULL, 'harness_checker', 'test', current_timestamp()""", args={"p": pid, "v": verdict})
    return ids


def count(table: str, pid: str) -> int:
    return int(q(f"SELECT count(*) AS n FROM {T[table]} WHERE proposal_id = :p", {"p": pid})[0]["n"])


def main() -> int:
    sfx = setup()
    ids = seed(sfx)
    print(f"authority rule (suffix {sfx})")
    want = {"ok": "allowed", "fail": "verdict_not_passing", "unchecked": "not_checked",
            "other": "not_owner", "nolin": "no_lineage", "blocked": "blocked",
            "closed": "exception_closed", "mismatch": "lineage_mismatch"}
    for name, code in want.items():
        got = q(H.authority_check(T), {"proposal_id": ids[name], "action": "apply",
                                      "confirmed_records": None})[0]["reason_code"]
        check(f"apply {name} -> {code}", got == code, got)
    got = q(H.authority_check(T), {"proposal_id": "missing_" + sfx, "action": "apply",
                                  "confirmed_records": None})[0]["reason_code"]
    check("missing proposal -> not_found", got == "not_found", got)
    got = q(H.authority_check(T), {"proposal_id": ids["fail"], "action": "reject",
                                  "confirmed_records": None})[0]["reason_code"]
    check("reject is not gated on the verdict", got == "allowed", got)
    got = q(H.authority_check(T), {"proposal_id": ids["ok"], "action": "apply",
                                  "confirmed_records": '["rec-1"]'})[0]["reason_code"]
    check("stale record set -> record_set_changed", got == "record_set_changed", got)

    print("apply transaction")
    req = "req_" + sfx
    r1 = work.act(q, proposal_id=ids["ok"], action="apply", confirmed_record_ids=["rec-2", "rec-1"],
                  notes="live", request_id=req)
    check("apply allowed", r1["allowed"] and r1["decision_id"] is not None, r1["reason_code"])
    check("apply wrote decision, determination, attempt, status",
          (count("decisions", ids["ok"]), count("determinations", ids["ok"]),
           count("decision_attempts", ids["ok"])) == (1, 1, 1)
          and q(f"SELECT status FROM {T['proposals']} WHERE proposal_id = :p", {"p": ids["ok"]})[0]["status"] == "applied")
    r2 = work.act(q, proposal_id=ids["ok"], action="apply", confirmed_record_ids=["rec-2", "rec-1"],
                  notes="live", request_id=req)
    check("replay returns the first outcome", r2["replayed"] and r2["decision_id"] == r1["decision_id"])
    check("replay wrote nothing", count("decision_attempts", ids["ok"]) == 1 and count("decisions", ids["ok"]) == 1)
    r3 = work.act(q, proposal_id=ids["ok"], action="apply", confirmed_record_ids=["rec-2", "rec-1"], notes=None)
    check("second apply with a new request -> not_pending", r3["reason_code"] == "not_pending")
    # The confirmation must name the proposal's own records, or the record-set
    # guard refuses first (record_set_changed) and ownership is never reached.
    r4 = work.act(q, proposal_id=ids["other"], action="apply", confirmed_record_ids=["rec-1", "rec-2"],
                  notes=None)
    check("refusal writes only the attempt",
          r4["reason_code"] == "not_owner" and count("decisions", ids["other"]) == 0
          and count("decision_attempts", ids["other"]) == 1, r4["reason_code"])
    r5 = work.act(q, proposal_id=ids["rej"], action="reject", confirmed_record_ids=["rec-1", "rec-2"], notes="no")
    check("reject writes a decision and no determination",
          r5["allowed"] and count("decisions", ids["rej"]) == 1 and count("determinations", ids["rej"]) == 0)

    print("rollback")
    t_rb = dict(T, determinations=T["determinations"] + "_rb")
    try:
        live.query(H.apply_block(t_rb), {"proposal_id": ids["rb"], "action": "apply",
                                        "confirmed_records": '["rec-1","rec-2"]',
                                        "request_id": "rb_" + sfx, "notes": None})
        check("failing determination raises", False, "no error")
    except live.LiveError:
        check("failing determination raises", True)
    check("nothing from the failed block remains",
          (count("decision_attempts", ids["rb"]), count("decisions", ids["rb"])) == (0, 0)
          and q(f"SELECT status FROM {T['proposals']} WHERE proposal_id = :p", {"p": ids["rb"]})[0]["status"] == "pending")

    print("\nall checks pass" if not FAIL else f"\n{len(FAIL)} FAILED: {FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
