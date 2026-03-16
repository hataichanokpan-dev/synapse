# Phase 3: Medium Priority Fixes (P2)

> **Duration**: 1-2 days
> **Goal**: Improve data integrity and completeness
> **Assignee**: เดฟ (Dev) 🦀
> **Reviewer**: Mneme 🧠
> **Dependencies**: Phase 1 & 2 Complete

---

## Overview

Phase 3 เน้นปรับปรุงความสมบูรณ์ของข้อมูล:
- Archive ก่อนลบ
- Search ครบทุก layer
- Sync ระหว่าง Qdrant และ SQLite

---

## Tasks

### Task 3.1: Archive Before Purge

| Field | Value |
|-------|-------|
| **Priority** | P2 - Medium |
| **Est. Time** | 2 hours |
| **Assignee** | เดฟ (Dev) |
| **Reviewer** | Mneme |
| **Dependencies** | None |

#### Problem

`purge_expired()` ลบ episode โดยไม่ archive — ข้อมูลสูญหายถาวร

**Evidence** (Lines 641-643):
```python
def purge_expired(self, archive: bool = True) -> int:
    # ...
    if archive:
        # TODO: Archive to separate table or file
        # For now, just log
        pass  # ← ไม่ทำอะไรเลย!
    conn.execute("DELETE FROM episodes WHERE id = ?", (row["id"],))
```

#### Files to Modify

| File | Action |
|------|--------|
| `synapse/layers/episodic.py` | MODIFY - Add archive logic |

#### Implementation Details

**Step 1: Add archive table in `_ensure_db()`**

```python
def _ensure_db(self):
    # ... existing tables ...

    # Archive table (same schema + archived_at)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS episodes_archive (
            id TEXT PRIMARY KEY,
            content TEXT NOT NULL,
            source TEXT,
            timestamp TEXT NOT NULL,
            metadata TEXT,
            access_count INTEGER DEFAULT 0,
            last_accessed TEXT,
            expires_at TEXT,
            archived_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Index for archive queries
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_archive_archived_at
        ON episodes_archive(archived_at)
    """)
```

**Step 2: Implement archive logic in `purge_expired()`**

```python
def purge_expired(
    self,
    archive: bool = True,
    archive_retention_days: int = 365,
) -> Dict[str, int]:
    """
    Purge expired episodes, optionally archiving them first.

    Args:
        archive: Whether to archive before deletion (default: True)
        archive_retention_days: Days to keep archived data (default: 365)

    Returns:
        Dict with 'deleted' and 'archived' counts
    """
    conn = self._get_connection()
    now = datetime.now()

    # Find expired episodes
    expired = conn.execute("""
        SELECT * FROM episodes
        WHERE expires_at IS NOT NULL
        AND datetime(expires_at) < datetime(?)
    """, (now.isoformat(),)).fetchall()

    deleted_count = 0
    archived_count = 0

    for row in expired:
        episode_id = row["id"]

        if archive:
            # Archive before delete
            try:
                conn.execute("""
                    INSERT INTO episodes_archive
                    (id, content, source, timestamp, metadata, access_count, last_accessed, expires_at)
                    SELECT id, content, source, timestamp, metadata, access_count, last_accessed, expires_at
                    FROM episodes
                    WHERE id = ?
                """, (episode_id,))
                archived_count += 1
                logger.info(f"Archived episode: {episode_id}")
            except Exception as e:
                logger.error(f"Failed to archive episode {episode_id}: {e}")
                continue

        # Delete from main table
        conn.execute("DELETE FROM episodes WHERE id = ?", (episode_id,))
        deleted_count += 1

        # Delete from vector store
        self._delete_from_vector_store(episode_id)

    conn.commit()

    # Clean up old archives (beyond retention period)
    if archive:
        cutoff = (now - timedelta(days=archive_retention_days)).isoformat()
        conn.execute("""
            DELETE FROM episodes_archive
            WHERE datetime(archived_at) < datetime(?)
        """, (cutoff,))
        conn.commit()

    return {
        "deleted": deleted_count,
        "archived": archived_count,
    }
```

