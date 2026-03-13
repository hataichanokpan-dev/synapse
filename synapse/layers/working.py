"""
Layer 5: Working Memory

Session context and temporary data.
SESSION-BASED - No persistence, cleared on session end

Storage:
- In-memory dict only (no persistence)

Working memory is ephemeral and never decays (it's either alive or dead).
It's useful for:
- Current conversation context
- Temporary variables
- Session state
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime
import threading

from .types import MemoryLayer, utcnow


@dataclass
class WorkingContext:
    """
    A single working memory context entry.
    """
    key: str
    value: Any
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)
    access_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class WorkingManager:
    """
    Manager for Layer 5: Working Memory.

    In-memory only, no persistence. Cleared on session end.
    """

    def __init__(self):
        """Initialize Working Memory Manager."""
        self._context: Dict[str, WorkingContext] = {}
        self._session_id: Optional[str] = None
        self._session_started_at: Optional[datetime] = None
        self._lock = threading.Lock()

    def set_session(self, session_id: str) -> None:
        """
        Set the current session ID.

        Clears previous session's context.

        Args:
            session_id: Session identifier
        """
        with self._lock:
            self.clear_context()
            self._session_id = session_id
            self._session_started_at = utcnow()

    def get_session_id(self) -> Optional[str]:
        """
        Get current session ID.

        Returns:
            Session ID or None
        """
        return self._session_id

    def set_context(
        self,
        key: str,
        value: Any,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> WorkingContext:
        """
        Set a context value.

        Args:
            key: Context key
            value: Context value
            metadata: Optional metadata

        Returns:
            Created/Updated WorkingContext
        """
        now = utcnow()

        with self._lock:
            if key in self._context:
                # Update existing
                ctx = self._context[key]
                ctx.value = value
                ctx.updated_at = now
                ctx.access_count += 1
                if metadata:
                    ctx.metadata.update(metadata)
            else:
                # Create new
                ctx = WorkingContext(
                    key=key,
                    value=value,
                    created_at=now,
                    updated_at=now,
                    access_count=0,
                    metadata=metadata or {},
                )
                self._context[key] = ctx

        return ctx

    def get_context(self, key: str, default: Any = None) -> Any:
        """
        Get a context value.

        Args:
            key: Context key
            default: Default value if key not found

        Returns:
            Context value or default
        """
        with self._lock:
            ctx = self._context.get(key)
            if ctx is None:
                return default
            ctx.access_count += 1
            ctx.updated_at = utcnow()
            return ctx.value

    def has_context(self, key: str) -> bool:
        """
        Check if context key exists.

        Args:
            key: Context key

        Returns:
            True if exists
        """
        return key in self._context

    def delete_context(self, key: str) -> bool:
        """
        Delete a context value.

        Args:
            key: Context key

        Returns:
            True if deleted, False if not found
        """
        with self._lock:
            if key in self._context:
                del self._context[key]
                return True
            return False

    def clear_context(self) -> int:
        """
        Clear all context values.

        Returns:
            Number of items cleared
        """
        with self._lock:
            count = len(self._context)
            self._context.clear()
            return count

    def get_all_context(self) -> Dict[str, Any]:
        """
        Get all context values.

        Returns:
            Dict of key -> value
        """
        with self._lock:
            return {k: v.value for k, v in self._context.items()}

    def get_context_keys(self) -> List[str]:
        """
        Get all context keys.

        Returns:
            List of keys
        """
        with self._lock:
            return list(self._context.keys())

    def get_context_stats(self) -> Dict[str, Any]:
        """
        Get statistics about working memory.

        Returns:
            Dict with statistics
        """
        with self._lock:
            total_access = sum(ctx.access_count for ctx in self._context.values())
            return {
                "session_id": self._session_id,
                "session_started_at": self._session_started_at.isoformat() if self._session_started_at else None,
                "context_count": len(self._context),
                "total_access_count": total_access,
                "keys": list(self._context.keys()),
            }

    def increment_counter(self, key: str, delta: int = 1) -> int:
        """
        Increment a counter in context.

        Creates counter if not exists.

        Args:
            key: Counter key
            delta: Amount to increment

        Returns:
            New counter value
        """
        with self._lock:
            current = self._context.get(key)
            if current is None:
                self.set_context(key, delta)
                return delta
            else:
                new_value = current.value + delta
                current.value = new_value
                current.updated_at = utcnow()
                current.access_count += 1
                return new_value

    def append_to_list(self, key: str, value: Any) -> List[Any]:
        """
        Append to a list in context.

        Creates list if not exists.

        Args:
            key: List key
            value: Value to append

        Returns:
            Updated list
        """
        with self._lock:
            current = self._context.get(key)
            if current is None:
                new_list = [value]
                self.set_context(key, new_list)
                return new_list
            else:
                if not isinstance(current.value, list):
                    # Convert to list
                    current.value = [current.value, value]
                else:
                    current.value.append(value)
                current.updated_at = utcnow()
                current.access_count += 1
                return current.value

    def merge_dict(self, key: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge updates into a dict in context.

        Creates dict if not exists.

        Args:
            key: Dict key
            updates: Dict to merge

        Returns:
            Updated dict
        """
        with self._lock:
            current = self._context.get(key)
            if current is None:
                self.set_context(key, updates.copy())
                return updates
            else:
                if not isinstance(current.value, dict):
                    # Convert to dict
                    current.value = {"_value": current.value}
                current.value.update(updates)
                current.updated_at = utcnow()
                current.access_count += 1
                return current.value

    def end_session(self) -> Dict[str, Any]:
        """
        End the current session.

        Clears all context and returns final stats.

        Returns:
            Final session statistics
        """
        stats = self.get_context_stats()
        self.clear_context()
        self._session_id = None
        self._session_started_at = None
        return stats


# Singleton instance
_manager: Optional[WorkingManager] = None


def get_manager() -> WorkingManager:
    """Get singleton WorkingManager instance."""
    global _manager
    if _manager is None:
        _manager = WorkingManager()
    return _manager


# Convenience functions
def set_context(key: str, value: Any, **kwargs) -> WorkingContext:
    """Set a context value."""
    return get_manager().set_context(key, value, **kwargs)


def get_context(key: str, default: Any = None) -> Any:
    """Get a context value."""
    return get_manager().get_context(key, default)


def clear_context() -> int:
    """Clear all context."""
    return get_manager().clear_context()


def set_session(session_id: str) -> None:
    """Set current session."""
    get_manager().set_session(session_id)


def end_session() -> Dict[str, Any]:
    """End current session."""
    return get_manager().end_session()
