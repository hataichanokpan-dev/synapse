"""
Oracle routes for Synapse API.

Endpoints:
    POST /api/oracle/consult  - Consult memory for guidance
    POST /api/oracle/reflect  - Get random reflection
    POST /api/oracle/analyze  - Analyze memory patterns
"""

from fastapi import APIRouter, Depends

from api.deps import get_synapse_service
from api.normalization import parse_api_memory_layer, parse_core_memory_layer
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
from synapse.search import HybridSearchError

router = APIRouter(tags=["Oracle"])


@router.post("/consult", response_model=ConsultResponse)
async def consult(
    request: ConsultRequest,
    service=Depends(get_synapse_service),
):
    """Consult memory for guidance."""
    layers = None
    if request.layers:
        layers = []
        for layer in request.layers:
            normalized = parse_core_memory_layer(layer)
            if normalized is not None:
                layers.append(normalized.value)

    try:
        result = await service.consult(
            query=request.query,
            layers=layers,
            limit=request.limit,
            mode=request.mode.value,
            query_type=request.query_type.value,
            explain=request.explain,
        )
    except HybridSearchError as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=503, detail={"message": str(exc), "degraded_backends": exc.degraded_backends})

    # Parse layer summaries - service returns {layer_name: [items]}
    layer_summaries = {}
    for layer_name, layer_data in result.get("layers", {}).items():
        layer_enum = parse_api_memory_layer(layer_name)
        if layer_enum is None:
            continue

        # layer_data is a list of items from search_all
        items = layer_data if isinstance(layer_data, list) else []
        top_results = []
        for item in items[:5]:
            if isinstance(item, dict):
                top_results.append(item)
            elif hasattr(item, "__dict__"):
                top_results.append({"preview": str(item)[:200], "type": type(item).__name__})
            else:
                top_results.append({"preview": str(item)[:200]})

        layer_summaries[layer_enum.value] = LayerSummary(
            layer=layer_enum,
            count=len(items),
            top_results=top_results,
            relevance_score=None,
        )

    # summary from service is a list of dicts with layer/count/top_result
    summary_texts = []
    for s in result.get("summary", []):
        if isinstance(s, dict):
            summary_texts.append(f"{s.get('layer', '')}: {s.get('count', 0)} results")
        else:
            summary_texts.append(str(s))

    ranked_results = []
    for item in result.get("ranked_results", []):
        layer_enum = parse_api_memory_layer(item.get("layer")) or MemoryLayer.EPISODIC
        ranked_results.append(
            {
                "uuid": str(item.get("uuid", "")),
                "layer": layer_enum,
                "name": str(item.get("name", "")),
                "content": str(item.get("content", "")),
                "score": float(item.get("score", 1.0)),
                "metadata": item.get("metadata", {}) if isinstance(item.get("metadata"), dict) else {},
                "sources": item.get("sources"),
                "score_breakdown": item.get("score_breakdown"),
                "match_reasons": item.get("match_reasons"),
                "path": item.get("path"),
                "degraded_backends": item.get("degraded_backends"),
            }
        )

    return ConsultResponse(
        query=request.query,
        layers=layer_summaries,
        summary=summary_texts,
        suggestions=result.get("suggestions", []),
        ranked_results=ranked_results,
        mode_used=result.get("mode_used"),
        query_type_detected=result.get("query_type_detected"),
        used_backends=list(result.get("used_backends", [])),
        degraded=bool(result.get("degraded", False)),
        warnings=list(result.get("warnings", [])),
        pinned_context=list(result.get("pinned_context", [])),
    )


@router.post("/reflect", response_model=ReflectResponse)
async def reflect(
    request: ReflectRequest,
    service=Depends(get_synapse_service),
):
    """Get random reflection."""
    layer = request.layer.value if request.layer else None

    result = await service.reflect(layer=layer)

    insights = []
    for i in result.get("insights", []):
        # Map service insight dicts to Insight model
        insight_type = i.get("type", "unknown")
        if insight_type == "procedure":
            content = f"Procedure: {i.get('trigger', '')} → {i.get('steps', [])}"
            source_layer = "PROCEDURAL"
        elif insight_type == "episode":
            content = i.get("summary") or i.get("content", "")
            source_layer = "EPISODIC"
        elif insight_type == "working_context":
            content = f"{i.get('key', '')}: {i.get('value', '')}"
            source_layer = "WORKING"
        else:
            content = str(i)
            source_layer = "EPISODIC"

        insights.append(Insight(
            content=content,
            layer=MemoryLayer(source_layer),
            source=insight_type,
            relevance=1.0,
        ))

    return ReflectResponse(
        insights=insights[:request.count],
        source_layer=result.get("source_layer", layer or "all"),
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
    )

    return AnalyzeResponse(
        time_range_days=request.time_range_days,
        patterns=result.get("patterns", {}),
    )
