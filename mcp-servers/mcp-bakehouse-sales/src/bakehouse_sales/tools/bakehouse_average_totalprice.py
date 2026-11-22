"""Average totalPrice.

How many transactions and what average ticket size did a franchise have?

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

    bakehouse_average_totalprice
    """

    @mcp.tool(
        name="bakehouse_average_totalprice",
        annotations={
            "title": "Average totalPrice",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    def bakehouse_average_totalprice(
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
        """How many transactions and what average ticket size did a franchise have?

        One record is one point-of-sale transaction for one product line. The source
        refreshes static sample and currently reflects the as_of value in the response.

        Returns: Record count and the measure's sum, mean, minimum and maximum.

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
            measure_column = column("totalPrice", COLUMNS)
            sql = (
                f"SELECT COUNT(*) AS record_count, "  # nosemgrep # nosec B608
                f"SUM({measure_column}) AS measure_total, "
                f"AVG({measure_column}) AS measure_mean, "
                f"MIN({measure_column}) AS measure_min, "
                f"MAX({measure_column}) AS measure_max "
                f"FROM {TABLE}{where}"
            )
            rows = run_query(sql, list(params))
        except (ValueError, WarehouseError) as error:
            return {
                "error": str(error),
                "hint": "Drop a filter, or check the period.",
            }
        return {
            "as_of": AS_OF,
            "measure": "totalPrice",
            "totals": rows[0] if rows else {},
            "filters_applied": len(clauses),
        }
