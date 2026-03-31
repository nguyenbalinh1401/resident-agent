"""Redis-based conversation state management.

Manages conversation history and session state with Redis for persistence and TTL support.
"""

from typing import Optional, Dict, Any, List
import json
import redis.asyncio as redis
import structlog

from resident_agent.core.config import Settings

logger = structlog.get_logger()


class StateManager:
    """Redis-based conversation state manager."""

    def __init__(self, settings: Optional[Settings] = None):
        """Initialize state manager.

        Args:
            settings: Application settings
        """
        self.settings = settings or Settings.get()
        self._redis: Optional[redis.Redis] = None
        self._prefix = self.settings.redis_prefix

    async def connect(self) -> "StateManager":
        """Establish Redis connection.

        Returns:
            Self for chaining
        """
        if self._redis is None:
            self._redis = redis.from_url(
            self.settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        logger.info("redis_connected", url=self.settings.redis_url)
        return self

    async def disconnect(self) -> None:
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
            self._redis = None
            logger.info("redis_disconnected")

    def _get_history_key(self, session_id: str) -> str:
        """Get Redis key for message history."""
        return f"{self._prefix}history:{session_id}"

    def _get_state_key(self, session_id: str) -> str:
        """Get Redis key for session state."""
        return f"{self._prefix}state:{session_id}"

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
    ) -> None:
        """Add a message to conversation history.

        Args:
            session_id: Session identifier
            role: Message role ("user" or "assistant")
            content: Message content
        """
        key = self._get_history_key(session_id)
        message = {"role": role, "content": content}

        # Add to Redis list
        await self._redis.rpush(key, json.dumps(message, ensure_ascii=False))

        # Trim to max history length
        await self._redis.ltrim(key, -self.settings.max_history_length, -1)

        # Set TTL on the key
        await self._redis.expire(key, self.settings.redis_session_ttl)

        logger.debug(
            "message_added",
            session_id=session_id,
            role=role,
            content_length=len(content),
        )

    async def get_history(
        self,
        session_id: str,
        limit: Optional[int] = None,
    ) -> List[Dict[str, str]]:
        """Get conversation history.

        Args:
            session_id: Session identifier
            limit: Maximum number of messages to return (default: all)

        Returns:
            List of message dicts with 'role' and 'content' keys
        """
        key = self._get_history_key(session_id)

        if limit:
            messages = await self._redis.lrange(key, -limit, -1)
        else:
            messages = await self._redis.lrange(key, 0, -1)

        return [json.loads(msg) for msg in messages]

    async def get_history_for_llm(
        self,
        session_id: str,
        limit: int = 10,
    ) -> List[Dict[str, str]]:
        """Get conversation history formatted for LLM.

        Args:
            session_id: Session identifier
            limit: Maximum number of messages

        Returns:
            List of message dicts ready for LLM consumption
        """
        messages = await self.get_history(session_id, limit=limit)
        return [{"role": msg["role"], "content": msg["content"]} for msg in messages]

    async def clear_history(self, session_id: str) -> None:
        """Clear conversation history for a session.

        Args:
            session_id: Session identifier
        """
        key = self._get_history_key(session_id)
        await self._redis.delete(key)
        logger.debug("history_cleared", session_id=session_id)

    async def set_state(
        self,
        session_id: str,
        state: Dict[str, Any],
    ) -> None:
        """Set session state.

        Args:
            session_id: Session identifier
            state: State dictionary to store
        """
        key = self._get_state_key(session_id)
        await self._redis.set(
            key,
            json.dumps(state, ensure_ascii=False),
            ex=self.settings.redis_session_ttl,
        )
        logger.debug("state_set", session_id=session_id)

    async def get_state(self, session_id: str) -> Dict[str, Any]:
        """Get session state.

        Args:
            session_id: Session identifier

        Returns:
            State dictionary or empty dict if not found
        """
        key = self._get_state_key(session_id)
        state = await self._redis.get(key)

        if state:
            return json.loads(state)
        return {}

    async def update_state(
        self,
        session_id: str,
        updates: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Update session state (merge with existing).

        Args:
            session_id: Session identifier
            updates: State updates to merge

        Returns:
            Updated state dictionary
        """
        current = await self.get_state(session_id)
        current.update(updates)
        await self.set_state(session_id, current)
        return current

    async def delete_state(self, session_id: str) -> None:
        """Delete session state.

        Args:
            session_id: Session identifier
        """
        key = self._get_state_key(session_id)
        await self._redis.delete(key)
        logger.debug("state_deleted", session_id=session_id)

    async def session_exists(self, session_id: str) -> bool:
        """Check if a session exists (has history or state).

        Args:
            session_id: Session identifier

        Returns:
            True if session has any data
        """
        history_key = self._get_history_key(session_id)
        state_key = self._get_state_key(session_id)

        history_exists = await self._redis.exists(history_key)
        state_exists = await self._redis.exists(state_key)

        return bool(history_exists or state_exists)
