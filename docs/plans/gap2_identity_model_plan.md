# 🔷 Neo's Implementation Plan — Gap 2: Identity Model

> **Created**: 2026-03-17T10:05+07:00
> **Architect**: Neo
> **Priority**: P0 Critical
> **Estimated Time**: 4-6 hours

---

## 📋 Problem Statement

### Current State

```python
# synapse/layers/types.py

class UserModel(BaseModel):
    user_id: str
    # Missing: agent_id, chat_id
    language: str = "th"
    ...

class SynapseEpisode(BaseModel):
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    # Missing: agent_id, chat_id
```

### Impact

- **Cannot distinguish between multiple AI agents** serving same user
- **Cannot track conversation history** across sessions
- **Cannot isolate context** per chat/conversation
- **Blocks multi-agent scenarios**

---

## 🎯 Solution: Identity Hierarchy

```
user_id → agent_id → chat_id → session_id
   │         │          │          │
   │         │          │          └── Working memory (L5)
   │         │          └───────────── Episodic memory (L4)
   │         └──────────────────────── Agent isolation
   └────────────────────────────────── User preferences (L1)
```

### Hierarchy Rules

1. `user_id` - Required, identifies the human user
2. `agent_id` - Optional, identifies which AI agent (for multi-agent)
3. `chat_id` - Optional, identifies the conversation thread
4. `session_id` - Optional, identifies the current session

---

## 📝 Implementation Plan

### Phase 1: Update Types (1-2h)

#### 1.1 Update UserModel

**File**: `synapse/layers/types.py`

```python
class UserModel(BaseModel):
    """User Model (Layer 1) - User preferences and expertise"""

    # Identity hierarchy: user → agent → chat → session
    user_id: str = Field(..., description="User identifier")
    agent_id: Optional[str] = Field(None, description="Agent identifier for multi-agent support")
    chat_id: Optional[str] = Field(None, description="Chat/conversation identifier")

    # Preferences (unchanged)
    language: str = Field("th", description="Preferred language")
    response_style: str = Field("casual", description="formal | casual | auto")
    response_length: str = Field("auto", description="concise | detailed | auto")
    timezone: str = Field("Asia/Bangkok")

    # Expertise levels (unchanged)
    expertise: Dict[str, str] = Field(default_factory=dict)

    # Common topics (unchanged)
    common_topics: List[str] = Field(default_factory=list)

    # Notes (unchanged)
    notes: List[str] = Field(default_factory=list)

    # Timestamps
    updated_at: datetime = Field(default_factory=utcnow)
```

#### 1.2 Update SynapseEpisode

**File**: `synapse/layers/types.py`

```python
class SynapseEpisode(BaseModel):
    """Episode (provenance) - raw data that produced knowledge"""

    id: str = Field(..., description="Episode ID")
    content: str = Field(..., description="Raw content")
    summary: Optional[str] = Field(None)
    topics: List[str] = Field(default_factory=list)
    outcome: str = Field("unknown")
    memory_layer: MemoryLayer = Field(MemoryLayer.EPISODIC)

    # Identity hierarchy (UPDATED)
    user_id: Optional[str] = Field(None)
    agent_id: Optional[str] = Field(None)  # NEW
    chat_id: Optional[str] = Field(None)   # NEW
    session_id: Optional[str] = Field(None)

    recorded_at: datetime = Field(default_factory=utcnow)
    expires_at: Optional[datetime] = Field(None)
```

#### 1.3 Update SynapseNode

**File**: `synapse/layers/types.py`

```python
class SynapseNode(BaseModel):
    """Base node in the Knowledge Graph"""

    id: str = Field(..., description="Unique node identifier")
    type: EntityType = Field(..., description="Entity type")
    name: str = Field(..., description="Entity name")
    summary: Optional[str] = Field(None)

    # Identity context (NEW)
    user_id: Optional[str] = Field(None)
    agent_id: Optional[str] = Field(None)
    chat_id: Optional[str] = Field(None)

    # Memory layer
    memory_layer: MemoryLayer = Field(MemoryLayer.SEMANTIC)

    # Scoring (unchanged)
    confidence: float = Field(0.7, ge=0.0, le=1.0)
    decay_score: float = Field(1.0, ge=0.0, le=1.0)
    access_count: int = Field(0, ge=0)

    # Timestamps
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    expires_at: Optional[datetime] = Field(None)

    # Provenance
    source_episode: Optional[str] = Field(None)
    created_by: str = Field("synapse")
```

