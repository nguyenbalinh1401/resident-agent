"""Configuration management using Pydantic Settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, ClassVar


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Class variable for singleton (not a model field)
    _instance: ClassVar[Optional["Settings"]] = None

    # Application
    environment: str = "development"
    log_level: str = "INFO"
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # Database
    database_url: str = "postgresql://user:pass@localhost:5432/pulse"

    # Redis (optional)
    redis_url: Optional[str] = None

    # OpenAI
    openai_api_key: str = "sk-test-key"
    openai_model: str = "gpt-4o-mini"
    openai_max_tokens: int = 1000
    openai_temperature: float = 0.3

    # JWT
    secret_key: str = "your-secret-key-here-change-in-production"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # Demo user credentials (for testing)
    demo_email: str = "demo@example.com"
    demo_password: str = "demo123"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True
    )

    @classmethod
    def get(cls) -> "Settings":
        """Get or create Settings instance (singleton pattern)."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset instance (for testing)."""
        cls._instance = None
