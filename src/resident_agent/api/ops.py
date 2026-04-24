"""Operational endpoints for sessions, handoffs, summaries, and admin config."""

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status

from resident_agent.auth.dependencies import get_current_user
from resident_agent.core.ops_store import OpsStore
from resident_agent.schemas.ops_schemas import (
    ApiKeyRecord,
    ApiKeyUpdateRequest,
    HandoffCreateRequest,
    HandoffRecord,
    HandoffUpdateRequest,
    KnowledgeBasePayload,
    KnowledgeBaseResponse,
    SessionSummary,
    SummaryGenerateRequest,
    SummaryResponse,
)

router = APIRouter()


def _require_admin(user: Dict[str, Any]) -> None:
    if str(user.get("role", "")).lower() != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access is required",
        )


@router.get(
    "/sessions",
    response_model=List[SessionSummary],
    summary="List chat sessions for current user",
)
async def list_sessions(
    user: Dict[str, Any] = Depends(get_current_user),
) -> List[SessionSummary]:
    store = OpsStore.create()
    return [SessionSummary(**item) for item in store.list_sessions_for_user(str(user.get("sub")))]


@router.get(
    "/handoffs",
    response_model=List[HandoffRecord],
    summary="List handoffs for current user",
)
async def list_my_handoffs(
    user: Dict[str, Any] = Depends(get_current_user),
) -> List[HandoffRecord]:
    store = OpsStore.create()
    return [HandoffRecord(**item) for item in store.list_handoffs(str(user.get("sub")))]


@router.post(
    "/handoffs",
    response_model=HandoffRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create a handoff to human staff",
)
async def create_handoff(
    request: HandoffCreateRequest,
    user: Dict[str, Any] = Depends(get_current_user),
) -> HandoffRecord:
    store = OpsStore.create()
    payload = store.create_handoff(
        user=user,
        session_id=request.session_id,
        topic=request.topic,
        summary=request.summary,
        priority=request.priority,
        requested_team=request.requested_team,
    )
    return HandoffRecord(**payload)


@router.get(
    "/admin/handoffs",
    response_model=List[HandoffRecord],
    summary="List all handoffs for admin operations",
)
async def list_admin_handoffs(
    user: Dict[str, Any] = Depends(get_current_user),
) -> List[HandoffRecord]:
    _require_admin(user)
    store = OpsStore.create()
    return [HandoffRecord(**item) for item in store.list_handoffs()]


@router.patch(
    "/admin/handoffs/{handoff_id}",
    response_model=HandoffRecord,
    summary="Update handoff status or assignment",
)
async def patch_handoff(
    handoff_id: str,
    request: HandoffUpdateRequest,
    user: Dict[str, Any] = Depends(get_current_user),
) -> HandoffRecord:
    _require_admin(user)
    store = OpsStore.create()
    try:
        updated = store.update_handoff(
            handoff_id,
            status=request.status,
            assigned_to=request.assigned_to,
            resolution_note=request.resolution_note,
        )
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Handoff not found")
    return HandoffRecord(**updated)


@router.get(
    "/admin/knowledge-base",
    response_model=KnowledgeBaseResponse,
    summary="Get AI knowledge base content",
)
async def get_knowledge_base(
    user: Dict[str, Any] = Depends(get_current_user),
) -> KnowledgeBaseResponse:
    _require_admin(user)
    store = OpsStore.create()
    return KnowledgeBaseResponse(**store.get_knowledge_base())


@router.put(
    "/admin/knowledge-base",
    response_model=KnowledgeBaseResponse,
    summary="Update AI knowledge base content",
)
async def put_knowledge_base(
    request: KnowledgeBasePayload,
    user: Dict[str, Any] = Depends(get_current_user),
) -> KnowledgeBaseResponse:
    _require_admin(user)
    store = OpsStore.create()
    return KnowledgeBaseResponse(**store.save_knowledge_base(request.content))


@router.get(
    "/admin/api-keys",
    response_model=List[ApiKeyRecord],
    summary="List configured Resident Agent secrets",
)
async def list_api_keys(
    user: Dict[str, Any] = Depends(get_current_user),
) -> List[ApiKeyRecord]:
    _require_admin(user)
    store = OpsStore.create()
    return [ApiKeyRecord(**item) for item in store.list_api_keys()]


@router.put(
    "/admin/api-keys/{env_name}",
    response_model=ApiKeyRecord,
    summary="Update a Resident Agent secret",
)
async def update_api_key(
    env_name: str,
    request: ApiKeyUpdateRequest,
    user: Dict[str, Any] = Depends(get_current_user),
) -> ApiKeyRecord:
    _require_admin(user)
    store = OpsStore.create()
    try:
        updated = store.update_api_key(env_name.upper(), request.value)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key entry not found")
    return ApiKeyRecord(**updated)


@router.post(
    "/admin/summaries/generate",
    response_model=SummaryResponse,
    summary="Generate operations summary from sessions and handoffs",
)
async def generate_summary(
    request: SummaryGenerateRequest,
    user: Dict[str, Any] = Depends(get_current_user),
) -> SummaryResponse:
    _require_admin(user)
    store = OpsStore.create()
    return SummaryResponse(**store.generate_summary(request.days))
