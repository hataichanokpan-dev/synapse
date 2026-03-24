"""
Feed routes for Synapse API.

Endpoints:
    GET /api/feed        - Get event history
    GET /api/feed/stream - SSE stream of events
"""

import asyncio
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from api.config import settings
from api.deps import get_synapse_service, get_event_bus
from api.normalization import api_layer_value, coerce_utc_datetime, utcnow
from api.models import (
    FeedEvent,
    FeedEventListResponse,
)

router = APIRouter(tags=["Feed"])

# Map internal event types to frontend action types
_TYPE_TO_ACTION = {
    "MEMORY_ADD": "ADD",
    "MEMORY_DELETE": "DELETE",
    "MEMORY_SEARCH": "ACCESS",
    "MEMORY_DECAY": "DECAY",
    "CONSOLIDATION": "CONSOLIDATE",
    "PROCEDURE_ADD": "ADD",
    "PROCEDURE_SUCCESS": "ACCESS",
    "IDENTITY_CHANGE": "ADD",
    "MAINTENANCE": "ADD",
    "SYSTEM_ERROR": "ADD",
    "GRAPH_PROJECTION_QUEUED": "ADD",
    "GRAPH_PROJECTION_COMPLETED": "ADD",
    "GRAPH_PROJECTION_FAILED": "ADD",
    "GRAPH_CIRCUIT_OPEN": "ADD",
    "GRAPH_CIRCUIT_CLOSED": "ADD",
}


def _normalize_feed_layer(layer: Optional[str]) -> Optional[str]:
    """Normalize feed layer names for the frontend."""
    if layer is None:
        return None
    if str(layer).strip().lower() == "all":
        return "ALL"
    normalized = api_layer_value(layer)
    if normalized == "USER_MODEL":
        return "USER"
    return normalized


def _normalize_event_type(event_type: object) -> str:
    """Normalize internal event types into a stable action key."""
    raw = event_type.value if hasattr(event_type, "value") else event_type
    return str(raw).strip().replace(".", "_").upper()


@router.get("/", response_model=FeedEventListResponse)
async def get_feed(
    layer: str = Query(None, description="Filter by memory layer"),
    limit: int = Query(50, ge=1, le=200),
    since: datetime = Query(None, description="Get events after this timestamp"),
    service=Depends(get_synapse_service),
    event_bus=Depends(get_event_bus),
):
    """Get recent feed events from real memory activity."""
    events = []
    existing_ids = set()
    normalized_filter = _normalize_feed_layer(layer)
    normalized_since = coerce_utc_datetime(since)

    # First: pull from EventBus ring buffer (real-time events)
    if event_bus is not None:
        try:
            bus_events = await event_bus.get_recent(
                limit=settings.feed_buffer_size,
                since=normalized_since,
            )
            for e in bus_events:
                event_type = getattr(e, "type", "MEMORY_ADD")
                normalized_type = _normalize_event_type(event_type)
                action = _TYPE_TO_ACTION.get(normalized_type, "ADD")
                eid = str(getattr(e, 'id', ''))
                event_layer = _normalize_feed_layer(getattr(e, 'layer', None))

                if normalized_filter not in (None, "ALL") and event_layer != normalized_filter:
                    continue

                events.append(FeedEvent(
                    id=eid,
                    type=normalized_type,
                    layer=event_layer,
                    action=action,
                    summary=getattr(e, 'summary', ''),
                    detail=getattr(e, 'detail', None),
                    metadata=getattr(e, 'detail', None),
                    timestamp=coerce_utc_datetime(getattr(e, "timestamp", None)) or utcnow(),
                ))
                existing_ids.add(eid)
        except Exception:
            pass

    # Second: pull from SynapseService (episodic layer + graph)
    try:
        result = await service.get_feed_events(
            layer=layer if layer and layer.upper() != "ALL" else None,
            limit=limit,
            since=normalized_since,
        )
    except Exception:
        result = {"events": []}

    for e in result.get("events", []):
        eid = e.get("id", "")
        if eid in existing_ids:
            continue

        event_type = _normalize_event_type(e.get("type", "MEMORY_ADD"))
        action = _TYPE_TO_ACTION.get(event_type, "ADD")

        detail = e.get("detail", {}) or {}
        metadata = {}
        if detail.get("topics"):
            metadata["topics"] = detail["topics"]
        if detail.get("content"):
            metadata["content"] = detail["content"]

        events.append(FeedEvent(
            id=eid,
            type=event_type,
            layer=_normalize_feed_layer(e.get("layer")),
            action=action,
            summary=e.get("summary", ""),
            title=e.get("summary", "")[:60] if e.get("summary") else None,
            source=detail.get("source"),
            detail=detail,
            metadata=metadata or None,
            timestamp=coerce_utc_datetime(e.get("timestamp")) or utcnow(),
        ))

    # Sort by timestamp descending
    events.sort(key=lambda x: coerce_utc_datetime(x.timestamp) or utcnow(), reverse=True)
    events = events[:limit]

    return FeedEventListResponse(
        events=events,
        total=len(events),
        limit=limit,
    )


@router.get("/stream")
async def feed_stream(
    event_bus=Depends(get_event_bus),
):
    """SSE stream of feed events.

    This endpoint returns a Server-Sent Events stream.
    Clients receive real-time updates when memories are added/updated/deleted.
    """
    if event_bus is None:
        # Return empty stream if event bus not available
        async def empty_stream():
            yield "data: {\"error\": \"Event bus not initialized\"}\n\n"
        return StreamingResponse(
            empty_stream(),
            media_type="text/event-stream",
        )

    queue = event_bus.subscribe()

    async def event_generator():
        try:
            # Send initial connection message
            yield f"data: {{\"type\": \"connected\", \"timestamp\": \"{utcnow().isoformat()}\"}}\n\n"

            while True:
                try:
                    # Wait for event with timeout for heartbeat
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {event.json()}\n\n"
                except asyncio.TimeoutError:
                    # Send heartbeat
                    yield f"data: {{\"type\": \"heartbeat\", \"timestamp\": \"{utcnow().isoformat()}\"}}\n\n"
        except asyncio.CancelledError:
            # Client disconnected
            pass
        finally:
            event_bus.unsubscribe(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
