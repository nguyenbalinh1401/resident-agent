"""API module - FastAPI routers for endpoints."""

from fastapi import APIRouter

from resident_agent.api.auth import router as auth_router
from resident_agent.api.chat import router as chat_router
from resident_agent.api.ops import router as ops_router
from resident_agent.api.sse import router as sse_router

# Main API router that combines all sub-routers
router = APIRouter()

# Include sub-routers with their prefixes
router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
router.include_router(chat_router, prefix="/chat", tags=["Chat"])
router.include_router(ops_router, tags=["Operations"])
router.include_router(sse_router, tags=["Streaming"])

__all__ = ["router"]
