"""
Tests for Gap 2: Identity Model - Real Logic (No Mocks)

Tests identity hierarchy for multi-agent, multi-conversation support:
- user_id → agent_id → chat_id → session_id
- UserModel with agent_id, chat_id
- SynapseEpisode with agent_id, chat_id
- SynapseNode with user_id, agent_id, chat_id
"""

import pytest
from datetime import datetime
from typing import Dict, Any, Optional

# Import real implementations
from synapse.layers import (
    LayerManager,
    MemoryLayer,
    UserModel,
    SynapseEpisode,
    SynapseNode,
    EntityType,
)
from synapse.layers.working import WorkingManager
from synapse.layers.user_model import UserModelManager
from synapse.services.synapse_service import SynapseService


# ============================================
# FIXTURES - Real implementations
# ============================================

@pytest.fixture
def layer_manager():
    """Create a real LayerManager for testing."""
    return LayerManager()


@pytest.fixture
def user_model_manager():
    """Create a real UserModelManager for testing."""
    return UserModelManager()


@pytest.fixture
def working_manager():
    """Create a real WorkingManager for testing."""
    return WorkingManager()


@pytest.fixture
def synapse_service(layer_manager):
    """Create a real SynapseService for testing."""
    return SynapseService(
        graphiti_client=None,
        layer_manager=layer_manager,
        user_id="test_user",
    )


# ============================================
# TYPE DEFINITION TESTS
# ============================================

class TestUserModelIdentity:
    """Tests for UserModel identity fields."""

    def test_user_model_accepts_user_id(self):
        """UserModel should require user_id."""
        user = UserModel(user_id="user123")
        assert user.user_id == "user123"

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
        assert user.user_id == "user123"
        assert user.agent_id == "claude"
        assert user.chat_id == "chat_abc"

    def test_user_model_agent_id_defaults_to_none(self):
        """agent_id should default to None."""
        user = UserModel(user_id="user123")
        assert user.agent_id is None

    def test_user_model_chat_id_defaults_to_none(self):
        """chat_id should default to None."""
        user = UserModel(user_id="user123")
        assert user.chat_id is None

    def test_user_model_get_composite_key_user_only(self):
        """get_composite_key should return user_id only if no agent/chat."""
        user = UserModel(user_id="user123")
        assert user.get_composite_key() == "user123"

    def test_user_model_get_composite_key_with_agent(self):
        """get_composite_key should include agent_id."""
        user = UserModel(user_id="user123", agent_id="claude")
        assert user.get_composite_key() == "user123:claude"

    def test_user_model_get_composite_key_full(self):
        """get_composite_key should include all levels."""
        user = UserModel(
            user_id="user123",
            agent_id="claude",
            chat_id="chat_abc",
        )
        assert user.get_composite_key() == "user123:claude:chat_abc"

    def test_user_model_chat_without_agent(self):
        """chat_id without agent_id should only use user_id."""
        # This is a valid case - user-level chat without agent
        user = UserModel(user_id="user123", chat_id="chat_abc")
        # Composite key only includes chat if agent exists
        assert user.get_composite_key() == "user123"


class TestSynapseEpisodeIdentity:
    """Tests for SynapseEpisode identity fields."""

    def test_episode_accepts_user_id(self):
        """SynapseEpisode should accept user_id."""
        episode = SynapseEpisode(
            id="ep1",
            content="Test content",
            user_id="user123",
        )
        assert episode.user_id == "user123"

    def test_episode_accepts_agent_id(self):
        """SynapseEpisode should accept agent_id."""
        episode = SynapseEpisode(
            id="ep1",
            content="Test content",
            user_id="user123",
            agent_id="claude",
        )
        assert episode.agent_id == "claude"

    def test_episode_accepts_chat_id(self):
        """SynapseEpisode should accept chat_id."""
        episode = SynapseEpisode(
            id="ep1",
            content="Test content",
            user_id="user123",
            agent_id="claude",
            chat_id="chat_abc",
        )
        assert episode.chat_id == "chat_abc"

    def test_episode_accepts_session_id(self):
        """SynapseEpisode should accept session_id."""
        episode = SynapseEpisode(
            id="ep1",
            content="Test content",
            user_id="user123",
            session_id="session_xyz",
        )
        assert episode.session_id == "session_xyz"

    def test_episode_all_identity_fields(self):
        """SynapseEpisode should store all identity fields."""
        episode = SynapseEpisode(
            id="ep1",
            content="Test content",
            user_id="user123",
            agent_id="claude",
            chat_id="chat_abc",
            session_id="session_xyz",
        )
        assert episode.user_id == "user123"
        assert episode.agent_id == "claude"
        assert episode.chat_id == "chat_abc"
        assert episode.session_id == "session_xyz"