---

### Phase 2: Update Services (1-2h)

#### 2.1 Update SynapseService Constructor

**File**: `synapse/services/synapse_service.py`

```python
class SynapseService:
    def __init__(
        self,
        graphiti_client: Any,
        layer_manager: Optional[LayerManager] = None,
        user_id: str = "default",
        agent_id: Optional[str] = None,  # NEW
        chat_id: Optional[str] = None,   # NEW
    ):
        self.graphiti = graphiti_client
        self.layers = layer_manager or LayerManager()
        self.user_id = user_id
        self.agent_id = agent_id  # NEW
        self.chat_id = chat_id    # NEW

    def set_identity(
        self,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        chat_id: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        Update identity context for subsequent operations.

        Args:
            user_id: User identifier
            agent_id: Agent identifier
            chat_id: Chat/conversation identifier

        Returns:
            Current identity context
        """
        if user_id:
            self.user_id = user_id
        if agent_id is not None:
            self.agent_id = agent_id
        if chat_id is not None:
            self.chat_id = chat_id

        return self.get_identity()

    def get_identity(self) -> Dict[str, Optional[str]]:
        """Get current identity context."""
        return {
            "user_id": self.user_id,
            "agent_id": self.agent_id,
            "chat_id": self.chat_id,
        }

    def get_full_user_key(self) -> str:
        """
        Get composite key for user model lookup.

        Format: user_id[:agent_id[:chat_id]]
        """
        parts = [self.user_id]
        if self.agent_id:
            parts.append(self.agent_id)
            if self.chat_id:
                parts.append(self.chat_id)
        return ":".join(parts)
```

#### 2.2 Update Episode Recording

**File**: `synapse/services/synapse_service.py`

```python
def record_episode(
    self,
    content: str,
    summary: Optional[str] = None,
    topics: Optional[List[str]] = None,
    outcome: str = "unknown",
) -> SynapseEpisode:
    """
    Record an episode with current identity context.
    """
    return self.layers.record_episode(
        content=content,
        summary=summary,
        topics=topics,
        outcome=outcome,
        user_id=self.user_id,
        agent_id=self.agent_id,  # NEW
        chat_id=self.chat_id,    # NEW
    )
```

---

### Phase 3: Update Layer Managers (1-2h)

#### 3.1 Update EpisodicManager

**File**: `synapse/layers/episodic.py`

```python
def record_episode(
    self,
    content: str,
    summary: Optional[str] = None,
    topics: Optional[List[str]] = None,
    outcome: str = "unknown",
    user_id: Optional[str] = None,
    agent_id: Optional[str] = None,  # NEW
    chat_id: Optional[str] = None,   # NEW
) -> SynapseEpisode:
    """Record an episode with identity context."""
    ...
```

#### 3.2 Update UserModelManager

**File**: `synapse/layers/user_model.py`

```python
def get_user_model(
    self,
    user_id: str,
    agent_id: Optional[str] = None,  # NEW
    chat_id: Optional[str] = None,   # NEW
) -> UserModel:
    """
    Get user model with optional agent/chat context.

    Lookup order:
    1. user_id:agent_id:chat_id (most specific)
    2. user_id:agent_id
    3. user_id (fallback)
    """
    # Try most specific first
    if agent_id and chat_id:
        key = f"{user_id}:{agent_id}:{chat_id}"
        if key in self._users:
            return self._users[key]

    if agent_id:
        key = f"{user_id}:{agent_id}"
        if key in self._users:
            return self._users[key]

    # Fallback to base user
    return self._users.get(user_id, self._create_default(user_id))
```

---

### Phase 4: Add MCP Tools (1h)

#### 4.1 set_identity MCP Tool

**File**: `synapse/mcp_server/src/graphiti_mcp_server.py`

