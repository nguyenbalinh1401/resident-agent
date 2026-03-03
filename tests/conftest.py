"""Shared pytest fixtures for testing."""

import pytest
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock
import asyncio

# Import the modules we'll be testing
# Note: These imports will work once the package is properly installed


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def settings():
    """Create test settings instance."""
    from resident_agent.core.config import Settings

    # Reset any existing instance
    Settings.reset()

    # Create test settings with known values
    test_settings = Settings(
        environment="test",
        secret_key="test-secret-key-for-jwt-authentication-testing-minimum-32-characters",
        openai_api_key="test-openai-key",
        database_url="postgresql://test:test@localhost:5432/pulse_test",
        demo_email="demo@example.com",
        demo_password="demo123",
        access_token_expire_minutes=15,
        refresh_token_expire_days=7
    )

    # Set as the singleton instance
    Settings._instance = test_settings

    yield test_settings

    # Cleanup
    Settings.reset()


@pytest.fixture
def executor():
    """Create LangGraph executor for testing."""
    from resident_agent.workflows.executor import LangGraphExecutor
    return LangGraphExecutor()


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for testing without actual API calls."""
    from unittest.mock import patch

    mock_client = AsyncMock()

    # Mock chat completion response
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(
            message=MagicMock(
                content='{"answer": "Test response", "actions": [], "intent": "unknown", "needs_tool": false}'
            )
        )
    ]
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    with patch('resident_agent.core.openai_client.OpenAIClient.get', return_value=mock_client):
        yield mock_client


@pytest.fixture
def jwt_handler(settings):
    """Create JWT handler instance for testing."""
    from resident_agent.auth.jwt_handler import JWTHandler
    return JWTHandler(settings)


@pytest.fixture
def rule_based_detector():
    """Create rule-based intent detector for testing."""
    from resident_agent.cux.intent_detector import RuleBasedDetector
    return RuleBasedDetector()


@pytest.fixture
def hybrid_intent_detector(settings, mock_openai_client):
    """Create hybrid intent detector with mocked LLM."""
    from resident_agent.cux.intent_detector import HybridIntentDetector, LLMIntentDetector

    llm_detector = LLMIntentDetector(settings)
    return HybridIntentDetector(llm_detector=llm_detector)


@pytest.fixture
def allowance_client():
    """Create allowance client for testing."""
    from resident_agent.cux.allowance_client import AllowanceClient
    return AllowanceClient()


@pytest.fixture
def state_manager():
    """Create conversation state manager for testing."""
    from resident_agent.cux.state_manager import ConversationStateManager
    return ConversationStateManager()


@pytest.fixture
def cux_orchestrator(settings, rule_based_detector, allowance_client, state_manager):
    """Create CUX orchestrator with all dependencies."""
    from resident_agent.cux.orchestrator import CuxOrchestrator
    from resident_agent.cux.intent_detector import HybridIntentDetector

    # Create hybrid detector with rule-based only (no LLM for faster tests)
    hybrid_detector = HybridIntentDetector(rule_detector=rule_based_detector, llm_detector=None)

    return CuxOrchestrator(
        intent_detector=hybrid_detector,
        allowance_client=allowance_client,
        state_manager=state_manager,
        settings=settings
    )


@pytest.fixture
def access_token(jwt_handler):
    """Generate a valid access token for testing."""
    return jwt_handler.create_access_token("test_user_123", "resident")


@pytest.fixture
def refresh_token(jwt_handler):
    """Generate a valid refresh token for testing."""
    return jwt_handler.create_refresh_token("test_user_123")


@pytest.fixture
def auth_headers(access_token):
    """Create authorization headers for authenticated requests."""
    return {"Authorization": f"Bearer {access_token}"}
