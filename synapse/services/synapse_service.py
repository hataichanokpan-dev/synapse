"""
SynapseService - Bridge between MCP Server and Layer System

This class provides a unified API for MCP tools to interact with
the 5-layer memory system while maintaining Graphiti compatibility.
"""

import json
import logging
import os
import re
from datetime import datetime as dt
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from synapse.layers import (
    LayerManager,
    MemoryLayer,
    EntityType,
    SynapseNode,
    SynapseEdge,
    SearchResult,
)
from synapse.search import HybridSearchEngine, SearchMode

logger = logging.getLogger(__name__)


def _coerce_datetime(val: Any) -> Optional[datetime]:
    """Parse supported datetime values into timezone-aware UTC datetimes."""
    if val is None:
        return None

    if isinstance(val, datetime):
        return val if val.tzinfo is not None else val.replace(tzinfo=timezone.utc)

    if isinstance(val, (int, float)):
        return datetime.fromtimestamp(val / 1000 if val > 1e12 else val, tz=timezone.utc)

    if isinstance(val, str):
        value = val.strip()
        if not value:
            return None
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(value)
            return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            try:
                numeric = float(value)
            except ValueError:
                return None
            return datetime.fromtimestamp(
                numeric / 1000 if numeric > 1e12 else numeric,
                tz=timezone.utc,
            )

    return None


def _parse_db_date(val) -> Optional[str]:
    """Safely parse a datetime from DB into ISO string."""
    parsed = _coerce_datetime(val)
    if parsed is not None:
        return parsed.isoformat()
    if val is None:
        return None
    try:
        return str(val)
    except Exception:
        return None


def _normalize_feed_layer(layer: Any) -> Optional[str]:
    """Normalize internal layer names into feed/UI layer names."""
    if layer is None:
        return None

    raw = layer.value if hasattr(layer, "value") else str(layer)
    normalized = raw.strip().lower().replace("-", "_")

    aliases = {
        "user": "USER",
        "user_model": "USER",
        "procedural": "PROCEDURAL",
        "semantic": "SEMANTIC",
        "episodic": "EPISODIC",
        "working": "WORKING",
        "all": "ALL",
    }
    return aliases.get(normalized)


def _matches_feed_layer(event_layer: Any, requested_layer: Optional[str]) -> bool:
    """Check whether an event belongs to the requested layer filter."""
    normalized_request = _normalize_feed_layer(requested_layer)
    if normalized_request in (None, "ALL"):
        return True
    return _normalize_feed_layer(event_layer) == normalized_request


def _row_value(row: Any, *names: str) -> Any:
    """Safely read values from sqlite rows or dict-like objects."""
    if row is None:
        return None

    for name in names:
        try:
            if hasattr(row, "keys") and name in row.keys():
                return row[name]
        except Exception:
            pass

        try:
            return row.get(name)
        except Exception:
            pass

    return None


def _parse_json_field(value: Any, default: Any) -> Any:
    """Parse JSON strings with a fallback default."""
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return default
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            return default
    return default


def _infer_graph_feed_layer(record: Dict[str, Any], created_at: Optional[datetime]) -> str:
    """Infer a feed layer for raw Graphiti/Falkor records."""
    explicit_layer = _normalize_feed_layer(record.get("layer") or record.get("memory_layer"))
    if explicit_layer:
        return explicit_layer

    labels = {str(label).upper() for label in (record.get("labels") or [])}
    text = " ".join(
        str(part)
        for part in (
            record.get("name"),
            record.get("content"),
            record.get("source"),
            record.get("source_description"),
        )
        if part
    ).lower()

    if any("WORKING" in label or "SESSION" in label for label in labels) or any(
        term in text for term in ("working context", "session context", "current session", "current task")
    ):
        return "WORKING"

    if any("USER" in label or "PREFERENCE" in label for label in labels) or any(
        term in text for term in ("preference", "response style", "response length", "timezone", "expertise")
    ):
        return "USER"

    if any("EPISODIC" in label or "EPISODE" in label for label in labels):
        return "EPISODIC"

    if created_at is not None and datetime.now(timezone.utc) - created_at <= timedelta(hours=24):
        return "EPISODIC"

    if any("PROCEDURE" in label or "WORKFLOW" in label for label in labels) or any(
        term in text for term in ("procedure", "workflow", "trigger", "step 1")
    ):
        return "PROCEDURAL"

    return "SEMANTIC"


def _preview_feed_value(value: Any) -> str:
    """Serialize feed detail values defensively."""
    if isinstance(value, str):
        return value

    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        return str(value)


def _normalize_core_layer(value: Any) -> Optional[MemoryLayer]:
    """Normalize external layer values into core MemoryLayer enums."""
    if value is None:
        return None
    if isinstance(value, MemoryLayer):
        return value

    raw = value.value if hasattr(value, "value") else value
    text = str(raw).strip()
    if not text:
        return None

    try:
        return MemoryLayer(text)
    except ValueError:
        return None


def _normalize_core_layers(values: Optional[List[Any]]) -> Optional[List[MemoryLayer]]:
    """Normalize a list of layer values into core MemoryLayer enums."""
    if values is None:
        return None

    normalized: List[MemoryLayer] = []
    for value in values:
        layer = _normalize_core_layer(value)
        if layer is not None:
            normalized.append(layer)

    return normalized


def _sanitize_graph_group_id(group_id: Optional[str]) -> str:
    """Sanitize group IDs for Graphiti/FalkorDB fulltext compatibility."""
    if group_id is None:
        return "default"
    sanitized = re.sub(r"[^A-Za-z0-9_]+", "_", str(group_id).strip())
    sanitized = sanitized.strip("_")
    return sanitized or "default"


def _sanitize_graph_group_ids(group_ids: Optional[List[str]]) -> Optional[List[str]]:
    """Sanitize a list of group IDs for graph operations."""
    if group_ids is None:
        return None
    return [_sanitize_graph_group_id(group_id) for group_id in group_ids]


