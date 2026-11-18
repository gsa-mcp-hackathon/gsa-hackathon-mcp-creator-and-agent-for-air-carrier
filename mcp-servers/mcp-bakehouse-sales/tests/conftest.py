"""Test-time compatibility across FastMCP versions.

FastMCP 3 and later expose `list_tools()` and `list_prompts()`, which return
lists. FastMCP 2.x exposes `get_tools()` and `get_prompts()`, which return
dicts keyed by name. The tests use the newer names, so this adds them when
the installed FastMCP is 2.x. Nothing outside the tests depends on it.
"""

from fastmcp import FastMCP

if not hasattr(FastMCP, "list_tools"):

    async def _list_tools(self):
        return list((await self.get_tools()).values())

    FastMCP.list_tools = _list_tools

if not hasattr(FastMCP, "list_prompts"):

    async def _list_prompts(self):
        return list((await self.get_prompts()).values())

    FastMCP.list_prompts = _list_prompts