**Step 3: Add restore method**

```python
def restore_episode(self, episode_id: str) -> Optional[Episode]:
    """
    Restore an archived episode.

    Args:
        episode_id: ID of archived episode

    Returns:
        Restored Episode or None if not found
    """
    conn = self._get_connection()

    # Find in archive
    row = conn.execute("""
        SELECT * FROM episodes_archive WHERE id = ?
    """, (episode_id,)).fetchone()

    if not row:
        logger.warning(f"Episode not found in archive: {episode_id}")
        return None

    # Restore to main table
    try:
        conn.execute("""
            INSERT INTO episodes
            (id, content, source, timestamp, metadata, access_count, last_accessed, expires_at)
            SELECT id, content, source, timestamp, metadata, access_count, last_accessed,
                   datetime('now', '+90 days')  -- Reset expiry
            FROM episodes_archive
            WHERE id = ?
        """, (episode_id,))

        # Remove from archive
        conn.execute("DELETE FROM episodes_archive WHERE id = ?", (episode_id,))
        conn.commit()

        # Re-index to vector store
        episode = self._row_to_episode(row)
        self._index_episode(episode, access_count=row["access_count"])

        logger.info(f"Restored episode: {episode_id}")
        return episode

    except Exception as e:
        logger.error(f"Failed to restore episode {episode_id}: {e}")
        return None
```

**Step 4: Add list archived method**

```python
def list_archived(
    self,
    limit: int = 100,
    offset: int = 0,
) -> List[Dict]:
    """List archived episodes."""
    conn = self._get_connection()

    rows = conn.execute("""
        SELECT id, content, source, timestamp, archived_at
        FROM episodes_archive
        ORDER BY archived_at DESC
        LIMIT ? OFFSET ?
    """, (limit, offset)).fetchall()

    return [dict(row) for row in rows]
```

#### Acceptance Criteria

- [ ] `episodes_archive` table created
- [ ] `purge_expired()` archives before deleting
- [ ] `restore_episode()` works
- [ ] `list_archived()` returns archived episodes
- [ ] Old archives cleaned up automatically

#### Test Cases

```python
def test_archive_before_purge():
    manager = EpisodicManager()

    # Create episode that expires immediately
    manager.record_episode(
        content="Test content",
        source="test",
        expires_in_hours=0,  # Already expired
    )

    # Purge with archive
    result = manager.purge_expired(archive=True)

    assert result["deleted"] >= 1
    assert result["archived"] >= 1

    # Should be in archive
    archived = manager.list_archived()
    assert any(e["content"] == "Test content" for e in archived)

def test_restore_episode():
    manager = EpisodicManager()

    # Create and archive
    manager.record_episode(content="To restore", source="test", expires_in_hours=0)
    manager.purge_expired(archive=True)

    # Get archived ID
    archived = manager.list_archived()
    episode_id = next(e["id"] for e in archived if "To restore" in e["content"])

    # Restore
    restored = manager.restore_episode(episode_id)
    assert restored is not None
    assert "To restore" in restored.content

def test_archive_not_in_main_search():
    manager = EpisodicManager()

    # Create and archive
    manager.record_episode(content="Archived content", source="test", expires_in_hours=0)
    manager.purge_expired(archive=True)

    # Search should not find archived
    results = manager.search_episodes("Archived content")
    assert len(results) == 0
```

---

### Task 3.2: Complete search_all() Implementation

| Field | Value |
|-------|-------|
| **Priority** | P2 - Medium |
| **Est. Time** | 1 hour |
| **Assignee** | เดฟ (Dev) |
| **Reviewer** | Mneme |
| **Dependencies** | None |

#### Problem

`search_all()` ข้าม User Model และ Working Memory — ไม่ครบทุก layer

**Evidence** (Lines 227-244):
```python
async def search_all(
    self,
    query: str,
    layers: Optional[List[MemoryLayer]] = None,
    limit_per_layer: int = 5,
) -> Dict[MemoryLayer, List[Any]]:
    if layers is None:
        layers = [
            MemoryLayer.PROCEDURAL,
            MemoryLayer.SEMANTIC,
            MemoryLayer.EPISODIC,
        ]  # ← Missing: USER_MODEL, WORKING
```

