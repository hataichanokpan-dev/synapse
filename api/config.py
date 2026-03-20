"""
Configuration settings for Synapse API.

Environment variables (all optional with defaults):
    SYNAPSE_API_KEY: API key for authentication
    SYNAPSE_API_PORT: Server port (default 8000)
    CORS_ORIGINS: Comma-separated CORS origins
    DEBUG: Enable debug mode
"""

from functools import lru_cache
from typing import List, Optional, Union

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_TRUTHY_DEBUG = {"1", "true", "yes", "on", "dev", "development"}
_FALSY_DEBUG = {"0", "false", "no", "off", "prod", "production", "release"}


class Settings(BaseSettings):
    """API configuration settings."""

    # App
    app_name: str = Field(default="Synapse API", validation_alias=AliasChoices("APP_NAME", "app_name"))
    app_version: str = Field(default="1.0.0", validation_alias=AliasChoices("APP_VERSION", "app_version"))
    debug: bool = Field(default=False, validation_alias=AliasChoices("DEBUG", "debug"))
    host: str = Field(default="0.0.0.0", validation_alias=AliasChoices("SYNAPSE_API_HOST", "HOST", "host"))
    port: int = Field(default=8000, validation_alias=AliasChoices("SYNAPSE_API_PORT", "PORT", "port"))

    # Auth
    api_key: str = Field(
        default="synapse-dev-key",
        validation_alias=AliasChoices("SYNAPSE_API_KEY", "API_KEY", "api_key"),
    )
    api_key_header: str = Field(
        default="X-API-Key",
        validation_alias=AliasChoices("SYNAPSE_API_KEY_HEADER", "API_KEY_HEADER", "api_key_header"),
    )

    # CORS - accept string or list, validator will convert
    cors_origins: Union[str, List[str]] = Field(default=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ], validation_alias=AliasChoices("CORS_ORIGINS", "cors_origins"))

    # Database paths (passed to SynapseService)
    falkordb_uri: str = Field(
        default="redis://localhost:6379",
        validation_alias=AliasChoices("FALKORDB_URI", "falkordb_uri"),
    )
    qdrant_url: str = Field(
        default="http://localhost:6333",
        validation_alias=AliasChoices("QDRANT_URL", "qdrant_url"),
    )
    sqlite_path: str = Field(
        default="~/.synapse/synapse.db",
        validation_alias=AliasChoices("SQLITE_PATH", "sqlite_path"),
    )

    # LLM
    anthropic_api_key: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("ANTHROPIC_API_KEY", "anthropic_api_key"),
    )

    # Feed
    feed_buffer_size: int = Field(
        default=500,
        validation_alias=AliasChoices("SYNAPSE_FEED_BUFFER_SIZE", "FEED_BUFFER_SIZE", "feed_buffer_size"),
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore extra env vars not defined here
        populate_by_name=True,
    )

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug(cls, value):
        """Accept common deployment aliases for DEBUG."""
        if value is None or isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in _TRUTHY_DEBUG:
                return True
            if normalized in _FALSY_DEBUG:
                return False
        raise ValueError(
            "DEBUG must be a boolean or one of: true/false, 1/0, on/off, dev/development, prod/production/release"
        )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse CORS origins from comma-separated string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    def validate_startup(self) -> None:
        """Run lightweight startup validation with clear errors."""
        if not self.api_key_header.strip():
            raise ValueError("SYNAPSE_API_KEY_HEADER/API_KEY_HEADER must not be empty")
        if not (1 <= self.port <= 65535):
            raise ValueError(f"SYNAPSE_API_PORT must be between 1 and 65535, got {self.port}")
        if not isinstance(self.cors_origins, list):
            raise ValueError("CORS_ORIGINS must resolve to a list of origins")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    try:
        settings = Settings()
        settings.validate_startup()
        return settings
    except Exception as exc:
        raise RuntimeError(f"Failed to load Synapse API settings: {exc}") from exc


settings = get_settings()
