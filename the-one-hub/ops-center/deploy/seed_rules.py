"""Seed the rule register with the 22 spec rules (task 7).

Idempotent: skips any rule_id + version that already exists.
Writes an audit row for every insert.

Run with: spark-submit or as a notebook cell after setting AIRCARRIER_STORE_SCHEMA.

Data-availability status (C5, B28):
  active               — expression can run and data exists
  blocked_no_source    — expression references a feed not in this workspace
  blocked_param_unset  — depends on a parameter that the user has not set

User answers (B28):
  CAP-05  — baseline unset; CAP rules emit 'baseline not provided' gap
  AV-06   — preliminary acceptance
  CC-01   — WBS level 3
  CM checker — gpt-5-5 primary, gemini-3-8-flash fallback
"""
import uuid
from datetime import datetime, timezone

SCHEMA = "users.xiaobing_shang1_civ"  # overridden by env at transfer
TABLE = f"{SCHEMA}.aircarrier_app_rule_register"
AUDIT = f"{SCHEMA}.aircarrier_app_rule_register_audit"
ACTOR = "seed_rules.py"

# fmt: off
RULES = [
    # ---- Cost capture -------------------------------------------------------
    {
        "rule_id": "CC-01", "version": 1, "area": "cost_capture",
        "owner_role": "PMS379",
        "statement_text": "Contractor incurred cost to ledger recorded cost delta above $5M or 2% at WBS level 3 becomes a reconciliation item.",
        "expression_sql": None,  # needs IPMDAR, CCDR, GL/ledger
        "params": {"threshold_dollars": "5000000", "threshold_pct": "0.02", "wbs_level": "3"},
        "value_lists": None,
        "status": "blocked_no_source",
        "blocked_reason": "Requires IPMDAR, CCDR, and GL/ledger recorded cost feeds.",
        "owner_office": "PEO Carriers", "required_action": "Reconciliation review",
    },
    {
        "rule_id": "CC-02", "version": 1, "area": "cost_capture",
        "owner_role": "PMS379",
        "statement_text": "A reconciliation item unresolved for 45 days escalates to the next authority level.",
        "expression_sql": (
            "SELECT e.exception_id, e.rule_id, e.rule_version, e.subject_ids, "
            "e.dollar_amount, e.owner_office "
            "FROM {EXCEPTIONS} e "
            "WHERE e.rule_id = :source_rule AND e.status = :status_filter "
            "AND datediff(current_date(), e.detected_at) > CAST(:escalation_days AS INT)"
        ),
        "params": {"source_rule": "CC-01", "status_filter": "open", "escalation_days": "45"},
        "value_lists": None,
        "status": "active",
        "blocked_reason": None,
        "owner_office": "PEO Carriers", "required_action": "Escalation to next authority",
    },
    {
        "rule_id": "CC-03", "version": 1, "area": "cost_capture",
        "owner_role": "PMS379",
        "statement_text": "A CDRL submission more than 10 days past its contract due date raises a tasker.",
        "expression_sql": None,  # needs CDRL tracking data
        "params": {"overdue_days": "10"},
        "value_lists": None,
        "status": "blocked_no_source",
        "blocked_reason": "Requires CDRL due-date tracking feed.",
        "owner_office": "PEO Carriers", "required_action": "Tasker to contractor",
    },
    {
        "rule_id": "CC-04", "version": 1, "area": "cost_capture",
        "owner_role": "PMS379",
        "statement_text": "Cost charged to a CLIN with no unexpired funding authority is a compliance exception, excluded from valuation until cleared.",
        "expression_sql": None,  # needs CLIN funding authority
        "params": {},
        "value_lists": None,
        "status": "blocked_no_source",
        "blocked_reason": "Requires CLIN funding authority feed.",
        "owner_office": "PEO Carriers", "required_action": "Compliance review and valuation exclusion",
    },

    # ---- EVM ----------------------------------------------------------------
    {
        "rule_id": "EV-01", "version": 1, "area": "evm",
        "owner_role": "PMS379",
        "statement_text": "CPI below 0.95 at control account requires a variance explanation.",
        "expression_sql": None,  # needs EVM data
        "params": {"cpi_floor": "0.95"},
        "value_lists": None,
        "status": "blocked_no_source",
        "blocked_reason": "Requires EVM performance data feed.",
        "owner_office": "PEO Carriers", "required_action": "Variance explanation",
    },
    {
        "rule_id": "EV-02", "version": 1, "area": "evm",
        "owner_role": "PMS379",
        "statement_text": "TCPI exceeding CPI by more than 0.10 triggers an EAC credibility review.",
        "expression_sql": None,
        "params": {"tcpi_cpi_gap": "0.10"},
        "value_lists": None,
        "status": "blocked_no_source",
        "blocked_reason": "Requires EVM performance data feed.",
        "owner_office": "PEO Carriers", "required_action": "EAC credibility review",
    },
    {
        "rule_id": "EV-03", "version": 1, "area": "evm",
        "owner_role": "PMS379",
        "statement_text": "Management reserve burn above 15% in a quarter triggers a baseline review.",
        "expression_sql": None,
        "params": {"mr_burn_pct": "0.15"},
        "value_lists": None,
        "status": "blocked_no_source",
        "blocked_reason": "Requires management reserve data feed.",
        "owner_office": "PEO Carriers", "required_action": "Baseline review",
    },
    {
        "rule_id": "EV-04", "version": 1, "area": "evm",
        "owner_role": "PMS379",
        "statement_text": "A retroactive BCWS change above $2M is a baseline integrity flag.",
        "expression_sql": None,
        "params": {"bcws_change_threshold": "2000000"},
        "value_lists": None,
        "status": "blocked_no_source",
        "blocked_reason": "Requires EVM BCWS baseline data feed.",
        "owner_office": "PEO Carriers", "required_action": "Baseline integrity flag",
    },

    # ---- Cost cap -----------------------------------------------------------
    {
        "rule_id": "CAP-01", "version": 1, "area": "cost_cap",
        "owner_role": "OUSD_C_FMO",
        "statement_text": "Projected end cost within 3% of the current adjusted limitation escalates to leadership.",
        "expression_sql": None,  # needs CAP-05 param + GL/CIP
        "params": {"headroom_pct": "0.03"},
        "value_lists": None,
        "status": "blocked_param_unset",
        "blocked_reason": "CAP-05 (statutory limitation baseline) is not yet set.",
        "owner_office": "OUSD(C)", "required_action": "Leadership escalation",
    },
    {
        "rule_id": "CAP-02", "version": 1, "area": "cost_cap",
        "owner_role": "OUSD_C_FMO",
        "statement_text": "A projected breach drafts the notification package and routes it to the authorized role.",
        "expression_sql": None,
        "params": {},
        "value_lists": None,
        "status": "blocked_param_unset",
        "blocked_reason": "CAP-05 (statutory limitation baseline) is not yet set.",
        "owner_office": "OUSD(C)", "required_action": "Draft congressional notification",
    },
    {
        "rule_id": "CAP-03", "version": 1, "area": "cost_cap",
        "owner_role": "OUSD_C_FMO",
        "statement_text": "A claimed exclusion with no documented authority reference is an exclusion validity exception.",
        "expression_sql": None,  # needs GL/CIP exclusion claims
        "params": {},
        "value_lists": None,
        "status": "blocked_no_source",
        "blocked_reason": "Requires GL/CIP and exclusion authority documentation feeds.",
        "owner_office": "OUSD(C)", "required_action": "Exclusion validity review",
    },
    {
        "rule_id": "CAP-04", "version": 1, "area": "cost_cap",
        "owner_role": "OUSD_C_FMO",
        "statement_text": "Scope moved from SCN end cost into a post-delivery account above $25M in a quarter is a cost migration flag.",
        "expression_sql": None,  # needs SCN end cost and post-delivery accounts
        "params": {"migration_threshold": "25000000"},
        "value_lists": None,
        "status": "blocked_no_source",
        "blocked_reason": "Requires SCN end cost and OPN/O&M,N post-delivery account feeds.",
        "owner_office": "OUSD(C)", "required_action": "Cost migration report",
    },
    {
        "rule_id": "CAP-05", "version": 1, "area": "cost_cap",
        "owner_role": "OUSD_C_FMO",
        "statement_text": "The statutory limitation baseline per 10 USC 8692 for CVN-79, held as a parameter.",
        "expression_sql": None,  # param-only rule, no detection expression
        "params": {"baseline_amount": "", "adjustments": "", "exclusions": ""},
        "value_lists": None,
        "status": "active",
        "blocked_reason": "Parameter is intentionally unset (B28). CAP rules that read it emit a 'baseline not provided' gap until it is set.",
        "owner_office": "OUSD(C)", "required_action": "Set baseline when authoritative figure is confirmed",
    },

    # ---- Valuation ----------------------------------------------------------
    {
        "rule_id": "AV-01", "version": 1, "area": "valuation",
        "owner_role": "NAVY_FMO",
        "statement_text": "A cost element on the non-capitalizable list posted to the CVN-79 CIP account is a classification exception.",
        "expression_sql": None,  # needs CIP transactions
        "params": {},
        "value_lists": {"non_capitalizable": ["travel", "training", "rework_unsalvageable", "warranty", "pre_contract_costs"]},
        "status": "blocked_no_source",
        "blocked_reason": "Requires CIP transaction ledger feed.",
        "owner_office": "Navy FM&C", "required_action": "Classification review",
    },
    {
        "rule_id": "AV-02", "version": 1, "area": "valuation",
        "owner_role": "NAVY_FMO",
        "statement_text": "A CIP transaction with no linked source document is a KSD gap.",
        "expression_sql": None,
        "params": {},
        "value_lists": None,
        "status": "blocked_no_source",
        "blocked_reason": "Requires CIP transaction ledger and source document linkage.",
        "owner_office": "Navy FM&C", "required_action": "KSD gap remediation",
    },
    {
        "rule_id": "AV-03", "version": 1, "area": "valuation",
        "owner_role": "NAVY_FMO",
        "statement_text": "CIP balance movement above $50M in a month with no reconciling contractor report is unsupported accumulation.",
        "expression_sql": None,
        "params": {"movement_threshold": "50000000"},
        "value_lists": None,
        "status": "blocked_no_source",
        "blocked_reason": "Requires CIP balance and contractor report feeds.",
        "owner_office": "Navy FM&C", "required_action": "Accumulation review",
    },
    {
        "rule_id": "AV-04", "version": 1, "area": "valuation",
        "owner_role": "NAVY_FMO",
        "statement_text": "An acceptance event recorded with no placed-in-service determination documented within 30 days is a valuation event gap.",
        "expression_sql": None,  # needs acceptance event tracking
        "params": {"pis_window_days": "30"},
        "value_lists": None,
        "status": "blocked_no_source",
        "blocked_reason": "Requires acceptance event and placed-in-service determination feeds.",
        "owner_office": "Navy FM&C", "required_action": "Valuation event gap remediation",
    },
    {
        "rule_id": "AV-05", "version": 1, "area": "valuation",
        "owner_role": "NAVY_FMO",
        "statement_text": "A GFE or GFM transfer in with no receiving document is an existence exception.",
        "expression_sql": None,
        "params": {},
        "value_lists": None,
        "status": "blocked_no_source",
        "blocked_reason": "Requires GFE/GFM transfer and DD 1149 receiving document feeds.",
        "owner_office": "Navy FM&C", "required_action": "Existence verification",
    },
    {
        "rule_id": "AV-06", "version": 1, "area": "valuation",
        "owner_role": "NAVY_FMO",
        "statement_text": "The acceptance event that triggers CIP transfer and depreciation start for CVN-79, held as a parameter.",
        "expression_sql": None,  # param-only rule
        "params": {"triggering_event": "preliminary_acceptance"},
        "value_lists": {"recognised_events": ["preliminary_acceptance", "contractual_delivery", "dd_250"]},
        "status": "active",
        "blocked_reason": None,
        "owner_office": "Navy FM&C", "required_action": "Confirm or change when determination is made",
    },

    # ---- Cost model ---------------------------------------------------------
    {
        "rule_id": "CM-01", "version": 1, "area": "cost_model",
        "owner_role": "PMS379",
        "statement_text": "EAC growth above 2% quarter over quarter requires a forecast review with driver attribution.",
        "expression_sql": (
            "SELECT cur.model_run_id, cur.scenario_params, cur.outputs "
            "FROM ("
            "  SELECT model_run_id, scenario_params, outputs, created_at, "
            "    LAG(outputs) OVER (ORDER BY created_at) AS prev_outputs "
            "  FROM {MODEL_RUNS}"
            ") cur "
            "WHERE cur.prev_outputs IS NOT NULL "
            "AND (CAST(get_json_object(cur.outputs, :eac_path) AS DECIMAL(20,2)) "
            "  - CAST(get_json_object(cur.prev_outputs, :eac_path) AS DECIMAL(20,2))) "
            "  / NULLIF(CAST(get_json_object(cur.prev_outputs, :eac_path) AS DECIMAL(20,2)), 0) "
            "  > CAST(:growth_pct AS DECIMAL(5,4))"
        ),
        "params": {"eac_path": "$.eac", "growth_pct": "0.02"},
        "value_lists": None,
        "status": "active",
        "blocked_reason": None,
        "owner_office": "PEO Carriers", "required_action": "Forecast review with driver attribution",
    },
    {
        "rule_id": "CM-02", "version": 1, "area": "cost_model",
        "owner_role": "PMS379",
        "statement_text": "A model run using any input older than 60 days carries a stale input warning on its output.",
        "expression_sql": (
            "SELECT m.model_run_id, m.scenario_params "
            "FROM {MODEL_RUNS} m "
            "LATERAL VIEW OUTER explode(m.inputs_vintage) iv AS feed, vintage "
            "WHERE vintage IS NOT NULL "
            "AND datediff(m.created_at, vintage) > CAST(:staleness_days AS INT)"
        ),
        "params": {"staleness_days": "60"},
        "value_lists": None,
        "status": "active",
        "blocked_reason": None,
        "owner_office": "PEO Carriers", "required_action": "Stale input warning on output",
    },
    {
        "rule_id": "CM-03", "version": 1, "area": "cost_model",
        "owner_role": "PMS379",
        "statement_text": "A scenario result that breaches the limitation links automatically to CAP-01.",
        "expression_sql": None,  # needs CAP-05 baseline to compare against
        "params": {},
        "value_lists": None,
        "status": "blocked_param_unset",
        "blocked_reason": "CAP-05 (statutory limitation baseline) is not yet set.",
        "owner_office": "PEO Carriers", "required_action": "Link to CAP-01 escalation",
    },
]
# fmt: on


