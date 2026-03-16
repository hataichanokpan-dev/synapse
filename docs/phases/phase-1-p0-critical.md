# Phase 1: Critical Fixes (P0)

> **Duration**: 3-4 days
> **Goal**: Make system work as designed - connect MCP to LayerManager
> **Assignee**: เดฟ (Dev) 🦀
> **Reviewer**: Mneme 🧠

---

## Overview

Phase 1 เป็น foundation ของการแก้ไขทั้งหมด ต้องทำให้ MCP Server สามารถใช้ LayerManager ได้จริง

---

## Tasks

### Task 1.1: Create SynapseService Bridge Class

| Field | Value |
|-------|-------|
| **Priority** | P0 - Critical |
| **Est. Time** | 2 days |
| **Assignee** | เดฟ (Dev) |
| **Reviewer** | Mneme |
| **Dependencies** | None |

#### Problem

`graphiti_mcp_server.py` เรียก `graphiti_client` โดยตรง ไม่ผ่าน LayerManager

**Evidence** (Line 24, 169-171, 410):
```python
# graphiti_mcp_server.py
global graphiti_service  # ← ไม่มี LayerManager

@mcp.tool()
async def add_memory(name, episode_body, source_description):
    client = await graphiti_service.get_client()
    await client.add_episode(...)  # ← call Graphiti โดยตรง
```

#### Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `synapse/services/__init__.py` | CREATE | Package init |
| `synapse/services/synapse_service.py` | CREATE | Main bridge class |
| `synapse/mcp_server/src/graphiti_mcp_server.py` | MODIFY | Use SynapseService |

#### Implementation Details

**Step 1: Create `synapse/services/__init__.py`**

```python
"""Synapse Services - Bridge between MCP and Layer System"""

from .synapse_service import SynapseService

__all__ = ["SynapseService"]
```

**Step 2: Create `synapse/services/synapse_service.py`**

```python
"""
SynapseService - Bridge between MCP Server and Layer System

This class provides a unified API for MCP tools to interact with
the 5-layer memory system while maintaining Graphiti compatibility.
"""

import logging
from typing import Any, Dict, List, Optional

from synapse.layers import LayerManager, MemoryLayer
from synapse.layers.types import SynapseNode, SynapseEdge

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
        self.layers = layer_manager or LayerManager(user_id=user_id)
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
        graphiti_result = await self.graphiti.add_episode(
            name=name,
            episode_body=episode_body,
            source_description=source_description,
            source_url=source_url,
            reference_time=reference_time,
            **kwargs,
        )

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
            return await self.layers.add_semantic_entity(
                name=name,
                entity_type="concept",
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
            return self.layers.set_working_context(name, content)

        else:
            logger.warning(f"Unknown layer: {layer}, defaulting to semantic")
            return await self.layers.add_semantic_entity(
                name=name,
                entity_type="concept",
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
        )

        # Search Graphiti
        try:
            graphiti_results = await self.graphiti.search(
                query=query,
                num_results=limit,
            )
        except Exception as e:
            logger.error(f"Graphiti search failed: {e}")
            graphiti_results = []

        return {
            "layers": {k.value: v for k, v in layer_results.items()},
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
        return await self.layers.add_semantic_entity(
            name=name,
            entity_type=entity_type,
            summary=summary,
            **kwargs,
        )

    async def get_entity(self, entity_id: str) -> Optional[SynapseNode]:
        """Get entity from semantic layer."""
        return await self.layers.get_semantic_entity(entity_id)

    async def search_entities(
        self,
        query: str,
        entity_types: Optional[List[str]] = None,
        limit: int = 10,
    ) -> List[SynapseNode]:
        """Search entities in semantic layer."""
        return await self.layers.search_semantic(
            query=query,
            entity_types=entity_types,
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
        return self.layers.find_episodes_by_topic(
            topic=reference or "",
            limit=last_n,
        )

    # ============================================
    # PROCEDURE OPERATIONS
    # ============================================

    def find_procedure(self, trigger: str, limit: int = 5) -> List[Dict]:
        """Find procedures matching trigger."""
        return self.layers.find_procedures(trigger, limit)

    # ============================================
    # USER MODEL OPERATIONS
    # ============================================

    def get_user_context(self) -> Dict[str, Any]:
        """Get current user context."""
        return self.layers.get_user_model(self.user_id)

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
            results["components"]["graphiti"] = "ok"
        except Exception as e:
            results["components"]["graphiti"] = f"error: {e}"
            results["status"] = "degraded"

        # Check LayerManager
        try:
            self.layers.get_user_model(self.user_id)
            results["components"]["layer_manager"] = "ok"
        except Exception as e:
            results["components"]["layer_manager"] = f"error: {e}"
            results["status"] = "degraded"

        return results
```

