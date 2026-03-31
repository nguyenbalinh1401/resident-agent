"""Authentication schemas for request/response validation."""

from typing import Optional
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """Request model for login endpoint."""

    phone_number: str = Field(
        ...,
        min_length=10,
        max_length=15,
        description="User's phone number",
        examples=["0901234567"],
    )
    password: str = Field(
        ...,
        min_length=1,
        description="User's password",
    )


class TokenResponse(BaseModel):
    """Response model for successful authentication."""

    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration time in seconds")
    refresh_token: Optional[str] = Field(default=None, description="JWT refresh token for long-lived sessions")


class RefreshTokenRequest(BaseModel):
    """Request model for token refresh endpoint."""

    refresh_token: str = Field(..., description="JWT refresh token")


class UserInfo(BaseModel):
    """User information from JWT payload."""

    sub: str = Field(..., description="Subject (phone number)")
    user_id: Optional[str] = Field(default=None, description="User ID from Pulse Backend")
    roles: list[str] = Field(default_factory=list, description="User roles")
    exp: Optional[int] = Field(default=None, description="Token expiration timestamp")


class JWTPayload(BaseModel):
    """Full JWT payload model."""

    sub: str
    user_id: Optional[str] = None
    roles: list[str] = []
    exp: int
    iat: Optional[int] = None
