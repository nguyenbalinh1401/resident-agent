"""Configuration management using Pydantic Settings with YAML support."""

from typing import Optional, ClassVar, Any
from pathlib import Path
import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from config.yaml + .env overrides."""

    # Class variable for singleton (not a model field)
    _instance: ClassVar[Optional["Settings"]] = None
    _config_loaded: ClassVar[bool] = False

    # Application
    environment: str = "development"
    log_level: str = "INFO"
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # OpenAI / LLM
    openai_api_key: str = Field(default="sk-test-key", alias="OPENAI_API_KEY")
    openai_api_base_url: Optional[str] = Field(default=None, alias="OPENAI_API_BASE_URL")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")
    openai_max_tokens: int = Field(default=1000, alias="OPENAI_MAX_TOKENS")
    openai_temperature: float = Field(default=0.3, alias="OPENAI_TEMPERATURE")

    # JWT
    jwt_secret_key: str = Field(default="your-secret-key-here-change-in-production", alias="JWT_SECRET_KEY")
    jwt_access_token_expire_minutes: int = Field(default=15, alias="JWT_ACCESS_TOKEN_EXPIRE_MINUTES")
    jwt_refresh_token_expire_days: int = Field(default=7, alias="JWT_REFRESH_TOKEN_EXPIRE_DAYS")

    # Pulse Backend
    pulse_backend_url: str = Field(default="http://localhost:8080", alias="PULSE_BACKEND_URL")
    pulse_backend_timeout: float = Field(default=30.0, alias="PULSE_BACKEND_TIMEOUT")

    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    redis_prefix: str = Field(default="pulse:chat:", alias="REDIS_PREFIX")
    redis_session_ttl: int = Field(default=3600, alias="REDIS_SESSION_TTL")  # 1 hour

    # Conversation
    max_history_length: int = Field(default=10, alias="MAX_HISTORY_LENGTH")
    session_timeout_seconds: int = Field(default=3600, alias="SESSION_TIMEOUT_SECONDS")

    # Actions
    max_actions_per_response: int = Field(default=4, alias="MAX_ACTIONS_PER_RESPONSE")
    actions_cache_ttl_seconds: int = Field(default=300, alias="ACTIONS_CACHE_TTL_SECONDS")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore extra env vars
    )

    @classmethod
    def _load_yaml_config(cls) -> dict:
        """Load configuration from config.yaml."""
        config_path = Path("configs/config.yaml")
        if config_path.exists():
            with open(config_path, "r") as f:
                return yaml.safe_load(f) or {}
        return {}

    @classmethod
    def get(cls) -> "Settings":
        """Get or create Settings instance (singleton pattern)."""
        if cls._instance is None:
            # Load YAML config first
            yaml_config = cls._load_yaml_config()

            # Create instance with YAML defaults + env overrides
            # Pydantic will automatically load from .env
            cls._instance = cls()

            # Apply YAML config as defaults for any not set by env
            if yaml_config:
                cls._apply_yaml_config(cls._instance, yaml_config)

        return cls._instance

    @classmethod
    def _apply_yaml_config(cls, instance: "Settings", yaml_config: dict):
        """Apply YAML config values if not already set by env."""
        # Application
        if "application" in yaml_config:
            app_config = yaml_config["application"]
            if instance.environment == "development":
                instance.environment = app_config.get("environment", "development")
            if instance.log_level == "INFO":
                instance.log_level = app_config.get("log_level", "INFO")
            if instance.host == "0.0.0.0":
                instance.host = app_config.get("host", "0.0.0.0")
            if instance.port == 8000:
                instance.port = app_config.get("port", 8000)
            if instance.debug == False:
                instance.debug = app_config.get("debug", False)

        # OpenAI
        if "openai" in yaml_config:
            openai_config = yaml_config["openai"]
            if instance.openai_api_base_url is None:
                instance.openai_api_base_url = openai_config.get("api_base_url")
            if instance.openai_model == "gpt-4o-mini":
                instance.openai_model = openai_config.get("model", "gpt-4o-mini")
            if instance.openai_max_tokens == 1000:
                instance.openai_max_tokens = openai_config.get("max_tokens", 1000)
            if instance.openai_temperature == 0.3:
                instance.openai_temperature = openai_config.get("temperature", 0.3)

        # JWT
        if "jwt" in yaml_config:
            jwt_config = yaml_config["jwt"]
            if instance.jwt_access_token_expire_minutes == 15:
                instance.jwt_access_token_expire_minutes = jwt_config.get("access_token_expire_minutes", 15)
            if instance.jwt_refresh_token_expire_days == 7:
                instance.jwt_refresh_token_expire_days = jwt_config.get("refresh_token_expire_days", 7)

        # Pulse Backend
        if "pulse_backend" in yaml_config:
            pulse_config = yaml_config["pulse_backend"]
            if instance.pulse_backend_url == "http://localhost:5000":
                instance.pulse_backend_url = pulse_config.get("base_url", "http://localhost:5000")
            if instance.pulse_backend_timeout == 30.0:
                instance.pulse_backend_timeout = pulse_config.get("timeout", 30.0)

        # Redis
        if "redis" in yaml_config:
            redis_config = yaml_config["redis"]
            if instance.redis_url == "redis://localhost:6379/0":
                instance.redis_url = redis_config.get("url", "redis://localhost:6379/0")
            if instance.redis_prefix == "pulse:chat:":
                instance.redis_prefix = redis_config.get("prefix", "pulse:chat:")
            if instance.redis_session_ttl == 3600:
                instance.redis_session_ttl = redis_config.get("session_ttl", 3600)

        # Conversation
        if "conversation" in yaml_config:
            conv_config = yaml_config["conversation"]
            if instance.max_history_length == 10:
                instance.max_history_length = conv_config.get("max_history_length", 10)
            if instance.session_timeout_seconds == 3600:
                instance.session_timeout_seconds = conv_config.get("session_timeout_seconds", 3600)

        # Actions
        if "actions" in yaml_config:
            actions_config = yaml_config["actions"]
            if instance.max_actions_per_response == 4:
                instance.max_actions_per_response = actions_config.get("max_actions_per_response", 4)
            if instance.actions_cache_ttl_seconds == 300:
                instance.actions_cache_ttl_seconds = actions_config.get("cache_ttl_seconds", 300)

    @classmethod
    def reset(cls) -> None:
        """Reset instance (for testing)."""
        cls._instance = None
