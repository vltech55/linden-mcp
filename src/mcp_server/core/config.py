from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    openai_api_key: str = Field(default="")
    openai_embedding_model: str = Field(default="text-embedding-3-small")
    embedding_dim: int = Field(default=1536)

    database_url: str = Field(default="postgresql+asyncpg://postgres:postgres@postgres:5432/mcp")
    readonly_user: str = Field(default="mcp_readonly")
    readonly_password: str = Field(default="mcp_readonly")
    readonly_database_url: str = Field(
        default="postgresql+asyncpg://mcp_readonly:mcp_readonly@postgres:5432/mcp"
    )

    sql_statement_timeout_ms: int = Field(default=5000, ge=100, le=60_000)
    sql_max_rows: int = Field(default=500, ge=1, le=10_000)
    sql_max_query_len: int = Field(default=4000, ge=100, le=100_000)

    http_host: str = Field(default="0.0.0.0")
    http_port: int = Field(default=8765)
    mcp_api_keys: str = Field(default="")

    rate_limit_tokens: int = Field(default=60, ge=1)
    rate_limit_refill_per_sec: float = Field(default=1.0, gt=0)

    log_level: str = Field(default="INFO")

    @property
    def api_key_set(self) -> set[str]:
        return {k.strip() for k in self.mcp_api_keys.split(",") if k.strip()}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