#### Files to Modify

| File | Action |
|------|--------|
| `synapse/layers/manager.py` | MODIFY - Complete search |

#### Implementation Details

```python
async def search_all(
    self,
    query: str,
    layers: Optional[List[MemoryLayer]] = None,
    limit_per_layer: int = 5,
    include_user_context: bool = True,
    include_working_memory: bool = True,
) -> Dict[MemoryLayer, List[Any]]:
    """
    Search across all memory layers.

    Args:
        query: Search query
        layers: Optional list of layers to search (default: all 5)
        limit_per_layer: Max results per layer
        include_user_context: Include user model in results (default: True)
        include_working_memory: Include working memory in results (default: True)

    Returns:
        Dict mapping MemoryLayer to list of results
    """
    # Default to all 5 layers
    if layers is None:
        layers = [
            MemoryLayer.USER_MODEL,
            MemoryLayer.PROCEDURAL,
            MemoryLayer.SEMANTIC,
            MemoryLayer.EPISODIC,
            MemoryLayer.WORKING,
        ]

    results: Dict[MemoryLayer, List[Any]] = {}

    # Layer 1: User Model
    if MemoryLayer.USER_MODEL in layers:
        user_results = self._search_user_model(query, limit_per_layer)
        if user_results:
            results[MemoryLayer.USER_MODEL] = user_results

    # Layer 2: Procedural
    if MemoryLayer.PROCEDURAL in layers:
        results[MemoryLayer.PROCEDURAL] = self.find_procedures(query, limit_per_layer)

    # Layer 3: Semantic
    if MemoryLayer.SEMANTIC in layers:
        results[MemoryLayer.SEMANTIC] = await self.search_semantic(query, limit_per_layer)

    # Layer 4: Episodic
    if MemoryLayer.EPISODIC in layers:
        results[MemoryLayer.EPISODIC] = self.find_episodes_by_topic(query, limit_per_layer)

    # Layer 5: Working Memory
    if MemoryLayer.WORKING in layers:
        working_results = self._search_working_memory(query, limit_per_layer)
        if working_results:
            results[MemoryLayer.WORKING] = working_results

    return results


def _search_user_model(self, query: str, limit: int) -> List[Dict]:
    """Search user model for matching preferences/topics."""
    user_model = self.get_user_model(self.user_id)
    results = []

    query_lower = query.lower()

    # Search topics
    for topic in user_model.get("topics", []):
        if query_lower in topic.lower():
            results.append({
                "type": "topic",
                "value": topic,
                "source": "user_model",
            })

    # Search preferences
    for pref in user_model.get("preferences", []):
        if query_lower in pref.lower():
            results.append({
                "type": "preference",
                "value": pref,
                "source": "user_model",
            })

    # Search expertise
    for exp in user_model.get("expertise", []):
        if query_lower in exp.lower():
            results.append({
                "type": "expertise",
                "value": exp,
                "source": "user_model",
            })

    return results[:limit]


def _search_working_memory(self, query: str, limit: int) -> List[Dict]:
    """Search working memory for matching context."""
    working = self.get_working_context()
    results = []

    query_lower = query.lower()

    # Search all context keys/values
    for key, value in working.items():
        value_str = str(value).lower()
        if query_lower in key.lower() or query_lower in value_str:
            results.append({
                "key": key,
                "value": value,
                "source": "working_memory",
            })

    return results[:limit]
```

#### Acceptance Criteria

- [ ] `search_all()` includes all 5 layers by default
- [ ] User Model search returns preferences/topics/expertise
- [ ] Working Memory search returns context keys/values
- [ ] `include_user_context` and `include_working_memory` flags work

#### Test Cases

