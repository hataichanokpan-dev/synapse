"""
Synapse - Unified AI Memory System

Knowledge Graph + Five-Layer Memory + Thai NLP

Usage:
    from synapse import MemoryLayer, DecayConfig
    from synapse import compute_decay_score, should_forget

    # Check if memory should be forgotten
    score = compute_decay_score(updated_at, access_count, MemoryLayer.SEMANTIC)
    if should_forget(score, expires_at):
        # Archive or delete
        pass
"""

__version__ = "0.1.0"

from synapse.layers import (
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
    # Decay functions
    compute_decay_score,
    compute_ttl,
    extend_ttl,
    should_forget,
    get_half_life,
    refresh_all_decay_scores,
    decay_summary,
)

__all__ = [
    # Version
    "__version__",
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
