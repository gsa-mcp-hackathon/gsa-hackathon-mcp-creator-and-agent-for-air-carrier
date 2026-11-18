"""Bakehouse sales transactions over time.

How has transactionID moved month by month, and where did it change most?

Source: sales (uc_table).
"""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp import FastMCP
from pydantic import Field

from mcp_bakehouse_sales.data import sources
from mcp_bakehouse_sales.data.warehouse import (
    WarehouseError,
    column,
    qualified,
    run_query,
)
from mcp_bakehouse_sales.models import PaymentmethodValue, ProductValue

TABLE = qualified(
    sources.SALES_CATALOG,
    sources.SALES_SCHEMA,
    sources.SALES_TABLE,
)
COLUMNS = sources.SALES_COLUMNS
AS_OF = sources.SALES_AS_OF


def register(mcp: FastMCP) -> None:
    """Register the mcp_sales_trend tool with the MCP server."""

    @mcp.tool(
        name="mcp_sales_trend",
        annotations={
            "title": "Bakehouse sales transactions over time",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    def mcp_sales_trend(
        product: Annotated[
            ProductValue,
            Field(
                description=("Narrow results to one product."),
            ),
        ] = ProductValue.ANY,
        paymentmethod: Annotated[
            PaymentmethodValue,
            Field(
                description=("Narrow results to one paymentMethod."),
            ),
        ] = PaymentmethodValue.ANY,
    ) -> dict[str, Any]:
        """How has transactionID moved month by month, and where did it change most?

        One record is one point-of-sale transaction for one product line. The source
        refreshes static sample and currently reflects the as_of value in the response.

        Returns: One row per month with the measure total, record count, and the change
        and percentage change against the prior month, computed server-side.

        Does not cover: Customer personal details such as names, emails or addresses;
        Forecasting future sales; Changing or deleting any sales record.
        """
        filter_product = "" if product is ProductValue.ANY else product.value
        filter_paymentmethod = (
            "" if paymentmethod is PaymentmethodValue.ANY else paymentmethod.value
        )
        clauses: list[str] = []
        params: list[Any] = []
        if filter_product:
            clauses.append(f"{column('product', COLUMNS)} = ?")
            params.append(filter_product)
        if filter_paymentmethod:
            clauses.append(f"{column('paymentMethod', COLUMNS)} = ?")
            params.append(filter_paymentmethod)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        try:
            date_column = column("dateTime", COLUMNS)
            measure_column = column("transactionID", COLUMNS)
            sql = (
                f"SELECT date_trunc('MONTH', {date_column}) "
                f"AS period, "
                f"SUM({measure_column}) AS measure_total, "
                f"COUNT(*) AS record_count "
                f"FROM {TABLE}{where} "
                f"GROUP BY period ORDER BY period"
            )
            rows = run_query(sql, list(params))
        except (ValueError, WarehouseError) as error:
            return {
                "error": str(error),
                "hint": "Check the date filter; the period may be empty.",
            }
        previous: float | None = None
        for row in rows:
            current = row.get("measure_total")
            if current is None:
                current = row.get("record_count")
            current = float(current or 0)
            row["change_from_prior"] = (
                round(current - previous, 4) if previous is not None else None
            )
            row["pct_change_from_prior"] = (
                round((current - previous) / previous, 4) if previous else None
            )
            previous = current
        return {
            "as_of": AS_OF,
            "date_field": "dateTime",
            "measure": "transactionID",
            "granularity": "month",
            "periods": rows,
        }
