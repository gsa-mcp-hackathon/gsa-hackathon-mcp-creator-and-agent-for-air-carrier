"""Get one Bakehouse sales transactions record.

Show me the full Bakehouse sales transactions record for one identifier.

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

TABLE = qualified(
    sources.SALES_CATALOG,
    sources.SALES_SCHEMA,
    sources.SALES_TABLE,
)
COLUMNS = sources.SALES_COLUMNS
AS_OF = sources.SALES_AS_OF


def register(mcp: FastMCP) -> None:
    """Register this tool with the MCP server:

    bakehouse_get_sales
    """

    @mcp.tool(
        name="bakehouse_get_sales",
        annotations={
            "title": "Get one Bakehouse sales transactions record",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    def bakehouse_get_sales(
        transactionid: Annotated[
            str,
            Field(
                description=("Exact transactionID to fetch. Example: 1000000."),
            ),
        ],
    ) -> dict[str, Any]:
        """Show me the full Bakehouse sales transactions record for one identifier.

        One record is one point-of-sale transaction for one product line. The source
        refreshes static sample and currently reflects the as_of value in the response.

        Returns: The matching record, plus the field used to find it. An error with a
        hint when nothing matches.

        Does not cover: Customer personal details such as names, emails or addresses;
        Forecasting future sales; Changing or deleting any sales record.
        """
        try:
            key_column = column("transactionID", COLUMNS)
            select_list = ", ".join(
                column(name, COLUMNS)
                for name in [
                    "transactionID",
                    "franchiseID",
                    "dateTime",
                    "product",
                    "quantity",
                    "unitPrice",
                    "totalPrice",
                    "paymentMethod",
                ]
            )
            sql = (
                f"SELECT {select_list} FROM {TABLE} "  # nosemgrep # nosec B608
                f"WHERE {key_column} = ? LIMIT 1"  # nosemgrep
            )
            rows = run_query(sql, [transactionid])
        except (ValueError, WarehouseError) as error:
            return {
                "error": str(error),
                "hint": "Check the identifier format and try again.",
            }
        if not rows:
            return {
                "error": f"No record matched {transactionid!r}.",
                "hint": (
                    "Identifiers are exact. Call the describe tool "
                    "for the field list and example values."
                ),
                "as_of": AS_OF,
            }
        return {
            "as_of": AS_OF,
            "record": rows[0],
            "fields_used": ["transactionID"],
        }
