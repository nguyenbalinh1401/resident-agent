"""SSE (Server-Sent Events) streaming endpoint for real-time chat.

Implements SSE protocol for streaming chat responses,
allowing clients to receive incremental updates as the response is generated.
"""

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from typing import AsyncGenerator, Optional
import json
import asyncio

from ..schemas.chat_schemas import SSEMessage, ActionButton, ActionStyle, ActionType
from ..auth.dependencies import get_current_user
from ..cux.orchestrator import CuxOrchestrator
from ..core.config import Settings

router = APIRouter()

# Global orchestrator instance
_orchestrator: Optional[CuxOrchestrator] = None


def get_orchestrator() -> CuxOrchestrator:
    """Get or create CUX orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        settings = Settings.get()
        _orchestrator = CuxOrchestrator(settings=settings)
    return _orchestrator


async def stream_chat_response(
    message: str,
    session_id: str,
    user_id: str,
    orchestrator: CuxOrchestrator
) -> AsyncGenerator[str, None]:
    """Generate SSE events for chat response.

    Args:
        message: User message
        session_id: Session identifier
        user_id: User identifier
        orchestrator: CUX orchestrator

    Yields:
        SSE formatted strings: "data: {...}\\n\\n"
    """
    try:
        # Send thinking message
        thinking_msg = SSEMessage(
            type=ActionType.THINKING,
            content="Đang xử lý yêu cầu của bạn...",
            session_id=session_id
        )
        yield f"data: {thinking_msg.model_dump_json()}\n\n"

        # Small delay for realistic feel
        await asyncio.sleep(0.1)

        # Process through CUX
        response = await orchestrator.process(
            session_id=session_id,
            user_id=user_id,
            message=message
        )

        # Send content message
        content_msg = SSEMessage(
            type=ActionType.CONTENT,
            content=response.message,
            session_id=session_id
        )
        yield f"data: {content_msg.model_dump_json()}\n\n"

        # Send action suggestions if available
        if response.actions:
            action_msg = SSEMessage(
                type=ActionType.ACTION,
                actions=response.actions,
                session_id=session_id
            )
            yield f"data: {action_msg.model_dump_json()}\n\n"

        # Send complete message
        complete_msg = SSEMessage(
            type=ActionType.COMPLETE,
            session_id=session_id
        )
        yield f"data: {complete_msg.model_dump_json()}\n\n"

    except Exception as e:
        # Send error message
        error_msg = SSEMessage(
            type=ActionType.ERROR,
            error=str(e),
            session_id=session_id
        )
        yield f"data: {error_msg.model_dump_json()}\n\n"


@router.get("/chat")
async def chat_stream(
    message: str,
    session_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    orchestrator: CuxOrchestrator = Depends(get_orchestrator)
) -> StreamingResponse:
    """Stream chat response via Server-Sent Events.

    This endpoint provides real-time streaming of chat responses,
    sending thinking, content, action, and complete events.

    Args:
        message: User message (query string parameter)
        session_id: Optional session identifier (query string parameter)
        current_user: Authenticated user from JWT token
        orchestrator: CUX orchestrator instance

    Returns:
        StreamingResponse with SSE content type

    Example:
        GET /stream/chat?message=xin%20chào&session_id=abc123
    """
    # Use provided session_id or create default
    sid = session_id or f"stream_{current_user['user_id']}"

    return StreamingResponse(
        stream_chat_response(
            message=message,
            session_id=sid,
            user_id=current_user["user_id"],
            orchestrator=orchestrator
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )


@router.post("/chat")
async def chat_stream_post(
    message: str,
    session_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    orchestrator: CuxOrchestrator = Depends(get_orchestrator)
) -> StreamingResponse:
    """Stream chat response via POST request.

    Same as GET but allows longer messages in request body.

    Args:
        message: User message (form data)
        session_id: Optional session identifier
        current_user: Authenticated user from JWT token
        orchestrator: CUX orchestrator instance

    Returns:
        StreamingResponse with SSE content type
    """
    sid = session_id or f"stream_{current_user['user_id']}"

    return StreamingResponse(
        stream_chat_response(
            message=message,
            session_id=sid,
            user_id=current_user["user_id"],
            orchestrator=orchestrator
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
