"""Pydantic models for chat-related requests and responses."""

from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class ActionType(str, Enum):
    """Types of SSE messages sent to the client."""
    THINKING = "thinking"
    CONTENT = "content"
    ACTION = "action"
    COMPLETE = "complete"
    ERROR = "error"


class ActionStyle(str, Enum):
    """Visual styles for action buttons."""
    PRIMARY = "primary"
    SECONDARY = "secondary"
    OUTLINE = "outline"


class ActionButton(BaseModel):
    """Suggested action button for user interaction."""
    id: str
    label: str
    action_type: str
    params: Dict[str, str] = {}
    style: ActionStyle = ActionStyle.PRIMARY
    icon: Optional[str] = None

    class Config:
        json_schema_extra = {
                "style": {"enum": [e.value for e in ActionStyle]}
            }


class ChatRequest(BaseModel):
    """Request model for chat messages."""
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    """Response model for chat messages."""
    message: str
    actions: List[ActionButton] = []
    intent: Optional[str] = None
    needs_tool: bool = False
    session_id: Optional[str] = None


class SSEMessage(BaseModel):
    """Server-Sent Events message format."""
    type: ActionType
    content: Optional[str] = None
    actions: Optional[List[ActionButton]] = None
    error: Optional[str] = None
    session_id: Optional[str] = None

    class Config:
        json_schema_extra = {
                "type": {"enum": [e.value for e in ActionType]}
            }


class StreamChunk(BaseModel):
    """A single chunk in the SSE stream."""
    data: SSEMessage
    event: str = "message"
    id: Optional[str] = None

    def to_sse_format(self) -> str:
        """Convert to SSE format string.

        Returns:
            Formatted string for SSE: "data: {...}\\n\\n"
        """
        import json
        data_dict = self.data.model_dump()
        return f"data: {json.dumps(data_dict)}\n\n"
