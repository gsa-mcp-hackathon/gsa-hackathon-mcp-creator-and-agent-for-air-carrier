"""Call the read tools on live data and report any answer its output schema refuses.

Each tool declares a return model, and FastMCP checks every answer against it
before the answer leaves the server. The contract tests (contract/ in each
server) prove the models on fixtures. This proves them on the tables: it runs
the docs, analyst and ops servers in-process through mcp_local, as the person
calling, and calls every tool that only reads. Arguments come from earlier
answers (a real artifact id, a real table id, a real File C period), so the
answers carry the values the warehouse really holds.

Nothing is written. mcp_local refuses writes, so an analyst lead is answered
and not logged. Two tools are not called: analyst_record_outcome (it writes)
and docs_parse_pdf (it needs a PDF in a volume).

Use the notebook "Output Schema Live Check" beside this file, or:

    import mcp_local, live_schema_check
    rows = live_schema_check.run(mcp_local.call)
    print(live_schema_check.report(rows))
"""
from __future__ import annotations

import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

SCHEMA_ERROR = "Output validation error"   # how FastMCP reports an answer its schema refuses
NOT_CALLED = {"analyst_record_outcome": "writes a training label",
              "docs_parse_pdf": "needs a PDF in a Unity Catalog volume"}
PIIDS = ("N0002415C2114", "N0002409C2116")
CONTRACTS = ("N00024-15-C-2114", "N00024-09-C-2116")
RECORD = {"GL Amount": "$454,765,071.00", "Memo": "SCN progress payment CVN 79"}
_PERIOD = re.compile(r"^FY(\d{4})(?:Q([1-4])|P(\d{2}))$")

FITS, REFUSED, SCHEMA = "fits", "refused", "SCHEMA MISMATCH"


@dataclass
class Row:
    server: str
    tool: str
    arguments: dict[str, Any]
    outcome: str      # FITS, REFUSED (the tool's own error) or SCHEMA
    detail: str
    ms: int


def _first(items: Any) -> dict[str, Any]:
    """The first dict in a list, or {} when there is none."""
    return items[0] if isinstance(items, list) and items and isinstance(items[0], dict) else {}


def _window(period: str) -> tuple[int, int, int] | None:
    """FY2021P03 -> (2021, 3, 3); FY2019Q2 -> (2019, 4, 6)."""
    m = _PERIOD.match(period or "")
    if not m:
        return None
    year = int(m.group(1))
    if m.group(2):
        quarter = int(m.group(2))
        return year, quarter * 3 - 2, quarter * 3
    return year, int(m.group(3)), int(m.group(3))


def run(call: Callable[..., dict[str, Any]], slow: bool = True) -> list[Row]:
    """Call every read tool once or more. `call` is mcp_local.call. slow=False skips the backtest."""
    rows: list[Row] = []

    def ask(server: str, tool: str, **arguments: Any) -> Any:
        """Record one call; return its result when the answer fits, else None."""
        start = time.time()
        try:
            answer = call(server, tool, **arguments)
        except Exception as error:  # noqa: BLE001 - one broken call must not end the check
            answer = {"ok": False, "error": f"{type(error).__name__}: {error}"}
        ms = int((time.time() - start) * 1000)
        if answer.get("ok"):
            rows.append(Row(server, tool, arguments, FITS, "", ms))
            return answer.get("result")
        text = str(answer.get("error") or "")
        rows.append(Row(server, tool, arguments, SCHEMA if SCHEMA_ERROR in text else REFUSED,
                        " ".join(text.split())[:300], ms))
        return None

    _docs(ask)
    _analyst(ask, slow)
    _ops(ask)
    return rows


def _docs(ask: Callable[..., Any]) -> None:
    ask("docs", "docs_status")
    documents = ask("docs", "docs_list_documents") or []
    book = next((d for d in documents if d.get("kind") == "budget_justification"), _first(documents))
    hit = _first((ask("docs", "docs_search", query="Total Ship Estimate") or {}).get("hits"))
    artifact = hit.get("artifact_id") or book.get("artifact_id")
    if artifact:
        ask("docs", "docs_document_map", artifact_id=artifact)
        page = hit.get("page") or 1
        ask("docs", "docs_read_page", artifact_id=artifact, page=page)
        ask("docs", "docs_tieout_document", artifact_id=artifact, first_page=page, last_page=page)
    line = ask("docs", "docs_find_line_item", line_item="2001") or {}
    ask("docs", "docs_find_line_item", line_item="2001", budget_cycle="PB2001")   # a book that is not loaded
    chains = _first(line.get("sections")).get("table_chains") or []
    table = hit.get("table_id") or (chains[0] if chains else None)
    if table:
        ask("docs", "docs_get_table", table_id=table)
    ask("docs", "docs_find_figure", value_musd="13409.97")
    ask("docs", "docs_find_figure", value_musd="1.23")                           # printed nowhere
    ask("docs", "docs_compare_figures", figures=[{"label": "total ship estimate", "value_musd": "13409.97"},
                                                 {"label": "printed nowhere", "value_musd": "1.23"}])


