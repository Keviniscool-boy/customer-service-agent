from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    model_name: str = "gpt-4o-mini"
    temperature: float = 0.7
    jwt_secret: str = ""
    mcp_server_url: str = "http://127.0.0.1:9123/mcp"
    weknora_base_url: str = "http://127.0.0.1:8080"
    weknora_api_key: str = ""
    weknora_timeout_seconds: float = 10.0
    weknora_embedding_model_id: str = ""
    knowledge_provider: Literal["local", "weknora"] = "weknora"
    weknora_knowledge_base_id: str = ""
    redis_url: str = "redis://127.0.0.1:6379/0"
    redis_timeout_seconds: float = 1.0
    database_backend: Literal["sqlite", "postgres"] = "postgres"
    postgres_dsn: str = ""
    database_path: str = "data/app.db"
    cors_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:8088,http://127.0.0.1:8088"
    )
    embedding_model: str = "text-embedding-3-small"
    registration_rate_limit: int = Field(default=60, ge=0)
    registration_rate_window_seconds: int = Field(default=60, ge=1)
    chat_rate_limit: int = Field(default=60, ge=0)
    chat_rate_window_seconds: int = Field(default=60, ge=1)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