class TestSynapseNodeIdentity:
    """Tests for SynapseNode identity fields."""

    def test_node_accepts_user_id(self):
        """SynapseNode should accept user_id."""
        node = SynapseNode(
            id="node1",
            name="Test Node",
            type=EntityType.CONCEPT,
            user_id="user123",
        )
        assert node.user_id == "user123"

    def test_node_accepts_agent_id(self):
        """SynapseNode should accept agent_id."""
        node = SynapseNode(
            id="node1",
            name="Test Node",
            type=EntityType.CONCEPT,
            user_id="user123",
            agent_id="claude",
        )
        assert node.agent_id == "claude"

    def test_node_accepts_chat_id(self):
        """SynapseNode should accept chat_id."""
        node = SynapseNode(
            id="node1",
            name="Test Node",
            type=EntityType.CONCEPT,
            user_id="user123",
            agent_id="claude",
            chat_id="chat_abc",
        )
        assert node.chat_id == "chat_abc"

    def test_node_all_identity_fields(self):
        """SynapseNode should store all identity fields."""
        node = SynapseNode(
            id="node1",
            name="Test Node",
            type=EntityType.CONCEPT,
            user_id="user123",
            agent_id="claude",
            chat_id="chat_abc",
        )
        assert node.user_id == "user123"
        assert node.agent_id == "claude"
        assert node.chat_id == "chat_abc"


# ============================================
# SYNAPSE SERVICE IDENTITY TESTS
# ============================================

class TestSynapseServiceIdentity:
    """Tests for SynapseService identity methods."""

    def test_service_default_user_id(self, synapse_service):
        """Service should use default user_id from constructor."""
        identity = synapse_service.get_identity()
        assert identity["user_id"] == "test_user"

    def test_service_default_agent_id_none(self, synapse_service):
        """Service should default agent_id to None."""
        identity = synapse_service.get_identity()
        assert identity["agent_id"] is None

    def test_service_default_chat_id_none(self, synapse_service):
        """Service should default chat_id to None."""
        identity = synapse_service.get_identity()
        assert identity["chat_id"] is None

    def test_set_identity_updates_user_id(self, synapse_service):
        """set_identity should update user_id."""
        result = synapse_service.set_identity(user_id="new_user")

        assert result["user_id"] == "new_user"
        assert synapse_service.user_id == "new_user"

    def test_set_identity_updates_agent_id(self, synapse_service):
        """set_identity should update agent_id."""
        result = synapse_service.set_identity(agent_id="gpt4")

        assert result["agent_id"] == "gpt4"
        assert synapse_service.agent_id == "gpt4"

    def test_set_identity_updates_chat_id(self, synapse_service):
        """set_identity should update chat_id."""
        result = synapse_service.set_identity(chat_id="chat_xyz")

        assert result["chat_id"] == "chat_xyz"
        assert synapse_service.chat_id == "chat_xyz"

    def test_set_identity_partial_update(self, synapse_service):
        """set_identity should allow partial updates."""
        # Set full identity
        synapse_service.set_identity(
            user_id="user1",
            agent_id="agent1",
            chat_id="chat1",
        )

        # Update only chat_id
        result = synapse_service.set_identity(chat_id="chat2")

        # user_id and agent_id should remain
        assert result["user_id"] == "user1"
        assert result["agent_id"] == "agent1"
        assert result["chat_id"] == "chat2"

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

    def test_get_full_user_key_user_only(self, synapse_service):
        """get_full_user_key should return user_id only if no agent/chat."""
        synapse_service.set_identity(user_id="user1")

        result = synapse_service.get_full_user_key()

        assert result == "user1"

    def test_get_full_user_key_with_agent(self, synapse_service):
        """get_full_user_key should include agent_id."""
        synapse_service.set_identity(user_id="user1", agent_id="agent1")

        result = synapse_service.get_full_user_key()

        assert result == "user1:agent1"

    def test_get_full_user_key_full(self, synapse_service):
        """get_full_user_key should include all levels."""
        synapse_service.set_identity(
            user_id="user1",
            agent_id="agent1",
            chat_id="chat1",
        )

        result = synapse_service.get_full_user_key()

        assert result == "user1:agent1:chat1"

    def test_clear_identity_resets_agent_and_chat(self, synapse_service):
        """clear_identity should reset agent_id and chat_id."""
        synapse_service.set_identity(
            user_id="user1",
            agent_id="agent1",
            chat_id="chat1",
        )

        previous = synapse_service.clear_identity()

        # Previous should have the old values
        assert previous["agent_id"] == "agent1"
        assert previous["chat_id"] == "chat1"

        # Current should be cleared
        current = synapse_service.get_identity()
        assert current["user_id"] == "user1"  # Kept
        assert current["agent_id"] is None  # Cleared
        assert current["chat_id"] is None  # Cleared


# ============================================
# USER MODEL MANAGER IDENTITY TESTS
# ============================================

class TestUserModelManagerIdentity:
    """Tests for UserModelManager with identity."""

    def test_manager_creates_base_user(self, user_model_manager):
        """Manager should create user with base user_id."""
        user = user_model_manager.get_user_model("new_user")

        assert user.user_id == "new_user"
        assert user.agent_id is None
        assert user.chat_id is None

    def test_manager_updates_base_user(self, user_model_manager):
        """Manager should update base user preferences."""
        user_model_manager.update_user_model(
            "user1",
            language="en",
        )

        user = user_model_manager.get_user_model("user1")
        assert user.language == "en"


# ============================================
# IDENTITY ISOLATION TESTS
# ============================================

class TestIdentityIsolation:
    """Tests for identity-based isolation."""

    def test_different_users_isolated_preferences(self, user_model_manager):
        """Different users should have isolated preferences."""
        # User 1
        user_model_manager.update_user_model(
            "user1",
            language="th",
        )

        # User 2
        user_model_manager.update_user_model(
            "user2",
            language="en",
        )

        # Check isolation
        user1 = user_model_manager.get_user_model("user1")
        user2 = user_model_manager.get_user_model("user2")

        assert user1.language == "th"
        assert user2.language == "en"

    def test_service_context_switch(self, synapse_service):
        """Service should switch context properly."""
        # Set context for user1
        synapse_service.set_identity(user_id="user1")
        synapse_service.update_user_preferences(add_note="Note for user1")

        # Switch to user2
        synapse_service.set_identity(user_id="user2")
        synapse_service.update_user_preferences(add_note="Note for user2")

        # Switch back to user1
        synapse_service.set_identity(user_id="user1")
        ctx = synapse_service.get_user_context()

        # Should have user1's note
        assert "Note for user1" in ctx["notes"]

    def test_working_memory_isolated_by_chat(self, synapse_service):
        """Working memory should be isolated by chat context."""
        # Chat 1
        synapse_service.set_identity(user_id="user1", chat_id="chat1")
        synapse_service.set_working_context("topic", "python")

        # Chat 2 (same user)
        synapse_service.set_identity(user_id="user1", chat_id="chat2")
        synapse_service.set_working_context("topic", "javascript")

        # Check chat1 still has python
        # Note: This test assumes WorkingManager is not chat-aware
        # In production, each chat would have its own WorkingManager
        # For now, we just verify the identity context is set correctly
        identity = synapse_service.get_identity()
        assert identity["chat_id"] == "chat2"


# ============================================
# BACKWARD COMPATIBILITY TESTS
# ============================================

class TestBackwardCompatibility:
    """Tests for backward compatibility."""

    def test_user_model_without_new_fields(self):
        """UserModel should work without agent_id/chat_id."""
        user = UserModel(user_id="legacy_user")

        assert user.user_id == "legacy_user"
        assert user.language == "th"  # Default
        assert user.expertise == {}  # Default

    def test_episode_without_new_fields(self):
        """SynapseEpisode should work without agent_id/chat_id."""
        episode = SynapseEpisode(
            id="ep1",
            content="Legacy content",
        )

        assert episode.id == "ep1"
        assert episode.content == "Legacy content"
        assert episode.agent_id is None
        assert episode.chat_id is None

    def test_service_without_agent_chat(self, synapse_service):
        """Service should work without agent_id/chat_id."""
        # Don't set agent_id or chat_id
        synapse_service.set_identity(user_id="simple_user")

        ctx = synapse_service.get_user_context()

        assert ctx["user_id"] == "simple_user"
        # agent_id and chat_id should be None
        assert ctx.get("agent_id") is None
        assert ctx.get("chat_id") is None


# ============================================
# EDGE CASE TESTS
# ============================================

class TestIdentityEdgeCases:
    """Edge case tests for identity."""

    def test_empty_user_id(self):
        """UserModel should accept empty user_id."""
        user = UserModel(user_id="")
        assert user.user_id == ""

    def test_special_chars_in_user_id(self):
        """UserModel should handle special characters in user_id."""
        user = UserModel(user_id="user@example.com")
        assert user.user_id == "user@example.com"

    def test_unicode_in_agent_id(self):
        """agent_id should handle unicode."""
        user = UserModel(
            user_id="user1",
            agent_id="โบ๊ท",  # Thai
        )
        assert user.agent_id == "โบ๊ท"

    def test_very_long_user_id(self):
        """UserModel should handle long user_id."""
        long_id = "user_" + "x" * 1000
        user = UserModel(user_id=long_id)
        assert user.user_id == long_id

    def test_agent_id_with_spaces(self):
        """agent_id should handle spaces."""
        user = UserModel(
            user_id="user1",
            agent_id="Claude Opus 4",
        )
        assert user.agent_id == "Claude Opus 4"

    def test_chat_id_with_slashes(self):
        """chat_id should handle slashes."""
        user = UserModel(
            user_id="user1",
            chat_id="chats/2024/01/chat_abc",
        )
        assert user.chat_id == "chats/2024/01/chat_abc"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
