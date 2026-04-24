"""Chat API endpoints."""

from typing import Dict, Any, Optional
import uuid
from fastapi import APIRouter, Depends, Header
import structlog

from resident_agent.schemas.chat_schemas import ChatRequest, ChatResponse
from resident_agent.auth.dependencies import get_current_user, get_pulse_client
from resident_agent.cux.orchestrator import CuxOrchestrator
from resident_agent.core.config import Settings
from resident_agent.core.ops_store import OpsStore
from resident_agent.clients.pulse_client import PulseClient

logger = structlog.get_logger()

router = APIRouter()


@router.post(
    "",
    response_model=ChatResponse,
    summary="Send a chat message",
    description="Send a message and get a response with optional action buttons.",
)
async def chat(
    request: ChatRequest,
    user: Dict[str, Any] = Depends(get_current_user),
    pulse_client: PulseClient = Depends(get_pulse_client),
) -> ChatResponse:
    """Process a chat message.

    Args:
        request: Chat request with message and optional session_id
        user: Current user from JWT
        pulse_client: Authenticated PulseClient instance (injected)

    Returns:
        ChatResponse with message, actions, and session_id
    """
    # Generate session_id if not provided
    session_id = request.session_id or str(uuid.uuid4())

    logger.info(
        "chat_request",
        session_id=session_id,
        user_id=user.get("sub"),
        message_preview=request.message[:50],
    )

    # Initialize orchestrator
    settings = Settings.get()
    orchestrator = CuxOrchestrator(settings)

    # Process message with injected PulseClient
    response = await orchestrator.process(
        message=request.message,
        session_id=session_id,
        user=user,
        pulse_client=pulse_client,
        intent_type=request.intent_type or "agentic_flow",
        attachments=request.attachments,
    )

    logger.info(
        "chat_response",
        session_id=session_id,
        response_length=len(response.message),
        action_count=len(response.actions),
        tool_call_count=len(response.tool_calls),
    )

    OpsStore.create().upsert_session(
        user=user,
        session_id=session_id,
        user_message=request.message,
        assistant_message=response.message,
    )

    return response


@router.post(
    "/action",
    response_model=ChatResponse,
    summary="Execute an action",
    description="Execute a suggested action directly (from action button click).",
)
async def execute_action(
    request: ChatRequest,
    user: Dict[str, Any] = Depends(get_current_user),
    pulse_client: PulseClient = Depends(get_pulse_client),
) -> ChatResponse:
    """Execute an action directly.

    This endpoint is used when user clicks an action button.
    The action field should contain the action type to execute.

    Args:
        request: Chat request with action field set
        user: Current user from JWT
        pulse_client: Authenticated PulseClient instance (injected)

    Returns:
        ChatResponse with action results
    """
    session_id = request.session_id or str(uuid.uuid4())
    action = request.action or request.message

    logger.info(
        "action_request",
        session_id=session_id,
        user_id=user.get("sub"),
        action=action,
    )

    # Initialize orchestrator
    settings = Settings.get()
    orchestrator = CuxOrchestrator(settings)

    # Process as tool_call intent with injected PulseClient
    response = await orchestrator.process(
        message=request.message or f"Execute action: {action}",
        session_id=session_id,
        user=user,
        pulse_client=pulse_client,
        intent_type="tool_call",
        attachments=request.attachments,
    )

    OpsStore.create().upsert_session(
        user=user,
        session_id=session_id,
        user_message=request.message or f"Execute action: {action}",
        assistant_message=response.message,
    )

    return response
