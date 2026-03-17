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

from api.deps import get_synapse_service
from api.models import (
    ProcedureCreate,
    ProcedureResponse,
    ProcedureListResponse,
    ProcedureSuccessResponse,
    ProcedureUpdate,
    SuccessResponse,
)

router = APIRouter(tags=["Procedures"])


@router.get("/", response_model=ProcedureListResponse)
async def list_procedures(
    trigger: str = Query(None, description="Filter by trigger pattern"),
    topic: str = Query(None, description="Filter by topic"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    service=Depends(get_synapse_service),
):
    """List or find procedures."""
    if trigger:
        result = await service.find_procedures(trigger=trigger)
    else:
        result = []

    items = [
        ProcedureResponse(
            uuid=p.get("uuid", str(i)),
            trigger=p.get("trigger", ""),
            steps=p.get("steps", []),
            topics=p.get("topics", []),
            source=p.get("source", "api"),
            success_count=p.get("success_count", 0),
            failure_count=p.get("failure_count", 0),
        )
        for i, p in enumerate(result)
    ]

    return ProcedureListResponse(
        items=items,
        total=len(items),
        limit=limit,
        offset=offset,
    )


@router.post("/", response_model=ProcedureResponse)
async def add_procedure(
    request: ProcedureCreate,
    service=Depends(get_synapse_service),
):
    """Add a new procedure."""
    result = await service.add_procedure(
        trigger=request.trigger,
        steps=request.steps,
        topics=request.topics,
        source=request.source,
    )

    return ProcedureResponse(
        uuid=result.get("uuid", "new"),
        trigger=request.trigger,
        steps=request.steps,
        topics=request.topics,
        source=request.source,
        source_description=request.source_description,
    )


@router.post("/{trigger:path}/success", response_model=ProcedureSuccessResponse)
async def record_procedure_success(
    trigger: str,
    service=Depends(get_synapse_service),
):
    """Record successful procedure execution."""
    result = await service.record_procedure_success(trigger=trigger)
    return ProcedureSuccessResponse(
        uuid=result.get("uuid", trigger),
        trigger=trigger,
        success_count=result.get("success_count", 1),
    )


@router.get("/{procedure_id}", response_model=ProcedureResponse)
async def get_procedure(
    procedure_id: str,
    service=Depends(get_synapse_service),
):
    """Get procedure by ID."""
    # GAP - needs direct DB access
    result = await service.get_procedure_by_id(procedure_id=procedure_id)

    if not result:
        raise HTTPException(status_code=404, detail=f"Procedure {procedure_id} not found")

    return ProcedureResponse(
        uuid=result.get("uuid", procedure_id),
        trigger=result.get("trigger", ""),
        steps=result.get("steps", []),
        topics=result.get("topics", []),
        source=result.get("source", "api"),
        source_description=result.get("source_description"),
        success_count=result.get("success_count", 0),
        failure_count=result.get("failure_count", 0),
    )


@router.put("/{procedure_id}", response_model=ProcedureResponse)
async def update_procedure(
    procedure_id: str,
    request: ProcedureUpdate,
    service=Depends(get_synapse_service),
):
    """Update a procedure."""
    # GAP - needs direct DB access
    result = await service.update_procedure(
        procedure_id=procedure_id,
        trigger=request.trigger,
        steps=request.steps,
        topics=request.topics,
    )

    if not result:
        raise HTTPException(status_code=404, detail=f"Procedure {procedure_id} not found")

    return ProcedureResponse(
        uuid=procedure_id,
        trigger=result.get("trigger", request.trigger or ""),
        steps=result.get("steps", request.steps or []),
        topics=result.get("topics", request.topics or []),
        source=result.get("source", "api"),
        success_count=result.get("success_count", 0),
        failure_count=result.get("failure_count", 0),
    )


@router.delete("/{procedure_id}", response_model=SuccessResponse)
async def delete_procedure(
    procedure_id: str,
    service=Depends(get_synapse_service),
):
    """Delete a procedure."""
    # GAP - needs direct DB access
    result = await service.delete_procedure(procedure_id=procedure_id)

    return SuccessResponse(
        status="ok",
        message=result.get("message", f"Procedure {procedure_id} deleted"),
    )
