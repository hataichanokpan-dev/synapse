"""
Pytest configuration and fixtures for Synapse API tests.
"""

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.deps import MockSynapseService, _synapse_service, _event_bus
from api.services.event_bus import EventBus
from api.config import settings


@pytest.fixture(scope="session", autouse=True)
def setup_services():
    """Initialize services for all tests."""
    import api.deps as deps
    deps._synapse_service = MockSynapseService()
    deps._event_bus = EventBus(buffer_size=settings.feed_buffer_size)
    yield
    deps._synapse_service = None
    deps._event_bus = None


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def api_headers():
    """Default API headers."""
    return {
        "X-API-Key": "synapse-dev-key",
        "Content-Type": "application/json",
    }
