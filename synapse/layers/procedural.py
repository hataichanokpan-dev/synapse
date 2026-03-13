"""
Layer 2: Procedural Memory

How-to patterns and procedures.
SLOW DECAY - λ = 0.005, half-life ~139 days

Storage:
- Graph: (Procedure) nodes with trigger edges
- Vector: ChromaDB for semantic search of triggers
"""

import json
import sqlite3
import uuid
from pathlib import Path
from typing import Optional, List, Dict, Any
from contextlib import contextmanager
from datetime import datetime

from .types import ProceduralMemory, MemoryLayer, utcnow
from .decay import compute_decay_score, DecayConfig


# Default database path
DEFAULT_DB_PATH = Path.home() / ".synapse" / "procedural.db"


class ProceduralManager:
    """
    Manager for Layer 2: Procedural Memory.

    Procedures decay slowly (λ = 0.005, half-life ~139 days).
    Success count boosts decay score.
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize Procedural Memory Manager.

        Args:
            db_path: Path to SQLite database (default: ~/.synapse/procedural.db)
        """
        self.db_path = db_path or DEFAULT_DB_PATH
        self._ensure_db()

    def _ensure_db(self) -> None:
        """Create database and tables if not exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS procedures (
                    id TEXT PRIMARY KEY,
                    trigger TEXT NOT NULL,
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

            # FTS5 for full-text search on triggers
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS procedures_fts
                USING fts5(trigger, content='procedures', content_rowid='rowid')
            """)

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

    def learn_procedure(
        self,
        trigger: str,
        procedure: List[str],
        source: str = "explicit",
        topics: Optional[List[str]] = None,
    ) -> ProceduralMemory:
        """
        Learn a new procedure.

        Args:
            trigger: When to activate this procedure
            procedure: List of steps to execute
            source: How this was learned (explicit | correction | repeated_pattern)
            topics: Related topics

        Returns:
            Created ProceduralMemory
        """
        now = utcnow()
        proc_id = str(uuid.uuid4())

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
                    id, trigger, procedure, source, success_count, last_used,
                    topics, created_at, updated_at, decay_score
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1.0)
                """,
                (
                    proc_id,
                    trigger,
                    json.dumps(procedure),
                    source,
                    0,
                    None,
                    json.dumps(topics or []),
                    now.isoformat(),
                    now.isoformat(),
                )
            )

        return proc

    def find_procedure(
        self,
        trigger: str,
        limit: int = 5,
        min_score: float = 0.1,
    ) -> List[ProceduralMemory]:
        """
        Find procedures matching a trigger.

        Uses FTS5 for full-text search on triggers.

        Args:
            trigger: Search query
            limit: Maximum results
            min_score: Minimum decay score threshold

        Returns:
            List of matching ProceduralMemory
        """
        procedures = []
        now = utcnow()

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
                    (trigger, limit)
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
                    proc = ProceduralMemory(
                        id=row["id"],
                        trigger=row["trigger"],
                        procedure=json.loads(row["procedure"]),
                        source=row["source"],
                        success_count=row["success_count"],
                        last_used=self._parse_datetime(row["last_used"]) if row["last_used"] else None,
                        topics=json.loads(row["topics"]),
                    )
                    procedures.append(proc)

        return procedures

    def get_procedure(self, procedure_id: str) -> Optional[ProceduralMemory]:
        """
        Get a specific procedure by ID.

        Args:
            procedure_id: Procedure identifier

        Returns:
            ProceduralMemory or None if not found
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM procedures WHERE id = ?",
                (procedure_id,)
            )
            row = cursor.fetchone()

            if row is None:
                return None

            return ProceduralMemory(
                id=row["id"],
                trigger=row["trigger"],
                procedure=json.loads(row["procedure"]),
                source=row["source"],
                success_count=row["success_count"],
                last_used=self._parse_datetime(row["last_used"]) if row["last_used"] else None,
                topics=json.loads(row["topics"]),
            )

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

        return self.get_procedure(procedure_id)

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
            return cursor.rowcount > 0

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
                    proc = ProceduralMemory(
                        id=row["id"],
                        trigger=row["trigger"],
                        procedure=json.loads(row["procedure"]),
                        source=row["source"],
                        success_count=row["success_count"],
                        last_used=self._parse_datetime(row["last_used"]) if row["last_used"] else None,
                        topics=json.loads(row["topics"]),
                    )
                    procedures.append(proc)

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
