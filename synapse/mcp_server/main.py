#!/usr/bin/env python3
"""
Main entry point for Synapse MCP Server

This is a backwards-compatible wrapper around the original graphiti_mcp_server.py
to maintain compatibility with existing deployment scripts and documentation.

Usage:
    python main.py [args...]
    synapse-mcp  # via console script

All arguments are passed through to the original server implementation.
"""

import sys
from pathlib import Path

# Add src directory to Python path for imports
src_path = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_path))


def main():
    """
    Main entry point for Synapse MCP Server.

    This function is called by the console script entrypoint.
    """
    from graphiti_mcp_server import main as server_main

    # Pass all command line arguments to the original main function
    server_main()


# Import and run the original server
if __name__ == '__main__':
    main()
