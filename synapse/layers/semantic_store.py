"""SQLite projection and outbox storage for semantic memory."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from .types import EntityType, MemoryLayer, RelationType, SynapseEdge, SynapseNode, utcnow

DEFAULT_DB_PATH = Path.home() / ".synapse" / "semantic.db"
_DEFAULT_PROJECTOR_BACKENDS = ("graph", "vector")
_RETRYABLE_OUTBOX_STATUSES = ("pending", "retry_wait", "failed")
_ACTIVE_OUTBOX_STATUSES = ("pending", "retry_wait", "failed", "leased")

_nlp_preprocessor = None


def _get_nlp_preprocessor():
    global _nlp_preprocessor
    if _nlp_preprocessor is None:
        try:
            from synapse.nlp.preprocess import get_preprocessor

            _nlp_preprocessor = get_preprocessor()
        except ImportError:
            _nlp_preprocessor = False
    return _nlp_preprocessor if _nlp_preprocessor else None


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


class SemanticProjectionStore:
    """Durable SQLite store for semantic lexical search and outbox state."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DEFAULT_DB_PATH
        self._ensure_db()

    def _ensure_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS semantic_nodes (
                    id TEXT PRIMARY KEY,
                    entity_type TEXT NOT NULL,
                    name TEXT NOT NULL,
                    summary TEXT,
                    indexed_text TEXT NOT NULL,
                    confidence REAL DEFAULT 0.7,
                    decay_score REAL DEFAULT 1.0,
                    access_count INTEGER DEFAULT 0,
                    source_episode TEXT,
                    created_by TEXT DEFAULT 'synapse',
                    user_id TEXT,
                    agent_id TEXT,
                    group_id TEXT,
                    metadata_json TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS semantic_nodes_fts
                USING fts5(record_id UNINDEXED, name, summary, entity_type, indexed_text)
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS semantic_edges (
                    id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    relation_type TEXT NOT NULL,
                    fact_text TEXT,
                    confidence REAL DEFAULT 0.7,
                    source_episode TEXT,
                    metadata_json TEXT DEFAULT '{}',
                    valid_at TEXT NOT NULL,
                    invalid_at TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS semantic_outbox (
                    operation_id TEXT PRIMARY KEY,
                    target_backend TEXT NOT NULL,
                    record_id TEXT NOT NULL,
                    op_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    next_attempt_at TEXT NOT NULL,
                    last_error TEXT,
                    dedupe_key TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            self._ensure_column(conn, "semantic_outbox", "lease_owner TEXT")
            self._ensure_column(conn, "semantic_outbox", "leased_at TEXT")
            self._ensure_column(conn, "semantic_outbox", "available_at TEXT")
            self._ensure_column(conn, "semantic_outbox", "error_code TEXT")
            self._ensure_column(conn, "semantic_outbox", "error_class TEXT")
            self._ensure_column(conn, "semantic_outbox", "projector_version TEXT DEFAULT 'v1'")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS semantic_projector_state (
                    backend TEXT PRIMARY KEY,
                    circuit_state TEXT NOT NULL DEFAULT 'closed',
                    cooldown_until TEXT,
                    pause_reason TEXT,
                    last_error_code TEXT,
                    provider_last_429_at TEXT,
                    last_projected_at TEXT,
                    last_error TEXT,
                    failure_streak INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_semantic_nodes_type ON semantic_nodes(entity_type)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_semantic_outbox_backend ON semantic_outbox(target_backend, status, next_attempt_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_semantic_outbox_available ON semantic_outbox(target_backend, status, available_at)"
            )
            conn.execute(
                """
                UPDATE semantic_outbox
                SET status = 'retry_wait'
                WHERE status = 'failed'
                """
            )
            conn.execute(
                """
                UPDATE semantic_outbox
                SET available_at = COALESCE(available_at, next_attempt_at, created_at),
                    projector_version = COALESCE(NULLIF(projector_version, ''), 'v1')
                """
            )
            # Rebuild the derived lexical index from the SQLite source of truth.
            conn.execute("DELETE FROM semantic_nodes_fts")
            conn.execute(
                """
                INSERT INTO semantic_nodes_fts(record_id, name, summary, entity_type, indexed_text)
                SELECT id, name, COALESCE(summary, ''), entity_type, indexed_text
                FROM semantic_nodes
                """
            )

    def _ensure_column(self, conn: sqlite3.Connection, table_name: str, column_def: str) -> None:
        column_name = column_def.split()[0]
        existing = {
            str(row["name"])
            for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        if column_name not in existing:
            conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_def}")

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _indexed_text(self, *parts: Optional[str]) -> str:
        text = "\n".join(str(part) for part in parts if part)
        preprocessor = _get_nlp_preprocessor()
        if preprocessor:
            return preprocessor.tokenize_for_fts(text)
        return " ".join(text.split())

    def save_node(self, node: SynapseNode, alias_terms: Optional[Iterable[str]] = None) -> None:
        entity_type = node.type.value if hasattr(node.type, "value") else str(node.type)
        memory_layer = node.memory_layer.value if hasattr(node.memory_layer, "value") else str(node.memory_layer)
        metadata = {
            "memory_layer": memory_layer,
        }
        indexed_text = self._indexed_text(node.name, node.summary, entity_type, " ".join(alias_terms or []))
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO semantic_nodes (
                    id, entity_type, name, summary, indexed_text, confidence, decay_score,
                    access_count, source_episode, created_by, user_id, agent_id, group_id,
                    metadata_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    entity_type = excluded.entity_type,
                    name = excluded.name,
                    summary = excluded.summary,
                    indexed_text = excluded.indexed_text,
                    confidence = excluded.confidence,
                    decay_score = excluded.decay_score,
                    access_count = excluded.access_count,
                    source_episode = excluded.source_episode,
                    created_by = excluded.created_by,
                    user_id = excluded.user_id,
                    agent_id = excluded.agent_id,
                    group_id = excluded.group_id,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at
                """,
                (
                    node.id,
                    entity_type,
                    node.name,
                    node.summary,
                    indexed_text,
                    node.confidence,
                    node.decay_score,
                    node.access_count,
                    node.source_episode,
                    node.created_by,
                    node.user_id,
                    node.agent_id,
                    node.chat_id,
                    json.dumps(metadata, ensure_ascii=False),
                    node.created_at.isoformat(),
                    node.updated_at.isoformat(),
                ),
            )
            conn.execute("DELETE FROM semantic_nodes_fts WHERE record_id = ?", (node.id,))
            conn.execute(
                """
                INSERT INTO semantic_nodes_fts(record_id, name, summary, entity_type, indexed_text)
                VALUES (?, ?, ?, ?, ?)
                """,
                (node.id, node.name, node.summary or "", entity_type, indexed_text),
            )

    def save_edge(self, edge: SynapseEdge, fact_text: Optional[str] = None) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO semantic_edges (
                    id, source_id, target_id, relation_type, fact_text, confidence,
                    source_episode, metadata_json, valid_at, invalid_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    source_id = excluded.source_id,
                    target_id = excluded.target_id,
                    relation_type = excluded.relation_type,
                    fact_text = excluded.fact_text,
                    confidence = excluded.confidence,
                    source_episode = excluded.source_episode,
                    metadata_json = excluded.metadata_json,
                    valid_at = excluded.valid_at,
                    invalid_at = excluded.invalid_at
                """,
                (
                    edge.id,
                    edge.source_id,
                    edge.target_id,
                    edge.type.value if hasattr(edge.type, "value") else edge.type,
                    fact_text,
                    edge.confidence,
                    edge.source_episode,
                    json.dumps(edge.metadata or {}, ensure_ascii=False),
                    edge.valid_at.isoformat(),
                    edge.invalid_at.isoformat() if edge.invalid_at else None,
                    utcnow().isoformat(),
                ),
            )

    def get_node(self, node_id: str) -> Optional[SynapseNode]:
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM semantic_nodes WHERE id = ?", (node_id,))
            row = cursor.fetchone()
        if row is None:
            return None
        metadata = json.loads(row["metadata_json"] or "{}")
        return SynapseNode(
            id=row["id"],
            type=EntityType(row["entity_type"]),
            name=row["name"],
            summary=row["summary"],
            memory_layer=MemoryLayer(metadata.get("memory_layer", MemoryLayer.SEMANTIC.value)),
            confidence=float(row["confidence"]),
            decay_score=float(row["decay_score"]),
            access_count=int(row["access_count"]),
            created_at=_parse_datetime(row["created_at"]) or utcnow(),
            updated_at=_parse_datetime(row["updated_at"]) or utcnow(),
            source_episode=row["source_episode"],
            created_by=row["created_by"] or "synapse",
            user_id=row["user_id"],
            agent_id=row["agent_id"],
        )

    def fetch_lexical_candidates(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        query_text = self._indexed_text(query)
        rows = []
        with self._get_connection() as conn:
            try:
                cursor = conn.execute(
                    """
                    SELECT n.*, bm25(semantic_nodes_fts) AS fts_rank
                    FROM semantic_nodes n
                    JOIN semantic_nodes_fts ON n.id = semantic_nodes_fts.record_id
                    WHERE semantic_nodes_fts MATCH ?
                    ORDER BY fts_rank ASC, n.updated_at DESC
                    LIMIT ?
                    """,
                    (query_text, limit),
                )
                rows = cursor.fetchall()
            except sqlite3.OperationalError:
                rows = []

            if not rows:
                cursor = conn.execute(
                    """
                    SELECT *, 0.0 AS fts_rank
                    FROM semantic_nodes
                    WHERE name LIKE ? OR summary LIKE ?
                    ORDER BY updated_at DESC
                    LIMIT ?
                    """,
                    (f"%{query}%", f"%{query}%", limit),
                )
                rows = cursor.fetchall()

        query_terms = {term for term in query_text.split() if term}
        results: List[Dict[str, Any]] = []
        for rank, row in enumerate(rows, start=1):
            indexed_terms = {term for term in str(row["indexed_text"]).split() if term}
            overlap = len(query_terms.intersection(indexed_terms)) / max(1, len(query_terms)) if query_terms else 0.0
            exact_match = query.lower() in row["name"].lower() or query.lower() in (row["summary"] or "").lower()
            results.append(
                {
                    "record_id": row["id"],
                    "layer": MemoryLayer.SEMANTIC,
                    "backend": "lexical",
                    "backend_score": min(1.0, 0.65 * overlap + 0.35 * (1.0 if exact_match else 0.0)),
                    "rank": rank,
                    "exact_match": exact_match,
                    "matched_terms": [query] if exact_match else list(query_terms),
                    "match_reasons": ["fts" if row["indexed_text"] else "like"],
                    "freshness": max(0.0, min(1.0, float(row["decay_score"]))),
                    "usage_signal": min(1.0, int(row["access_count"]) / 10.0),
                    "payload": {
                        "uuid": row["id"],
                        "layer": MemoryLayer.SEMANTIC.value,
                        "name": row["name"],
                        "content": row["summary"] or "",
                        "metadata": {
                            "entity_type": row["entity_type"],
                            "confidence": float(row["confidence"]),
                            "source_episode": row["source_episode"],
                        },
                        "source": "semantic",
                        "indexed_text": row["indexed_text"],
                    },
                }
            )
        return results

    def enqueue_outbox(
        self,
        *,
        operation_id: str,
        target_backend: str,
        record_id: str,
        op_type: str,
        payload: Dict[str, Any],
        dedupe_key: str,
        status: str = "pending",
        available_at: Optional[str] = None,
        error_code: Optional[str] = None,
        error_class: Optional[str] = None,
        projector_version: str = "v2",
    ) -> None:
        now = utcnow().isoformat()
        scheduled_at = available_at or now
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO semantic_outbox (
                    operation_id, target_backend, record_id, op_type, payload_json,
                    status, retry_count, next_attempt_at, available_at, last_error, error_code, error_class,
                    lease_owner, leased_at, dedupe_key, projector_version, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, NULL, ?, ?, NULL, NULL, ?, ?, ?, ?)
                ON CONFLICT(dedupe_key) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    status = excluded.status,
                    next_attempt_at = excluded.next_attempt_at,
                    available_at = excluded.available_at,
                    last_error = NULL,
                    error_code = NULL,
                    error_class = NULL,
                    lease_owner = NULL,
                    leased_at = NULL,
                    retry_count = CASE
                        WHEN excluded.status = 'pending' THEN 0
                        ELSE semantic_outbox.retry_count
                    END,
                    projector_version = excluded.projector_version,
                    updated_at = excluded.updated_at
                """,
                (
                    operation_id,
                    target_backend,
                    record_id,
                    op_type,
                    json.dumps(payload, ensure_ascii=False, default=str),
                    status,
                    scheduled_at,
                    scheduled_at,
                    error_code,
                    error_class,
                    dedupe_key,
                    projector_version,
                    now,
                    now,
                ),
            )

    def fetch_pending_outbox(self, target_backend: str, limit: int = 20) -> List[sqlite3.Row]:
        now = utcnow().isoformat()
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM semantic_outbox
                WHERE target_backend = ?
                  AND status IN ('pending', 'retry_wait', 'failed')
                  AND COALESCE(available_at, next_attempt_at, created_at) <= ?
                ORDER BY created_at ASC
                LIMIT ?
                """,
                (target_backend, now, limit),
            )
            return cursor.fetchall()

    def release_expired_leases(
        self,
        *,
        lease_timeout_seconds: int,
        target_backend: Optional[str] = None,
    ) -> int:
        cutoff = datetime.fromtimestamp(
            utcnow().timestamp() - max(1, int(lease_timeout_seconds)),
            tz=timezone.utc,
        ).isoformat()
        clauses = ["status = 'leased'", "leased_at IS NOT NULL", "leased_at <= ?"]
        params: List[Any] = [cutoff]
        if target_backend is not None:
            clauses.append("target_backend = ?")
            params.append(target_backend)
        sql = f"""
            UPDATE semantic_outbox
            SET status = 'pending',
                lease_owner = NULL,
                leased_at = NULL,
                available_at = COALESCE(available_at, next_attempt_at, created_at),
                updated_at = ?
            WHERE {' AND '.join(clauses)}
        """
        params = [utcnow().isoformat(), *params]
        with self._get_connection() as conn:
            cursor = conn.execute(sql, params)
            return int(cursor.rowcount or 0)

    def lease_due_outbox(
        self,
        *,
        target_backend: str,
        lease_owner: str,
        limit: int = 20,
        lease_timeout_seconds: int = 300,
    ) -> List[sqlite3.Row]:
        self.release_expired_leases(
            lease_timeout_seconds=lease_timeout_seconds,
            target_backend=target_backend,
        )
        now = utcnow().isoformat()
        with self._get_connection() as conn:
            due_rows = conn.execute(
                """
                SELECT operation_id
                FROM semantic_outbox
                WHERE target_backend = ?
                  AND status IN ('pending', 'retry_wait', 'failed')
                  AND COALESCE(available_at, next_attempt_at, created_at) <= ?
                ORDER BY created_at ASC
                LIMIT ?
                """,
                (target_backend, now, limit),
            ).fetchall()
            operation_ids = [str(row["operation_id"]) for row in due_rows if row["operation_id"]]
            if not operation_ids:
                return []

            placeholders = ", ".join("?" for _ in operation_ids)
            conn.execute(
                f"""
                UPDATE semantic_outbox
                SET status = 'leased',
                    lease_owner = ?,
                    leased_at = ?,
                    updated_at = ?
                WHERE operation_id IN ({placeholders})
                """,
                [lease_owner, now, now, *operation_ids],
            )
            rows = conn.execute(
                f"""
                SELECT *
                FROM semantic_outbox
                WHERE operation_id IN ({placeholders})
                ORDER BY created_at ASC
                """,
                operation_ids,
            ).fetchall()
        return rows

    def count_outbox_rows(
        self,
        *,
        target_backend: Optional[str] = None,
        statuses: Optional[Sequence[str]] = None,
        due_only: bool = False,
    ) -> int:
        clauses = ["1 = 1"]
        params: List[Any] = []
        normalized_statuses = [str(status) for status in (statuses or []) if status]

        if target_backend is not None:
            clauses.append("target_backend = ?")
            params.append(target_backend)

        if normalized_statuses:
            placeholders = ", ".join("?" for _ in normalized_statuses)
            clauses.append(f"status IN ({placeholders})")
            params.extend(normalized_statuses)

        if due_only:
            clauses.append("COALESCE(available_at, next_attempt_at, created_at) <= ?")
            params.append(utcnow().isoformat())

        sql = f"SELECT COUNT(*) AS count FROM semantic_outbox WHERE {' AND '.join(clauses)}"
        with self._get_connection() as conn:
            row = conn.execute(sql, params).fetchone()
        return int(row["count"] if row is not None else 0)

    def list_outbox_backends(self) -> List[str]:
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT DISTINCT target_backend FROM semantic_outbox ORDER BY target_backend"
            ).fetchall()
        return [str(row["target_backend"]) for row in rows if row["target_backend"]]

    def mark_outbox_success(self, operation_id: str) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE semantic_outbox
                SET status = 'done',
                    updated_at = ?,
                    last_error = NULL,
                    error_code = NULL,
                    error_class = NULL,
                    lease_owner = NULL,
                    leased_at = NULL,
                    available_at = ?
                WHERE operation_id = ?
                """,
                (utcnow().isoformat(), utcnow().isoformat(), operation_id),
            )

    def mark_outbox_retry(
        self,
        operation_id: str,
        error: str,
        retry_count: int,
        *,
        delay_seconds: Optional[int] = None,
        error_code: Optional[str] = None,
        error_class: Optional[str] = None,
    ) -> None:
        delay_seconds = delay_seconds if delay_seconds is not None else min(300, max(15, 15 * (2 ** min(retry_count, 4))))
        next_attempt = utcnow().timestamp() + delay_seconds
        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE semantic_outbox
                SET status = 'retry_wait',
                    retry_count = ?,
                    next_attempt_at = ?,
                    available_at = ?,
                    last_error = ?,
                    error_code = ?,
                    error_class = ?,
                    lease_owner = NULL,
                    leased_at = NULL,
                    updated_at = ?
                WHERE operation_id = ?
                """,
                (
                    retry_count,
                    datetime.fromtimestamp(next_attempt, tz=timezone.utc).isoformat(),
                    datetime.fromtimestamp(next_attempt, tz=timezone.utc).isoformat(),
                    error[:500],
                    error_code,
                    error_class,
                    utcnow().isoformat(),
                    operation_id,
                ),
            )

    def mark_outbox_failure(
        self,
        operation_id: str,
        error: str,
        retry_count: int,
        *,
        delay_seconds: Optional[int] = None,
        error_code: Optional[str] = None,
        error_class: Optional[str] = None,
    ) -> None:
        """Backward-compatible alias for retryable failures."""
        self.mark_outbox_retry(
            operation_id,
            error,
            retry_count,
            delay_seconds=delay_seconds,
            error_code=error_code,
            error_class=error_class,
        )

    def mark_outbox_dead_letter(
        self,
        operation_id: str,
        error: str,
        retry_count: int,
        *,
        error_code: Optional[str] = None,
        error_class: Optional[str] = None,
    ) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE semantic_outbox
                SET status = 'dead_letter',
                    retry_count = ?,
                    last_error = ?,
                    error_code = ?,
                    error_class = ?,
                    lease_owner = NULL,
                    leased_at = NULL,
                    available_at = NULL,
                    updated_at = ?
                WHERE operation_id = ?
                """,
                (
                    retry_count,
                    error[:500],
                    error_code,
                    error_class,
                    utcnow().isoformat(),
                    operation_id,
                ),
            )

    def requeue_outbox_rows(
        self,
        *,
        target_backend: str,
        source_status: str,
        reset_retry_count: bool = False,
    ) -> int:
        now = utcnow().isoformat()
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                UPDATE semantic_outbox
                SET status = 'pending',
                    retry_count = CASE WHEN ? THEN 0 ELSE retry_count END,
                    available_at = ?,
                    next_attempt_at = ?,
                    last_error = NULL,
                    error_code = NULL,
                    error_class = NULL,
                    lease_owner = NULL,
                    leased_at = NULL,
                    updated_at = ?
                WHERE target_backend = ?
                  AND status = ?
                """,
                (
                    1 if reset_retry_count else 0,
                    now,
                    now,
                    now,
                    target_backend,
                    source_status,
                ),
            )
            return int(cursor.rowcount or 0)

    def get_projector_state(self, backend: str) -> Dict[str, Any]:
        with self._get_connection() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM semantic_projector_state
                WHERE backend = ?
                """,
                (backend,),
            ).fetchone()
        if row is None:
            return {
                "backend": backend,
                "circuit_state": "closed",
                "cooldown_until": None,
                "pause_reason": None,
                "last_error_code": None,
                "provider_last_429_at": None,
                "last_projected_at": None,
                "last_error": None,
                "failure_streak": 0,
                "updated_at": None,
            }
        return dict(row)

    def update_projector_state(self, backend: str, **fields: Any) -> Dict[str, Any]:
        state = self.get_projector_state(backend)
        state.update({key: value for key, value in fields.items()})
        state["backend"] = backend
        state["updated_at"] = utcnow().isoformat()
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO semantic_projector_state (
                    backend, circuit_state, cooldown_until, pause_reason, last_error_code,
                    provider_last_429_at, last_projected_at, last_error, failure_streak, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(backend) DO UPDATE SET
                    circuit_state = excluded.circuit_state,
                    cooldown_until = excluded.cooldown_until,
                    pause_reason = excluded.pause_reason,
                    last_error_code = excluded.last_error_code,
                    provider_last_429_at = excluded.provider_last_429_at,
                    last_projected_at = excluded.last_projected_at,
                    last_error = excluded.last_error,
                    failure_streak = excluded.failure_streak,
                    updated_at = excluded.updated_at
                """,
                (
                    backend,
                    state.get("circuit_state", "closed"),
                    state.get("cooldown_until"),
                    state.get("pause_reason"),
                    state.get("last_error_code"),
                    state.get("provider_last_429_at"),
                    state.get("last_projected_at"),
                    state.get("last_error"),
                    int(state.get("failure_streak") or 0),
                    state["updated_at"],
                ),
            )
        return state

    def get_outbox_health(self) -> Dict[str, Dict[str, Any]]:
        now = utcnow()
        health: Dict[str, Dict[str, Any]] = {}
        with self._get_connection() as conn:
            backends = sorted(
                set(_DEFAULT_PROJECTOR_BACKENDS).union(
                    {
                        str(row["target_backend"])
                        for row in conn.execute(
                            "SELECT DISTINCT target_backend FROM semantic_outbox ORDER BY target_backend"
                        ).fetchall()
                        if row["target_backend"]
                    }
                ).union(
                    {
                        str(row["backend"])
                        for row in conn.execute(
                            "SELECT DISTINCT backend FROM semantic_projector_state ORDER BY backend"
                        ).fetchall()
                        if row["backend"]
                    }
                )
            )
            for backend in backends:
                active_row = conn.execute(
                    """
                    SELECT MAX(retry_count) AS max_retry_count,
                           MIN(created_at) AS oldest_active_at,
                           MIN(COALESCE(available_at, next_attempt_at, created_at)) AS next_attempt_at,
                           MIN(CASE
                               WHEN status IN ('pending', 'retry_wait', 'failed')
                                    AND COALESCE(available_at, next_attempt_at, created_at) <= ?
                               THEN COALESCE(available_at, next_attempt_at, created_at)
                           END) AS oldest_due_at,
                           SUM(CASE WHEN status IN ('retry_wait', 'failed') THEN 1 ELSE 0 END) AS failed_count,
                           SUM(CASE WHEN status = 'dead_letter' THEN 1 ELSE 0 END) AS dead_letter_count,
                           SUM(CASE WHEN status = 'leased' THEN 1 ELSE 0 END) AS leased_count,
                           SUM(CASE
                               WHEN status IN ('pending', 'retry_wait', 'failed')
                                    AND COALESCE(available_at, next_attempt_at, created_at) <= ?
                               THEN 1 ELSE 0
                           END) AS due_count,
                           SUM(CASE WHEN status IN ('pending', 'retry_wait', 'failed') THEN 1 ELSE 0 END) AS pending_count
                    FROM semantic_outbox
                    WHERE target_backend = ?
                      AND status IN ('pending', 'retry_wait', 'failed', 'leased', 'dead_letter')
                    """,
                    (now.isoformat(), now.isoformat(), backend),
                ).fetchone()
                error_row = conn.execute(
                    """
                    SELECT last_error, error_code
                    FROM semantic_outbox
                    WHERE target_backend = ?
                      AND status IN ('retry_wait', 'failed', 'dead_letter')
                      AND last_error IS NOT NULL
                    ORDER BY updated_at DESC
                    LIMIT 1
                    """,
                    (backend,),
                ).fetchone()
                projector_state = self.get_projector_state(backend)
                oldest_active = _parse_datetime(active_row["oldest_active_at"]) if active_row else None
                next_attempt = _parse_datetime(active_row["next_attempt_at"]) if active_row else None
                oldest_due = _parse_datetime(active_row["oldest_due_at"]) if active_row else None
                pending_count = int(active_row["pending_count"] or 0) if active_row else 0
                failed_count = int(active_row["failed_count"] or 0) if active_row else 0
                due_count = int(active_row["due_count"] or 0) if active_row else 0
                dead_letter_count = int(active_row["dead_letter_count"] or 0) if active_row else 0
                leased_count = int(active_row["leased_count"] or 0) if active_row else 0
                max_retry_count = int(active_row["max_retry_count"] or 0) if active_row else 0
                lag_anchor = oldest_due or oldest_active
                lag_seconds = max(0.0, (now - lag_anchor).total_seconds()) if lag_anchor else 0.0
                last_error = str(error_row["last_error"]) if error_row and error_row["last_error"] else None
                last_error_code = (
                    str(projector_state.get("last_error_code"))
                    if projector_state.get("last_error_code")
                    else str(error_row["error_code"])
                    if error_row and error_row["error_code"]
                    else None
                )
                circuit_state = str(projector_state.get("circuit_state") or "closed")
                unhealthy = (
                    dead_letter_count > 0
                    or circuit_state not in {"closed", "half_open"}
                    or (pending_count > 0 and (max_retry_count > 3 or lag_seconds > 60.0))
                )
                health[backend] = {
                    "max_retry_count": max_retry_count,
                    "failed_count": failed_count,
                    "pending_count": pending_count,
                    "due_count": due_count,
                    "dead_letter_count": dead_letter_count,
                    "leased_count": leased_count,
                    "lag_seconds": lag_seconds,
                    "unhealthy": unhealthy,
                    "oldest_active_at": oldest_active.isoformat() if oldest_active else None,
                    "oldest_due_at": oldest_due.isoformat() if oldest_due else None,
                    "next_attempt_at": next_attempt.isoformat() if next_attempt else None,
                    "last_error_excerpt": last_error[:200] if last_error else None,
                    "circuit_state": circuit_state,
                    "cooldown_until": projector_state.get("cooldown_until"),
                    "pause_reason": projector_state.get("pause_reason"),
                    "last_error_code": last_error_code,
                    "provider_last_429_at": projector_state.get("provider_last_429_at"),
                    "last_projected_at": projector_state.get("last_projected_at"),
                }
        return health

    def fetch_graph_rebuild_nodes(self, limit: Optional[int] = None) -> List[sqlite3.Row]:
        sql = "SELECT * FROM semantic_nodes ORDER BY updated_at ASC"
        params: List[Any] = []
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        with self._get_connection() as conn:
            return conn.execute(sql, params).fetchall()

    def fetch_graph_rebuild_edges(self, limit: Optional[int] = None) -> List[sqlite3.Row]:
        sql = "SELECT * FROM semantic_edges ORDER BY created_at ASC"
        params: List[Any] = []
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        with self._get_connection() as conn:
            return conn.execute(sql, params).fetchall()

    def get_stats(self) -> Dict[str, Any]:
        with self._get_connection() as conn:
            node_count = conn.execute("SELECT count(*) AS count FROM semantic_nodes").fetchone()["count"]
            edge_count = conn.execute("SELECT count(*) AS count FROM semantic_edges").fetchone()["count"]
        return {
            "nodes": int(node_count or 0),
            "edges": int(edge_count or 0),
            "outbox": self.get_outbox_health(),
        }
