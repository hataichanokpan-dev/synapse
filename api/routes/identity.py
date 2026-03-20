"""
Identity routes for Synapse API.

Endpoints:
    GET    /api/identity              - Get current identity
    PUT    /api/identity              - Set identity
    DELETE /api/identity              - Clear identity
    GET    /api/identity/preferences  - Get user preferences
    PUT    /api/identity/preferences  - Update user preferences
"""

from fastapi import APIRouter, Depends

from api.deps import get_synapse_service
from api.models import (
    IdentityResponse,
    SetIdentityRequest,
    SuccessResponse,
    UserPreferences,
    UpdatePreferencesRequest,
    PreferencesResponse,
    ResponseStyle,
    ResponseLength,
)

router = APIRouter(tags=["Identity"])


def _build_preferences_response(result: dict, user_id: str | None = None) -> PreferencesResponse:
    """Normalize service user-context output into canonical API preferences."""
    expertise_raw = result.get("expertise", [])
    expertise = list(expertise_raw.keys()) if isinstance(expertise_raw, dict) else list(expertise_raw or [])
    notes_raw = result.get("notes", "")
    notes = ", ".join(notes_raw) if isinstance(notes_raw, list) else str(notes_raw or "")

    try:
        style = ResponseStyle(result.get("response_style", "auto"))
    except ValueError:
        style = ResponseStyle.AUTO
    try:
        length = ResponseLength(result.get("response_length", "auto"))
    except ValueError:
        length = ResponseLength.AUTO

    prefs = UserPreferences(
        language=result.get("language", "en"),
        timezone=result.get("timezone", "UTC"),
        response_style=style,
        response_length=length,
        expertise=expertise,
        topics=result.get("common_topics", []),
        notes=notes,
        custom={},
    )
    return PreferencesResponse(
        user_id=result.get("user_id", user_id),
        preferences=prefs,
        updated_at=result.get("updated_at"),
    )


@router.get("/", response_model=IdentityResponse)
async def get_identity(service=Depends(get_synapse_service)):
    """Get current identity context."""
    result = service.get_identity()
    return IdentityResponse(
        user_id=result.get("user_id"),
        agent_id=result.get("agent_id"),
        chat_id=result.get("chat_id"),
    )


@router.put("/", response_model=IdentityResponse)
async def set_identity(
    request: SetIdentityRequest,
    service=Depends(get_synapse_service),
):
    """Set identity context."""
    result = service.set_identity(
        user_id=request.user_id,
        agent_id=request.agent_id,
        chat_id=request.chat_id,
    )
    return IdentityResponse(
        user_id=result.get("user_id") or request.user_id,
        agent_id=result.get("agent_id") or request.agent_id,
        chat_id=result.get("chat_id") or request.chat_id,
    )


@router.delete("/", response_model=SuccessResponse)
async def clear_identity(service=Depends(get_synapse_service)):
    """Clear identity context."""
    result = service.clear_identity()
    return SuccessResponse(
        message="Identity cleared",
        detail=f"Previous: {result}",
    )


@router.get("/preferences", response_model=PreferencesResponse)
async def get_preferences(
    user_id: str = None,
    service=Depends(get_synapse_service),
):
    """Get user preferences (Layer 1 - User Model)."""
    result = service.get_user_context()
    return _build_preferences_response(result, user_id=user_id)


@router.put("/preferences", response_model=PreferencesResponse)
async def update_preferences(
    request: UpdatePreferencesRequest,
    service=Depends(get_synapse_service),
):
    """Update user preferences."""
    # Pass fields directly to service - it now handles List[str] for expertise/topics
    result = service.update_user_preferences(
        language=request.language,
        timezone=request.timezone,
        response_style=request.response_style.value if request.response_style else None,
        response_length=request.response_length.value if request.response_length else None,
        add_expertise=request.add_expertise,
        remove_expertise=request.remove_expertise,
        add_topics=request.add_topics,
        remove_topics=request.remove_topics,
        notes=request.notes,
    )
    return _build_preferences_response(result)
