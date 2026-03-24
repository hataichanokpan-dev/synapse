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
    resolved_api_key = api_key or request.query_params.get("api_key")
    if settings.api_key and settings.api_key != "synapse-dev-key":
        if not resolved_api_key or resolved_api_key != settings.api_key:
            raise HTTPException(
                status_code=401,
                detail="Invalid or missing API key",
                headers={settings.api_key_header: "Required"},
            )
    return resolved_api_key or "anonymous"


# Service singletons
_synapse_service = None
_event_bus = None
_graphiti_client = None

_TRUTHY = {"1", "true", "yes", "on"}


def _env_flag(name: str, default: bool) -> bool:
    """Parse a boolean-ish environment variable."""
    value = os.getenv(name)
    if value is None:
        return default
    return str(value).strip().lower() in _TRUTHY


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

    # Initialize SynapseService with LayerManager (SQLite-backed)
    # This always works - no external dependencies
    from synapse.services import SynapseService
    from synapse.layers import LayerManager

    layer_manager = LayerManager()
    print("[OK] LayerManager initialized (SQLite-backed)")

    # Try to initialize Graphiti for knowledge graph (optional)
    _graphiti_client = None
    require_graphiti = _env_flag("SYNAPSE_REQUIRE_GRAPHITI", False)
    enable_graphiti = _env_flag("SYNAPSE_ENABLE_GRAPHITI", True)
    anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")

    graphiti_skip_reason = None
    if not enable_graphiti:
        graphiti_skip_reason = "SYNAPSE_ENABLE_GRAPHITI=false"
    elif not anthropic_api_key:
        graphiti_skip_reason = "ANTHROPIC_API_KEY not set"

    if graphiti_skip_reason:
        message = f"Graphiti startup skipped: {graphiti_skip_reason}"
        if require_graphiti:
            raise RuntimeError(message)
        print(f"[INFO] {message}")
    else:
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
            anthropic_base_url = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com")

            # Create FalkorDB driver
            print(f"[OK] Connecting to FalkorDB: {falkor_host}:{falkor_port}/{falkor_database}")
            driver = FalkorDriver(
                host=falkor_host,
                port=falkor_port,
                password=falkor_password if falkor_password else None,
                database=falkor_database,
            )

            # Create LLM config using OpenAI-compatible endpoint (Z.ai wrapper for Anthropic)
            llm_config = GraphitiLLMConfig(
                api_key=anthropic_api_key,
                base_url=anthropic_base_url,
                model="claude-sonnet-4-20250514",
            )

            from synapse.graphiti.llm_client.zai_client import ZaiClient
            llm_client = ZaiClient(config=llm_config, max_tokens=4096)
            print(f"[OK] LLM Client created (ZaiClient): {anthropic_base_url}")

            embedder_provider = os.getenv("EMBEDDER_PROVIDER", "openai")

            if embedder_provider == "local":
                from synapse.graphiti.embedder.local import LocalEmbedder, LocalEmbedderConfig
                embedder = LocalEmbedder(config=LocalEmbedderConfig(
                    embedding_dim=384,
                    model_name="intfloat/multilingual-e5-small",
                ))
                print("[OK] Using Local Embedder (sentence-transformers)")
            else:
                openai_api_key = os.getenv("OPENAI_API_KEY")
                if not openai_api_key:
                    print("[WARN] OPENAI_API_KEY not set, using Anthropic key (may fail)")
                    openai_api_key = anthropic_api_key

                embedder = OpenAIEmbedder(config=OpenAIEmbedderConfig(
                    api_key=openai_api_key,
                    embedding_model="text-embedding-3-small",
                    embedding_dim=1536,
                ))
                print("[OK] Using OpenAI Embedder")

            from synapse.graphiti.cross_encoder import MockCrossEncoderClient
            cross_encoder = MockCrossEncoderClient()
            print("[OK] Using Mock Cross Encoder (no API key needed)")

            _graphiti_client = Graphiti(
                graph_driver=driver,
                llm_client=llm_client,
                embedder=embedder,
                cross_encoder=cross_encoder,
            )
            print("[OK] Graphiti client initialized (FalkorDB connected)")

        except Exception as e:
            print(f"[INFO] Graphiti not available: {e}")
            print("      Knowledge graph features will return empty data")
            _graphiti_client = None

    # Always initialize SynapseService with real LayerManager
    _synapse_service = SynapseService(
        graphiti_client=_graphiti_client,
        layer_manager=layer_manager,
        user_id=os.getenv("USER_ID", "cerberus"),
    )
    if hasattr(_synapse_service, "set_event_bus"):
        _synapse_service.set_event_bus(_event_bus)
    semantic_manager = getattr(_synapse_service.layers, "semantic", None)
    if semantic_manager is not None and hasattr(semantic_manager, "start_background_processing"):
        semantic_manager.start_background_processing()
    print(f"[OK] SynapseService initialized (user: {_synapse_service.user_id}, graphiti: {'yes' if _graphiti_client else 'no'})")


async def shutdown_services():
    """Cleanup services at shutdown."""
    global _synapse_service, _event_bus, _graphiti_client

    # Close Graphiti client if it exists
    if _synapse_service is not None:
        semantic_manager = getattr(_synapse_service.layers, "semantic", None)
        if semantic_manager is not None and hasattr(semantic_manager, "stop_background_processing"):
            semantic_manager.stop_background_processing()

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
