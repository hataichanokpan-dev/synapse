"""Types and contracts for hybrid search."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from synapse.layers import MemoryLayer


class SearchMode(str, Enum):
    LEGACY = "legacy"
    HYBRID_AUTO = "hybrid_auto"
    HYBRID_STRICT = "hybrid_strict"


class QueryType(str, Enum):
    AUTO = "auto"
    EXACT = "exact"
    SEMANTIC = "semantic"
    RELATIONAL = "relational"
    PROCEDURAL = "procedural"
    EPISODIC = "episodic"
    PREFERENCE = "preference"
    MIXED = "mixed"


@dataclass
class HybridCandidate:
    """Unified candidate from any retrieval backend."""

    record_id: str
    layer: MemoryLayer
    payload: Dict[str, Any]
    backend_scores: Dict[str, float] = field(default_factory=dict)
    backend_ranks: Dict[str, int] = field(default_factory=dict)
    sources: List[str] = field(default_factory=list)
    matched_terms: List[str] = field(default_factory=list)
    match_reasons: List[str] = field(default_factory=list)
    degraded_backends: List[str] = field(default_factory=list)
    freshness: float = 0.0
    usage_signal: float = 0.0
    exact_match: bool = False
    path: Optional[List[str]] = None
    fused_score: float = 0.0
    final_score: float = 0.0
    score_breakdown: Optional[Dict[str, float]] = None

    def merge(self, other: "HybridCandidate") -> None:
        """Merge another candidate for the same record."""
        self.backend_scores.update(other.backend_scores)
        self.backend_ranks.update(other.backend_ranks)
        self.sources = sorted(set(self.sources + other.sources))
        self.matched_terms = sorted(set(self.matched_terms + other.matched_terms))
        self.match_reasons = sorted(set(self.match_reasons + other.match_reasons))
        self.degraded_backends = sorted(set(self.degraded_backends + other.degraded_backends))
        self.freshness = max(self.freshness, other.freshness)
        self.usage_signal = max(self.usage_signal, other.usage_signal)
        self.exact_match = self.exact_match or other.exact_match
        if self.path is None and other.path:
            self.path = other.path


@dataclass
class HybridSearchPlan:
    """Execution plan for a hybrid query."""

    query: str
    normalized_query: str
    query_type: QueryType
    mode: SearchMode
    limit: int
    layers: List[MemoryLayer]
    explain: bool
    user_id: Optional[str]
    group_id: Optional[str]
    lexical_budget: int
    vector_budget: int
    graph_budget: int
    total_timeout_ms: int
    timeout_ms_by_backend: Dict[str, int]
    rerank_top_k: int
    weights: Dict[str, float]


class HybridSearchError(RuntimeError):
    """Raised when strict hybrid search cannot satisfy backend requirements."""

    def __init__(self, message: str, *, degraded_backends: Optional[List[str]] = None):
        super().__init__(message)
        self.degraded_backends = degraded_backends or []
