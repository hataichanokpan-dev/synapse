"""
Synapse Decay System

Temporal decay scoring for memory management.

Formula: decay_score = recency_factor × access_factor

recency_factor = e^(-λ × days_since_update)
access_factor = min(1.0, 0.5 + access_count × 0.05)
"""

import math
from datetime import datetime, timedelta, timezone
from typing import Optional, List

from .types import MemoryLayer, DecayConfig, utcnow


def compute_decay_score(
    updated_at: datetime,
    access_count: int,
    memory_layer: MemoryLayer,
    now: Optional[datetime] = None,
) -> float:
    """
    Compute decay score for a memory node.

    Args:
        updated_at: When the node was last updated (timezone-aware UTC)
        access_count: Number of times accessed (will be clamped to >= 0)
        memory_layer: Which memory layer the node belongs to
        now: Current time (default: utcnow())

    Returns:
        Decay score between 0.0 and 1.0
    """
    if now is None:
        now = utcnow()

    # Clamp access_count to prevent negative impact
    access_count = max(0, access_count)

    # Layer 1 (user_model) never decays
    if memory_layer == MemoryLayer.USER_MODEL:
        return 1.0

    # Layer 5 (working) is session-based, always fresh
    if memory_layer == MemoryLayer.WORKING:
        return 1.0

    # Layer 4 (episodic) uses TTL, not decay
    if memory_layer == MemoryLayer.EPISODIC:
        return 1.0  # TTL handled separately

    # Calculate fractional days since update (more precise than integer)
    delta = now - updated_at
    days_since = max(0.0, delta.total_seconds() / 86400.0)

    # Pick λ based on layer
    if memory_layer == MemoryLayer.PROCEDURAL:
        lambda_val = DecayConfig.LAMBDA_PROCEDURAL
    else:
        lambda_val = DecayConfig.LAMBDA_DEFAULT

    # Apply layer multiplier
    multiplier = DecayConfig.LAYER_MULTIPLIERS.get(memory_layer, 1.0)
    effective_lambda = lambda_val * multiplier

    # Recency factor: e^(-λ × days)
    recency_factor = math.exp(-effective_lambda * days_since)

    # Access factor: min(1.0, 0.5 + count × 0.05)
    # 10+ accesses = max factor
    access_factor = min(
        1.0,
        DecayConfig.ACCESS_BASE + access_count * DecayConfig.ACCESS_INCREMENT,
    )

    # Combined score
    score = recency_factor * access_factor

    return round(score, 4)


def compute_ttl(
    memory_layer: MemoryLayer,
    created_at: datetime,
    access_count: int = 0,
) -> Optional[datetime]:
    """
    Compute TTL expiration for episodic memory.

    Args:
        memory_layer: Memory layer
        created_at: Creation timestamp (timezone-aware)
        access_count: Number of accesses

    Returns:
        Expiration datetime or None (no expiration)
    """
    if memory_layer != MemoryLayer.EPISODIC:
        return None

    # Base TTL: 90 days
    base_days = DecayConfig.TTL_EPISODIC_DAYS

    # Extend based on access: +1 day per access (max 30 extra)
    extra_days = min(30, max(0, access_count))

    return created_at + timedelta(days=base_days + extra_days)


def extend_ttl(
    current_expires_at: Optional[datetime],
    now: Optional[datetime] = None,
    allow_revival: bool = False,
) -> Optional[datetime]:
    """
    Extend TTL on access (for episodic memory).

    Args:
        current_expires_at: Current expiration
        now: Current time
        allow_revival: If True, can extend even if already expired
                       If False, return None if already expired

    Returns:
        New expiration or None (if not applicable or not revivable)
    """
    if current_expires_at is None:
        return None

    if now is None:
        now = utcnow()

    # BUG FIX: Check if already expired
    if current_expires_at <= now:
        if not allow_revival:
            return None  # Already expired, no revival
        # If revival allowed, extend from now
        return now + timedelta(days=DecayConfig.TTL_EXTEND_DAYS)

    # Extend from current expiration
    return current_expires_at + timedelta(days=DecayConfig.TTL_EXTEND_DAYS)


def should_forget(
    decay_score: float,
    expires_at: Optional[datetime],
    now: Optional[datetime] = None,
    threshold: Optional[float] = None,
) -> bool:
    """
    Determine if memory should be forgotten.

    Args:
        decay_score: Current decay score
        expires_at: TTL expiration
        now: Current time
        threshold: Decay threshold (default: from DecayConfig)

    Returns:
        True if should forget
    """
    if now is None:
        now = utcnow()

    if threshold is None:
        threshold = DecayConfig.DECAY_THRESHOLD

    # TTL expired (use <= for exact expiry)
    if expires_at is not None and expires_at <= now:
        return True

    # Decay below threshold
    if decay_score < threshold:
        return True

    return False


def get_half_life(memory_layer: MemoryLayer) -> Optional[float]:
    """
    Get half-life in days for a memory layer.

    Half-life = ln(2) / λ

    Args:
        memory_layer: Memory layer

    Returns:
        Half-life in days, or None if not applicable (TTL/session-based)
    """
    # TTL-based layers - no decay half-life
    if memory_layer == MemoryLayer.EPISODIC:
        return None  # TTL-based, not decay

    # Session-based layers - no decay
    if memory_layer == MemoryLayer.WORKING:
        return None  # Session only

    # Never decays
    if memory_layer == MemoryLayer.USER_MODEL:
        return float("inf")

    # Decay-based layers
    if memory_layer == MemoryLayer.PROCEDURAL:
        lambda_val = DecayConfig.LAMBDA_PROCEDURAL
    else:
        lambda_val = DecayConfig.LAMBDA_DEFAULT

    return math.log(2) / lambda_val


def refresh_all_decay_scores(
    nodes: List[dict],
    now: Optional[datetime] = None,
) -> List[dict]:
    """
    Refresh decay scores for a batch of nodes.

    Args:
        nodes: List of node dicts with 'updated_at', 'access_count', 'memory_layer'
        now: Current time

    Returns:
        List of nodes with updated 'decay_score' field
    """
    if now is None:
        now = utcnow()

    for node in nodes:
        updated_at = node.get("updated_at")
        access_count = node.get("access_count", 0)
        memory_layer = node.get("memory_layer", MemoryLayer.SEMANTIC)

        if updated_at is not None:
            node["decay_score"] = compute_decay_score(
                updated_at=updated_at,
                access_count=access_count,
                memory_layer=memory_layer,
                now=now,
            )

    return nodes


def decay_summary(nodes: List[dict]) -> dict:
    """
    Get summary statistics for decay scores.

    Args:
        nodes: List of nodes with decay_score

    Returns:
        Summary dict with counts and averages
    """
    if not nodes:
        return {
            "total": 0,
            "healthy": 0,
            "decaying": 0,
            "forgotten": 0,
            "avg_score": 0.0,
        }

    scores = [n.get("decay_score", 1.0) for n in nodes]
    threshold = DecayConfig.DECAY_THRESHOLD

    return {
        "total": len(nodes),
        "healthy": sum(1 for s in scores if s >= 0.7),
        "decaying": sum(1 for s in scores if threshold <= s < 0.7),
        "forgotten": sum(1 for s in scores if s < threshold),
        "avg_score": round(sum(scores) / len(scores), 4),
    }


# Half-lives for reference:
# λ = 0.01  → half-life ≈ 69.3 days
# λ = 0.005 → half-life ≈ 138.6 days
