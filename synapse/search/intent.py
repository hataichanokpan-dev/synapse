"""Heuristic query intent analysis for hybrid search."""

from __future__ import annotations

import re
from typing import Iterable

from .types import QueryType

_EXACT_PATTERNS = (
    re.compile(r'"[^"]+"'),
    re.compile(r"'[^']+'"),
    re.compile(r"\b[A-Z]{2,}-\d+\b"),
    re.compile(r"[A-Za-z0-9_/\.-]{8,}"),
)

_PROCEDURAL_TERMS = {
    "how", "steps", "procedure", "workflow", "deploy", "setup", "install",
    "fix", "runbook", "backup", "migrate", "command",
}
_EPISODIC_TERMS = {
    "when", "happened", "meeting", "session", "yesterday", "today", "last time",
    "remember", "episode", "discussion", "timeline",
}
_RELATIONAL_TERMS = {
    "related", "relationship", "depends", "depends on", "between", "connected",
    "works on", "works with", "linked", "graph",
}
_PREFERENCE_TERMS = {
    "prefer", "preference", "style", "timezone", "language", "usually",
    "likes", "dislikes", "response length", "response style",
}


class QueryIntentAnalyzer:
    """Simple heuristic query classifier for hybrid search."""

    def analyze(self, query: str, requested: str | None = None, layers: Iterable[str] | None = None) -> QueryType:
        if requested and requested != QueryType.AUTO.value:
            return QueryType(requested)

        text = (query or "").strip().lower()
        if not text:
            return QueryType.MIXED

        if layers:
            normalized_layers = {str(layer).strip().lower() for layer in layers}
            if normalized_layers == {"user_model"}:
                return QueryType.PREFERENCE

        if any(pattern.search(query or "") for pattern in _EXACT_PATTERNS):
            return QueryType.EXACT

        if any(term in text for term in _RELATIONAL_TERMS):
            return QueryType.RELATIONAL

        if any(term in text for term in _PROCEDURAL_TERMS):
            return QueryType.PROCEDURAL

        if any(term in text for term in _EPISODIC_TERMS):
            return QueryType.EPISODIC

        if any(term in text for term in _PREFERENCE_TERMS):
            return QueryType.PREFERENCE

        if len(text.split()) <= 3:
            return QueryType.SEMANTIC

        return QueryType.MIXED
