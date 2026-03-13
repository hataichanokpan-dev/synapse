"""
Synapse Decay System

Temporal decay scoring for memory management.

Formula: decay_score = recency_factor × access_factor

recency_factor = e^(-λ × days_since_update)
access_factor = min(1.0, 0.5 + access_count × 0.05)
"""

import math
from datetime import datetime, timedelta
from typing import Optional

from synapse.layers.types import MemoryLayer


class DecayConfig:
    """Decay configuration constants"""

    # Lambda values for exponential decay
    LAMBDA_DEFAULT = 0.01  # Half-life ~69 days
    LAMBDA_PROCEDURAL = 0.005  # Half-life ~139 days

    # TTL for episodic memory
    TTL_EPISODIC_DAYS = 90
    TTL_EXTEND_DAYS = 30

    # Decay threshold
    DECAY_THRESHOLD = 0.1


def compute_decay_score(
    updated_at: datetime,
    access_count: int,
    memory_layer: MemoryLayer,
    now: Optional[datetime] = None,
) -> float:
    """
    Compute decay score for a memory node.

    Args:
        updated_at: When the node was last updated
        access_count: Number of times accessed
        memory_layer: Which memory layer the node belongs to
        now: Current time (default: datetime.utcnow())

    Returns:
        Decay score between 0.0 and 1.0
    """
    if now is None:
        now = datetime.utcnow()

    # Layer 1 (user_model) never decays
    if memory_layer == MemoryLayer.USER_MODEL:
        return 1.0

    # Layer 5 (working) is session-based, always fresh
    if memory_layer == MemoryLayer.WORKING:
        return 1.0

    # Layer 4 (episodic) uses TTL, not decay
    if memory_layer == MemoryLayer.EPISODIC:
        return 1.0  # TTL handled separately

    # Calculate days since update
    days_since = max(0, (now - updated_at).days)

    # Pick λ based on layer
    if memory_layer == MemoryLayer.PROCEDURAL:
        lambda_val = DecayConfig.LAMBDA_PROCEDURAL
    else:
        lambda_val = DecayConfig.LAMBDA_DEFAULT

    # Recency factor: e^(-λ × days)
    recency_factor = math.exp(-lambda_val * days_since)

    # Access factor: min(1.0, 0.5 + count × 0.05)
    # 10+ accesses = max factor
    access_factor = min(1.0, 0.5 + access_count * 0.05)

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
        created_at: Creation timestamp
        access_count: Number of accesses

    Returns:
        Expiration datetime or None (no expiration)
    """
    if memory_layer != MemoryLayer.EPISODIC:
        return None

    # Base TTL: 90 days
    base_days = DecayConfig.TTL_EPISODIC_DAYS

    # Extend based on access: +1 day per access (max 30 extra)
    extra_days = min(30, access_count)

    return created_at + timedelta(days=base_days + extra_days)


def extend_ttl(
    current_expires_at: Optional[datetime],
    now: Optional[datetime] = None,
) -> Optional[datetime]:
    """
    Extend TTL on access (for episodic memory).

    Args:
        current_expires_at: Current expiration
        now: Current time

    Returns:
        New expiration or None
    """
    if current_expires_at is None:
        return None

    if now is None:
        now = datetime.utcnow()

    # Extend by 30 days
    return current_expires_at + timedelta(days=DecayConfig.TTL_EXTEND_DAYS)


def should_forget(
    decay_score: float,
    expires_at: Optional[datetime],
    now: Optional[datetime] = None,
    threshold: float = 0.1,
) -> bool:
    """
    Determine if memory should be forgotten.

    Args:
        decay_score: Current decay score
        expires_at: TTL expiration
        now: Current time
        threshold: Decay threshold

    Returns:
        True if should forget
    """
    if now is None:
        now = datetime.utcnow()

    # TTL expired
    if expires_at and expires_at < now:
        return True

    # Decay below threshold
    if decay_score < threshold:
        return True

    return False


def get_half_life(memory_layer: MemoryLayer) -> float:
    """
    Get half-life in days for a memory layer.

    Half-life = ln(2) / λ

    Args:
        memory_layer: Memory layer

    Returns:
        Half-life in days
    """
    if memory_layer == MemoryLayer.USER_MODEL:
        return float("inf")  # Never decays

    if memory_layer == MemoryLayer.PROCEDURAL:
        lambda_val = DecayConfig.LAMBDA_PROCEDURAL
    else:
        lambda_val = DecayConfig.LAMBDA_DEFAULT

    return math.log(2) / lambda_val


# Half-lives for reference:
# λ = 0.01  → half-life ≈ 69 days
# λ = 0.005 → half-life ≈ 139 days
