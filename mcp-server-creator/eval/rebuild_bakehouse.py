"""Rebuild mcp-servers/mcp-bakehouse-sales through the Creator's own tools.

The same calls a model makes: start a design from the analyst's purpose and
questions, add the sales table (schema and a sample whose distinct values
match the table's), design the tools, review them, write the project. No
workspace is needed; the sample stands in for live inspection.

    CREATOR_ALLOW_WRITE=true CREATOR_OUTPUT_ROOT=/tmp/out \\
      PYTHONPATH=src python eval/rebuild_bakehouse.py

Prints the tool list, the review verdict and the seconds each step took.
"""

from __future__ import annotations

import asyncio
import itertools
import json
import logging
import sys
import time

from fastmcp import Client

from mcp_server_creator.app import mcp

logging.disable(logging.CRITICAL)

# Distinct values of samples.bakehouse.sales_transactions, from the live
# profile of the first build.
PRODUCTS = [
    "Austin Almond Biscotti",
    "Golden Gate Ginger",
    "Orchard Oasis",
    "Outback Oatmeal",
    "Pearly Pies",
    "Tokyo Tidbits",
]
PAYMENTS = ["amex", "mastercard", "visa"]
HEADER = (
    "transactionID,customerID,franchiseID,dateTime,product,quantity,"
    "unitPrice,totalPrice,paymentMethod,cardNumber"
)
JOBS = [
    "Which franchises had the highest total revenue between two dates?",
    "What are the top 5 best-selling products by quantity for a given franchise?",
    "How does revenue split by payment method?",
    "What was total revenue per day over a date range?",
    "How many transactions and what average ticket size did a franchise have?",
]


def sample() -> str:
    rows = [HEADER]
    combos = itertools.islice(
        itertools.cycle(itertools.product(PRODUCTS, PAYMENTS)), 36
    )
    for i, (product, payment) in enumerate(combos):
        qty = 1 + i % 7
        rows.append(
            f"{1000000 + i},{2000000 + i},{3000000 + i % 5},"
            f"2024-05-{1 + i % 28:02d} 10:{i % 60:02d}:00,{product},{qty},3,"
            f"{3 * qty},{payment},{4000000000000000 + i}"
        )
    return "\n".join(rows)


async def main() -> int:
    timings: dict[str, float] = {}

    async with Client(mcp) as client:

        async def call(name: str, args: dict) -> dict:
            t0 = time.perf_counter()
            res = await client.call_tool(name, args, raise_on_error=False)
            timings[name] = round(time.perf_counter() - t0, 3)
            body = res.structured_content or json.loads(res.content[0].text)
            if res.is_error:
                raise SystemExit(f"{name} failed: {json.dumps(body)[:400]}")
            return body

        start = await call(
            "creator_start_design",
            {
                "purpose": (
                    "Let an agent answer a bakery franchise sales analyst's "
                    "questions about point-of-sale transactions: revenue by "
                    "franchise, best-selling products, sales by payment method, "
                    "and daily sales trends."
                ),
                "primary_user": (
                    "a sales analyst at the Bakehouse franchise head office who "
                    "reviews franchise performance weekly"
                ),
                "jobs_to_be_done": JOBS,
                "out_of_scope": [
                    "Customer personal details such as names, emails or addresses",
                    "Forecasting future sales",
                    "Changing or deleting any sales record",
                ],
                "server_name": "bakehouse-sales",
                "domain": "retail point-of-sale sales",
                "classification": "internal",
                "environment": "commercial",
            },
        )
        design = start["design_id"]
        await call(
            "creator_add_data_source",
            {
                "design_id": design,
                "name": "sales",
                "kind": "uc_table",
                "modality": "structured",
                "schema_text": sample(),
                "catalog": "samples",
                "schema_name": "bakehouse",
                "table": "sales_transactions",
                "title": "Bakehouse sales transactions",
                "grain": "one point-of-sale transaction for one product line",
                "update_cadence": "static sample",
                "try_live_inspection": False,
            },
        )
        tools = await call("creator_design_tools", {"design_id": design})
        review = await call("creator_review_server", {"design_id": design})
        written = await call(
            "creator_write_project",
            {
                "destination": "local",
                "design_id": design,
                "dry_run": False,
                "subdirectory": "mcp-bakehouse-sales",
            },
        )
    for tool in tools["tools"]:
        print(f"  {tool['name']}: {tool['goal']}")
    print("review:", review["verdict"])
    print("written:", written.get("root"), written.get("file_count"), "files")
    print("seconds per step:", json.dumps(timings))
    print("total seconds:", round(sum(timings.values()), 3))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
