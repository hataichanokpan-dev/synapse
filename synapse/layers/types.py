"""
Synapse Type Definitions

Five-Layer Memory Model + Graph Schema
"""

from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from pydantic import BaseModel, Field


class MemoryLayer(str, Enum):
    """
    Five-Layer Memory Model

    Based on cognitive memory architecture:
    - Layer 1: user_model - User preferences, expertise (NEVER decay)
    - Layer 2: procedural - How-to patterns, procedures (SLOW decay)
    - Layer 3: semantic - Principles, patterns, learnings (NORMAL decay)
    - Layer 4: episodic - Conversation summaries (TTL-based)
    - Layer 5: working - Session context (SESSION-based)
    """

    USER_MODEL = "user_model"
    PROCEDURAL = "procedural"
    SEMANTIC = "semantic"
    EPISODIC = "episodic"
    WORKING = "working"


class DecayConfig:
    """
    Decay configuration for each layer.

    SINGLE SOURCE OF TRUTH - import from here, do not duplicate.
    """

    # Lambda values for exponential decay
    LAMBDA_DEFAULT = 0.01  # Half-life ~69 days
    LAMBDA_PROCEDURAL = 0.005  # Half-life ~139 days

    # TTL for episodic memory
    TTL_EPISODIC_DAYS = 90
    TTL_EXTEND_DAYS = 30  # Extend on access

    # Decay threshold for forgetting
    DECAY_THRESHOLD = 0.1  # Below this = forget

    # Access factor constants
    ACCESS_BASE = 0.5
    ACCESS_INCREMENT = 0.05
    ACCESS_MAX_COUNT = 10  # 10+ accesses = max factor

    # Decay multipliers per layer (applied to lambda)
    LAYER_MULTIPLIERS = {
        MemoryLayer.USER_MODEL: 0.0,  # Never decay
        MemoryLayer.PROCEDURAL: 0.5,  # Half the decay rate
        MemoryLayer.SEMANTIC: 1.0,  # Normal decay
        MemoryLayer.EPISODIC: 0.0,  # TTL-based, not decay
        MemoryLayer.WORKING: 0.0,  # Session only
    }

    # TTL constants (days)
    TTL_EPISODIC_DEFAULT_DAYS = 90
    TTL_EPISODIC_MAX_EXTENSION = 30  # Max extra days from access


def utcnow() -> datetime:
    """Get current UTC time (timezone-aware)."""
    return datetime.now(timezone.utc)


class EntityType(str, Enum):
    """Entity types for Knowledge Graph"""

    PERSON = "person"
    TECH = "tech"
    PROJECT = "project"
    CONCEPT = "concept"
    COMPANY = "company"
    TOPIC = "topic"
    PROCEDURE = "procedure"
    PREFERENCE = "preference"


class RelationType(str, Enum):
    """Relationship types for Knowledge Graph"""

    # Personal
    LIKES = "likes"
    DISLIKES = "dislikes"
    PREFERS = "prefers"
    USES = "uses"
    KNOWS = "knows"
    WORKS_AT = "works_at"
    WORKS_ON = "works_on"

    # Knowledge
    IS_A = "is_a"
    HAS_A = "has_a"
    PART_OF = "part_of"
    RELATED_TO = "related_to"
    DEPENDS_ON = "depends_on"
    SUPERSEDES = "supersedes"

    # Temporal
    VALID_FROM = "valid_from"
    VALID_UNTIL = "valid_until"

    # Procedural
    TRIGGERS = "triggers"
    FOLLOWS = "follows"
    REQUIRES = "requires"


class SynapseNode(BaseModel):
    """Base node in the Knowledge Graph"""

    id: str = Field(..., description="Unique node identifier")
    type: EntityType = Field(..., description="Entity type")
    name: str = Field(..., description="Entity name")
    summary: Optional[str] = Field(None, description="Evolving summary")

    # Identity hierarchy: user → agent → chat → session
    user_id: Optional[str] = Field(None, description="User identifier")
    agent_id: Optional[str] = Field(None, description="Agent identifier for multi-agent")
    chat_id: Optional[str] = Field(None, description="Chat/conversation identifier")

    # Memory layer
    memory_layer: MemoryLayer = Field(
        MemoryLayer.SEMANTIC, description="Which memory layer"
    )

    # Scoring
    confidence: float = Field(0.7, ge=0.0, le=1.0, description="Confidence score")
    decay_score: float = Field(1.0, ge=0.0, le=1.0, description="Decay score")
    access_count: int = Field(0, ge=0, description="Access count")

    # Timestamps (timezone-aware UTC)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    expires_at: Optional[datetime] = Field(None, description="TTL expiration")

    # Provenance
    source_episode: Optional[str] = Field(None, description="Source episode ID")
    created_by: str = Field("synapse", description="Who created this node")

    class Config:
        use_enum_values = True


