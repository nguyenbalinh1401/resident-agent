"""Integration tests for API endpoints."""

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient
import asyncio

from main import app
from resident_agent.core.config import Settings
from resident_agent.auth.jwt_handler import JWTHandler


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def auth_token():
    """Generate auth token for testing."""
    settings = Settings.get()
    handler = JWTHandler(settings)
    return handler.create_access_token("test_user_123", "resident")


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    def test_health_check(self, client: TestClient):
        """Test health check endpoint."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "pulse-chat"

    def test_root_endpoint(self, client: TestClient):
        """Test root endpoint."""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "docs" in data


class TestAuthEndpoints:
    """Tests for authentication endpoints."""

    def test_login_success(self, client: TestClient):
        """Test successful login."""
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "demo@example.com",
                "password": "demo123"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert "expires_in" in data

    def test_login_invalid_credentials(self, client: TestClient):
        """Test login with invalid credentials."""
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "demo@example.com",
                "password": "wrong_password"
            }
        )

        assert response.status_code == 401

    def test_login_invalid_email(self, client: TestClient):
        """Test login with invalid email format."""
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "invalid_email",
                "password": "password"
            }
        )

        assert response.status_code == 422  # Validation error

    def test_refresh_token(self, client: TestClient):
        """Test token refresh."""
        # First login to get refresh token
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "demo@example.com",
                "password": "demo123"
            }
        )
        refresh_token = login_response.json()["refresh_token"]

        # Use refresh token to get new access token
        response = client.post(
            "/api/v1/auth/refresh",
            headers={"Authorization": f"Bearer {refresh_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data

    def test_refresh_with_access_token_fails(self, client: TestClient):
        """Test that using access token for refresh fails."""
        # Login to get access token
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "demo@example.com",
                "password": "demo123"
            }
        )
        access_token = login_response.json()["access_token"]

        # Try to use access token for refresh
        response = client.post(
            "/api/v1/auth/refresh",
            headers={"Authorization": f"Bearer {access_token}"}
        )

        assert response.status_code == 401


class TestChatEndpoints:
    """Tests for chat endpoints."""

    def test_chat_without_auth(self, client: TestClient):
        """Test chat endpoint without authentication."""
        response = client.post(
            "/api/v1/chat",
            json={"message": "xin chào"}
        )

        assert response.status_code == 401  # Unauthorized

    def test_chat_with_auth(self, client: TestClient, auth_token: str):
        """Test chat endpoint with authentication."""
        response = client.post(
            "/api/v1/chat",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"message": "xin chào"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert len(data["message"]) > 0

    def test_chat_greeting(self, client: TestClient, auth_token: str):
        """Test chat with greeting message."""
        response = client.post(
            "/api/v1/chat",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"message": "hello"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "message" in data

    def test_chat_with_session_id(self, client: TestClient, auth_token: str):
        """Test chat with custom session ID."""
        response = client.post(
            "/api/v1/chat",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "message": "test message",
                "session_id": "custom_session_123"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data

    def test_chat_empty_message(self, client: TestClient, auth_token: str):
        """Test chat with empty message."""
        response = client.post(
            "/api/v1/chat",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"message": ""}
        )

        # API handles empty message and returns 200 with default response
        assert response.status_code == 200


class TestSSEEndpoints:
    """Tests for SSE streaming endpoints."""

    def test_sse_stream_without_auth(self, client: TestClient):
        """Test SSE endpoint without authentication."""
        response = client.get(
            "/api/v1/stream/chat",
            params={"message": "test"}
        )

        assert response.status_code == 401  # Unauthorized

    def test_sse_stream_with_auth(self, client: TestClient, auth_token: str):
        """Test SSE endpoint with authentication."""
        with client.stream(
            "GET",
            "/api/v1/stream/chat",
            params={"message": "xin chào"},
            headers={"Authorization": f"Bearer {auth_token}"}
        ) as response:
            assert response.status_code == 200
            assert "text/event-stream" in response.headers.get("content-type", "")


class TestOpenAPI:
    """Tests for OpenAPI documentation."""

    def test_docs_endpoint(self, client: TestClient):
        """Test that docs endpoint is accessible."""
        response = client.get("/docs")
        assert response.status_code == 200

    def test_openapi_json(self, client: TestClient):
        """Test OpenAPI JSON schema."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "paths" in data

    def test_redoc_endpoint(self, client: TestClient):
        """Test that redoc endpoint is accessible."""
        response = client.get("/redoc")
        assert response.status_code == 200
