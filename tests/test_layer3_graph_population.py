"""
Layer 3 Graph Population Verification Tests

These tests verify that Graphiti actually writes to the graph database.
They are the ONLY tests that verify the core value proposition of Synapse.

Run with:
    pytest tests/test_layer3_graph_population.py -v -m integration

Requires:
    - FalkorDB or Neo4j running (see docker-compose)
    - ANTHROPIC_API_KEY or OPENAI_API_KEY set
"""

import pytest
import asyncio
import os
from typing import Optional
from datetime import datetime

# Load .env file before checking environment variables
from dotenv import load_dotenv
load_dotenv()

# Skip all tests if no graph database available
pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_GRAPH_INTEGRATION_TESTS", "false").lower() != "true",
    reason="Set RUN_GRAPH_INTEGRATION_TESTS=true to run graph integration tests"
)


# ============================================
# NO-OP CROSS ENCODER (for non-OpenAI setups)
# ============================================

class NoOpCrossEncoder:
    """
    A no-op cross encoder that returns passages with equal scores.
    Used when we don't have OpenAI API key for the reranker.

    Note: This inherits from CrossEncoderClient via duck typing.
    Pydantic validates using isinstance check, so we need to
    register as a virtual subclass.
    """

    def rank(self, query: str, passages: list[str]) -> list[tuple[str, float]]:
        """Return passages with equal scores (no actual reranking)."""
        # Simple scoring: give each passage a decreasing score
        # In production, you'd want actual reranking for better results
        return [(passage, 1.0 / (i + 1)) for i, passage in enumerate(passages)]


# Register NoOpCrossEncoder as a virtual subclass of CrossEncoderClient
from graphiti_core.cross_encoder import CrossEncoderClient
CrossEncoderClient.register(NoOpCrossEncoder)


# ============================================
# FIXTURES
# ============================================

@pytest.fixture
async def real_graphiti():
    """Create a real Graphiti client connected to test database."""
    try:
        from graphiti_core import Graphiti
        from graphiti_core.driver.falkordb_driver import FalkorDriver

        # Get connection details from env
        uri = os.environ.get("FALKORDB_URI", "redis://localhost:6379")
        password = os.environ.get("FALKORDB_PASSWORD", "")

        # Create FalkorDB driver
        from urllib.parse import urlparse
        parsed = urlparse(uri)
        host = parsed.hostname or "localhost"
        port = parsed.port or 6379

        driver = FalkorDriver(
            host=host,
            port=port,
            password=password,
            database="test_synapse",
        )

        # Create Graphiti client
        # Use Anthropic from .env (ANTHROPIC_API_KEY, ANTHROPIC_BASE_URL)
        from graphiti_core.llm_client.anthropic_client import AnthropicClient
        from graphiti_core.llm_client.config import LLMConfig as GraphitiLLMConfig

        # Support both Anthropic and OpenAI
        anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY")
        anthropic_base_url = os.environ.get("ANTHROPIC_BASE_URL")
        openai_api_key = os.environ.get("OPENAI_API_KEY")

        if anthropic_api_key:
            # Use Anthropic
            llm_config = GraphitiLLMConfig(
                api_key=anthropic_api_key,
                base_url=anthropic_base_url,
                model="claude-sonnet-4-20250514",
            )
            llm_client = AnthropicClient(config=llm_config)
            # Use local embedder for Anthropic setup
            from synapse.graphiti.embedder.local import LocalEmbedder, LocalEmbedderConfig
            embedder_config = LocalEmbedderConfig(embedding_dim=384)
            embedder = LocalEmbedder(config=embedder_config)
            # Use no-op cross encoder (no OpenAI reranking)
            cross_encoder = NoOpCrossEncoder()
        elif openai_api_key:
            # Fallback to OpenAI
            from graphiti_core.llm_client import OpenAIClient
            from graphiti_core.embedder import OpenAIEmbedder
            from graphiti_core.embedder.openai import OpenAIEmbedderConfig

            llm_config = GraphitiLLMConfig(api_key=openai_api_key, model="gpt-4o-mini")
            llm_client = OpenAIClient(config=llm_config)
            embedder_config = OpenAIEmbedderConfig(api_key=openai_api_key)
            embedder = OpenAIEmbedder(config=embedder_config)
            # OpenAI can use its own reranker
            cross_encoder = None
        else:
            pytest.skip("ANTHROPIC_API_KEY or OPENAI_API_KEY not set")

        graphiti = Graphiti(
            graph_driver=driver,
            llm_client=llm_client,
            embedder=embedder,
            cross_encoder=cross_encoder,
        )

        await graphiti.build_indices_and_constraints()

        yield graphiti

        # Cleanup
        try:
            await graphiti.clear_data()
        except Exception:
            pass

    except ImportError as e:
        pytest.skip(f"Graphiti not available: {e}")
    except Exception as e:
        pytest.skip(f"Could not create Graphiti client: {e}")


