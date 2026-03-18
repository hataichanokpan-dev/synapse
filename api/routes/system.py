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
    MaintenanceRequest,
    MaintenanceResponse,
    MaintenanceResult,
    MaintenanceAction,
)

router = APIRouter(tags=["System"])


@router.get("/status", response_model=StatusResponse)
async def get_status(service=Depends(get_synapse_service)):
    """Get system status."""
    result = await service.get_status()

    # Parse component health
    components = []
    if "components" in result:
        for name, status in result["components"].items():
            components.append(ComponentHealth(
                name=name,
                status=ServiceStatus.HEALTHY if status == "ok" else ServiceStatus.UNHEALTHY,
                message=status,
            ))
    else:
        components.append(ComponentHealth(
            name="synapse",
            status=ServiceStatus.HEALTHY if result.get("status") == "ok" else ServiceStatus.DEGRADED,
            message=result.get("message", ""),
        ))

    return StatusResponse(
        status=ServiceStatus.HEALTHY if result.get("status") == "ok" else ServiceStatus.DEGRADED,
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

    storage_data = result.get("storage", {})

    return StatsResponse(
        memory=MemoryStats(
            entities=result.get("entities", 0),
            edges=result.get("edges", 0),
            episodes=result.get("episodes", 0),
            procedures=result.get("procedures", 0),
            episodic_items=result.get("episodic_items", 0),
            working_keys=result.get("working_keys", 0),
        ),
        storage=StorageStats(
            falkordb_mb=storage_data.get("falkordb_mb", 0.0),
            qdrant_mb=storage_data.get("qdrant_mb", 0.0),
            sqlite_mb=storage_data.get("sqlite_mb", 0.0),
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
            message=result.get("message", ""),
        ))

    return MaintenanceResponse(
        results=results,
        dry_run=request.dry_run,
    )
