"""FastAPI dependencies for authentication."""

from typing import Dict, Any
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .jwt_handler import JWTHandler
from ..core.config import Settings


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer()),
    settings: Settings = Depends(lambda: Settings.get())
) -> Dict[str, Any]:
    """FastAPI dependency to extract and validate current user from JWT token.

    Usage:
        @router.get("/protected")
        async def protected_route(user: dict = Depends(get_current_user)):
            return {"user_id": user["user_id"], "role": user["role"]}

    Raises:
        HTTPException: 401 if token is invalid or expired
    """
    handler = JWTHandler(settings)
    token = credentials.credentials

    payload = handler.verify_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )

    # Ensure it's an access token
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type. Please use access token."
        )

    return {
        "user_id": payload["sub"],
        "role": payload.get("role", "resident"),
        "exp": payload["exp"],
        "iat": payload["iat"]
    }


async def get_current_user_id(
    user: Dict[str, Any] = Depends(get_current_user)
) -> str:
    """Extract just the user ID from the current user."""
    return user["user_id"]


async def require_role(roles: list[str]):
    """Dependency factory to require specific roles.

    Usage:
        @router.get("/admin-only")
        async def admin_route(user: dict = Depends(require_role(["admin"]))):
            return user
    """
    async def role_checker(
        user: Dict[str, Any] = Depends(get_current_user)
    ) -> None:
        user_role = user.get("role", "resident")
        if user_role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user_role}' not allowed. Required roles: {roles}"
            )
        return user

    return role_checker
