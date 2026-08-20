from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    model_name: str = "gpt-4o-mini"
    temperature: float = 0.7
    jwt_secret: str = ""
    mcp_server_url: str = "http://127.0.0.1:9123/mcp"
    database_path: str = "data/app.db"
    cors_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:8080,http://127.0.0.1:8080"
    )

    model_config = {"env_file": ".env"}
    embedding_model: str = "text-embedding-3-small"


settings = Settings()