```python
@mcp.tool()
async def set_identity(
    user_id: str | None = None,
    agent_id: str | None = None,
    chat_id: str | None = None,
) -> dict[str, Any] | ErrorResponse:
    """Set identity context for memory operations.

    The identity hierarchy determines memory isolation:
    - user_id: User-level preferences (persists across agents/chats)
    - agent_id: Agent-specific context (shared across chats)
    - chat_id: Chat-specific context (isolated per conversation)

    Args:
        user_id: User identifier (required for first call)
        agent_id: Agent identifier (optional, for multi-agent)
        chat_id: Chat/conversation identifier (optional)

    Returns:
        Current identity context

    Example:
        # Set user context
        await set_identity(user_id="user123")

        # Add agent context for multi-agent
        await set_identity(agent_id="claude")

        # Add chat context for conversation isolation
        await set_identity(chat_id="chat_abc123")
    """
    global synapse_service

    if synapse_service is None:
        return ErrorResponse(error='SynapseService not initialized')

    try:
        result = synapse_service.set_identity(
            user_id=user_id,
            agent_id=agent_id,
            chat_id=chat_id,
        )

        return {
            "message": "Identity context updated",
            "identity": result,
        }
    except Exception as e:
        return ErrorResponse(error=f'Error setting identity: {e}')


@mcp.tool()
async def get_identity() -> dict[str, Any] | ErrorResponse:
    """Get current identity context.

    Returns:
        Current user_id, agent_id, chat_id
    """
    global synapse_service

    if synapse_service is None:
        return ErrorResponse(error='SynapseService not initialized')

    try:
        result = synapse_service.get_identity()

        return {
            "message": "Current identity context",
            "identity": result,
        }
    except Exception as e:
        return ErrorResponse(error=f'Error getting identity: {e}')
```

---

## 🧪 Test Plan

### Test File: `tests/test_identity_model.py`

```python
"""
Tests for Gap 2: Identity Model - Real Logic (No Mocks)
"""

import pytest
from synapse.layers import UserModel, SynapseEpisode, SynapseNode
from synapse.layers.user_model import UserModelManager
from synapse.layers.episodic import EpisodicManager
from synapse.services.synapse_service import SynapseService


class TestIdentityHierarchy:
    """Tests for identity hierarchy."""

    def test_user_model_accepts_agent_id(self):
        """UserModel should accept optional agent_id."""
        user = UserModel(
            user_id="user123",
            agent_id="claude",
        )
        assert user.user_id == "user123"
        assert user.agent_id == "claude"

    def test_user_model_accepts_chat_id(self):
        """UserModel should accept optional chat_id."""
        user = UserModel(
            user_id="user123",
            agent_id="claude",
            chat_id="chat_abc",
        )
        assert user.chat_id == "chat_abc"

    def test_episode_stores_identity(self):
        """SynapseEpisode should store full identity."""
        episode = SynapseEpisode(
            id="ep1",
            content="Test content",
            user_id="user123",
            agent_id="claude",
            chat_id="chat_abc",
        )
        assert episode.user_id == "user123"
        assert episode.agent_id == "claude"
        assert episode.chat_id == "chat_abc"

    def test_node_stores_identity(self):
        """SynapseNode should store identity for isolation."""
        node = SynapseNode(
            id="node1",
            name="Test Node",
            type="concept",
            user_id="user123",
            agent_id="claude",
        )
        assert node.user_id == "user123"
        assert node.agent_id == "claude"


class TestSynapseServiceIdentity:
    """Tests for SynapseService identity methods."""

    def test_set_identity_updates_user_id(self, synapse_service):
        """set_identity should update user_id."""
        result = synapse_service.set_identity(user_id="new_user")

        assert result["user_id"] == "new_user"

    def test_set_identity_updates_agent_id(self, synapse_service):
        """set_identity should update agent_id."""
        result = synapse_service.set_identity(agent_id="gpt4")

        assert result["agent_id"] == "gpt4"

    def test_set_identity_updates_chat_id(self, synapse_service):
        """set_identity should update chat_id."""
        result = synapse_service.set_identity(chat_id="chat_xyz")

        assert result["chat_id"] == "chat_xyz"

    def test_get_identity_returns_all(self, synapse_service):
        """get_identity should return all identity fields."""
        synapse_service.set_identity(
            user_id="user1",
            agent_id="agent1",
            chat_id="chat1",
        )

        result = synapse_service.get_identity()

        assert result["user_id"] == "user1"
        assert result["agent_id"] == "agent1"
        assert result["chat_id"] == "chat1"

    def test_get_full_user_key_composite(self, synapse_service):
        """get_full_user_key should return composite key."""
        synapse_service.set_identity(
            user_id="user1",
            agent_id="agent1",
            chat_id="chat1",
        )

        result = synapse_service.get_full_user_key()

        assert result == "user1:agent1:chat1"

    def test_get_full_user_key_partial(self, synapse_service):
        """get_full_user_key should work with partial identity."""
        synapse_service.set_identity(
            user_id="user1",
            agent_id="agent1",
        )

        result = synapse_service.get_full_user_key()

        assert result == "user1:agent1"

    def test_get_full_user_key_user_only(self, synapse_service):
        """get_full_user_key should work with user_id only."""
        synapse_service.set_identity(user_id="user1")

        result = synapse_service.get_full_user_key()

        assert result == "user1"


class TestUserModelManagerIdentity:
    """Tests for UserModelManager with identity."""

    def test_get_user_model_fallback_to_base(self, user_model_manager):
        """Should fallback to base user if agent-specific not found."""
        # Create base user
        base = user_model_manager.update_user_model(
            "user1",
            language="th",
        )

        # Request agent-specific (should fallback)
        result = user_model_manager.get_user_model(
            "user1",
            agent_id="claude",
        )

        # Should get base user
        assert result.user_id == "user1"
        assert result.language == "th"

    def test_agent_specific_preferences(self, user_model_manager):
        """Should support agent-specific preferences."""
        # Create agent-specific user model
        user_model_manager.update_user_model(
            "user1:claude",
            language="en",
            response_style="formal",
        )

        # Get agent-specific
        result = user_model_manager.get_user_model(
            "user1",
            agent_id="claude",
        )

        assert result.language == "en"
        assert result.response_style == "formal"


class TestIdentityIsolation:
    """Tests for identity-based isolation."""

    def test_different_agents_different_context(self, synapse_service):
        """Different agents should have isolated contexts."""
        # Agent 1
        synapse_service.set_identity(user_id="user1", agent_id="claude")
        synapse_service.update_user_preferences(add_note="For Claude")

        # Agent 2
        synapse_service.set_identity(user_id="user1", agent_id="gpt")
        synapse_service.update_user_preferences(add_note="For GPT")

        # Check Claude's context
        synapse_service.set_identity(user_id="user1", agent_id="claude")
        ctx1 = synapse_service.get_user_context()

        # Check GPT's context
        synapse_service.set_identity(user_id="user1", agent_id="gpt")
        ctx2 = synapse_service.get_user_context()

        # Should be different
        assert ctx1["notes"] != ctx2["notes"]

    def test_chat_isolation(self, synapse_service):
        """Different chats should have isolated working memory."""
        # Chat 1
        synapse_service.set_identity(user_id="user1", chat_id="chat1")
        synapse_service.set_working_context("topic", "python")

        # Chat 2
        synapse_service.set_identity(user_id="user1", chat_id="chat2")
        synapse_service.set_working_context("topic", "javascript")

        # Check chat1
        synapse_service.set_identity(user_id="user1", chat_id="chat1")
        assert synapse_service.get_working_context("topic") == "python"

        # Check chat2
        synapse_service.set_identity(user_id="user1", chat_id="chat2")
        assert synapse_service.get_working_context("topic") == "javascript"
```

