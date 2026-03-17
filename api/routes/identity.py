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
)

router = APIRouter(tags=["Identity"])


@router.get("/", response_model=IdentityResponse)
async def get_identity(service=Depends(get_synapse_service)):
    """Get current identity context."""
    result = await service.get_identity()
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
    result = await service.set_identity(
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
    result = await service.clear_identity()
    return SuccessResponse(
        message="Identity cleared",
        detail=f"Previous: {result.get('previous', {})}",
    )


@router.get("/preferences", response_model=PreferencesResponse)
async def get_preferences(
    user_id: str = None,
    service=Depends(get_synapse_service),
):
    """Get user preferences (Layer 1 - User Model)."""
    result = await service.get_user_preferences(user_id=user_id)
    prefs = UserPreferences(
        language=result.get("language", "en"),
        timezone=result.get("timezone", "UTC"),
        response_style=result.get("response_style", "balanced"),
        expertise=result.get("expertise", []),
        topics=result.get("topics", []),
        notes=result.get("notes", ""),
        custom=result.get("custom", {}),
    )
    return PreferencesResponse(
        user_id=user_id,
        preferences=prefs,
    )


@router.put("/preferences", response_model=PreferencesResponse)
async def update_preferences(
    request: UpdatePreferencesRequest,
    service=Depends(get_synapse_service),
):
    """Update user preferences."""
    updates = request.model_dump(exclude_unset=True, exclude_none=True)

    # Handle list operations
    updates.pop("add_expertise", None)
    updates.pop("remove_expertise", None)
    updates.pop("add_topics", None)
    updates.pop("remove_topics", None)

    result = await service.update_user_preferences(**updates)

    prefs = UserPreferences(
        language=result.get("language", "en"),
        timezone=result.get("timezone", "UTC"),
        response_style=result.get("response_style", "balanced"),
        expertise=result.get("expertise", []),
        topics=result.get("topics", []),
        notes=result.get("notes", ""),
        custom=result.get("custom", {}),
    )
    return PreferencesResponse(preferences=prefs)
