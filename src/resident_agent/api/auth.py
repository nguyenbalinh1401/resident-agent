"""Authentication API endpoints."""

from datetime import timedelta
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, status, Depends
import structlog

from resident_agent.schemas.auth_schemas import LoginRequest, TokenResponse
from resident_agent.auth.jwt_handler import JWTHandler
from resident_agent.auth.dependencies import get_current_user, get_pulse_token
from resident_agent.core.config import Settings
from resident_agent.clients.pulse_client import PulseClient, PulseConfig, PulseAPIError

logger = structlog.get_logger()

router = APIRouter()


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login to Resident Agent",
    description="Authenticate using phone number and password. Validates against Pulse Backend.",
)
async def login(request: LoginRequest) -> TokenResponse:
    """Login endpoint that validates against Pulse Backend.

    This endpoint:
    1. Validates credentials against Pulse Backend
    2. Issues a Resident Agent JWT token

    Args:
        request: Login request with email and password

    Returns:
        TokenResponse with access_token

    Raises:
        HTTPException: If authentication fails
    """
    settings = Settings.get()
    logger.info("login_attempt", email=request.email)

    # Validate against Pulse Backend
    pulse_config = PulseConfig(base_url=settings.pulse_backend_url)

    try:
        async with PulseClient(pulse_config) as client:
            login_response = await client.login(
                email=request.email,
                password=request.password,
            )

            logger.info(
                "pulse_login_success",
                user_id=login_response.user_id,
                role=login_response.role,
            )

            # Fetch user permissions from Pulse Backend
            permissions = []
            try:
                permissions = await client.get_permissions()
                logger.info("permissions_fetched", count=len(permissions))
            except PulseAPIError as e:
                logger.warning("permissions_fetch_failed", error=str(e))
                # Continue without permissions - user will have basic access only

            # If user is Admin, ensure they have wildcard permission for all tools
            if login_response.role == "Admin":
                logger.info("admin_role_detected_injecting_wildcard_permission")
                # Check if wildcard already exists, if not add it
                if not any(p.get("resource") == "*" for p in permissions):
                    permissions.append({"resource": "*", "action": "*"})

            # Create Resident Agent JWT with user info
            jwt_handler = JWTHandler(settings)

            # Include user info in token payload
            token_data = {
                "sub": login_response.user_id,
                "name": login_response.full_name,
                "email": login_response.email,
                "role": login_response.role,
                "pulse_token": login_response.token,  # Store Pulse token for later use
                "permissions": permissions,
            }

            access_token = jwt_handler.create_access_token(token_data)

            return TokenResponse(
                access_token=access_token,
                token_type="bearer",
                expires_in=jwt_handler.get_access_token_expires_in(),
            )

    except PulseAPIError as e:
        logger.warning(
            "pulse_login_failed",
            email=request.email,
            status_code=e.status_code,
            error=str(e),
        )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    except Exception as e:
        logger.error("login_error", error=str(e), exc_info=True)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during login",
        )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
    description="Get a new access token using refresh token.",
)
async def refresh_token(
    user: Dict[str, Any] = Depends(get_current_user),
    pulse_token: Optional[str] = Depends(get_pulse_token),
) -> TokenResponse:
    """Refresh access token.

    Args:
        user: Current user from JWT

    Returns:
        New TokenResponse
    """
    settings = Settings.get()
    jwt_handler = JWTHandler(settings)

    resolved_pulse_token = pulse_token or user.get("pulse_token")

    if pulse_token:
        logger.info("refresh_using_header_pulse_token", user_id=user.get("sub"))
    elif resolved_pulse_token:
        logger.warning("refresh_fallback_embedded_pulse_token", user_id=user.get("sub"))

    # Create new token with same user data
    token_data = {
        "sub": user.get("sub"),
        "name": user.get("name"),
        "email": user.get("email"),
        "role": user.get("role"),
        "pulse_token": resolved_pulse_token,
        "permissions": user.get("permissions", []),
    }

    access_token = jwt_handler.create_access_token(token_data)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=jwt_handler.get_access_token_expires_in(),
    )


@router.get(
    "/me",
    summary="Get current user",
    description="Get current authenticated user information.",
)
async def get_me(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Get current user info.

    Args:
        user: Current user from JWT

    Returns:
        User payload
    """
    # Remove sensitive data
    return {
        "user_id": user.get("sub"),
        "name": user.get("name"),
        "email": user.get("email"),
        "role": user.get("role"),
        "permissions": user.get("permissions", []),
    }
