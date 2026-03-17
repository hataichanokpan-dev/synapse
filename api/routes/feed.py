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

from api.deps import get_synapse_service, get_event_bus
from api.models import (
    FeedEvent,
    FeedEventListResponse,
)

router = APIRouter(tags=["Feed"])


@router.get("/", response_model=FeedEventListResponse)
async def get_feed(
    layer: str = Query(None, description="Filter by memory layer"),
    limit: int = Query(50, ge=1, le=200),
    since: datetime = Query(None, description="Get events after this timestamp"),
    service=Depends(get_synapse_service),
):
    """Get recent feed events."""
    # GAP - needs event log system
    result = await service.get_feed_events(
        layer=layer,
        limit=limit,
        since=since,
    )

    events = result.get("events", [])

    return FeedEventListResponse(
        events=[
            FeedEvent(
                id=e.get("id", str(i)),
                type=e.get("type", "memory_added"),
                layer=e.get("layer"),
                summary=e.get("summary", ""),
                detail=e.get("detail"),
                timestamp=e.get("timestamp", datetime.utcnow()),
            )
            for i, e in enumerate(events)
        ],
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
            yield f"data: {{\"type\": \"connected\", \"timestamp\": \"{datetime.utcnow().isoformat()}\"}}\n\n"

            while True:
                try:
                    # Wait for event with timeout for heartbeat
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {event.json()}\n\n"
                except asyncio.TimeoutError:
                    # Send heartbeat
                    yield f"data: {{\"type\": \"heartbeat\", \"timestamp\": \"{datetime.utcnow().isoformat()}\"}}\n\n"
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
