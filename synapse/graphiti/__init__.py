"""
Synapse Graphiti Module

This is a vendored copy of Graphiti (https://github.com/getzep/graphiti) -
an open-source temporal context graph engine.

Vendored from: graphiti-core v0.28.2
License: MIT

NOTE: Currently, the MCP server still imports from 'graphiti_core' package.
This vendored copy is kept for future customization and integration with
Synapse's Five-Layer Memory Model.
"""

# Lazy import to avoid requiring graphiti_core for basic operations
# Only import when actually needed
Graphiti = None

def get_graphiti():
    """Get Graphiti class (lazy import)."""
    global Graphiti
    if Graphiti is None:
        try:
            from .graphiti import Graphiti as _Graphiti
            Graphiti = _Graphiti
        except ImportError:
            pass
    return Graphiti

__all__ = ['Graphiti', 'get_graphiti']
