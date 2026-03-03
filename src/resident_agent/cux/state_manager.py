"""Conversation state management for multi-turn dialogues.

This module handles:
- Storing conversation state between messages
- Managing conversation history
- Session lifecycle management
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
import structlog

logger = structlog.get_logger()


class ConversationStateManager:
    """Manages conversation state for multi-turn dialogues.

    In production, this would use Redis or database.
    For now, uses in-memory storage for testing.
    """

    def __init__(self, max_history_length: int = 10):
        """Initialize state manager.

        Args:
            max_history_length: Maximum number of messages to keep in history
        """
        self._states: Dict[str, Dict[str, Any]] = {}
        self.max_history_length = max_history_length

    async def get_state(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get current conversation state for a session.

        Args:
            session_id: Session identifier

        Returns:
            Current state dict or None if no state exists
        """
        state = self._states.get(session_id)
        if state:
            logger.debug(
                "state_retrieved",
                session_id=session_id,
                history_length=len(state.get("history", []))
            )
        return state

    async def update_state(
        self,
        session_id: str,
        updates: Dict[str, Any]
    ) -> None:
        """Update conversation state.

        Args:
            session_id: Session identifier
            updates: Dict of state updates to apply
        """
        current = self._states.get(session_id, {
            "created_at": datetime.utcnow().isoformat(),
            "history": [],
            "context": {},
        })

        # Apply updates
        current.update(updates)

        # Update timestamp
        current["updated_at"] = datetime.utcnow().isoformat()

        # Manage history length
        if "history" in updates:
            history = current.get("history", [])
            if len(history) > self.max_history_length:
                current["history"] = history[-self.max_history_length:]

        self._states[session_id] = current

        logger.debug(
            "state_updated",
            session_id=session_id,
            keys_updated=list(updates.keys())
        )

    async def add_message_to_history(
        self,
        session_id: str,
        role: str,
        message: str
    ) -> None:
        """Add a message to conversation history.

        Args:
            session_id: Session identifier
            role: Message role ("user" or "assistant")
            message: Message content
        """
        state = await self.get_state(session_id)
        if not state:
            state = {
                "created_at": datetime.utcnow().isoformat(),
                "history": [],
                "context": {},
            }

        history = state.get("history", [])
        history.append({
            "role": role,
            "content": message,
            "timestamp": datetime.utcnow().isoformat()
        })

        await self.update_state(session_id, {"history": history})

    async def get_history(
        self,
        session_id: str,
        limit: Optional[int] = None
    ) -> List[Dict[str, str]]:
        """Get conversation history.

        Args:
            session_id: Session identifier
            limit: Maximum number of messages to return

        Returns:
            List of message dicts with role, content, timestamp
        """
        state = await self.get_state(session_id)
        if not state:
            return []

        history = state.get("history", [])
        if limit:
            return history[-limit:]
        return history

    async def get_context(self, session_id: str) -> Dict[str, Any]:
        """Get conversation context (entities, preferences, etc.).

        Args:
            session_id: Session identifier

        Returns:
            Context dict with extracted entities and metadata
        """
        state = await self.get_state(session_id)
        if not state:
            return {}
        return state.get("context", {})

    async def set_context(
        self,
        session_id: str,
        context: Dict[str, Any]
    ) -> None:
        """Set conversation context.

        Args:
            session_id: Session identifier
            context: Context dict to set
        """
        await self.update_state(session_id, {"context": context})

    async def clear_state(self, session_id: str) -> None:
        """Clear conversation state for a session.

        Args:
            session_id: Session identifier
        """
        if session_id in self._states:
            del self._states[session_id]
            logger.debug("state_cleared", session_id=session_id)

    async def get_all_sessions(self) -> List[str]:
        """Get all active session IDs.

        Returns:
            List of session IDs
        """
        return list(self._states.keys())

    def get_session_count(self) -> int:
        """Get number of active sessions.

        Returns:
            Number of sessions
        """
        return len(self._states)
