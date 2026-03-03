"""Pydantic models for authentication."""

from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class Token(BaseModel):
    """JWT token response model."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # Seconds until expiration


class TokenData(BaseModel):
    """Decoded token payload data."""
    user_id: str
    role: str
    exp: int
    iat: int
    type: str  # access or refresh


class UserLogin(BaseModel):
    """User login request model."""
    email: EmailStr
    password: str


class UserCreate(BaseModel):
    """User registration request model."""
    email: EmailStr
    password: str
    name: Optional[str] = None
    role: str = "resident"
    unit_id: Optional[str] = None


class UserResponse(BaseModel):
    """User response model."""
    id: str
    email: str
    name: Optional[str] = None
    role: str
    unit_id: Optional[str] = None
    created_at: datetime
