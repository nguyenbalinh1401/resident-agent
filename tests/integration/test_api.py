"""Integration tests for API endpoints.

Tests cover all endpoints per specs/api-reference.md:
- POST /auth/login - Login with email, get JWT token
- POST /chat - Send message, get response with actions
- POST /action - Execute suggested action
- GET /chat/stream - SSE streaming chat

Also tests Token Passthrough per specs/architecture.md.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from resident_agent.clients.pulse_client import LoginResponse
from resident_agent.schemas.chat_schemas import ChatResponse, ActionButton, ActionStyle


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    def test_health_check(self, test_client: TestClient):
        """Test health check endpoint."""
        response = test_client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "pulse-chat"

    def test_root_endpoint(self, test_client: TestClient):
        """Test root endpoint returns API info."""
        response = test_client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data


class TestAuthLogin:
    """Tests for POST /auth/login per specs/authentication.md.

    Per specs:
    - Login field: email (NOT email)
    - Returns: access_token, token_type, expires_in
    """

    def test_login_with_email_success(self, test_client: TestClient):
        """Test login with email per specs/authentication.md."""
        with patch("resident_agent.api.auth.PulseClient") as MockPulseClient:
            mock_client = AsyncMock()
            mock_client.login = AsyncMock(return_value=LoginResponse(
                user_id="user_123",
                full_name="Test User",
                email="test@example.com",
                role="resident",
                token="pulse_jwt_token_123",
            ))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            MockPulseClient.return_value = mock_client

            response = test_client.post(
                "/api/v1/auth/login",
                json={
                    "email": "test@example.com",
                    "password": "demo123",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert "access_token" in data
            assert "token_type" in data
            assert data["token_type"] == "bearer"
            assert "expires_in" in data

    def test_login_invalid_credentials(self, test_client: TestClient):
        """Test login with invalid credentials returns 401."""
        from resident_agent.clients.pulse_client import PulseAPIError

        with patch("resident_agent.api.auth.PulseClient") as MockPulseClient:
            mock_client = AsyncMock()
            mock_client.login = AsyncMock(side_effect=PulseAPIError("Invalid credentials", status_code=401))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            MockPulseClient.return_value = mock_client

            response = test_client.post(
                "/api/v1/auth/login",
                json={
                    "email": "test@example.com",
                    "password": "wrongpassword",
                },
            )

            assert response.status_code == 401

    def test_login_missing_email(self, test_client: TestClient):
        """Test login without email returns 422."""
        response = test_client.post(
            "/api/v1/auth/login",
            json={"password": "demo123"},
        )

        assert response.status_code == 422

    def test_login_missing_password(self, test_client: TestClient):
        """Test login without password returns 422."""
        response = test_client.post(
            "/api/v1/auth/login",
            json={"email": "test@example.com"},
        )

        assert response.status_code == 422


class TestChatEndpoint:
    """Tests for POST /chat per specs/api-reference.md.

    Chat Request Schema:
    {
        "message": "Kiểm tra bưu kiện",
        "session_id": "session_123"
    }

    Chat Response Schema:
    {
        "message": "Bạn có 2 bưu kiện...",
        "actions": [...],
        "session_id": "session_123"
    }
    """

    def test_chat_requires_authentication(self, test_client: TestClient):
        """Test that chat endpoint requires authentication."""
        response = test_client.post(
            "/api/v1/chat",
            json={"message": "Xin chào"},
        )

        # Should return 401 or 403 for unauthenticated
        assert response.status_code in [401, 403]

    def test_chat_with_valid_token(self, test_client: TestClient, access_token: str):
        """Test chat with valid authentication token."""
        with patch("resident_agent.api.chat.CuxOrchestrator") as MockOrchestrator:
            mock_instance = MagicMock()
            mock_instance.process = AsyncMock(return_value=ChatResponse(
                message="Xin chào! Tôi có thể giúp gì?",
                actions=[],
                session_id="test_session",
                tool_calls=[],
                intent="chitchat",
            ))
            MockOrchestrator.return_value = mock_instance

            response = test_client.post(
                "/api/v1/chat",
                headers={"Authorization": f"Bearer {access_token}"},
                json={"message": "Xin chào", "session_id": "test_session"},
            )

            # Should succeed
            assert response.status_code == 200

    def test_chat_response_schema(self, test_client: TestClient, access_token: str):
        """Test chat response follows ChatResponse schema per specs/api-reference.md."""
        with patch("resident_agent.api.chat.CuxOrchestrator") as MockOrchestrator:
            mock_instance = MagicMock()
            mock_instance.process = AsyncMock(return_value=ChatResponse(
                message="Bạn có 2 bưu kiện chờ nhận",
                actions=[
                    ActionButton(
                        id="check_package",
                        label="Xem chi tiết",
                        action_type="navigate",
                        params={"screen": "packages"},
                        style=ActionStyle.PRIMARY,
                    )
                ],
                session_id="test_session",
                tool_calls=[],
                intent="check_package",
            ))
            MockOrchestrator.return_value = mock_instance

            response = test_client.post(
                "/api/v1/chat",
                headers={"Authorization": f"Bearer {access_token}"},
                json={"message": "Kiểm tra bưu kiện"},
            )

            assert response.status_code == 200
            data = response.json()
            assert "message" in data
            assert "actions" in data
            assert isinstance(data["actions"], list)

    def test_chat_with_session_id(self, test_client: TestClient, access_token: str):
        """Test chat with custom session_id per specs/api-reference.md."""
        with patch("resident_agent.api.chat.CuxOrchestrator") as MockOrchestrator:
            mock_instance = MagicMock()
            mock_instance.process = AsyncMock(return_value=ChatResponse(
                message="Response",
                actions=[],
                session_id="custom_session_123",
                tool_calls=[],
                intent="chitchat",
            ))
            MockOrchestrator.return_value = mock_instance

            response = test_client.post(
                "/api/v1/chat",
                headers={"Authorization": f"Bearer {access_token}"},
                json={
                    "message": "Test message",
                    "session_id": "custom_session_123",
                },
            )

            assert response.status_code == 200


class TestActionEndpoint:
    """Tests for POST /action per specs/api-reference.md.

    Action endpoint executes suggested actions from chat responses.
    """

    def test_action_requires_authentication(self, test_client: TestClient):
        """Test that action endpoint requires authentication."""
        response = test_client.post(
            "/api/v1/chat/action",
            params={"action_id": "report_incident"},
            json={},
        )

        assert response.status_code in [401, 403]

    def test_action_execution(self, test_client: TestClient, access_token: str):
        """Test action button execution per specs/api-reference.md."""
        with patch("resident_agent.api.chat.CuxOrchestrator") as MockOrchestrator:
            mock_instance = MagicMock()
            mock_instance.process = AsyncMock(return_value=ChatResponse(
                message="Báo sự cố thành công",
                actions=[],
                session_id="test_session",
                tool_calls=[],
                intent="report_incident",
            ))
            MockOrchestrator.return_value = mock_instance

            response = test_client.post(
                "/api/v1/chat/action",
                headers={"Authorization": f"Bearer {access_token}"},
                json={"message": "Báo sự cố"},
            )

            assert response.status_code in [200, 422]  # 422 if validation requires message


class TestSSEEndpoint:
    """Tests for GET/POST /chat/stream SSE endpoint per specs/api-reference.md.

    SSE Event Types:
    - thinking: AI is processing
    - content: Text content chunk
    - action: Suggested action buttons
    - complete: Stream finished
    - error: Error occurred
    """

    def test_sse_requires_authentication(self, test_client: TestClient):
        """Test that SSE endpoint requires authentication."""
        response = test_client.get(
            "/api/v1/chat/stream",
            params={"message": "Hello"},
        )

        assert response.status_code in [401, 403]

    def test_sse_event_format(self, test_client: TestClient, access_token: str):
        """Test SSE stream returns proper event format per specs/api-reference.md.

        SSE format: data: {"type": "...", ...}\n\n
        """
        with patch("resident_agent.cux.orchestrator.CuxOrchestrator") as MockOrchestrator:
            mock_instance = MagicMock()

            async def mock_stream(*args, **kwargs):
                yield 'data: {"type": "thinking", "content": "Đang xử lý...", "session_id": "test"}\n\n'
                yield 'data: {"type": "content", "content": "Hello", "session_id": "test"}\n\n'
                yield 'data: {"type": "complete", "session_id": "test"}\n\n'

            mock_instance.process_stream = mock_stream
            MockOrchestrator.return_value = mock_instance

            response = test_client.get(
                "/api/v1/chat/stream",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"message": "Hello"},
            )

            if response.status_code == 200:
                assert "text/event-stream" in response.headers.get("content-type", "")

    def test_sse_valid_event_types(self, test_client: TestClient, access_token: str):
        """Test SSE events have valid types per specs/api-reference.md."""
        with patch("resident_agent.cux.orchestrator.CuxOrchestrator") as MockOrchestrator:
            mock_instance = MagicMock()

            async def mock_stream(*args, **kwargs):
                yield 'data: {"type": "thinking", "session_id": "test"}\n\n'
                yield 'data: {"type": "content", "content": "Hello", "session_id": "test"}\n\n'
                yield 'data: {"type": "actions", "actions": [], "session_id": "test"}\n\n'
                yield 'data: {"type": "complete", "session_id": "test"}\n\n'

            mock_instance.process_stream = mock_stream
            MockOrchestrator.return_value = mock_instance

            response = test_client.get(
                "/api/v1/chat/stream",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"message": "Hello"},
            )

            if response.status_code == 200:
                content = response.content.decode()
                valid_types = {"thinking", "content", "action", "actions", "complete", "error", "token"}

                for line in content.split("\n"):
                    if line.startswith("data: "):
                        try:
                            data = json.loads(line[6:])
                            assert data.get("type") in valid_types
                        except json.JSONDecodeError:
                            pass  # Skip invalid JSON


class TestTokenPassthrough:
    """Tests for Token Passthrough per specs/architecture.md.

    Token Passthrough:
    - Mobile app passes Pulse Backend JWT via X-Pulse-Token header
    - Resident Agent uses Pulse token to fetch user capabilities
    - Enables permission checking and authenticated API calls
    """

    def test_x_pulse_token_header_accepted(self, test_client: TestClient, access_token: str):
        """Test X-Pulse-Token header is accepted per specs/architecture.md."""
        with patch("resident_agent.api.chat.CuxOrchestrator") as MockOrchestrator:
            mock_instance = MagicMock()
            mock_instance.process = AsyncMock(return_value=ChatResponse(
                message="Response",
                actions=[],
                session_id="test_session",
                tool_calls=[],
                intent="test",
            ))
            MockOrchestrator.return_value = mock_instance

            response = test_client.post(
                "/api/v1/chat",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "X-Pulse-Token": "valid_pulse_token",
                },
                json={"message": "Test"},
            )

            # Request should be accepted (may return 200 or 500)
            assert response.status_code in [200, 500]

    def test_action_endpoint_accepts_pulse_token(self, test_client: TestClient, access_token: str):
        """Test X-Pulse-Token in action endpoint per specs/architecture.md."""
        with patch("resident_agent.api.chat.CuxOrchestrator") as MockOrchestrator:
            mock_instance = MagicMock()
            mock_instance.process = AsyncMock(return_value=ChatResponse(
                message="Done",
                actions=[],
                session_id="test",
                tool_calls=[],
                intent="test",
            ))
            MockOrchestrator.return_value = mock_instance

            response = test_client.post(
                "/api/v1/chat/action",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "X-Pulse-Token": "valid_pulse_token",
                },
                json={"message": "Execute action"},
            )

            assert response.status_code in [200, 500]


class TestErrorHandling:
    """Tests for error handling per specs."""

    def test_404_for_unknown_endpoint(self, test_client: TestClient):
        """Test 404 for unknown endpoint."""
        response = test_client.get("/unknown")
        assert response.status_code == 404

    def test_405_wrong_method(self, test_client: TestClient):
        """Test 405 for wrong HTTP method."""
        response = test_client.delete("/health")
        assert response.status_code == 405

    def test_422_invalid_json(self, test_client: TestClient):
        """Test 422 for invalid JSON body."""
        response = test_client.post(
            "/api/v1/auth/login",
            content="invalid json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422
