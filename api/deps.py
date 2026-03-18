"""
Dependency injection for Synapse API.
"""

import os
import sys
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, HTTPException, Request
from fastapi.security import APIKeyHeader

from api.config import settings

# Load .env from parent directory
env_file = Path(__file__).parent.parent / ".env"
if env_file.exists():
    load_dotenv(env_file)

# Add parent directory to path for imports
parent_dir = Path(__file__).parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))


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
_graphiti_client = None


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
    global _synapse_service, _event_bus, _graphiti_client

    # Initialize event bus first
    from api.services.event_bus import EventBus
    _event_bus = EventBus(buffer_size=settings.feed_buffer_size)
    print("[OK] EventBus initialized")

    # Try to initialize real services
    try:
        from graphiti_core import Graphiti
        from graphiti_core.driver.falkordb_driver import FalkorDriver
        from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
        from graphiti_core.llm_client.config import LLMConfig as GraphitiLLMConfig

        # Get configuration from environment
        falkor_host = os.getenv("FALKORDB_HOST", "localhost")
        falkor_port = int(os.getenv("FALKORDB_PORT", "6379"))
        falkor_password = os.getenv("FALKORDB_PASSWORD", "")
        falkor_database = os.getenv("FALKORDB_DATABASE", "user-bfipa")

        # LLM Configuration - use Anthropic via OpenAI-compatible endpoint (Z.ai)
        anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        anthropic_base_url = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com")

        if not anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")

        # Create FalkorDB driver
        print(f"[OK] Connecting to FalkorDB: {falkor_host}:{falkor_port}/{falkor_database}")
        driver = FalkorDriver(
            host=falkor_host,
            port=falkor_port,
            password=falkor_password if falkor_password else None,
        )

        # Create LLM config using OpenAI-compatible endpoint (Z.ai wrapper for Anthropic)
        llm_config = GraphitiLLMConfig(
            api_key=anthropic_api_key,
            base_url=anthropic_base_url,
            model="claude-sonnet-4-20250514",  # Default model
        )

        # Create LLM client using OpenAI-compatible client (for Z.ai)
        from graphiti_core.llm_client.openai_generic_client import OpenAIGenericClient
        llm_client = OpenAIGenericClient(config=llm_config, max_tokens=4096)
        print(f"[OK] LLM Client created: {anthropic_base_url}")

        # Create embedder - use local or OpenAI
        embedder_provider = os.getenv("EMBEDDER_PROVIDER", "openai")

        if embedder_provider == "local":
            # Use local embedder (no API key needed)
            from synapse.graphiti.embedder.local import LocalEmbedder, LocalEmbedderConfig
            embedder = LocalEmbedder(config=LocalEmbedderConfig(
                embedding_dim=384,
                model_name="intfloat/multilingual-e5-small",
            ))
            print("[OK] Using Local Embedder (sentence-transformers)")
        else:
            # Use OpenAI embedder (requires API key)
            openai_api_key = os.getenv("OPENAI_API_KEY")
            if not openai_api_key:
                # Try to use Anthropic endpoint with OpenAI embedder (might not work)
                print("[WARN] OPENAI_API_KEY not set, using Anthropic key (may fail)")
                openai_api_key = anthropic_api_key

            embedder = OpenAIEmbedder(config=OpenAIEmbedderConfig(
                api_key=openai_api_key,
                embedding_model="text-embedding-3-small",
                embedding_dim=1536,
            ))
            print("[OK] Using OpenAI Embedder")

        # Create Graphiti client
        # Note: cross_encoder defaults to OpenAI if not provided, so we use mock
        from synapse.graphiti.cross_encoder import MockCrossEncoderClient
        cross_encoder = MockCrossEncoderClient()
        print("[OK] Using Mock Cross Encoder (no API key needed)")

        _graphiti_client = Graphiti(
            graph_driver=driver,
            llm_client=llm_client,
            embedder=embedder,
            cross_encoder=cross_encoder,
        )

        # Initialize SynapseService
        from synapse.services import SynapseService
        _synapse_service = SynapseService(
            graphiti_client=_graphiti_client,
            user_id=os.getenv("USER_ID", "cerberus"),
        )
        print(f"[OK] SynapseService initialized (user: {_synapse_service.user_id})")

    except Exception as e:
        import traceback
        print(f"[DEV] Real services not available: {e}")
        traceback.print_exc()
        print("      Using mock service for development")
        _synapse_service = MockSynapseService()


