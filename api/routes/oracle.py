"""
Oracle routes for Synapse API.

Endpoints:
    POST /api/oracle/consult  - Consult memory for guidance
    POST /api/oracle/reflect  - Get random reflection
    POST /api/oracle/analyze  - Analyze memory patterns
"""

from fastapi import APIRouter, Depends

from api.deps import get_synapse_service
from api.models import (
    ConsultRequest,
    ConsultResponse,
    LayerSummary,
    ReflectRequest,
    ReflectResponse,
    Insight,
    AnalyzeRequest,
    AnalyzeResponse,
    MemoryLayer,
)

router = APIRouter(tags=["Oracle"])


@router.post("/consult", response_model=ConsultResponse)
async def consult(
    request: ConsultRequest,
    service=Depends(get_synapse_service),
):
    """Consult memory for guidance."""
    layers = [l.value for l in request.layers] if request.layers else None

    result = await service.consult(
        query=request.query,
        layers=layers,
        limit=request.limit,
    )

    # Parse layer summaries
    layer_summaries = {}
    for layer_name, layer_data in result.get("layers", {}).items():
        try:
            layer_enum = MemoryLayer(layer_name.upper())
        except ValueError:
            continue
        layer_summaries[layer_name] = LayerSummary(
            layer=layer_enum,
            count=layer_data.get("count", 0),
            top_results=layer_data.get("top_results", []),
            relevance_score=layer_data.get("relevance_score"),
        )

    return ConsultResponse(
        query=request.query,
        layers=layer_summaries,
        summary=result.get("summary", []),
        suggestions=result.get("suggestions", []),
    )


@router.post("/reflect", response_model=ReflectResponse)
async def reflect(
    request: ReflectRequest,
    service=Depends(get_synapse_service),
):
    """Get random reflection."""
    layer = request.layer.value if request.layer else None

    result = await service.reflect(layer=layer)

    insights = [
        Insight(
            content=i.get("content", ""),
            layer=MemoryLayer(i.get("layer", "EPISODIC")),
            source=i.get("source", "unknown"),
            relevance=i.get("relevance", 1.0),
        )
        for i in result.get("insights", [])
    ]

    return ReflectResponse(
        insights=insights[:request.count],
        source_layer=layer or "all",
    )


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(
    request: AnalyzeRequest,
    service=Depends(get_synapse_service),
):
    """Analyze memory patterns."""
    result = await service.analyze_patterns(
        analysis_type=request.analysis_type.value,
        time_range_days=request.time_range_days,
        group_id=request.group_id,
    )

    return AnalyzeResponse(
        time_range_days=request.time_range_days,
        patterns=result.get("patterns", {}),
    )
