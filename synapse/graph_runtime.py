"""Shared runtime helpers for canonical graph projection behavior."""

from __future__ import annotations

import copy
import os
import re
from dataclasses import dataclass
from typing import Any, Optional

_DEFAULT_FALKOR_DATABASE = "user-bfipa"
_DEFAULT_GRAPH_GROUP = "global"


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(str(raw).strip())
    except (TypeError, ValueError):
        return default


def canonical_graph_database() -> str:
    """Return the single graph database/runtime namespace used by the app."""
    configured = os.getenv("GRAPH_CANONICAL_DATABASE") or os.getenv(
        "FALKORDB_DATABASE",
        _DEFAULT_FALKOR_DATABASE,
    )
    value = str(configured).strip()
    return value or _DEFAULT_FALKOR_DATABASE


def normalize_graph_group_id(group_id: Optional[str]) -> str:
    """Normalize app-level graph group IDs to a single default."""
    configured_default = os.getenv("GRAPH_DEFAULT_GROUP_ID", _DEFAULT_GRAPH_GROUP)
    raw = configured_default if group_id is None else group_id
    sanitized = re.sub(r"[^A-Za-z0-9_]+", "_", str(raw).strip())
    sanitized = sanitized.strip("_")
    return sanitized or _DEFAULT_GRAPH_GROUP


@dataclass(frozen=True)
class GraphProjectionRuntimeConfig:
    canonical_database: str
    default_group_id: str
    max_inflight: int
    min_interval_seconds: float
    cooldown_seconds: int
    max_retries: int
    lease_timeout_seconds: int
    projector_version: str = "v2"


def load_graph_projection_runtime_config() -> GraphProjectionRuntimeConfig:
    """Load the graph projection runtime config from environment variables."""
    return GraphProjectionRuntimeConfig(
        canonical_database=canonical_graph_database(),
        default_group_id=normalize_graph_group_id(None),
        max_inflight=max(1, _env_int("GRAPH_PROJECTION_MAX_INFLIGHT", 1)),
        min_interval_seconds=max(0.0, _env_float("GRAPH_PROJECTION_MIN_INTERVAL_SECONDS", 10.0)),
        cooldown_seconds=max(1, _env_int("GRAPH_PROJECTION_COOLDOWN_SECONDS", 300)),
        max_retries=max(1, _env_int("GRAPH_PROJECTION_MAX_RETRIES", 12)),
        lease_timeout_seconds=max(30, _env_int("GRAPH_PROJECTION_LEASE_TIMEOUT_SECONDS", 300)),
        projector_version=os.getenv("GRAPH_PROJECTION_VERSION", "v2").strip() or "v2",
    )


def bind_graph_driver(driver: Any, database: Optional[str] = None) -> Any:
    """Return a driver bound to the canonical graph database without mutating the shared instance."""
    if driver is None:
        return None
    resolved_database = database or canonical_graph_database()
    if hasattr(driver, "clone"):
        return driver.clone(database=resolved_database)
    if hasattr(driver, "with_database"):
        return driver.with_database(resolved_database)
    return driver


def bind_graphiti_client(graphiti_client: Any, database: Optional[str] = None) -> Any:
    """Return a shallow graphiti client copy pinned to one graph database."""
    if graphiti_client is None:
        return None

    isolated = copy.copy(graphiti_client)
    graphiti_dict = getattr(graphiti_client, "__dict__", {})
    bound_driver = bind_graph_driver(
        graphiti_dict.get("_driver")
        or graphiti_dict.get("driver")
        or getattr(graphiti_client, "_driver", None)
        or getattr(graphiti_client, "driver", None),
        database=database,
    )
    if bound_driver is not None:
        if hasattr(isolated, "_driver"):
            isolated._driver = bound_driver
        if hasattr(isolated, "driver"):
            isolated.driver = bound_driver
        clients = getattr(isolated, "clients", None)
        if clients is not None and hasattr(clients, "driver"):
            clients.driver = bound_driver
    return isolated
