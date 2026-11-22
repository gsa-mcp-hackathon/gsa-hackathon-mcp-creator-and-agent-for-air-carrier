"""Top paymentMethod by total totalPrice.

How does revenue split by payment method?

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
from bakehouse_sales.models import ProductValue

TABLE = qualified(
    sources.SALES_CATALOG,
    sources.SALES_SCHEMA,
    sources.SALES_TABLE,
)
COLUMNS = sources.SALES_COLUMNS
AS_OF = sources.SALES_AS_OF


def register(mcp: FastMCP) -> None:
    """Register this tool with the MCP server:

    bakehouse_top_paymentmethod_by_totalprice
    """

    @mcp.tool(
        name="bakehouse_top_paymentmethod_by_totalprice",
        annotations={
            "title": "Top paymentMethod by total totalPrice",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    def bakehouse_top_paymentmethod_by_totalprice(
        start_date: Annotated[
            str,
            Field(
                description=(
                    "First day to include, YYYY-MM-DD. Work out relative periods such "
                    "as 'last month' from today's date. Empty for no bound."
                ),
                max_length=32,
            ),
        ] = "",
        end_date: Annotated[
            str,
            Field(
                description=(
                    "Day after the last day to include, YYYY-MM-DD (exclusive). Empty "
                    "for no bound."
                ),
                max_length=32,
            ),
        ] = "",
        product: Annotated[
            ProductValue,
            Field(
                description=("Narrow results to one product."),
            ),
        ] = ProductValue.ANY,
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
        """How does revenue split by payment method?

        One record is one point-of-sale transaction for one product line. The source
        refreshes static sample and currently reflects the as_of value in the response.

        Returns: Groups of paymentMethod ordered by total totalPrice, with record counts
        and, for totals and counts, each group's share.

        Does not cover: Customer personal details such as names, emails or addresses;
        Forecasting future sales; Changing or deleting any sales record.
        """
        filter_start_date = start_date.strip()
        filter_end_date = end_date.strip()
        filter_product = "" if product is ProductValue.ANY else product.value
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
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        try:
            group_column = column("paymentMethod", COLUMNS)
            measure_column = column("totalPrice", COLUMNS)
            sql = (
                f"SELECT {group_column} AS group_value, "  # nosemgrep # nosec B608
                f"SUM({measure_column}) AS measure_total, "
                f"COUNT(*) AS record_count "
                f"FROM {TABLE}{where} "
                f"GROUP BY {group_column} "
                f"ORDER BY measure_total DESC LIMIT ?"
            )
            rows = run_query(sql, list(params) + [limit])
            overall = run_query(
                f"SELECT SUM({measure_column}) "  # nosemgrep # nosec B608
                "AS measure_total, "
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
            "ranked_by": "totalPrice",
            "aggregation": "sum",
            "grouped_by": "paymentMethod",
            "items": rows,
            "population": population,
        }
