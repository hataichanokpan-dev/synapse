"""
Pytest fixtures for Synapse API tests.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

import pytest
from fastapi.testclient import TestClient

from api.deps import get_event_bus, get_synapse_service
from api.main import app
from api.services.event_bus import EventBus
from synapse.layers import LayerManager
from synapse.layers.episodic import EpisodicManager
from synapse.layers.procedural import ProceduralManager
from synapse.layers.semantic import SemanticManager
from synapse.layers.user_model import UserModelManager
from synapse.layers.working import WorkingManager
from synapse.services.synapse_service import SynapseService


class DummyVectorClient:
    """No-op vector client to keep API tests deterministic and offline."""

    enabled = True

    def upsert(self, *args, **kwargs):
        return None

    def search(self, *args, **kwargs):
        return []

    def delete(self, *args, **kwargs):
        return None

    def scroll(self, *args, **kwargs):
        return ([], None)


@pytest.fixture
def synapse_service(tmp_path, monkeypatch):
    """Create a real SynapseService backed by temp SQLite databases."""
    monkeypatch.setenv("SYNAPSE_ENABLE_GRAPHITI", "false")
    vector_client = DummyVectorClient()
    layer_manager = LayerManager(
        user_model_manager=UserModelManager(tmp_path / "user_model.db"),
        procedural_manager=ProceduralManager(tmp_path / "procedural.db", vector_client=vector_client),
        episodic_manager=EpisodicManager(tmp_path / "episodic.db", vector_client=vector_client),
        semantic_manager=SemanticManager(
            graphiti_client=None,
            vector_client=vector_client,
            db_path=tmp_path / "semantic.db",
        ),
        working_manager=WorkingManager(),
        user_id="test-user",
    )
    return SynapseService(
        graphiti_client=None,
        layer_manager=layer_manager,
        user_id="test-user",
    )


@pytest.fixture
def event_bus():
    """Create an isolated in-memory event bus."""
    return EventBus(buffer_size=100)


@pytest.fixture
def client(synapse_service, event_bus):
    """Create a test client with dependency overrides and no startup side effects."""

    @asynccontextmanager
    async def noop_lifespan(_app):
        yield

    original_lifespan = app.router.lifespan_context
    app.router.lifespan_context = noop_lifespan
    app.dependency_overrides[get_synapse_service] = lambda: synapse_service
    app.dependency_overrides[get_event_bus] = lambda: event_bus

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        app.router.lifespan_context = original_lifespan


@pytest.fixture
def api_headers():
    """Default API headers."""
    return {
        "X-API-Key": "synapse-dev-key",
        "Content-Type": "application/json",
    }
