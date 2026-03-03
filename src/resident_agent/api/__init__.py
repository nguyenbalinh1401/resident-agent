"""API module with FastAPI routers."""

from fastapi import APIRouter
from .auth import router as auth_router
from .chat import router as chat_router
from .sse import router as sse_router

# Create main API router
router = APIRouter()

# Include sub-routers
router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
router.include_router(chat_router, prefix="/chat", tags=["Chat"])
router.include_router(sse_router, prefix="/stream", tags=["SSE Streaming"])

__all__ = ["router"]
