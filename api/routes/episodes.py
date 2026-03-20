"""
Episodes routes for Synapse API.

Endpoints:
    GET    /api/episodes         - List episodes
    GET    /api/episodes/:id     - Get episode by ID
    DELETE /api/episodes/:id     - Delete episode
"""

from fastapi import APIRouter, Depends, Query, HTTPException

from api.deps import get_synapse_service
from api.models import (
    EpisodeResponse,
    EpisodeListResponse,
    EpisodeDetailResponse,
    SuccessResponse,
)

router = APIRouter(tags=["Episodes"])


@router.get("/", response_model=EpisodeListResponse)
async def list_episodes(
    group_id: str = Query(None, description="Filter by group ID"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    sort: str = Query("created_at", pattern="^(created_at|name)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    service=Depends(get_synapse_service),
):
    """List episodes from both local storage and knowledge graph."""
    result = await service.get_episodes(
        group_id=group_id,
        limit=limit,
        offset=offset,
        sort=sort,
        order=order,
    )

    episodes = result.get("episodes", [])

    return EpisodeListResponse(
        episodes=[
            EpisodeResponse(
                uuid=e.get("uuid", ""),
                name=e.get("name", ""),
                content=e.get("content", ""),
                source=e.get("source", "unknown"),
                source_id=e.get("source_id"),
                source_description=e.get("source_description"),
                group_id=e.get("group_id", group_id),
                created_at=e.get("created_at"),
                entity_count=e.get("entity_count"),
                edge_count=e.get("edge_count"),
            )
            for e in episodes
        ],
        total=result.get("total", len(episodes)),
        limit=limit,
        offset=offset,
    )


@router.get("/{episode_id}", response_model=EpisodeDetailResponse)
async def get_episode(
    episode_id: str,
    service=Depends(get_synapse_service),
):
    """Get episode details by ID."""
    result = await service.get_episode_by_id(episode_id=episode_id)

    if not result:
        raise HTTPException(status_code=404, detail=f"Episode {episode_id} not found")

    return EpisodeDetailResponse(
        uuid=result.get("uuid", episode_id),
        name=result.get("name", ""),
        content=result.get("content", ""),
        source=result.get("source", "unknown"),
        source_id=result.get("source_id"),
        source_description=result.get("source_description"),
        group_id=result.get("group_id"),
        entities=result.get("entities", []),
        facts=result.get("facts", []),
        created_at=result.get("created_at"),
        updated_at=result.get("updated_at"),
        entity_count=len(result.get("entities", [])),
        edge_count=len(result.get("facts", [])),
    )


@router.delete("/{episode_id}", response_model=SuccessResponse)
async def delete_episode(
    episode_id: str,
    service=Depends(get_synapse_service),
):
    """Delete an episode."""
    result = await service.delete_episode(episode_id=episode_id)

    return SuccessResponse(
        status="ok",
        message=result.get("message", f"Episode {episode_id} deleted"),
    )
