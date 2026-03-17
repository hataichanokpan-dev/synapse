"""
SynapseService - Bridge between MCP Server and Layer System

This class provides a unified API for MCP tools to interact with
the 5-layer memory system while maintaining Graphiti compatibility.
"""

import logging
from typing import Any, Dict, List, Optional

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
        agent_id: Optional[str] = None,
        chat_id: Optional[str] = None,
    ):
        """
        Initialize SynapseService.

        Args:
            graphiti_client: Graphiti client for knowledge graph operations
            layer_manager: Optional LayerManager instance (created if not provided)
            user_id: User identifier for isolation
            agent_id: Optional agent identifier for multi-agent support
            chat_id: Optional chat/conversation identifier
        """
        self.graphiti = graphiti_client
        self.layers = layer_manager or LayerManager()
        self.user_id = user_id
        self.agent_id = agent_id
        self.chat_id = chat_id

    # ============================================
    # IDENTITY MANAGEMENT
    # ============================================

    def set_identity(
        self,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        chat_id: Optional[str] = None,
    ) -> Dict[str, Optional[str]]:
        """
        Set identity context for memory operations.

        The identity hierarchy determines memory isolation:
        - user_id: User-level preferences (persists across agents/chats)
        - agent_id: Agent-specific context (shared across chats)
        - chat_id: Chat-specific context (isolated per conversation)

        Args:
            user_id: User identifier (required for first call)
            agent_id: Agent identifier (optional, for multi-agent)
            chat_id: Chat/conversation identifier (optional)

        Returns:
            Current identity context
        """
        if user_id is not None:
            self.user_id = user_id
        if agent_id is not None:
            self.agent_id = agent_id
        if chat_id is not None:
            self.chat_id = chat_id

        return self.get_identity()

    def get_identity(self) -> Dict[str, Optional[str]]:
        """
        Get current identity context.

        Returns:
            Dict with user_id, agent_id, chat_id
        """
        return {
            "user_id": self.user_id,
            "agent_id": self.agent_id,
            "chat_id": self.chat_id,
        }

    def get_full_user_key(self) -> str:
        """
        Get composite key for user model lookup.

        Format: user_id[:agent_id[:chat_id]]

        Returns:
            Composite key string
        """
        parts = [self.user_id]
        if self.agent_id:
            parts.append(self.agent_id)
            if self.chat_id:
                parts.append(self.chat_id)
        return ":".join(parts)

    def clear_identity(self) -> Dict[str, Optional[str]]:
        """
        Clear identity context (reset to defaults).

        Returns:
            Previous identity context
        """
        previous = self.get_identity()
        self.agent_id = None
        self.chat_id = None
        return previous

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
        """Get current user context with identity hierarchy."""
        # Try to get specific user model (with agent/chat context)
        user = self.layers.get_user(self.get_full_user_key())

        # If not found and we have agent/chat context, fallback to base user
        if user is None and (self.agent_id or self.chat_id):
            user = self.layers.get_user(self.user_id)

        # If still not found, create default
        if user is None:
            user = self.layers.get_user(self.user_id)

        return {
            "user_id": user.user_id,
            "agent_id": getattr(user, 'agent_id', self.agent_id),
            "chat_id": getattr(user, 'chat_id', self.chat_id),
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

    # ============================================
    # ORACLE TOOLS (Gap 3)
    # ============================================

    async def consult(
        self,
        query: str,
        layers: Optional[List[str]] = None,
        limit: int = 5,
    ) -> Dict[str, Any]:
        """
        Consult memory layers for guidance on a query.

        Searches across specified layers to find relevant guidance,
        combining results with relevance ranking.

        Args:
            query: Question or topic to consult about
            layers: Optional list of layers to search ('user_model', 'procedural',
                   'semantic', 'episodic', 'working'). Default: all layers
            limit: Maximum results per layer

        Returns:
            Dict with guidance from each layer, ranked by relevance
        """
        from synapse.layers import MemoryLayer

        # Convert string layer names to MemoryLayer enums
        target_layers = None
        if layers:
            target_layers = []
            layer_map = {
                'user_model': MemoryLayer.USER_MODEL,
                'procedural': MemoryLayer.PROCEDURAL,
                'semantic': MemoryLayer.SEMANTIC,
                'episodic': MemoryLayer.EPISODIC,
                'working': MemoryLayer.WORKING,
            }
            for layer_name in layers:
                if layer_name.lower() in layer_map:
                    target_layers.append(layer_map[layer_name.lower()])

        # Search all specified layers
        results = await self.layers.search_all(
            query=query,
            layers=target_layers,
            limit_per_layer=limit,
            user_id=self.user_id,
        )

        # Format results for each layer
        guidance = {
            "query": query,
            "identity": self.get_identity(),
            "layers": {},
            "summary": [],
        }

        for layer, items in results.items():
            layer_name = layer.value if hasattr(layer, 'value') else str(layer)
            guidance["layers"][layer_name] = items

            # Add to summary if results found
            if items:
                guidance["summary"].append({
                    "layer": layer_name,
                    "count": len(items),
                    "top_result": self._extract_top_result(items),
                })

        return guidance

    def _extract_top_result(self, items: List[Any]) -> Optional[Dict[str, Any]]:
        """Extract the most relevant result from a list of items."""
        if not items:
            return None

        top = items[0]

        # Handle different item types
        if isinstance(top, dict):
            return {"type": "dict", "preview": str(top)[:200]}
        elif hasattr(top, 'to_dict'):
            return {"type": "model", "preview": str(top.to_dict())[:200]}
        else:
            return {"type": "unknown", "preview": str(top)[:200]}

    async def reflect(
        self,
        layer: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get a random insight from memory layers.

        Retrieves a random piece of knowledge from specified layer
        (or all layers if not specified) for reflection.

        Args:
            layer: Optional specific layer to reflect from
                  ('procedural', 'episodic', 'working')

        Returns:
            Random insight from memory
        """
        import random

        insights = []
        source_layer = None

        if layer and layer.lower() == 'procedural':
            # Get random procedure
            procedures = self.layers.procedural.get_all_procedures()
            if procedures:
                proc = random.choice(procedures)
                insights.append({
                    "type": "procedure",
                    "trigger": proc.trigger,
                    "steps": proc.procedure,
                    "success_count": proc.success_count,
                })
                source_layer = "procedural"

        elif layer and layer.lower() == 'episodic':
            # Get random episode
            episodes = self.layers.episodic.get_all_episodes()
            if episodes:
                ep = random.choice(episodes)
                insights.append({
                    "type": "episode",
                    "content": ep.content,
                    "summary": ep.summary,
                    "topics": ep.topics,
                })
                source_layer = "episodic"

        elif layer and layer.lower() == 'working':
            # Get random working memory item
            all_context = self.layers.working.get_all_context()
            if all_context:
                key, value = random.choice(list(all_context.items()))
                insights.append({
                    "type": "working_context",
                    "key": key,
                    "value": value,
                })
                source_layer = "working"

        else:
            # Get from all layers
            # Procedural
            procedures = self.layers.procedural.get_all_procedures()
            if procedures:
                proc = random.choice(procedures)
                insights.append({
                    "type": "procedure",
                    "trigger": proc.trigger,
                    "steps": proc.procedure,
                    "success_count": proc.success_count,
                })

            # Episodic
            episodes = self.layers.episodic.get_all_episodes()
            if episodes:
                ep = random.choice(episodes)
                insights.append({
                    "type": "episode",
                    "content": ep.content,
                    "summary": ep.summary,
                    "topics": ep.topics,
                })

            # Working
            all_context = self.layers.working.get_all_context()
            if all_context:
                key, value = random.choice(list(all_context.items()))
                insights.append({
                    "type": "working_context",
                    "key": key,
                    "value": value,
                })

            source_layer = "all"

        return {
            "insights": insights,
            "source_layer": source_layer or layer,
            "identity": self.get_identity(),
            "timestamp": self._get_timestamp(),
        }

    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()

    async def analyze_patterns(
        self,
        analysis_type: Optional[str] = None,
        time_range_days: int = 30,
    ) -> Dict[str, Any]:
        """
        Analyze patterns in memory across layers.

        Examines user behavior, common topics, procedure usage,
        and memory distribution.

        Args:
            analysis_type: Optional specific analysis type
                          ('topics', 'procedures', 'activity', 'all')
            time_range_days: Days to include in analysis (default: 30)

        Returns:
            Pattern analysis results
        """
        from collections import Counter
        from datetime import datetime, timezone, timedelta

        results = {
            "analysis_type": analysis_type or "all",
            "time_range_days": time_range_days,
            "identity": self.get_identity(),
            "patterns": {},
        }

        cutoff_date = datetime.now(timezone.utc) - timedelta(days=time_range_days)

        # Analyze topics
        if analysis_type in (None, "all", "topics"):
            user = self.layers.get_user(self.user_id)
            topic_counts = Counter(user.common_topics)
            results["patterns"]["topics"] = {
                "common_topics": dict(topic_counts.most_common(10)),
                "total_unique": len(topic_counts),
            }

        # Analyze procedures
        if analysis_type in (None, "all", "procedures"):
            procedures = self.layers.procedural.get_all_procedures()
            trigger_patterns = Counter(p.trigger for p in procedures)
            success_rates = []
            for p in procedures:
                if p.success_count > 0:
                    success_rates.append({
                        "trigger": p.trigger,
                        "success_count": p.success_count,
                    })

            results["patterns"]["procedures"] = {
                "total_procedures": len(procedures),
                "trigger_patterns": dict(trigger_patterns.most_common(10)),
                "top_successful": sorted(
                    success_rates,
                    key=lambda x: x["success_count"],
                    reverse=True
                )[:5],
            }

        # Analyze activity
        if analysis_type in (None, "all", "activity"):
            episodes = self.layers.episodic.get_all_episodes()
            recent_episodes = [
                ep for ep in episodes
                if ep.recorded_at and ep.recorded_at > cutoff_date
            ]

            results["patterns"]["activity"] = {
                "total_episodes": len(episodes),
                "recent_episodes": len(recent_episodes),
                "topics_covered": list(set(
                    topic for ep in recent_episodes
                    for topic in (ep.topics or [])
                ))[:20],
            }

        # Memory distribution
        if analysis_type in (None, "all"):
            working_context = self.layers.working.get_all_context()
            results["patterns"]["memory_distribution"] = {
                "user_model": 1,
                "procedures": len(procedures) if 'procedures' in dir() else 0,
                "episodes": len(episodes) if 'episodes' in dir() else 0,
                "working_contexts": len(working_context),
            }

        return results

    async def consolidate(
        self,
        source: str = "episodic",
        criteria: Optional[Dict[str, Any]] = None,
        min_access_count: int = 2,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Consolidate memory by promoting frequently accessed items.

        Converts episodic memories that are frequently referenced
        into semantic knowledge for long-term retention.

        Args:
            source: Source layer to consolidate from ('episodic')
            criteria: Optional criteria for consolidation
                     {'min_access': N, 'topics': [...], 'min_age_days': N}
            min_access_count: Minimum access count for consolidation
            dry_run: If True, only preview what would be consolidated

        Returns:
            Consolidation results with items promoted
        """
        from datetime import datetime, timezone, timedelta

        criteria = criteria or {}
        results = {
            "source": source,
            "criteria": criteria,
            "dry_run": dry_run,
            "promoted": [],
            "skipped": [],
            "errors": [],
        }

        if source != "episodic":
            results["errors"].append(f"Consolidation from '{source}' not supported")
            return results

        # Get episodes for potential consolidation
        episodes = self.layers.episodic.get_all_episodes()

        # Filter by criteria
        candidates = []
        for ep in episodes:
            # Check access count (simulated - using topic count as proxy)
            access_count = len(ep.topics or [])
            if access_count < min_access_count:
                results["skipped"].append({
                    "id": ep.id,
                    "reason": f"access_count ({access_count}) < {min_access_count}",
                })
                continue

            # Check topic criteria
            if "topics" in criteria:
                if not any(t in (ep.topics or []) for t in criteria["topics"]):
                    results["skipped"].append({
                        "id": ep.id,
                        "reason": "topic_criteria_not_met",
                    })
                    continue

            # Check age criteria
            if "min_age_days" in criteria and ep.recorded_at:
                age_days = (datetime.now(timezone.utc) - ep.recorded_at).days
                if age_days < criteria["min_age_days"]:
                    results["skipped"].append({
                        "id": ep.id,
                        "reason": f"age ({age_days} days) < {criteria['min_age_days']} days",
                    })
                    continue

            candidates.append(ep)

        # Promote candidates to semantic memory
        for ep in candidates:
            if dry_run:
                results["promoted"].append({
                    "id": ep.id,
                    "preview": {
                        "name": f"Consolidated: {ep.summary or ep.content[:50]}",
                        "summary": ep.summary or ep.content[:200],
                        "topics": ep.topics,
                    },
                    "status": "would_promote",
                })
            else:
                try:
                    # Create semantic entity from episode
                    entity = await self.layers.add_entity(
                        name=f"Consolidated: {ep.summary or ep.content[:50]}",
                        entity_type=EntityType.CONCEPT,
                        summary=ep.summary or ep.content[:200],
                    )

                    results["promoted"].append({
                        "id": ep.id,
                        "new_entity_id": entity.id,
                        "status": "promoted",
                    })
                except Exception as e:
                    results["errors"].append({
                        "id": ep.id,
                        "error": str(e),
                    })

        return results
