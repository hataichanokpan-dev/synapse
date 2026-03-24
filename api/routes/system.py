"""
System routes for Synapse API.

Endpoints:
    GET    /api/system/status       - Health check
    GET    /api/system/stats        - System statistics
    POST   /api/system/maintenance  - Run maintenance tasks
    DELETE /api/system/graph        - Clear graph (dangerous)
"""

from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_synapse_service
from api.models import (
    StatusResponse,
    SuccessResponse,
    ServiceStatus,
    ComponentHealth,
    ClearGraphRequest,
    ClearGraphResponse,
    StatsResponse,
    StorageStats,
    MemoryStats,
    SearchStats,
    MaintenanceRequest,
    MaintenanceResponse,
    MaintenanceResult,
    MaintenanceAction,
)

router = APIRouter(tags=["System"])


def _map_component_status(status: str) -> ServiceStatus:
    """Map raw component health strings into API status values."""
    normalized = str(status).strip().lower()
    if normalized in {"ok", "healthy"}:
        return ServiceStatus.HEALTHY
    if normalized in {"degraded", "unknown"} or "not initialized" in normalized or "degraded" in normalized:
        return ServiceStatus.DEGRADED
    if normalized in {"unhealthy"} or normalized.startswith("error"):
        return ServiceStatus.UNHEALTHY
    return ServiceStatus.DEGRADED


def _map_overall_status(status: str) -> ServiceStatus:
    normalized = str(status).strip().lower()
    if normalized in {"ok", "healthy"}:
        return ServiceStatus.HEALTHY
    if normalized == "degraded":
        return ServiceStatus.DEGRADED
    if normalized == "unhealthy":
        return ServiceStatus.UNHEALTHY
    return ServiceStatus.UNKNOWN


@router.get("/status", response_model=StatusResponse)
async def get_status(service=Depends(get_synapse_service)):
    """Get system status."""
    result = await service.get_status()

    # Parse component health
    components = []
    if "components" in result:
        raw_components = result["components"]
        if isinstance(raw_components, dict):
            for name, raw in raw_components.items():
                if isinstance(raw, dict):
                    components.append(ComponentHealth(
                        name=name,
                        status=_map_component_status(raw.get("status", raw.get("message", "unknown"))),
                        message=raw.get("message"),
                        details=raw.get("details", {}) or {},
                        latency_ms=raw.get("latency_ms"),
                    ))
                else:
                    components.append(ComponentHealth(
                        name=name,
                        status=_map_component_status(raw),
                        message=str(raw),
                    ))
    else:
        components.append(ComponentHealth(
            name="synapse",
            status=_map_overall_status(result.get("status", "unknown")),
            message=result.get("message", ""),
        ))

    return StatusResponse(
        status=_map_overall_status(result.get("status", "unknown")),
        message=result.get("message", ""),
        components=components,
    )


@router.delete("/graph", response_model=ClearGraphResponse)
async def clear_graph(
    request: ClearGraphRequest,
    service=Depends(get_synapse_service),
):
    """Clear the knowledge graph (dangerous)."""
    if not request.confirm:
        raise HTTPException(
            status_code=400,
            detail="confirm=true required for this destructive operation",
        )

    result = await service.clear_graph(
        confirm=True,
        group_ids=request.group_ids,
    )
    if result.get("available") is False:
        raise HTTPException(status_code=503, detail=result.get("message", "Graph driver unavailable"))

    return ClearGraphResponse(
        status="ok",
        message=result.get("message", "Graph cleared"),
        groups_cleared=request.group_ids or ["all"],
        nodes_deleted=result.get("nodes_deleted", 0),
        edges_deleted=result.get("edges_deleted", 0),
    )


@router.get("/stats", response_model=StatsResponse)
async def get_stats(service=Depends(get_synapse_service)):
    """Get system statistics."""
    result = await service.get_system_stats()

    memory_data = result.get("memory", {})
    storage_data = result.get("storage", {})
    search_data = result.get("search", {})
    semantic_projection = search_data.get("semantic_projection", result.get("semantic_projection", {}))

    return StatsResponse(
        memory=MemoryStats(
            entities=memory_data.get("entities", result.get("entities", 0)),
            edges=memory_data.get("edges", result.get("edges", 0)),
            episodes=memory_data.get("episodes", result.get("episodes", 0)),
            procedures=memory_data.get("procedures", result.get("procedures", 0)),
            episodic_items=memory_data.get("episodic_items", result.get("episodic_items", 0)),
            working_keys=memory_data.get("working_keys", result.get("working_keys", 0)),
            user_models=memory_data.get("user_models", 0),
        ),
        storage=StorageStats(
            falkordb_mb=storage_data.get("falkordb_mb", 0.0),
            qdrant_mb=storage_data.get("qdrant_mb", 0.0),
            sqlite_mb=storage_data.get("sqlite_mb", 0.0),
        ),
        search=SearchStats(
            counts=search_data.get("counts", {}),
            latency_ms=search_data.get("latency_ms", {}),
            semantic_projection=semantic_projection,
        ),
    )


@router.post("/maintenance", response_model=MaintenanceResponse)
async def run_maintenance(
    request: MaintenanceRequest,
    service=Depends(get_synapse_service),
):
    """Run maintenance tasks."""
    if not request.actions:
        raise HTTPException(
            status_code=400,
            detail="At least one action required",
        )

    results = []
    for action in request.actions:
        result = await service.run_maintenance(action=action.value, dry_run=request.dry_run)
        results.append(MaintenanceResult(
            action=action,
            affected=result.get("affected", 0),
            duration_ms=result.get("duration_ms", 0.0),
            success=result.get("success", True),
            message=result.get("message", ""),
        ))

    return MaintenanceResponse(
        results=results,
        total_duration_ms=sum(result.duration_ms for result in results),
        dry_run=request.dry_run,
    )
