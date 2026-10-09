from pathlib import Path
from typing import List
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # LLM Settings
    anthropic_api_key: SecretStr
    primary_model: str = "claude-sonnet-4-6"

    # GitHub App Integration
    github_app_id: int
    github_app_private_key_path: Path
    github_webhook_secret: SecretStr

    # Databases and Queues
    database_url: SecretStr
    redis_url: str

    # Sandbox Orchestration / Container Settings
    sandbox_image: str
    max_sandbox_cpu: float = 0.5
    max_sandbox_memory_mb: int = 512
    sandbox_timeout_seconds: int = 120

    # Agent Constraints
    max_agent_iterations: int = 8
    allowed_file_extensions: List[str] = [
        ".py",
        ".md",
        ".txt",
        ".json",
        ".yaml",
        ".toml",
    ]
    require_human_approval_for_patterns: List[str] = [
        "**/migrations/**",
        "**/secrets/**",
    ]


settings = Settings()
