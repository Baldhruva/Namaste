from functools import lru_cache
from typing import List, Optional

from pydantic import AnyHttpUrl, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables.

    All secrets and sensitive configuration must be provided via environment variables
    to adhere to a zero-trust approach. No PHI is persisted by the service.
    """

    # App
    APP_NAME: str = Field(default="ICD11-TM2 EMR Plugin")
    ENV: str = Field(default="production")
    LOG_LEVEL: str = Field(default="INFO", description="Logging level: DEBUG/INFO/WARNING/ERROR")

    # CORS
    ALLOW_ORIGINS: List[str] = Field(
        default_factory=lambda: ["*"],
        description="Comma-separated origins allowed for CORS. Defaults to '*' for demo; restrict in prod.",
    )
    ALLOW_CREDENTIALS: bool = Field(default=False)
    ALLOW_METHODS: List[str] = Field(default_factory=lambda: ["*"])
    ALLOW_HEADERS: List[str] = Field(default_factory=lambda: ["*"])

    # Parse comma-separated origins from env if provided as string
    @field_validator("ALLOW_ORIGINS", mode="before")
    @classmethod
    def _split_origins(cls, v):
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v

    # MongoDB (Atlas)
    MONGODB_URI: str = Field(
        default="mongodb://localhost:27017",
        description="MongoDB connection string. Use SRV string for Atlas.",
    )
    MONGODB_DB_NAME: str = Field(default="emr_plugin")

    # Cache
    CACHE_TTL_SECONDS: int = Field(default=86400, ge=60, description="TTL for cached responses in seconds (>=60)")

    # WHO ICD API
    WHO_API_KEY: Optional[str] = Field(default=None, description="WHO ICD API key if required")
    WHO_MMS_SEARCH_URL: AnyHttpUrl = Field(
        default="https://id.who.int/icd/release/11/2024-01/mms/search",
        description="WHO ICD-11 MMS search endpoint",
    )
    WHO_TM2_SEARCH_URL: AnyHttpUrl = Field(
        default="https://id.who.int/icd/release/11/2024-01/tm2/search",
        description="WHO ICD-11 Traditional Medicine Module 2 search endpoint",
    )

    REQUEST_TIMEOUT_SECONDS: float = Field(default=8.0, ge=1.0, le=30.0)

    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='ignore',
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached settings instance to avoid re-parsing env multiple times."""
    return Settings()