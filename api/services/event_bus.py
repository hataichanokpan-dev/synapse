"""
Event Bus for Synapse API.

Provides in-memory event publishing and SSE streaming for the feed system.
"""

import asyncio
from collections import deque
from enum import Enum
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


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


class FeedEvent(BaseModel):
    """A single feed event."""

    id: str
    type: FeedEventType
    layer: Optional[str] = None
    summary: str
    detail: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime

    class Config:
        use_enum_values = True


class EventBus:
    """
    In-process event bus with SSE support.

    Features:
    - Ring buffer for recent events (last 500)
    - Subscriber queues for SSE streaming
    - SQLite persistence (Phase 3)
    """

    def __init__(self, buffer_size: int = 500):
        self._buffer_size = buffer_size
        self._ring_buffer: deque[FeedEvent] = deque(maxlen=buffer_size)
        self._subscribers: List[asyncio.Queue] = []
        self._event_counter = 0
        self._lock = asyncio.Lock()

    async def emit(
        self,
        event_type: FeedEventType,
        summary: str,
        layer: Optional[str] = None,
        detail: Optional[Dict[str, Any]] = None,
    ) -> FeedEvent:
        """
        Emit a new event.

        - Adds to ring buffer
        - Broadcasts to all subscribers
        """
        async with self._lock:
            self._event_counter += 1
            event = FeedEvent(
                id=f"evt-{self._event_counter}",
                type=event_type,
                layer=layer,
                summary=summary,
                detail=detail or {},
                timestamp=datetime.now(timezone.utc),
            )

            # Add to ring buffer
            self._ring_buffer.append(event)

            # Broadcast to subscribers
            for queue in self._subscribers:
                try:
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    pass  # Drop if queue is full

            return event

    def subscribe(self, maxsize: int = 100) -> asyncio.Queue:
        """
        Subscribe to events.

        Returns a queue that will receive new events.
        """
        queue = asyncio.Queue(maxsize=maxsize)
        self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue):
        """Unsubscribe from events."""
        if queue in self._subscribers:
            self._subscribers.remove(queue)

    async def get_recent(
        self,
        limit: int = 50,
        layer: Optional[str] = None,
        since: Optional[datetime] = None,
    ) -> List[FeedEvent]:
        """
        Get recent events from buffer.

        Args:
            limit: Maximum events to return
            layer: Filter by layer
            since: Only events after this timestamp
        """
        def _coerce_utc(value: Optional[datetime]) -> Optional[datetime]:
            if value is None:
                return None
            return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)

        events = list(self._ring_buffer)
        since = _coerce_utc(since)

        # Filter by layer
        if layer:
            events = [e for e in events if e.layer == layer]

        # Filter by timestamp
        if since:
            events = [e for e in events if _coerce_utc(e.timestamp) and _coerce_utc(e.timestamp) > since]

        # Sort by timestamp (newest first) and limit
        events.sort(key=lambda e: _coerce_utc(e.timestamp) or datetime.now(timezone.utc), reverse=True)
        return events[:limit]

    @property
    def subscriber_count(self) -> int:
        """Number of active subscribers."""
        return len(self._subscribers)

    @property
    def buffer_count(self) -> int:
        """Number of events in buffer."""
        return len(self._ring_buffer)


# Global event bus instance
_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """Get the global event bus instance."""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus
