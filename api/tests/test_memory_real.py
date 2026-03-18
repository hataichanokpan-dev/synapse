"""
Real integration tests for Memory API - NO MOCK.

Tests the full chain: API → SynapseService → LayerManager → SQLite
"""

import pytest
import asyncio
from datetime import datetime

# Test configuration
TEST_DB_PATH = "/tmp/synapse_test_episodic.db"
TEST_PROCEDURAL_DB_PATH = "/tmp/synapse_test_procedural.db"


@pytest.fixture
async def real_service():
    """Create a real SynapseService with test databases."""
    import os
    import sys
    from pathlib import Path

    # Add parent to path
    parent = Path(__file__).parent.parent.parent
    if str(parent) not in sys.path:
        sys.path.insert(0, str(parent))

    from synapse.layers import LayerManager
    from synapse.layers.episodic import EpisodicManager
    from synapse.layers.procedural import ProceduralManager
    from synapse.services.synapse_service import SynapseService

    # Create managers with test databases
    episodic = EpisodicManager(db_path=Path(TEST_DB_PATH))
    procedural = ProceduralManager(db_path=Path(TEST_PROCEDURAL_DB_PATH))

    # Create layer manager
    layers = LayerManager(
        episodic_manager=episodic,
        procedural_manager=procedural,
    )

    # Create service (no graphiti for this test)
    service = SynapseService(
        graphiti_client=None,
        layer_manager=layers,
        user_id="test_user",
    )

    yield service

    # Cleanup
    os.remove(TEST_DB_PATH)
    os.remove(TEST_PROCEDURAL_DB_PATH)


class TestMemoryListReal:
    """Real tests for list_memories - NO MOCK."""

    @pytest.mark.asyncio
    async def test_list_memories_empty(self, real_service):
        """Test listing memories when empty."""
        result = await real_service.list_memories()

        assert result is not None
        assert "items" in result
        assert "total" in result
        assert result["items"] == []
        assert result["total"] == 0

    @pytest.mark.asyncio
    async def test_list_memories_with_episode(self, real_service):
        """Test listing memories after adding an episode."""
        # Add an episode directly
        episode = real_service.layers.episodic.record_episode(
            content="Test episode content",
            summary="Test summary",
            topics=["test"],
            outcome="success",
            user_id="test_user",
        )

        # List memories
        result = await real_service.list_memories()

        assert result["total"] >= 1
        assert len(result["items"]) >= 1

        # Find our episode
        found = False
        for item in result["items"]:
            if item["uuid"] == episode.id:
                found = True
                assert item["layer"] == "EPISODIC"
                assert "Test" in item["name"] or "Test" in item["content"]
                break

        assert found, f"Episode {episode.id} not found in results"

    @pytest.mark.asyncio
    async def test_list_memories_with_procedure(self, real_service):
        """Test listing memories after adding a procedure."""
        # Add a procedure directly
        procedure = real_service.layers.procedural.learn_procedure(
            trigger="test trigger",
            procedure=["step 1", "step 2"],
            source="test",
            topics=["testing"],
        )

        # List memories
        result = await real_service.list_memories(layer="procedural")

        assert result["total"] >= 1
        assert len(result["items"]) >= 1

        # Find our procedure
        found = False
        for item in result["items"]:
            if item["uuid"] == procedure.id:
                found = True
                assert item["layer"] == "PROCEDURAL"
                assert item["name"] == "test trigger"
                break

        assert found, f"Procedure {procedure.id} not found in results"

    @pytest.mark.asyncio
    async def test_list_memories_pagination(self, real_service):
        """Test pagination works correctly."""
        # Add multiple episodes
        for i in range(5):
            real_service.layers.episodic.record_episode(
                content=f"Episode {i}",
                summary=f"Summary {i}",
                user_id="test_user",
            )

        # Get first page
        page1 = await real_service.list_memories(limit=2, offset=0)
        assert len(page1["items"]) == 2

        # Get second page
        page2 = await real_service.list_memories(limit=2, offset=2)
        assert len(page2["items"]) == 2

        # Pages should be different
        page1_ids = {item["uuid"] for item in page1["items"]}
        page2_ids = {item["uuid"] for item in page2["items"]}
        assert page1_ids.isdisjoint(page2_ids), "Pages should not overlap"

    @pytest.mark.asyncio
    async def test_list_memories_filter_by_layer(self, real_service):
        """Test filtering by layer."""
        # Add episode and procedure
        episode = real_service.layers.episodic.record_episode(
            content="Test episode",
            user_id="test_user",
        )
        procedure = real_service.layers.procedural.learn_procedure(
            trigger="test proc",
            procedure=["step 1"],
        )

        # Filter by episodic
        result = await real_service.list_memories(layer="episodic")
        for item in result["items"]:
            assert item["layer"] == "EPISODIC"

        # Filter by procedural
        result = await real_service.list_memories(layer="procedural")
        for item in result["items"]:
            assert item["layer"] == "PROCEDURAL"


class TestMemoryGetByIdReal:
    """Real tests for get_memory_by_id - NO MOCK."""

    @pytest.mark.asyncio
    async def test_get_memory_by_id_episode(self, real_service):
        """Test getting an episode by ID."""
        # Add episode
        episode = real_service.layers.episodic.record_episode(
            content="Test content for get",
            summary="Test summary for get",
            topics=["get_test"],
            user_id="test_user",
        )

        # Get by ID
        result = await real_service.get_memory_by_id(episode.id)

        assert result is not None
        assert result["uuid"] == episode.id
        assert result["layer"] == "EPISODIC"
        assert "Test content" in result["content"]

    @pytest.mark.asyncio
    async def test_get_memory_by_id_procedure(self, real_service):
        """Test getting a procedure by ID."""
        # Add procedure
        procedure = real_service.layers.procedural.learn_procedure(
            trigger="get test trigger",
            procedure=["step 1", "step 2"],
        )

        # Get by ID
        result = await real_service.get_memory_by_id(procedure.id)

        assert result is not None
        assert result["uuid"] == procedure.id
        assert result["layer"] == "PROCEDURAL"
        assert "step 1" in result["content"]

    @pytest.mark.asyncio
    async def test_get_memory_by_id_not_found(self, real_service):
        """Test getting a non-existent memory."""
        result = await real_service.get_memory_by_id("nonexistent-uuid-12345")
        assert result is None


class TestMemoryDeleteReal:
    """Real tests for delete_memory - NO MOCK."""

    @pytest.mark.asyncio
    async def test_delete_episode(self, real_service):
        """Test deleting an episode."""
        # Add episode
        episode = real_service.layers.episodic.record_episode(
            content="To be deleted",
            user_id="test_user",
        )

        # Verify it exists
        result = await real_service.get_memory_by_id(episode.id)
        assert result is not None

        # Delete it
        delete_result = await real_service.delete_memory(episode.id)
        assert "deleted" in delete_result["message"].lower()

        # Verify it's gone
        result = await real_service.get_memory_by_id(episode.id)
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_procedure(self, real_service):
        """Test deleting a procedure."""
        # Add procedure
        procedure = real_service.layers.procedural.learn_procedure(
            trigger="delete test trigger",
            procedure=["step 1"],
        )

        # Verify it exists
        result = await real_service.get_memory_by_id(procedure.id)
        assert result is not None

        # Delete it
        delete_result = await real_service.delete_memory(procedure.id)
        assert "deleted" in delete_result["message"].lower()

        # Verify it's gone
        result = await real_service.get_memory_by_id(procedure.id)
        assert result is None


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
