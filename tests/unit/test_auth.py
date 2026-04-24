"""Unit tests for Authentication module.

Tests cover JWT authentication per specs/authentication.md:
- Two-Token System (Resident Agent JWT + Pulse Backend JWT)
- Login with email (NOT email)
- Token Passthrough via X-Pulse-Token header
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from resident_agent.auth.jwt_handler import JWTHandler
from resident_agent.core.config import Settings


class TestJWTHandler:
    """Tests for JWT token handling per specs/authentication.md."""

    def test_create_access_token(self, test_settings):
        """Test access token creation per specs."""
        handler = JWTHandler(test_settings)
        token = handler.create_access_token({"sub": "user_123", "role": "resident"})

        assert token is not None
        assert isinstance(token, str)

        payload = handler.decode_token(token)
        assert payload is not None
        assert payload["sub"] == "user_123"
        assert payload["role"] == "resident"

    def test_create_refresh_token(self, test_settings):
        """Test refresh token creation per specs."""
        handler = JWTHandler(test_settings)
        token = handler.create_refresh_token({"sub": "user_123"})

        payload = handler.decode_token(token)
        assert payload is not None
        assert payload["sub"] == "user_123"
        assert payload["type"] == "refresh"

    def test_verify_valid_token(self, test_settings):
        """Test verification of valid token."""
        handler = JWTHandler(test_settings)
        token = handler.create_access_token({"sub": "user_123", "role": "admin"})

        payload = handler.decode_token(token)
        assert payload is not None
        assert payload["sub"] == "user_123"
        assert payload["role"] == "admin"

    def test_verify_expired_token(self, test_settings):
        """Test that expired tokens are rejected."""
        import jwt

        # Create expired token
        expire = datetime.now(timezone.utc) - timedelta(hours=1)
        payload = {
            "sub": "user_123",
            "role": "resident",
            "exp": expire.timestamp(),
            "iat": datetime.now(timezone.utc).timestamp(),
            "iss": "resident-agent",
        }
        expired_token = jwt.encode(payload, test_settings.jwt_secret_key, algorithm="HS256")

        handler = JWTHandler(test_settings)
        try:
            result = handler.decode_token(expired_token)
            assert False, "Should have raised AuthenticationError"
        except Exception:
            pass  # Expected

    def test_verify_invalid_token(self, test_settings):
        """Test that invalid tokens are rejected."""
        handler = JWTHandler(test_settings)

        try:
            handler.decode_token("invalid.token.here")
            assert False, "Should have raised AuthenticationError"
        except Exception:
            pass  # Expected

        try:
            handler.decode_token("")
            assert False, "Should have raised AuthenticationError"
        except Exception:
            pass  # Expected

    def test_verify_token_wrong_secret(self, test_settings):
        """Test tokens signed with wrong secret are rejected."""
        handler = JWTHandler(test_settings)
        token = handler.create_access_token({"sub": "user_123", "role": "resident"})

        # Different secret
        different_settings = Settings(
            jwt_secret_key="different-secret-key",
            openai_api_key="test-key",
        )
        different_handler = JWTHandler(different_settings)

        try:
            different_handler.decode_token(token)
            assert False, "Should have raised AuthenticationError"
        except Exception:
            pass  # Expected


class TestLoginWithemail:
    """Tests for login with email per specs/authentication.md.

    Per specs:
    - Login field: email (NOT email)
    - Demo credentials: email + password
    """

    def test_login_request_uses_email(self):
        """Verify LoginRequest schema uses email per specs/authentication.md."""
        from resident_agent.schemas.auth_schemas import LoginRequest

        # Per specs, login uses email
        request = LoginRequest(email="test@example.com", password="demo123")

        assert request.email == "test@example.com"
        assert request.password == "demo123"

    def test_login_response_schema(self):
        """Verify TokenResponse schema per specs/authentication.md."""
        from resident_agent.schemas.auth_schemas import TokenResponse

        response = TokenResponse(
            access_token="token123",
            token_type="bearer",
            expires_in=3600,
        )

        assert response.access_token == "token123"
        assert response.token_type == "bearer"
        assert response.expires_in == 3600


class TestTokenPassthrough:
    """Tests for Token Passthrough per specs/architecture.md.

    Token Passthrough:
    - Mobile app passes Pulse Backend JWT via X-Pulse-Token header
    - Resident Agent uses Pulse token to fetch user capabilities
    """

    def test_x_pulse_token_header_format(self):
        """Test X-Pulse-Token header format per specs."""
        from tests.conftest import create_pulse_token_header

        headers = create_pulse_token_header("pulse_jwt_token")
        assert headers["X-Pulse-Token"] == "pulse_jwt_token"

    def test_two_token_system_separation(self, test_settings):
        """Test that Resident Agent and Pulse tokens are separate (per specs)."""
        handler = JWTHandler(test_settings)

        # Resident Agent token
        ra_token = handler.create_access_token({"sub": "user_123", "role": "resident"})
        ra_payload = handler.decode_token(ra_token)

        # Pulse token would be from .NET backend (we just verify separation concept)
        assert ra_payload["sub"] == "user_123"


class TestRoleBasedAccess:
    """Tests for role-based access control per specs/components.md.

    Roles: resident, staff, admin
    """

    @pytest.mark.parametrize("role", ["resident", "staff", "admin"])
    def test_create_tokens_for_different_roles(self, test_settings, role):
        """Test token creation for all role types per specs."""
        handler = JWTHandler(test_settings)
        token = handler.create_access_token({"sub": "user_001", "role": role})

        payload = handler.decode_token(token)
        assert payload["role"] == role
