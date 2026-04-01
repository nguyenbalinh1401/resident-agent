"""SSE (Server-Sent Events) streaming endpoint for chat."""

from typing import Dict, Any, Optional
import uuid
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
import structlog

from resident_agent.auth.dependencies import get_current_user, get_pulse_client
from resident_agent.cux.orchestrator import CuxOrchestrator
from resident_agent.core.config import Settings
from resident_agent.clients.pulse_client import PulseClient

logger = structlog.get_logger()

router = APIRouter()


@router.get(
    "/chat/stream",
    summary="Stream chat response",
    description="Send a message and stream the response via Server-Sent Events (SSE).",
)
async def chat_stream(
    message: str = Query(..., description="User message"),
    session_id: Optional[str] = Query(None, description="Session identifier"),
    intent_type: str = Query("agentic_flow", description="Intent type: chitchat, agentic_flow, tool_call"),
    user: Dict[str, Any] = Depends(get_current_user),
    pulse_client: PulseClient = Depends(get_pulse_client),
) -> StreamingResponse:
    """Stream chat response via SSE.

    SSE Event Types:
    - `thinking`: AI is processing
    - `token`: Text token chunk
    - `tool_call`: Tool is being executed
    - `actions`: Action buttons to display
    - `complete`: Stream finished
    - `error`: Error occurred

    Args:
        message: User message
        session_id: Optional session identifier
        intent_type: Intent type (chitchat, agentic_flow, tool_call)
        user: Current user from JWT
        pulse_client: Authenticated PulseClient instance (injected)

    Returns:
        StreamingResponse with SSE events
    """
    # Generate session_id if not provided
    session_id = session_id or str(uuid.uuid4())

    logger.info(
        "chat_stream_request",
        session_id=session_id,
        user_id=user.get("sub"),
        message_preview=message[:50],
        intent_type=intent_type,
    )

    # Initialize orchestrator
    settings = Settings.get()
    orchestrator = CuxOrchestrator(settings)

    async def event_generator():
        """Generate SSE events."""
        try:
            async for sse_event in orchestrator.process_stream(
                message=message,
                session_id=session_id,
                user=user,
                pulse_client=pulse_client,
                intent_type=intent_type,
            ):
                yield sse_event

        except Exception as e:
            logger.error("stream_error", error=str(e), exc_info=True)
            import json
            error_event = {
                "type": "error",
                "session_id": session_id,
                "error": str(e),
            }
            yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
