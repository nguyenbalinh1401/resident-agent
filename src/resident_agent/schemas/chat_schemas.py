"""Chat schemas for request/response validation."""

from typing import Optional, List, Dict, Any, Literal
from enum import Enum
from pydantic import BaseModel, Field


class AttachmentType(str, Enum):
    """Types of attachments supported."""

    IMAGE = "image"
    URL = "url"
    FILE = "file"


class ActionStyle(str, Enum):
    """Visual styles for action buttons."""

    PRIMARY = "primary"
    SECONDARY = "secondary"
    OUTLINE = "outline"
    DANGER = "danger"


class IntentType(str, Enum):
    """Intent types for CUX processing."""

    CHITCHAT = "chitchat"
    AGENTIC_FLOW = "agentic_flow"
    TOOL_CALL = "tool_call"


class Attachment(BaseModel):
    """Attachment model for multimodal input."""

    type: str = Field(..., description="Attachment type: image, url, file")
    data: Optional[str] = Field(
        default=None,
        description="Base64 encoded data for inline attachments",
    )
    url: Optional[str] = Field(
        default=None,
        description="URL for remote attachments",
    )
    mime_type: Optional[str] = Field(
        default=None,
        description="MIME type of the attachment",
        examples=["image/jpeg", "application/pdf"],
    )


class ActionButton(BaseModel):
    """Action button model for UI interactions."""

    id: str = Field(..., description="Unique action identifier")
    label: str = Field(..., description="Button display text with emoji")
    action_type: str = Field(
        ...,
        description="Action type for client handling (e.g., navigate, report_incident)",
    )
    params: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional parameters for the action",
    )
    style: ActionStyle = Field(
        default=ActionStyle.SECONDARY,
        description="Visual style of the button",
    )

    model_config = {"use_enum_values": True}


class ToolCall(BaseModel):
    """Tool call result model."""

    tool: str = Field(..., description="Tool name that was called")
    params: Dict[str, Any] = Field(default_factory=dict, description="Parameters used")
    result: Optional[Dict[str, Any]] = Field(default=None, description="Tool execution result")
    error: Optional[str] = Field(default=None, description="Error message if failed")


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""

    message: str = Field(..., min_length=1, description="User message")
    session_id: Optional[str] = Field(
        default=None,
        description="Session identifier for conversation continuity",
    )
    attachments: Optional[List[Attachment]] = Field(
        default=None,
        description="List of attachments (images, files, URLs)",
    )
    intent_type: IntentType = Field(
        default=IntentType.AGENTIC_FLOW,
        description="Intent type: chitchat, agentic_flow, tool_call",
    )
    action: Optional[str] = Field(
        default=None,
        description="Action ID for tool_call intent",
    )
    context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional context from client",
    )

    model_config = {"use_enum_values": True}


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""

    message: str = Field(..., description="AI response message")
    actions: List[Dict] = Field(
        default_factory=list,
        description="Suggested action buttons",
    )
    session_id: str = Field(..., description="Session identifier")
    tool_calls: List[ToolCall] = Field(
        default_factory=list,
        description="Tool calls made during processing",
    )
    intent: Optional[str] = Field(default=None, description="Detected intent")


class SSEEventType(str, Enum):
    """SSE event types for streaming responses."""

    THINKING = "thinking"
    TOKEN = "token"
    CONTENT = "content"
    ACTION = "action"
    ACTIONS = "actions"
    TOOL_CALL = "tool_call"
    COMPLETE = "complete"
    ERROR = "error"


class SSEEvent(BaseModel):
    """SSE event model for streaming responses."""

    type: SSEEventType
    session_id: str
    content: Optional[str] = Field(default=None, description="Content for token/content events")
    actions: Optional[List[ActionButton]] = Field(default=None, description="Actions for action events")
    tool_call: Optional[ToolCall] = Field(default=None, description="Tool call for tool_call events")
    error: Optional[str] = Field(default=None, description="Error message for error events")

    model_config = {"use_enum_values": True}

    def to_sse(self) -> str:
        """Convert to SSE format string."""
        import json

        data = self.model_dump(exclude_none=True)
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
