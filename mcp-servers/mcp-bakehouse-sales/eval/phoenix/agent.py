"""The agent under test: a LangChain agent wired to this MCP server.

Launches the server over stdio exactly as a real client would, so the thing
being measured is the server's tool surface, not a mock of it.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from openinference.instrumentation.langchain import LangChainInstrumentor
from phoenix.otel import register

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parents[2]
PROMPT_DIR = Path(__file__).resolve().parent / "prompts"


class BakehouseSalesAgent:
    """Runs questions against Mcp Bakehouse Sales over stdio."""

    def __init__(
        self,
        system_prompt_version: str = "v1",
        project_name: str = "mcp-eval-0",
        phoenix_endpoint: str = "http://localhost:6006/v1/traces",
        with_tools: bool = True,
    ) -> None:
        self.system_prompt_version = system_prompt_version
        self.project_name = project_name
        self.phoenix_endpoint = phoenix_endpoint
        self.with_tools = with_tools
        self.client: MultiServerMCPClient | None = None
        self.agent = None

    def _load_system_prompt(self) -> str:
        path = PROMPT_DIR / f"system_prompt_{self.system_prompt_version}.txt"
        return path.read_text(encoding="utf-8")

    async def initialize(self) -> None:
        """Instrument once, connect to the server, build the agent."""
        tracer_provider = register(
            project_name=self.project_name, endpoint=self.phoenix_endpoint
        )
        LangChainInstrumentor().instrument(tracer_provider=tracer_provider)

        tools = []
        if self.with_tools:
            self.client = MultiServerMCPClient(
                {
                    "mcp_bakehouse_sales": {
                        "transport": "stdio",
                        "command": "uv",
                        "args": ["run", "mcp-bakehouse-sales"],
                        "cwd": str(REPO_ROOT),
                    }
                }
            )
            tools = await self.client.get_tools()

        model = ChatOpenAI(
            model=os.getenv("AGENT_MODEL", "databricks-claude-sonnet-4-5"),
            api_key=os.getenv("MODEL_API_KEY", "not-set"),
            base_url=os.getenv("MODEL_BASE_URL") or None,
            temperature=0,
        )
        self.agent = create_agent(
            model=model, tools=tools, system_prompt=self._load_system_prompt()
        )

    async def run(self, question: str) -> str:
        """Answer one question and return the final text."""
        if self.agent is None:
            await self.initialize()
        result = await self.agent.ainvoke(
            {"messages": [{"role": "user", "content": question}]}
        )
        messages = result.get("messages") or []
        if not messages:
            return ""
        return getattr(messages[-1], "content", "") or ""

    def create_experiment_task(self):
        """Return a synchronous task closure, as Phoenix experiments expect."""

        def task(example) -> str:
            return asyncio.run(self.run(example.input["query"]))

        return task


async def _smoke() -> None:
    agent = BakehouseSalesAgent()
    await agent.initialize()
    print(
        await agent.run(
            "Which franchises had the highest total revenue between two dates?"
        )
    )


if __name__ == "__main__":
    asyncio.run(_smoke())
