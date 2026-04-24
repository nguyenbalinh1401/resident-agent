"""Schemas for resident-agent operations endpoints."""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class SessionSummary(BaseModel):
    id: str
    title: Optional[str] = None
    user_id: Optional[str] = None
    user_name: Optional[str] = None
    phone_number: Optional[str] = None
    last_user_message: Optional[str] = None
    last_assistant_message: Optional[str] = None
    last_preview: Optional[str] = None
    handoff_count: int = 0
    status: str = "Active"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class HandoffCreateRequest(BaseModel):
    session_id: Optional[str] = None
    topic: str = Field(..., min_length=3)
    summary: str = Field(..., min_length=10)
    priority: str = Field(default="Normal")
    requested_team: Optional[str] = None


class HandoffUpdateRequest(BaseModel):
    status: Optional[str] = None
    assigned_to: Optional[str] = None
    resolution_note: Optional[str] = None


class HandoffRecord(BaseModel):
    id: str
    session_id: Optional[str] = None
    resident_id: Optional[str] = None
    resident_name: Optional[str] = None
    phone_number: Optional[str] = None
    topic: str
    summary: str
    priority: str
    requested_team: Optional[str] = None
    assigned_to: Optional[str] = None
    status: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    resolution_note: Optional[str] = None


class KnowledgeBasePayload(BaseModel):
    content: str = Field(..., min_length=1)


class KnowledgeBaseResponse(BaseModel):
    path: str
    content: str
    updated_at: str


class ApiKeyUpdateRequest(BaseModel):
    value: str = Field(..., min_length=1)


class ApiKeyRecord(BaseModel):
    id: str
    env_name: str
    provider: str
    description: str
    status: str
    masked_value: str
    updated_at: Optional[str] = None


class SummaryGenerateRequest(BaseModel):
    days: int = Field(default=1, ge=1, le=30)


class SummaryResponse(BaseModel):
    days: int
    generated_at: str
    metrics: Dict[str, Any]
    summary: str