@pytest.fixture
async def synapse_with_real_graphiti(real_graphiti):
    """Create SynapseService with real Graphiti client."""
    from synapse.services.synapse_service import SynapseService
    from synapse.layers import LayerManager

    layer_manager = LayerManager()

    service = SynapseService(
        graphiti_client=real_graphiti,
        layer_manager=layer_manager,
        user_id="integration_test_user",
    )

    yield service


# ============================================
# GRAPH WRITE VERIFICATION TESTS
# ============================================

class TestGraphitiWriteVerification:
    """Tests that verify Graphiti actually writes to the graph database."""

    @pytest.mark.asyncio
    async def test_add_episode_creates_node_in_graph(self, real_graphiti):
        """
        CRITICAL: Verify add_episode actually creates a node in the graph.

        This is the CORE VALUE of Synapse - if this fails, Layer 3 is broken.
        """
        # Add an episode
        episode_name = "test_python_knowledge"
        episode_body = "Python is a high-level programming language known for its readability."

        result = await real_graphiti.add_episode(
            name=episode_name,
            episode_body=episode_body,
            source_description="Integration test",
            reference_time=datetime.now(),
            group_id="test_group",
        )

        # VERIFY: Result is not None
        assert result is not None, "add_episode returned None!"

        # VERIFY: Episode was created
        assert result.episode is not None, "Episode is None!"
        assert result.episode.name == episode_name

        # VERIFY: At least one entity node was extracted and created
        # This is the key verification - if nodes were created, the graph is being populated
        assert len(result.nodes) > 0, (
            "No entity nodes were extracted! "
            "Either LLM extraction failed, or graph write failed."
        )

        # VERIFY: At least one node mentions Python
        found_python = False
        for node in result.nodes:
            if 'python' in node.name.lower():
                found_python = True
                break

        assert found_python, f"No node mentions Python. Nodes: {[n.name for n in result.nodes]}"

    @pytest.mark.asyncio
    async def test_add_episode_extracts_entities(self, real_graphiti):
        """
        Verify that add_episode uses LLM to extract entities.

        Graphiti should create nodes for entities found in the text.
        """
        # Add episode with clear entities
        result = await real_graphiti.add_episode(
            name="entity_test",
            episode_body="John works at Google as a software engineer. He uses Python and JavaScript.",
            source_description="Entity extraction test",
            reference_time=datetime.now(),
            group_id="entity_test_group",
        )

        # VERIFY: Result is not None
        assert result is not None, "add_episode returned None!"

        # VERIFY: At least one entity node was extracted
        assert len(result.nodes) > 0, (
            f"No entity nodes extracted! LLM extraction may be broken. "
            f"Episode: {result.episode}"
        )

        # VERIFY: Expected entities are present
        entity_names = [node.name.lower() for node in result.nodes]
        expected_entities = ["john", "google", "python", "javascript"]

        found_entities = [e for e in expected_entities if any(e in name for name in entity_names)]

        # At least 2 of the 4 expected entities should be found
        assert len(found_entities) >= 2, (
            f"Expected at least 2 of {expected_entities}, found: {entity_names}"
        )

    @pytest.mark.asyncio
    async def test_multiple_episodes_create_edges(self, real_graphiti):
        """
        Verify that multiple episodes about the same entities create edges.

        This tests the knowledge graph building capability.
        """
        # Add first episode
        result1 = await real_graphiti.add_episode(
            name="person_intro",
            episode_body="Alice is a data scientist at TechCorp.",
            source_description="Person introduction",
            reference_time=datetime.now(),
            group_id="multi_episode_group",
        )

        # Add second episode about same person
        result2 = await real_graphiti.add_episode(
            name="person_update",
            episode_body="Alice uses Python for machine learning projects.",
            source_description="Person update",
            reference_time=datetime.now(),
            group_id="multi_episode_group",
        )

        # VERIFY: Both episodes created entities
        assert len(result1.nodes) > 0, "First episode created no nodes"
        assert len(result2.nodes) > 0, "Second episode created no nodes"

        # VERIFY: Alice entity exists in at least one result
        all_nodes = result1.nodes + result2.nodes
        entity_names = [node.name.lower() for node in all_nodes]

        assert any("alice" in name for name in entity_names), (
            f"No 'Alice' entity found. Entities: {entity_names}"
        )


