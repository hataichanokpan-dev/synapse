"""
Synapse REST API Gateway

FastAPI-based REST API that provides a clean HTTP interface for the Synapse
memory system. This gateway directly imports SynapseService for zero-latency
access to the memory layers.

Architecture:
    Browser → FastAPI (:8000) → SynapseService → FalkorDB / Qdrant / SQLite

Reference: docs/plans/backend_api_plan.md
"""

__version__ = "1.0.0"
