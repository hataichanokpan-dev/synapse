"""
Configuration settings for Synapse API.

Environment variables (all optional with defaults):
    SYNAPSE_API_KEY: API key for authentication
    SYNAPSE_API_PORT: Server port (default 8000)
    CORS_ORIGINS: Comma-separated CORS origins
    DEBUG: Enable debug mode
"""

from typing import List, Optional, Union
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from functools import lru_cache


class Settings(BaseSettings):
    """API configuration settings."""

    # App
    app_name: str = "Synapse API"
    app_version: str = "1.0.0"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000

    # Auth
    api_key: str = "synapse-dev-key"
    api_key_header: str = "X-API-Key"

    # CORS - accept string or list, validator will convert
    cors_origins: Union[str, List[str]] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ]

    # Database paths (passed to SynapseService)
    falkordb_uri: str = "redis://localhost:6379"
    qdrant_url: str = "http://localhost:6333"
    sqlite_path: str = "~/.synapse/synapse.db"

    # LLM
    anthropic_api_key: Optional[str] = None

    # Feed
    feed_buffer_size: int = 500

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore extra env vars not defined here
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse CORS origins from comma-separated string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
