"""Describe Bakehouse sales transactions.

Tell me what is in Bakehouse sales transactions: the fields, what they mean, the allowed
values, and how fresh it is.

Source: sales (uc_table).
"""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from mcp_bakehouse_sales.data import sources

AS_OF = sources.SALES_AS_OF


def register(mcp: FastMCP) -> None:
    """Register the mcp_describe_sales tool with the MCP server."""

    @mcp.tool(
        name="mcp_describe_sales",
        annotations={
            "title": "Describe Bakehouse sales transactions",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    def mcp_describe_sales() -> dict[str, Any]:
        """Tell me what is in Bakehouse sales transactions: the fields, what they mean,
        the allowed values, and how fresh it is.

        One record is one point-of-sale transaction for one product line. The source
        refreshes static sample and currently reflects the as_of value in the response.

        Returns: The source's grain, update cadence, as-of date, and every field with
        its type, role, description, and allowed values.

        This tool needs no credentials and no query: the dictionary ships with the
        server.

        Does not cover: Customer personal details such as names, emails or addresses;
        Forecasting future sales; Changing or deleting any sales record.
        """
        fields = [
            {
                "name": "transactionID",
                "type": "bigint",
                "role": "measure",
                "description": "",
                "example": "",
                "allowed_values": None,
            },
            {
                "name": "customerID",
                "type": "bigint",
                "role": "measure",
                "description": "",
                "example": "",
                "allowed_values": None,
            },
            {
                "name": "franchiseID",
                "type": "bigint",
                "role": "measure",
                "description": "",
                "example": "",
                "allowed_values": None,
            },
            {
                "name": "dateTime",
                "type": "timestamp",
                "role": "date",
                "description": "",
                "example": "",
                "allowed_values": None,
            },
            {
                "name": "product",
                "type": "string",
                "role": "dimension",
                "description": "",
                "example": "",
                "allowed_values": [
                    "Austin Almond Biscotti",
                    "Golden Gate Ginger",
                    "Orchard Oasis",
                    "Outback Oatmeal",
                    "Pearly Pies",
                    "Tokyo Tidbits",
                ],
            },
            {
                "name": "quantity",
                "type": "bigint",
                "role": "measure",
                "description": "",
                "example": "",
                "allowed_values": None,
            },
            {
                "name": "unitPrice",
                "type": "bigint",
                "role": "measure",
                "description": "",
                "example": "",
                "allowed_values": None,
            },
            {
                "name": "totalPrice",
                "type": "bigint",
                "role": "measure",
                "description": "",
                "example": "",
                "allowed_values": None,
            },
            {
                "name": "paymentMethod",
                "type": "string",
                "role": "dimension",
                "description": "",
                "example": "",
                "allowed_values": ["amex", "mastercard", "visa"],
            },
            {
                "name": "cardNumber",
                "type": "bigint",
                "role": "measure",
                "description": "",
                "example": "",
                "allowed_values": None,
            },
        ]
        return {
            "source": "sales",
            "kind": sources.SALES_KIND,
            "grain": sources.SALES_GRAIN,
            "update_cadence": sources.SALES_CADENCE,
            "as_of": sources.SALES_AS_OF,
            "field_count": len(fields),
            "fields": fields,
            "note": (
                "Read this before calling the other tools: it gives "
                "the exact column spellings and the allowed values."
            ),
        }
