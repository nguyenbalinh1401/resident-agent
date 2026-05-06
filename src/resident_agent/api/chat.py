"""Chat API endpoints."""

from typing import Dict, Any, Optional
import uuid
from fastapi import APIRouter, Depends, Header
import structlog
from openai import BadRequestError

from resident_agent.schemas.chat_schemas import ChatRequest, ChatResponse
from resident_agent.auth.dependencies import get_current_user, get_pulse_client
from resident_agent.cux.orchestrator import CuxOrchestrator
from resident_agent.core.config import Settings
from resident_agent.core.ops_store import OpsStore
from resident_agent.clients.pulse_client import PulseClient

logger = structlog.get_logger()

router = APIRouter()


def _provider_error_message(error: Exception) -> Optional[str]:
    text = str(error)
    lowered = text.lower()

    if "api key expired" in lowered or "api_key_invalid" in lowered:
        return (
            "Dich vu AI tam thoi chua san sang do khoa API da het han hoac khong hop le. "
            "Vui long cap nhat API key tren server Agent."
        )

    if "user location is not supported" in lowered or "failed_precondition" in lowered:
        return (
            "Dich vu AI hien dang bi chan theo khu vuc cua nha cung cap. "
            "Vui long doi provider ho tro hoac cap nhat cau hinh server Agent."
        )

    return None


def _resolve_session_id(
    requested_session_id: Optional[str],
    user: Dict[str, Any],
) -> str:
    if not requested_session_id:
        return str(uuid.uuid4())

    store = OpsStore.create()
    owner = store.get_session_owner(requested_session_id)
    current_user_id = str(user.get("sub") or "")

    if owner == current_user_id:
        return requested_session_id

    if owner and owner != current_user_id:
        logger.warning(
            "session_owner_mismatch_regenerated",
            requested_session_id=requested_session_id,
            owner=owner,
            current_user_id=current_user_id,
        )
        return str(uuid.uuid4())

    # Unknown or legacy session without a persisted owner:
    # regenerate to prevent cross-user reuse via stale client state.
    logger.info(
        "session_owner_missing_regenerated",
        requested_session_id=requested_session_id,
        current_user_id=current_user_id,
    )
    return str(uuid.uuid4())


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
    session_id = _resolve_session_id(request.session_id, user)

    logger.info(
        "chat_request",
        session_id=session_id,
        user_id=user.get("sub"),
        message_preview=request.message[:50],
    )

    # Initialize orchestrator
    settings = Settings.get()
    orchestrator = CuxOrchestrator(settings)

    try:
        # Process message with injected PulseClient
        response = await orchestrator.process(
            message=request.message,
            session_id=session_id,
            user=user,
            pulse_client=pulse_client,
            intent_type=request.intent_type or "agentic_flow",
            attachments=request.attachments,
        )
    except BadRequestError as e:
        friendly = _provider_error_message(e) or (
            "Dich vu AI tam thoi gap loi khi xu ly yeu cau. Vui long thu lai sau."
        )
        logger.warning(
            "chat_provider_error",
            session_id=session_id,
            user_id=user.get("sub"),
            error=str(e),
        )
        return ChatResponse(
            message=friendly,
            actions=[],
            session_id=session_id,
            tool_calls=[],
            intent=request.intent_type or "agentic_flow",
        )
    except Exception as e:
        logger.error(
            "chat_unhandled_error",
            session_id=session_id,
            user_id=user.get("sub"),
            error=str(e),
            exc_info=True,
        )
        return ChatResponse(
            message="Dich vu AI tam thoi gap loi khi xu ly yeu cau. Vui long thu lai sau.",
            actions=[],
            session_id=session_id,
            tool_calls=[],
            intent=request.intent_type or "agentic_flow",
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
    session_id = _resolve_session_id(request.session_id, user)
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

    try:
        # Process as tool_call intent with injected PulseClient
        response = await orchestrator.process(
            message=request.message or f"Execute action: {action}",
            session_id=session_id,
            user=user,
            pulse_client=pulse_client,
            intent_type="tool_call",
            attachments=request.attachments,
        )
    except BadRequestError as e:
        friendly = _provider_error_message(e) or (
            "Dich vu AI tam thoi chua the thuc hien hanh dong nay. Vui long thu lai sau."
        )
        logger.warning(
            "action_provider_error",
            session_id=session_id,
            user_id=user.get("sub"),
            action=action,
            error=str(e),
        )
        return ChatResponse(
            message=friendly,
            actions=[],
            session_id=session_id,
            tool_calls=[],
            intent="tool_call",
        )
    except Exception as e:
        logger.error(
            "action_unhandled_error",
            session_id=session_id,
            user_id=user.get("sub"),
            action=action,
            error=str(e),
            exc_info=True,
        )
        return ChatResponse(
            message="Dich vu AI tam thoi chua the thuc hien hanh dong nay. Vui long thu lai sau.",
            actions=[],
            session_id=session_id,
            tool_calls=[],
            intent="tool_call",
        )

    OpsStore.create().upsert_session(
        user=user,
        session_id=session_id,
        user_message=request.message or f"Execute action: {action}",
        assistant_message=response.message,
    )

    return response