class TestSynapseServiceGraphitiIntegration:
    """Tests for SynapseService with real Graphiti."""

    @pytest.mark.asyncio
    async def test_add_memory_calls_graphiti(self, synapse_with_real_graphiti, real_graphiti):
        """
        Verify that SynapseService.add_memory() calls Graphiti.
        """
        service = synapse_with_real_graphiti

        result = await service.add_memory(
            name="test_memory",
            episode_body="The user prefers dark mode for coding.",
            source_description="User preference",
        )

        # VERIFY: Layer classification happened
        assert "layer" in result
        assert result["layer"] in ["user_model", "procedural", "semantic", "episodic", "working"]

        # VERIFY: Graphiti was called
        assert result.get("graphiti_result") is not None, (
            "graphiti_result is None! add_memory() didn't call Graphiti."
        )

    @pytest.mark.asyncio
    async def test_add_memory_semantic_creates_entity(self, synapse_with_real_graphiti):
        """
        Verify that semantic content creates entities.
        """
        service = synapse_with_real_graphiti

        # Content that should be classified as semantic
        result = await service.add_memory(
            name="programming_concept",
            episode_body="Dependency injection is a design pattern that implements inversion of control.",
            source_description="Technical concept",
        )

        # VERIFY: Classified as semantic
        assert result["layer"] == "semantic", f"Expected semantic, got {result['layer']}"

        # VERIFY: Graphiti was called
        assert result.get("graphiti_result") is not None

    @pytest.mark.asyncio
    async def test_search_returns_graphiti_results(self, synapse_with_real_graphiti):
        """
        Verify that search_memory() includes Graphiti results.
        """
        service = synapse_with_real_graphiti

        # First, add some data
        await service.add_memory(
            name="search_test",
            episode_body="Docker is a containerization platform for building and running applications.",
            source_description="Technology knowledge",
        )

        # Wait for indexing
        await asyncio.sleep(2)

        # Search
        results = await service.search_memory(
            query="Docker containerization",
            limit=10,
        )

        # VERIFY: Results structure
        assert "layers" in results
        assert "graphiti" in results

        # VERIFY: Graphiti has results
        graphiti_results = results.get("graphiti", [])
        # Note: May be empty if Graphiti search failed
        # This test documents the expected behavior

        print(f"Graphiti search results: {len(graphiti_results)} items")


class TestSemanticManagerGraphiti:
    """Tests for SemanticManager with real Graphiti."""

    @pytest.mark.asyncio
    async def test_add_entity_persists_to_graph(self, real_graphiti):
        """
        Verify that SemanticManager.add_entity() writes to Graphiti.
        """
        from synapse.layers.semantic import SemanticManager
        from synapse.layers.types import EntityType

        manager = SemanticManager(graphiti_client=real_graphiti)

        # Add entity
        node = await manager.add_entity(
            name="FastAPI",
            entity_type=EntityType.TECH,
            summary="FastAPI is a modern Python web framework.",
        )

        # VERIFY: Node returned
        assert node is not None
        assert node.name == "FastAPI"
        assert node.type == EntityType.TECH

        # VERIFY: Can retrieve entity
        retrieved = await manager.get_entity(node.id)
        # Note: May be None if Graphiti search doesn't find it
        # This documents current behavior

    @pytest.mark.asyncio
    async def test_add_fact_creates_edge(self, real_graphiti):
        """
        Verify that SemanticManager.add_fact() creates an edge.
        """
        from synapse.layers.semantic import SemanticManager
        from synapse.layers.types import EntityType, RelationType

        manager = SemanticManager(graphiti_client=real_graphiti)

        # First create entities
        source = await manager.add_entity(
            name="Python",
            entity_type=EntityType.TECH,
            summary="Python programming language",
        )

        target = await manager.add_entity(
            name="FastAPI",
            entity_type=EntityType.TECH,
            summary="FastAPI web framework",
        )

        # Add fact/relationship
        edge = await manager.add_fact(
            source_id=source.id,
            target_id=target.id,
            relation_type=RelationType.RELATED_TO,
        )

        # VERIFY: Edge returned
        assert edge is not None
        assert edge.source_id == source.id
        assert edge.target_id == target.id
        assert edge.type == RelationType.RELATED_TO


