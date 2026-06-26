from functools import lru_cache
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """Configuration settings for the VentureMind Multi-Agent System.

    Loaded from environment variables or a .env file.
    """
    DATABASE_URL: str = Field(..., description="SQLite database connection URL for persisting diligence reports.")
    DRAGONFLY_URL: str = Field(..., description="SQLite database connection URL for shared inter-agent memory.")
    OLLAMA_BASE_URL: str = Field("http://localhost:11434", description="Base URL of the local Ollama server.")
    OLLAMA_ORCHESTRATOR_MODEL: str = Field("qwen2.5:7b", description="Ollama model used by the orchestrator for planning and routing.")
    OLLAMA_ANALYST_MODEL: str = Field("qwen2.5:7b", description="Ollama model used by domain-specific specialist agents for analysis.")
    OLLAMA_SUMMARY_MODEL: str = Field("qwen2.5:7b", description="Ollama model used by the summarization agent for synthesizing reports.")
    OLLAMA_EMBED_MODEL: str = Field("nomic-embed-text", description="Ollama model used for generating embeddings.")
    REPORTS_OUTPUT_DIR: str = Field("data/reports", description="Directory where generated Markdown, DOCX, and HTML reports will be saved.")
    MAX_SEARCH_RESULTS: int = Field(10, description="Maximum number of search results retrieved per query.")
    MAX_PDF_PAGES: int = Field(50, description="Maximum number of pages parsed from a source PDF document.")
    AGENT_TIMEOUT_SECONDS: int = Field(180, description="Timeout limit in seconds for a single agent's execution.")
    PARALLEL_AGENT_LIMIT: int = Field(4, description="Maximum number of specialist agents permitted to run in parallel.")
    LOG_LEVEL: str = Field("INFO", description="Logging level for the system.")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("OLLAMA_BASE_URL")
    @classmethod
    def validate_ollama_url(cls, v: str) -> str:
        """Ensure OLLAMA_BASE_URL is a valid http/https URL."""
        v = v.strip().rstrip("/")
        if not v.startswith(("http://", "https://")):
            raise ValueError("OLLAMA_BASE_URL must start with http:// or https://")
        return v

@lru_cache
def get_settings() -> Settings:
    """Retrieve and cache the system configuration settings."""
    return Settings()
