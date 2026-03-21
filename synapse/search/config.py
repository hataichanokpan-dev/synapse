"""Hybrid search configuration and weights loading."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Dict

import yaml

from .types import QueryType

DEFAULT_WEIGHTS = {
    QueryType.EXACT.value: {"lexical": 1.4, "vector": 0.8, "graph": 0.6, "structured": 1.2},
    QueryType.SEMANTIC.value: {"lexical": 1.0, "vector": 1.3, "graph": 0.9, "structured": 0.8},
    QueryType.RELATIONAL.value: {"lexical": 0.8, "vector": 0.9, "graph": 1.5, "structured": 0.7},
    QueryType.PROCEDURAL.value: {"lexical": 1.2, "vector": 1.0, "graph": 0.7, "structured": 0.6},
    QueryType.EPISODIC.value: {"lexical": 1.1, "vector": 1.0, "graph": 0.6, "structured": 0.7},
    QueryType.PREFERENCE.value: {"lexical": 1.0, "vector": 0.4, "graph": 0.3, "structured": 1.5},
    QueryType.MIXED.value: {"lexical": 1.0, "vector": 1.0, "graph": 1.0, "structured": 1.0},
}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


class SearchWeights:
    """Loads hybrid ranking weights with file reload support."""

    def __init__(self, path: str | None = None):
        self.path = Path(path or os.getenv("SYNAPSE_HYBRID_WEIGHTS_PATH", "config/hybrid_weights.yaml"))
        self._loaded_at = 0.0
        self._mtime = -1.0
        self._values: Dict[str, Dict[str, float]] = {key: dict(value) for key, value in DEFAULT_WEIGHTS.items()}
        self.version = "builtin"

    def _reload_if_needed(self) -> None:
        now = time.monotonic()
        if now - self._loaded_at < 60:
            return
        self._loaded_at = now

        if not self.path.exists():
            self._values = {key: dict(value) for key, value in DEFAULT_WEIGHTS.items()}
            self.version = "builtin"
            self._mtime = -1.0
            return

        try:
            stat = self.path.stat()
        except OSError:
            return
        if stat.st_mtime == self._mtime:
            return

        try:
            data = yaml.safe_load(self.path.read_text(encoding="utf-8")) or {}
            weights = data.get("weights", {})
        except Exception:
            self._values = {key: dict(value) for key, value in DEFAULT_WEIGHTS.items()}
            self.version = "builtin-invalid"
            self._mtime = stat.st_mtime
            return

        loaded: Dict[str, Dict[str, float]] = {}
        for key, defaults in DEFAULT_WEIGHTS.items():
            loaded[key] = dict(defaults)
            override = weights.get(key, {})
            if isinstance(override, dict):
                for backend, value in override.items():
                    try:
                        loaded[key][backend] = float(value)
                    except (TypeError, ValueError):
                        continue

        self._values = loaded
        self.version = str(data.get("version", stat.st_mtime))
        self._mtime = stat.st_mtime

    def get(self, query_type: str) -> Dict[str, float]:
        self._reload_if_needed()
        if query_type in self._values:
            return dict(self._values[query_type])
        return dict(self._values[QueryType.MIXED.value])

    @property
    def rrf_k(self) -> int:
        return _env_int("SYNAPSE_HYBRID_RRF_K", 60)

    @property
    def rerank_top_k(self) -> int:
        return _env_int("SYNAPSE_HYBRID_RERANK_TOP_K", 25)