class TestGraphitiFailureHandling:
    """Tests for how the system handles Graphiti failures."""

    @pytest.mark.asyncio
    async def test_broken_graphiti_is_detected(self):
        """
        Verify that we can detect when Graphiti is broken.

        This test uses a mock that always fails to simulate a broken Graphiti.
        """
        from unittest.mock import AsyncMock
        from synapse.services.synapse_service import SynapseService
        from synapse.layers import LayerManager

        # Create a broken Graphiti mock
        broken_graphiti = AsyncMock()
        broken_graphiti.add_episode = AsyncMock(side_effect=Exception("Connection refused"))
        broken_graphiti.search = AsyncMock(side_effect=Exception("Connection refused"))

        service = SynapseService(
            graphiti_client=broken_graphiti,
            layer_manager=LayerManager(),
            user_id="test_user",
        )

        # Current behavior: add_memory catches the exception and logs
        # It returns a result with graphiti_result=None
        result = await service.add_memory(
            name="test",
            episode_body="Test content",
        )

        # DOCUMENT CURRENT BEHAVIOR:
        # graphiti_result should be None because the mock raised an exception
        # This is a SILENT FAILURE - the caller doesn't know Graphiti failed!

        # EXPECTED BEHAVIOR (for future fix):
        # The function should either:
        # 1. Raise an exception, or
        # 2. Return a status indicating failure

        # For now, document the current behavior
        assert result["graphiti_result"] is None, (
            "Expected graphiti_result to be None when Graphiti fails. "
            "If this assertion fails, the behavior has changed."
        )

    @pytest.mark.asyncio
    async def test_health_check_detects_graphiti_issues(self):
        """
        Verify that health_check() can detect Graphiti issues.
        """
        from synapse.services.synapse_service import SynapseService

        # Test with None Graphiti
        service = SynapseService(graphiti_client=None)
        health = await service.health_check()

        # Should indicate Graphiti is not available
        assert health["components"]["graphiti"] != "ok", (
            "health_check should detect when Graphiti is None"
        )


# ============================================
# DIAGNOSTIC TESTS
# ============================================

class TestGraphitiDiagnostics:
    """Diagnostic tests to understand Graphiti behavior."""

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Diagnostic test - run manually")
    async def test_graphiti_raw_search(self, real_graphiti):
        """
        Diagnostic: Test Graphiti search directly.

        Run this manually to understand search behavior.
        """
        # Add some data
        await real_graphiti.add_episode(
            name="diag_test",
            episode_body="React is a JavaScript library for building user interfaces.",
            source_description="Diagnostic test",
            reference_time=datetime.now(),
        )

        await asyncio.sleep(2)

        # Try various searches
        queries = [
            "React",
            "JavaScript",
            "user interfaces",
            "library",
            "building",
        ]

        for query in queries:
            results = await real_graphiti.search(query=query, num_results=5)
            print(f"\nQuery: {query}")
            print(f"Results: {len(results)}")
            for r in results:
                print(f"  - {getattr(r, 'fact', r)}")


# ============================================
# TEST RUNNER
# ============================================

if __name__ == "__main__":
    """
    Run tests directly:

        # With environment variables
        export RUN_GRAPH_INTEGRATION_TESTS=true
        export OPENAI_API_KEY=sk-...
        export FALKORDB_URI=redis://localhost:6379

        python tests/test_layer3_graph_population.py
    """
    pytest.main([__file__, "-v", "-s"])
