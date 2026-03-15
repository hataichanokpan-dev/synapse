"""
Layer 2: Procedural Memory

How-to patterns and procedures.
SLOW DECAY - λ = 0.005, half-life ~139 days

Storage:
- Graph: (Procedure) nodes with trigger edges
- Vector: Qdrant for semantic search of triggers

Thai NLP Integration:
- Triggers are preprocessed for Thai tokenization before FTS5
- Search queries are tokenized for better matching
- Qdrant indexing applies Thai-aware preprocessing before vectorization
"""

import json
import logging
import sqlite3
import uuid
from pathlib import Path
from typing import Optional, List
from contextlib import contextmanager
from datetime import datetime

from synapse.storage import QdrantClient

from .types import ProceduralMemory, MemoryLayer, utcnow
from .decay import compute_decay_score

logger = logging.getLogger(__name__)

# Lazy import for Thai NLP
_nlp_preprocessor = None


def _get_nlp_preprocessor():
    """Get NLP preprocessor (lazy import)."""
    global _nlp_preprocessor
    if _nlp_preprocessor is None:
        try:
            from synapse.nlp.preprocess import get_preprocessor
            _nlp_preprocessor = get_preprocessor()
        except ImportError:
            _nlp_preprocessor = False  # Mark as unavailable
    return _nlp_preprocessor if _nlp_preprocessor else None


# Default database path
DEFAULT_DB_PATH = Path.home() / ".synapse" / "procedural.db"
DEFAULT_COLLECTION_NAME = "procedural_memory"


