from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # API Keys & Sensitive Info
    ANTHROPIC_API_KEY: SecretStr = SecretStr("mock-anthropic-key")
    STRIPE_SECRET_KEY: SecretStr = SecretStr("mock-stripe-key")
    STRIPE_WEBHOOK_SECRET: SecretStr = SecretStr("whsec_mock")
    DATABASE_URL: SecretStr = SecretStr("postgresql://postgres:postgres@localhost:5432/postgres")
    
    # Non-sensitive config
    REDIS_URL: str = "redis://localhost:6379/0"
    PRIMARY_MODEL: str = "claude-sonnet-4-6"
    FALLBACK_MODEL: str = "claude-haiku-4-5-20251001"
    
    # Resilience & Policy Configuration
    MAX_RETRIES: int = 3
    RETRY_BASE_DELAY: float = 1.0
    CIRCUIT_BREAKER_THRESHOLD: int = 5
    TIMEOUT_SECONDS: float = 30.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    def __repr__(self) -> str:
        # Formats the representation, masking SecretStr fields
        masked_fields = []
        for name, value in self.model_fields.items():
            val = getattr(self, name)
            if isinstance(val, SecretStr):
                masked_fields.append(f"{name}=SecretStr('**********')")
            else:
                masked_fields.append(f"{name}={repr(val)}")
        return f"{self.__class__.__name__}({', '.join(masked_fields)})"


settings = Settings()
