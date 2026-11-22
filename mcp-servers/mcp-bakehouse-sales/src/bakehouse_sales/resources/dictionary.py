"""Data dictionary resources.

A client can read these without spending a tool call, which is
the cheapest way to stop a model guessing column semantics.
"""

from __future__ import annotations

import json

from fastmcp import FastMCP

CATALOGUE = {
    "sales": {
        "kind": "uc_table",
        "modality": "structured",
        "title": "Bakehouse sales transactions",
        "grain": "one point-of-sale transaction for one product line",
        "update_cadence": "static sample",
        "as_of": "",
        "fields": [
            {
                "name": "transactionID",
                "type": "bigint",
                "role": "identifier",
                "description": "",
                "allowed_values": None,
            },
            {
                "name": "customerID",
                "type": "bigint",
                "role": "identifier",
                "description": "",
                "allowed_values": None,
            },
            {
                "name": "franchiseID",
                "type": "bigint",
                "role": "identifier",
                "description": "",
                "allowed_values": None,
            },
            {
                "name": "dateTime",
                "type": "date",
                "role": "date",
                "description": "",
                "allowed_values": None,
            },
            {
                "name": "product",
                "type": "string",
                "role": "dimension",
                "description": "",
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
                "allowed_values": None,
            },
            {
                "name": "unitPrice",
                "type": "bigint",
                "role": "measure",
                "description": "",
                "allowed_values": None,
            },
            {
                "name": "totalPrice",
                "type": "bigint",
                "role": "measure",
                "description": "",
                "allowed_values": None,
            },
            {
                "name": "paymentMethod",
                "type": "string",
                "role": "dimension",
                "description": "",
                "allowed_values": ["amex", "mastercard", "visa"],
            },
            {
                "name": "cardNumber",
                "type": "bigint",
                "role": "identifier",
                "description": "",
                "allowed_values": None,
            },
        ],
    }
}


def register(mcp: FastMCP) -> None:
    """Register the dictionary resources with the server."""

    @mcp.resource("bakehouse://dictionary/sources")
    def source_catalogue() -> str:
        """Every source behind this server, with its fields."""
        return json.dumps(CATALOGUE, indent=2, default=str)

    @mcp.resource("bakehouse://dictionary/{source}")
    def source_dictionary(source: str) -> str:
        """The field list for one named source."""
        entry = CATALOGUE.get(source)
        if entry is None:
            known = ", ".join(sorted(CATALOGUE))
            return json.dumps(
                {
                    "error": f"unknown source {source!r}",
                    "known_sources": known,
                },
                indent=2,
            )
        return json.dumps(entry, indent=2, default=str)
