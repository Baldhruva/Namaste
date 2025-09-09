"""
Application configuration using Pydantic Settings.

This module defines the Settings object used across the service to configure:
- App metadata and environment
- CORS configuration
- MongoDB Atlas connectivity and index TTLs
- OpenMRS REST API credentials and timeouts
- Ingestion behavior and file paths
- Logging levels and privacy options

Values are read from environment variables with sensible defaults for development.
Use a .env file in development; in production, set environment variables via the platform's secret management.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class OpenMRSSettings(BaseSettings):
    base_url: str | None = None
    username: str | None = None
    password: str | None = None
    timeout_seconds: int = 10
    max_retries: int = 3
    backoff_base: float = 0.5
    backoff_max: float = 8.0
    create_patients: bool = False


class IngestionSettings(BaseSettings):
    mappings_path: str = "tm2_mappings.json"
    data_path: str = "data"
    batch_size: int = 100
    default_format: Literal["csv", "ndjson", "json"] = "csv"
    id_hash_salt: str = "dev-salt"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App metadata
    APP_NAME: str = Field("tm2-ingestion-service")
    ENV: Literal["dev", "test", "staging", "prod"] = Field("dev")
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field("INFO")

    # MongoDB connection string (SRV URI for Atlas)
    MONGO_URI: str | None = Field(None, env="MONGO_URI")
    MONGO_DATABASE: str = Field("tm2_ingestion", env="MONGO_DATABASE")

    # OpenMRS REST API credentials and timeouts
    openmrs: OpenMRSSettings = OpenMRSSettings()

    # Ingestion behavior and file paths
    ingestion: IngestionSettings = IngestionSettings()

    # Observability
    ENABLE_ACCESS_LOG: bool = Field(True)

    @property
    def is_prod(self) -> bool:
        return self.ENV == "prod"

    @property
    def is_dev(self) -> bool:
        return self.ENV == "dev"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached Settings instance.

    Use lru_cache to avoid re-parsing environment variables. Tests may clear the cache if needed.
    """
    settings = Settings()  # type: ignore[arg-type]

    # Normalize and ensure paths exist for data/mappings in dev/test; in prod we allow missing until runtime
    if settings.is_dev or settings.ENV == "test":
        # Create the data directory if it points to a directory path
        try:
            if (Path("./data").suffix == "" or Path("./data").is_dir()):
                Path("./data").mkdir(parents=True, exist_ok=True)
        except Exception:
            # Do not fail settings loading; the ingestion service will validate paths at runtime
            pass

    return settings
