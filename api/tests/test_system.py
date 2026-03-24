"""
Tests for system endpoints.
"""

import sqlite3
from datetime import timedelta

import pytest

from synapse.layers.types import EntityType, MemoryLayer, RelationType, SynapseEdge, SynapseNode, utcnow


def _rewrite_outbox_timestamps(db_path, operation_id, *, created_at, next_attempt_at=None, available_at=None):
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            UPDATE semantic_outbox
            SET created_at = ?,
                updated_at = ?,
                next_attempt_at = COALESCE(?, next_attempt_at),
                available_at = COALESCE(?, available_at)
            WHERE operation_id = ?
            """,
            (created_at, created_at, next_attempt_at, available_at, operation_id),
        )
        conn.commit()
    finally:
        conn.close()


def _fetch_outbox_row(db_path, operation_id):
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT * FROM semantic_outbox WHERE operation_id = ?",
            (operation_id,),
        ).fetchone()
        assert row is not None
        return row
    finally:
        conn.close()


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

    def test_status_separates_graph_outbox_backlog_from_vector_health(self, client, api_headers, synapse_service):
        """Graph backlog should degrade graph only; done vector rows should stay healthy."""
        store = synapse_service.layers.semantic.store

        vector_operation = "vector-done-old"
        store.enqueue_outbox(
            operation_id=vector_operation,
            target_backend="vector",
            record_id="node-vector",
            op_type="add_entity",
            payload={"id": "node-vector"},
            dedupe_key="add_entity:node-vector:vector",
        )
        store.mark_outbox_success(vector_operation)
        _rewrite_outbox_timestamps(
            store.db_path,
            vector_operation,
            created_at=(utcnow() - timedelta(days=2)).isoformat(),
        )

        graph_operation = "graph-rate-limited"
        store.enqueue_outbox(
            operation_id=graph_operation,
            target_backend="graph",
            record_id="node-graph",
            op_type="add_entity",
            payload={"id": "node-graph"},
            dedupe_key="add_entity:node-graph:graph",
        )
        store.mark_outbox_failure(
            graph_operation,
            "429 rate limit exceeded",
            retry_count=4,
            delay_seconds=300,
        )

        response = client.get("/api/system/status", headers=api_headers)
        assert response.status_code == 200
        data = response.json()
        components = {component["name"]: component for component in data["components"]}

        assert components["semantic_outbox_graph"]["status"] == "degraded"
        assert "pending=1" in components["semantic_outbox_graph"]["message"]
        assert "failed=1" in components["semantic_outbox_graph"]["message"]
        assert components["semantic_outbox_graph"]["details"]["next_attempt_at"] is not None
        assert components["semantic_outbox_vector"]["status"] == "healthy"
        assert components["semantic_outbox_vector"]["message"] == "ok"
        assert components["hybrid_search"]["status"] == "degraded"
        assert components["hybrid_search"]["message"] == "degraded: graph"


class TestSystemStats:
    """Tests for /api/system/stats endpoint."""

    def test_stats_returns_counts(self, client, api_headers):
        """Stats endpoint should return memory counts."""
        response = client.get("/api/system/stats", headers=api_headers)
        assert response.status_code == 200
        data = response.json()
        assert "memory" in data
        assert "storage" in data

    def test_stats_include_semantic_projection_outbox_details(self, client, api_headers, synapse_service):
        """Stats should expose per-backend outbox detail for semantic projection."""
        store = synapse_service.layers.semantic.store
        operation_id = "graph-stats-row"
        store.enqueue_outbox(
            operation_id=operation_id,
            target_backend="graph",
            record_id="node-stats",
            op_type="add_entity",
            payload={"id": "node-stats"},
            dedupe_key="add_entity:node-stats:graph",
        )
        store.mark_outbox_failure(
            operation_id,
            "429 rate limit exceeded",
            retry_count=2,
            delay_seconds=300,
        )

        response = client.get("/api/system/stats", headers=api_headers)
        assert response.status_code == 200
        body = response.json()
        graph = body["search"]["semantic_projection"]["outbox"]["graph"]

        assert graph["pending_count"] == 1
        assert graph["failed_count"] == 1
        assert graph["next_attempt_at"] is not None
        assert "429" in graph["last_error_excerpt"]
        assert graph["circuit_state"] == "closed"


class TestSystemMaintenance:
    """Tests for /api/system/maintenance endpoint."""

    def test_maintenance_supports_semantic_recovery_actions_in_dry_run(self, client, api_headers, synapse_service):
        """Maintenance dry-run should expose semantic replay and graph rebuild actions."""
        store = synapse_service.layers.semantic.store
        now = utcnow()
        store.enqueue_outbox(
            operation_id="graph-due-replay",
            target_backend="graph",
            record_id="node-replay",
            op_type="add_entity",
            payload={"id": "node-replay"},
            dedupe_key="add_entity:node-replay:graph",
        )
        store.save_node(
            SynapseNode(
                id="node-rebuild",
                type=EntityType.CONCEPT,
                name="Node Rebuild",
                summary="Rebuild me",
                memory_layer=MemoryLayer.SEMANTIC,
                created_at=now,
                updated_at=now,
            )
        )
        store.save_edge(
            SynapseEdge(
                id="edge-rebuild",
                source_id="node-rebuild",
                target_id="node-target",
                type=RelationType.RELATED_TO,
                valid_at=now,
            ),
            fact_text="node-rebuild related_to node-target",
        )

        response = client.post(
            "/api/system/maintenance",
            headers=api_headers,
            json={
                "actions": ["replay_semantic_outbox", "rebuild_semantic_graph"],
                "dry_run": True,
            },
        )

        assert response.status_code == 200
        body = response.json()
        results = {result["action"]: result for result in body["results"]}

        assert results["replay_semantic_outbox"]["affected"] == 1
        assert "Would replay 1 due semantic outbox tasks" in results["replay_semantic_outbox"]["message"]
        assert results["rebuild_semantic_graph"]["affected"] == 2
        assert "nodes=1" in results["rebuild_semantic_graph"]["message"]
        assert "edges=1" in results["rebuild_semantic_graph"]["message"]

    def test_maintenance_executes_semantic_outbox_replay(self, client, api_headers, synapse_service):
        """Replay execute mode should attempt due outbox work immediately."""
        store = synapse_service.layers.semantic.store
        store.enqueue_outbox(
            operation_id="graph-execute-replay",
            target_backend="graph",
            record_id="node-execute",
            op_type="add_entity",
            payload={
                "id": "node-execute",
                "op_type": "add_entity",
                "name": "Execute Replay",
                "graph_name": "entity_Execute Replay",
                "episode_body": "Execute Replay: summary",
                "source_description": "Entity type: concept",
                "created_at": utcnow().isoformat(),
            },
            dedupe_key="add_entity:node-execute:graph",
        )

        response = client.post(
            "/api/system/maintenance",
            headers=api_headers,
            json={"actions": ["replay_semantic_outbox"], "dry_run": False},
        )

        assert response.status_code == 200
        body = response.json()
        result = body["results"][0]
        row = _fetch_outbox_row(store.db_path, "graph-execute-replay")

        assert result["action"] == "replay_semantic_outbox"
        assert result["affected"] == 1
        assert "Triggered replay for 1 due semantic outbox tasks" in result["message"]
        assert row["status"] == "retry_wait"

    def test_maintenance_supports_graph_projection_control_actions(self, client, api_headers, synapse_service):
        """Maintenance should expose pause/resume/dead-letter replay flows."""
        store = synapse_service.layers.semantic.store
        store.enqueue_outbox(
            operation_id="graph-dead-letter",
            target_backend="graph",
            record_id="node-dead",
            op_type="add_entity",
            payload={"id": "node-dead"},
            dedupe_key="add_entity:node-dead:graph",
        )
        store.mark_outbox_dead_letter(
            "graph-dead-letter",
            "invalid payload",
            retry_count=12,
            error_code="INVALID_PAYLOAD",
            error_class="permanent",
        )

        dry_run = client.post(
            "/api/system/maintenance",
            headers=api_headers,
            json={
                "actions": [
                    "pause_graph_projection",
                    "resume_graph_projection",
                    "replay_dead_letter_graph",
                ],
                "dry_run": True,
            },
        )

        assert dry_run.status_code == 200
        dry_results = {result["action"]: result for result in dry_run.json()["results"]}
        assert "Would pause graph projection" in dry_results["pause_graph_projection"]["message"]
        assert "Would resume graph projection" in dry_results["resume_graph_projection"]["message"]
        assert dry_results["replay_dead_letter_graph"]["affected"] == 1

        execute = client.post(
            "/api/system/maintenance",
            headers=api_headers,
            json={
                "actions": [
                    "pause_graph_projection",
                    "replay_dead_letter_graph",
                    "resume_graph_projection",
                ],
                "dry_run": False,
            },
        )

        assert execute.status_code == 200
        row = _fetch_outbox_row(store.db_path, "graph-dead-letter")
        projector_state = store.get_projector_state("graph")

        assert row["status"] in {"pending", "retry_wait", "leased"}
        assert projector_state["circuit_state"] == "closed"
