from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = Field(default="askmeinsurance-backend")
    app_env: Literal["local", "dev", "staging", "prod"] = Field(default="local")
    app_debug: bool = Field(default=False)

    # Auth
    auth_enabled: bool = Field(default=True)
    jwt_algorithm: str = Field(default="RS256")
    jwt_audience: str | None = Field(default=None)
    jwt_issuer: str | None = Field(default=None)
    jwt_public_key: str | None = Field(default=None)

    # Supabase
    supabase_url: str | None = Field(default=None)
    supabase_anon_key: str | None = Field(default=None)
    supabase_service_role_key: str | None = Field(default=None)
    supabase_jwt_secret: str | None = Field(default=None)

    # LLM providers
    llm_provider: Literal["openai", "gemini", "openrouter", "mock"] = Field(default="mock")
    openai_api_key: str | None = Field(default=None)
    gemini_api_key: str | None = Field(default=None)
    gemini_model: str = Field(default="gemini-2.0-flash-lite")
    openrouter_api_key: str | None = Field(default=None)

    # Observability
    langfuse_public_key: str | None = Field(default=None)
    langfuse_secret_key: str | None = Field(default=None)
    langfuse_host: str | None = Field(default=None)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
