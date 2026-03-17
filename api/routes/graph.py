"""
Graph routes for Synapse API.

Endpoints:
    GET    /api/graph/nodes           - List/search nodes
    GET    /api/graph/nodes/:id       - Get node by ID
    GET    /api/graph/nodes/:id/edges - Get node edges
    GET    /api/graph/edges           - List edges
    GET    /api/graph/edges/:id       - Get edge by ID
    DELETE /api/graph/nodes/:id       - Delete node
    DELETE /api/graph/edges/:id       - Delete edge
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException

from api.deps import get_synapse_service
from api.models import (
    NodeResponse,
    NodeListResponse,
    NodeDetailResponse,
    EdgeResponse,
    EdgeListResponse,
    EdgeDetailResponse,
    SuccessResponse,
)

router = APIRouter(tags=["Graph"])


@router.get("/nodes", response_model=NodeListResponse)
async def list_nodes(
    query: str = Query(None, description="Search query for nodes"),
    type: str = Query(None, description="Filter by node type"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    service=Depends(get_synapse_service),
):
    """List or search graph nodes."""
    if query:
        # Use search if query provided
        result = await service.search_nodes(query=query, limit=limit)
        nodes = result.get("nodes", [])
    else:
        # List all nodes (GAP - needs direct DB access)
        nodes = []

    return NodeListResponse(
        nodes=[
            NodeResponse(
                uuid=n.get("uuid", str(i)),
                name=n.get("name", ""),
                type=n.get("type", "Entity"),
                summary=n.get("summary"),
                created_at=n.get("created_at"),
            )
            for i, n in enumerate(nodes)
        ],
        total=len(nodes),
        limit=limit,
        offset=offset,
    )


@router.get("/nodes/{node_id}", response_model=NodeDetailResponse)
async def get_node(
    node_id: str,
    service=Depends(get_synapse_service),
):
    """Get node details by ID."""
    # GAP - needs direct FalkorDB access
    result = await service.get_node_by_id(node_id=node_id)

    if not result:
        raise HTTPException(status_code=404, detail=f"Node {node_id} not found")

    return NodeDetailResponse(
        uuid=result.get("uuid", node_id),
        name=result.get("name", ""),
        type=result.get("type", "Entity"),
        summary=result.get("summary"),
        facts=result.get("facts", []),
        episodes=result.get("episodes", []),
        created_at=result.get("created_at"),
        updated_at=result.get("updated_at"),
    )


@router.get("/nodes/{node_id}/edges", response_model=EdgeListResponse)
async def get_node_edges(
    node_id: str,
    direction: str = Query("both", regex="^(in|out|both)$"),
    type: str = Query(None, description="Filter by edge type"),
    limit: int = Query(50, ge=1, le=200),
    service=Depends(get_synapse_service),
):
    """Get edges connected to a node."""
    # GAP - needs direct FalkorDB access
    result = await service.get_node_edges(
        node_id=node_id,
        direction=direction,
        edge_type=type,
        limit=limit,
    )

    edges = result.get("edges", [])

    return EdgeListResponse(
        edges=[
            EdgeResponse(
                uuid=e.get("uuid", str(i)),
                source_id=e.get("source_id", ""),
                target_id=e.get("target_id", ""),
                type=e.get("type", "RELATES_TO"),
                fact=e.get("fact"),
                created_at=e.get("created_at"),
            )
            for i, e in enumerate(edges)
        ],
        total=len(edges),
        limit=limit,
        offset=0,
    )


@router.get("/edges", response_model=EdgeListResponse)
async def list_edges(
    type: str = Query(None, description="Filter by edge type"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    service=Depends(get_synapse_service),
):
    """List graph edges."""
    # GAP - needs direct FalkorDB access
    result = await service.list_edges(edge_type=type, limit=limit, offset=offset)

    edges = result.get("edges", [])

    return EdgeListResponse(
        edges=[
            EdgeResponse(
                uuid=e.get("uuid", str(i)),
                source_id=e.get("source_id", ""),
                target_id=e.get("target_id", ""),
                type=e.get("type", "RELATES_TO"),
                fact=e.get("fact"),
                created_at=e.get("created_at"),
            )
            for i, e in enumerate(edges)
        ],
        total=result.get("total", len(edges)),
        limit=limit,
        offset=offset,
    )


@router.get("/edges/{edge_id}", response_model=EdgeDetailResponse)
async def get_edge(
    edge_id: str,
    service=Depends(get_synapse_service),
):
    """Get edge details by ID."""
    # Use existing MCP method
    result = await service.get_entity_edge(edge_id=edge_id)

    if not result:
        raise HTTPException(status_code=404, detail=f"Edge {edge_id} not found")

    return EdgeDetailResponse(
        uuid=result.get("uuid", edge_id),
        source_id=result.get("source_id", ""),
        target_id=result.get("target_id", ""),
        source_name=result.get("source_name", ""),
        target_name=result.get("target_name", ""),
        type=result.get("type", "RELATES_TO"),
        fact=result.get("fact"),
        episodes=result.get("episodes", []),
        created_at=result.get("created_at"),
    )


@router.delete("/nodes/{node_id}", response_model=SuccessResponse)
async def delete_node(
    node_id: str,
    service=Depends(get_synapse_service),
):
    """Delete a node and its edges."""
    # GAP - needs direct FalkorDB + Qdrant access
    result = await service.delete_node(node_id=node_id)

    return SuccessResponse(
        status="ok",
        message=result.get("message", f"Node {node_id} deleted"),
    )


@router.delete("/edges/{edge_id}", response_model=SuccessResponse)
async def delete_edge(
    edge_id: str,
    service=Depends(get_synapse_service),
):
    """Delete an edge."""
    # Use existing MCP method
    result = await service.delete_entity_edge(edge_id=edge_id)

    return SuccessResponse(
        status="ok",
        message=result.get("message", f"Edge {edge_id} deleted"),
    )