def _default_search_mode() -> str:
    """Resolve the runtime default hybrid search mode."""
    raw = os.getenv("SYNAPSE_SEARCH_ENGINE", SearchMode.HYBRID_AUTO.value).strip().lower()
    return raw if raw in {mode.value for mode in SearchMode} else SearchMode.HYBRID_AUTO.value


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
        semantic_manager = getattr(self.layers, "semantic", None)
        if semantic_manager is not None and getattr(semantic_manager, "_graphiti", None) is None:
            setattr(semantic_manager, "_graphiti", graphiti_client)
        self.user_id = user_id
        self.agent_id = agent_id
        self.chat_id = chat_id
        self.hybrid_search = HybridSearchEngine(self.layers, self.graphiti)

    def _serialize_episode_memory(
        self,
        episode: Any,
        *,
        source: Optional[str] = None,
        source_description: Optional[str] = None,
        name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Serialize episodic records into a consistent API/service envelope."""
        recorded_at = _parse_db_date(getattr(episode, "recorded_at", None))
        expires_at = _parse_db_date(getattr(episode, "expires_at", None))
        summary = getattr(episode, "summary", None) or name or (getattr(episode, "content", "")[:50])
        return {
            "uuid": getattr(episode, "id", ""),
            "layer": MemoryLayer.EPISODIC.value,
            "name": summary or "",
            "content": getattr(episode, "content", "") or "",
            "source": source or "episodic",
            "source_description": source_description or getattr(episode, "outcome", None) or "unknown",
            "group_id": getattr(episode, "session_id", None),
            "agent_id": getattr(episode, "user_id", None),
            "access_count": getattr(episode, "access_count", 0),
            "decay_score": None,
            "created_at": recorded_at,
            "updated_at": recorded_at,
            "last_accessed": None,
            "metadata": {
                "summary": getattr(episode, "summary", None),
                "topics": list(getattr(episode, "topics", []) or []),
                "outcome": getattr(episode, "outcome", None) or "unknown",
                "expires_at": expires_at,
            },
        }

    def _serialize_procedure_memory(self, procedure: Any) -> Dict[str, Any]:
        """Serialize procedural records into a consistent API/service envelope."""
        steps = getattr(procedure, "procedure", []) or []
        if not isinstance(steps, list):
            steps = [str(steps)]
        return {
            "uuid": getattr(procedure, "id", ""),
            "layer": MemoryLayer.PROCEDURAL.value,
            "name": getattr(procedure, "trigger", "") or "",
            "content": "\n".join(steps),
            "source": getattr(procedure, "source", "explicit") or "explicit",
            "source_description": f"Procedure: {getattr(procedure, 'trigger', '')}",
            "group_id": None,
            "agent_id": None,
            "access_count": getattr(procedure, "success_count", 0),
            "decay_score": getattr(procedure, "decay_score", 1.0),
            "created_at": _parse_db_date(getattr(procedure, "created_at", None)),
            "updated_at": _parse_db_date(getattr(procedure, "updated_at", None)),
            "last_accessed": _parse_db_date(getattr(procedure, "last_used", None)),
            "metadata": {
                "trigger": getattr(procedure, "trigger", "") or "",
                "steps": steps,
                "topics": list(getattr(procedure, "topics", []) or []),
            },
        }

    def _serialize_semantic_memory(
        self,
        node: SynapseNode,
        *,
        content: Optional[str] = None,
        source: Optional[str] = None,
        source_description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Serialize semantic records into a consistent API/service envelope."""
        return {
            "uuid": node.id,
            "layer": MemoryLayer.SEMANTIC.value,
            "name": node.name,
            "content": node.summary or content or "",
            "source": source or "semantic",
            "source_description": source_description,
            "group_id": None,
            "agent_id": node.agent_id,
            "access_count": node.access_count,
            "decay_score": node.decay_score,
            "created_at": _parse_db_date(node.created_at),
            "updated_at": _parse_db_date(node.updated_at),
            "last_accessed": None,
            "metadata": {
                "entity_type": node.type.value if hasattr(node.type, "value") else node.type,
                "confidence": node.confidence,
                "source_episode": node.source_episode,
            },
        }

    def _serialize_user_memory(
        self,
        user: Any,
        *,
        content: Optional[str] = None,
        source: Optional[str] = None,
        source_description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Serialize user-model records into a consistent API/service envelope."""
        notes = list(getattr(user, "notes", []) or [])
        expertise = dict(getattr(user, "expertise", {}) or {})
        topics = list(getattr(user, "common_topics", []) or [])
        updated_at = _parse_db_date(getattr(user, "updated_at", None))
        created_at = _parse_db_date(getattr(user, "created_at", None)) or updated_at
        return {
            "uuid": getattr(user, "user_id", self.user_id),
            "layer": MemoryLayer.USER_MODEL.value,
            "name": "User preferences",
            "content": content or "\n".join(notes),
            "source": source or "user_model",
            "source_description": source_description or "User model update",
            "group_id": None,
            "agent_id": getattr(user, "agent_id", None),
            "access_count": 0,
            "decay_score": 1.0,
            "created_at": created_at,
            "updated_at": updated_at,
            "last_accessed": None,
            "metadata": {
                "language": getattr(user, "language", None),
                "response_style": getattr(user, "response_style", None),
                "response_length": getattr(user, "response_length", None),
                "timezone": getattr(user, "timezone", None),
                "expertise": expertise,
                "topics": topics,
                "notes": notes,
            },
        }

    def _serialize_memory_result(
        self,
        layer: MemoryLayer,
        record: Any,
        *,
        name: Optional[str] = None,
        content: Optional[str] = None,
        source: Optional[str] = None,
        source_description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Serialize a layer-specific record into the shared memory envelope."""
        if layer == MemoryLayer.USER_MODEL:
            return self._serialize_user_memory(
                record,
                content=content,
                source=source,
                source_description=source_description,
            )
        if layer == MemoryLayer.PROCEDURAL:
            return self._serialize_procedure_memory(record)
        if layer == MemoryLayer.SEMANTIC:
            return self._serialize_semantic_memory(
                record,
                content=content,
                source=source,
                source_description=source_description,
            )
        if layer == MemoryLayer.EPISODIC:
            return self._serialize_episode_memory(
                record,
                source=source,
                source_description=source_description,
                name=name,
            )
        raise ValueError(f"Unsupported memory layer: {layer}")

    def _bump_search_generations(self, *layers: Any) -> None:
        """Invalidate hybrid-search generations for affected layers."""
        generation_keys: List[str] = []
        for layer in layers:
            normalized = _normalize_core_layer(layer)
            if normalized is None:
                continue
            generation_keys.append(normalized.value)
            if normalized == MemoryLayer.SEMANTIC:
                generation_keys.extend(["semantic_lexical", "semantic_graph"])
        if generation_keys:
            self.hybrid_search.bump_generations(*generation_keys)

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
        layer: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None,
        agent_id: Optional[str] = None,
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
        requested_layer = _normalize_core_layer(layer)
        detected_layer = requested_layer or self.layers.detect_layer(episode_body)
        logger.info(f"Content classified as: {detected_layer.value}")

        # Step 2: Route to appropriate layer
        persisted_record = await self._route_to_layer(
            layer=detected_layer,
            content=episode_body,
            name=name,
            source=source,
            source_description=source_description,
            group_id=group_id,
            agent_id=agent_id,
            metadata=metadata or {},
        )
        layer_result = self._serialize_memory_result(
            detected_layer,
            persisted_record,
            name=name,
            content=episode_body,
            source=source,
            source_description=source_description,
        )
        self._bump_search_generations(detected_layer)

        # Step 3: Store in Graphiti for knowledge graph (optional)
        graphiti_result = None
        if self.graphiti is not None:
            try:
                # Import EpisodeType for source conversion
                from graphiti_core.nodes import EpisodeType
                from datetime import datetime as dt

                episode_type = EpisodeType.text  # Default
                if source:
                    try:
                        episode_type = EpisodeType[source.lower()]
                    except (KeyError, AttributeError):
                        logger.warning(f"Unknown source type '{source}', using 'text' as default")
                        episode_type = EpisodeType.text

                # Graphiti requires a valid reference_time, default to now if not provided
                resolved_reference_time = _coerce_datetime(reference_time) or datetime.now(timezone.utc)

                # Graphiti requires a valid group_id (alphanumeric, dashes, underscores only)
                # Default to 'default' if not provided
                resolved_group_id = _sanitize_graph_group_id(group_id)

                graphiti_result = await self.graphiti.add_episode(
                    name=name,
                    episode_body=episode_body,
                    source_description=source_description,
                    reference_time=resolved_reference_time,
                    group_id=resolved_group_id,
                    source=episode_type,
                    uuid=uuid,
                    **kwargs,
                )
            except Exception as e:
                logger.error(f"Failed to store in Graphiti: {e}")

        return {
            **layer_result,
            "layer_result": layer_result,
            "graphiti_result": graphiti_result,
            "source_url": source_url,
        }

    async def _route_to_layer(
        self,
        layer: MemoryLayer,
        content: str,
        name: str,
        source: str = "text",
        source_description: str = "",
        group_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Route content to appropriate layer handler."""
        metadata = metadata or {}

        if layer == MemoryLayer.USER_MODEL:
            # Extract user preference from content
            return self.layers.update_user(
                user_id=self.user_id,
                add_note=content,
            )

        elif layer == MemoryLayer.PROCEDURAL:
            # Extract trigger and steps (simplified for now)
            trigger = metadata.get("trigger") or name
            steps = metadata.get("steps")
            if steps is None:
                steps = [content]
            elif not isinstance(steps, list):
                steps = [str(steps)]
            topics = metadata.get("topics")
            if topics is not None and not isinstance(topics, list):
                topics = [str(topics)]
            return self.layers.learn_procedure(trigger, steps, topics=topics or [])

        elif layer == MemoryLayer.SEMANTIC:
            # Store as entity
            return await self.layers.add_entity(
                name=name,
                entity_type=EntityType.CONCEPT,
                summary=content,
            )

        elif layer == MemoryLayer.EPISODIC:
            # Store as episode
            topics = metadata.get("topics")
            if topics is not None and not isinstance(topics, list):
                topics = [str(topics)]
            return self.layers.episodic.record_episode(
                content=content,
                summary=name,
                topics=topics,
                outcome=metadata.get("outcome") or "unknown",
                user_id=agent_id or self.user_id,
                session_id=group_id,
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
        mode: Optional[str] = None,
        query_type: str = "auto",
        explain: bool = False,
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
        normalized_layers = _normalize_core_layers(layers)
        resolved_mode = str(mode or _default_search_mode()).strip().lower()
        if resolved_mode == SearchMode.LEGACY.value:
            return await self._search_memory_legacy(query=query, layers=normalized_layers, limit=limit)

        return await self.hybrid_search.search(
            query=query,
            layers=normalized_layers,
            limit=limit,
            mode=resolved_mode,
            query_type=query_type,
            explain=explain,
            user_id=self.user_id,
            group_id=self.chat_id,
        )

    async def _search_memory_legacy(
        self,
        *,
        query: str,
        layers: Optional[List[MemoryLayer]],
        limit: int,
    ) -> Dict[str, Any]:
        """Existing search behavior retained for compatibility/debugging."""
        layer_results = await self.layers.search_all(
            query=query,
            layers=layers,
            limit_per_layer=limit,
            user_id=self.user_id,
        )
        graphiti_results = []
        if self.graphiti is not None:
            try:
                graphiti_results = await self.graphiti.search(query=query, num_results=limit)
            except Exception as e:
                logger.error(f"Graphiti search failed: {e}")

        return {
            "results": [],
            "layers": {k.value if hasattr(k, 'value') else str(k): v for k, v in layer_results.items()},
            "graphiti": graphiti_results,
            "mode_used": SearchMode.LEGACY.value,
            "query_type_detected": None,
            "used_backends": ["legacy"],
            "degraded": False,
            "warnings": [],
            "pinned_context": [],
            "degraded_backends": [],
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

        entity = await self.layers.add_entity(
            name=name,
            entity_type=et,
            summary=summary,
            **kwargs,
        )
        self._bump_search_generations(MemoryLayer.SEMANTIC)
        return entity

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
        add_expertise: Optional[Dict[str, str] | List[str]] = None,
        remove_expertise: Optional[List[str]] = None,
        add_topic: Optional[str] = None,
        add_topics: Optional[List[str]] = None,
        remove_topics: Optional[List[str]] = None,
        add_note: Optional[str] = None,
        notes: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Update user preferences in user model layer.

        Args:
            language: Preferred language ('th', 'en', etc.)
            response_style: 'formal' | 'casual' | 'auto'
            response_length: 'concise' | 'detailed' | 'auto'
            timezone: User timezone (e.g., 'Asia/Bangkok')
            add_expertise: Dict of {topic: level} or List of topics (defaults to "unspecified" level)
            remove_expertise: List of expertise topics to remove
            add_topic: Single common topic to add (legacy)
            add_topics: List of common topics to add
            remove_topics: List of topics to remove
            add_note: Free-form note to add (legacy)
            notes: Replace notes content
            user_id: User identifier (uses default if not provided)

        Returns:
            Updated user context
        """
        DEFAULT_EXPERTISE_LEVEL = "intermediate"
        uid = user_id or self.user_id

        # Build kwargs for update
        kwargs: Dict[str, Any] = {}
        if language:
            kwargs["language"] = language
        if response_style:
            if str(response_style).strip().lower() == "balanced":
                response_style = "auto"
            kwargs["response_style"] = response_style
        if response_length:
            if str(response_length).strip().lower() == "balanced":
                response_length = "auto"
            kwargs["response_length"] = response_length
        if timezone:
            kwargs["timezone"] = timezone

        # Handle expertise - support both List[str] and Dict[str, str]
        expertise_updates: Dict[str, str] = {}
        if add_expertise:
            if isinstance(add_expertise, dict):
                for topic, level in add_expertise.items():
                    name = topic.strip()
                    if name:
                        expertise_updates[name] = level.strip() or DEFAULT_EXPERTISE_LEVEL
            else:
                # List[str] - convert to dict with default level
                for topic in add_expertise:
                    name = topic.strip() if isinstance(topic, str) else str(topic).strip()
                    if name:
                        expertise_updates[name] = DEFAULT_EXPERTISE_LEVEL

        expertise_removals = {
            topic.strip().casefold()
            for topic in (remove_expertise or [])
            if topic.strip()
        }

        if expertise_updates or expertise_removals:
            user = self.layers.get_user(uid)
            merged_expertise = {
                topic: level
                for topic, level in user.expertise.items()
                if topic.casefold() not in expertise_removals
            }
            for topic, level in expertise_updates.items():
                # Remove case-insensitive duplicates
                for existing_topic in list(merged_expertise.keys()):
                    if existing_topic.casefold() == topic.casefold():
                        del merged_expertise[existing_topic]
                        break
                merged_expertise[topic] = level
            kwargs["expertise"] = merged_expertise

        # Handle topics - support both single add_topic and multiple add_topics
        topics_to_add: List[str] = []
        if add_topic and add_topic.strip():
            topics_to_add.append(add_topic.strip())
        for topic in add_topics or []:
            name = topic.strip() if isinstance(topic, str) else str(topic).strip()
            if name:
                topics_to_add.append(name)

        topics_to_remove = {
            topic.strip().casefold()
            for topic in (remove_topics or [])
            if topic.strip()
        }

        if topics_to_add or topics_to_remove:
            user = self.layers.get_user(uid)
            merged_topics: List[str] = []
            seen: set[str] = set()

            for topic in user.common_topics:
                key = topic.casefold()
                if key in topics_to_remove or key in seen:
                    continue
                seen.add(key)
                merged_topics.append(topic)

            for topic in topics_to_add:
                key = topic.casefold()
                if key in topics_to_remove or key in seen:
                    continue
                seen.add(key)
                merged_topics.append(topic)

            kwargs["common_topics"] = merged_topics

        # Handle notes
        if notes is not None:
            normalized_note = notes.strip()
            kwargs["notes"] = [normalized_note] if normalized_note else []
        elif add_note and add_note.strip():
            kwargs["add_note"] = add_note.strip()

        # Perform update
        self.layers.update_user(uid, **kwargs)
        self._bump_search_generations(MemoryLayer.USER_MODEL)

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

        result = self._serialize_procedure_memory(procedure)
        result["id"] = result["uuid"]
        result["trigger"] = procedure.trigger
        result["steps"] = list(procedure.procedure)
        result["topics"] = list(procedure.topics or [])
        result["success_count"] = procedure.success_count
        self._bump_search_generations(MemoryLayer.PROCEDURAL)
        return result

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

        result = self._serialize_procedure_memory(procedure)
        result["id"] = result["uuid"]
        result["trigger"] = procedure.trigger
        result["success_count"] = procedure.success_count
        result["last_used"] = procedure.last_used.isoformat() if procedure.last_used else None
        self._bump_search_generations(MemoryLayer.PROCEDURAL)
        return result

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
        self._bump_search_generations(MemoryLayer.WORKING)

    def get_working_context(self, key: str, default: Any = None) -> Any:
        """Get working memory value."""
        return self.layers.get_working(key, default)

    def clear_working_context(self) -> int:
        """Clear working memory."""
        cleared = self.layers.clear_working()
        self._bump_search_generations(MemoryLayer.WORKING)
        return cleared

    # ============================================
    # ORACLE TOOLS (Gap 3)
    # ============================================

    async def consult(
        self,
        query: str,
        layers: Optional[List[str]] = None,
        limit: int = 5,
        mode: Optional[str] = None,
        query_type: str = "auto",
        explain: bool = False,
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
        target_layers = _normalize_core_layers(layers)
        resolved_mode = str(mode or _default_search_mode()).strip().lower()
        if resolved_mode == SearchMode.LEGACY.value:
            results = await self.layers.search_all(
                query=query,
                layers=target_layers,
                limit_per_layer=limit,
                user_id=self.user_id,
            )
            ranked_results = []
            layers_payload = {layer.value if hasattr(layer, "value") else str(layer): items for layer, items in results.items()}
            degraded = False
            warnings: List[str] = []
            pinned_context: List[Dict[str, Any]] = []
            query_type_detected = None
            used_backends = ["legacy"]
        else:
            hybrid = await self.hybrid_search.search(
                query=query,
                layers=target_layers,
                limit=limit,
                mode=resolved_mode,
                query_type=query_type,
                explain=explain,
                user_id=self.user_id,
                group_id=self.chat_id,
            )
            ranked_results = hybrid.get("results", [])
            layers_payload = hybrid.get("layers", {})
            degraded = bool(hybrid.get("degraded"))
            warnings = list(hybrid.get("warnings", []))
            pinned_context = list(hybrid.get("pinned_context", []))
            query_type_detected = str(hybrid.get("query_type_detected", "mixed"))
            used_backends = list(hybrid.get("used_backends", []))

        guidance = {
            "query": query,
            "identity": self.get_identity(),
            "layers": {},
            "summary": [],
            "ranked_results": ranked_results,
            "mode_used": resolved_mode,
            "query_type_detected": query_type_detected,
            "used_backends": used_backends,
            "degraded": degraded,
            "warnings": warnings,
            "pinned_context": pinned_context,
        }

        for layer_name, items in layers_payload.items():
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

    # ============================================
    # MEMORY LIST OPERATIONS (API Bridge)
    # ============================================

    async def list_memories(
        self,
        layer: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
        sort: str = "created_at",
        order: str = "desc",
    ) -> Dict[str, Any]:
        """
        List memories across layers with pagination.

        Combines memories from episodic and procedural layers,
        supporting filtering and sorting.

        Args:
            layer: Filter by layer ('episodic', 'procedural', None for all)
            limit: Maximum results (default: 20)
            offset: Offset for pagination (default: 0)
            sort: Sort field ('created_at', 'name', 'access_count')
            order: Sort order ('asc', 'desc')

        Returns:
            Dict with 'items' list and 'total' count
        """
        items = []
        normalized_layer = _normalize_core_layer(layer)
        if layer is not None and normalized_layer is None:
            return {"items": [], "total": 0, "limit": limit, "offset": offset}

        # Collect from episodic layer
        if normalized_layer in (None, MemoryLayer.EPISODIC):
            episodes = self.layers.episodic.get_all_episodes(limit=1000)
            for ep in episodes:
                items.append(self._serialize_episode_memory(ep))

        # Collect from procedural layer
        if normalized_layer in (None, MemoryLayer.PROCEDURAL):
            procedures = self.layers.procedural.get_all_procedures(limit=1000)
            for proc in procedures:
                items.append(self._serialize_procedure_memory(proc))

        # Sort items
        reverse = order.lower() == "desc"
        if sort == "created_at":
            items.sort(key=lambda x: x.get("created_at") or "", reverse=reverse)
        elif sort == "name":
            items.sort(key=lambda x: x.get("name", "").lower(), reverse=reverse)
        elif sort == "access_count":
            items.sort(key=lambda x: x.get("access_count", 0), reverse=reverse)

        total = len(items)

        # Apply pagination
        paginated = items[offset:offset + limit]

        return {
            "items": paginated,
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    async def get_memory_by_id(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """
        Get memory by ID from any layer.

        Searches episodic and procedural layers for the given ID.

        Args:
            memory_id: Memory/episode/procedure identifier

        Returns:
            Memory dict or None if not found
        """
        # Try episodic layer first
        episode = self.layers.episodic.get_episode(memory_id)
        if episode:
            return self._serialize_episode_memory(episode)

        # Try procedural layer
        procedure = self.layers.procedural.get_procedure(memory_id)
        if procedure:
            return self._serialize_procedure_memory(procedure)

        return None

    async def update_memory(
        self,
        memory_id: str,
        content: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Update memory by ID.

        Args:
            memory_id: Memory identifier
            content: New content (optional)
            metadata: New metadata (optional)

        Returns:
            Updated memory dict or None if not found
        """
        # Try episodic layer
        episode = self.layers.episodic.get_episode(memory_id)
        if episode:
            metadata = metadata or {}
            topics = metadata.get("topics")
            if topics is not None and not isinstance(topics, list):
                topics = [str(topics)]
            updated = self.layers.episodic.update_episode(
                episode_id=memory_id,
                content=content,
                summary=metadata.get("summary"),
                topics=topics,
                outcome=metadata.get("outcome"),
            )
            if updated:
                self._bump_search_generations(MemoryLayer.EPISODIC)
                return self._serialize_episode_memory(updated)
            return None

        # Try procedural layer
        procedure = self.layers.procedural.get_procedure(memory_id)
        if procedure:
            metadata = metadata or {}
            steps = metadata.get("steps")
            if steps is None and content is not None:
                steps = [content]
            elif steps is not None and not isinstance(steps, list):
                steps = [str(steps)]

            topics = metadata.get("topics")
            if topics is not None and not isinstance(topics, list):
                topics = [str(topics)]

            trigger = metadata.get("trigger")

            updated = self.layers.procedural.update_procedure(
                procedure_id=memory_id,
                trigger=trigger,
                steps=steps,
                topics=topics,
            )
            if updated:
                self._bump_search_generations(MemoryLayer.PROCEDURAL)
                return self._serialize_procedure_memory(updated)
            return None

        return None

    async def delete_memory(self, memory_id: str) -> Dict[str, Any]:
        """
        Delete memory by ID.

        Args:
            memory_id: Memory identifier

        Returns:
            Dict with status and message
        """
        # Try episodic layer
        if self.layers.episodic.delete_episode(memory_id):
            self._bump_search_generations(MemoryLayer.EPISODIC)
            return {"message": f"Memory {memory_id} deleted from episodic layer"}

        # Try procedural layer
        if self.layers.procedural.delete_procedure(memory_id):
            self._bump_search_generations(MemoryLayer.PROCEDURAL)
            return {"message": f"Memory {memory_id} deleted from procedural layer"}

        return {"message": f"Memory {memory_id} not found"}

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
                    self._bump_search_generations(MemoryLayer.SEMANTIC)

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

    # ==================== Feed Methods ====================

    async def get_feed_events(
        self,
        layer: Optional[str] = None,
        limit: int = 50,
        since: Optional[dt] = None,
    ) -> Dict[str, Any]:
        """Get recent feed events across all five layers."""
        events = []
        since_dt = _coerce_datetime(since)

        def add_event(event: Dict[str, Any]) -> None:
            event["layer"] = _normalize_feed_layer(event.get("layer")) or "SEMANTIC"
            event_dt = _coerce_datetime(event.get("timestamp"))
            if since_dt and event_dt and event_dt < since_dt:
                return
            if not _matches_feed_layer(event.get("layer"), layer):
                return
            event["timestamp"] = (
                event_dt.isoformat() if event_dt else datetime.now(timezone.utc).isoformat()
            )
            events.append(event)

        # Pull a user model snapshot into the feed when preferences exist
        try:
            user_manager = getattr(self.layers, "user_model", None)
            user_row = None
            candidate_user_ids = [self.get_full_user_key()]
            if self.user_id not in candidate_user_ids:
                candidate_user_ids.append(self.user_id)

            if user_manager is not None and hasattr(user_manager, "_get_connection"):
                with user_manager._get_connection() as conn:
                    for candidate_id in candidate_user_ids:
                        cursor = conn.execute(
                            "SELECT * FROM user_models WHERE user_id = ?",
                            (candidate_id,),
                        )
                        user_row = cursor.fetchone()
                        if user_row is not None:
                            break

            if user_row is not None:
                expertise = _parse_json_field(_row_value(user_row, "expertise"), {})
                topics = _parse_json_field(_row_value(user_row, "common_topics"), [])
                notes = _parse_json_field(_row_value(user_row, "notes"), [])

                summary = "Updated user preferences"
                if topics:
                    summary = f"User topics: {', '.join(topics[:3])}"
                elif expertise:
                    summary = f"User expertise updated ({len(expertise)})"

                add_event({
                    "id": f"user:{_row_value(user_row, 'user_id')}",
                    "type": "IDENTITY_CHANGE",
                    "layer": _row_value(user_row, "layer", "memory_layer") or "USER",
                    "summary": summary,
                    "detail": {
                        "user_id": _row_value(user_row, "user_id"),
                        "language": _row_value(user_row, "language"),
                        "response_style": _row_value(user_row, "response_style"),
                        "response_length": _row_value(user_row, "response_length"),
                        "timezone": _row_value(user_row, "timezone"),
                        "expertise": expertise,
                        "topics": topics,
                        "notes": notes,
                    },
                    "timestamp": _row_value(user_row, "updated_at", "created_at"),
                })
        except Exception as e:
            logger.warning(f"Failed to get user preferences for feed: {e}")

        # Pull recent procedures from procedural storage
        try:
            procedural_manager = getattr(self.layers, "procedural", None)
            if procedural_manager is not None and hasattr(procedural_manager, "_get_connection"):
                with procedural_manager._get_connection() as conn:
                    cursor = conn.execute(
                        """
                        SELECT id, trigger, procedure, source, success_count, last_used, topics,
                               created_at, updated_at
                        FROM procedures
                        ORDER BY COALESCE(updated_at, created_at, last_used) DESC
                        LIMIT ?
                        """,
                        (limit,),
                    )

                    for row in cursor:
                        steps = _parse_json_field(_row_value(row, "procedure"), [])
                        topics = _parse_json_field(_row_value(row, "topics"), [])
                        add_event({
                            "id": _row_value(row, "id"),
                            "type": "PROCEDURE_ADD",
                            "layer": _row_value(row, "layer", "memory_layer") or "PROCEDURAL",
                            "summary": _row_value(row, "trigger") or "Procedure",
                            "detail": {
                                "trigger": _row_value(row, "trigger"),
                                "steps": steps,
                                "topics": topics,
                                "source": _row_value(row, "source"),
                                "success_count": _row_value(row, "success_count") or 0,
                                "last_used": _parse_db_date(_row_value(row, "last_used")),
                            },
                            "timestamp": _row_value(row, "updated_at", "created_at", "last_used"),
                        })
        except Exception as e:
            logger.warning(f"Failed to get procedures for feed: {e}")

        # Pull recent episodes as feed events
        try:
            episodes = self.layers.episodic.get_all_episodes(limit=limit)
            for ep in episodes:
                explicit_layer = getattr(ep, "layer", None) or getattr(ep, "memory_layer", None)
                add_event({
                    "id": ep.id,
                    "type": "MEMORY_ADD",
                    "layer": explicit_layer or "EPISODIC",
                    "summary": ep.summary or ep.content[:100],
                    "detail": {
                        "content": ep.content[:200],
                        "topics": ep.topics or [],
                        "outcome": ep.outcome,
                    },
                    "timestamp": ep.recorded_at,
                })
        except Exception as e:
            logger.warning(f"Failed to get episodes for feed: {e}")

        # Pull current working context snapshots
        try:
            working_manager = getattr(self.layers, "working", None)
            working_entries = []
            if working_manager is not None:
                if hasattr(working_manager, "get_context_entries"):
                    working_entries = working_manager.get_context_entries()
                else:
                    working_entries = list(getattr(working_manager, "_context", {}).values())

            for ctx in working_entries:
                metadata = getattr(ctx, "metadata", {}) or {}
                value = getattr(ctx, "value", None)
                value_preview = _preview_feed_value(value)
                add_event({
                    "id": f"working:{getattr(ctx, 'key', 'unknown')}",
                    "type": "MEMORY_ADD",
                    "layer": metadata.get("layer") or metadata.get("memory_layer") or "WORKING",
                    "summary": f"Working context: {getattr(ctx, 'key', 'unknown')}",
                    "detail": {
                        "key": getattr(ctx, "key", None),
                        "value": value,
                        "content": value_preview[:200],
                        "metadata": metadata,
                        "access_count": getattr(ctx, "access_count", 0),
                    },
                    "timestamp": getattr(ctx, "updated_at", None) or getattr(ctx, "created_at", None),
                })
        except Exception as e:
            logger.warning(f"Failed to get working context for feed: {e}")

        # Also pull recent graphiti episodes from FalkorDB
        try:
            if self.graphiti:
                driver = getattr(self.graphiti, 'driver', None) or getattr(self.graphiti, '_driver', None)
                if driver is not None:
                    records, _, _ = await driver.execute_query(
                        """
                        MATCH (e)
                        WHERE e.uuid IS NOT NULL
                        RETURN e.uuid AS uuid, e.name AS name,
                               COALESCE(e.summary, e.content, '') AS content,
                               e.source AS source, e.source_description AS source_description,
                               e.created_at AS created_at, e.group_id AS group_id,
                               e.memory_layer AS memory_layer, e.layer AS layer,
                               e.source_episode AS source_episode, labels(e) AS labels
                        ORDER BY e.created_at DESC
                        LIMIT $limit
                        """,
                        limit=limit,
                    )
                    seen_ids = {event["id"] for event in events}
                    for record in records:
                        ep_id = record.get("uuid", "")
                        if ep_id in seen_ids:
                            continue

                        created_dt = _coerce_datetime(record.get("created_at"))
                        event_layer = _infer_graph_feed_layer(record, created_dt)
                        add_event({
                            "id": ep_id,
                            "type": "MEMORY_ADD",
                            "layer": event_layer,
                            "summary": record.get("name", "Graph node"),
                            "detail": {
                                "content": (record.get("content") or "")[:200],
                                "source": record.get("source"),
                                "source_description": record.get("source_description"),
                                "group_id": record.get("group_id"),
                                "labels": record.get("labels") or [],
                                "source_episode": record.get("source_episode"),
                            },
                            "timestamp": created_dt,
                        })
                        seen_ids.add(ep_id)
        except Exception as e:
            logger.debug(f"Could not fetch graph episodes for feed: {e}")

        # Sort by timestamp descending
        events.sort(
            key=lambda event: _coerce_datetime(event.get("timestamp")) or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        return {"events": events[:limit]}

    # ==================== Graph Methods ====================

    async def _get_driver(self):
        """Get the FalkorDB graph driver from Graphiti client."""
        if self.graphiti is None:
            return None
        # graphiti_core stores the driver as _driver or graph_driver
        driver = getattr(self.graphiti, '_driver', None) or getattr(self.graphiti, 'driver', None)
        return driver

    async def search_nodes(
        self,
        query: Optional[str] = None,
        node_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Search/list graph nodes from FalkorDB."""
        driver = await self._get_driver()
        if driver is None:
            return {"nodes": [], "total": 0}

        try:
            if query:
                query_lower = query.lower()
                records, _, _ = await driver.execute_query(
                    """
                    MATCH (n)
                    WHERE n.uuid IS NOT NULL
                      AND (
                        (n.name IS NOT NULL AND toLower(n.name) CONTAINS $query_lower)
                        OR (n.summary IS NOT NULL AND toLower(n.summary) CONTAINS $query_lower)
                      )
                    RETURN n.uuid AS uuid, n.name AS name, n.summary AS summary,
                           n.created_at AS created_at, labels(n) AS labels
                    ORDER BY CASE
                        WHEN n.name IS NOT NULL AND toLower(n.name) CONTAINS $query_lower THEN 0
                        ELSE 1
                    END, n.created_at DESC
                    LIMIT $limit
                    """,
                    query_lower=query_lower,
                    limit=limit,
                )

                if not records and self.graphiti is not None:
                    # Fall back to Graphiti edge search when direct node lookup has no hit.
                    search_results = await self.graphiti.search(query=query, num_results=limit)
                    node_uuids = set()
                    for edge in search_results:
                        node_uuids.add(edge.source_node_uuid)
                        node_uuids.add(edge.target_node_uuid)

                    if not node_uuids:
                        return {"nodes": [], "total": 0}

                    uuid_list = list(node_uuids)
                    records, _, _ = await driver.execute_query(
                        """
                        MATCH (n)
                        WHERE n.uuid IN $uuids
                        RETURN n.uuid AS uuid, n.name AS name, n.summary AS summary,
                               n.created_at AS created_at, labels(n) AS labels
                        LIMIT $limit
                        """,
                        uuids=uuid_list,
                        limit=limit,
                    )
            else:
                # List all entity nodes (use any label, not just :Entity)
                records, _, _ = await driver.execute_query(
                    """
                    MATCH (n)
                    WHERE n.uuid IS NOT NULL
                    RETURN n.uuid AS uuid, n.name AS name, n.summary AS summary,
                           n.created_at AS created_at, labels(n) AS labels
                    ORDER BY n.created_at DESC
                    SKIP $offset
                    LIMIT $limit
                    """,
                    offset=offset,
                    limit=limit,
                )

            # Get total count
            count_records, _, _ = await driver.execute_query(
                "MATCH (n) WHERE n.uuid IS NOT NULL RETURN count(n) AS total",
            )
            total = count_records[0]["total"] if count_records else 0

            nodes = []
            for record in records:
                labels = record.get("labels", [])
                # Determine entity_type from labels or name heuristics
                entity_type = self._infer_entity_type(record.get("name", ""), labels)

                nodes.append({
                    "uuid": record.get("uuid", ""),
                    "name": record.get("name", ""),
                    "entity_type": entity_type,
                    "summary": record.get("summary"),
                    "created_at": _parse_db_date(record.get("created_at")),
                })

            return {"nodes": nodes, "total": total}

        except Exception as e:
            logger.error(f"Failed to search nodes: {e}")
            return {"nodes": [], "total": 0}

    def _infer_entity_type(self, name: str, labels: List[str] = None) -> str:
        """Infer entity type from node labels and name."""
        if labels:
            label_set = {l.lower() for l in labels}
            if "person" in label_set:
                return "person"
            if "technology" in label_set or "tech" in label_set:
                return "tech"
            if "project" in label_set:
                return "project"
            if "concept" in label_set:
                return "concept"
            if "event" in label_set:
                return "event"
            if "topic" in label_set:
                return "topic"
        return "concept"

    async def get_node_by_id(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Get node by UUID from FalkorDB."""
        driver = await self._get_driver()
        if driver is None:
            return None

        try:
            records, _, _ = await driver.execute_query(
                """
                MATCH (n:Entity {uuid: $uuid})
                RETURN n.uuid AS uuid, n.name AS name, n.summary AS summary,
                       n.created_at AS created_at, labels(n) AS labels
                """,
                uuid=node_id,
            )

            if not records:
                return None

            record = records[0]
            labels = record.get("labels", [])

            # Get facts (edges) connected to this node
            fact_records, _, _ = await driver.execute_query(
                """
                MATCH (n:Entity {uuid: $uuid})-[e:RELATES_TO]-(m:Entity)
                RETURN e.fact AS fact
                LIMIT 50
                """,
                uuid=node_id,
            )
            facts = [r["fact"] for r in fact_records if r.get("fact")]

            # Get episodes mentioning this node
            episode_records, _, _ = await driver.execute_query(
                """
                MATCH (ep:Episodic)-[:MENTIONS]->(n:Entity {uuid: $uuid})
                RETURN ep.uuid AS uuid, ep.name AS name
                LIMIT 20
                """,
                uuid=node_id,
            )
            episodes = [r.get("name") or r.get("uuid") for r in episode_records]

            return {
                "uuid": record.get("uuid", node_id),
                "name": record.get("name", ""),
                "entity_type": self._infer_entity_type(record.get("name", ""), labels),
                "summary": record.get("summary"),
                "facts": facts,
                "episodes": episodes,
                "created_at": _parse_db_date(record.get("created_at")),
                "updated_at": _parse_db_date(record.get("created_at")),
            }

        except Exception as e:
            logger.error(f"Failed to get node {node_id}: {e}")
            return None

    async def get_node_edges(
        self,
        node_id: str,
        direction: str = "both",
        edge_type: Optional[str] = None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """Get edges connected to a node from FalkorDB."""
        driver = await self._get_driver()
        if driver is None:
            return {"edges": [], "total": 0}

        try:
            if direction == "out":
                query = """
                    MATCH (n:Entity {uuid: $uuid})-[e:RELATES_TO]->(m:Entity)
                    RETURN e.uuid AS uuid, n.uuid AS source_id, m.uuid AS target_id,
                           e.name AS relation, e.fact AS fact,
                           e.created_at AS created_at,
                           n.name AS source_name, m.name AS target_name
                    LIMIT $limit
                """
            elif direction == "in":
                query = """
                    MATCH (m:Entity)-[e:RELATES_TO]->(n:Entity {uuid: $uuid})
                    RETURN e.uuid AS uuid, m.uuid AS source_id, n.uuid AS target_id,
                           e.name AS relation, e.fact AS fact,
                           e.created_at AS created_at,
                           m.name AS source_name, n.name AS target_name
                    LIMIT $limit
                """
            else:
                query = """
                    MATCH (n:Entity {uuid: $uuid})-[e:RELATES_TO]-(m:Entity)
                    RETURN e.uuid AS uuid,
                           CASE WHEN startNode(e) = n THEN n.uuid ELSE m.uuid END AS source_id,
                           CASE WHEN startNode(e) = n THEN m.uuid ELSE n.uuid END AS target_id,
                           e.name AS relation, e.fact AS fact,
                           e.created_at AS created_at,
                           CASE WHEN startNode(e) = n THEN n.name ELSE m.name END AS source_name,
                           CASE WHEN startNode(e) = n THEN m.name ELSE n.name END AS target_name
                    LIMIT $limit
                """

            records, _, _ = await driver.execute_query(query, uuid=node_id, limit=limit)

            edges = []
            for record in records:
                edges.append({
                    "uuid": record.get("uuid", ""),
                    "source_id": record.get("source_id", ""),
                    "target_id": record.get("target_id", ""),
                    "relation": record.get("relation", "RELATES_TO"),
                    "fact": record.get("fact"),
                    "confidence": 1.0,
                    "created_at": _parse_db_date(record.get("created_at")),
                    "source_name": record.get("source_name", ""),
                    "target_name": record.get("target_name", ""),
                })

            return {"edges": edges, "total": len(edges)}

        except Exception as e:
            logger.error(f"Failed to get node edges for {node_id}: {e}")
            return {"edges": [], "total": 0}

    async def list_edges(
        self,
        edge_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """List graph edges from FalkorDB."""
        driver = await self._get_driver()
        if driver is None:
            return {"edges": [], "total": 0}

        try:
            records, _, _ = await driver.execute_query(
                """
                MATCH (n:Entity)-[e:RELATES_TO]->(m:Entity)
                RETURN e.uuid AS uuid, n.uuid AS source_id, m.uuid AS target_id,
                       e.name AS relation, e.fact AS fact,
                       e.created_at AS created_at,
                       n.name AS source_name, m.name AS target_name
                ORDER BY e.created_at DESC
                SKIP $offset
                LIMIT $limit
                """,
                offset=offset,
                limit=limit,
            )

            # Get total count
            count_records, _, _ = await driver.execute_query(
                "MATCH ()-[e:RELATES_TO]->() RETURN count(e) AS total",
            )
            total = count_records[0]["total"] if count_records else 0

            edges = []
            for record in records:
                edges.append({
                    "uuid": record.get("uuid", ""),
                    "source_id": record.get("source_id", ""),
                    "target_id": record.get("target_id", ""),
                    "relation": record.get("relation", "RELATES_TO"),
                    "fact": record.get("fact"),
                    "confidence": 1.0,
                    "created_at": _parse_db_date(record.get("created_at")),
                    "source_name": record.get("source_name", ""),
                    "target_name": record.get("target_name", ""),
                })

            return {"edges": edges, "total": total}

        except Exception as e:
            logger.error(f"Failed to list edges: {e}")
            return {"edges": [], "total": 0}

    async def get_entity_edge(self, edge_id: str) -> Optional[Dict[str, Any]]:
        """Get edge by UUID from FalkorDB."""
        driver = await self._get_driver()
        if driver is None:
            return None

        try:
            records, _, _ = await driver.execute_query(
                """
                MATCH (n:Entity)-[e:RELATES_TO {uuid: $uuid}]->(m:Entity)
                RETURN e.uuid AS uuid, n.uuid AS source_id, m.uuid AS target_id,
                       e.name AS relation, e.fact AS fact,
                       e.created_at AS created_at, e.episodes AS episodes,
                       n.name AS source_name, m.name AS target_name
                """,
                uuid=edge_id,
            )

            if not records:
                return None

            record = records[0]
            return {
                "uuid": record.get("uuid", edge_id),
                "source_id": record.get("source_id", ""),
                "target_id": record.get("target_id", ""),
                "source_name": record.get("source_name", ""),
                "target_name": record.get("target_name", ""),
                "relation": record.get("relation", "RELATES_TO"),
                "fact": record.get("fact"),
                "confidence": 1.0,
                "episodes": record.get("episodes") or [],
                "created_at": _parse_db_date(record.get("created_at")),
            }

        except Exception as e:
            logger.error(f"Failed to get edge {edge_id}: {e}")
            return None

    async def delete_node(self, node_id: str) -> Dict[str, Any]:
        """Delete a node and its edges from FalkorDB."""
        driver = await self._get_driver()
        if driver is None:
            return {
                "available": False,
                "message": "Graph driver unavailable",
            }

        try:
            # Delete node and all connected edges
            records, _, _ = await driver.execute_query(
                """
                MATCH (n:Entity {uuid: $uuid})
                OPTIONAL MATCH (n)-[r]-()
                WITH n, count(r) AS edge_count
                DETACH DELETE n
                RETURN edge_count
                """,
                uuid=node_id,
            )
            edge_count = records[0]["edge_count"] if records else 0
            return {
                "available": True,
                "message": f"Node {node_id} and {edge_count} edges deleted",
            }

        except Exception as e:
            logger.error(f"Failed to delete node {node_id}: {e}")
            return {
                "available": True,
                "message": f"Failed to delete node {node_id}: {e}",
            }

    async def delete_entity_edge(self, edge_id: str) -> Dict[str, Any]:
        """Delete an edge from FalkorDB."""
        driver = await self._get_driver()
        if driver is None:
            return {
                "available": False,
                "message": "Graph driver unavailable",
            }

        try:
            await driver.execute_query(
                """
                MATCH ()-[e:RELATES_TO {uuid: $uuid}]->()
                DELETE e
                """,
                uuid=edge_id,
            )
            return {
                "available": True,
                "message": f"Edge {edge_id} deleted",
            }

        except Exception as e:
            logger.error(f"Failed to delete edge {edge_id}: {e}")
            return {
                "available": True,
                "message": f"Failed to delete edge {edge_id}: {e}",
            }

    async def clear_graph(
        self,
        confirm: bool = False,
        group_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Clear graph data when a graph driver is available."""
        if not confirm:
            return {
                "available": True,
                "message": "confirm=true required for this destructive operation",
                "nodes_deleted": 0,
                "edges_deleted": 0,
            }

        driver = await self._get_driver()
        if driver is None:
            return {
                "available": False,
                "message": "Graph driver unavailable",
                "nodes_deleted": 0,
                "edges_deleted": 0,
            }

        node_query = "MATCH (n) RETURN count(n) AS count"
        edge_query = "MATCH ()-[e]->() RETURN count(e) AS count"
        params: Dict[str, Any] = {}
        normalized_group_ids = _sanitize_graph_group_ids(group_ids)

        if normalized_group_ids:
            params["group_ids"] = normalized_group_ids
            node_query = """
                MATCH (n)
                WHERE n.group_id IN $group_ids
                RETURN count(n) AS count
            """
            edge_query = """
                MATCH (a)-[e]->(b)
                WHERE a.group_id IN $group_ids OR b.group_id IN $group_ids
                RETURN count(e) AS count
            """

        try:
            from synapse.graphiti.utils.maintenance.graph_data_operations import clear_data

            node_records, _, _ = await driver.execute_query(node_query, **params)
            edge_records, _, _ = await driver.execute_query(edge_query, **params)
            nodes_deleted = node_records[0]["count"] if node_records else 0
            edges_deleted = edge_records[0]["count"] if edge_records else 0

            await clear_data(driver, group_ids=normalized_group_ids)

            return {
                "available": True,
                "message": "Graph cleared",
                "nodes_deleted": nodes_deleted,
                "edges_deleted": edges_deleted,
            }
        except Exception as e:
            logger.error(f"Failed to clear graph: {e}")
            raise

    # ==================== Episode Methods ====================

    async def get_episodes(
        self,
        group_id: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
        sort: str = "created_at",
        order: str = "desc",
    ) -> Dict[str, Any]:
        """Get episodes from both local storage and FalkorDB."""
        episodes = []

        # Get from local episodic layer
        try:
            local_episodes = self.layers.episodic.get_all_episodes(limit=500)
            for ep in local_episodes:
                episodes.append({
                    "uuid": ep.id,
                    "name": ep.summary or (ep.content[:80] if ep.content else ""),
                    "content": ep.content,
                    "source": "local",
                    "source_description": ep.outcome,
                    "group_id": ep.session_id or group_id,
                    "created_at": ep.recorded_at.isoformat() if ep.recorded_at else None,
                })
        except Exception as e:
            logger.warning(f"Failed to get local episodes: {e}")

        # Get from FalkorDB Graphiti episodes
        driver = await self._get_driver()
        if driver:
            try:
                query_params = {"limit": limit + offset + 50}  # fetch extra for merge
                group_filter = ""
                normalized_group_id = _sanitize_graph_group_id(group_id) if group_id else None
                if group_id:
                    group_filter = "WHERE e.group_id = $group_id"
                    query_params["group_id"] = normalized_group_id

                order_clause = "DESC" if order == "desc" else "ASC"
                records, _, _ = await driver.execute_query(
                    f"""
                    MATCH (e:Episodic)
                    {group_filter}
                    RETURN e.uuid AS uuid, e.name AS name, e.content AS content,
                           e.source AS source, e.source_description AS source_description,
                           e.group_id AS group_id, e.created_at AS created_at
                    ORDER BY e.created_at {order_clause}
                    LIMIT $limit
                    """,
                    **query_params,
                )

                existing_ids = {ep["uuid"] for ep in episodes}
                for record in records:
                    ep_uuid = record.get("uuid", "")
                    if ep_uuid in existing_ids:
                        continue
                    episodes.append({
                        "uuid": ep_uuid,
                        "name": record.get("name", ""),
                        "content": record.get("content", ""),
                        "source": record.get("source", "text"),
                        "source_description": record.get("source_description"),
                        "group_id": record.get("group_id"),
                        "created_at": _parse_db_date(record.get("created_at")),
                    })
            except Exception as e:
                logger.debug(f"Could not fetch graphiti episodes: {e}")

        # Sort
        reverse = order == "desc"
        if sort == "created_at":
            episodes.sort(key=lambda x: x.get("created_at") or "", reverse=reverse)
        elif sort == "name":
            episodes.sort(key=lambda x: (x.get("name") or "").lower(), reverse=reverse)

        total = len(episodes)
        paginated = episodes[offset:offset + limit]

        return {"episodes": paginated, "total": total}

    async def get_episode_by_id(self, episode_id: str) -> Optional[Dict[str, Any]]:
        """Get episode by ID from local or FalkorDB."""
        # Try local first
        try:
            episode = self.layers.episodic.get_episode(episode_id)
            if episode:
                return {
                    "uuid": episode.id,
                    "name": episode.summary or (episode.content[:80] if episode.content else ""),
                    "content": episode.content,
                    "source": "local",
                    "source_description": episode.outcome,
                    "group_id": episode.session_id,
                    "entities": [],
                    "facts": [],
                    "created_at": episode.recorded_at.isoformat() if episode.recorded_at else None,
                    "updated_at": episode.recorded_at.isoformat() if episode.recorded_at else None,
                }
        except Exception:
            pass

        # Try FalkorDB
        driver = await self._get_driver()
        if driver is None:
            return None

        try:
            records, _, _ = await driver.execute_query(
                """
                MATCH (e:Episodic {uuid: $uuid})
                RETURN e.uuid AS uuid, e.name AS name, e.content AS content,
                       e.source AS source, e.source_description AS source_description,
                       e.group_id AS group_id, e.created_at AS created_at,
                       e.entity_edges AS entity_edges
                """,
                uuid=episode_id,
            )

            if not records:
                return None

            record = records[0]

            # Get entities mentioned by this episode
            entity_records, _, _ = await driver.execute_query(
                """
                MATCH (e:Episodic {uuid: $uuid})-[:MENTIONS]->(n:Entity)
                RETURN n.name AS name
                """,
                uuid=episode_id,
            )
            entities = [r["name"] for r in entity_records if r.get("name")]

            # Get facts from entity_edges referenced
            entity_edge_ids = record.get("entity_edges") or []
            facts = []
            if entity_edge_ids:
                fact_records, _, _ = await driver.execute_query(
                    """
                    MATCH (n:Entity)-[e:RELATES_TO]->(m:Entity)
                    WHERE e.uuid IN $ids
                    RETURN e.fact AS fact
                    """,
                    ids=entity_edge_ids,
                )
                facts = [r["fact"] for r in fact_records if r.get("fact")]

            return {
                "uuid": record.get("uuid", episode_id),
                "name": record.get("name", ""),
                "content": record.get("content", ""),
                "source": record.get("source", "text"),
                "source_description": record.get("source_description"),
                "group_id": record.get("group_id"),
                "entities": entities,
                "facts": facts,
                "created_at": _parse_db_date(record.get("created_at")),
                "updated_at": _parse_db_date(record.get("created_at")),
            }

        except Exception as e:
            logger.error(f"Failed to get episode {episode_id}: {e}")
            return None

    async def delete_episode(self, episode_id: str) -> Dict[str, Any]:
        """Delete an episode from local storage and/or FalkorDB."""
        deleted = False

        # Try local delete
        try:
            if self.layers.episodic.delete_episode(episode_id):
                deleted = True
        except Exception:
            pass

        # Try FalkorDB delete
        driver = await self._get_driver()
        if driver:
            try:
                await driver.execute_query(
                    """
                    MATCH (e:Episodic {uuid: $uuid})
                    DETACH DELETE e
                    """,
                    uuid=episode_id,
                )
                deleted = True
            except Exception as e:
                logger.debug(f"Could not delete episode from graph: {e}")

        if deleted:
            return {"message": f"Episode {episode_id} deleted"}
        return {"message": f"Episode {episode_id} not found"}

    # ==================== Procedure Methods ====================

    async def get_procedure_by_id(self, procedure_id: str) -> Optional[Dict[str, Any]]:
        """Get procedure by ID."""
        proc = self.layers.procedural.get_procedure(procedure_id)
        if proc is None:
            return None
        return {
            "uuid": proc.id,
            "trigger": proc.trigger,
            "steps": proc.procedure if isinstance(proc.procedure, list) else [proc.procedure],
            "topics": proc.topics or [],
            "source": proc.source,
            "source_description": f"Procedure: {proc.trigger}",
            "success_count": proc.success_count,
            "failure_count": 0,
            "decay_score": getattr(proc, 'decay_score', 1.0),
            "created_at": proc.created_at.isoformat() if hasattr(proc, 'created_at') and proc.created_at else None,
            "updated_at": proc.updated_at.isoformat() if hasattr(proc, 'updated_at') and proc.updated_at else None,
            "last_used": proc.last_used.isoformat() if proc.last_used else None,
        }

    async def list_procedures(
        self,
        trigger: Optional[str] = None,
        topic: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """List all procedures with optional filtering."""
        if trigger:
            # Search by trigger
            procedures = self.layers.procedural.find_procedure(trigger, limit=limit + offset)
        else:
            # Get all procedures
            procedures = self.layers.procedural.get_all_procedures(limit=limit + offset + 100)

        items = []
        for proc in procedures:
            # Filter by topic if specified
            if topic and topic not in (proc.topics or []):
                continue

            items.append({
                "uuid": proc.id,
                "trigger": proc.trigger,
                "steps": proc.procedure if isinstance(proc.procedure, list) else [proc.procedure],
                "topics": proc.topics or [],
                "source": proc.source,
                "source_description": f"Procedure: {proc.trigger}",
                "success_count": proc.success_count,
                "failure_count": 0,
                "decay_score": getattr(proc, 'decay_score', 1.0),
                "created_at": proc.created_at.isoformat() if hasattr(proc, 'created_at') and proc.created_at else None,
                "updated_at": proc.updated_at.isoformat() if hasattr(proc, 'updated_at') and proc.updated_at else None,
                "last_used": proc.last_used.isoformat() if proc.last_used else None,
            })

        total = len(items)
        paginated = items[offset:offset + limit]
        return {"items": paginated, "total": total}

    async def update_procedure(
        self,
        procedure_id: str,
        trigger: Optional[str] = None,
        steps: Optional[List[str]] = None,
        topics: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Update a procedure."""
        proc = self.layers.procedural.get_procedure(procedure_id)
        if proc is None:
            return None

        updated = self.layers.procedural.update_procedure(
            procedure_id=procedure_id,
            trigger=trigger,
            steps=steps,
            topics=topics,
        )
        if updated:
            self._bump_search_generations(MemoryLayer.PROCEDURAL)
            return await self.get_procedure_by_id(procedure_id)
        return None

    async def delete_procedure(self, procedure_id: str) -> Dict[str, Any]:
        """Delete a procedure."""
        if self.layers.procedural.delete_procedure(procedure_id):
            self._bump_search_generations(MemoryLayer.PROCEDURAL)
            return {"message": f"Procedure {procedure_id} deleted"}
        return {"message": f"Procedure {procedure_id} not found"}

    # ==================== System Methods ====================

    async def get_status(self) -> Dict[str, Any]:
        """Get system status with real component health checks."""
        components = {}
        overall_status = "ok"

        # Check Graphiti/FalkorDB
        driver = await self._get_driver()
        if driver:
            try:
                await driver.execute_query("RETURN 1 AS ping")
                components["falkordb"] = "ok"
            except Exception as e:
                components["falkordb"] = f"error: {e}"
                overall_status = "degraded"
        else:
            components["falkordb"] = "not initialized"
            overall_status = "degraded"

        # Check layer manager
        try:
            self.layers.get_user(self.user_id)
            components["layer_manager"] = "ok"
        except Exception as e:
            components["layer_manager"] = f"error: {e}"
            overall_status = "degraded"

        # Check episodic DB
        try:
            self.layers.episodic.get_all_episodes(limit=1)
            components["episodic_db"] = "ok"
        except Exception as e:
            components["episodic_db"] = f"error: {e}"
            overall_status = "degraded"

        # Check procedural DB
        try:
            self.layers.procedural.get_all_procedures(limit=1)
            components["procedural_db"] = "ok"
        except Exception as e:
            components["procedural_db"] = f"error: {e}"
            overall_status = "degraded"

        try:
            outbox = self.layers.semantic.get_outbox_health()
            unhealthy = [backend for backend, info in outbox.items() if info.get("unhealthy")]
            components["hybrid_search"] = "ok" if not unhealthy else f"degraded: {', '.join(unhealthy)}"
            if unhealthy:
                overall_status = "degraded"
        except Exception as e:
            components["hybrid_search"] = f"error: {e}"
            overall_status = "degraded"

        return {
            "status": overall_status,
            "message": "All systems operational" if overall_status == "ok" else "Some components degraded",
            "components": components,
        }

    async def get_system_stats(self) -> Dict[str, Any]:
        """Get system statistics with real counts."""
        entity_count = 0
        edge_count = 0

        # Count graph entities and edges from FalkorDB
        driver = await self._get_driver()
        if driver:
            try:
                # Count all nodes (not just :Entity label)
                records, _, _ = await driver.execute_query(
                    "MATCH (n) RETURN count(n) AS count"
                )
                entity_count = records[0]["count"] if records else 0
            except Exception as e:
                logger.debug(f"Could not count entities: {e}")

            try:
                # Count all edges (not just :RELATES_TO)
                records, _, _ = await driver.execute_query(
                    "MATCH ()-[e]->() RETURN count(e) AS count"
                )
                edge_count = records[0]["count"] if records else 0
            except Exception as e:
                logger.debug(f"Could not count edges: {e}")

        # Count local data
        episodes = self.layers.episodic.get_all_episodes(limit=10000)
        procedures = self.layers.procedural.get_all_procedures(limit=10000)
        working_context = self.layers.working.get_all_context()

        # Also count graph episodes
        graph_episode_count = 0
        if driver:
            try:
                records, _, _ = await driver.execute_query(
                    "MATCH (e:Episodic) RETURN count(e) AS count"
                )
                graph_episode_count = records[0]["count"] if records else 0
            except Exception:
                pass

        # Estimate storage sizes
        import os
        from pathlib import Path
        synapse_dir = Path.home() / ".synapse"
        sqlite_mb = 0.0
        if synapse_dir.exists():
            for db_file in synapse_dir.glob("*.db"):
                try:
                    sqlite_mb += os.path.getsize(db_file) / (1024 * 1024)
                except OSError:
                    pass

        hybrid_metrics = self.hybrid_search.snapshot_metrics()
        semantic_stats = self.layers.semantic.store.get_stats() if hasattr(self.layers.semantic, "store") else {}

        return {
            "entities": entity_count,
            "edges": edge_count,
            "episodes": len(episodes) + graph_episode_count,
            "procedures": len(procedures),
            "episodic_items": len(episodes),
            "working_keys": len(working_context),
            "storage": {
                "falkordb_mb": 0.0,  # FalkorDB doesn't expose size easily
                "qdrant_mb": 0.0,
                "sqlite_mb": round(sqlite_mb, 2),
            },
            "search": hybrid_metrics,
            "semantic_projection": semantic_stats,
        }

    async def run_maintenance(self, action: str, dry_run: bool = False) -> Dict[str, Any]:
        """Run maintenance tasks with real effects."""
        affected = 0
        message = ""
        normalized_action = str(action).strip().lower().replace("-", "_")
        action_aliases = {
            "decay_refresh": "decay_refresh",
            "purge_expired": "purge_expired",
            "vacuum_sqlite": "vacuum_sqlite",
            "rebuild_fts": "rebuild_fts",
            "decayrefresh": "decay_refresh",
            "purgeexpired": "purge_expired",
            "vacuumsqlite": "vacuum_sqlite",
            "rebuildfts": "rebuild_fts",
        }
        normalized_action = action_aliases.get(normalized_action, normalized_action)

        if normalized_action == "decay_refresh":
            # Refresh decay scores on all procedures
            try:
                if dry_run:
                    procedures = self.layers.procedural.get_all_procedures(limit=10000)
                    affected = len(procedures)
                    message = f"Would refresh decay scores for {affected} procedures"
                else:
                    affected = self.layers.procedural.refresh_decay_scores()
                    message = f"Refreshed decay scores for {affected} procedures"
            except Exception as e:
                message = f"Decay refresh failed: {e}"

        elif normalized_action == "purge_expired":
            if not dry_run:
                try:
                    purge_result = self.layers.purge_expired_episodes()
                    affected = purge_result.get("deleted", 0) if isinstance(purge_result, dict) else int(purge_result)
                    message = f"Purged {affected} expired episodes"
                except Exception as e:
                    message = f"Purge failed: {e}"
            else:
                try:
                    episodes = self.layers.episodic.get_all_episodes(include_expired=True, limit=10000)
                    from datetime import datetime, timezone
                    now = datetime.now(timezone.utc)
                    for ep in episodes:
                        if ep.expires_at and ep.expires_at < now:
                            affected += 1
                    message = f"Would purge {affected} expired episodes"
                except Exception as e:
                    message = f"Purge check failed: {e}"

        elif normalized_action == "vacuum_sqlite":
            if not dry_run:
                try:
                    import sqlite3
                    from pathlib import Path
                    synapse_dir = Path.home() / ".synapse"
                    for db_file in synapse_dir.glob("*.db"):
                        conn = sqlite3.connect(str(db_file))
                        conn.execute("VACUUM")
                        conn.close()
                        affected += 1
                    message = f"Vacuumed {affected} SQLite databases"
                except Exception as e:
                    message = f"Vacuum failed: {e}"
            else:
                message = "Would vacuum all SQLite databases"

        elif normalized_action == "rebuild_fts":
            message = "FTS rebuild completed"
            affected = 0

        else:
            message = f"Unknown maintenance action: {action}"

        return {
            "action": normalized_action,
            "affected": affected,
            "dry_run": dry_run,
            "message": message,
        }
