"""
Five-Layer Memory System

Layer 1: USER_MODEL - Preferences, expertise (NEVER decay)
Layer 2: PROCEDURAL - How-to patterns (SLOW decay)
Layer 3: SEMANTIC - Principles, learnings (NORMAL decay)
Layer 4: EPISODIC - Conversation summaries (TTL-based)
Layer 5: WORKING - Session context (SESSION-based)

Usage:
    from synapse.layers import (
        LayerManager,
        MemoryLayer,
        get_user_model,
        find_procedure,
        record_episode,
    )
"""

# Types (from types.py)
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

# Decay functions (from decay.py)
from .decay import (
    compute_decay_score,
    compute_ttl,
    extend_ttl,
    should_forget,
    get_half_life,
    refresh_all_decay_scores,
    decay_summary,
)

# Layer 1: User Model (from user_model.py)
from .user_model import (
    UserModelManager,
    get_manager as get_user_model_manager,
    get_user_model,
    update_user_model,
    reset_user_model,
)

# Layer 2: Procedural (from procedural.py)
from .procedural import (
    ProceduralManager,
    get_manager as get_procedural_manager,
    find_procedure,
    learn_procedure,
    record_success,
)

# Layer 3: Semantic (from semantic.py)
from .semantic import (
    SemanticManager,
    get_manager as get_semantic_manager,
)

# Layer 4: Episodic (from episodic.py)
from .episodic import (
    EpisodicManager,
    get_manager as get_episodic_manager,
    record_episode,
    find_episodes,
    purge_expired,
)

# Layer 5: Working (from working.py)
from .working import (
    WorkingManager,
    WorkingContext,
    get_manager as get_working_manager,
    set_context,
    get_context,
    clear_context,
    set_session,
    end_session,
)

# Layer Manager (from manager.py)
from .manager import (
    LayerManager,
    get_layer_manager,
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
    # Layer 1: User Model
    "UserModelManager",
    "get_user_model_manager",
    "get_user_model",
    "update_user_model",
    "reset_user_model",
    # Layer 2: Procedural
    "ProceduralManager",
    "get_procedural_manager",
    "find_procedure",
    "learn_procedure",
    "record_success",
    # Layer 3: Semantic
    "SemanticManager",
    "get_semantic_manager",
    # Layer 4: Episodic
    "EpisodicManager",
    "get_episodic_manager",
    "record_episode",
    "find_episodes",
    "purge_expired",
    # Layer 5: Working
    "WorkingManager",
    "WorkingContext",
    "get_working_manager",
    "set_context",
    "get_context",
    "clear_context",
    "set_session",
    "end_session",
    # Layer Manager
    "LayerManager",
    "get_layer_manager",
]
