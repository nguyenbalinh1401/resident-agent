"""FastAPI dependencies for authentication."""

from typing import Optional, Dict, Any, Tuple, AsyncGenerator
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import structlog

from resident_agent.auth.jwt_handler import JWTHandler
from resident_agent.core.config import Settings
from resident_agent.core.exceptions import AuthenticationError
from resident_agent.clients.pulse_client import PulseClient, PulseConfig

logger = structlog.get_logger()

# HTTP Bearer scheme
security = HTTPBearer(
    scheme_name="Bearer",
    description="Resident Agent JWT token",
    auto_error=False,
)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    settings: Settings = Depends(lambda: Settings.get()),
) -> Dict[str, Any]:
    """Get current user from JWT token.

    This dependency extracts and validates the Resident Agent JWT token.

    Args:
        credentials: HTTP Bearer credentials
        settings: Application settings

    Returns:
        User payload dict with fields like 'sub', 'phone_number', etc.

    Raises:
        HTTPException: If token is missing or invalid
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    try:
        jwt_handler = JWTHandler(settings)
        payload = jwt_handler.decode_token(token)

        # Ensure required fields exist
        if "sub" not in payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
                headers={"WWW-Authenticate": "Bearer"},
            )

        logger.debug(
            "user_authenticated",
            user_id=payload.get("sub"),
            phone_number=payload.get("phone_number"),
        )

        return payload

    except AuthenticationError as e:
        logger.warning("authentication_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    settings: Settings = Depends(lambda: Settings.get()),
) -> Optional[Dict[str, Any]]:
    """Get current user from JWT token (optional - returns None if no token).

    Args:
        credentials: HTTP Bearer credentials
        settings: Application settings

    Returns:
        User payload dict or None if no token provided
    """
    if credentials is None:
        return None

    try:
        jwt_handler = JWTHandler(settings)
        return jwt_handler.decode_token(credentials.credentials)
    except AuthenticationError:
        return None


def get_pulse_token(
    x_pulse_token: Optional[str] = Header(
        None,
        alias="X-Pulse-Token",
        description="Pulse Backend JWT token for API access",
    ),
) -> Optional[str]:
    """Extract Pulse Backend token from request headers.

    This is used for passthrough authentication - the Pulse Backend token
    is needed to access Pulse API endpoints on behalf of the user.

    Args:
        x_pulse_token: Pulse JWT token from X-Pulse-Token header

    Returns:
        Pulse token string or None if not provided
    """
    if x_pulse_token:
        logger.debug("pulse_token_provided", token_length=len(x_pulse_token))
    else:
        logger.debug("pulse_token_not_provided")

    return x_pulse_token


async def get_user_with_pulse_token(
    user: Dict[str, Any] = Depends(get_current_user),
    pulse_token: Optional[str] = Depends(get_pulse_token),
) -> Tuple[Dict[str, Any], Optional[str]]:
    """Combined dependency for user + Pulse token.

    Args:
        user: Current user payload
        pulse_token: Optional Pulse Backend token

    Returns:
        Tuple of (user_payload, pulse_token)

    Raises:
        HTTPException: If Pulse token is required but not provided
    """
    return user, pulse_token


async def get_pulse_client(
    user: Dict[str, Any] = Depends(get_current_user),
    pulse_token: Optional[str] = Depends(get_pulse_token),
    settings: Settings = Depends(lambda: Settings.get()),
) -> AsyncGenerator[PulseClient, None]:
    """Create and yield PulseClient with token from user session.

    This dependency:
    1. Extracts token from header or JWT payload
    2. Creates PulseClient with the token
    3. Yields the client for use in endpoints
    4. Cleans up the client after request completes

    Args:
        user: Current user payload from JWT
        pulse_token: Optional Pulse Backend token from header
        settings: Application settings

    Yields:
        PulseClient: Authenticated Pulse client

    Raises:
        HTTPException: If Pulse token is missing
    """
    # Prefer the fresh Pulse token passed by the client. The embedded token in
    # the Resident Agent JWT is kept only as a backward-compatible fallback.
    token = pulse_token

    if not token:
        token = user.get("pulse_token")
        if token:
            logger.warning(
                "pulse_token_fallback_from_ra_jwt",
                user_id=user.get("sub"),
            )

    if not token:
        logger.warning("pulse_token_missing", user_id=user.get("sub"))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Pulse authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    config = PulseConfig(
        base_url=settings.pulse_backend_url,
        token=token,
    )

    client = PulseClient(config)
    await client.__aenter__()

    logger.debug(
        "pulse_client_created",
        user_id=user.get("sub"),
        base_url=settings.pulse_backend_url,
    )

    try:
        yield client
    finally:
        await client.__aexit__(None, None, None)
        logger.debug("pulse_client_closed", user_id=user.get("sub"))
