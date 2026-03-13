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

from .graphiti import Graphiti

__all__ = ['Graphiti']
