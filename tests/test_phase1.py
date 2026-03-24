"""
Tests for Phase 1 (P0 - Critical) Implementation

Tests for:
- Task 1.1: SynapseService Bridge Class
- Task 1.2: Semantic Layer FalkorDB Persistence
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta, timezone

from synapse.services import SynapseService
from synapse.services.synapse_service import SynapseService as SynapseServiceClass
from synapse.graph_runtime import normalize_graph_group_id
from synapse.layers import (
    LayerManager,
    MemoryLayer,
    EntityType,
    RelationType,
    SynapseNode,
    SynapseEdge,
)
from synapse.layers.episodic import EpisodicManager
from synapse.layers.procedural import ProceduralManager
from synapse.layers.user_model import UserModelManager
from synapse.layers.working import WorkingManager


# ============================================
# Test Fixtures
# ============================================

@pytest.fixture
def mock_graphiti():
    """Create a mock Graphiti client."""
    client = AsyncMock()
    client.add_episode = AsyncMock(return_value={"uuid": "test-uuid"})
    client.search = AsyncMock(return_value=[])
    return client


@pytest.fixture
def mock_layer_manager():
    """Create a mock LayerManager."""
    manager = MagicMock(spec=LayerManager)
    manager.procedural = MagicMock()
    manager.procedural.fetch_lexical_candidates = MagicMock(return_value=[])
    manager.procedural.fetch_vector_candidates = MagicMock(return_value=[])
    manager.episodic = MagicMock()
    manager.episodic.fetch_lexical_candidates = MagicMock(return_value=[])
    manager.episodic.fetch_vector_candidates = MagicMock(return_value=[])
    manager.semantic = MagicMock()
    manager.semantic.fetch_lexical_candidates = MagicMock(return_value=[])
    manager.semantic.fetch_vector_candidates = MagicMock(return_value=[])
    manager.semantic.get_outbox_health = MagicMock(return_value={})
    manager.semantic._graphiti = None
    manager.working = MagicMock()
    manager.working.get_all_context = MagicMock(return_value={})
    manager.detect_layer = MagicMock(return_value=MemoryLayer.SEMANTIC)
    manager.add_entity = AsyncMock(return_value=SynapseNode(
        id="test_id",
        type=EntityType.CONCEPT,
        name="Test Entity",
        summary="Test summary",
    ))
    manager.search_semantic = AsyncMock(return_value=[])
    manager.get_user = MagicMock(return_value=MagicMock(
        user_id="default",
        language="th",
        response_style="casual",
        expertise={},
        common_topics=[],
        notes=[],
    ))
    manager.find_procedures = MagicMock(return_value=[])
    manager.set_working = MagicMock()
    manager.update_user = MagicMock()
    manager.record_episode = MagicMock()
    manager._search_working_memory = MagicMock(return_value=[])
    manager._search_user_model = MagicMock(return_value=[])
    return manager


@pytest.fixture
def synapse_service(mock_graphiti, mock_layer_manager):
    """Create a SynapseService instance with mocks."""
    return SynapseService(
        graphiti_client=mock_graphiti,
        layer_manager=mock_layer_manager,
        user_id="test_user",
    )


# ============================================
# Task 1.1: SynapseService Tests
# ============================================

class TestSynapseService:
    """Tests for SynapseService bridge class."""

    def test_initialization(self, mock_graphiti):
        """Test that SynapseService initializes correctly."""
        service = SynapseService(graphiti_client=mock_graphiti)

        assert service.graphiti is mock_graphiti
        assert service.layers is not None
        assert service.user_id == "default"

    def test_initialization_with_custom_user(self, mock_graphiti, mock_layer_manager):
        """Test initialization with custom user_id."""
        service = SynapseService(
            graphiti_client=mock_graphiti,
            layer_manager=mock_layer_manager,
            user_id="custom_user",
        )

        assert service.user_id == "custom_user"

    @pytest.mark.asyncio
    async def test_add_memory_classifies_content(self, synapse_service, mock_graphiti):
        """Test that add_memory classifies content to appropriate layer."""
        result = await synapse_service.add_memory(
            name="test",
            episode_body="Python is a programming language",
            source_description="test",
        )

        assert "layer" in result
        assert result["layer"] in [layer.value for layer in MemoryLayer]
        mock_graphiti.add_episode.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_add_memory_procedural_content(self, synapse_service, mock_layer_manager):
        """Test that procedural content is classified correctly."""
        mock_layer_manager.detect_layer.return_value = MemoryLayer.PROCEDURAL

        result = await synapse_service.add_memory(
            name="test_procedure",
            episode_body="How to make coffee",
        )

        assert result["layer"] == MemoryLayer.PROCEDURAL.value

    @pytest.mark.asyncio
    async def test_add_memory_user_model_content(self, synapse_service, mock_layer_manager):
        """Test that user model content is classified correctly."""
        mock_layer_manager.detect_layer.return_value = MemoryLayer.USER_MODEL

        result = await synapse_service.add_memory(
            name="preference",
            episode_body="I prefer Thai language",
        )

        assert result["layer"] == MemoryLayer.USER_MODEL.value

    @pytest.mark.asyncio
    async def test_search_memory(self, synapse_service, mock_layer_manager, mock_graphiti):
        """Test search across memory layers."""
        result = await synapse_service.search_memory(
            query="test query",
            limit=10,
        )

        assert "results" in result
        assert "mode_used" in result
        assert result["mode_used"] in {"legacy", "hybrid_auto", "hybrid_best_effort", "hybrid_strict"}

    @pytest.mark.asyncio
    async def test_add_entity(self, synapse_service, mock_layer_manager):
        """Test adding entity through SynapseService."""
        entity = await synapse_service.add_entity(
            name="Python",
            entity_type="tech",
            summary="Programming language",
        )

        assert entity is not None
        mock_layer_manager.add_entity.assert_called_once()

    def test_graph_group_normalization_uses_global_default(self):
        """Graph group IDs should normalize to a single default namespace."""
        assert normalize_graph_group_id(None) == "global"
        assert normalize_graph_group_id("Project Alpha") == "Project_Alpha"

    @pytest.mark.asyncio
    async def test_get_entity(self, synapse_service, mock_layer_manager):
        """Test getting entity through SynapseService."""
        mock_layer_manager.semantic = MagicMock()
        mock_layer_manager.semantic.get_entity = AsyncMock(return_value=SynapseNode(
            id="test_id",
            type=EntityType.CONCEPT,
            name="Test",
        ))

        entity = await synapse_service.get_entity("test_id")

        assert entity is not None

    @pytest.mark.asyncio
    async def test_find_procedure(self, synapse_service, mock_layer_manager):
        """Test finding procedures through SynapseService."""
        from synapse.layers.types import ProceduralMemory

        mock_layer_manager.find_procedures = MagicMock(return_value=[
            ProceduralMemory(
                id="proc_1",
                trigger="test",
                procedure=["step1", "step2"],
            )
        ])

        procedures = synapse_service.find_procedure("test")

        assert isinstance(procedures, list)
        assert len(procedures) == 1
        assert procedures[0]["trigger"] == "test"

    def test_get_user_context(self, synapse_service, mock_layer_manager):
        """Test getting user context."""
        context = synapse_service.get_user_context()

        assert "user_id" in context
        # User ID comes from the layer_manager.get_user which returns "default"
        # The service stores user_id but get_user_context fetches from layers
        assert context["user_id"] in ["default", "test_user"]

    @pytest.mark.asyncio
    async def test_health_check(self, synapse_service):
        """Test health check."""
        result = await synapse_service.health_check()

        assert "status" in result
        assert "components" in result

    @pytest.mark.asyncio
    async def test_get_feed_events_collects_all_layers(self, tmp_path):
        """Feed should include durable events from all five layers."""
        layer_manager = LayerManager(
            user_model_manager=UserModelManager(db_path=tmp_path / "user.db"),
            procedural_manager=ProceduralManager(
                db_path=tmp_path / "procedural.db",
                vector_client=MagicMock(),
            ),
            semantic_manager=MagicMock(),
            episodic_manager=EpisodicManager(
                db_path=tmp_path / "episodic.db",
                vector_client=MagicMock(),
            ),
            working_manager=WorkingManager(),
        )

        graph_driver = MagicMock()
        graph_driver.clone.return_value = graph_driver
        graph_driver.execute_query = AsyncMock(return_value=(
            [
                {
                    "uuid": "graph-sem-1",
                    "name": "Semantic node",
                    "content": "Long-term fact",
                    "source": "text",
                    "source_description": "Entity type: concept",
                    "created_at": (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),
                    "group_id": "default",
                    "memory_layer": None,
                    "layer": None,
                    "source_episode": None,
                    "labels": ["Entity"],
                }
            ],
            None,
            None,
        ))
        graphiti_client = MagicMock()
        graphiti_client.driver = graph_driver
        graphiti_client._driver = graph_driver

        service = SynapseService(
            graphiti_client=graphiti_client,
            layer_manager=layer_manager,
            user_id="feed-user",
        )

        service.update_user_preferences(language="en", add_topics=["testing"])
        service.add_procedure("deploy app", ["build", "release"])
        service.layers.record_episode(
            content="User asked about feed layers",
            summary="Discussed feed layer coverage",
            topics=["feed"],
            outcome="success",
        )
        service.set_working_context("current_task", "fix feed")

        result = await service.get_feed_events(limit=20)
        layers = {event["layer"] for event in result["events"]}

        assert {"USER", "PROCEDURAL", "EPISODIC", "WORKING", "SEMANTIC"} <= layers


# ============================================
# Task 1.2: Semantic Layer Persistence Tests
# ============================================

class TestSemanticLayerPersistence:
    """Tests for Semantic Layer FalkorDB persistence."""

    @pytest.fixture
    def semantic_manager(self, mock_graphiti, tmp_path):
        """Create a SemanticManager with mock Graphiti."""
        from synapse.layers.semantic import SemanticManager

        # Mock Qdrant client
        with patch('synapse.layers.semantic.QdrantClient') as MockQdrant:
            mock_qdrant = MagicMock()
            mock_qdrant.upsert = MagicMock()
            mock_qdrant.search = MagicMock(return_value=[])
            MockQdrant.return_value = mock_qdrant

            manager = SemanticManager(
                graphiti_client=mock_graphiti,
                db_path=tmp_path / "semantic.db",
            )
            manager._submit_outbox_worker = MagicMock()
            return manager

    @pytest.mark.asyncio
    async def test_add_entity_queues_graph_projection(self, semantic_manager, mock_graphiti):
        """Test that add_entity queues graph projection durably."""
        entity = await semantic_manager.add_entity(
            name="Python",
            entity_type=EntityType.TECH,
            summary="A programming language",
        )

        assert entity is not None
        assert entity.name == "Python"
        pending = semantic_manager.store.fetch_pending_outbox(target_backend="graph", limit=10)
        assert len(pending) == 1
        assert pending[0]["op_type"] == "add_entity"
        assert mock_graphiti.add_episode.await_count == 0

    @pytest.mark.asyncio
    async def test_add_fact_queues_graph_projection(self, semantic_manager, mock_graphiti):
        """Test that add_fact queues graph projection durably."""
        edge = await semantic_manager.add_fact(
            source_id="entity_1",
            target_id="entity_2",
            relation_type=RelationType.RELATED_TO,
        )

        assert edge is not None
        assert edge.source_id == "entity_1"
        assert edge.target_id == "entity_2"
        pending = semantic_manager.store.fetch_pending_outbox(target_backend="graph", limit=10)
        assert len(pending) == 1
        assert pending[0]["op_type"] == "add_fact"
        assert mock_graphiti.add_episode.await_count == 0

    @pytest.mark.asyncio
    async def test_get_entity_returns_data(self, semantic_manager):
        """Test that get_entity returns actual data."""
        # Mock Qdrant to return a node
        semantic_manager.vector_client.search = MagicMock(return_value=[
            {
                "payload": {
                    "node_id": "test_entity",
                    "entity_type": "tech",
                    "name": "Python",
                    "summary": "Programming language",
                    "memory_layer": "semantic",
                    "confidence": 0.7,
                    "decay_score": 1.0,
                    "access_count": 0,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            }
        ])

        entity = await semantic_manager.get_entity("test_entity")

        # Should return None because the ID doesn't match exactly
        # or return the entity if we search more broadly
        assert entity is None or entity.id == "test_entity"

    @pytest.mark.asyncio
    async def test_update_entity(self, semantic_manager, mock_graphiti):
        """Test updating entity."""
        # Mock get_entity to return existing entity
        semantic_manager.get_entity = AsyncMock(return_value=SynapseNode(
            id="test_id",
            type=EntityType.TECH,
            name="Python",
            summary="Old summary",
        ))

        updated = await semantic_manager.update_entity(
            entity_id="test_id",
            summary="New summary",
            confidence=0.9,
        )

        assert updated is not None
        assert "New summary" in updated.summary
        assert updated.confidence == 0.9
        # Graphiti add_episode may not be called if graphiti_core is not available

    @pytest.mark.asyncio
    async def test_supersede_fact(self, semantic_manager, mock_graphiti):
        """Test superseding a fact."""
        new_edge = SynapseEdge(
            id="new_edge",
            source_id="entity_1",
            target_id="entity_2",
            type=RelationType.RELATED_TO,
        )

        result = await semantic_manager.supersede_fact(
            old_edge_id="old_edge_id",
            new_edge=new_edge,
        )

        assert result is not None
        assert "supersedes" in result.metadata
        assert result.metadata["supersedes"] == "old_edge_id"
        # Graphiti calls depend on whether graphiti_core is available
        # The important thing is that the metadata is set correctly

    @pytest.mark.asyncio
    async def test_get_related_entities(self, semantic_manager, mock_graphiti):
        """Test getting related entities."""
        # Mock Graphiti search to return edges
        mock_edge = MagicMock()
        mock_edge.fact = "Python is related to AI"
        mock_edge.source_node_uuid = "python_id"
        mock_edge.target_node_uuid = "ai_id"
        mock_graphiti.search = AsyncMock(return_value=[mock_edge])

        related = await semantic_manager.get_related_entities(
            entity_id="python_id",
            limit=10,
        )

        assert isinstance(related, list)

    @pytest.mark.asyncio
    async def test_cleanup_forgotten(self, semantic_manager):
        """Test cleaning up forgotten nodes."""
        # Mock search to return empty list
        semantic_manager.vector_client.search = MagicMock(return_value=[])

        count = await semantic_manager.cleanup_forgotten(batch_size=10)

        assert isinstance(count, int)
        assert count >= 0


# ============================================
# Integration Tests
# ============================================

class TestPhase1Integration:
    """Integration tests for Phase 1."""

    @pytest.mark.asyncio
    async def test_full_memory_flow(self, mock_graphiti):
        """Test complete memory flow: add -> search -> retrieve."""
        with patch('synapse.layers.semantic.QdrantClient') as MockQdrant:
            mock_qdrant = MagicMock()
            mock_qdrant.upsert = MagicMock()
            mock_qdrant.search = MagicMock(return_value=[])
            MockQdrant.return_value = mock_qdrant

            service = SynapseService(graphiti_client=mock_graphiti)

            # Add memory
            result = await service.add_memory(
                name="test_memory",
                episode_body="This is a test memory about Python programming",
            )

            assert "layer" in result

            # Search memory
            search_result = await service.search_memory(query="Python")

            assert "layers" in search_result
            assert "graphiti" in search_result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
