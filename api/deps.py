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

    # Initialize SynapseService with LayerManager (SQLite-backed)
    # This always works - no external dependencies
    from synapse.services import SynapseService
    from synapse.layers import LayerManager

    layer_manager = LayerManager()
    print("[OK] LayerManager initialized (SQLite-backed)")

    # Try to initialize Graphiti for knowledge graph (optional)
    _graphiti_client = None
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
            database=falkor_database,  # Pass the database name!
        )

        # Create LLM config using OpenAI-compatible endpoint (Z.ai wrapper for Anthropic)
        llm_config = GraphitiLLMConfig(
            api_key=anthropic_api_key,
            base_url=anthropic_base_url,
            model="claude-sonnet-4-20250514",  # Default model (Z.ai maps to GLM-4.7)
        )

        # Create LLM client using custom ZaiClient (Anthropic format)
        from synapse.graphiti.llm_client.zai_client import ZaiClient
        llm_client = ZaiClient(config=llm_config, max_tokens=4096)
        print(f"[OK] LLM Client created (ZaiClient): {anthropic_base_url}")

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
        print("[OK] Graphiti client initialized (FalkorDB connected)")

    except Exception as e:
        import traceback
        print(f"[INFO] Graphiti not available: {e}")
        print("      Knowledge graph features will return empty data")
        _graphiti_client = None

    # Always initialize SynapseService with real LayerManager
    _synapse_service = SynapseService(
        graphiti_client=_graphiti_client,
        layer_manager=layer_manager,
        user_id=os.getenv("USER_ID", "cerberus"),
    )
    print(f"[OK] SynapseService initialized (user: {_synapse_service.user_id}, graphiti: {'yes' if _graphiti_client else 'no'})")


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
