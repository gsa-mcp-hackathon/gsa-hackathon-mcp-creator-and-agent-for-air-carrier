"""Daily total totalPrice.

What was total revenue per day over a date range?

Source: sales (uc_table).
"""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp import FastMCP
from pydantic import Field

from bakehouse_sales.data import sources
from bakehouse_sales.data.warehouse import (
    WarehouseError,
    column,
    qualified,
    run_query,
)
from bakehouse_sales.models import PaymentmethodValue, ProductValue

TABLE = qualified(
    sources.SALES_CATALOG,
    sources.SALES_SCHEMA,
    sources.SALES_TABLE,
)
COLUMNS = sources.SALES_COLUMNS
AS_OF = sources.SALES_AS_OF


def register(mcp: FastMCP) -> None:
    """Register this tool with the MCP server:

    bakehouse_daily_totalprice
    """

    @mcp.tool(
        name="bakehouse_daily_totalprice",
        annotations={
            "title": "Daily total totalPrice",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    def bakehouse_daily_totalprice(
        start_date: Annotated[
            str,
            Field(
                description=(
                    "First day to include, YYYY-MM-DD. Work out relative periods such "
                    "as 'last month' from today's date. Empty for no bound."
                ),
            ),
        ] = "",
        end_date: Annotated[
            str,
            Field(
                description=(
                    "Day after the last day to include, YYYY-MM-DD (exclusive). Empty "
                    "for no bound."
                ),
            ),
        ] = "",
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
        """What was total revenue per day over a date range?

        One record is one point-of-sale transaction for one product line. The source
        refreshes static sample and currently reflects the as_of value in the response.

        Returns: One row per day with the total totalPrice and record count, plus the
        change and percentage change against the prior period.

        Does not cover: Customer personal details such as names, emails or addresses;
        Forecasting future sales; Changing or deleting any sales record.
        """
        filter_start_date = start_date.strip()
        filter_end_date = end_date.strip()
        filter_product = "" if product is ProductValue.ANY else product.value
        filter_paymentmethod = (
            "" if paymentmethod is PaymentmethodValue.ANY else paymentmethod.value
        )
        clauses: list[str] = []
        params: list[Any] = []
        if filter_start_date:
            clauses.append(column("dateTime", COLUMNS) + " >= ?")
            params.append(filter_start_date)
        if filter_end_date:
            clauses.append(column("dateTime", COLUMNS) + " < ?")
            params.append(filter_end_date)
        if filter_product:
            clauses.append(column("product", COLUMNS) + " = ?")
            params.append(filter_product)
        if filter_paymentmethod:
            clauses.append(column("paymentMethod", COLUMNS) + " = ?")
            params.append(filter_paymentmethod)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        try:
            date_column = column("dateTime", COLUMNS)
            measure_column = column("totalPrice", COLUMNS)
            sql = (
                f"SELECT date_trunc('DAY', {date_column}) "  # nosemgrep # nosec B608
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
            "measure": "totalPrice",
            "granularity": "day",
            "periods": rows,
        }