```python
@pytest.mark.asyncio
async def test_search_all_includes_user_model():
    manager = LayerManager(user_id="test_user")

    # Add user preference
    manager.update_user(user_id="test_user", add_note="I prefer Python over JavaScript")

    # Search
    results = await manager.search_all("Python")

    assert MemoryLayer.USER_MODEL in results
    assert len(results[MemoryLayer.USER_MODEL]) > 0

@pytest.mark.asyncio
async def test_search_all_includes_working_memory():
    manager = LayerManager()

    # Add to working memory
    manager.set_working_context("current_task", "Fix the login bug")

    # Search
    results = await manager.search_all("login")

    assert MemoryLayer.WORKING in results
    assert any("login" in str(r) for r in results[MemoryLayer.WORKING])

@pytest.mark.asyncio
async def test_search_all_excludes_layers():
    manager = LayerManager()

    # Search only specific layers
    results = await manager.search_all(
        query="test",
        layers=[MemoryLayer.EPISODIC, MemoryLayer.SEMANTIC],
    )

    assert MemoryLayer.USER_MODEL not in results
    assert MemoryLayer.WORKING not in results
```

---

### Task 3.3: Qdrant-SQLite Sync with Retry Queue

| Field | Value |
|-------|-------|
| **Priority** | P2 - Medium |
| **Est. Time** | 3 hours |
| **Assignee** | เดฟ (Dev) |
| **Reviewer** | Mneme |
| **Dependencies** | Phase 1 (SynapseService) |

#### Problem

Qdrant และ SQLite ไม่ sync กัน — ถ้า Qdrant fail หลัง SQLite commit แล้ว ข้อมูลไม่ตรง

**Evidence**:
```python
# semantic.py
self._index_entity(node)  # Index to Qdrant (might fail)
# TODO: Persist to Graphiti
# No retry, no sync verification
```

#### Files to Create/Modify

| File | Action |
|------|--------|
| `synapse/services/sync_queue.py` | CREATE - Retry queue |
| `synapse/services/__init__.py` | MODIFY - Export |
| `synapse/layers/episodic.py` | MODIFY - Use sync queue |
| `synapse/layers/semantic.py` | MODIFY - Use sync queue |

#### Implementation Details

**Step 1: Create `synapse/services/sync_queue.py`**

