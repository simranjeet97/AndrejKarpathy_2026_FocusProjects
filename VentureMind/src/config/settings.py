from functools import lru_cache
from pydantic import AnyUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """Configuration settings for the VentureMind Multi-Agent System.

    Loaded from environment variables or a .env file.
    """
    DATABASE_URL: AnyUrl = Field(..., description="PostgreSQL database connection URL.")
    DRAGONFLY_URL: AnyUrl = Field(..., description="DragonflyDB (Redis-compatible) connection URL.")
    OLLAMA_BASE_URL: AnyUrl = Field("http://localhost:11434", description="Base URL of the Ollama server.")
    OLLAMA_ORCHESTRATOR_MODEL: str = Field("mistral:7b", description="Ollama model used by the orchestrator for planning and routing.")
    OLLAMA_ANALYST_MODEL: str = Field("codellama:13b", description="Ollama model used by domain-specific specialist agents for analysis.")
    OLLAMA_SUMMARY_MODEL: str = Field("mistral:7b", description="Ollama model used by the summarization agent for synthesizing reports.")
    OLLAMA_EMBED_MODEL: str = Field("nomic-embed-text", description="Ollama model used for generating embeddings.")
    REPORTS_OUTPUT_DIR: str = Field("data/reports", description="Directory where generated PDF and JSON reports will be saved.")
    MAX_SEARCH_RESULTS: int = Field(10, description="Maximum number of search results retrieved per query.")
    MAX_PDF_PAGES: int = Field(50, description="Maximum number of pages parsed from a source PDF document.")
    AGENT_TIMEOUT_SECONDS: int = Field(120, description="Timeout limit in seconds for a single agent's execution.")
    PARALLEL_AGENT_LIMIT: int = Field(4, description="Maximum number of specialist agents permitted to run in parallel.")
    LOG_LEVEL: str = Field("INFO", description="Logging level for the system.")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

@lru_cache
def get_settings() -> Settings:
    """Retrieve and cache the system configuration settings."""
    return Settings()
