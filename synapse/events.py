"""
Synapse event type definitions.

Placed at the synapse package root so that synapse.layers and synapse.services
can both import it without triggering each other's circular dependencies.

api/services/event_bus re-exports FeedEventType from here.
"""

from enum import Enum


class FeedEventType(str, Enum):
    """Types of feed events."""

    MEMORY_ADD = "memory.add"
    MEMORY_DELETE = "memory.delete"
    MEMORY_SEARCH = "memory.search"
    MEMORY_DECAY = "memory.decay"
    PROCEDURE_ADD = "procedure.add"
    PROCEDURE_SUCCESS = "procedure.success"
    IDENTITY_CHANGE = "identity.change"
    CONSOLIDATION = "consolidation"
    MAINTENANCE = "maintenance"
    SYSTEM_ERROR = "system.error"
    GRAPH_PROJECTION_QUEUED = "graph.projection.queued"
    GRAPH_PROJECTION_COMPLETED = "graph.projection.completed"
    GRAPH_PROJECTION_FAILED = "graph.projection.failed"
    GRAPH_CIRCUIT_OPEN = "graph.circuit.open"
    GRAPH_CIRCUIT_CLOSED = "graph.circuit.closed"
