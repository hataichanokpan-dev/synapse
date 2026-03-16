"""
SyncQueue - Ensures Qdrant and SQLite stay synchronized

Handles:
- Retry on failure
- Exponential backoff
- Sync verification
- Background processing
- Feature flag control
"""

import asyncio
import json
import logging
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class SyncStatus(Enum):
    """Status of a sync task."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRY_EXHAUSTED = "retry_exhausted"


@dataclass
class SyncTask:
    """Represents a sync task in the queue."""
    id: Optional[int] = None
    operation: str = ""  # 'index', 'delete', 'update'
    entity_type: str = ""  # 'episode', 'entity', 'fact'
    entity_id: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    status: SyncStatus = SyncStatus.PENDING
    attempts: int = 0
    max_attempts: int = 3
    last_error: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class SyncQueue:
    """
    Queue for synchronizing Qdrant and SQLite.

    Features:
    - Persistent queue (SQLite)
    - Exponential backoff
    - Background processing
    - Sync verification
    - Feature flag control

    Usage:
        queue = SyncQueue()

        # Register handlers
        queue.register_handler("index", handle_index)
        queue.register_handler("delete", handle_delete)

        # Enqueue tasks
        queue.enqueue("index", "episode", "ep-123", {"content": "..."})

        # Process manually
        await queue.process_all()

        # Or start background processing
        await queue.start_background(interval=60)
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize sync queue.

        Args:
            db_path: Path to queue database (default: ~/.synapse/sync_queue.db)
        """
        if db_path is None:
            db_path = Path.home() / ".synapse" / "sync_queue.db"

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_db()

        # Handlers for different operations
        self._handlers: Dict[str, Callable[[SyncTask], Awaitable[bool]]] = {}

        # Background task
        self._background_task: Optional[asyncio.Task] = None
        self._running = False

        # Feature flag - disabled by default for backward compatibility
        self._enabled = os.getenv("SYNAPSE_USE_SYNC_QUEUE", "false").lower() == "true"

    def _ensure_db(self) -> None:
        """Create queue tables if not exist."""
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sync_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operation TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                payload TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                attempts INTEGER DEFAULT 0,
                max_attempts INTEGER DEFAULT 3,
                last_error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_sync_status
            ON sync_queue(status)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_sync_entity
            ON sync_queue(entity_type, entity_id)
        """)
        conn.commit()
        conn.close()

    def is_enabled(self) -> bool:
        """Check if sync queue is enabled via feature flag."""
        return self._enabled

    def register_handler(
        self,
        operation: str,
        handler: Callable[[SyncTask], Awaitable[bool]],
    ) -> None:
        """
        Register a handler for an operation type.

        Args:
            operation: Operation name ('index', 'delete', 'update')
            handler: Async function that processes the task, returns True on success
        """
        self._handlers[operation] = handler
        logger.debug(f"Registered handler for operation: {operation}")

    def enqueue(
        self,
        operation: str,
        entity_type: str,
        entity_id: str,
        payload: Dict[str, Any],
        max_attempts: int = 3,
    ) -> int:
        """
        Add a task to the sync queue.

        Args:
            operation: 'index', 'delete', 'update'
            entity_type: 'episode', 'entity', 'fact'
            entity_id: Unique identifier
            payload: Data needed for the operation
            max_attempts: Max retry attempts (default: 3)

        Returns:
            Task ID, or -1 if queue is disabled
        """
        if not self._enabled:
            return -1

        now = datetime.now().isoformat()

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.execute(
            """
            INSERT INTO sync_queue
            (operation, entity_type, entity_id, payload, status, max_attempts, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'pending', ?, ?, ?)
            """,
            (
                operation,
                entity_type,
                entity_id,
                json.dumps(payload),
                max_attempts,
                now,
                now,
            ),
        )
        task_id = cursor.lastrowid
        conn.commit()
        conn.close()

        logger.debug(f"Enqueued sync task: {task_id} ({operation} {entity_type}/{entity_id})")
        return task_id

    def get_pending(self, limit: int = 100) -> List[SyncTask]:
        """
        Get pending tasks ready for processing.

        Args:
            limit: Maximum tasks to return

        Returns:
            List of SyncTask objects
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row

        rows = conn.execute(
            """
            SELECT * FROM sync_queue
            WHERE status IN ('pending', 'failed')
            AND attempts < max_attempts
            ORDER BY created_at ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

        tasks = []
        for row in rows:
            tasks.append(
                SyncTask(
                    id=row["id"],
                    operation=row["operation"],
                    entity_type=row["entity_type"],
                    entity_id=row["entity_id"],
                    payload=json.loads(row["payload"]),
                    status=SyncStatus(row["status"]),
                    attempts=row["attempts"],
                    max_attempts=row["max_attempts"],
                    last_error=row["last_error"],
                    created_at=self._parse_datetime(row["created_at"]),
                    updated_at=self._parse_datetime(row["updated_at"]),
                )
            )

        conn.close()
        return tasks

    def update_task(self, task: SyncTask) -> None:
        """
        Update task status in database.

        Args:
            task: SyncTask to update
        """
        now = datetime.now().isoformat()

        conn = sqlite3.connect(str(self.db_path))
        conn.execute(
            """
            UPDATE sync_queue
            SET status = ?, attempts = ?, last_error = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                task.status.value,
                task.attempts,
                task.last_error,
                now,
                task.id,
            ),
        )
        conn.commit()
        conn.close()

    async def process_one(self, task: SyncTask) -> bool:
        """
        Process a single sync task.

        Args:
            task: SyncTask to process

        Returns:
            True if successful, False otherwise
        """
        handler = self._handlers.get(task.operation)

        if not handler:
            logger.error(f"No handler for operation: {task.operation}")
            task.status = SyncStatus.FAILED
            task.last_error = f"No handler for {task.operation}"
            self.update_task(task)
            return False

        task.status = SyncStatus.IN_PROGRESS
        task.attempts += 1
        self.update_task(task)

        try:
            success = await handler(task)

            if success:
                task.status = SyncStatus.COMPLETED
                self.update_task(task)
                logger.info(f"Sync task completed: {task.id} ({task.operation} {task.entity_id})")
                return True
            else:
                raise Exception("Handler returned False")

        except Exception as e:
            task.last_error = str(e)

            if task.attempts >= task.max_attempts:
                task.status = SyncStatus.RETRY_EXHAUSTED
                logger.error(
                    f"Sync task exhausted retries: {task.id} ({task.operation} {task.entity_id}) - {e}"
                )
            else:
                task.status = SyncStatus.FAILED
                logger.warning(
                    f"Sync task failed (attempt {task.attempts}/{task.max_attempts}): "
                    f"{task.id} ({task.operation} {task.entity_id}) - {e}"
                )

            self.update_task(task)
            return False

    async def process_all(self, limit: int = 100) -> int:
        """
        Process all pending tasks.

        Args:
            limit: Maximum tasks to process

        Returns:
            Number of tasks processed
        """
        tasks = self.get_pending(limit)
        processed = 0

        for task in tasks:
            success = await self.process_one(task)
            processed += 1

            # Exponential backoff between failed tasks
            if task.status == SyncStatus.FAILED:
                backoff = min(2 ** task.attempts, 60)  # Max 60 seconds
                logger.debug(f"Backing off for {backoff}s after failed task")
                await asyncio.sleep(backoff)

        return processed

    async def start_background(self, interval: int = 60) -> None:
        """
        Start background processing.

        Args:
            interval: Seconds between processing runs (default: 60)
        """
        if self._running or not self._enabled:
            return

        self._running = True

        async def _loop():
            while self._running:
                try:
                    processed = await self.process_all()
                    if processed > 0:
                        logger.info(f"Background sync processed {processed} tasks")
                except Exception as e:
                    logger.error(f"Background sync error: {e}")

                await asyncio.sleep(interval)

        self._background_task = asyncio.create_task(_loop())
        logger.info(f"Background sync started (interval: {interval}s)")

    def stop_background(self) -> None:
        """Stop background processing."""
        self._running = False
        if self._background_task:
            self._background_task.cancel()
            self._background_task = None
            logger.info("Background sync stopped")

    def get_stats(self) -> Dict[str, int]:
        """
        Get queue statistics.

        Returns:
            Dict with counts per status
        """
        conn = sqlite3.connect(str(self.db_path))

        stats = {}
        for status in SyncStatus:
            count = conn.execute(
                "SELECT COUNT(*) FROM sync_queue WHERE status = ?",
                (status.value,),
            ).fetchone()[0]
            stats[status.value] = count

        # Total count
        stats["total"] = conn.execute("SELECT COUNT(*) FROM sync_queue").fetchone()[0]

        conn.close()
        return stats

    def clear_completed(self, older_than_days: int = 7) -> int:
        """
        Clear completed/exhausted tasks older than specified days.

        Args:
            older_than_days: Clear tasks older than this many days

        Returns:
            Number of tasks cleared
        """
        cutoff = (datetime.now() - __import__("datetime").timedelta(days=older_than_days)).isoformat()

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.execute(
            """
            DELETE FROM sync_queue
            WHERE status IN ('completed', 'retry_exhausted')
            AND datetime(updated_at) < datetime(?)
            """,
            (cutoff,),
        )
        deleted = cursor.rowcount
        conn.commit()
        conn.close()

        if deleted > 0:
            logger.info(f"Cleared {deleted} old sync tasks")

        return deleted

    def _parse_datetime(self, dt_str: Optional[str]) -> Optional[datetime]:
        """Parse ISO format datetime string."""
        if dt_str is None:
            return None

        if dt_str.endswith("Z"):
            dt_str = dt_str[:-1] + "+00:00"

        try:
            return datetime.fromisoformat(dt_str)
        except ValueError:
            return None


# Singleton instance
_queue: Optional[SyncQueue] = None


def get_sync_queue(db_path: Optional[Path] = None) -> SyncQueue:
    """Get singleton SyncQueue instance."""
    global _queue
    if _queue is None:
        _queue = SyncQueue(db_path)
    return _queue