class ProceduralManager:
    """
    Manager for Layer 2: Procedural Memory.

    Procedures decay slowly (λ = 0.005, half-life ~139 days).
    Success count boosts decay score.
    """

    def __init__(
        self,
        db_path: Optional[Path] = None,
        vector_client: Optional[QdrantClient] = None,
        collection_name: str = DEFAULT_COLLECTION_NAME,
    ):
        """
        Initialize Procedural Memory Manager.

        Args:
            db_path: Path to SQLite database (default: ~/.synapse/procedural.db)
        """
        self.db_path = db_path or DEFAULT_DB_PATH
        self.vector_client = vector_client or QdrantClient()
        self.collection_name = collection_name
        self._vector_warning_emitted = False
        self._ensure_db()

    def _ensure_db(self) -> None:
        """Create database and tables if not exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS procedures (
                    id TEXT PRIMARY KEY,
                    trigger TEXT NOT NULL,
                    trigger_fts TEXT,
                    procedure TEXT NOT NULL,
                    source TEXT DEFAULT 'explicit',
                    success_count INTEGER DEFAULT 0,
                    last_used TEXT,
                    topics TEXT DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    decay_score REAL DEFAULT 1.0
                )
            """)

            # Index for trigger search
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_procedures_trigger
                ON procedures(trigger)
            """)

            # FTS5 for full-text search on triggers (using tokenized version)
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS procedures_fts
                USING fts5(trigger_fts, content='procedures', content_rowid='rowid')
            """)

            # Migration: Add trigger_fts column if not exists
            try:
                conn.execute("ALTER TABLE procedures ADD COLUMN trigger_fts TEXT")
            except sqlite3.OperationalError:
                pass  # Column already exists

    @contextmanager
    def _get_connection(self):
        """Get database connection with context manager."""
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

    def _warn_vector_issue(self, exc: Exception) -> None:
        """Log a single warning when Qdrant is unavailable."""
        if self._vector_warning_emitted:
            return

        logger.warning("Procedural memory Qdrant integration unavailable: %s", exc)
        self._vector_warning_emitted = True

    def _get_procedure_row(self, procedure_id: str) -> Optional[sqlite3.Row]:
        """Fetch a single procedure row."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM procedures WHERE id = ?",
                (procedure_id,),
            )
            return cursor.fetchone()

    def _get_procedure_rows(self, procedure_ids: List[str]) -> dict[str, sqlite3.Row]:
        """Fetch multiple procedure rows keyed by ID."""
        if not procedure_ids:
            return {}

        placeholders = ", ".join("?" for _ in procedure_ids)
        with self._get_connection() as conn:
            cursor = conn.execute(
                f"SELECT * FROM procedures WHERE id IN ({placeholders})",
                procedure_ids,
            )
            rows = cursor.fetchall()

        return {str(row["id"]): row for row in rows}

    def _row_to_procedure(self, row: sqlite3.Row) -> ProceduralMemory:
        """Convert a SQLite row into a ProceduralMemory model."""
        return ProceduralMemory(
            id=row["id"],
            trigger=row["trigger"],
            procedure=json.loads(row["procedure"]),
            source=row["source"],
            success_count=row["success_count"],
            last_used=self._parse_datetime(row["last_used"]) if row["last_used"] else None,
            topics=json.loads(row["topics"]),
        )

    def _index_procedure(
        self,
        procedure_id: str,
        trigger: str,
        steps: List[str],
        source: str,
        topics: List[str],
        success_count: int,
        last_used: Optional[str | datetime],
        created_at: datetime,
        updated_at: datetime,
        decay_score: float,
    ) -> None:
        """Store procedure text and metadata in Qdrant."""
        if isinstance(last_used, datetime):
            last_used_value = last_used.isoformat()
        else:
            last_used_value = last_used

        try:
            self.vector_client.upsert(
                collection_name=self.collection_name,
                points=[
                    {
                        "id": procedure_id,
                        "text": "\n".join([trigger, *steps]),
                        "payload": {
                            "procedure_id": procedure_id,
                            "trigger": trigger,
                            "steps": steps,
                            "source": source,
                            "topics": topics,
                            "success_count": success_count,
                            "last_used": last_used_value,
                            "created_at": created_at.isoformat(),
                            "updated_at": updated_at.isoformat(),
                            "decay_score": decay_score,
                            "memory_layer": MemoryLayer.PROCEDURAL.value,
                        },
                    }
                ],
            )
        except Exception as exc:
            self._warn_vector_issue(exc)

    def _index_procedure_row(self, row: sqlite3.Row) -> None:
        """Re-index a persisted procedure row into Qdrant."""
        self._index_procedure(
            procedure_id=str(row["id"]),
            trigger=row["trigger"],
            steps=json.loads(row["procedure"]),
            source=row["source"],
            topics=json.loads(row["topics"]),
            success_count=row["success_count"],
            last_used=row["last_used"],
            created_at=self._parse_datetime(row["created_at"]),
            updated_at=self._parse_datetime(row["updated_at"]),
            decay_score=float(row["decay_score"]),
        )

    def _delete_from_vector_store(self, procedure_id: str) -> None:
        """Delete a procedure point from Qdrant."""
        try:
            self.vector_client.delete(
                collection_name=self.collection_name,
                ids=[procedure_id],
            )
        except Exception as exc:
            self._warn_vector_issue(exc)

    def _find_procedure_vector(
        self,
        trigger: str,
        limit: int,
        min_score: float,
    ) -> Optional[List[ProceduralMemory]]:
        """Try semantic retrieval from Qdrant. Returns None when unavailable."""
        try:
            results = self.vector_client.search(
                collection_name=self.collection_name,
                query_text=trigger,
                limit=max(limit * 3, limit),
            )
        except Exception as exc:
            self._warn_vector_issue(exc)
            return None

        if not results:
            return []

        rows_by_id = self._get_procedure_rows([result["id"] for result in results])
        procedures = []
        now = utcnow()

        for result in results:
            row = rows_by_id.get(result["id"])
            if row is None:
                continue

            decay_score = compute_decay_score(
                updated_at=self._parse_datetime(row["updated_at"]),
                access_count=row["success_count"],
                memory_layer=MemoryLayer.PROCEDURAL,
                now=now,
            )

            if decay_score >= min_score:
                procedures.append(self._row_to_procedure(row))

            if len(procedures) >= limit:
                break

        return procedures

    def learn_procedure(
        self,
        trigger: str,
        procedure: List[str],
        source: str = "explicit",
        topics: Optional[List[str]] = None,
        preprocess: bool = True,
    ) -> ProceduralMemory:
        """
        Learn a new procedure.

        Args:
            trigger: When to activate this procedure
            procedure: List of steps to execute
            source: How this was learned (explicit | correction | repeated_pattern)
            topics: Related topics
            preprocess: Apply Thai NLP tokenization for FTS

        Returns:
            Created ProceduralMemory
        """
        now = utcnow()
        proc_id = str(uuid.uuid4())

        # Tokenize trigger for FTS5 (especially for Thai)
        trigger_fts = trigger
        if preprocess:
            preprocessor = _get_nlp_preprocessor()
            if preprocessor:
                trigger_fts = preprocessor.tokenize_for_fts(trigger)

        proc = ProceduralMemory(
            id=proc_id,
            trigger=trigger,
            procedure=procedure,
            source=source,
            success_count=0,
            last_used=None,
            topics=topics or [],
        )

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO procedures (
                    id, trigger, trigger_fts, procedure, source, success_count, last_used,
                    topics, created_at, updated_at, decay_score
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1.0)
                """,
                (
                    proc_id,
                    trigger,
                    trigger_fts,
                    json.dumps(procedure),
                    source,
                    0,
                    None,
                    json.dumps(topics or []),
                    now.isoformat(),
                    now.isoformat(),
                )
            )

        self._index_procedure(
            procedure_id=proc_id,
            trigger=trigger,
            steps=procedure,
            source=source,
            topics=topics or [],
            success_count=0,
            last_used=None,
            created_at=now,
            updated_at=now,
            decay_score=1.0,
        )

        return proc

    def find_procedure(
        self,
        trigger: str,
        limit: int = 5,
        min_score: float = 0.1,
        preprocess: bool = True,
    ) -> List[ProceduralMemory]:
        """
        Find procedures matching a trigger.

        Uses FTS5 for full-text search on triggers.
        Thai triggers are tokenized for better FTS5 matching.

        Args:
            trigger: Search query
            limit: Maximum results
            min_score: Minimum decay score threshold
            preprocess: Apply Thai NLP preprocessing

        Returns:
            List of matching ProceduralMemory
        """
        vector_results = self._find_procedure_vector(trigger, limit, min_score)
        if vector_results is not None:
            return vector_results

        procedures = []
        now = utcnow()

        # Preprocess trigger for Thai
        search_query = trigger
        if preprocess:
            preprocessor = _get_nlp_preprocessor()
            if preprocessor:
                search_query = preprocessor.tokenize_for_fts(trigger)

        with self._get_connection() as conn:
            # Try FTS5 search first
            try:
                cursor = conn.execute(
                    """
                    SELECT p.* FROM procedures p
                    JOIN procedures_fts fts ON p.rowid = fts.rowid
                    WHERE procedures_fts MATCH ?
                    ORDER BY p.decay_score DESC, p.success_count DESC
                    LIMIT ?
                    """,
                    (search_query, limit)
                )
                rows = cursor.fetchall()
            except sqlite3.OperationalError:
                # FTS5 might not have data yet, fallback to LIKE
                cursor = conn.execute(
                    """
                    SELECT * FROM procedures
                    WHERE trigger LIKE ?
                    ORDER BY decay_score DESC, success_count DESC
                    LIMIT ?
                    """,
                    (f"%{trigger}%", limit)
                )
                rows = cursor.fetchall()

            for row in rows:
                # Recompute decay score
                updated_at = self._parse_datetime(row["updated_at"])
                decay_score = compute_decay_score(
                    updated_at=updated_at,
                    access_count=row["success_count"],
                    memory_layer=MemoryLayer.PROCEDURAL,
                    now=now,
                )

                if decay_score >= min_score:
                    procedures.append(self._row_to_procedure(row))

        return procedures

    def get_procedure(self, procedure_id: str) -> Optional[ProceduralMemory]:
        """
        Get a specific procedure by ID.

        Args:
            procedure_id: Procedure identifier

        Returns:
            ProceduralMemory or None if not found
        """
        row = self._get_procedure_row(procedure_id)
        return self._row_to_procedure(row) if row is not None else None

    def record_success(self, procedure_id: str) -> Optional[ProceduralMemory]:
        """
        Record successful use of a procedure.

        Increments success count and updates last_used timestamp.
        This boosts the decay score.

        Args:
            procedure_id: Procedure identifier

        Returns:
            Updated ProceduralMemory or None if not found
        """
        now = utcnow()
        updated_row = None

        with self._get_connection() as conn:
            # Get current procedure
            cursor = conn.execute(
                "SELECT * FROM procedures WHERE id = ?",
                (procedure_id,)
            )
            row = cursor.fetchone()

            if row is None:
                return None

            new_success_count = row["success_count"] + 1

            # Compute new decay score
            decay_score = compute_decay_score(
                updated_at=now,
                access_count=new_success_count,
                memory_layer=MemoryLayer.PROCEDURAL,
                now=now,
            )

            # Update
            conn.execute(
                """
                UPDATE procedures
                SET success_count = ?, last_used = ?, updated_at = ?, decay_score = ?
                WHERE id = ?
                """,
                (new_success_count, now.isoformat(), now.isoformat(), decay_score, procedure_id)
            )

            cursor = conn.execute(
                "SELECT * FROM procedures WHERE id = ?",
                (procedure_id,),
            )
            updated_row = cursor.fetchone()

        if updated_row is None:
            return None

        self._index_procedure_row(updated_row)
        return self._row_to_procedure(updated_row)

    def get_decay_score(self, procedure_id: str) -> float:
        """
        Get current decay score for a procedure.

        Args:
            procedure_id: Procedure identifier

        Returns:
            Decay score (0.0 to 1.0)
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT updated_at, success_count FROM procedures WHERE id = ?",
                (procedure_id,)
            )
            row = cursor.fetchone()

            if row is None:
                return 0.0

            return compute_decay_score(
                updated_at=self._parse_datetime(row["updated_at"]),
                access_count=row["success_count"],
                memory_layer=MemoryLayer.PROCEDURAL,
            )

    def refresh_decay_scores(self) -> int:
        """
        Refresh decay scores for all procedures.

        Returns:
            Number of procedures updated
        """
        now = utcnow()
        count = 0

        with self._get_connection() as conn:
            cursor = conn.execute("SELECT id, updated_at, success_count FROM procedures")
            rows = cursor.fetchall()

            for row in rows:
                decay_score = compute_decay_score(
                    updated_at=self._parse_datetime(row["updated_at"]),
                    access_count=row["success_count"],
                    memory_layer=MemoryLayer.PROCEDURAL,
                    now=now,
                )

                conn.execute(
                    "UPDATE procedures SET decay_score = ? WHERE id = ?",
                    (decay_score, row["id"])
                )
                count += 1

        return count

    def delete_procedure(self, procedure_id: str) -> bool:
        """
        Delete a procedure.

        Args:
            procedure_id: Procedure identifier

        Returns:
            True if deleted, False if not found
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM procedures WHERE id = ?",
                (procedure_id,)
            )
            deleted = cursor.rowcount > 0

        if deleted:
            self._delete_from_vector_store(procedure_id)

        return deleted

    def list_procedures(
        self,
        source: Optional[str] = None,
        min_score: float = 0.1,
        limit: int = 100,
    ) -> List[ProceduralMemory]:
        """
        List all procedures, optionally filtered.

        Args:
            source: Filter by source type
            min_score: Minimum decay score
            limit: Maximum results

        Returns:
            List of ProceduralMemory
        """
        procedures = []
        now = utcnow()

        with self._get_connection() as conn:
            if source:
                cursor = conn.execute(
                    """
                    SELECT * FROM procedures
                    WHERE source = ?
                    ORDER BY decay_score DESC, success_count DESC
                    LIMIT ?
                    """,
                    (source, limit)
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT * FROM procedures
                    ORDER BY decay_score DESC, success_count DESC
                    LIMIT ?
                    """,
                    (limit,)
                )

            for row in cursor:
                decay_score = compute_decay_score(
                    updated_at=self._parse_datetime(row["updated_at"]),
                    access_count=row["success_count"],
                    memory_layer=MemoryLayer.PROCEDURAL,
                    now=now,
                )

                if decay_score >= min_score:
                    procedures.append(self._row_to_procedure(row))

        return procedures

    def _parse_datetime(self, dt_str: Optional[str]) -> datetime:
        """Parse ISO format datetime string."""
        if dt_str is None:
            return utcnow()

        if dt_str.endswith('Z'):
            dt_str = dt_str[:-1] + '+00:00'

        try:
            return datetime.fromisoformat(dt_str)
        except ValueError:
            return utcnow()


# Singleton instance
_manager: Optional[ProceduralManager] = None


def get_manager(db_path: Optional[Path] = None) -> ProceduralManager:
    """Get singleton ProceduralManager instance."""
    global _manager
    if _manager is None:
        _manager = ProceduralManager(db_path)
    return _manager


# Convenience functions
def find_procedure(trigger: str, limit: int = 5) -> List[ProceduralMemory]:
    """Find procedures matching a trigger."""
    return get_manager().find_procedure(trigger, limit)


def learn_procedure(trigger: str, procedure: List[str], source: str = "explicit", topics: Optional[List[str]] = None) -> ProceduralMemory:
    """Learn a new procedure."""
    return get_manager().learn_procedure(trigger, procedure, source, topics)


def record_success(procedure_id: str) -> Optional[ProceduralMemory]:
    """Record successful use of a procedure."""
    return get_manager().record_success(procedure_id)
