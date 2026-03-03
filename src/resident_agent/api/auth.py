"""Authentication API endpoints for login and token refresh."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from ..schemas.auth_schemas import LoginRequest, LoginResponse
from ..auth.jwt_handler import JWTHandler
from ..core.config import Settings

router = APIRouter()
security = HTTPBearer()


@router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    settings: Settings = Depends(lambda: Settings.get())
) -> LoginResponse:
    """Login endpoint to get access and refresh tokens.

    Demo credentials:
    - Email: demo@example.com
    - Password: demo123

    Returns:
        LoginResponse with access_token, refresh_token, and expires_in
    """
    # Verify credentials (mock implementation - replace with database lookup in production)
    if request.email == settings.demo_email and request.password == settings.demo_password:
        handler = JWTHandler(settings)
        access_token = handler.create_access_token("user_123", "resident")
        refresh_token = handler.create_refresh_token("user_123")

        return LoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.access_token_expire_minutes * 60
        )

    # Invalid credentials
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials"
    )


@router.post("/refresh", response_model=LoginResponse)
async def refresh_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    settings: Settings = Depends(lambda: Settings.get())
) -> LoginResponse:
    """Refresh access token using a valid refresh token.

    Returns:
        LoginResponse with new access_token
    """
    handler = JWTHandler(settings)
    payload = handler.verify_token(credentials.credentials)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type. Please use refresh token."
        )

    # Create new access token
    new_access_token = handler.create_access_token(
        payload["sub"],
        payload.get("role", "resident")
    )

    return LoginResponse(
        access_token=new_access_token,
        refresh_token=credentials.credentials,  # Return same refresh token
        expires_in=settings.access_token_expire_minutes * 60
    )


@router.post("/logout")
async def logout(
    user: dict = Depends(lambda: Depends(lambda: Settings.get()) and Depends(lambda: None))
) -> dict:
    """Logout endpoint to invalidate tokens.

    Note: In production, this would add the token to a blacklist.
    For now, just returns success message.
    """
    return {"message": "Logged out successfully", "user_id": user.get("user_id") if user else None}
