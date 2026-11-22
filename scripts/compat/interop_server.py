"""A minimal FastMCP server for the protocol interop check (scripts/check_compat.sh).

Runs under the FastMCP version being tested, on 127.0.0.1:8765, stateless HTTP.
"""
from fastmcp import FastMCP

mcp = FastMCP("interop")


@mcp.tool
def ping(x: int) -> dict:
    """Return the number it was given."""
    return {"x": x}


if __name__ == "__main__":
    mcp.run(transport="http", host="127.0.0.1", port=8765, stateless_http=True)
