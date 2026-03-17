"""
Tests for memory endpoints.
"""

import pytest


class TestMemoryAdd:
    """Tests for POST /api/memory endpoint."""

    def test_add_memory_success(self, client, api_headers):
        """Should add a new memory."""
        response = client.post(
            "/api/memory/",
            headers=api_headers,
            json={
                "name": "Test Memory",
                "content": "This is a test memory",
                "layer": "EPISODIC",
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test Memory"
        assert data["content"] == "This is a test memory"

    def test_add_memory_requires_name(self, client, api_headers):
        """Should require name field."""
        response = client.post(
            "/api/memory/",
            headers=api_headers,
            json={"content": "test"}
        )
        assert response.status_code == 422

    def test_add_memory_requires_content(self, client, api_headers):
        """Should require content field."""
        response = client.post(
            "/api/memory/",
            headers=api_headers,
            json={"name": "test"}
        )
        assert response.status_code == 422


class TestMemorySearch:
    """Tests for POST /api/memory/search endpoint."""

    def test_search_memories(self, client, api_headers):
        """Should search memories."""
        response = client.post(
            "/api/memory/search",
            headers=api_headers,
            json={"query": "test"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert "total" in data


class TestMemoryList:
    """Tests for GET /api/memory endpoint."""

    def test_list_memories(self, client, api_headers):
        """Should list memories."""
        response = client.get("/api/memory/", headers=api_headers)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data


class TestMemoryGetById:
    """Tests for GET /api/memory/:id endpoint."""

    def test_get_memory_not_found(self, client, api_headers):
        """Should return 404 for non-existent memory."""
        response = client.get("/api/memory/nonexistent", headers=api_headers)
        assert response.status_code == 404
