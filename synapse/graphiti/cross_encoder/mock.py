"""
Mock Cross Encoder Client for Synapse.

A simple pass-through reranker that doesn't require external API calls.
Uses simple text matching for relevance scoring.
"""

import logging
from typing import Any

from graphiti_core.cross_encoder.client import CrossEncoderClient

logger = logging.getLogger(__name__)


class MockCrossEncoderClient(CrossEncoderClient):
    """
    Mock cross-encoder client that uses simple text matching.

    This doesn't require any external API and provides reasonable
    relevance scores based on term frequency overlap.
    """

    def __init__(self):
        """Initialize the mock cross encoder."""
        logger.info("[MockCrossEncoder] Initialized (no API key needed)")

    async def rank(
        self,
        query: str,
        passages: list[dict[str, Any]],
        top_n: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Rank passages by relevance to query using simple text matching.

        Args:
            query: The search query
            passages: List of passages to rank
            top_n: Number of top results to return

        Returns:
            Ranked list of passages with relevance scores
        """
        if not passages:
            return []

        # Simple scoring based on term overlap
        query_terms = set(query.lower().split())
        scored_passages = []

        for passage in passages:
            content = passage.get("content", "") or passage.get("text", "")
            content_terms = set(content.lower().split())

            # Calculate overlap score (Jaccard similarity)
            if query_terms and content_terms:
                intersection = len(query_terms & content_terms)
                union = len(query_terms | content_terms)
                score = intersection / union if union > 0 else 0.0
            else:
                score = 0.0

            # Boost score slightly to avoid all zeros
            score = 0.5 + (score * 0.5)

            scored_passages.append({
                **passage,
                "score": score,
            })

        # Sort by score descending
        scored_passages.sort(key=lambda x: x.get("score", 0), reverse=True)

        # Return top_n results
        return scored_passages[:top_n]
