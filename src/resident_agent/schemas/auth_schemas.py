"""Pydantic models for authentication requests and responses."""

from pydantic import BaseModel, EmailStr
from typing import Optional


class LoginRequest(BaseModel):
    """Request model for user login."""
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    """Response model for successful login."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # Seconds until expiration


class RefreshRequest(BaseModel):
    """Request model for token refresh."""
    refresh_token: str


class RefreshResponse(BaseModel):
    """Response model for token refresh."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    """Response model for user data."""
    id: str
    email: str
    name: Optional[str] = None
    role: str
    unit_id: Optional[str] = None
