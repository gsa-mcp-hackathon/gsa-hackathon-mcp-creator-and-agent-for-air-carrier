"""Top product by transactionID.

Which product accounts for the most transactionID?

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
    """Register the mcp_top_product_by_transactionid tool with the MCP server."""

    @mcp.tool(
        name="mcp_top_product_by_transactionid",
        annotations={
            "title": "Top product by transactionID",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    def mcp_top_product_by_transactionid(
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
        limit: Annotated[
            int,
            Field(
                description="Maximum rows to return.",
                ge=1,
                le=100,
            ),
        ] = 20,
        offset: Annotated[
            int,
            Field(
                description="Rows to skip from the start.",
                ge=0,
            ),
        ] = 0,
    ) -> dict[str, Any]:
        """Which product accounts for the most transactionID?

        One record is one point-of-sale transaction for one product line. The source
        refreshes static sample and currently reflects the as_of value in the response.

        Returns: The top groups with their measure total, record count, and share of the
        whole, plus the population totals so the share can be stated honestly.

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
            group_column = column("product", COLUMNS)
            measure_column = column("transactionID", COLUMNS)
            sql = (
                f"SELECT {group_column} AS group_value, "
                f"SUM({measure_column}) AS measure_total, "
                f"COUNT(*) AS record_count "
                f"FROM {TABLE}{where} "
                f"GROUP BY {group_column} "
                f"ORDER BY measure_total DESC LIMIT ?"
            )
            rows = run_query(sql, list(params) + [limit])
            overall = run_query(
                f"SELECT SUM({measure_column}) AS measure_total, "
                f"COUNT(*) AS record_count, "
                f"COUNT(DISTINCT {group_column}) AS group_count "
                f"FROM {TABLE}{where}",
                list(params),
            )
        except (ValueError, WarehouseError) as error:
            return {
                "error": str(error),
                "hint": "Drop a filter, or widen the period.",
            }
        population = overall[0] if overall else {}
        grand_total = float(population.get("measure_total") or 0)
        for row in rows:
            value = float(row.get("measure_total") or 0)
            row["share_of_total"] = (
                round(value / grand_total, 4) if grand_total else None
            )
        return {
            "as_of": AS_OF,
            "ranked_by": "transactionID",
            "grouped_by": "product",
            "items": rows,
            "population": population,
        }
