"""Coordinates and freshness metadata for every data source.

Generated from the server specification. Edit here rather than in the tools,
so a table move or a refresh change is a one-line edit.
"""

from __future__ import annotations

# --- sales: Bakehouse sales transactions
SALES_KIND = "uc_table"
SALES_GRAIN = "one point-of-sale transaction for one product line"
SALES_CADENCE = "static sample"
SALES_AS_OF = ""
SALES_CATALOG = "samples"
SALES_SCHEMA = "bakehouse"
SALES_TABLE = "sales_transactions"
SALES_COLUMNS = (
    "transactionID",
    "customerID",
    "franchiseID",
    "dateTime",
    "product",
    "quantity",
    "unitPrice",
    "totalPrice",
    "paymentMethod",
    "cardNumber",
)
