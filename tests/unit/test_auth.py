"""Unit tests for authentication module."""

import pytest
from datetime import datetime, timedelta
import time

from resident_agent.auth.jwt_handler import JWTHandler
from resident_agent.auth.models import Token, TokenData, UserLogin, UserCreate


class TestJWTHandler:
    """Tests for JWT token generation and validation."""

    def test_create_access_token(self, jwt_handler):
        """Test access token creation."""
        token = jwt_handler.create_access_token("user_123", "resident")

        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_refresh_token(self, jwt_handler):
        """Test refresh token creation."""
        token = jwt_handler.create_refresh_token("user_123")

        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 1

    def test_verify_valid_access_token(self, jwt_handler):
        """Test verification of valid access token."""
        token = jwt_handler.create_access_token("user_456", "staff")
        payload = jwt_handler.verify_token(token)

        assert payload is not None
        assert payload["sub"] == "user_456"
        assert payload["role"] == "staff"
        assert payload["type"] == "access"

    def test_verify_valid_refresh_token(self, jwt_handler):
        """Test verification of valid refresh token."""
        token = jwt_handler.create_refresh_token("user_789")
        payload = jwt_handler.verify_token(token)

        assert payload is not None
        assert payload["sub"] == "user_789"
        assert payload["type"] == "refresh"

    def test_verify_invalid_token(self, jwt_handler):
        """Test verification of invalid token."""
        payload = jwt_handler.verify_token("invalid_token_here")
        assert payload is None

    def test_verify_malformed_token(self, jwt_handler):
        """Test verification of malformed token."""
        payload = jwt_handler.verify_token("not.a.valid.token")
        assert payload is None

    def test_password_hashing(self, jwt_handler):
        """Test password hashing and verification."""
        password = "my_secure_password_123"
        hashed = jwt_handler.hash_password(password)

        assert hashed is not None
        assert hashed != password  # Should be different
        assert jwt_handler.verify_password(password, hashed) is True
        assert jwt_handler.verify_password("wrong_password", hashed) is False

    def test_different_passwords_have_different_hashes(self, jwt_handler):
        """Test that different passwords produce different hashes."""
        hash1 = jwt_handler.hash_password("password1")
        hash2 = jwt_handler.hash_password("password2")

        assert hash1 != hash2

    def test_token_with_additional_claims(self, jwt_handler):
        """Test token creation with additional claims."""
        additional_claims = {
            "unit_id": "A-1201",
            "building_id": "pulse-tower"
        }
        token = jwt_handler.create_access_token(
            "user_999",
            "resident",
            additional_claims
        )
        payload = jwt_handler.verify_token(token)

        assert payload is not None
        assert payload["unit_id"] == "A-1201"
        assert payload["building_id"] == "pulse-tower"


class TestAuthModels:
    """Tests for Pydantic models in auth module."""

    def test_user_login_model(self):
        """Test UserLogin model validation."""
        login = UserLogin(email="test@example.com", password="password123")

        assert login.email == "test@example.com"
        assert login.password == "password123"

    def test_token_model(self):
        """Test Token model."""
        token = Token(
            access_token="access_token_value",
            refresh_token="refresh_token_value",
            token_type="bearer",
            expires_in=900
        )

        assert token.access_token == "access_token_value"
        assert token.refresh_token == "refresh_token_value"
        assert token.token_type == "bearer"
        assert token.expires_in == 900

    def test_user_create_model(self):
        """Test UserCreate model validation."""
        user = UserCreate(
            email="new@example.com",
            password="secure_password",
            name="Test User",
            role="resident"
        )

        assert user.email == "new@example.com"
        assert user.name == "Test User"
        assert user.role == "resident"