class SynapseEdge(BaseModel):
    """Edge with temporal properties"""

    id: str = Field(..., description="Unique edge identifier")
    source_id: str = Field(..., description="Source node ID")
    target_id: str = Field(..., description="Target node ID")
    type: RelationType = Field(..., description="Relationship type")

    # Temporal validity
    valid_at: datetime = Field(
        default_factory=utcnow, description="When it became true"
    )
    invalid_at: Optional[datetime] = Field(
        None, description="When it became false (null = still true)"
    )

    # Scoring
    confidence: float = Field(0.7, ge=0.0, le=1.0)

    # Provenance
    source_episode: Optional[str] = Field(None)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        use_enum_values = True


class SynapseEpisode(BaseModel):
    """Episode (provenance) - raw data that produced knowledge"""

    id: str = Field(..., description="Episode ID")
    content: str = Field(..., description="Raw content")
    summary: Optional[str] = Field(None, description="LLM-generated summary")

    # Classification
    topics: List[str] = Field(default_factory=list)
    outcome: str = Field("unknown", description="success | partial | failed | unknown")

    # Memory layer
    memory_layer: MemoryLayer = Field(MemoryLayer.EPISODIC)

    # Timestamps
    recorded_at: datetime = Field(default_factory=utcnow)
    expires_at: Optional[datetime] = Field(None, description="TTL expiration")

    # Identity hierarchy: user → agent → chat → session
    user_id: Optional[str] = Field(None, description="User identifier")
    agent_id: Optional[str] = Field(None, description="Agent identifier")
    chat_id: Optional[str] = Field(None, description="Chat/conversation identifier")
    session_id: Optional[str] = Field(None, description="Session identifier")


class UserModel(BaseModel):
    """User Model (Layer 1) - User preferences and expertise

    Identity Hierarchy:
    - user_id: Required, identifies the human user
    - agent_id: Optional, identifies which AI agent (for multi-agent)
    - chat_id: Optional, identifies the conversation thread

    Lookup uses composite key: user_id[:agent_id][:chat_id]
    Fallback chain: specific → agent-level → user-level
    """

    # Identity hierarchy: user → agent → chat
    user_id: str = Field(..., description="User identifier")
    agent_id: Optional[str] = Field(None, description="Agent identifier for multi-agent support")
    chat_id: Optional[str] = Field(None, description="Chat/conversation identifier")

    # Preferences
    language: str = Field("th", description="Preferred language")
    response_style: str = Field("casual", description="formal | casual | auto")
    response_length: str = Field("auto", description="concise | detailed | auto")
    timezone: str = Field("Asia/Bangkok")

    # Expertise levels
    expertise: Dict[str, str] = Field(
        default_factory=dict,
        description="Topic -> level (novice | intermediate | advanced | expert)",
    )

    # Common topics
    common_topics: List[str] = Field(default_factory=list)

    # Notes
    notes: List[str] = Field(default_factory=list, description="Free-form notes")

    # Timestamps
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    def get_composite_key(self) -> str:
        """Get composite key for storage lookup."""
        parts = [self.user_id]
        if self.agent_id:
            parts.append(self.agent_id)
            if self.chat_id:
                parts.append(self.chat_id)
        return ":".join(parts)


class ProceduralMemory(BaseModel):
    """Procedural Memory (Layer 2) - How-to patterns"""

    id: str = Field(..., description="Procedure ID")
    trigger: str = Field(..., description="When to activate")
    procedure: List[str] = Field(..., description="Steps to execute")

    # Source tracking
    source: str = Field(
        "explicit", description="explicit | correction | repeated_pattern"
    )

    # Success tracking
    success_count: int = Field(0, ge=0)
    last_used: Optional[datetime] = None

    # Topics
    topics: List[str] = Field(default_factory=list)


class SearchResult(BaseModel):
    """Search result from hybrid retrieval"""

    node: SynapseNode
    score: float = Field(..., ge=0.0, le=1.0)
    source: str = Field(..., description="vector | fts | graph | hybrid")

    # For graph results
    path: Optional[List[str]] = Field(None, description="Graph path if applicable")
    temporal: Optional[Dict[str, Any]] = Field(None, description="Temporal info")
