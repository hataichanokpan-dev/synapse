"""
Layer 4: Episodic Memory

Conversation summaries and experiences.
TTL-BASED - 90 days base, +30 days extension on access

Storage:
- Graph: (Episode) nodes with expires_at
- Vector: ChromaDB for semantic search

Episodic memories have a Time-To-Live (TTL) instead of decay scoring.
Access extends TTL by 30 days (max 30 extra days from access count).

Thai NLP Integration:
- Content and summaries are tokenized for FTS5
- Search queries are preprocessed for Thai
"""

import json
import sqlite3
import uuid
from pathlib import Path
from typing import Optional, List, Dict, Any
from contextlib import contextmanager
from datetime import datetime, timedelta

from .types import SynapseEpisode, MemoryLayer, utcnow
from .decay import compute_ttl, extend_ttl, should_forget, DecayConfig

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
DEFAULT_DB_PATH = Path.home() / ".synapse" / "episodic.db"


class EpisodicManager:
    """
    Manager for Layer 4: Episodic Memory.

    Episodes use TTL (90 days base) instead of decay scoring.
    Access extends TTL by 30 days.
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize Episodic Memory Manager.

        Args:
            db_path: Path to SQLite database (default: ~/.synapse/episodic.db)
        """
        self.db_path = db_path or DEFAULT_DB_PATH
        self._ensure_db()

    def _ensure_db(self) -> None:
        """Create database and tables if not exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS episodes (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    content_fts TEXT,
                    summary TEXT,
                    summary_fts TEXT,
                    topics TEXT DEFAULT '[]',
                    outcome TEXT DEFAULT 'unknown',
                    memory_layer TEXT DEFAULT 'episodic',
                    recorded_at TEXT NOT NULL,
                    expires_at TEXT,
                    user_id TEXT,
                    session_id TEXT,
                    access_count INTEGER DEFAULT 0
                )
            """)

            # Index for expiration queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_episodes_expires
                ON episodes(expires_at)
            """)

            # Index for topic search
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_episodes_topics
                ON episodes(topics)
            """)

            # FTS5 for full-text search (using tokenized content/summary)
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS episodes_fts
                USING fts5(content_fts, summary_fts, content='episodes', content_rowid='rowid')
            """)

            # Migration: Add FTS columns if not exists
            try:
                conn.execute("ALTER TABLE episodes ADD COLUMN content_fts TEXT")
            except sqlite3.OperationalError:
                pass
            try:
                conn.execute("ALTER TABLE episodes ADD COLUMN summary_fts TEXT")
            except sqlite3.OperationalError:
                pass

            # FTS5 for full-text search on summaries
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS episodes_fts
                USING fts5(summary, content='episodes', content_rowid='rowid')
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

    def record_episode(
        self,
        content: str,
        summary: Optional[str] = None,
        topics: Optional[List[str]] = None,
        outcome: str = "unknown",
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        ttl_days: Optional[int] = None,
        preprocess: bool = True,
    ) -> SynapseEpisode:
        """
        Record a new episode.

        Args:
            content: Raw content of the episode
            summary: LLM-generated summary
            topics: List of topics/tags
            outcome: Outcome (success | partial | failed | unknown)
            user_id: User identifier
            session_id: Session identifier
            ttl_days: Custom TTL (default: 90 days + access-based extension)
            preprocess: Apply Thai NLP tokenization for FTS

        Returns:
            Created SynapseEpisode
        """
        now = utcnow()
        episode_id = str(uuid.uuid4())

        # Compute TTL
        if ttl_days is None:
            expires_at = compute_ttl(
                memory_layer=MemoryLayer.EPISODIC,
                created_at=now,
                access_count=0,
            )
        else:
            expires_at = now + timedelta(days=ttl_days)

        # Tokenize content and summary for FTS5 (especially for Thai)
        content_fts = content
        summary_fts = summary
        if preprocess:
            preprocessor = _get_nlp_preprocessor()
            if preprocessor:
                content_fts = preprocessor.tokenize_for_fts(content)
                if summary:
                    summary_fts = preprocessor.tokenize_for_fts(summary)

        episode = SynapseEpisode(
            id=episode_id,
            content=content,
            summary=summary,
            topics=topics or [],
            outcome=outcome,
            memory_layer=MemoryLayer.EPISODIC,
            recorded_at=now,
            expires_at=expires_at,
            user_id=user_id,
            session_id=session_id,
        )

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO episodes (
                    id, content, content_fts, summary, summary_fts, topics, outcome, memory_layer,
                    recorded_at, expires_at, user_id, session_id, access_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                """,
                (
                    episode_id,
                    content,
                    content_fts,
                    summary,
                    summary_fts,
                    json.dumps(topics or []),
                    outcome,
                    MemoryLayer.EPISODIC.value,
                    now.isoformat(),
                    expires_at.isoformat() if expires_at else None,
                    user_id,
                    session_id,
                )
            )

        return episode

    def get_episode(self, episode_id: str) -> Optional[SynapseEpisode]:
        """
        Get episode by ID.

        Extends TTL on access.

        Args:
            episode_id: Episode identifier

        Returns:
            SynapseEpisode or None
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM episodes WHERE id = ?",
                (episode_id,)
            )
            row = cursor.fetchone()

            if row is None:
                return None

            # Extend TTL on access
            current_expires = self._parse_datetime(row["expires_at"]) if row["expires_at"] else None
            new_expires = extend_ttl(current_expires, allow_revival=False)

            if new_expires is not None:
                conn.execute(
                    """
                    UPDATE episodes
                    SET expires_at = ?, access_count = access_count + 1
                    WHERE id = ?
                    """,
                    (new_expires.isoformat(), episode_id)
                )

            return SynapseEpisode(
                id=row["id"],
                content=row["content"],
                summary=row["summary"],
                topics=json.loads(row["topics"]),
                outcome=row["outcome"],
                memory_layer=MemoryLayer(row["memory_layer"]),
                recorded_at=self._parse_datetime(row["recorded_at"]),
                expires_at=new_expires or current_expires,
                user_id=row["user_id"],
                session_id=row["session_id"],
            )

    def find_episodes(
        self,
        query: Optional[str] = None,
        topics: Optional[List[str]] = None,
        outcome: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 10,
        include_expired: bool = False,
        preprocess: bool = True,
    ) -> List[SynapseEpisode]:
        """
        Find episodes matching criteria.

        Uses FTS5 for full-text search on summaries.
        Thai queries are tokenized for better FTS5 matching.

        Args:
            query: Full-text search query
            topics: Filter by topics
            outcome: Filter by outcome
            user_id: Filter by user
            limit: Maximum results
            include_expired: Include expired episodes
            preprocess: Apply Thai NLP preprocessing

        Returns:
            List of SynapseEpisode
        """
        episodes = []
        now = utcnow()

        # Preprocess query for Thai
        search_query = query
        if query and preprocess:
            preprocessor = _get_nlp_preprocessor()
            if preprocessor:
                search_query = preprocessor.tokenize_for_fts(query)

        with self._get_connection() as conn:
            # Build query
            if search_query:
                # Use FTS5 for full-text search
                try:
                    sql = """
                        SELECT e.* FROM episodes e
                        JOIN episodes_fts fts ON e.rowid = fts.rowid
                        WHERE episodes_fts MATCH ?
                    """
                    params = [search_query]

                    if not include_expired:
                        sql += " AND (e.expires_at IS NULL OR e.expires_at > ?)"
                        params.append(now.isoformat())

                    if outcome:
                        sql += " AND e.outcome = ?"
                        params.append(outcome)

                    if user_id:
                        sql += " AND e.user_id = ?"
                        params.append(user_id)

                    # Topic filtering (JSON array contains)
                    if topics:
                        for topic in topics:
                            sql += " AND e.topics LIKE ?"
                            params.append(f'%"{topic}"%')

                    sql += " ORDER BY e.recorded_at DESC LIMIT ?"
                    params.append(limit)

                    cursor = conn.execute(sql, params)
                    rows = cursor.fetchall()

                except sqlite3.OperationalError:
                    # FTS5 might not have data yet, fallback to LIKE
                    sql = "SELECT * FROM episodes WHERE 1=1"
                    params = []

                    if not include_expired:
                        sql += " AND (expires_at IS NULL OR expires_at > ?)"
                        params.append(now.isoformat())

                    if outcome:
                        sql += " AND outcome = ?"
                        params.append(outcome)

                    if user_id:
                        sql += " AND user_id = ?"
                        params.append(user_id)

                    # Content/summary LIKE search
                    sql += " AND (content LIKE ? OR summary LIKE ?)"
                    params.extend([f"%{query}%", f"%{query}%"])

                    if topics:
                        for topic in topics:
                            sql += " AND topics LIKE ?"
                            params.append(f'%"{topic}"%')

                    sql += " ORDER BY recorded_at DESC LIMIT ?"
                    params.append(limit)

                    cursor = conn.execute(sql, params)
                    rows = cursor.fetchall()
            else:
                # No query, just filter
                sql = "SELECT * FROM episodes WHERE 1=1"
                params = []

                if not include_expired:
                    sql += " AND (expires_at IS NULL OR expires_at > ?)"
                    params.append(now.isoformat())

                if outcome:
                    sql += " AND outcome = ?"
                    params.append(outcome)

                if user_id:
                    sql += " AND user_id = ?"
                    params.append(user_id)

                # Topic filtering (JSON array contains)
                if topics:
                    for topic in topics:
                        sql += " AND topics LIKE ?"
                        params.append(f'%"{topic}"%')

                sql += " ORDER BY recorded_at DESC LIMIT ?"
                params.append(limit)

                cursor = conn.execute(sql, params)
                rows = cursor.fetchall()

            # Process results
            for row in rows:
                episode = SynapseEpisode(
                    id=row["id"],
                    content=row["content"],
                    summary=row["summary"],
                    topics=json.loads(row["topics"]),
                    outcome=row["outcome"],
                    memory_layer=MemoryLayer(row["memory_layer"]),
                    recorded_at=self._parse_datetime(row["recorded_at"]),
                    expires_at=self._parse_datetime(row["expires_at"]) if row["expires_at"] else None,
                    user_id=row["user_id"],
                    session_id=row["session_id"],
                )
                episodes.append(episode)

        return episodes

    def purge_expired(self, archive: bool = True) -> int:
        """
        Remove expired episodes.

        Args:
            archive: If True, archive before deletion

        Returns:
            Number of episodes removed
        """
        now = utcnow()
        count = 0

        with self._get_connection() as conn:
            # Find expired episodes
            cursor = conn.execute(
                "SELECT * FROM episodes WHERE expires_at IS NOT NULL AND expires_at <= ?",
                (now.isoformat(),)
            )
            expired = cursor.fetchall()

            for row in expired:
                if archive:
                    # TODO: Archive to separate table or file
                    # For now, just log
                    pass

                conn.execute("DELETE FROM episodes WHERE id = ?", (row["id"],))
                count += 1

        return count

    def extend_episode_ttl(
        self,
        episode_id: str,
        extra_days: Optional[int] = None,
    ) -> Optional[datetime]:
        """
        Manually extend episode TTL.

        Args:
            episode_id: Episode identifier
            extra_days: Extra days (default: from DecayConfig)

        Returns:
            New expiration datetime or None
        """
        if extra_days is None:
            extra_days = DecayConfig.TTL_EXTEND_DAYS

        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT expires_at FROM episodes WHERE id = ?",
                (episode_id,)
            )
            row = cursor.fetchone()

            if row is None:
                return None

            current_expires = self._parse_datetime(row["expires_at"]) if row["expires_at"] else None
            new_expires = extend_ttl(current_expires, allow_revival=True)

            if new_expires is not None:
                conn.execute(
                    "UPDATE episodes SET expires_at = ? WHERE id = ?",
                    (new_expires.isoformat(), episode_id)
                )

            return new_expires

    def get_episodes_by_session(self, session_id: str) -> List[SynapseEpisode]:
        """
        Get all episodes for a session.

        Args:
            session_id: Session identifier

        Returns:
            List of SynapseEpisode
        """
        return self.find_episodes(session_id=session_id, limit=1000)

    def get_episode_stats(self) -> Dict[str, Any]:
        """
        Get statistics about episodes.

        Returns:
            Dict with counts and statistics
        """
        now = utcnow()

        with self._get_connection() as conn:
            total = conn.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]
            expired = conn.execute(
                "SELECT COUNT(*) FROM episodes WHERE expires_at IS NOT NULL AND expires_at <= ?",
                (now.isoformat(),)
            ).fetchone()[0]
            active = total - expired

            outcomes = conn.execute(
                "SELECT outcome, COUNT(*) as count FROM episodes GROUP BY outcome"
            ).fetchall()

            return {
                "total": total,
                "active": active,
                "expired": expired,
                "outcomes": {row["outcome"]: row["count"] for row in outcomes},
            }

    def delete_episode(self, episode_id: str) -> bool:
        """
        Delete an episode.

        Args:
            episode_id: Episode identifier

        Returns:
            True if deleted, False if not found
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM episodes WHERE id = ?",
                (episode_id,)
            )
            return cursor.rowcount > 0

    def _parse_datetime(self, dt_str: Optional[str]) -> Optional[datetime]:
        """Parse ISO format datetime string."""
        if dt_str is None:
            return None

        if dt_str.endswith('Z'):
            dt_str = dt_str[:-1] + '+00:00'

        try:
            return datetime.fromisoformat(dt_str)
        except ValueError:
            return None


# Singleton instance
_manager: Optional[EpisodicManager] = None


def get_manager(db_path: Optional[Path] = None) -> EpisodicManager:
    """Get singleton EpisodicManager instance."""
    global _manager
    if _manager is None:
        _manager = EpisodicManager(db_path)
    return _manager


# Convenience functions
def record_episode(content: str, summary: Optional[str] = None, **kwargs) -> SynapseEpisode:
    """Record a new episode."""
    return get_manager().record_episode(content, summary, **kwargs)


def find_episodes(query: Optional[str] = None, limit: int = 10, **kwargs) -> List[SynapseEpisode]:
    """Find episodes matching criteria."""
    return get_manager().find_episodes(query=query, limit=limit, **kwargs)


def purge_expired(archive: bool = True) -> int:
    """Remove expired episodes."""
    return get_manager().purge_expired(archive)
