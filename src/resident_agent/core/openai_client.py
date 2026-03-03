"""OpenAI client wrapper with singleton pattern."""

from typing import Optional
from openai import AsyncOpenAI

from .config import Settings


class OpenAIClient:
    """Singleton wrapper for OpenAI AsyncClient."""

    _instance: Optional[AsyncOpenAI] = None

    @classmethod
    def get(cls, settings: Settings = None) -> "AsyncOpenAI":
        """Get or create OpenAI client instance."""
        if cls._instance is None:
            if settings is None:
                from .config import Settings
                settings = Settings.get()
            cls._instance = AsyncOpenAI(api_key=settings.openai_api_key)
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset client instance (for testing)."""
        cls._instance = None
