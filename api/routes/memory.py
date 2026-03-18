"""
Memory routes for Synapse API.

Endpoints:
    GET    /api/memory              - List memories
    GET    /api/memory/:id          - Get memory by ID
    POST   /api/memory              - Add memory
    PUT    /api/memory/:id          - Update memory
    DELETE /api/memory/:id          - Delete memory
    POST   /api/memory/search       - Search memories
    POST   /api/memory/consolidate  - Consolidate memories
"""

from fastapi import APIRouter, Depends, Query, HTTPException

from api.deps import get_synapse_service, get_event_bus
from api.services.event_bus import FeedEventType
from api.models import (
    MemoryCreate,
    MemoryUpdate,
    MemoryResponse,
    MemoryListResponse,
    MemorySearchRequest,
    MemorySearchResponse,
    MemorySearchResult,
    ConsolidateRequest,
    ConsolidateResponse,
    SuccessResponse,
    MemoryLayer,
)

router = APIRouter(tags=["Memory"])


@router.get("/", response_model=MemoryListResponse)
async def list_memories(
    layer: str = Query(None, description="Filter by layer"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    sort: str = Query("created_at", regex="^(created_at|name|access_count)$"),
    order: str = Query("desc", regex="^(asc|desc)$"),
    service=Depends(get_synapse_service),
):
    """List memories with pagination."""
    result = await service.list_memories(
        layer=layer,
        limit=limit,
        offset=offset,
        sort=sort,
        order=order,
    )

    items = [
        MemoryResponse(
            uuid=m.get("uuid", str(i)),
            layer=MemoryLayer(m.get("layer", "EPISODIC")),
            name=m.get("name", ""),
            content=m.get("content", ""),
            source=m.get("source", "api"),
            source_description=m.get("source_description"),
            group_id=m.get("group_id"),
            agent_id=m.get("agent_id"),
            metadata=m.get("metadata", {}),
        )
        for i, m in enumerate(result.get("items", []))
    ]

    return MemoryListResponse(
        items=items,
        total=result.get("total", len(items)),
        limit=limit,
        offset=offset,
    )


@router.get("/{memory_id}", response_model=MemoryResponse)
async def get_memory(
    memory_id: str,
    service=Depends(get_synapse_service),
):
    """Get memory by ID."""
    result = await service.get_memory_by_id(memory_id=memory_id)

    if not result:
        raise HTTPException(status_code=404, detail=f"Memory {memory_id} not found")

    return MemoryResponse(
        uuid=memory_id,
        layer=MemoryLayer(result.get("layer", "EPISODIC")),
        name=result.get("name", ""),
        content=result.get("content", ""),
        source=result.get("source", "api"),
        source_description=result.get("source_description"),
        group_id=result.get("group_id"),
        agent_id=result.get("agent_id"),
        access_count=result.get("access_count", 0),
        metadata=result.get("metadata", {}),
        created_at=result.get("created_at"),
        updated_at=result.get("updated_at"),
        last_accessed=result.get("last_accessed"),
    )


@router.post("/", response_model=MemoryResponse)
async def add_memory(
    request: MemoryCreate,
    service=Depends(get_synapse_service),
    event_bus=Depends(get_event_bus),
):
    """Add a new memory."""
    result = await service.add_memory(
        name=request.name,
        episode_body=request.content,
        source=request.source,
        source_description=request.source_description or "",
        group_id=request.group_id,
    )

    # Emit feed event
    if event_bus:
        await event_bus.emit(
            event_type=FeedEventType.MEMORY_ADD,
            summary=f"Added memory: {request.name}",
            layer=result.get("layer", "EPISODIC"),
            detail={
                "name": request.name,
                "source": request.source,
                "layer": result.get("layer"),
            },
        )

    # Determine the layer from classification result
    detected_layer = result.get("layer", "EPISODIC")
    try:
        layer_enum = MemoryLayer(detected_layer)
    except ValueError:
        layer_enum = request.layer or MemoryLayer.EPISODIC

    return MemoryResponse(
        uuid=result.get("uuid", ""),
        layer=layer_enum,
        name=request.name,
        content=request.content,
        source=request.source,
        source_description=request.source_description,
        group_id=request.group_id,
        agent_id=request.agent_id,
        metadata=request.metadata or {},
    )


@router.post("/search", response_model=MemorySearchResponse)
async def search_memories(
    request: MemorySearchRequest,
    service=Depends(get_synapse_service),
):
    """Search memories across layers."""
    layers = [l.value for l in request.layers] if request.layers else None

    result = await service.search_memory(
        query=request.query,
        layers=layers,
        limit=request.limit,
    )

    # Flatten layer results into a single list
    results = []
    for layer_name, layer_items in result.get("layers", {}).items():
        for item in (layer_items if isinstance(layer_items, list) else []):
            # Items may be dicts or model objects - handle both
            if isinstance(item, dict):
                uid = item.get("uuid", item.get("id", ""))
                name = item.get("name", item.get("trigger", ""))
                content = item.get("content", item.get("episode_body", ""))
                score = item.get("score", 1.0)
                highlight = item.get("highlight")
                metadata = item.get("metadata", {})
            else:
                uid = str(getattr(item, 'uuid', getattr(item, 'id', '')))
                name = getattr(item, 'name', getattr(item, 'trigger', ''))
                content = getattr(item, 'content', getattr(item, 'episode_body', ''))
                if hasattr(item, 'procedure') and not content:
                    content = str(item.procedure)
                score = getattr(item, 'score', 1.0)
                highlight = None
                metadata = {}

            try:
                layer_enum = MemoryLayer(layer_name.upper())
            except ValueError:
                layer_enum = MemoryLayer.EPISODIC

            results.append(MemorySearchResult(
                uuid=str(uid),
                layer=layer_enum,
                name=str(name),
                content=str(content) if content else "",
                score=float(score) if score else 1.0,
                highlight=highlight,
                metadata=metadata if isinstance(metadata, dict) else {},
            ))

    # Add Graphiti (semantic graph) results
    for item in result.get("graphiti", []):
        fact = getattr(item, 'fact', None) or getattr(item, 'name', str(item))
        results.append(MemorySearchResult(
            uuid=getattr(item, 'uuid', ""),
            layer=MemoryLayer.SEMANTIC,
            name=getattr(item, 'name', fact[:50] if isinstance(fact, str) else ""),
            content=fact if isinstance(fact, str) else str(fact),
            score=getattr(item, 'score', 1.0),
            metadata={},
        ))

    return MemorySearchResponse(
        results=results,
        total=len(results),
        query=request.query,
        layers_searched=layers or ["all"],
    )


@router.post("/consolidate", response_model=ConsolidateResponse)
async def consolidate_memories(
    request: ConsolidateRequest,
    service=Depends(get_synapse_service),
):
    """Consolidate memories."""
    criteria = {}
    if request.topics:
        criteria["topics"] = request.topics
    result = await service.consolidate(
        source=request.source or "episodic",
        criteria=criteria or None,
        min_access_count=request.min_access_count,
        dry_run=request.dry_run,
    )

    return ConsolidateResponse(
        promoted=result.get("promoted", []),
        skipped=result.get("skipped", []),
        errors=result.get("errors", []),
        dry_run=request.dry_run,
    )


@router.put("/{memory_id}", response_model=MemoryResponse)
async def update_memory(
    memory_id: str,
    request: MemoryUpdate,
    service=Depends(get_synapse_service),
):
    """Update a memory."""
    result = await service.update_memory(
        memory_id=memory_id,
        content=request.content,
        metadata=request.metadata,
    )

    if not result:
        raise HTTPException(status_code=404, detail=f"Memory {memory_id} not found")

    return MemoryResponse(
        uuid=memory_id,
        layer=MemoryLayer(result.get("layer", "EPISODIC")),
        name=result.get("name", ""),
        content=result.get("content", request.content or ""),
        source=result.get("source", "api"),
        source_description=result.get("source_description"),
        group_id=result.get("group_id"),
        agent_id=result.get("agent_id"),
        metadata=result.get("metadata", request.metadata or {}),
    )


@router.delete("/{memory_id}", response_model=SuccessResponse)
async def delete_memory(
    memory_id: str,
    service=Depends(get_synapse_service),
    event_bus=Depends(get_event_bus),
):
    """Delete a memory."""
    result = await service.delete_memory(memory_id=memory_id)

    # Emit feed event
    if event_bus:
        await event_bus.emit(
            event_type=FeedEventType.MEMORY_DELETE,
            summary=f"Deleted memory: {memory_id}",
            detail={"uuid": memory_id},
        )

    return SuccessResponse(
        status="ok",
        message=result.get("message", f"Memory {memory_id} deleted"),
    )
