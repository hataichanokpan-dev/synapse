"""
Normalization helpers for API <-> core boundary values.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

from api.models.memory import MemoryLayer as ApiMemoryLayer
from synapse.layers import MemoryLayer as CoreMemoryLayer

_API_LAYER_ALIASES = {
    "user": ApiMemoryLayer.USER_MODEL,
    "user_model": ApiMemoryLayer.USER_MODEL,
    "procedural": ApiMemoryLayer.PROCEDURAL,
    "semantic": ApiMemoryLayer.SEMANTIC,
    "episodic": ApiMemoryLayer.EPISODIC,
    "working": ApiMemoryLayer.WORKING,
}

_CORE_LAYER_ALIASES = {
    "user": CoreMemoryLayer.USER_MODEL,
    "user_model": CoreMemoryLayer.USER_MODEL,
    "procedural": CoreMemoryLayer.PROCEDURAL,
    "semantic": CoreMemoryLayer.SEMANTIC,
    "episodic": CoreMemoryLayer.EPISODIC,
    "working": CoreMemoryLayer.WORKING,
}

_API_TO_CORE = {
    ApiMemoryLayer.USER_MODEL: CoreMemoryLayer.USER_MODEL,
    ApiMemoryLayer.PROCEDURAL: CoreMemoryLayer.PROCEDURAL,
    ApiMemoryLayer.SEMANTIC: CoreMemoryLayer.SEMANTIC,
    ApiMemoryLayer.EPISODIC: CoreMemoryLayer.EPISODIC,
    ApiMemoryLayer.WORKING: CoreMemoryLayer.WORKING,
}

_CORE_TO_API = {value: key for key, value in _API_TO_CORE.items()}


def utcnow() -> datetime:
    """Return timezone-aware current UTC timestamp."""
    return datetime.now(timezone.utc)


def coerce_utc_datetime(value: Any) -> datetime | None:
    """Convert supported datetime-like values into aware UTC datetimes."""
    if value is None:
        return None

    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)

    if isinstance(value, (int, float)):
        scale = 1000 if value > 1e12 else 1
        return datetime.fromtimestamp(value / scale, tz=timezone.utc)

    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
            return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            try:
                numeric = float(text)
            except ValueError:
                return None
            scale = 1000 if numeric > 1e12 else 1
            return datetime.fromtimestamp(numeric / scale, tz=timezone.utc)

    return None


def parse_api_memory_layer(value: Any) -> ApiMemoryLayer | None:
    """Normalize user-facing/API memory layer values."""
    if value is None:
        return None
    if isinstance(value, ApiMemoryLayer):
        return value
    if isinstance(value, CoreMemoryLayer):
        return _CORE_TO_API.get(value)

    text = str(value).strip()
    if not text:
        return None

    normalized = text.lower().replace("-", "_")
    if normalized in _API_LAYER_ALIASES:
        return _API_LAYER_ALIASES[normalized]

    try:
        return ApiMemoryLayer(text.upper())
    except ValueError:
        return None


def parse_core_memory_layer(value: Any) -> CoreMemoryLayer | None:
    """Normalize core/internal memory layer values."""
    if value is None:
        return None
    if isinstance(value, CoreMemoryLayer):
        return value
    if isinstance(value, ApiMemoryLayer):
        return _API_TO_CORE[value]

    text = str(value).strip()
    if not text:
        return None

    normalized = text.lower().replace("-", "_")
    if normalized in _CORE_LAYER_ALIASES:
        return _CORE_LAYER_ALIASES[normalized]

    try:
        return CoreMemoryLayer(normalized)
    except ValueError:
        return None


def internal_layer_value(value: Any) -> str | None:
    """Return normalized internal layer string."""
    layer = parse_core_memory_layer(value)
    return layer.value if layer is not None else None


def api_layer_value(value: Any) -> str | None:
    """Return normalized API layer string."""
    layer = parse_api_memory_layer(value)
    return layer.value if layer is not None else None


def normalize_layer_list(values: Iterable[Any] | None, target: str = "core") -> list[Any] | None:
    """Normalize a layer iterable into API or core enums."""
    if values is None:
        return None

    parsed = []
    for value in values:
        layer = parse_core_memory_layer(value) if target == "core" else parse_api_memory_layer(value)
        if layer is not None:
            parsed.append(layer)

    return parsed
