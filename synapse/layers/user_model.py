"""
Layer 1: User Model

User preferences, expertise, and personalization.
NEVER DECAYS - Always score = 1.0

Storage:
- SQLite: Persistent local storage
- Graph: (User) node with properties
"""

import json
import sqlite3
from pathlib import Path
from typing import Optional, Dict, Any, List
from contextlib import contextmanager

from .types import UserModel, MemoryLayer, utcnow
from .decay import compute_decay_score


# Default database path
DEFAULT_DB_PATH = Path.home() / ".synapse" / "user_model.db"


class UserModelManager:
    """
    Manager for Layer 1: User Model.

    User models never decay and are stored locally for privacy.
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize User Model Manager.

        Args:
            db_path: Path to SQLite database (default: ~/.synapse/user_model.db)
        """
        self.db_path = db_path or DEFAULT_DB_PATH
        self._ensure_db()

    def _ensure_db(self) -> None:
        """Create database and tables if not exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_models (
                    user_id TEXT PRIMARY KEY,
                    language TEXT DEFAULT 'th',
                    response_style TEXT DEFAULT 'casual',
                    response_length TEXT DEFAULT 'auto',
                    timezone TEXT DEFAULT 'Asia/Bangkok',
                    expertise TEXT DEFAULT '{}',
                    common_topics TEXT DEFAULT '[]',
                    notes TEXT DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
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

    def get_user_model(self, user_id: str) -> UserModel:
        """
        Get user model by ID.

        Creates default model if not exists.

        Args:
            user_id: User identifier

        Returns:
            UserModel (never None, creates default if missing)
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM user_models WHERE user_id = ?",
                (user_id,)
            )
            row = cursor.fetchone()

            if row is None:
                # Create default model
                now = utcnow()
                conn.execute(
                    """
                    INSERT INTO user_models (user_id, created_at, updated_at)
                    VALUES (?, ?, ?)
                    """,
                    (user_id, now.isoformat(), now.isoformat())
                )
                return UserModel(user_id=user_id, updated_at=now)

            return UserModel(
                user_id=row["user_id"],
                language=row["language"],
                response_style=row["response_style"],
                response_length=row["response_length"],
                timezone=row["timezone"],
                expertise=json.loads(row["expertise"]),
                common_topics=json.loads(row["common_topics"]),
                notes=json.loads(row["notes"]),
                updated_at=self._parse_datetime(row["updated_at"]),
            )

    def update_user_model(
        self,
        user_id: str,
        language: Optional[str] = None,
        response_style: Optional[str] = None,
        response_length: Optional[str] = None,
        timezone: Optional[str] = None,
        expertise: Optional[Dict[str, str]] = None,
        common_topics: Optional[List[str]] = None,
        notes: Optional[List[str]] = None,
        add_note: Optional[str] = None,
        add_expertise: Optional[Dict[str, str]] = None,
        add_topic: Optional[str] = None,
    ) -> UserModel:
        """
        Update user model.

        Args:
            user_id: User identifier
            language: Preferred language (th, en, etc.)
            response_style: Response style (formal, casual, auto)
            response_length: Response length (concise, detailed, auto)
            timezone: User timezone
            expertise: Replace expertise dict
            common_topics: Replace topics list
            notes: Replace notes list
            add_note: Append a note
            add_expertise: Merge expertise entries
            add_topic: Append a topic

        Returns:
            Updated UserModel
        """
        # Get current model
        model = self.get_user_model(user_id)
        now = utcnow()

        # Apply updates
        if language is not None:
            model.language = language
        if response_style is not None:
            model.response_style = response_style
        if response_length is not None:
            model.response_length = response_length
        if timezone is not None:
            model.timezone = timezone
        if expertise is not None:
            model.expertise = expertise
        if common_topics is not None:
            model.common_topics = common_topics
        if notes is not None:
            model.notes = notes

        # Append operations
        if add_note is not None:
            model.notes.append(add_note)
        if add_expertise is not None:
            model.expertise.update(add_expertise)
        if add_topic is not None and add_topic not in model.common_topics:
            model.common_topics.append(add_topic)

        model.updated_at = now

        # Save to database
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO user_models (
                    user_id, language, response_style, response_length, timezone,
                    expertise, common_topics, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    model.user_id,
                    model.language,
                    model.response_style,
                    model.response_length,
                    model.timezone,
                    json.dumps(model.expertise),
                    json.dumps(model.common_topics),
                    json.dumps(model.notes),
                    now.isoformat(),  # created_at (use now for upsert)
                    now.isoformat(),
                )
            )

        return model

    def reset_user_model(self, user_id: str) -> UserModel:
        """
        Reset user model to defaults.

        Args:
            user_id: User identifier

        Returns:
            New default UserModel
        """
        with self._get_connection() as conn:
            conn.execute(
                "DELETE FROM user_models WHERE user_id = ?",
                (user_id,)
            )

        return self.get_user_model(user_id)

    def get_decay_score(self, user_id: str) -> float:
        """
        Get decay score for user model.

        Layer 1 (User Model) NEVER decays - always returns 1.0

        Args:
            user_id: User identifier

        Returns:
            Always 1.0
        """
        # User model never decays
        return 1.0

    def _parse_datetime(self, dt_str: str):
        """Parse ISO format datetime string."""
        from datetime import datetime, timezone

        # Handle various ISO formats
        if dt_str.endswith('Z'):
            dt_str = dt_str[:-1] + '+00:00'

        try:
            return datetime.fromisoformat(dt_str)
        except ValueError:
            # Fallback to current time if parse fails
            return utcnow()


# Singleton instance
_manager: Optional[UserModelManager] = None


def get_manager(db_path: Optional[Path] = None) -> UserModelManager:
    """Get singleton UserModelManager instance."""
    global _manager
    if _manager is None:
        _manager = UserModelManager(db_path)
    return _manager


# Convenience functions
def get_user_model(user_id: str) -> UserModel:
    """Get user model by ID."""
    return get_manager().get_user_model(user_id)


def update_user_model(user_id: str, **kwargs) -> UserModel:
    """Update user model."""
    return get_manager().update_user_model(user_id, **kwargs)


def reset_user_model(user_id: str) -> UserModel:
    """Reset user model to defaults."""
    return get_manager().reset_user_model(user_id)