def seed(spark):
    """Insert rules that don't already exist. Returns (inserted, skipped)."""
    now = datetime.now(timezone.utc).isoformat()
    inserted = skipped = 0

    for r in RULES:
        # Check existence
        exists = spark.sql(
            f"SELECT 1 FROM {TABLE} WHERE rule_id = :rule_id AND version = {int(r['version'])}",
            args={"rule_id": r["rule_id"]},
        ).count()
        if exists:
            skipped += 1
            continue

        # Build the SQL parts. Values are bound as parameter markers, never
        # pasted into SQL text (F18: Spark reads 'a''b' as "ab").
        bound: dict[str, str] = {"rule_id": r["rule_id"], "actor": ACTOR,
                                 "audit_id": str(uuid.uuid4())}

        def sq(v, bound=bound):
            if v is None:
                return "NULL"
            name = f"b{len(bound)}"
            bound[name] = str(v)
            return f":{name}"

        params_sql = "NULL"
        if r.get("params"):
            entries = ", ".join(f"{sq(k)}, {sq(str(v))}" for k, v in r["params"].items())
            params_sql = f"MAP({entries})"

        vl_sql = "NULL"
        if r.get("value_lists"):
            entries = []
            for k, vals in r["value_lists"].items():
                arr = ", ".join(sq(v) for v in vals)
                entries.append(f"{sq(k)}, ARRAY({arr})")
            vl_sql = f"MAP({', '.join(entries)})"

        spark.sql(f"""
            INSERT INTO {TABLE}
              (rule_id, version, effective_from, effective_to, owner_role,
               statement_text, expression_sql, params, value_lists,
               status, created_by, created_at, owner_office, required_action,
               area, blocked_reason)
            VALUES (
                :rule_id, {int(r['version'])},
                TIMESTAMP '{now}', NULL,
                {sq(r['owner_role'])},
                {sq(r['statement_text'])},
                {sq(r.get('expression_sql'))},
                {params_sql}, {vl_sql},
                {sq(r['status'])},
                :actor, TIMESTAMP '{now}',
                {sq(r.get('owner_office'))}, {sq(r.get('required_action'))},
                {sq(r.get('area'))}, {sq(r.get('blocked_reason'))}
            )
        """, args=bound)

        # Audit row (same bound values: rule_id, actor, audit_id, params markers)
        spark.sql(f"""
            INSERT INTO {AUDIT}
              (audit_id, rule_id, version, event, actor, actor_role,
               event_at, prior_params, new_params, notes)
            VALUES (
                :audit_id, :rule_id, {int(r['version'])},
                'insert', :actor, NULL,
                TIMESTAMP '{now}', NULL, {params_sql},
                'Initial seed from spec'
            )
        """, args=bound)
        inserted += 1

    return inserted, skipped


if __name__ == "__main__":
    from pyspark.sql import SparkSession
    spark = SparkSession.getActiveSession() or SparkSession.builder.getOrCreate()
    ins, skip = seed(spark)
    print(f"seed_rules: {ins} inserted, {skip} skipped")
