"""A dependency-light evaluation runner.

The Phoenix harness in `phoenix/` is the richer tool: traces, judges, a UI.
It also needs LangChain, Phoenix, OpenTelemetry and their transitive tree,
which an environment behind an internal package mirror may not be able to
install, and which moves fast enough to break.

This runner needs only what the server already depends on plus httpx, which
arrives with fastmcp. It launches the server over stdio, drives it with an
OpenAI-compatible chat endpoint, and scores answers by exact and numeric
match. Use it as the floor: if this cannot run, nothing can.

    uv run python eval/simple_eval.py --limit 5
    uv run python eval/simple_eval.py --no-tools      # the baseline
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import httpx
from fastmcp import Client

REPO_ROOT = Path(__file__).resolve().parents[1]
DATASET_DIR = REPO_ROOT / "eval/phoenix/datasets/bakehouse-eval-0"
DATASET = DATASET_DIR / "examples/bakehouse-eval-0.csv"
MAX_TURNS = 8
NUMBER = re.compile(r"-?[\d,]*\.?\d+")


def load_cases(limit: int) -> list[dict[str, str]]:
    """Read the golden question set."""
    if not DATASET.is_file():
        raise SystemExit(f"dataset not found: {DATASET}")
    with DATASET.open(encoding="utf-8", newline="") as handle:
        rows = [dict(row) for row in csv.DictReader(handle)]
    return rows[:limit] if limit else rows


def mcp_tools_to_openai(tools: list[Any]) -> list[dict[str, Any]]:
    """Convert MCP tool definitions to OpenAI tool specifications."""
    converted = []
    for tool in tools:
        schema = (
            getattr(tool, "parameters", None)
            or getattr(tool, "inputSchema", None)
            or {"type": "object", "properties": {}}
        )
        converted.append(
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": (tool.description or "")[:1024],
                    "parameters": schema,
                },
            }
        )
    return converted


async def chat(
    client: httpx.AsyncClient,
    model: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
) -> dict[str, Any]:
    """One chat completion call against an OpenAI-compatible endpoint."""
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": 0,
    }
    if tools:
        payload["tools"] = tools
    response = await client.post("/chat/completions", json=payload)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]


def scores(answer: str, expected: str) -> dict[str, bool]:
    """Exact-ish and numeric comparison. No model needed."""
    answer_text = (answer or "").strip().lower()
    expected_text = (expected or "").strip().lower()
    if not expected_text or expected_text.startswith("todo"):
        return {"scored": False, "correct": False}
    contains = expected_text in answer_text
    numbers_expected = [n.replace(",", "") for n in NUMBER.findall(expected_text)]
    numbers_answer = [n.replace(",", "") for n in NUMBER.findall(answer_text)]
    numeric = bool(numbers_expected) and all(
        value in numbers_answer for value in numbers_expected
    )
    return {"scored": True, "correct": contains or numeric}


async def run_case(
    question: str,
    tools: list[dict[str, Any]],
    mcp_client: Any,
    http_client: httpx.AsyncClient,
    model: str,
    system_prompt: str,
) -> tuple[str, int]:
    """Answer one question, returning the answer and the tool calls used."""
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question},
    ]
    calls = 0
    for _ in range(MAX_TURNS):
        message = await chat(http_client, model, messages, tools)
        messages.append(message)
        tool_calls = message.get("tool_calls") or []
        if not tool_calls:
            return message.get("content") or "", calls
        for call in tool_calls:
            calls += 1
            name = call["function"]["name"]
            try:
                arguments = json.loads(call["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                arguments = {}
            try:
                result = await mcp_client.call_tool(name, arguments)
                body = "\n".join(getattr(block, "text", "") for block in result.content)
            except Exception as error:
                body = f"tool error: {error}"
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.get("id", name),
                    "content": body[:8000],
                }
            )
    return "(no answer within the turn limit)", calls


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument(
        "--no-tools",
        action="store_true",
        help="The baseline: same questions, no server attached.",
    )
    parser.add_argument(
        "--model", default=os.getenv("AGENT_MODEL", "databricks-claude-sonnet-4-5")
    )
    args = parser.parse_args()

    base_url = os.getenv("MODEL_BASE_URL", "").rstrip("/")
    api_key = os.getenv("MODEL_API_KEY", "")
    if not base_url or not api_key:
        print(
            "Set MODEL_BASE_URL and MODEL_API_KEY in eval/.env.\n"
            "For Databricks: https://<workspace-host>/serving-endpoints and "
            "a workspace token. The model name is a serving endpoint name."
        )
        return 2

    cases = load_cases(args.limit)
    prompt_path = REPO_ROOT / "eval/phoenix/prompts/system_prompt_v1.txt"
    system_prompt = (
        prompt_path.read_text(encoding="utf-8")
        if prompt_path.is_file()
        else "Answer using only the tools provided."
    )

    results: list[dict[str, Any]] = []
    async with httpx.AsyncClient(
        base_url=base_url,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=120.0,
    ) as http_client:
        if args.no_tools:
            for case in cases:
                answer, calls = await run_case(
                    case["query"], [], None, http_client, args.model, system_prompt
                )
                results.append({**case, "answer": answer, "tool_calls": calls})
        else:
            async with Client(REPO_ROOT / "src/bakehouse_sales/app.py") as mcp_client:
                tools = mcp_tools_to_openai(await mcp_client.list_tools())
                print(f"attached {len(tools)} tools")
                for case in cases:
                    answer, calls = await run_case(
                        case["query"],
                        tools,
                        mcp_client,
                        http_client,
                        args.model,
                        system_prompt,
                    )
                    results.append({**case, "answer": answer, "tool_calls": calls})

    scored = graded = 0
    print(f"\n{'id':6} {'kind':14} {'calls':>5}  result")
    print("-" * 78)
    for row in results:
        verdict = scores(row["answer"], row.get("responses", ""))
        mark = "-"
        if verdict["scored"]:
            scored += 1
            graded += int(verdict["correct"])
            mark = "correct" if verdict["correct"] else "WRONG"
        print(
            f"{row.get('id', ''):6} {row.get('case_kind', ''):14} "
            f"{row['tool_calls']:5}  {mark}"
        )
    label = "baseline (no tools)" if args.no_tools else "with the server"
    print("-" * 78)
    if scored:
        print(f"{label}: {graded}/{scored} scored questions correct")
    else:
        print(
            f"{label}: nothing was scored. Fill the TODO answers in the "
            "dataset from eval/answer_key.py first."
        )
    out = REPO_ROOT / "eval/simple-eval-results.csv"
    with out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(results)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