def _analyst(ask: Callable[..., Any], slow: bool) -> None:
    ask("analyst", "analyst_list_sources")
    ask("analyst", "analyst_search_documents", query="N00024-15-C-2114")
    ask("analyst", "analyst_trace_entity", entity="CVN-79")
    ask("analyst", "analyst_profile_record", record=RECORD)
    ask("analyst", "analyst_investigate_record", record=RECORD)
    ask("analyst", "analyst_investigate_record", record=RECORD, detail="full")
    ask("analyst", "analyst_model_status")
    for piid in PIIDS:
        questions = ask("analyst", "analyst_open_questions", piid=piid) or {}
        key = _first(questions.get("largest_unattributed_transactions")).get("transaction_key")
        if key:
            ask("analyst", "analyst_investigate_transaction", piid=piid, transaction_key=key)
        residual = _first(questions.get("residual_periods")).get("period")
        tied = (questions.get("tied_periods") or [None])[0]
        for period in (residual, tied):     # one period that does not tie, one that does
            if period:
                ask("analyst", "analyst_explain_residual", piid=piid, submission_period=period)
        month = _first(questions.get("uncovered_months"))
        window = ((month["fiscal_year"], month["period"], month["period"]) if month
                  else _window(residual or tied or ""))
        if window:
            ask("analyst", "analyst_investigate_window", piid=piid, fiscal_year=window[0],
                first_period=window[1], last_period=window[2])
    if slow:
        ask("analyst", "analyst_backtest", piid=PIIDS[0])


def _ops(ask: Callable[..., Any]) -> None:
    found = ask("ops", "carrier_search_exhibit_cells", query="Total Ship Estimate") or {}
    table = _first(found.get("items")).get("table_id")
    if table:
        ask("ops", "carrier_get_exhibit_cells", table_id=table)
    ask("ops", "carrier_get_exhibit_cells", table_id="no-such-table")           # the tool's own error body
    ask("ops", "carrier_search_graph_edges", query="CVN-79")
    for contract in CONTRACTS:
        ask("ops", "carrier_search_obligations", contract=contract, order="largest_first")
    ask("ops", "carrier_search_obligations", contract=CONTRACTS[0], detail="full", limit=3)
    ask("ops", "carrier_search_variances")
    ask("ops", "carrier_search_work_register", query="CVN")
    ask("ops", "carrier_work_register_counts")


def mismatches(rows: list[Row]) -> list[Row]:
    """The answers a schema refused. Each one is a tool that would fail for a user."""
    return [r for r in rows if r.outcome == SCHEMA]


def not_validated(rows: list[Row], tools: dict[str, list[str]]) -> list[str]:
    """Tools with no fitting answer in this run, other than the two never called."""
    fitted = {r.tool for r in rows if r.outcome == FITS}
    return sorted(name for names in tools.values() for name in names
                  if name not in fitted and name not in NOT_CALLED)


def report(rows: list[Row], tools: dict[str, list[str]] | None = None) -> str:
    """One line per call, then the verdict."""
    lines = [f"{'server':8} {'tool':34} {'outcome':16} {'ms':>6}  detail"]
    for r in rows:
        shown = r.detail or ", ".join(f"{k}={str(v)[:28]}" for k, v in r.arguments.items())
        lines.append(f"{r.server:8} {r.tool:34} {r.outcome:16} {r.ms:>6}  {shown[:150]}")
    bad = mismatches(rows)
    lines.append("")
    lines.append(f"{len(rows)} calls: {sum(r.outcome == FITS for r in rows)} fit, "
                 f"{sum(r.outcome == REFUSED for r in rows)} refused in the tool's own words, "
                 f"{len(bad)} refused by an output schema.")
    if tools is not None:
        missing = not_validated(rows, tools)
        lines.append("Every tool that only reads had an answer that fits." if not missing
                     else "No fitting answer for: " + ", ".join(missing))
    lines.append("Not called: " + "; ".join(f"{k} ({v})" for k, v in NOT_CALLED.items()) + ".")
    return "\n".join(lines)