async def shutdown_services():
    """Cleanup services at shutdown."""
    global _synapse_service, _event_bus, _graphiti_client

    # Close Graphiti client if it exists
    if _graphiti_client is not None:
        try:
            await _graphiti_client.close()
            print("[OK] Graphiti client closed")
        except Exception as e:
            print(f"[WARN] Error closing Graphiti client: {e}")

    _synapse_service = None
    _event_bus = None
    _graphiti_client = None
    print("[OK] Services shut down")


# Mock service for development
class MockSynapseService:
    """Mock SynapseService for development."""

    # Identity methods (sync, not async)
    def get_identity(self):
        return {"user_id": "dev", "agent_id": None, "chat_id": None}

    def set_identity(self, **kwargs):
        return {"user_id": kwargs.get("user_id", "dev"), "agent_id": kwargs.get("agent_id"), "chat_id": kwargs.get("chat_id")}

    def clear_identity(self):
        return {"user_id": "dev", "agent_id": None, "chat_id": None}

    def get_user_context(self):
        return {
            "user_id": "dev",
            "language": "en",
            "timezone": "UTC",
            "response_style": "balanced",
            "expertise": [],
            "common_topics": [],
            "notes": "",
        }

    def update_user_preferences(self, **kwargs):
        result = self.get_user_context()
        result.update(kwargs)
        return result

    # Memory methods (async)
    async def add_memory(self, **kwargs):
        return {"uuid": "mock-uuid", "layer": "EPISODIC"}

    async def search_memory(self, query, **kwargs):
        return {"layers": {}, "graphiti": []}

    async def list_memories(self, layer=None, limit=20, offset=0, sort="created_at", order="desc"):
        return {"items": [], "total": 0}

    async def get_memory_by_id(self, memory_id):
        return None

    async def update_memory(self, memory_id, content=None, metadata=None):
        return {"uuid": memory_id}

    async def delete_memory(self, memory_id):
        return {"message": f"Memory {memory_id} deleted (mock)"}

    async def consolidate(self, **kwargs):
        return {"promoted": [], "skipped": [], "errors": []}

    # Procedure methods (async)
    async def add_procedure(self, **kwargs):
        return {"uuid": "mock-proc", "trigger": kwargs.get("trigger")}

    async def list_procedures(self, trigger=None, topic=None, limit=20, offset=0):
        return {"items": [], "total": 0}

    async def get_procedure_by_id(self, procedure_id):
        return None

    async def update_procedure(self, procedure_id, **kwargs):
        return {"uuid": procedure_id}

    async def delete_procedure(self, procedure_id):
        return {"message": f"Procedure {procedure_id} deleted (mock)"}

    async def record_procedure_success(self, trigger):
        return {"success_count": 1}

    # Graph methods (async)
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

    # Episodes methods (async)
    async def get_episodes(self, group_id=None, limit=20, offset=0, sort="created_at", order="desc"):
        return {"episodes": [], "total": 0}

    async def get_episode_by_id(self, episode_id):
        return None

    async def delete_episode(self, episode_id):
        return {"message": f"Episode {episode_id} deleted (mock)"}

    # Feed methods (async)
    async def get_feed_events(self, layer=None, limit=50, since=None):
        return {"events": []}

    # System methods (async)
    async def get_status(self):
        return {"status": "ok", "message": "Mock mode", "components": {"synapse": "ok"}}

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

    async def run_maintenance(self, action, dry_run=False):
        return {"affected": 0, "message": f"Maintenance {action} completed (mock)"}

    async def clear_graph(self, confirm=False, group_ids=None):
        return {"status": "ok", "message": "Mock clear"}

    # Oracle methods (async)
    async def consult(self, query, **kwargs):
        return {"query": query, "layers": {}, "summary": [], "suggestions": []}

    async def reflect(self, layer=None):
        return {"insights": [], "source_layer": layer or "all"}

    async def analyze_patterns(self, **kwargs):
        return {"patterns": {}}
