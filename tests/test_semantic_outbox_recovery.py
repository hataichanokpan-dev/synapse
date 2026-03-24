import sqlite3
from datetime import timedelta
from pathlib import Path
from unittest.mock import AsyncMock

from synapse.layers.semantic import SemanticManager
from synapse.layers.semantic_store import SemanticProjectionStore
from synapse.layers.types import EntityType, MemoryLayer, RelationType, SynapseEdge, SynapseNode, utcnow


class DummyVectorClient:
    enabled = False

    def upsert(self, *args, **kwargs):
        return None

    def search(self, *args, **kwargs):
        return []

    def delete(self, *args, **kwargs):
        return None


def _update_outbox_timestamps(
    db_path: Path,
    operation_id: str,
    *,
    created_at: str,
    next_attempt_at: str | None = None,
    available_at: str | None = None,
) -> None:
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


def _fetch_outbox_row(db_path: Path, operation_id: str) -> sqlite3.Row:
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


def test_outbox_health_ignores_done_only_rows(tmp_path):
    db_path = tmp_path / "semantic.db"
    store = SemanticProjectionStore(db_path)

    operation_id = "vector-op-1"
    store.enqueue_outbox(
        operation_id=operation_id,
        target_backend="vector",
        record_id="node-1",
        op_type="add_entity",
        payload={"id": "node-1"},
        dedupe_key="add_entity:node-1:vector",
    )
    store.mark_outbox_success(operation_id)

    old_timestamp = (utcnow() - timedelta(days=2)).isoformat()
    _update_outbox_timestamps(db_path, operation_id, created_at=old_timestamp)

    health = store.get_outbox_health()
    assert health["vector"]["pending_count"] == 0
    assert health["vector"]["failed_count"] == 0
    assert health["vector"]["lag_seconds"] == 0.0
    assert health["vector"]["oldest_active_at"] is None
    assert health["vector"]["unhealthy"] is False


def test_graph_rate_limit_uses_long_backoff(tmp_path):
    db_path = tmp_path / "semantic.db"
    graphiti = AsyncMock()
    graphiti.add_episode = AsyncMock(side_effect=Exception("429 rate limit exceeded"))
    manager = SemanticManager(
        graphiti_client=graphiti,
        vector_client=DummyVectorClient(),
        db_path=db_path,
    )

    operation_id = "graph-op-1"
    manager.store.enqueue_outbox(
        operation_id=operation_id,
        target_backend="graph",
        record_id="node-1",
        op_type="add_entity",
        payload={
            "id": "node-1",
            "op_type": "add_entity",
            "name": "Node 1",
            "graph_name": "entity_Node 1",
            "episode_body": "Node 1: summary",
            "source_description": "Entity type: concept",
            "created_at": utcnow().isoformat(),
        },
        dedupe_key="add_entity:node-1:graph",
    )

    processed = manager._drain_outbox_backend("graph", limit=5)
    row = _fetch_outbox_row(db_path, operation_id)
    next_attempt_at = manager._parse_datetime(row["next_attempt_at"])
    projector_state = manager.store.get_projector_state("graph")
    assert processed == 1
    assert row["status"] == "retry_wait"
    assert row["retry_count"] == 1
    assert "429" in str(row["last_error"])
    assert row["error_code"] == "RATE_LIMIT"
    assert next_attempt_at is not None
    assert projector_state["circuit_state"] == "paused_by_rate_limit"
    delay_seconds = (next_attempt_at - utcnow()).total_seconds()
    assert 280 <= delay_seconds <= 330


