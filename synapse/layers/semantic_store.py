"""SQLite projection and outbox storage for semantic memory."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .types import EntityType, MemoryLayer, RelationType, SynapseEdge, SynapseNode, utcnow

DEFAULT_DB_PATH = Path.home() / ".synapse" / "semantic.db"

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
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_semantic_nodes_type ON semantic_nodes(entity_type)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_semantic_outbox_backend ON semantic_outbox(target_backend, status, next_attempt_at)"
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
                    None,
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
    ) -> None:
        now = utcnow().isoformat()
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO semantic_outbox (
                    operation_id, target_backend, record_id, op_type, payload_json,
                    status, retry_count, next_attempt_at, last_error, dedupe_key, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 'pending', 0, ?, NULL, ?, ?, ?)
                ON CONFLICT(dedupe_key) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    status = 'pending',
                    next_attempt_at = excluded.next_attempt_at,
                    updated_at = excluded.updated_at
                """,
                (
                    operation_id,
                    target_backend,
                    record_id,
                    op_type,
                    json.dumps(payload, ensure_ascii=False, default=str),
                    now,
                    dedupe_key,
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
                  AND status IN ('pending', 'failed')
                  AND next_attempt_at <= ?
                ORDER BY created_at ASC
                LIMIT ?
                """,
                (target_backend, now, limit),
            )
            return cursor.fetchall()

    def mark_outbox_success(self, operation_id: str) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE semantic_outbox
                SET status = 'done', updated_at = ?, last_error = NULL
                WHERE operation_id = ?
                """,
                (utcnow().isoformat(), operation_id),
            )

    def mark_outbox_failure(self, operation_id: str, error: str, retry_count: int) -> None:
        delay_seconds = min(300, max(15, 15 * (2 ** min(retry_count, 4))))
        next_attempt = utcnow().timestamp() + delay_seconds
        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE semantic_outbox
                SET status = 'failed',
                    retry_count = ?,
                    next_attempt_at = ?,
                    last_error = ?,
                    updated_at = ?
                WHERE operation_id = ?
                """,
                (
                    retry_count,
                    datetime.fromtimestamp(next_attempt, tz=timezone.utc).isoformat(),
                    error[:500],
                    utcnow().isoformat(),
                    operation_id,
                ),
            )

    def get_outbox_health(self) -> Dict[str, Dict[str, Any]]:
        now = utcnow()
        health: Dict[str, Dict[str, Any]] = {}
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT target_backend,
                       MAX(retry_count) AS max_retry_count,
                       MIN(created_at) AS oldest_created_at,
                       SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed_count,
                       SUM(CASE WHEN status IN ('pending', 'failed') THEN 1 ELSE 0 END) AS pending_count
                FROM semantic_outbox
                GROUP BY target_backend
                """
            )
            rows = cursor.fetchall()
        for row in rows:
            oldest = _parse_datetime(row["oldest_created_at"])
            lag_seconds = max(0.0, (now - oldest).total_seconds()) if oldest else 0.0
            health[str(row["target_backend"])] = {
                "max_retry_count": int(row["max_retry_count"] or 0),
                "failed_count": int(row["failed_count"] or 0),
                "pending_count": int(row["pending_count"] or 0),
                "lag_seconds": lag_seconds,
                "unhealthy": int(row["max_retry_count"] or 0) > 3 or lag_seconds > 60.0,
            }
        return health

    def get_stats(self) -> Dict[str, Any]:
        with self._get_connection() as conn:
            node_count = conn.execute("SELECT count(*) AS count FROM semantic_nodes").fetchone()["count"]
            edge_count = conn.execute("SELECT count(*) AS count FROM semantic_edges").fetchone()["count"]
        return {
            "nodes": int(node_count or 0),
            "edges": int(edge_count or 0),
            "outbox": self.get_outbox_health(),
        }
