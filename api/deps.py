"""
Dependency injection for Synapse API.
"""

from typing import Optional
from fastapi import Depends, HTTPException, Request
from fastapi.security import APIKeyHeader

from api.config import settings


# API Key header
api_key_header = APIKeyHeader(name=settings.api_key_header, auto_error=False)


async def verify_api_key(
    request: Request,
    api_key: Optional[str] = Depends(api_key_header)
) -> str:
    """Verify API key from header."""
    if settings.api_key and settings.api_key != "synapse-dev-key":
        if not api_key or api_key != settings.api_key:
            raise HTTPException(
                status_code=401,
                detail="Invalid or missing API key",
                headers={settings.api_key_header: "Required"},
            )
    return api_key or "anonymous"


# Service singletons
_synapse_service = None
_event_bus = None


def get_synapse_service():
    """Get SynapseService instance."""
    if _synapse_service is None:
        raise RuntimeError("Services not initialized")
    return _synapse_service


def get_event_bus():
    """Get EventBus instance."""
    return _event_bus


async def init_services():
    """Initialize all services at startup."""
    global _synapse_service, _event_bus

    # Try to import SynapseService from parent package
    import sys
    from pathlib import Path
    parent_dir = Path(__file__).parent.parent
    if str(parent_dir) not in sys.path:
        sys.path.insert(0, str(parent_dir))

    try:
        from synapse.services import SynapseService
        _synapse_service = SynapseService()
        print("[OK] SynapseService initialized (real)")
    except (ImportError, TypeError) as e:
        print(f"[DEV] SynapseService not available: {e}")
        print("      Using mock service for development")
        _synapse_service = MockSynapseService()

    # Initialize event bus
    from api.services.event_bus import EventBus
    _event_bus = EventBus(buffer_size=settings.feed_buffer_size)
    print("[OK] EventBus initialized")


async def shutdown_services():
    """Cleanup services at shutdown."""
    global _synapse_service, _event_bus
    _synapse_service = None
    _event_bus = None
    print("[OK] Services shut down")


# Mock service for development
class MockSynapseService:
    """Mock SynapseService for development."""

    async def get_identity(self):
        return {"user_id": "dev", "agent_id": None, "chat_id": None}

    async def set_identity(self, **kwargs):
        return kwargs

    async def clear_identity(self):
        return {"previous": {}, "current": {}}

    async def get_user_preferences(self, user_id=None):
        return {
            "language": "en",
            "timezone": "UTC",
            "response_style": "balanced",
            "expertise": [],
            "topics": [],
            "notes": "",
            "custom": {},
        }

    async def update_user_preferences(self, **kwargs):
        return kwargs

    async def add_memory(self, **kwargs):
        return {"uuid": "mock-uuid", "layer": kwargs.get("layer", "EPISODIC")}

    async def search_memory_layers(self, query, **kwargs):
        return {"results": [], "total": 0, "query": query}

    async def consolidate(self, **kwargs):
        return {"promoted": [], "skipped": [], "errors": []}

    async def add_procedure(self, **kwargs):
        return {"uuid": "mock-proc", "trigger": kwargs.get("trigger")}

    async def find_procedures(self, trigger=None):
        return []

    async def record_procedure_success(self, trigger):
        return {"success_count": 1}

    async def get_status(self):
        return {"status": "ok", "message": "Mock mode"}

    async def clear_graph(self, confirm=False, group_ids=None):
        return {"status": "ok", "message": "Mock clear"}

    async def consult(self, query, **kwargs):
        return {"query": query, "layers": {}, "summary": ["Mock consult"]}

    async def reflect(self, layer=None):
        return {"insights": [], "source_layer": layer or "all"}

    async def analyze_patterns(self, **kwargs):
        return {"patterns": {}}

    # Graph methods
    async def search_nodes(self, query, limit=50):
        return {"nodes": []}

    async def get_node_by_id(self, node_id):
        return None

    async def get_node_edges(self, node_id, direction="both", edge_type=None, limit=50):
        return {"edges": []}

    async def list_edges(self, edge_type=None, limit=50, offset=0):
        return {"edges": [], "total": 0}

    async def get_entity_edge(self, edge_id):
        return None

    async def delete_node(self, node_id):
        return {"message": f"Node {node_id} deleted (mock)"}

    async def delete_entity_edge(self, edge_id):
        return {"message": f"Edge {edge_id} deleted (mock)"}

    # Episodes methods
    async def get_episodes(self, group_id=None, limit=20, offset=0):
        return {"episodes": [], "total": 0}

    async def get_episode_by_id(self, episode_id):
        return None

    async def delete_episode(self, episode_id):
        return {"message": f"Episode {episode_id} deleted (mock)"}

    # Procedures methods (extended)
    async def get_procedure_by_id(self, procedure_id):
        return None

    async def update_procedure(self, procedure_id, **kwargs):
        return {"uuid": procedure_id}

    async def delete_procedure(self, procedure_id):
        return {"message": f"Procedure {procedure_id} deleted (mock)"}

    # Feed methods
    async def get_feed_events(self, layer=None, limit=50, since=None):
        return {"events": []}

    # System methods (extended)
    async def get_system_stats(self):
        return {
            "entities": 0,
            "edges": 0,
            "episodes": 0,
            "procedures": 0,
            "episodic_items": 0,
            "working_keys": 0,
            "storage": {},
        }

    async def run_maintenance(self, action):
        return {"affected": 0, "message": f"Maintenance {action} completed (mock)"}

    # Memory methods (extended)
    async def list_memories(self, layer=None, limit=20, offset=0, sort="created_at", order="desc"):
        return {"items": [], "total": 0}

    async def get_memory_by_id(self, memory_id):
        return None

    async def update_memory(self, memory_id, content=None, metadata=None):
        return {"uuid": memory_id}

    async def delete_memory(self, memory_id):
        return {"message": f"Memory {memory_id} deleted (mock)"}