**Step 3: Modify `synapse/mcp_server/src/graphiti_mcp_server.py`**

เพิ่ม import และใช้ SynapseService:

```python
# Add import at top
from synapse.services import SynapseService

# Replace global clients
synapse_service: SynapseService | None = None

# Modify initialization
async def initialize_services():
    global synapse_service

    # Initialize Graphiti
    graphiti_client = await graphiti_service.get_client()

    # Initialize SynapseService
    synapse_service = SynapseService(
        graphiti_client=graphiti_client,
        user_id="default",  # TODO: Get from context
    )

# Modify MCP tools to use synapse_service
@mcp.tool()
async def add_memory(name: str, episode_body: str, source_description: str = ""):
    global synapse_service
    if synapse_service is None:
        return {"error": "Services not initialized"}

    return await synapse_service.add_memory(
        name=name,
        episode_body=episode_body,
        source_description=source_description,
    )
```

#### Acceptance Criteria

- [ ] SynapseService class created with all methods
- [ ] MCP tools use SynapseService instead of direct Graphiti calls
- [ ] Layer classification works (detect_layer called)
- [ ] Data stored in both LayerManager AND Graphiti
- [ ] All existing MCP tools still work

#### Test Cases

```python
# Test 1: Service initialization
service = SynapseService(graphiti_client=mock_graphiti)
assert service.layers is not None

# Test 2: Memory addition with classification
result = await service.add_memory(
    name="test",
    episode_body="วิธีทำข้าวผัด",
)
assert result["layer"] == "procedural"

# Test 3: Search across layers
results = await service.search_memory("ข้าวผัด")
assert "layers" in results
assert "graphiti" in results
```

---

### Task 1.2: Implement Semantic Layer FalkorDB Persistence

| Field | Value |
|-------|-------|
| **Priority** | P0 - Critical |
| **Est. Time** | 1 day |
| **Assignee** | เดฟ (Dev) |
| **Reviewer** | Mneme |
| **Dependencies** | Task 1.1 |

#### Problem

`semantic.py` มี 8 TODO comments — ทุก method สำคัญไม่ persist ไป FalkorDB

#### Files to Modify

| File | Action |
|------|--------|
| `synapse/layers/semantic.py` | MODIFY - Implement 8 TODOs |

#### TODOs to Implement

| Line | Method | Action |
|------|--------|--------|
| 229 | `add_entity()` | Persist to Graphiti |
| 278 | `add_fact()` | Persist to Graphiti |
| 364 | `get_entity()` | Return actual data (not None) |
| 388 | `supersede_fact()` | Update edge in Graphiti |
| 394 | `supersede_fact()` | Add new edge to Graphiti |
| 418 | `update_entity()` | Implement actual update |
| 482 | `get_related_entities()` | Implement graph traversal |
| 499 | `cleanup_forgotten()` | Implement cleanup logic |

#### Implementation Details

**Fix `add_entity()` (Line 229)**

```python
async def add_entity(
    self,
    name: str,
    entity_type: str,
    summary: Optional[str] = None,
    **kwargs,
) -> SynapseNode:
    """Add entity to semantic layer and persist to Graphiti."""
    # Create node
    node = SynapseNode(
        name=name,
        labels=[entity_type],
        summary=summary,
        created_at=datetime.now(),
        **kwargs,
    )

    # Index to Qdrant (existing)
    self._index_entity(node)

    # NEW: Persist to Graphiti
    await self._ensure_graphiti()
    try:
        # Use add_episode to let LLM extract entity
        episode_content = f"{name}: {summary or ''}"
        await self._graphiti.add_episode(
            name=f"entity_{name}",
            episode_body=episode_content,
            source_description=f"Entity type: {entity_type}",
        )
    except Exception as e:
        logger.warning(f"Failed to persist entity to Graphiti: {e}")

    return node
```

