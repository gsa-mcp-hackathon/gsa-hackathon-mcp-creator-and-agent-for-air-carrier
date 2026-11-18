"""Harness table and function names. One import, one place to change at transfer.

Every harness module reads these constants. No module spells a table name.
The schema comes from core.catalog.STORE_SCHEMA, which reads AIRCARRIER_STORE_SCHEMA.
"""
from core.catalog import STORE_SCHEMA

_P = f"{STORE_SCHEMA}.aircarrier_app_"
_T = f"{STORE_SCHEMA}.aircarrier_tool_"

# Application tables (harness_ddl.sql)
RULE_REGISTER = _P + "rule_register"
RULE_REGISTER_AUDIT = _P + "rule_register_audit"
EXCEPTIONS = _P + "exceptions"
AGENT_RUNS = _P + "agent_runs"
AGENT_STEPS = _P + "agent_steps"
CHECKER_VERDICTS = _P + "checker_verdicts"
PROPOSALS = _P + "proposals"
DECISIONS = _P + "decisions"
DOCUMENTS = _P + "documents"
MODEL_RUNS = _P + "model_runs"
RULE_EVALS = _P + "rule_evals"
DETERMINATIONS = _P + "determinations"
METRICS = _P + "metrics"
ROLE_MAP = _P + "role_map"
AUTHORITY = _P + "authority"

# Views
CURRENT_RULES = _P + "current_rules"

# UC SQL tool functions (harness_tools.sql)
TOOL_GET_EXCEPTION = _T + "get_exception"
TOOL_GET_RULE = _T + "get_rule"
TOOL_GET_DOCUMENT_TEXT = _T + "get_document_text"
TOOL_GET_COST_CAPTURE = _T + "get_cost_capture"
TOOL_GET_EVM_CONTROL_ACCOUNT = _T + "get_evm_control_account"
TOOL_GET_CAP_LEDGER = _T + "get_cap_ledger"
TOOL_GET_CIP_TRANSACTIONS = _T + "get_cip_transactions"
