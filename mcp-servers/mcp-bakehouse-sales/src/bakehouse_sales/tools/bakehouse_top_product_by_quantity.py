"""Top product by total quantity.

What are the top 5 best-selling products by quantity for a given franchise?

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
from bakehouse_sales.models import PaymentmethodValue

TABLE = qualified(
    sources.SALES_CATALOG,
    sources.SALES_SCHEMA,
    sources.SALES_TABLE,
)
COLUMNS = sources.SALES_COLUMNS
AS_OF = sources.SALES_AS_OF


def register(mcp: FastMCP) -> None:
    """Register this tool with the MCP server:

    bakehouse_top_product_by_quantity
    """

    @mcp.tool(
        name="bakehouse_top_product_by_quantity",
        annotations={
            "title": "Top product by total quantity",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    def bakehouse_top_product_by_quantity(
        franchiseid: Annotated[
            str,
            Field(
                description=("Only rows for this franchiseID. Leave empty for all."),
                max_length=256,
            ),
        ] = "",
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
        """What are the top 5 best-selling products by quantity for a given franchise?

        One record is one point-of-sale transaction for one product line. The source
        refreshes static sample and currently reflects the as_of value in the response.

        Returns: Groups of product ordered by total quantity, with record counts and,
        for totals and counts, each group's share.

        Does not cover: Customer personal details such as names, emails or addresses;
        Forecasting future sales; Changing or deleting any sales record.
        """
        filter_franchiseid = franchiseid.strip()
        filter_start_date = start_date.strip()
        filter_end_date = end_date.strip()
        filter_paymentmethod = (
            "" if paymentmethod is PaymentmethodValue.ANY else paymentmethod.value
        )
        clauses: list[str] = []
        params: list[Any] = []
        if filter_franchiseid:
            clauses.append(column("franchiseID", COLUMNS) + " = ?")
            params.append(filter_franchiseid)
        if filter_start_date:
            clauses.append(column("dateTime", COLUMNS) + " >= ?")
            params.append(filter_start_date)
        if filter_end_date:
            clauses.append(column("dateTime", COLUMNS) + " < ?")
            params.append(filter_end_date)
        if filter_paymentmethod:
            clauses.append(column("paymentMethod", COLUMNS) + " = ?")
            params.append(filter_paymentmethod)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        try:
            group_column = column("product", COLUMNS)
            measure_column = column("quantity", COLUMNS)
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
            "ranked_by": "quantity",
            "aggregation": "sum",
            "grouped_by": "product",
            "items": rows,
            "population": population,
        }