```python
"""
SyncQueue - Ensures Qdrant and SQLite stay synchronized

Handles:
- Retry on failure
- Exponential backoff
- Sync verification
- Background processing
"""

import asyncio
import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
import json

logger = logging.getLogger(__name__)


class SyncStatus(Enum):
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
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize sync queue.

        Args:
            db_path: Path to queue database (default: ~/.synapse/sync_queue.db)
        """
        if db_path is None:
            db_path = Path.home() / ".synapse" / "sync_queue.db"

        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_db()

        # Handlers for different operations
        self._handlers: Dict[str, Callable] = {}

        # Background task
        self._background_task: Optional[asyncio.Task] = None
        self._running = False

    def _ensure_db(self):
        """Create queue tables if not exist."""
        conn = sqlite3.connect(self.db_path)
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
        conn.commit()
        conn.close()

    def register_handler(
        self,
        operation: str,
        handler: Callable[[SyncTask], Awaitable[bool]],
    ):
        """Register a handler for an operation type."""
        self._handlers[operation] = handler

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
            max_attempts: Max retry attempts

        Returns:
            Task ID
        """
        now = datetime.now().isoformat()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("""
            INSERT INTO sync_queue
            (operation, entity_type, entity_id, payload, status, max_attempts, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'pending', ?, ?, ?)
        """, (
            operation,
            entity_type,
            entity_id,
            json.dumps(payload),
            max_attempts,
            now,
            now,
        ))
        task_id = cursor.lastrowid
        conn.commit()
        conn.close()

        logger.debug(f"Enqueued sync task: {task_id} ({operation} {entity_type}/{entity_id})")
        return task_id

    def get_pending(self, limit: int = 100) -> List[SyncTask]:
        """Get pending tasks ready for processing."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        rows = conn.execute("""
            SELECT * FROM sync_queue
            WHERE status IN ('pending', 'failed')
            AND attempts < max_attempts
            ORDER BY created_at ASC
            LIMIT ?
        """, (limit,)).fetchall()

        tasks = []
        for row in rows:
            tasks.append(SyncTask(
                id=row["id"],
                operation=row["operation"],
                entity_type=row["entity_type"],
                entity_id=row["entity_id"],
                payload=json.loads(row["payload"]),
                status=SyncStatus(row["status"]),
                attempts=row["attempts"],
                max_attempts=row["max_attempts"],
                last_error=row["last_error"],
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
            ))

        conn.close()
        return tasks

    def update_task(self, task: SyncTask):
        """Update task status."""
        now = datetime.now().isoformat()

        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            UPDATE sync_queue
            SET status = ?, attempts = ?, last_error = ?, updated_at = ?
            WHERE id = ?
        """, (
            task.status.value,
            task.attempts,
            task.last_error,
            now,
            task.id,
        ))
        conn.commit()
        conn.close()

    async def process_one(self, task: SyncTask) -> bool:
        """Process a single sync task."""
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
                logger.info(f"Sync task completed: {task.id}")
                return True
            else:
                raise Exception("Handler returned False")

        except Exception as e:
            task.last_error = str(e)

            if task.attempts >= task.max_attempts:
                task.status = SyncStatus.RETRY_EXHAUSTED
                logger.error(f"Sync task exhausted retries: {task.id} - {e}")
            else:
                task.status = SyncStatus.FAILED
                logger.warning(f"Sync task failed (attempt {task.attempts}): {task.id} - {e}")

            self.update_task(task)
            return False

    async def process_all(self, limit: int = 100):
        """Process all pending tasks."""
        tasks = self.get_pending(limit)

        for task in tasks:
            await self.process_one(task)

            # Exponential backoff between tasks
            if task.status == SyncStatus.FAILED:
                await asyncio.sleep(2 ** task.attempts)

    async def start_background(self, interval: int = 60):
        """Start background processing."""
        if self._running:
            return

        self._running = True

        async def _loop():
            while self._running:
                try:
                    await self.process_all()
                except Exception as e:
                    logger.error(f"Background sync error: {e}")

                await asyncio.sleep(interval)

        self._background_task = asyncio.create_task(_loop())
        logger.info(f"Background sync started (interval: {interval}s)")

    def stop_background(self):
        """Stop background processing."""
        self._running = False
        if self._background_task:
            self._background_task.cancel()
            self._background_task = None

    def get_stats(self) -> Dict[str, int]:
        """Get queue statistics."""
        conn = sqlite3.connect(self.db_path)

        stats = {}
        for status in SyncStatus:
            count = conn.execute(
                "SELECT COUNT(*) FROM sync_queue WHERE status = ?",
                (status.value,)
            ).fetchone()[0]
            stats[status.value] = count

        conn.close()
        return stats
```

**Step 2: Modify `synapse/layers/episodic.py` to use SyncQueue**

```python
# In record_episode method
def record_episode(self, content: str, source: str, ...) -> Episode:
    # ... existing SQLite save ...

    # Queue sync to Qdrant (instead of direct call)
    if self._sync_queue:
        self._sync_queue.enqueue(
            operation="index",
            entity_type="episode",
            entity_id=episode.id,
            payload={
                "content": episode.content,
                "summary": episode.summary,
                "metadata": episode.metadata,
            },
        )
    else:
        # Fallback to direct indexing
        self._index_episode(episode, access_count=0)

    return episode
```

**Step 3: Add sync verification**

```python
async def verify_sync(self) -> Dict[str, Any]:
    """
    Verify SQLite and Qdrant are in sync.

    Returns:
        Dict with sync status and any discrepancies
    """
    conn = self._get_connection()

    # Get all episode IDs from SQLite
    sqlite_ids = set(
        row["id"]
        for row in conn.execute("SELECT id FROM episodes").fetchall()
    )

    # Get all episode IDs from Qdrant
    qdrant_ids = set()
    if self._qdrant_client:
        try:
            results = self._qdrant_client.scroll(
                collection_name=self._collection_name,
                limit=10000,
            )
            qdrant_ids = {str(p.id) for p in results[0]}
        except Exception as e:
            logger.error(f"Failed to get Qdrant IDs: {e}")

    # Find discrepancies
    only_sqlite = sqlite_ids - qdrant_ids
    only_qdrant = qdrant_ids - sqlite_ids

    return {
        "in_sync": len(only_sqlite) == 0 and len(only_qdrant) == 0,
        "sqlite_count": len(sqlite_ids),
        "qdrant_count": len(qdrant_ids),
        "only_in_sqlite": list(only_sqlite),
        "only_in_qdrant": list(only_qdrant),
    }
```