---

## 📊 Effort Estimate

| Phase | Tasks | Time |
|-------|-------|------|
| Phase 1: Types | Update 3 models | 1-2h |
| Phase 2: Services | Add methods to SynapseService | 1-2h |
| Phase 3: Managers | Update managers | 1h |
| Phase 4: MCP Tools | Add 2 tools | 1h |
| Testing | Write 15+ tests | 1h |
| **Total** | | **4-6h** |

---

## ✅ Acceptance Criteria

### Per Component

- [ ] `UserModel` has `agent_id`, `chat_id` fields
- [ ] `SynapseEpisode` has `agent_id`, `chat_id` fields
- [ ] `SynapseNode` has `agent_id`, `chat_id` fields
- [ ] `SynapseService.set_identity()` works
- [ ] `SynapseService.get_identity()` works
- [ ] `SynapseService.get_full_user_key()` returns composite key

### Tests

- [ ] All 15+ tests passing
- [ ] 0% mock usage
- [ ] Identity isolation verified

### Backward Compatibility

- [ ] Existing code works without agent_id/chat_id
- [ ] Default behavior unchanged
- [ ] No breaking changes to API

---

## 📁 Files to Modify

```
synapse/
├── layers/
│   ├── types.py              +15 lines (3 models)
│   ├── user_model.py         +30 lines (lookup logic)
│   └── episodic.py           +10 lines (identity params)
├── services/
│   └── synapse_service.py    +40 lines (identity methods)
├── mcp_server/src/
│   └── graphiti_mcp_server.py  +80 lines (2 MCP tools)
└── tests/
    └── test_identity_model.py   +200 lines (15+ tests) [NEW]
```

---

## 🎯 Ready to Implement?

This plan is **approved for implementation** when you're ready.

---

*Neo — Architecting the future of memory.*
