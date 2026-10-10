import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_name: str = "SentinelOps"
    port: int = 8007
    database_url: str = "sentinelops.db"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"
    timeout_seconds: float = 30.0

    class Config:
        env_prefix = "SENTINEL_"

settings = Settings()
