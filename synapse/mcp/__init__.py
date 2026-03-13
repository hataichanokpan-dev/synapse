"""MCP Server Module"""

from synapse.mcp.server import create_server
from synapse.mcp.tools import register_tools

__all__ = [
    "create_server",
    "register_tools",
]
