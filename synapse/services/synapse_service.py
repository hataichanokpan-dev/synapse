"""
SynapseService - Bridge between MCP Server and Layer System

This class provides a unified API for MCP tools to interact with
the 5-layer memory system while maintaining Graphiti compatibility.
"""

import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from synapse.layers import (
    LayerManager,
    MemoryLayer,
    EntityType,
    SynapseNode,
    SynapseEdge,
    SearchResult,
)

logger = logging.getLogger(__name__)


class SynapseService:
    """
    Unified service for Synapse memory operations.

    This class:
    1. Wraps LayerManager for layer-specific operations
    2. Provides Graphiti client for knowledge graph operations
    3. Handles content classification and routing
    4. Manages user isolation
    """

    def __init__(
        self,
        graphiti_client: Any,
        layer_manager: Optional[LayerManager] = None,
        user_id: str = "default",
    ):
        """
        Initialize SynapseService.

        Args:
            graphiti_client: Graphiti client for knowledge graph operations
            layer_manager: Optional LayerManager instance (created if not provided)
            user_id: User identifier for isolation
        """
        self.graphiti = graphiti_client
        self.layers = layer_manager or LayerManager()
        self.user_id = user_id

    # ============================================
    # MEMORY OPERATIONS (High-level API)
    # ============================================

    async def add_memory(
        self,
        name: str,
        episode_body: str,
        source_description: str = "",
        source_url: Optional[str] = None,
        reference_time: Optional[str] = None,
        group_id: Optional[str] = None,
        source: str = "text",
        uuid: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Add memory with automatic layer classification.

        This method:
        1. Classifies content to determine appropriate layer
        2. Routes to layer-specific handler
        3. Also stores in Graphiti for knowledge graph

        Args:
            name: Episode name
            episode_body: Content to store
            source_description: Description of source
            source_url: Optional source URL
            reference_time: Optional timestamp
            group_id: Optional group ID for isolation
            source: Source type (text, json, message)
            uuid: Optional UUID for the episode

        Returns:
            Dict with layer info and Graphiti result
        """
        # Step 1: Classify content
        detected_layer = self.layers.detect_layer(episode_body)
        logger.info(f"Content classified as: {detected_layer.value}")

        # Step 2: Route to appropriate layer
        layer_result = await self._route_to_layer(
            layer=detected_layer,
            content=episode_body,
            name=name,
        )

        # Step 3: Store in Graphiti for knowledge graph
        graphiti_result = None
        try:
            # Import EpisodeType for source conversion
            from graphiti_core.nodes import EpisodeType

            episode_type = EpisodeType.text  # Default
            if source:
                try:
                    episode_type = EpisodeType[source.lower()]
                except (KeyError, AttributeError):
                    logger.warning(f"Unknown source type '{source}', using 'text' as default")
                    episode_type = EpisodeType.text

            graphiti_result = await self.graphiti.add_episode(
                name=name,
                episode_body=episode_body,
                source_description=source_description,
                reference_time=reference_time,
                group_id=group_id,
                source=episode_type,
                uuid=uuid,
                **kwargs,
            )
        except Exception as e:
            logger.error(f"Failed to store in Graphiti: {e}")

        return {
            "layer": detected_layer.value,
            "layer_result": layer_result,
            "graphiti_result": graphiti_result,
        }

    async def _route_to_layer(
        self,
        layer: MemoryLayer,
        content: str,
        name: str,
    ) -> Any:
        """Route content to appropriate layer handler."""

        if layer == MemoryLayer.USER_MODEL:
            # Extract user preference from content
            return self.layers.update_user(
                user_id=self.user_id,
                add_note=content,
            )

        elif layer == MemoryLayer.PROCEDURAL:
            # Extract trigger and steps (simplified for now)
            # TODO: Use LLM to extract structured procedure
            trigger = name
            steps = [content]
            return self.layers.learn_procedure(trigger, steps)

        elif layer == MemoryLayer.SEMANTIC:
            # Store as entity
            return await self.layers.add_entity(
                name=name,
                entity_type=EntityType.CONCEPT,
                summary=content,
            )

        elif layer == MemoryLayer.EPISODIC:
            # Store as episode
            return self.layers.record_episode(
                content=content,
                source="user_input",
                metadata={"name": name},
            )

        elif layer == MemoryLayer.WORKING:
            # Store in working memory
            return self.layers.set_working(name, content)

        else:
            logger.warning(f"Unknown layer: {layer}, defaulting to semantic")
            return await self.layers.add_entity(
                name=name,
                entity_type=EntityType.CONCEPT,
                summary=content,
            )

    # ============================================
    # SEARCH OPERATIONS
    # ============================================

    async def search_memory(
        self,
        query: str,
        layers: Optional[List[MemoryLayer]] = None,
        limit: int = 10,
    ) -> Dict[str, Any]:
        """
        Search across memory layers.

        Args:
            query: Search query
            layers: Optional list of layers to search (default: all)
            limit: Max results per layer

        Returns:
            Dict with results per layer and Graphiti results
        """
        # Search layers
        layer_results = await self.layers.search_all(
            query=query,
            layers=layers,
            limit_per_layer=limit,
            user_id=self.user_id,
        )

        # Search Graphiti
        graphiti_results = []
        try:
            graphiti_results = await self.graphiti.search(
                query=query,
                num_results=limit,
            )
        except Exception as e:
            logger.error(f"Graphiti search failed: {e}")

        return {
            "layers": {k.value if hasattr(k, 'value') else str(k): v for k, v in layer_results.items()},
            "graphiti": graphiti_results,
        }

    # ============================================
    # ENTITY OPERATIONS (Delegated to Semantic Layer)
    # ============================================

    async def add_entity(
        self,
        name: str,
        entity_type: str,
        summary: Optional[str] = None,
        **kwargs,
    ) -> SynapseNode:
        """Add entity to semantic layer and Graphiti."""
        # Convert string to EntityType enum
        try:
            et = EntityType(entity_type.lower())
        except ValueError:
            et = EntityType.CONCEPT

        return await self.layers.add_entity(
            name=name,
            entity_type=et,
            summary=summary,
            **kwargs,
        )

    async def get_entity(self, entity_id: str) -> Optional[SynapseNode]:
        """Get entity from semantic layer."""
        return await self.layers.semantic.get_entity(entity_id)

    async def search_entities(
        self,
        query: str,
        entity_types: Optional[List[str]] = None,
        limit: int = 10,
    ) -> List[SearchResult]:
        """Search entities in semantic layer."""
        # Convert string entity types to EntityType enums
        et_list = None
        if entity_types:
            et_list = []
            for et in entity_types:
                try:
                    et_list.append(EntityType(et.lower()))
                except ValueError:
                    pass

        return await self.layers.search_semantic(
            query=query,
            limit=limit,
        )

    # ============================================
    # EPISODE OPERATIONS
    # ============================================

    async def get_episodes(
        self,
        reference: Optional[str] = None,
        last_n: int = 10,
        group_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get recent episodes."""
        episodes = self.layers.find_episodes_by_topic(
            topic=reference or "",
            limit=last_n,
        )

        # Convert to dict format
        result = []
        for ep in episodes:
            result.append({
                "id": ep.id,
                "content": ep.content,
                "summary": ep.summary,
                "topics": ep.topics,
                "recorded_at": ep.recorded_at.isoformat() if ep.recorded_at else None,
                "expires_at": ep.expires_at.isoformat() if ep.expires_at else None,
            })

        return result

    # ============================================
    # PROCEDURE OPERATIONS
    # ============================================

    def find_procedure(self, trigger: str, limit: int = 5) -> List[Dict]:
        """Find procedures matching trigger."""
        procedures = self.layers.find_procedures(trigger, limit)

        # Convert to dict format
        result = []
        for proc in procedures:
            result.append({
                "id": proc.id,
                "trigger": proc.trigger,
                "steps": proc.procedure,
                "source": proc.source,
                "success_count": proc.success_count,
                "last_used": proc.last_used.isoformat() if proc.last_used else None,
            })

        return result

    # ============================================
    # USER MODEL OPERATIONS
    # ============================================

    def get_user_context(self) -> Dict[str, Any]:
        """Get current user context."""
        user = self.layers.get_user(self.user_id)
        return {
            "user_id": user.user_id,
            "language": user.language,
            "response_style": user.response_style,
            "response_length": user.response_length,
            "timezone": user.timezone,
            "expertise": user.expertise,
            "common_topics": user.common_topics,
            "notes": user.notes,
            "updated_at": user.updated_at.isoformat() if user.updated_at else None,
        }

    def update_user_preferences(
        self,
        language: Optional[str] = None,
        response_style: Optional[str] = None,
        response_length: Optional[str] = None,
        timezone: Optional[str] = None,
        add_expertise: Optional[Dict[str, str]] = None,
        add_topic: Optional[str] = None,
        add_note: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Update user preferences in user model layer.

        Args:
            language: Preferred language ('th', 'en', etc.)
            response_style: 'formal' | 'casual' | 'auto'
            response_length: 'concise' | 'detailed' | 'auto'
            timezone: User timezone (e.g., 'Asia/Bangkok')
            add_expertise: Dict of {topic: level} to add
            add_topic: Common topic to add
            add_note: Free-form note to add
            user_id: User identifier (uses default if not provided)

        Returns:
            Updated user context
        """
        uid = user_id or self.user_id

        # Build kwargs for update
        kwargs: Dict[str, Any] = {}
        if language:
            kwargs['language'] = language
        if response_style:
            kwargs['response_style'] = response_style
        if response_length:
            kwargs['response_length'] = response_length
        if timezone:
            kwargs['timezone'] = timezone
        if add_topic:
            kwargs['add_topic'] = add_topic
        if add_note:
            kwargs['add_note'] = add_note

        # Handle expertise separately (need to merge with existing)
        if add_expertise:
            user = self.layers.get_user(uid)
            merged_expertise = {**user.expertise, **add_expertise}
            kwargs['expertise'] = merged_expertise

        # Perform update
        self.layers.update_user(uid, **kwargs)

        # Return updated context
        return self.get_user_context()

    def add_procedure(
        self,
        trigger: str,
        steps: List[str],
        topics: Optional[List[str]] = None,
        source: str = "explicit",
    ) -> Dict[str, Any]:
        """
        Add a new procedure to procedural memory.

        Args:
            trigger: When to activate this procedure
            steps: List of steps to execute
            topics: Related topics for categorization
            source: 'explicit' | 'correction' | 'repeated_pattern'

        Returns:
            Created procedure info
        """
        procedure = self.layers.learn_procedure(
            trigger=trigger,
            steps=steps,
            source=source,
            topics=topics or [],
        )

        return {
            "id": procedure.id,
            "trigger": procedure.trigger,
            "steps": procedure.procedure,
            "topics": procedure.topics,
            "source": procedure.source,
            "success_count": procedure.success_count,
        }

    def record_procedure_success(self, procedure_id: str) -> Optional[Dict[str, Any]]:
        """
        Record successful use of a procedure.

        Args:
            procedure_id: ID of the procedure that succeeded

        Returns:
            Updated procedure info or None if not found
        """
        procedure = self.layers.record_procedure_success(procedure_id)

        if procedure is None:
            return None

        return {
            "id": procedure.id,
            "trigger": procedure.trigger,
            "success_count": procedure.success_count,
            "last_used": procedure.last_used.isoformat() if procedure.last_used else None,
        }

    def get_all_working_context(self) -> Dict[str, Any]:
        """Get all working memory context."""
        return self.layers.working.get_all_context()

    # ============================================
    # HEALTH CHECK
    # ============================================

    async def health_check(self) -> Dict[str, Any]:
        """Check health of all components."""
        results = {
            "status": "healthy",
            "components": {},
        }

        # Check Graphiti
        try:
            # Simple check - can we access Graphiti?
            if self.graphiti is not None:
                results["components"]["graphiti"] = "ok"
            else:
                results["components"]["graphiti"] = "not initialized"
                results["status"] = "degraded"
        except Exception as e:
            results["components"]["graphiti"] = f"error: {e}"
            results["status"] = "degraded"

        # Check LayerManager
        try:
            self.layers.get_user(self.user_id)
            results["components"]["layer_manager"] = "ok"
        except Exception as e:
            results["components"]["layer_manager"] = f"error: {e}"
            results["status"] = "degraded"

        return results

    # ============================================
    # WORKING MEMORY OPERATIONS
    # ============================================

    def set_working_context(self, key: str, value: Any) -> None:
        """Set working memory value."""
        self.layers.set_working(key, value)

    def get_working_context(self, key: str, default: Any = None) -> Any:
        """Get working memory value."""
        return self.layers.get_working(key, default)

    def clear_working_context(self) -> int:
        """Clear working memory."""
        return self.layers.clear_working()
