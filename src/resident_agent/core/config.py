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
    environment: str = Field(default="development", alias="ENVIRONMENT")
    log_level: str = Field(default="info", alias="LOG_LEVEL")
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    debug: bool = Field(default=False)

    # OpenAI / LLM
    openai_api_key: str = Field(default="sk-test-key", alias="OPENAI_API_KEY")
    openai_api_base_url: Optional[str] = Field(default=None, alias="OPENAI_API_BASE_URL")
    openai_model: str = Field(default=None, alias="OPENAI_MODEL")
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

    # Prompts
    prompts_path: str = Field(default="configs/prompts.yaml", alias="PROMPTS_PATH")

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
        """Get or create Settings instance (singleton pattern).

        Priority: ENV variables > YAML config > class defaults
        """
        if cls._instance is None:
            # Load YAML config first - will serve as init_kwargs
            yaml_config = cls._load_yaml_config()
            init_kwargs = cls._flatten_yaml_config(yaml_config)

            # Create instance: ENV automatically overrides init_kwargs
            # Pydantic BaseSettings priority: ENV > init_kwargs > defaults
            cls._instance = cls(**init_kwargs)

        return cls._instance

    @classmethod
    def _flatten_yaml_config(cls, yaml_config: dict) -> dict:
        """Flatten nested YAML config to flat kwargs matching Settings fields.

        Returns dict with only non-None values to let class defaults work.
        """
        kwargs = {}

        # Application
        if "application" in yaml_config:
            app = yaml_config["application"]
            kwargs.setdefault("environment", app.get("environment"))
            kwargs.setdefault("log_level", app.get("log_level"))
            kwargs.setdefault("host", app.get("host"))
            kwargs.setdefault("port", app.get("port"))
            kwargs.setdefault("debug", app.get("debug"))

        # OpenAI
        if "openai" in yaml_config:
            openai = yaml_config["openai"]
            kwargs.setdefault("openai_api_base_url", openai.get("api_base_url"))
            kwargs.setdefault("openai_model", openai.get("model"))
            kwargs.setdefault("openai_max_tokens", openai.get("max_tokens"))
            kwargs.setdefault("openai_temperature", openai.get("temperature"))

        # JWT
        if "jwt" in yaml_config:
            jwt = yaml_config["jwt"]
            kwargs.setdefault("jwt_access_token_expire_minutes", jwt.get("access_token_expire_minutes"))
            kwargs.setdefault("jwt_refresh_token_expire_days", jwt.get("refresh_token_expire_days"))

        # Pulse Backend
        if "pulse_backend" in yaml_config:
            pulse = yaml_config["pulse_backend"]
            kwargs.setdefault("pulse_backend_url", pulse.get("base_url"))
            kwargs.setdefault("pulse_backend_timeout", pulse.get("timeout"))

        # Redis
        if "redis" in yaml_config:
            redis = yaml_config["redis"]
            kwargs.setdefault("redis_url", redis.get("url"))
            kwargs.setdefault("redis_prefix", redis.get("prefix"))
            kwargs.setdefault("redis_session_ttl", redis.get("session_ttl"))

        # Conversation
        if "conversation" in yaml_config:
            conv = yaml_config["conversation"]
            kwargs.setdefault("max_history_length", conv.get("max_history_length"))
            kwargs.setdefault("session_timeout_seconds", conv.get("session_timeout_seconds"))

        # Actions
        if "actions" in yaml_config:
            actions = yaml_config["actions"]
            kwargs.setdefault("max_actions_per_response", actions.get("max_actions_per_response"))
            kwargs.setdefault("actions_cache_ttl_seconds", actions.get("cache_ttl_seconds"))

        # Prompts
        if "prompts" in yaml_config:
            prompts = yaml_config["prompts"]
            kwargs.setdefault("prompts_path", prompts.get("path"))

        # Remove None values - let class defaults take over
        return {k: v for k, v in kwargs.items() if v is not None}

    @classmethod
    def reset(cls) -> None:
        """Reset instance (for testing)."""
        cls._instance = None
