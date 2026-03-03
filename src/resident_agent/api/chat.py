"""Chat API endpoint for processing user messages."""

from fastapi import APIRouter, Depends
from typing import Optional

from ..schemas.chat_schemas import ChatRequest, ChatResponse
from ..schemas.auth_schemas import UserResponse
from ..auth.dependencies import get_current_user
from ..cux.orchestrator import CuxOrchestrator
from ..core.config import Settings

router = APIRouter()

# Global orchestrator instance (initialized on first use)
_orchestrator: Optional[CuxOrchestrator] = None


def get_orchestrator() -> CuxOrchestrator:
    """Get or create CUX orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        settings = Settings.get()
        _orchestrator = CuxOrchestrator(settings=settings)
    return _orchestrator


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: dict = Depends(get_current_user),
    orchestrator: CuxOrchestrator = Depends(get_orchestrator)
) -> ChatResponse:
    """Process a chat message and return response with suggested actions.

    This endpoint:
    1. Authenticates the user via JWT
    2. Processes the message through CUX orchestrator
    3. Returns response with message and action buttons

    Args:
        request: ChatRequest with message and optional session_id
        current_user: Authenticated user from JWT token
        orchestrator: CUX orchestrator instance

    Returns:
        ChatResponse with message, actions, and intent
    """
    # Use provided session_id or create default
    session_id = request.session_id or f"session_{current_user['user_id']}"

    # Process through CUX orchestrator
    response = await orchestrator.process(
        session_id=session_id,
        user_id=current_user["user_id"],
        message=request.message
    )

    # Ensure session_id is in response
    response.session_id = session_id

    return response


@router.post("/action", response_model=ChatResponse)
async def execute_action(
    action_id: str,
    params: dict,
    current_user: dict = Depends(get_current_user),
    orchestrator: CuxOrchestrator = Depends(get_orchestrator)
) -> ChatResponse:
    """Execute a suggested action from a previous response.

    This endpoint allows executing action buttons returned in chat responses.

    Args:
        action_id: ID of the action to execute
        params: Parameters for the action
        current_user: Authenticated user from JWT token
        orchestrator: CUX orchestrator instance

    Returns:
        ChatResponse with action result
    """
    # Map action_id to a message for processing
    action_messages = {
        "report_incident": "Tôi muốn báo sự cố",
        "check_package": "Tôi muốn kiểm tra bưu kiện",
        "view_bills": "Tôi muốn xem hóa đơn",
        "book_amenity": "Tôi muốn đặt chỗ tiện ích",
        "service_request": "Tôi cần yêu cầu dịch vụ",
    }

    message = action_messages.get(action_id, f"Execute action: {action_id}")

    # Add params to message if available
    if params:
        message += f" với thông tin: {params}"

    session_id = f"session_{current_user['user_id']}"

    response = await orchestrator.process(
        session_id=session_id,
        user_id=current_user["user_id"],
        message=message
    )

    response.session_id = session_id
    return response
