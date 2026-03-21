"""Lightweight telemetry for hybrid search."""

from __future__ import annotations

import math
import threading
from collections import Counter, defaultdict, deque
from typing import Any, Dict


class HybridSearchTelemetry:
    """In-memory counters and latency samples."""

    def __init__(self):
        self._lock = threading.Lock()
        self._counts = Counter()
        self._latencies = defaultdict(lambda: deque(maxlen=500))

    def record_query(self, event: Dict[str, Any]) -> None:
        with self._lock:
            mode = str(event.get("mode", "unknown"))
            query_type = str(event.get("query_type_detected", "unknown"))
            self._counts["queries_total"] += 1
            self._counts[f"queries_mode:{mode}"] += 1
            self._counts[f"queries_type:{query_type}"] += 1
            self._counts[f"degraded:{bool(event.get('degraded'))}"] += 1
            if event.get("strict_failure"):
                self._counts["strict_failures"] += 1
            for cache_name in ("query", "embedding", "graph"):
                if event.get(f"cache_hit_{cache_name}"):
                    self._counts[f"cache_hit:{cache_name}"] += 1
            for backend in event.get("used_backends", []):
                self._counts[f"backend_used:{backend}"] += 1
            for backend in event.get("timeouts", []):
                self._counts[f"backend_timeout:{backend}"] += 1

            self._latencies["total"].append(float(event.get("latency_ms_total", 0.0)))
            for backend_name in ("lexical", "vector", "graph", "structured", "rerank"):
                latency_value = float(event.get(f"latency_ms_{backend_name}", 0.0))
                if latency_value > 0:
                    self._latencies[backend_name].append(latency_value)

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "counts": dict(self._counts),
                "latency_ms": {
                    name: self._percentiles(list(samples))
                    for name, samples in self._latencies.items()
                },
            }

    @staticmethod
    def _percentiles(values: list[float]) -> Dict[str, float]:
        if not values:
            return {"p50": 0.0, "p95": 0.0, "p99": 0.0}
        ordered = sorted(values)
        return {
            "p50": round(HybridSearchTelemetry._pick_percentile(ordered, 0.50), 3),
            "p95": round(HybridSearchTelemetry._pick_percentile(ordered, 0.95), 3),
            "p99": round(HybridSearchTelemetry._pick_percentile(ordered, 0.99), 3),
        }

    @staticmethod
    def _pick_percentile(values: list[float], fraction: float) -> float:
        if not values:
            return 0.0
        index = max(0, min(len(values) - 1, math.ceil(len(values) * fraction) - 1))
        return float(values[index])
