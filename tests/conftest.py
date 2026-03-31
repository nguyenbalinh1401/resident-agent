"""Pytest configuration and fixtures for Resident Agent tests.

Fixtures and test configuration per specs:
- specs/authentication.md - JWT token system (phoneNumber login, no refresh in specs)
- specs/api-reference.md - API endpoints (/auth/login, /chat, /chat/stream, /action)
- specs/cux.md - CUX orchestrator (3 intent types)
"""

import os
from typing import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# Test environment setup
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing-only")
os.environ.setdefault("OPENAI_API_KEY", "test-openai-api-key")
os.environ.setdefault("DEMO_PHONE_NUMBER", "0901234567")
os.environ.setdefault("DEMO_PASSWORD", "demo123")


# =============================================================================
# Settings Fixtures (per specs/authentication.md)
# =============================================================================

@pytest.fixture
def test_settings():
    """Create test settings per specs/authentication.md.

    Note: Login uses phoneNumber, NOT email.
    """
    from dataclasses import dataclass

    @dataclass
    class TestSettings:
        jwt_secret_key: str = "test-secret-key-for-testing-only"
        openai_api_key: str = "test-openai-api-key"
        openai_api_base_url: str = ""
        openai_model: str = "gpt-4o-mini"
        openai_temperature: float = 0.0
        openai_max_tokens: int = 1000
        jwt_access_token_expire_minutes: int = 30
        jwt_refresh_token_expire_days: int = 7
        environment: str = "test"
        host: str = "localhost"
        port: int = 8000
        pulse_backend_url: str = "http://localhost:5000"
        pulse_backend_timeout: float = 30.0
        redis_url: str = "redis://localhost:6379/0"
        redis_prefix: str = "pulse:chat:"
        redis_session_ttl: int = 3600
        max_history_length: int = 10
        session_timeout_seconds: int = 3600
        max_actions_per_response: int = 4
        actions_cache_ttl_seconds: int = 300

    return TestSettings()


# =============================================================================
# JWT Token Fixtures (per specs/authentication.md - Two-Token System)
# =============================================================================

@pytest.fixture
def jwt_handler(test_settings):
    """Create JWT handler for token creation."""
    from resident_agent.auth.jwt_handler import JWTHandler
    return JWTHandler(test_settings)


@pytest.fixture
def access_token(jwt_handler):
    """Create valid Resident Agent access token (per specs/authentication.md)."""
    return jwt_handler.create_access_token({"sub": "user_123", "role": "resident"})


@pytest.fixture
def admin_token(jwt_handler):
    """Create admin access token for testing."""
    return jwt_handler.create_access_token({"sub": "admin_001", "role": "admin"})


@pytest.fixture
def staff_token(jwt_handler):
    """Create staff access token for testing."""
    return jwt_handler.create_access_token({"sub": "staff_001", "role": "staff"})


@pytest.fixture
def pulse_token():
    """Mock Pulse Backend JWT token (per specs/authentication.md).

    This is a token from Pulse Backend (.NET), passed via X-Pulse-Token header.
    Used for Token Passthrough to fetch user permissions.
    """
    return "pulse_backend_jwt_token_for_passthrough"


# =============================================================================
# Test Client Fixtures
# =============================================================================

@pytest.fixture
def test_client(test_settings) -> Generator[TestClient, None, None]:
    """Create test client with mocked settings and state manager."""
    with patch("resident_agent.core.config.Settings.get", return_value=test_settings):
        # Mock StateManager to avoid Redis connection
        mock_state_manager = MagicMock()
        mock_state_manager.connect = AsyncMock()
        mock_state_manager.add_message = AsyncMock()
        mock_state_manager.get_history = AsyncMock(return_value=[])
        mock_state_manager.get_history_for_llm = AsyncMock(return_value=[])

        with patch("resident_agent.cux.orchestrator.StateManager", return_value=mock_state_manager):
            from main import app
            with TestClient(app) as client:
                yield client


# =============================================================================
# Mock Fixtures
# =============================================================================

@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for testing without real API calls (per specs/cux.md)."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = '{"intent_type": "chitchat", "category": "chitchat", "confidence": 0.9}'
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
    return mock_client


@pytest.fixture
def mock_pulse_backend():
    """Mock Pulse Backend API responses (per specs/architecture.md)."""
    mock = MagicMock()
    mock.get_user_roles = AsyncMock(return_value={
        "roles": [{"name": "resident"}],
        "effectiveCapabilities": [
            "REPORT_INCIDENT",
            "CHECK_PACKAGE",
            "VIEW_BILLS",
            "BOOK_AMENITY",
            "SERVICE_REQUEST",
        ]
    })
    return mock


# =============================================================================
# Sample Data Factories (per specs/api-reference.md)
# =============================================================================

class ChatRequestFactory:
    """Factory for creating chat request payloads per specs/api-reference.md."""

    @staticmethod
    def greeting() -> dict:
        return {"message": "Xin chào", "session_id": "test_session_123"}

    @staticmethod
    def incident_report() -> dict:
        return {"message": "Báo sự cố vòi nước rò rỉ", "session_id": "test_session_123"}

    @staticmethod
    def package_check() -> dict:
        return {"message": "Kiểm tra bưu kiện", "session_id": "test_session_123"}

    @staticmethod
    def bill_view() -> dict:
        return {"message": "Xem hóa đơn tháng này", "session_id": "test_session_123"}

    @staticmethod
    def amenity_booking() -> dict:
        return {"message": "Đặt chỗ bể bơi", "session_id": "test_session_123"}

    @staticmethod
    def service_request() -> dict:
        return {"message": "Đăng ký thẻ cư dân", "session_id": "test_session_123"}

    @staticmethod
    def with_attachment() -> dict:
        """Multimodal input per specs/cux.md."""
        return {
            "message": "Báo sự cố với hình ảnh",
            "session_id": "test_session_123",
            "attachments": [{
                "type": "image",
                "data": "base64_encoded_data",
                "mime_type": "image/jpeg"
            }]
        }

    @staticmethod
    def custom(message: str, session_id: str = "test_session_123") -> dict:
        return {"message": message, "session_id": session_id}


@pytest.fixture
def chat_request_factory() -> ChatRequestFactory:
    return ChatRequestFactory()


# =============================================================================
# Helper Functions
# =============================================================================

def create_auth_header(token: str) -> dict:
    """Create Authorization header (per specs/authentication.md)."""
    return {"Authorization": f"Bearer {token}"}


def create_pulse_token_header(pulse_token: str) -> dict:
    """Create X-Pulse-Token header for Token Passthrough (per specs/architecture.md)."""
    return {"X-Pulse-Token": pulse_token}
