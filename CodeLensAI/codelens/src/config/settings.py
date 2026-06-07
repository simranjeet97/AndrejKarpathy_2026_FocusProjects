from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    Configuration settings for CodeLens AI.
    """
    GITHUB_TOKEN: str = ""
    """GitHub API personal access token."""

    GITHUB_WEBHOOK_SECRET: str = ""
    """GitHub webhook secret for payload validation."""

    OLLAMA_BASE_URL: str = "http://localhost:11434"
    """Base URL for the Ollama server."""

    OLLAMA_MODEL_CODE: str = "codellama"
    """Model name for code generation/analysis."""

    OLLAMA_MODEL_REASON: str = "deepseek-coder"
    """Model name for reasoning tasks."""

    OLLAMA_EMBED_MODEL: str = "nomic-embed-text"
    """Model name for generating embeddings."""

    CHROMA_PATH: str = "data/chroma"
    """Path to the Chroma vector database."""

    SQLITE_PATH: str = "data/sqlite/codelens.db"
    """Path to the SQLite database."""

    EXCEL_PATH: str = "data/excel"
    """Path to the Excel outputs/templates."""

    DRAGONFLY_URL: str = "redis://localhost:6379/0"
    """Redis-compatible Dragonfly connection URL."""

    MAX_CONTEXT_TOKENS: int = 4096
    """Maximum allowed token count for LLM context."""

    LOG_LEVEL: str = "INFO"
    """Logging level configuration (e.g., DEBUG, INFO, WARNING)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

@lru_cache
def get_settings() -> Settings:
    """
    Get the cached Settings instance.
    """
    return Settings()

