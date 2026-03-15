"""
Layer 3: Semantic Memory

Principles, patterns, and learnings.
NORMAL DECAY - λ = 0.01, half-life ~69 days

Storage:
- Graph: Entity nodes + Fact edges (via Graphiti)
- Vector: Qdrant for embeddings

This layer wraps Graphiti's functionality with:
- Decay scoring on retrieval
- Supersede pattern for outdated facts
- Layer classification for entities
- Thai NLP preprocessing for better extraction
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

from synapse.storage import QdrantClient

from .types import (
    SynapseNode,
    SynapseEdge,
    SearchResult,
    MemoryLayer,
    EntityType,
    RelationType,
    utcnow,
)
from .decay import compute_decay_score, should_forget

logger = logging.getLogger(__name__)
DEFAULT_COLLECTION_NAME = "semantic_memory"

# Lazy import for Thai NLP
_nlp_preprocessor = None


def _get_nlp_preprocessor():
    """Get NLP preprocessor (lazy import)."""
    global _nlp_preprocessor
    if _nlp_preprocessor is None:
        try:
            from synapse.nlp.preprocess import get_preprocessor
            _nlp_preprocessor = get_preprocessor()
        except ImportError:
            _nlp_preprocessor = False  # Mark as unavailable
    return _nlp_preprocessor if _nlp_preprocessor else None


class SemanticManager:
    """
    Manager for Layer 3: Semantic Memory.

    Wraps Graphiti with decay scoring and supersede patterns.
    """

    def __init__(
        self,
        graphiti_client=None,
        vector_client: Optional[QdrantClient] = None,
        collection_name: str = DEFAULT_COLLECTION_NAME,
    ):
        """
        Initialize Semantic Memory Manager.

        Args:
            graphiti_client: Graphiti client instance (optional, lazy-loaded)
        """
        self._graphiti = graphiti_client
        self.vector_client = vector_client or QdrantClient()
        self.collection_name = collection_name
        self._initialized = False
        self._vector_warning_emitted = False

    async def _ensure_graphiti(self, require: bool = False) -> bool:
        """Ensure Graphiti client is initialized when available."""
        if self._graphiti is None:
            try:
                from graphiti_core import Graphiti

                self._graphiti = Graphiti()
                self._initialized = True
            except Exception as exc:
                if require:
                    raise RuntimeError(
                        "Graphiti not available. Install graphiti-core or provide client."
                    ) from exc
                return False
        return True

    def _warn_vector_issue(self, exc: Exception) -> None:
        """Log a single warning when Qdrant is unavailable."""
        if self._vector_warning_emitted:
            return

        logger.warning("Semantic memory Qdrant integration unavailable: %s", exc)
        self._vector_warning_emitted = True

    def _index_entity(self, node: SynapseNode) -> None:
        """Store entity text and metadata in Qdrant."""
        try:
            self.vector_client.upsert(
                collection_name=self.collection_name,
                points=[
                    {
                        "id": node.id,
                        "text": "\n".join(part for part in [node.name, node.summary or ""] if part),
                        "payload": {
                            "node_id": node.id,
                            "entity_type": node.type.value,
                            "name": node.name,
                            "summary": node.summary,
                            "memory_layer": node.memory_layer.value,
                            "confidence": node.confidence,
                            "decay_score": node.decay_score,
                            "access_count": node.access_count,
                            "created_at": node.created_at.isoformat(),
                            "updated_at": node.updated_at.isoformat(),
                            "expires_at": node.expires_at.isoformat() if node.expires_at else None,
                            "source_episode": node.source_episode,
                            "created_by": node.created_by,
                        },
                    }
                ],
            )
        except Exception as exc:
            self._warn_vector_issue(exc)

    def _payload_to_node(self, payload: Dict[str, Any]) -> Optional[SynapseNode]:
        """Convert a Qdrant payload into a SynapseNode."""
        node_id = payload.get("node_id")
        entity_type = payload.get("entity_type")
        name = payload.get("name")

        if node_id is None or entity_type is None or name is None:
            return None

        return SynapseNode(
            id=str(node_id),
            type=EntityType(str(entity_type)),
            name=str(name),
            summary=payload.get("summary"),
            memory_layer=MemoryLayer(str(payload.get("memory_layer", MemoryLayer.SEMANTIC.value))),
            confidence=float(payload.get("confidence", 0.7)),
            decay_score=float(payload.get("decay_score", 1.0)),
            access_count=int(payload.get("access_count", 0)),
            created_at=self._parse_datetime(payload.get("created_at")) or utcnow(),
            updated_at=self._parse_datetime(payload.get("updated_at")) or utcnow(),
            expires_at=self._parse_datetime(payload.get("expires_at")),
            source_episode=payload.get("source_episode"),
            created_by=str(payload.get("created_by", "synapse")),
        )

    def _parse_datetime(self, dt_str: Optional[str]) -> Optional[datetime]:
        """Parse ISO format datetime string."""
        if dt_str is None:
            return None

        if dt_str.endswith('Z'):
            dt_str = dt_str[:-1] + '+00:00'

        try:
            return datetime.fromisoformat(dt_str)
        except ValueError:
            return None

    async def add_entity(
        self,
        name: str,
        entity_type: EntityType,
        summary: Optional[str] = None,
        memory_layer: MemoryLayer = MemoryLayer.SEMANTIC,
        confidence: float = 0.7,
        source_episode: Optional[str] = None,
        preprocess: bool = True,
    ) -> SynapseNode:
        """
        Add an entity to semantic memory.

        Args:
            name: Entity name
            entity_type: Type of entity
            summary: Evolving summary of the entity
            memory_layer: Which memory layer (default: SEMANTIC)
            confidence: Confidence score (0.0 to 1.0)
            source_episode: Source episode ID
            preprocess: Apply Thai NLP preprocessing

        Returns:
            Created SynapseNode
        """
        await self._ensure_graphiti()

        now = utcnow()

        # Preprocess name and summary for Thai
        processed_name = name
        processed_summary = summary
        if preprocess:
            preprocessor = _get_nlp_preprocessor()
            if preprocessor:
                result = preprocessor.preprocess_for_extraction(name)
                processed_name = result.processed

                if summary:
                    summary_result = preprocessor.preprocess_for_extraction(summary)
                    processed_summary = summary_result.processed

        node_id = f"entity_{processed_name.lower().replace(' ', '_')}_{int(now.timestamp())}"

        node = SynapseNode(
            id=node_id,
            type=entity_type,
            name=processed_name,
            summary=processed_summary,
            memory_layer=memory_layer,
            confidence=confidence,
            decay_score=1.0,  # Fresh node
            access_count=0,
            created_at=now,
            updated_at=now,
            source_episode=source_episode,
        )

        # TODO: Persist to Graphiti
        # await self._graphiti.add_node(node)
        self._index_entity(node)

        return node

    async def add_fact(
        self,
        source_id: str,
        target_id: str,
        relation_type: RelationType,
        confidence: float = 0.7,
        valid_at: Optional[datetime] = None,
        source_episode: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SynapseEdge:
        """
        Add a fact (relationship) to semantic memory.

        Args:
            source_id: Source node ID
            target_id: Target node ID
            relation_type: Type of relationship
            confidence: Confidence score
            valid_at: When this became true (default: now)
            source_episode: Source episode ID
            metadata: Additional metadata

        Returns:
            Created SynapseEdge
        """
        await self._ensure_graphiti()

        now = utcnow()
        edge_id = f"edge_{source_id}_{relation_type}_{target_id}"

        edge = SynapseEdge(
            id=edge_id,
            source_id=source_id,
            target_id=target_id,
            type=relation_type,
            valid_at=valid_at or now,
            invalid_at=None,
            confidence=confidence,
            source_episode=source_episode,
            metadata=metadata or {},
        )

        # TODO: Persist to Graphiti
        # await self._graphiti.add_edge(edge)

        return edge

    async def search(
        self,
        query: str,
        limit: int = 10,
        min_score: float = 0.1,
        entity_types: Optional[List[EntityType]] = None,
        use_hybrid: bool = True,
        preprocess_query: bool = True,
    ) -> List[SearchResult]:
        """
        Search semantic memory.

        Args:
            query: Search query
            limit: Maximum results
            min_score: Minimum decay score threshold
            entity_types: Filter by entity types
            use_hybrid: Use hybrid search (vector + FTS + graph)
            preprocess_query: Apply Thai NLP preprocessing

        Returns:
            List of SearchResult
        """
        now = utcnow()
        filters: Dict[str, Any] = {}

        if entity_types:
            filters["entity_type"] = [entity_type.value for entity_type in entity_types]

        try:
            matches = self.vector_client.search(
                collection_name=self.collection_name,
                query_text=query,
                limit=max(limit * 3, limit),
                filters=filters or None,
            )
        except Exception as exc:
            self._warn_vector_issue(exc)
            return []

        results = []

        for match in matches:
            node = self._payload_to_node(match["payload"])
            if node is None:
                continue

            decay_score = self.compute_decay_score(node, now)
            vector_score = max(0.0, min(1.0, float(match.get("score", 0.0))))
            combined_score = max(0.0, min(1.0, (vector_score + decay_score) / 2.0))

            if combined_score < min_score:
                continue

            results.append(
                SearchResult(
                    node=node,
                    score=combined_score,
                    source="vector",
                )
            )

            if len(results) >= limit:
                break

        return results

    async def get_entity(self, entity_id: str) -> Optional[SynapseNode]:
        """
        Get entity by ID.

        Increments access count and updates decay score.

        Args:
            entity_id: Entity identifier

        Returns:
            SynapseNode or None
        """
        await self._ensure_graphiti()

        # TODO: Implement actual Graphiti query
        return None

    async def supersede_fact(
        self,
        old_edge_id: str,
        new_edge: SynapseEdge,
    ) -> SynapseEdge:
        """
        Mark old fact as superseded by new fact.

        Sets invalid_at on old edge and creates new edge.

        Args:
            old_edge_id: ID of edge to supersede
            new_edge: New edge to create

        Returns:
            Created new SynapseEdge
        """
        await self._ensure_graphiti()

        now = utcnow()

        # Mark old edge as invalid
        # TODO: await self._graphiti.update_edge(old_edge_id, invalid_at=now)

        # Create new edge
        new_edge.valid_at = now
        new_edge.metadata["supersedes"] = old_edge_id

        # TODO: await self._graphiti.add_edge(new_edge)

        return new_edge

    async def update_entity(
        self,
        entity_id: str,
        summary: Optional[str] = None,
        confidence: Optional[float] = None,
    ) -> Optional[SynapseNode]:
        """
        Update entity properties.

        Args:
            entity_id: Entity identifier
            summary: New summary (appended to existing)
            confidence: New confidence score

        Returns:
            Updated SynapseNode or None
        """
        await self._ensure_graphiti()

        # TODO: Implement actual update
        return None

    def compute_decay_score(
        self,
        node: SynapseNode,
        now: Optional[datetime] = None,
    ) -> float:
        """
        Compute decay score for a node.

        Args:
            node: SynapseNode to compute score for
            now: Current time

        Returns:
            Decay score (0.0 to 1.0)
        """
        return compute_decay_score(
            updated_at=node.updated_at,
            access_count=node.access_count,
            memory_layer=node.memory_layer,
            now=now,
        )

    async def should_forget_node(
        self,
        node: SynapseNode,
        now: Optional[datetime] = None,
    ) -> bool:
        """
        Check if node should be forgotten.

        Args:
            node: SynapseNode to check
            now: Current time

        Returns:
            True if should forget
        """
        decay_score = self.compute_decay_score(node, now)
        return should_forget(decay_score, node.expires_at, now)

    async def get_related_entities(
        self,
        entity_id: str,
        relation_types: Optional[List[RelationType]] = None,
        max_depth: int = 2,
        limit: int = 20,
    ) -> List[SynapseNode]:
        """
        Get entities related to a given entity.

        Args:
            entity_id: Starting entity ID
            relation_types: Filter by relation types
            max_depth: Maximum traversal depth
            limit: Maximum results

        Returns:
            List of related SynapseNodes
        """
        await self._ensure_graphiti()

        # TODO: Implement graph traversal
        return []

    async def cleanup_forgotten(self, batch_size: int = 100) -> int:
        """
        Remove forgotten nodes from storage.

        Args:
            batch_size: Number of nodes to process per batch

        Returns:
            Number of nodes removed
        """
        await self._ensure_graphiti()

        count = 0

        # TODO: Implement cleanup
        # 1. Find nodes with decay_score < threshold
        # 2. Archive before deletion (optional)
        # 3. Delete from graph and vector store

        return count


# Singleton instance
_manager: Optional[SemanticManager] = None


def get_manager(graphiti_client=None) -> SemanticManager:
    """Get singleton SemanticManager instance."""
    global _manager
    if _manager is None:
        _manager = SemanticManager(graphiti_client)
    return _manager


# Async convenience functions
async def search(query: str, limit: int = 10) -> List[SearchResult]:
    """Search semantic memory."""
    return await get_manager().search(query, limit)


async def add_entity(name: str, entity_type: EntityType, **kwargs) -> SynapseNode:
    """Add entity to semantic memory."""
    return await get_manager().add_entity(name, entity_type, **kwargs)


async def add_fact(source_id: str, target_id: str, relation_type: RelationType, **kwargs) -> SynapseEdge:
    """Add fact to semantic memory."""
    return await get_manager().add_fact(source_id, target_id, relation_type, **kwargs)
