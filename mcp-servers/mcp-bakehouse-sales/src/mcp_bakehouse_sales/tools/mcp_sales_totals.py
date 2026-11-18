"""Bakehouse sales transactions totals.

Give me the totals for Bakehouse sales transactions: how many records and how much
transactionID.

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
    """Register the mcp_sales_totals tool with the MCP server."""

    @mcp.tool(
        name="mcp_sales_totals",
        annotations={
            "title": "Bakehouse sales transactions totals",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    def mcp_sales_totals(
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
        """Give me the totals for Bakehouse sales transactions: how many records and how
        much transactionID.

        One record is one point-of-sale transaction for one product line. The source
        refreshes static sample and currently reflects the as_of value in the response.

        Returns: Record count and the measure's sum, mean, minimum, and maximum for the
        filtered scope.

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
            measure_column = column("transactionID", COLUMNS)
            sql = (
                f"SELECT COUNT(*) AS record_count, "
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
            "measure": "transactionID",
            "totals": rows[0] if rows else {},
            "filters_applied": len(clauses),
        }
