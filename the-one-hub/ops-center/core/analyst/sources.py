"""Load the analyst corpus from the lossless source tables.

The only module that touches Spark or SQL. Every value is read verbatim from
the aircarrier_src_* tables (strings) and converted to integer cents here.
Rows that are not obligations of the named PIID are never loaded: the keyset
rule (E-15) says 09-C-2116 and 16-C-2116 are different hulls, so matching
is on the exact PIID, never a fuzzy one.
"""
from __future__ import annotations

from core import catalog
from core.analyst import engine, loa

_P = f"{catalog.STORE_SCHEMA}.aircarrier_src_"
TX_TABLES = {
    "N0002415C2114": _P + "2114_contract_transactions",
    "N0002409C2116": _P + "2116_contract_transactions",
}
FC_TABLES = {
    "N0002415C2114": _P + "2114_federal_account_funding",
}
TX_COLS = ("contract_transaction_unique_key", "award_id_piid", "action_date", "modification_number",
           "federal_action_obligation", "action_type_code", "transaction_description",
           "treasury_accounts_funding_this_award", "object_classes_funding_this_award",
           "program_activities_funding_this_award", "_source_locator", "_row_num")


def tx_from_row(r: dict) -> engine.Tx:
    return engine.Tx(
        key=r["contract_transaction_unique_key"],
        piid=r["award_id_piid"],
        date=r["action_date"],
        mod=r["modification_number"],
        amount=loa.cents(r["federal_action_obligation"]),
        action_type=r.get("action_type_code") or "",
        desc=r.get("transaction_description") or "",
        award_tas=tuple(loa.split_list(r.get("treasury_accounts_funding_this_award"))),
        award_oc=tuple(loa.split_list(r.get("object_classes_funding_this_award"))),
        award_pa=tuple(loa.split_list(r.get("program_activities_funding_this_award"))),
    )


def fc_from_row(r: dict) -> engine.FCRow:
    return engine.FCRow(
        period=r["submission_period"], piid=r["award_id_piid"], tas=r["treasury_account_symbol"],
        oc=r.get("object_class_code") or "", pa=r.get("program_activity_code") or "",
        amount=loa.cents(r["transaction_obligated_amount"]),
        locator=f"{r.get('_source_locator', '')}#row{r.get('_row_num', '')}",
    )


def load_spark(spark, piids: list[str] | None = None) -> engine.Corpus:
    piids = piids or list(TX_TABLES)
    tx, fc = [], []
    for p in piids:
        df = spark.table(TX_TABLES[p]).select(*TX_COLS).where(f"award_id_piid = '{p}'")
        tx += [tx_from_row(r.asDict()) for r in df.collect()]
        if p in FC_TABLES:
            fdf = spark.table(FC_TABLES[p]).where(f"award_id_piid = '{p}'")
            fc += [fc_from_row(r.asDict()) for r in fdf.collect()]
    return engine.Corpus(tx, fc)


def load_rows(tx_rows: list[dict], fc_rows: list[dict]) -> engine.Corpus:
    """For the MCP server and tests: rows already fetched as dicts."""
    return engine.Corpus([tx_from_row(r) for r in tx_rows], [fc_from_row(r) for r in fc_rows])
