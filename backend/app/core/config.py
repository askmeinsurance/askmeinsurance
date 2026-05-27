from pathlib import Path
from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE_PATH = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE_PATH),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = Field(default="askmeinsurance-backend")
    app_env: Literal["local", "dev", "staging", "prod"] = Field(default="local")
    app_debug: bool = Field(default=False)
    cors_allowed_origins: str = Field(default="http://localhost:5173,http://127.0.0.1:5173")

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

    # Vector store
    qdrant_url: str | None = Field(default=None)
    qdrant_api_key: str | None = Field(default=None)

    # Embeddings
    embedding_model: str = Field(default="models/text-embedding-004")
    embedding_dimension: int = Field(default=768)

    # Retrieval tuning
    textbook_top_k: int = Field(default=5)
    product_summary_top_k: int = Field(default=5)
    textbook_score_threshold: float = Field(default=0.0)
    product_summary_score_threshold: float = Field(default=0.0)

    # Observability
    langfuse_public_key: str | None = Field(default=None)
    langfuse_secret_key: str | None = Field(default=None)
    langfuse_host: str | None = Field(default=None)
    langgraph_log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")
    langgraph_log_state_excerpt_chars: int = Field(default=240)
    langgraph_log_include_payloads: bool = Field(default=False)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