**Fix `get_entity()` (Line 364)**

```python
async def get_entity(self, entity_id: str) -> Optional[SynapseNode]:
    """Get entity from Graphiti by ID."""
    await self._ensure_graphiti()

    try:
        # Query Graphiti for node
        result = await self._graphiti.get_node(entity_id)
        if result:
            return SynapseNode(
                uuid=result.uuid,
                name=result.name,
                labels=result.labels,
                summary=result.summary,
                created_at=result.created_at,
            )
    except Exception as e:
        logger.error(f"Failed to get entity from Graphiti: {e}")

    return None
```

**Fix `get_related_entities()` (Line 482)**

```python
async def get_related_entities(
    self,
    entity_id: str,
    relation_types: Optional[List[str]] = None,
    depth: int = 1,
) -> List[SynapseNode]:
    """Get entities related to given entity via graph traversal."""
    await self._ensure_graphiti()

    try:
        # Build Cypher query for graph traversal
        # Note: FalkorDB uses Redis-compatible commands
        results = await self._graphiti.search(
            query=f"related to {entity_id}",
            num_results=10 * depth,
        )

        related = []
        for result in results:
            if result.uuid != entity_id:
                related.append(SynapseNode(
                    uuid=result.uuid,
                    name=result.name,
                    summary=result.summary,
                ))

        return related[:10 * depth]
    except Exception as e:
        logger.error(f"Graph traversal failed: {e}")
        return []
```

#### Acceptance Criteria

- [ ] `add_entity()` persists to both Qdrant AND Graphiti
- [ ] `get_entity()` returns actual data (not None)
- [ ] `get_related_entities()` returns related entities
- [ ] All 8 methods have working implementations
- [ ] No more TODO comments in semantic.py

#### Test Cases

```python
# Test 1: add_entity persists to both stores
entity = await manager.add_entity("Python", "language", "Programming language")
assert entity is not None

# Verify in Qdrant
qdrant_result = manager._search_vector("Python", limit=1)
assert len(qdrant_result) > 0

# Verify in Graphiti (may need async wait)
# graphiti_result = await graphiti.get_node(entity.uuid)

# Test 2: get_entity returns data
fetched = await manager.get_entity(entity.uuid)
assert fetched is not None
assert fetched.name == "Python"

# Test 3: get_related_entities returns list
related = await manager.get_related_entities(entity.uuid)
assert isinstance(related, list)
```

---

## Phase 1 Milestone

### M1: Phase 1 Complete

**Completion Criteria**:
- [ ] SynapseService bridge working
- [ ] MCP tools use SynapseService
- [ ] Semantic layer persists to FalkorDB
- [ ] All tests passing
- [ ] No P0 bugs remaining

**Verification Commands**:

```bash
# Start services
cd C:/Programing/PersonalAI/synapse
docker compose up -d

# Test MCP add_memory
curl -X POST http://localhost:47780/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "add_memory",
      "arguments": {
        "name": "test_entity",
        "episode_body": "Python เป็นภาษาโปรแกรมมิ่ง",
        "source_description": "test"
      }
    },
    "id": 1
  }'

# Verify in logs that layer classification happened
docker compose logs synapse-server | grep "classified as"
```

---

## Review Checklist (Mneme)

### Code Review

- [ ] SynapseService follows existing patterns
- [ ] Error handling is consistent
- [ ] Logging is appropriate
- [ ] Type hints are complete
- [ ] Docstrings are clear

### Integration Review

- [ ] MCP tools work with new service
- [ ] Graphiti client is properly injected
- [ ] LayerManager is properly initialized
- [ ] No circular dependencies

### Security Review

- [ ] User isolation is respected
- [ ] No hardcoded credentials
- [ ] Input validation is present

---

## Rollback Plan

If Phase 1 fails:

```bash
# 1. Revert code changes
git revert HEAD~N  # N = number of commits in Phase 1

# 2. Restart services
docker compose down
docker compose up -d

# 3. Verify old behavior
curl http://localhost:47780/health
```

---

*Phase 1 Plan created: 2026-03-16*
*Assignee: เดฟ (Dev) 🦀*
*Reviewer: Mneme 🧠*
