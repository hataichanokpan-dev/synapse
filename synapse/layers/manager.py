"""
Layer Manager - Unified Memory API

Manages all five memory layers with:
- Automatic layer detection (LLM-based with keyword fallback)
- Cross-layer search
- Decay maintenance
- Memory consolidation
- User isolation support
"""

import logging
import os
from pathlib import Path
from typing import Optional, List, Dict, Any, Union

from .types import (
    MemoryLayer,
    UserModel,
    ProceduralMemory,
    SynapseNode,
    SynapseEdge,
    SynapseEpisode,
    SearchResult,
    EntityType,
    RelationType,
    utcnow,
)
from .user_model import UserModelManager, get_user_model, update_user_model
from .procedural import ProceduralManager, find_procedure, learn_procedure
from .semantic import SemanticManager, search as semantic_search
from .episodic import EpisodicManager, record_episode, find_episodes
from .working import WorkingManager, set_context, get_context, clear_context
from .decay import compute_decay_score, should_forget, DecayConfig
from .context import UserContext

logger = logging.getLogger(__name__)


class LayerManager:
    """
    Unified manager for all five memory layers.

    Provides a single API for memory operations across all layers.
    Supports user isolation via UserContext.
    """

    def __init__(
        self,
        user_model_manager: Optional[UserModelManager] = None,
        procedural_manager: Optional[ProceduralManager] = None,
        semantic_manager: Optional[SemanticManager] = None,
        episodic_manager: Optional[EpisodicManager] = None,
        working_manager: Optional[WorkingManager] = None,
        user_context: Optional[UserContext] = None,
        user_id: str = "default",
        llm_client: Optional[object] = None,
    ):
        """
        Initialize Layer Manager.

        Args:
            user_model_manager: Layer 1 manager
            procedural_manager: Layer 2 manager
            semantic_manager: Layer 3 manager
            episodic_manager: Layer 4 manager
            working_manager: Layer 5 manager
            user_context: UserContext for user isolation (takes precedence)
            user_id: User identifier (default: "default")
            llm_client: LLM client for classification
        """
        # If user_context is provided, use it for all managers
        if user_context is not None:
            self.user_model = user_context.user_model
            self.procedural = user_context.procedural
            self.semantic = user_context.semantic
            self.episodic = user_context.episodic
            self.working = user_context.working
            self.user_context = user_context
            self.user_id = user_context.user_id
        else:
            # Legacy: use individual managers
            # Layer 1: User Model
            self.user_model = user_model_manager or UserModelManager()

            # Layer 2: Procedural
            self.procedural = procedural_manager or ProceduralManager()

            # Layer 3: Semantic
            self.semantic = semantic_manager or SemanticManager()

            # Layer 4: Episodic
            self.episodic = episodic_manager or EpisodicManager()

            # Layer 5: Working
            self.working = working_manager or WorkingManager()

            self.user_context = None
            self.user_id = user_id

        # Initialize classifier
        from synapse.classifiers import LayerClassifier
        self._classifier = LayerClassifier(llm_client=llm_client, use_llm=True)

    # ==================== Layer 1: User Model ====================

    def get_user(self, user_id: str) -> UserModel:
        """Get user model."""
        return self.user_model.get_user_model(user_id)

    def update_user(self, user_id: str, **kwargs) -> UserModel:
        """Update user model."""
        return self.user_model.update_user_model(user_id, **kwargs)

    # ==================== Layer 2: Procedural ====================

    def find_procedures(self, trigger: str, limit: int = 5) -> List[ProceduralMemory]:
        """Find procedures matching trigger."""
        return self.procedural.find_procedure(trigger, limit)

    def learn_procedure(
        self,
        trigger: str,
        steps: List[str],
        source: str = "explicit",
        topics: Optional[List[str]] = None,
    ) -> ProceduralMemory:
        """Learn a new procedure."""
        return self.procedural.learn_procedure(trigger, steps, source, topics)

    def record_procedure_success(self, procedure_id: str) -> Optional[ProceduralMemory]:
        """Record successful use of procedure."""
        return self.procedural.record_success(procedure_id)

    # ==================== Layer 3: Semantic ====================

    async def search_semantic(
        self,
        query: str,
        limit: int = 10,
        min_score: float = 0.1,
    ) -> List[SearchResult]:
        """Search semantic memory."""
        return await self.semantic.search(query, limit, min_score)

    async def add_entity(
        self,
        name: str,
        entity_type: EntityType,
        summary: Optional[str] = None,
    ) -> SynapseNode:
        """Add entity to semantic memory."""
        return await self.semantic.add_entity(name, entity_type, summary)

    async def add_fact(
        self,
        source_id: str,
        target_id: str,
        relation_type: RelationType,
    ) -> SynapseEdge:
        """Add fact to semantic memory."""
        return await self.semantic.add_fact(source_id, target_id, relation_type)

    # ==================== Layer 4: Episodic ====================

    def record_episode(
        self,
        content: str,
        summary: Optional[str] = None,
        topics: Optional[List[str]] = None,
        outcome: str = "unknown",
    ) -> SynapseEpisode:
        """Record a new episode."""
        return self.episodic.record_episode(content, summary, topics, outcome)

    def find_episodes_by_topic(
        self,
        topic: str,
        limit: int = 10,
    ) -> List[SynapseEpisode]:
        """Find episodes by topic."""
        return self.episodic.find_episodes(topics=[topic], limit=limit)

    def purge_expired_episodes(self) -> int:
        """Purge expired episodes."""
        return self.episodic.purge_expired()

    # ==================== Layer 5: Working ====================

    def set_working(self, key: str, value: Any) -> None:
        """Set working memory value."""
        self.working.set_context(key, value)

    def get_working(self, key: str, default: Any = None) -> Any:
        """Get working memory value."""
        return self.working.get_context(key, default)

    def clear_working(self) -> int:
        """Clear working memory."""
        return self.working.clear_context()

    # ==================== Cross-Layer Operations ====================

    def detect_layer(self, content: str, context: Optional[Dict[str, Any]] = None) -> MemoryLayer:
        """
        Automatically detect appropriate memory layer for content.

        Uses keyword-based classification for sync compatibility.
        For async LLM-based classification, use detect_layer_async().

        Args:
            content: Content to classify
            context: Additional context for classification

        Returns:
            Detected MemoryLayer
        """
        import asyncio
        try:
            # Try to run async classifier in event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're in an async context, use keyword fallback
                layer, confidence = self._classifier._classify_with_keywords(content)
                logger.debug(f"Detected layer: {layer.value} (confidence: {confidence}) [sync fallback]")
                return layer
            else:
                # We can run async
                layer, confidence = loop.run_until_complete(
                    self._classifier.classify(content, context)
                )
                logger.debug(f"Detected layer: {layer.value} (confidence: {confidence})")
                return layer
        except RuntimeError:
            # No event loop, use keyword fallback
            layer, confidence = self._classifier._classify_with_keywords(content)
            logger.debug(f"Detected layer: {layer.value} (confidence: {confidence}) [no event loop]")
            return layer

    async def detect_layer_async(
        self,
        content: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> MemoryLayer:
        """
        Async version of detect_layer using LLM when available.

        Args:
            content: Content to classify
            context: Additional context for classification

        Returns:
            Detected MemoryLayer
        """
        layer, confidence = await self._classifier.classify(content, context)
        logger.debug(f"Detected layer: {layer.value} (confidence: {confidence}) [async]")
        return layer

    async def search_all(
        self,
        query: str,
        layers: Optional[List[MemoryLayer]] = None,
        limit_per_layer: int = 5,
        user_id: Optional[str] = None,
    ) -> Dict[MemoryLayer, List[Any]]:
        """
        Search across multiple layers.

        Args:
            query: Search query
            layers: Layers to search (default: all)
            limit_per_layer: Results per layer
            user_id: User ID for USER_MODEL layer search

        Returns:
            Dict mapping layer to results
        """
        if layers is None:
            layers = [
                MemoryLayer.USER_MODEL,
                MemoryLayer.PROCEDURAL,
                MemoryLayer.SEMANTIC,
                MemoryLayer.EPISODIC,
                MemoryLayer.WORKING,
            ]

        results: Dict[MemoryLayer, List[Any]] = {}

        if MemoryLayer.USER_MODEL in layers:
            results[MemoryLayer.USER_MODEL] = self._search_user_model(query, user_id, limit_per_layer)

        if MemoryLayer.PROCEDURAL in layers:
            results[MemoryLayer.PROCEDURAL] = self.find_procedures(query, limit_per_layer)

        if MemoryLayer.SEMANTIC in layers:
            results[MemoryLayer.SEMANTIC] = await self.search_semantic(query, limit_per_layer)

        if MemoryLayer.EPISODIC in layers:
            episodic_results = self.episodic.find_episodes(
                query=query,
                user_id=user_id,
                limit=limit_per_layer,
            )
            if not episodic_results and query:
                episodic_results = self.episodic.find_episodes(
                    topics=[query],
                    user_id=user_id,
                    limit=limit_per_layer,
                )
            results[MemoryLayer.EPISODIC] = episodic_results

        if MemoryLayer.WORKING in layers:
            results[MemoryLayer.WORKING] = self._search_working_memory(query, limit_per_layer)

        return results

    def _search_user_model(
        self,
        query: str,
        user_id: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Search user model for matching preferences, expertise, or topics.

        Args:
            query: Search query
            user_id: User ID to search (required for user model)
            limit: Maximum results

        Returns:
            List of matching user model attributes
        """
        if not user_id:
            return []

        results = []
        query_lower = query.lower()
        user = self.get_user(user_id)

        # Search in expertise
        for area, level in user.expertise.items():
            if query_lower in area.lower():
                results.append({
                    "type": "expertise",
                    "area": area,
                    "level": level,
                    "relevance": 1.0,
                })

        # Search in common topics
        for topic in user.common_topics:
            if query_lower in topic.lower():
                results.append({
                    "type": "topic",
                    "topic": topic,
                    "relevance": 0.9,
                })

        # Search in notes
        for note in user.notes:
            if query_lower in note.lower():
                results.append({
                    "type": "note",
                    "note": note,
                    "relevance": 0.7,
                })

        return results[:limit]

    def _search_working_memory(
        self,
        query: str,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Search working memory for matching context values.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of matching working memory entries
        """
        results = []
        query_lower = query.lower()

        # Get all context and search through it
        all_context = self.working.get_all_context()

        for key, value in all_context.items():
            # Check if query matches key
            if query_lower in key.lower():
                results.append({
                    "key": key,
                    "value": value,
                    "match_type": "key",
                    "relevance": 1.0,
                })
                continue

            # Check if query matches string value
            if isinstance(value, str) and query_lower in value.lower():
                results.append({
                    "key": key,
                    "value": value,
                    "match_type": "value",
                    "relevance": 0.8,
                })
                continue

            # Check if query matches list items
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, str) and query_lower in item.lower():
                        results.append({
                            "key": key,
                            "value": value,
                            "matched_item": item,
                            "match_type": "list_item",
                            "relevance": 0.7,
                        })
                        break

        return results[:limit]

    def get_memory_stats(self) -> Dict[str, Any]:
        """
        Get statistics for all layers.

        Returns:
            Dict with stats per layer
        """
        return {
            "user_model": {
                "decay_policy": "never",
                "decay_score": 1.0,
            },
            "procedural": {
                "decay_policy": f"slow (λ={DecayConfig.LAMBDA_PROCEDURAL})",
                "half_life_days": DecayConfig.LAMBDA_PROCEDURAL and (0.693 / DecayConfig.LAMBDA_PROCEDURAL) or None,
            },
            "semantic": {
                "decay_policy": f"normal (λ={DecayConfig.LAMBDA_DEFAULT})",
                "half_life_days": 0.693 / DecayConfig.LAMBDA_DEFAULT,
            },
            "episodic": {
                "decay_policy": "TTL-based",
                "base_ttl_days": DecayConfig.TTL_EPISODIC_DAYS,
                "extension_days": DecayConfig.TTL_EXTEND_DAYS,
            },
            "working": {
                "decay_policy": "session-only",
                "persistent": False,
            },
            "episodic_stats": self.episodic.get_episode_stats(),
            "working_stats": self.working.get_context_stats(),
        }

    async def run_maintenance(self) -> Dict[str, int]:
        """
        Run maintenance tasks on all layers.

        - Refresh decay scores
        - Purge expired episodes
        - Clean up forgotten items

        Returns:
            Dict with counts of items affected
        """
        results = {}

        # Layer 2: Refresh procedural decay scores
        results["procedural_refreshed"] = self.procedural.refresh_decay_scores()

        # Layer 4: Purge expired episodes
        results["episodic_purged"] = self.episodic.purge_expired()

        # Layer 5: Working memory is auto-cleared on session end
        results["working_cleared"] = 0

        return results

    def create_context_for_prompt(self, user_id: str) -> str:
        """
        Create context string for LLM prompt.

        Combines relevant information from all layers.

        Args:
            user_id: User identifier

        Returns:
            Context string for prompt injection
        """
        user = self.get_user(user_id)
        working = self.working.get_all_context()

        parts = []

        # User preferences
        parts.append(f"User language: {user.language}")
        parts.append(f"Response style: {user.response_style}")

        if user.expertise:
            parts.append(f"User expertise: {user.expertise}")

        if user.common_topics:
            parts.append(f"Common topics: {', '.join(user.common_topics[:5])}")

        # Working memory
        if working:
            parts.append(f"Current context: {working}")

        return "\n".join(parts)


# User-isolated contexts
_contexts: Dict[str, UserContext] = {}
_default_context: Optional[UserContext] = None

# Feature flag for user isolation
_USER_ISOLATION_ENABLED = os.getenv("SYNAPSE_USE_USER_ISOLATION", "false").lower() == "true"


def get_layer_manager(user_id: str = "default", llm_client: Optional[object] = None) -> LayerManager:
    """
    Get LayerManager for specific user.

    When SYNAPSE_USE_USER_ISOLATION=true, each user gets isolated storage.
    When false, all users share the default manager (backward compatible).

    Args:
        user_id: User identifier (default: "default")
        llm_client: LLM client for classification

    Returns:
        LayerManager instance for the user
    """
    global _default_context

    if not _USER_ISOLATION_ENABLED:
        # Legacy mode: single global manager
        global _manager
        if _manager is None:
            _manager = LayerManager(llm_client=llm_client)
        return _manager

    # User isolation mode
    if user_id == "default" and _default_context is not None:
        return LayerManager(user_context=_default_context, llm_client=llm_client)

    if user_id not in _contexts:
        _contexts[user_id] = UserContext.create(user_id)
        if user_id == "default":
            _default_context = _contexts[user_id]

    return LayerManager(user_context=_contexts[user_id], llm_client=llm_client)


def clear_user_context(user_id: str) -> bool:
    """
    Clear context for a user (for testing/cleanup).

    Args:
        user_id: User identifier

    Returns:
        True if context was cleared, False if not found
    """
    global _default_context

    if user_id in _contexts:
        del _contexts[user_id]
        if user_id == "default":
            _default_context = None
        return True
    return False


# Legacy singleton instance (for backward compatibility)
_manager: Optional[LayerManager] = None
