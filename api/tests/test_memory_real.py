"""
Service-level regression tests for real SQLite-backed memory operations.
"""

from __future__ import annotations

import pytest

from synapse.layers import EntityType
from synapse.layers.semantic import SemanticManager


@pytest.mark.asyncio
async def test_list_memories_empty(synapse_service):
    result = await synapse_service.list_memories()
    assert result["items"] == []
    assert result["total"] == 0


@pytest.mark.asyncio
async def test_add_memory_honors_explicit_layers_and_returns_real_uuid(synapse_service):
    episodic = await synapse_service.add_memory(
        name="Meeting notes",
        episode_body="Met Alice and discussed project timeline",
        layer="EPISODIC",
        metadata={"topics": ["project"], "outcome": "scheduled"},
        source="api",
    )
    assert episodic["uuid"]
    assert episodic["layer"] == "episodic"
    assert synapse_service.layers.episodic.get_episode(episodic["uuid"]) is not None

    procedural = await synapse_service.add_memory(
        name="Deploy app",
        episode_body="Run tests before deployment",
        layer="PROCEDURAL",
        metadata={
            "trigger": "Deploy app safely",
            "steps": ["Run tests", "Deploy"],
            "topics": ["deploy"],
        },
        source="api",
    )
    assert procedural["uuid"]
    assert procedural["layer"] == "procedural"
    stored = synapse_service.layers.procedural.get_procedure(procedural["uuid"])
    assert stored is not None
    assert stored.trigger == "Deploy app safely"
    assert stored.procedure == ["Run tests", "Deploy"]


@pytest.mark.asyncio
async def test_update_memory_supports_episodic_and_procedural(synapse_service):
    episode = synapse_service.layers.episodic.record_episode(
        content="Initial content",
        summary="Initial summary",
        user_id="test-user",
    )
    updated_episode = await synapse_service.update_memory(
        episode.id,
        content="Updated content",
        metadata={"summary": "Updated summary", "topics": ["updated"], "outcome": "done"},
    )
    assert updated_episode is not None
    assert updated_episode["name"] == "Updated summary"
    assert updated_episode["content"] == "Updated content"
    assert updated_episode["metadata"]["topics"] == ["updated"]

    procedure = synapse_service.layers.procedural.learn_procedure(
        trigger="Initial trigger",
        procedure=["step 1"],
        topics=["ops"],
    )
    updated_procedure = await synapse_service.update_memory(
        procedure.id,
        metadata={"trigger": "Updated trigger", "steps": ["step 1", "step 2"], "topics": ["ops", "deploy"]},
    )
    assert updated_procedure is not None
    assert updated_procedure["name"] == "Updated trigger"
    assert updated_procedure["metadata"]["steps"] == ["step 1", "step 2"]
    assert updated_procedure["metadata"]["topics"] == ["ops", "deploy"]


@pytest.mark.asyncio
async def test_search_memory_normalizes_layer_filters(synapse_service):
    synapse_service.layers.procedural.learn_procedure(
        trigger="Deploy app",
        procedure=["Run tests", "Deploy"],
        topics=["deploy"],
    )

    result = await synapse_service.search_memory("deploy", layers=["PROCEDURAL"], limit=5)
    assert "procedural" in result["layers"]
    assert result["layers"]["procedural"]
    assert "episodic" not in result["layers"]


class RejectingVectorClient:
    def upsert(self, *args, **kwargs):
        raise RuntimeError("vector write failed")


@pytest.mark.asyncio
async def test_semantic_add_requires_a_durable_backend():
    manager = SemanticManager(graphiti_client=None, vector_client=RejectingVectorClient())

    with pytest.raises(RuntimeError, match="no durable backend accepted the write"):
        await manager.add_entity(
            name="Python",
            entity_type=EntityType.CONCEPT,
            summary="A programming language",
        )
