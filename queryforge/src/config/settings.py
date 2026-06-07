from functools import lru_cache
from pydantic import AnyUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """Configuration settings for the QueryForge agent application."""

    DATABASE_URL: str = "sqlite+aiosqlite:///queryforge.db"
    """SQLite/aiosqlite connection string for database tools."""

    STRIPE_API_KEY: SecretStr = SecretStr("mock_stripe_api_key")
    """API key for Stripe billing/churn queries."""

    STRIPE_WEBHOOK_SECRET: SecretStr = SecretStr("mock_stripe_webhook_secret")
    """Webhook secret for verifying Stripe events."""

    NOTION_API_KEY: SecretStr = SecretStr("mock_notion_api_key")
    """Integration token for Notion API."""

    NOTION_DATABASE_ID: str = "mock_notion_database_id"
    """Target database ID in Notion."""

    OLLAMA_BASE_URL: str = "http://localhost:11434"
    """Base URL for local Ollama LLM service."""

    OLLAMA_AGENT_MODEL: str = "qwen2.5:7b"
    """Local LLM model name used for agent orchestration/reasoning."""

    OLLAMA_EMBED_MODEL: str = "nomic-embed-text"
    """Local LLM model name used for embeddings."""

    DRAGONFLY_URL: str = "redis://localhost:6379"
    """DragonflyDB (Redis compatible) connection URL."""

    CHARTS_OUTPUT_DIR: str = "data/charts"
    """Directory where generated charts are saved."""

    MAX_PDF_PAGES: int = 50
    """Maximum number of PDF pages to process in research tasks."""

    MAX_TOOL_RETRIES: int = 3
    """Maximum retry count for failed tool calls."""

    LOG_LEVEL: str = "INFO"
    """Logging level for the application."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    """Return a cached instance of the settings."""
    return Settings()
