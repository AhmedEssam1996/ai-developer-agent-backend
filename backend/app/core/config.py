"""Application configuration, loaded from environment variables.

All secrets are read from the environment; nothing is hardcoded. The frontend
never receives these values — only the backend imports this module.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed application settings."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Core -----------------------------------------------------------------
    app_name: str = "MyWork AI"
    environment: Literal["development", "staging", "production", "test"] = "development"
    log_level: str = "INFO"
    secret_key: str = "change-me-to-a-long-random-string"
    token_encryption_key: str | None = None

    # --- URLs -----------------------------------------------------------------
    backend_base_url: str = "http://localhost:8000"
    frontend_base_url: str = "http://localhost:3000"
    cors_origins: str = "http://localhost:3000"

    # --- Database / cache -----------------------------------------------------
    database_url: str = "postgresql+asyncpg://mywork:mywork@localhost:5432/mywork"
    redis_url: str = "redis://localhost:6379/0"

    # --- AI gateway -----------------------------------------------------------
    ai_provider: str = "openrouter"
    openrouter_api_key: str | None = None
    openrouter_model: str = "openai/gpt-4o-mini"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    ai_request_timeout_seconds: int = 60
    ai_max_retries: int = 2

    # --- Microsoft Graph ------------------------------------------------------
    microsoft_client_id: str | None = None
    microsoft_client_secret: str | None = None
    microsoft_tenant_id: str = "common"
    microsoft_redirect_uri: str = (
        "http://localhost:8000/api/integrations/microsoft/callback"
    )

    # --- GoodDay --------------------------------------------------------------
    goodday_base_url: str = "https://api.goodday.work/1.0"
    goodday_api_key: str | None = None

    # --- Integration behaviour ------------------------------------------------
    integration_mode: Literal["live", "mock"] = "mock"
    sync_enabled: bool = True
    sync_interval_seconds: int = 120

    # --- Security -------------------------------------------------------------
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 14
    rate_limit_per_minute: int = 120

    algorithm: str = "HS256"

    @field_validator("cors_origins")
    @classmethod
    def _strip_origins(cls, value: str) -> str:
        return value.strip()

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def is_test(self) -> bool:
        return self.environment == "test"

    @property
    def microsoft_configured(self) -> bool:
        return bool(self.microsoft_client_id and self.microsoft_client_secret)

    @property
    def goodday_configured(self) -> bool:
        return bool(self.goodday_api_key)

    @property
    def openrouter_configured(self) -> bool:
        return bool(self.openrouter_api_key)

    def microsoft_authority(self) -> str:
        return f"https://login.microsoftonline.com/{self.microsoft_tenant_id}"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()