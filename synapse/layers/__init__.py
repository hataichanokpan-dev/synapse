"""
Five-Layer Memory System

Layer 1: USER_MODEL - Preferences, expertise (NEVER decay)
Layer 2: PROCEDURAL - How-to patterns (SLOW decay)
Layer 3: SEMANTIC - Principles, learnings (NORMAL decay)
Layer 4: EPISODIC - Conversation summaries (TTL-based)
Layer 5: WORKING - Session context (SESSION-based)
"""

from .types import (
    # Enums
    MemoryLayer,
    EntityType,
    RelationType,
    # Config
    DecayConfig,
    # Models
    SynapseNode,
    SynapseEdge,
    SynapseEpisode,
    UserModel,
    ProceduralMemory,
    SearchResult,
    # Utils
    utcnow,
)
from .decay import (
    compute_decay_score,
    compute_ttl,
    extend_ttl,
    should_forget,
    get_half_life,
    refresh_all_decay_scores,
    decay_summary,
)

__all__ = [
    # Enums
    "MemoryLayer",
    "EntityType",
    "RelationType",
    # Config
    "DecayConfig",
    # Models
    "SynapseNode",
    "SynapseEdge",
    "SynapseEpisode",
    "UserModel",
    "ProceduralMemory",
    "SearchResult",
    # Utils
    "utcnow",
    # Decay functions
    "compute_decay_score",
    "compute_ttl",
    "extend_ttl",
    "should_forget",
    "get_half_life",
    "refresh_all_decay_scores",
    "decay_summary",
]
