"""Main FastAPI application entry point for Pulse Chat Services.

This module sets up the FastAPI application with:
- CORS middleware
- API routers
- Health check endpoint
- Error handlers
"""

from contextlib import asynccontextmanager
import logging

import structlog
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from resident_agent.api import router as api_router
from resident_agent.core.config import Settings

# Set root log level from settings
settings = Settings.get()
logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))

# Silence noisy HTTP library loggers
for _name in ("httpcore", "httpcore.http11", "httpcore.http2", "httpx", "openai"):
    logging.getLogger(_name).setLevel(logging.WARNING)

# Configure structured logging — uvicorn-style format with colors
_LEVEL_COLORS = {
    "DEBUG": "\033[36m",     # cyan
    "INFO": "\033[32m",      # green
    "WARNING": "\033[33m",   # yellow
    "ERROR": "\033[31m",     # red
    "CRITICAL": "\033[1;31m",  # bold red
}
_RESET = "\033[0m"
_DIM = "\033[2m"


def _flatten_event(logger, method, event_dict):
    """Flatten structlog event dict into a single colored message line."""
    level = event_dict.get("level", "info").upper()
    color = _LEVEL_COLORS.get(level, "")
    event = event_dict.pop("event", "")
    skip_keys = {"level", "_record", "logger_name", "timestamp"}
    parts = [event] if event else []
    for k, v in sorted(event_dict.items()):
        if k not in skip_keys:
            parts.append(f"{k}={v}")
    msg = " ".join(str(p) for p in parts)
    event_dict.clear()
    event_dict["event"] = f"{color}{level:<8s}{_RESET} {_DIM}{msg}{_RESET}"
    return event_dict


structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        _flatten_event,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.stdlib.render_to_log_kwargs,
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

_handler = logging.StreamHandler()
_handler.setFormatter(logging.Formatter("%(message)s"))
logging.root.handlers = [_handler]

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown events."""
    # Startup
    settings = Settings.get()
    logger.info(
        "application_startup",
        environment=settings.environment,
        port=settings.port,
        redis_url=settings.redis_url,
        pulse_backend_url=settings.pulse_backend_url,
    )

    yield

    # Shutdown
    logger.info("application_shutdown")


# Create FastAPI application
app = FastAPI(
    title="Pulse Chat Services",
    description="Intelligent resident services platform with AI-powered chat",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include API routers
app.include_router(api_router, prefix="/api/v1")


# Exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors with detailed messages."""
    logger.warning("validation_error", path=request.url.path, errors=exc.errors())
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors(), "body": exc.body},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected errors."""
    logger.error("unhandled_exception", path=request.url.path, error=str(exc), exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "An unexpected error occurred",
            "error": str(exc) if Settings.get().environment == "development" else None,
        },
    )


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint for monitoring and load balancers.

    Returns:
        dict: Health status of the service
    """
    settings = Settings.get()
    return {
        "status": "healthy",
        "service": "pulse-chat",
        "environment": settings.environment,
        "version": "2.0.0",
    }


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API information.

    Returns:
        dict: Basic API information and links
    """
    return {
        "name": "Pulse Chat Services",
        "version": "2.0.0",
        "docs": "/docs",
        "health": "/health",
        "api": "/api/v1",
        "endpoints": {
            "auth": {
                "login": "POST /api/v1/auth/login",
                "refresh": "POST /api/v1/auth/refresh",
                "me": "GET /api/v1/auth/me",
            },
            "chat": {
                "send": "POST /api/v1/chat",
                "action": "POST /api/v1/chat/action",
                "stream": "GET /api/v1/chat/stream",
            },
        },
    }


# For running with uvicorn directly
if __name__ == "__main__":
    import uvicorn

    settings = Settings.get()
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.environment == "development",
    )