def test_rebuild_graph_projection_is_idempotent(tmp_path):
    db_path = tmp_path / "semantic.db"
    graphiti = AsyncMock()
    graphiti.add_episode = AsyncMock(return_value=None)
    manager = SemanticManager(
        graphiti_client=graphiti,
        vector_client=DummyVectorClient(),
        db_path=db_path,
    )

    now = utcnow()
    node = SynapseNode(
        id="node-1",
        type=EntityType.CONCEPT,
        name="Node 1",
        summary="Summary",
        memory_layer=MemoryLayer.SEMANTIC,
        created_at=now,
        updated_at=now,
    )
    edge = SynapseEdge(
        id="edge-1",
        source_id="node-1",
        target_id="node-2",
        type=RelationType.RELATED_TO,
        valid_at=now,
        created_at=now,
    )
    manager.store.save_node(node)
    manager.store.save_edge(edge, fact_text="node-1 related_to node-2")

    try:
        first = manager.rebuild_graph_projection(dry_run=False)
        second = manager.rebuild_graph_projection(dry_run=False)
        conn = sqlite3.connect(str(db_path))
        try:
            count = conn.execute("SELECT COUNT(*) FROM semantic_outbox").fetchone()[0]
        finally:
            conn.close()
    finally:
        manager.stop_background_processing()

    assert first["affected"] == 2
    assert second["affected"] == 2
    assert count == 2


def test_replay_due_outbox_drains_after_backend_recovers(tmp_path):
    db_path = tmp_path / "semantic.db"
    graphiti = AsyncMock()
    graphiti.add_episode = AsyncMock(side_effect=[
        Exception("429 rate limit exceeded"),
        None,
    ])
    manager = SemanticManager(
        graphiti_client=graphiti,
        vector_client=DummyVectorClient(),
        db_path=db_path,
    )

    operation_id = "graph-op-recover"
    manager.store.enqueue_outbox(
        operation_id=operation_id,
        target_backend="graph",
        record_id="node-1",
        op_type="add_entity",
        payload={
            "id": "node-1",
            "op_type": "add_entity",
            "name": "Recoverable Node",
            "graph_name": "entity_Recoverable Node",
            "episode_body": "Recoverable Node: summary",
            "source_description": "Entity type: concept",
            "created_at": utcnow().isoformat(),
        },
        dedupe_key="add_entity:node-1:graph",
    )

    first = manager.replay_due_outbox(target_backend="graph", dry_run=False)
    failed_row = _fetch_outbox_row(db_path, operation_id)
    _update_outbox_timestamps(
        db_path,
        operation_id,
        created_at=failed_row["created_at"],
        next_attempt_at=(utcnow() - timedelta(seconds=1)).isoformat(),
        available_at=(utcnow() - timedelta(seconds=1)).isoformat(),
    )
    manager.store.update_projector_state(
        "graph",
        circuit_state="paused_by_rate_limit",
        cooldown_until=(utcnow() - timedelta(seconds=1)).isoformat(),
    )
    manager._backend_next_allowed_at["graph"] = 0.0
    second = manager.replay_due_outbox(target_backend="graph", dry_run=False)
    recovered_row = _fetch_outbox_row(db_path, operation_id)
    projector_state = manager.store.get_projector_state("graph")

    assert first["affected"] == 1
    assert failed_row["status"] == "retry_wait"
    assert second["affected"] == 1
    assert recovered_row["status"] == "done"
    assert projector_state["circuit_state"] == "closed"


def test_release_expired_leases_returns_rows_to_pending(tmp_path):
    db_path = tmp_path / "semantic.db"
    store = SemanticProjectionStore(db_path)
    operation_id = "leased-graph-op"
    store.enqueue_outbox(
        operation_id=operation_id,
        target_backend="graph",
        record_id="node-lease",
        op_type="add_entity",
        payload={"id": "node-lease"},
        dedupe_key="add_entity:node-lease:graph",
    )
    leased_rows = store.lease_due_outbox(
        target_backend="graph",
        lease_owner="worker-1",
        limit=1,
        lease_timeout_seconds=300,
    )

    assert len(leased_rows) == 1
    _update_outbox_timestamps(
        db_path,
        operation_id,
        created_at=leased_rows[0]["created_at"],
    )

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            UPDATE semantic_outbox
            SET leased_at = ?, updated_at = ?
            WHERE operation_id = ?
            """,
            (
                (utcnow() - timedelta(minutes=10)).isoformat(),
                (utcnow() - timedelta(minutes=10)).isoformat(),
                operation_id,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    released = store.release_expired_leases(
        target_backend="graph",
        lease_timeout_seconds=300,
    )
    row = _fetch_outbox_row(db_path, operation_id)

    assert released == 1
    assert row["status"] == "pending"
    assert row["lease_owner"] is None
