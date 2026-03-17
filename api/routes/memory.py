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

from api.deps import get_synapse_service
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
    # GAP - needs direct DB access
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
    # GAP - needs direct DB access
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
):
    """Add a new memory."""
    result = await service.add_memory(
        name=request.name,
        content=request.content,
        source=request.source,
        source_description=request.source_description,
        layer=request.layer.value if request.layer else None,
        group_id=request.group_id,
        agent_id=request.agent_id,
        metadata=request.metadata,
    )

    return MemoryResponse(
        uuid=result.get("uuid", "unknown"),
        layer=request.layer or MemoryLayer.EPISODIC,
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

    result = await service.search_memory_layers(
        query=request.query,
        layers=layers,
        limit=request.limit,
    )

    results = [
        MemorySearchResult(
            uuid=r.get("uuid", ""),
            layer=MemoryLayer(r.get("layer", "EPISODIC")),
            name=r.get("name", ""),
            content=r.get("content", ""),
            score=r.get("score", 1.0),
            highlight=r.get("highlight"),
            metadata=r.get("metadata", {}),
        )
        for r in result.get("results", [])
    ]

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
    result = await service.consolidate(
        source=request.source,
        min_access_count=request.min_access_count,
        topics=request.topics,
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
    # GAP - needs direct DB access
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
):
    """Delete a memory."""
    # GAP - needs direct DB access
    result = await service.delete_memory(memory_id=memory_id)

    return SuccessResponse(
        status="ok",
        message=result.get("message", f"Memory {memory_id} deleted"),
    )
