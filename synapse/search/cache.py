"""Small in-process caches for hybrid search."""

from __future__ import annotations

import copy
import threading
import time
from collections import OrderedDict, defaultdict
from typing import Any


class TTLCache:
    """Simple TTL cache with bounded size."""

    def __init__(self, ttl_seconds: float, maxsize: int):
        self.ttl_seconds = ttl_seconds
        self.maxsize = maxsize
        self._store: "OrderedDict[Any, tuple[float, Any]]" = OrderedDict()
        self._lock = threading.Lock()

    def _purge_expired_locked(self) -> None:
        now = time.monotonic()
        expired = [key for key, (expires_at, _) in self._store.items() if expires_at <= now]
        for key in expired:
            self._store.pop(key, None)

    def get(self, key: Any) -> Any | None:
        with self._lock:
            self._purge_expired_locked()
            entry = self._store.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if expires_at <= time.monotonic():
                self._store.pop(key, None)
                return None
            self._store.move_to_end(key)
            return copy.deepcopy(value)

    def set(self, key: Any, value: Any) -> None:
        with self._lock:
            self._purge_expired_locked()
            self._store[key] = (time.monotonic() + self.ttl_seconds, copy.deepcopy(value))
            self._store.move_to_end(key)
            while len(self._store) > self.maxsize:
                self._store.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()


class LayerGenerationTracker:
    """Tracks cache generations per layer/backend."""

    def __init__(self):
        self._values = defaultdict(int)
        self._lock = threading.Lock()

    def bump(self, *keys: str) -> None:
        with self._lock:
            for key in keys:
                if key:
                    self._values[str(key)] += 1

    def snapshot(self, *keys: str) -> tuple[int, ...]:
        with self._lock:
            return tuple(int(self._values.get(str(key), 0)) for key in keys)

    def get(self, key: str) -> int:
        with self._lock:
            return int(self._values.get(str(key), 0))
