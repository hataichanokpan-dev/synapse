"""
Procedures routes for Synapse API.

Endpoints:
    GET    /api/procedures           - List procedures
    GET    /api/procedures/:id       - Get procedure by ID
    POST   /api/procedures           - Add procedure
    PUT    /api/procedures/:id       - Update procedure
    DELETE /api/procedures/:id       - Delete procedure
    POST   /api/procedures/:id/success - Record successful use
"""

from fastapi import APIRouter, Depends, Query, HTTPException

from api.deps import get_synapse_service, get_event_bus
from api.services.event_bus import FeedEventType
from api.models import (
    ProcedureCreate,
    ProcedureResponse,
    ProcedureListResponse,
    ProcedureSuccessResponse,
    ProcedureUpdate,
    SuccessResponse,
)

router = APIRouter(tags=["Procedures"])


def _procedure_response_from_result(result: dict, fallback_uuid: str = "") -> ProcedureResponse:
    """Build a procedure response from persisted data."""
    return ProcedureResponse(
        uuid=result.get("uuid", fallback_uuid),
        trigger=result.get("trigger", result.get("name", "")),
        steps=result.get("steps", result.get("metadata", {}).get("steps", [])),
        topics=result.get("topics", result.get("metadata", {}).get("topics", [])),
        source=result.get("source", "api"),
        source_description=result.get("source_description"),
        success_count=result.get("success_count", result.get("access_count", 0)),
        failure_count=result.get("failure_count", 0),
        decay_score=result.get("decay_score"),
        metadata=result.get("metadata", {}) or {},
        created_at=result.get("created_at"),
        updated_at=result.get("updated_at"),
        last_used=result.get("last_used", result.get("last_accessed")),
    )


@router.get("/", response_model=ProcedureListResponse)
async def list_procedures(
    trigger: str = Query(None, description="Filter by trigger pattern"),
    topic: str = Query(None, description="Filter by topic"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    service=Depends(get_synapse_service),
):
    """List or find procedures."""
    result = await service.list_procedures(
        trigger=trigger,
        topic=topic,
        limit=limit,
        offset=offset,
    )

    items = [
        ProcedureResponse(
            uuid=p.get("uuid", str(i)),
            trigger=p.get("trigger", ""),
            steps=p.get("steps", []),
            topics=p.get("topics", []),
            source=p.get("source", "api"),
            source_description=p.get("source_description"),
            success_count=p.get("success_count", 0),
            failure_count=p.get("failure_count", 0),
        )
        for i, p in enumerate(result.get("items", []))
    ]

    return ProcedureListResponse(
        items=items,
        total=result.get("total", len(items)),
        limit=limit,
        offset=offset,
    )


@router.post("/", response_model=ProcedureResponse)
async def add_procedure(
    request: ProcedureCreate,
    service=Depends(get_synapse_service),
    event_bus=Depends(get_event_bus),
):
    """Add a new procedure."""
    result = service.add_procedure(
        trigger=request.trigger,
        steps=request.steps,
        topics=request.topics,
        source=request.source,
    )

    # Emit feed event
    if event_bus:
        await event_bus.emit(
            event_type=FeedEventType.PROCEDURE_ADD,
            summary=f"Added procedure: {request.trigger}",
            layer="PROCEDURAL",
            detail={
                "uuid": result.get("uuid"),
                "trigger": request.trigger,
                "steps": request.steps,
            },
        )

    return _procedure_response_from_result(result)


@router.post("/{procedure_id:path}/success", response_model=ProcedureSuccessResponse)
async def record_procedure_success(
    procedure_id: str,
    service=Depends(get_synapse_service),
    event_bus=Depends(get_event_bus),
):
    """Record successful procedure execution."""
    result = service.record_procedure_success(procedure_id=procedure_id)

    if not result:
        raise HTTPException(status_code=404, detail=f"Procedure '{procedure_id}' not found")

    # Emit feed event
    if event_bus:
        await event_bus.emit(
            event_type=FeedEventType.PROCEDURE_SUCCESS,
            summary=f"Procedure succeeded: {result.get('trigger', procedure_id)}",
            layer="PROCEDURAL",
            detail={
                "uuid": result.get("uuid", procedure_id),
                "trigger": result.get("trigger", procedure_id),
                "success_count": result.get("success_count", 1),
            },
        )

    return ProcedureSuccessResponse(
        uuid=result.get("uuid", procedure_id),
        trigger=result.get("trigger", procedure_id),
        success_count=result.get("success_count", 1),
    )


@router.get("/{procedure_id}", response_model=ProcedureResponse)
async def get_procedure(
    procedure_id: str,
    service=Depends(get_synapse_service),
):
    """Get procedure by ID."""
    result = await service.get_procedure_by_id(procedure_id=procedure_id)

    if not result:
        raise HTTPException(status_code=404, detail=f"Procedure {procedure_id} not found")

    return _procedure_response_from_result(result, fallback_uuid=procedure_id)


@router.put("/{procedure_id}", response_model=ProcedureResponse)
async def update_procedure(
    procedure_id: str,
    request: ProcedureUpdate,
    service=Depends(get_synapse_service),
):
    """Update a procedure."""
    result = await service.update_procedure(
        procedure_id=procedure_id,
        trigger=request.trigger,
        steps=request.steps,
        topics=request.topics,
    )

    if not result:
        raise HTTPException(status_code=404, detail=f"Procedure {procedure_id} not found")

    return _procedure_response_from_result(result, fallback_uuid=procedure_id)


@router.delete("/{procedure_id}", response_model=SuccessResponse)
async def delete_procedure(
    procedure_id: str,
    service=Depends(get_synapse_service),
):
    """Delete a procedure."""
    result = await service.delete_procedure(procedure_id=procedure_id)

    return SuccessResponse(
        status="ok",
        message=result.get("message", f"Procedure {procedure_id} deleted"),
    )
