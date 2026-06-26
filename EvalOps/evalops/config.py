import os
from dataclasses import dataclass, field
from typing import Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

@dataclass
class Settings:
    """Settings class to manage configuration parameters loaded from environment variables."""
    ollama_base_url: str = field(default_factory=lambda: os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))
    db_path: str = field(default_factory=lambda: os.getenv("DB_PATH", "./evalops.db"))
    default_model: str = field(default_factory=lambda: os.getenv("DEFAULT_MODEL", "llama3"))
    judge_model: str = field(default_factory=lambda: os.getenv("JUDGE_MODEL", "llama3"))
    judge_threshold: float = field(default_factory=lambda: float(os.getenv("JUDGE_THRESHOLD", "0.7")))

# Singleton instance
_settings_instance: Optional[Settings] = None

def get_settings() -> Settings:
    """
    Get the singleton instance of the Settings class.
    
    Returns:
        Settings: Configured settings instance.
    """
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
    return _settings_instance
