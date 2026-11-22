"""One error contract for every tool: a failure is reported as an error.

Tools here answer a failure with a JSON body that says what went wrong and
what to do next, for example {"error": "No record matched 'X'.", "hint": ...}
or {"status": "failed", "error": ...}. Returned as an ordinary result, a
client, a grader or a probe counts that as a success. This middleware keeps
the body unchanged and sets isError on the MCP result, so the caller sees an
error and still reads the reason and the hint.

A result is an error when its structured content is a dict with a non-empty
top-level "error". A nested "error" (one row's status, an optional check that
did not run) does not count.

This file is copied byte for byte into every FastMCP server built by MCP A
Creator, and mcp-servers/test_error_contract.py checks that the copies match.
"""

from __future__ import annotations

from typing import Any


def is_error_body(body: Any) -> bool:
    """True when a tool's structured result reports a failure."""
    return isinstance(body, dict) and bool(body.get("error"))


try:
    from fastmcp.server.middleware import Middleware
except ImportError:  # a server built on the plain MCP SDK raises ToolError instead
    Middleware = None

if Middleware is not None:

    class ErrorContractMiddleware(Middleware):
        """Mark a result whose body reports an error as isError, body intact."""

        async def on_call_tool(self, context, call_next):
            result = await call_next(context)
            if is_error_body(getattr(result, "structured_content", None)):
                result.is_error = True
            return result
