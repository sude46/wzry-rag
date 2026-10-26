"""MCP server entrypoint.

Local (Claude Desktop / Cursor):
    MCP_TRANSPORT=stdio uv run python -m mcp_server.server

Remote:
    MCP_TRANSPORT=sse uv run python -m mcp_server.server
"""
from __future__ import annotations

import sys

sys.path.insert(0, ".")

from mcp.server.fastmcp import FastMCP

from config import get_settings
from mcp_server.tools import get_hero, get_item, search_knowledge

settings = get_settings()
mcp = FastMCP("wzry-rag", host=settings.mcp_host, port=settings.mcp_port)

mcp.tool()(search_knowledge)
mcp.tool()(get_hero)
mcp.tool()(get_item)


if __name__ == "__main__":
    mcp.run(transport=settings.mcp_transport)
