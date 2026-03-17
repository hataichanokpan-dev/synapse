"""
Comprehensive tests for all Synapse API endpoints.
"""

import pytest
from fastapi.testclient import TestClient


class TestHealthEndpoints:
    """Tests for health and root endpoints."""

    def test_health_returns_healthy(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "service" in data
        assert "version" in data

    def test_root_returns_api_info(self, client):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Synapse API"
        assert "docs" in data
        assert "health" in data


class TestIdentityEndpoints:
    """Tests for identity endpoints."""

    def test_get_identity(self, client, api_headers):
        response = client.get("/api/identity/", headers=api_headers)
        assert response.status_code == 200
        data = response.json()
        assert "user_id" in data

    def test_set_identity(self, client, api_headers):
        response = client.put(
            "/api/identity/",
            headers=api_headers,
            json={"user_id": "test-user", "agent_id": "test-agent"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "test-user"

    def test_clear_identity(self, client, api_headers):
        response = client.delete("/api/identity/", headers=api_headers)
        assert response.status_code == 200
        data = response.json()
        assert "message" in data

    def test_get_preferences(self, client, api_headers):
        response = client.get("/api/identity/preferences", headers=api_headers)
        assert response.status_code == 200
        data = response.json()
        assert "preferences" in data

    def test_update_preferences(self, client, api_headers):
        response = client.put(
            "/api/identity/preferences",
            headers=api_headers,
            json={"language": "th", "timezone": "Asia/Bangkok"}
        )
        assert response.status_code == 200


class TestMemoryEndpoints:
    """Tests for memory endpoints."""

    def test_add_memory_success(self, client, api_headers):
        response = client.post(
            "/api/memory/",
            headers=api_headers,
            json={
                "name": "Test Memory",
                "content": "Test content",
                "layer": "EPISODIC"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test Memory"
        assert "uuid" in data

    def test_add_memory_all_layers(self, client, api_headers):
        """Test adding memory to each layer."""
        layers = ["EPISODIC", "SEMANTIC", "PROCEDURAL", "WORKING", "USER_MODEL"]
        for layer in layers:
            response = client.post(
                "/api/memory/",
                headers=api_headers,
                json={"name": f"Test {layer}", "content": "content", "layer": layer}
            )
            assert response.status_code == 200

    def test_add_memory_requires_name(self, client, api_headers):
        response = client.post(
            "/api/memory/",
            headers=api_headers,
            json={"content": "test"}
        )
        assert response.status_code == 422

    def test_add_memory_requires_content(self, client, api_headers):
        response = client.post(
            "/api/memory/",
            headers=api_headers,
            json={"name": "test"}
        )
        assert response.status_code == 422

    def test_list_memories(self, client, api_headers):
        response = client.get("/api/memory/", headers=api_headers)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data

    def test_list_memories_with_pagination(self, client, api_headers):
        response = client.get("/api/memory/?limit=5&offset=10", headers=api_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 5
        assert data["offset"] == 10

    def test_search_memories(self, client, api_headers):
        response = client.post(
            "/api/memory/search",
            headers=api_headers,
            json={"query": "test", "limit": 10}
        )
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert data["query"] == "test"

    def test_search_memories_with_layers(self, client, api_headers):
        response = client.post(
            "/api/memory/search",
            headers=api_headers,
            json={"query": "test", "layers": ["EPISODIC", "SEMANTIC"]}
        )
        assert response.status_code == 200

    def test_consolidate_memories(self, client, api_headers):
        response = client.post(
            "/api/memory/consolidate",
            headers=api_headers,
            json={"dry_run": True}
        )
        assert response.status_code == 200
        data = response.json()
        assert "promoted" in data
        assert data["dry_run"] is True

    def test_get_memory_not_found(self, client, api_headers):
        response = client.get("/api/memory/nonexistent-id", headers=api_headers)
        assert response.status_code == 404

    def test_update_memory(self, client, api_headers):
        response = client.put(
            "/api/memory/test-id",
            headers=api_headers,
            json={"content": "updated"}
        )
        assert response.status_code == 200

    def test_delete_memory(self, client, api_headers):
        response = client.delete("/api/memory/test-id", headers=api_headers)
        assert response.status_code == 200


class TestProceduresEndpoints:
    """Tests for procedures endpoints."""

    def test_add_procedure(self, client, api_headers):
        response = client.post(
            "/api/procedures/",
            headers=api_headers,
            json={
                "trigger": "test-trigger",
                "steps": ["step1", "step2"],
                "topics": ["test"]
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["trigger"] == "test-trigger"

    def test_add_procedure_requires_trigger(self, client, api_headers):
        response = client.post(
            "/api/procedures/",
            headers=api_headers,
            json={"steps": ["step1"]}
        )
        assert response.status_code == 422

    def test_add_procedure_requires_steps(self, client, api_headers):
        response = client.post(
            "/api/procedures/",
            headers=api_headers,
            json={"trigger": "test"}
        )
        assert response.status_code == 422

    def test_list_procedures(self, client, api_headers):
        response = client.get("/api/procedures/", headers=api_headers)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data

    def test_record_procedure_success(self, client, api_headers):
        response = client.post(
            "/api/procedures/test-trigger/success",
            headers=api_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "success_count" in data

    def test_get_procedure_not_found(self, client, api_headers):
        response = client.get("/api/procedures/nonexistent", headers=api_headers)
        assert response.status_code == 404

    def test_update_procedure(self, client, api_headers):
        response = client.put(
            "/api/procedures/test-id",
            headers=api_headers,
            json={"steps": ["new-step"]}
        )
        assert response.status_code == 200

    def test_delete_procedure(self, client, api_headers):
        response = client.delete("/api/procedures/test-id", headers=api_headers)
        assert response.status_code == 200


class TestOracleEndpoints:
    """Tests for oracle endpoints."""

    def test_consult(self, client, api_headers):
        response = client.post(
            "/api/oracle/consult",
            headers=api_headers,
            json={"query": "What is the meaning?", "limit": 5}
        )
        assert response.status_code == 200
        data = response.json()
        assert "query" in data
        assert "layers" in data

    def test_consult_requires_query(self, client, api_headers):
        response = client.post(
            "/api/oracle/consult",
            headers=api_headers,
            json={}
        )
        assert response.status_code == 422

    def test_reflect(self, client, api_headers):
        response = client.post(
            "/api/oracle/reflect",
            headers=api_headers,
            json={"count": 5}
        )
        assert response.status_code == 200
        data = response.json()
        assert "insights" in data

    def test_analyze(self, client, api_headers):
        response = client.post(
            "/api/oracle/analyze",
            headers=api_headers,
            json={"analysis_type": "topics", "time_range_days": 30}
        )
        assert response.status_code == 200
        data = response.json()
        assert "patterns" in data


class TestSystemEndpoints:
    """Tests for system endpoints."""

    def test_get_status(self, client, api_headers):
        response = client.get("/api/system/status", headers=api_headers)
        assert response.status_code == 200
        data = response.json()
        assert "status" in data

    def test_get_stats(self, client, api_headers):
        response = client.get("/api/system/stats", headers=api_headers)
        assert response.status_code == 200
        data = response.json()
        assert "memory" in data
        assert "storage" in data

    def test_maintenance(self, client, api_headers):
        response = client.post(
            "/api/system/maintenance",
            headers=api_headers,
            json={"actions": ["decay_refresh"]}
        )
        assert response.status_code == 200
        data = response.json()
        assert "results" in data

    def test_clear_graph_requires_confirm(self, client, api_headers):
        response = client.delete(
            "/api/system/graph",
            headers=api_headers,
            json={"confirm": False}
        )
        assert response.status_code == 400

    def test_clear_graph_with_confirm(self, client, api_headers):
        response = client.delete(
            "/api/system/graph",
            headers=api_headers,
            json={"confirm": True}
        )
        assert response.status_code == 200


class TestGraphEndpoints:
    """Tests for graph endpoints."""

    def test_list_nodes(self, client, api_headers):
        response = client.get("/api/graph/nodes", headers=api_headers)
        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data

    def test_list_nodes_with_query(self, client, api_headers):
        response = client.get("/api/graph/nodes?query=test", headers=api_headers)
        assert response.status_code == 200

    def test_get_node_not_found(self, client, api_headers):
        response = client.get("/api/graph/nodes/nonexistent", headers=api_headers)
        assert response.status_code == 404

    def test_get_node_edges(self, client, api_headers):
        response = client.get("/api/graph/nodes/test-id/edges", headers=api_headers)
        assert response.status_code == 200

    def test_list_edges(self, client, api_headers):
        response = client.get("/api/graph/edges", headers=api_headers)
        assert response.status_code == 200

    def test_get_edge_not_found(self, client, api_headers):
        response = client.get("/api/graph/edges/nonexistent", headers=api_headers)
        assert response.status_code == 404

    def test_delete_node(self, client, api_headers):
        response = client.delete("/api/graph/nodes/test-id", headers=api_headers)
        assert response.status_code == 200

    def test_delete_edge(self, client, api_headers):
        response = client.delete("/api/graph/edges/test-id", headers=api_headers)
        assert response.status_code == 200


class TestEpisodesEndpoints:
    """Tests for episodes endpoints."""

    def test_list_episodes(self, client, api_headers):
        response = client.get("/api/episodes/", headers=api_headers)
        assert response.status_code == 200
        data = response.json()
        assert "episodes" in data

    def test_get_episode_not_found(self, client, api_headers):
        response = client.get("/api/episodes/nonexistent", headers=api_headers)
        assert response.status_code == 404

    def test_delete_episode(self, client, api_headers):
        response = client.delete("/api/episodes/test-id", headers=api_headers)
        assert response.status_code == 200


class TestFeedEndpoints:
    """Tests for feed endpoints."""

    def test_get_feed(self, client, api_headers):
        response = client.get("/api/feed/", headers=api_headers)
        assert response.status_code == 200
        data = response.json()
        assert "events" in data

    def test_feed_stream(self, client, api_headers):
        response = client.get("/api/feed/stream", headers=api_headers)
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"


class TestValidation:
    """Tests for validation and error handling."""

    def test_invalid_json(self, client, api_headers):
        response = client.post(
            "/api/memory/",
            headers=api_headers,
            content="not json"
        )
        assert response.status_code == 422

    def test_empty_body(self, client, api_headers):
        response = client.post(
            "/api/memory/",
            headers=api_headers,
            json={}
        )
        assert response.status_code == 422

    def test_invalid_layer(self, client, api_headers):
        response = client.post(
            "/api/memory/",
            headers=api_headers,
            json={"name": "test", "content": "test", "layer": "INVALID"}
        )
        assert response.status_code == 422

    def test_pagination_limits(self, client, api_headers):
        # Test max limit
        response = client.get("/api/memory/?limit=1000", headers=api_headers)
        assert response.status_code == 200  # Should clamp to max

    def test_negative_offset(self, client, api_headers):
        response = client.get("/api/memory/?offset=-1", headers=api_headers)
        assert response.status_code == 422


class TestOpenAPI:
    """Tests for API documentation."""

    def test_docs_endpoint(self, client):
        response = client.get("/docs")
        assert response.status_code == 200

    def test_redoc_endpoint(self, client):
        response = client.get("/redoc")
        assert response.status_code == 200

    def test_openapi_json(self, client):
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "paths" in data
