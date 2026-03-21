"""
Service-level regression tests for real SQLite-backed memory operations.
"""

from __future__ import annotations

import pytest

from synapse.search import HybridSearchError


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


@pytest.mark.asyncio
async def test_search_memory_returns_hybrid_metadata_and_pinned_context(synapse_service):
    synapse_service.set_working_context("current_task", "deploy release candidate")
    synapse_service.layers.procedural.learn_procedure(
        trigger="Deploy release",
        procedure=["Run tests", "Ship release"],
        topics=["deploy"],
    )

    result = await synapse_service.search_memory("deploy", limit=5, explain=True)
    assert result["mode_used"] == "hybrid_auto"
    assert result["query_type_detected"] in {
        "exact",
        "semantic",
        "relational",
        "procedural",
        "episodic",
        "preference",
        "mixed",
    }
    assert result["results"]
    assert any(entry["sources"] for entry in result["results"])
    assert result["pinned_context"]


@pytest.mark.asyncio
async def test_hybrid_strict_requires_semantic_graph_backend(synapse_service):
    with pytest.raises(HybridSearchError):
        await synapse_service.search_memory(
            "python",
            layers=["SEMANTIC"],
            limit=5,
            mode="hybrid_strict",
        )
