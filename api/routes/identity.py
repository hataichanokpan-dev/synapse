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
)

router = APIRouter(tags=["Identity"])


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

    # Normalize types: service may return dict for expertise, list for notes
    expertise_raw = result.get("expertise", [])
    expertise = list(expertise_raw.keys()) if isinstance(expertise_raw, dict) else list(expertise_raw)
    notes_raw = result.get("notes", "")
    notes = ", ".join(notes_raw) if isinstance(notes_raw, list) else str(notes_raw)

    # Normalize response_style: service may return values not in ResponseStyle enum
    style = result.get("response_style", "balanced")
    try:
        style = ResponseStyle(style)
    except ValueError:
        style = ResponseStyle.BALANCED

    prefs = UserPreferences(
        language=result.get("language", "en"),
        timezone=result.get("timezone", "UTC"),
        response_style=style,
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


@router.put("/preferences", response_model=PreferencesResponse)
async def update_preferences(
    request: UpdatePreferencesRequest,
    service=Depends(get_synapse_service),
):
    """Update user preferences."""
    updates = request.model_dump(exclude_unset=True, exclude_none=True)

    # Map frontend field names to service params
    kwargs = {}
    if "language" in updates:
        kwargs["language"] = updates["language"]
    if "timezone" in updates:
        kwargs["timezone"] = updates["timezone"]
    if "response_style" in updates:
        kwargs["response_style"] = updates["response_style"]
    if "add_expertise" in updates and updates["add_expertise"]:
        kwargs["add_expertise"] = updates["add_expertise"]
    if "add_topics" in updates and updates["add_topics"]:
        kwargs["add_topic"] = updates["add_topics"]

    result = service.update_user_preferences(**kwargs)

    expertise_raw = result.get("expertise", [])
    expertise = list(expertise_raw.keys()) if isinstance(expertise_raw, dict) else list(expertise_raw)
    notes_raw = result.get("notes", "")
    notes = ", ".join(notes_raw) if isinstance(notes_raw, list) else str(notes_raw)
    style = result.get("response_style", "balanced")
    try:
        style = ResponseStyle(style)
    except ValueError:
        style = ResponseStyle.BALANCED

    prefs = UserPreferences(
        language=result.get("language", "en"),
        timezone=result.get("timezone", "UTC"),
        response_style=style,
        expertise=expertise,
        topics=result.get("common_topics", []),
        notes=notes,
        custom={},
    )
    return PreferencesResponse(preferences=prefs)
