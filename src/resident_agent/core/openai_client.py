"""OpenAI client wrapper with async support and streaming."""

from typing import Optional, List, Dict, Any, AsyncGenerator
import structlog
from openai import AsyncOpenAI

from resident_agent.core.config import Settings
from resident_agent.core.llm_client_factory import build_openai_client_kwargs

logger = structlog.get_logger()


class OpenAIClient:
    """Async OpenAI client wrapper with streaming support."""

    _instance: Optional["OpenAIClient"] = None
    _settings: Optional[Settings] = None

    def __init__(self, settings: Settings):
        """Initialize OpenAI client.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self._client: Optional[AsyncOpenAI] = None

    @classmethod
    def get(cls, settings: Optional[Settings] = None) -> "OpenAIClient":
        """Get or create OpenAI client instance (singleton per settings)."""
        if settings is None:
            settings = Settings.get()

        if cls._instance is None or cls._settings != settings:
            cls._instance = cls(settings)
            cls._settings = settings

        return cls._instance

    async def __aenter__(self) -> "OpenAIClient":
        """Async context manager entry."""
        client_kwargs = build_openai_client_kwargs(self.settings)
        self._client = AsyncOpenAI(**client_kwargs)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        if self._client:
            await self._client.close()
            self._client = None

    @property
    def client(self) -> AsyncOpenAI:
        """Get the underlying AsyncOpenAI client."""
        if self._client is None:
            raise RuntimeError("Client not initialized. Use async with context manager.")
        return self._client

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict]] = None,
        tool_choice: Optional[str] = "auto",
        response_format: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Create a chat completion.

        Args:
            messages: List of message dicts with role and content
            tools: Optional list of tool definitions
            tool_choice: Tool choice strategy ("auto", "required", "none")
            response_format: Optional response format (e.g., {"type": "json_object"})

        Returns:
            Completion response dict
        """
        kwargs = {
            "model": self.settings.openai_model,
            "messages": messages,
            "temperature": self.settings.openai_temperature,
            "max_tokens": self.settings.openai_max_tokens,
        }

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice

        if response_format:
            kwargs["response_format"] = response_format

        logger.debug(
            "openai_request",
            model=kwargs["model"],
            message_count=len(messages),
            has_tools=tools is not None,
        )

        response = await self._client.chat.completions.create(**kwargs)

        logger.debug(
            "openai_response",
            usage=response.usage.model_dump() if response.usage else None,
            finish_reason=response.choices[0].finish_reason if response.choices else None,
        )

        return response

    async def chat_completion_stream(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict]] = None,
        tool_choice: Optional[str] = "auto",
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Create a streaming chat completion.

        Args:
            messages: List of message dicts with role and content
            tools: Optional list of tool definitions
            tool_choice: Tool choice strategy

        Yields:
            Stream chunks as dicts
        """
        kwargs = {
            "model": self.settings.openai_model,
            "messages": messages,
            "temperature": self.settings.openai_temperature,
            "max_tokens": self.settings.openai_max_tokens,
            "stream": True,
        }

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice

        logger.debug(
            "openai_stream_request",
            model=kwargs["model"],
            message_count=len(messages),
            has_tools=tools is not None,
        )

        stream = await self._client.chat.completions.create(**kwargs)

        async for chunk in stream:
            yield chunk

    async def close(self) -> None:
        """Close the client connection."""
        if self._client:
            await self._client.close()
            self._client = None
