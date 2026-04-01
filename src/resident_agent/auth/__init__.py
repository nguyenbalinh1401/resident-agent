"""Authentication module - JWT handling and FastAPI dependencies."""

from resident_agent.auth.jwt_handler import JWTHandler
from resident_agent.auth.dependencies import get_current_user, get_pulse_token

__all__ = [
    "JWTHandler",
    "get_current_user",
    "get_pulse_token",
]
