"""
Layer Manager - Unified Memory API

Manages all five memory layers with:
- Automatic layer detection
- Cross-layer search
- Decay maintenance
- Memory consolidation
"""

from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum

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


class LayerManager:
    """
    Unified manager for all five memory layers.

    Provides a single API for memory operations across all layers.
    """

    def __init__(
        self,
        user_model_manager: Optional[UserModelManager] = None,
        procedural_manager: Optional[ProceduralManager] = None,
        semantic_manager: Optional[SemanticManager] = None,
        episodic_manager: Optional[EpisodicManager] = None,
        working_manager: Optional[WorkingManager] = None,
    ):
        """
        Initialize Layer Manager.

        Args:
            user_model_manager: Layer 1 manager
            procedural_manager: Layer 2 manager
            semantic_manager: Layer 3 manager
            episodic_manager: Layer 4 manager
            working_manager: Layer 5 manager
        """
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

        Args:
            content: Content to classify
            context: Additional context for classification

        Returns:
            Detected MemoryLayer
        """
        content_lower = content.lower()

        # Layer 1: User Model keywords
        user_keywords = ["ฉันชอบ", "ผู้ใช้ชอบ", "my preference", "i prefer", "ฉันเป็นผู้เชี่ยวชาญ"]
        if any(kw in content_lower for kw in user_keywords):
            return MemoryLayer.USER_MODEL

        # Layer 2: Procedural keywords
        proc_keywords = ["วิธี", "ขั้นตอน", "how to", "steps", "procedure", "ทำอย่างไร"]
        if any(kw in content_lower for kw in proc_keywords):
            return MemoryLayer.PROCEDURAL

        # Layer 4: Episodic keywords
        epi_keywords = ["เมื่อวาน", "วันนี้", "yesterday", "today", "เกิดขึ้น", "happened", "บทสนทนา"]
        if any(kw in content_lower for kw in epi_keywords):
            return MemoryLayer.EPISODIC

        # Layer 5: Working (temporary) keywords
        work_keywords = ["ชั่วคราว", "ตอนนี้", "temp", "now", "current", "session"]
        if context and context.get("temporary"):
            return MemoryLayer.WORKING

        # Default: Semantic
        return MemoryLayer.SEMANTIC

    async def search_all(
        self,
        query: str,
        layers: Optional[List[MemoryLayer]] = None,
        limit_per_layer: int = 5,
    ) -> Dict[MemoryLayer, List[Any]]:
        """
        Search across multiple layers.

        Args:
            query: Search query
            layers: Layers to search (default: all)
            limit_per_layer: Results per layer

        Returns:
            Dict mapping layer to results
        """
        if layers is None:
            layers = [
                MemoryLayer.PROCEDURAL,
                MemoryLayer.SEMANTIC,
                MemoryLayer.EPISODIC,
            ]

        results: Dict[MemoryLayer, List[Any]] = {}

        if MemoryLayer.PROCEDURAL in layers:
            results[MemoryLayer.PROCEDURAL] = self.find_procedures(query, limit_per_layer)

        if MemoryLayer.SEMANTIC in layers:
            results[MemoryLayer.SEMANTIC] = await self.search_semantic(query, limit_per_layer)

        if MemoryLayer.EPISODIC in layers:
            results[MemoryLayer.EPISODIC] = self.find_episodes_by_topic(query, limit_per_layer)

        return results

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


# Singleton instance
_manager: Optional[LayerManager] = None


def get_layer_manager() -> LayerManager:
    """Get singleton LayerManager instance."""
    global _manager
    if _manager is None:
        _manager = LayerManager()
    return _manager
