"""
Tests for system endpoints.
"""

import pytest


class TestHealthEndpoint:
    """Tests for /health endpoint."""

    def test_health_returns_healthy(self, client):
        """Health endpoint should return healthy status."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "synapse-api"


class TestRootEndpoint:
    """Tests for / endpoint."""

    def test_root_returns_api_info(self, client):
        """Root endpoint should return API info."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "docs" in data


class TestSystemStatus:
    """Tests for /api/system/status endpoint."""

    def test_status_requires_auth(self, client):
        """Status endpoint should work with API key."""
        response = client.get(
            "/api/system/status",
            headers={"X-API-Key": "synapse-dev-key"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "status" in data


class TestSystemStats:
    """Tests for /api/system/stats endpoint."""

    def test_stats_returns_counts(self, client, api_headers):
        """Stats endpoint should return memory counts."""
        response = client.get("/api/system/stats", headers=api_headers)
        assert response.status_code == 200
        data = response.json()
        assert "memory" in data
        assert "storage" in data