#### Acceptance Criteria

- [ ] SyncQueue class created with persistent storage
- [ ] Retry with exponential backoff works
- [ ] Background processing works
- [ ] Sync verification returns discrepancies
- [ ] Feature flag `SYNAPSE_USE_SYNC_QUEUE` works

#### Test Cases

```python
@pytest.mark.asyncio
async def test_sync_queue_enqueue():
    queue = SyncQueue(db_path=Path(":memory:"))

    task_id = queue.enqueue(
        operation="index",
        entity_type="episode",
        entity_id="test-123",
        payload={"content": "test"},
    )

    assert task_id > 0

    tasks = queue.get_pending()
    assert len(tasks) == 1
    assert tasks[0].entity_id == "test-123"

@pytest.mark.asyncio
async def test_sync_queue_retry():
    queue = SyncQueue(db_path=Path(":memory:"))

    # Handler that fails twice then succeeds
    call_count = 0

    async def failing_handler(task):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise Exception("Simulated failure")
        return True

    queue.register_handler("index", failing_handler)

    task_id = queue.enqueue("index", "episode", "test", {}, max_attempts=3)

    # Process until complete
    for _ in range(3):
        tasks = queue.get_pending()
        if not tasks:
            break
        await queue.process_one(tasks[0])

    assert call_count == 3

@pytest.mark.asyncio
async def test_verify_sync():
    manager = EpisodicManager()

    # Add episode
    episode = manager.record_episode("Test content", source="test")

    # Verify sync
    sync_status = await manager.verify_sync()

    # Should be in sync after indexing
    # (May need to wait for async indexing)
    assert "in_sync" in sync_status
```

---

## Phase 3 Milestone

### M3: Phase 3 Complete

**Completion Criteria**:
- [ ] Archive before purge working
- [ ] search_all() includes all 5 layers
- [ ] Sync queue with retry working
- [ ] All tests passing
- [ ] No P2 bugs remaining

**Verification Commands**:

```bash
# Test archive functionality
curl -X POST http://localhost:47780/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "add_memory",
      "arguments": {
        "name": "test_archive",
        "episode_body": "This will be archived",
        "source_description": "test"
      }
    },
    "id": 1
  }'

# Test search includes all layers
curl -X POST http://localhost:47780/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "search_memory",
      "arguments": {"query": "test"}
    },
    "id": 2
  }'

# Check sync queue stats
docker compose exec synapse-server python -c "
from synapse.services.sync_queue import SyncQueue
q = SyncQueue()
print(q.get_stats())
"
```

---

## Review Checklist (Mneme)

### Code Review

- [ ] Archive table has proper indexes
- [ ] Sync queue is thread-safe
- [ ] Error messages are helpful
- [ ] No SQL injection vulnerabilities

### Integration Review

- [ ] Archive doesn't affect normal operations
- [ ] Search performance is acceptable
- [ ] Sync queue doesn't block main operations

### Data Integrity Review

- [ ] Archive preserves all data
- [ ] Restore recovers all fields
- [ ] Sync verification catches discrepancies

---

## Rollback Plan

```bash
# Disable sync queue
export SYNAPSE_USE_SYNC_QUEUE=false

# Revert code
git revert HEAD~N
docker compose restart synapse-server

# Archive table is separate, safe to drop if needed
# sqlite> DROP TABLE IF EXISTS episodes_archive;
```

---

*Phase 3 Plan created: 2026-03-16*
*Assignee: เดฟ (Dev) 🦀*
*Reviewer: Mneme 🧠*
