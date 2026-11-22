"""Calls interop_server.py with the MCP SDK the deployed servers pin today (1.x).

Prints the protocol version the two sides agreed on. Exits 1 if the call fails.
"""
import asyncio
import sys

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


async def main() -> int:
    async with streamablehttp_client("http://127.0.0.1:8765/mcp") as (read, write, _):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            tools = await session.list_tools()
            res = await session.call_tool("ping", {"x": 7})
    ok = res.structuredContent == {"x": 7} and not res.isError
    print(f"interop: SDK 1.x client and this server agreed on {init.protocolVersion}; "
          f"tools {[t.name for t in tools.tools]}; call {'ok' if ok else 'FAILED'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
