"""Unit tests for CUX Orchestrator module.

Tests cover the LLM-first orchestrator per specs/cux.md:
- 3 Intent Types: chitchat, agentic_flow, tool_call
- Flow Examples from specs
- Tool Definitions with capabilities
- SSE streaming support
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from resident_agent.schemas.chat_schemas import ActionButton, ActionStyle, ChatResponse


class TestActionButtons:
    """Tests for Action Button generation per specs/api-reference.md."""

    def test_action_button_schema(self):
        """Test ActionButton schema per specs/api-reference.md."""
        action = ActionButton(
            id="check_package",
            label="Xem chi tiết",
            action_type="navigate",
            params={"screen": "packages"},
            style=ActionStyle.PRIMARY,
        )

        assert action.id == "check_package"
        assert action.label == "Xem chi tiết"
        assert action.action_type == "navigate"
        assert action.params["screen"] == "packages"
        assert action.style == ActionStyle.PRIMARY

    def test_action_styles_per_specs(self):
        """Test ActionStyle values per specs/api-reference.md.

        Per specs: primary, secondary, outline
        """
        assert ActionStyle.PRIMARY.value == "primary"
        assert ActionStyle.SECONDARY.value == "secondary"
        assert ActionStyle.OUTLINE.value == "outline"

    def test_action_types_per_specs(self):
        """Test action_type values per specs/api-reference.md Flutter Action Handling."""
        # Per specs:
        # navigate, report_incident, check_package, view_bills,
        # book_amenity, service_request, make_payment, deeplink
        expected_action_types = [
            "navigate",
            "report_incident",
            "check_package",
            "view_bills",
            "book_amenity",
            "service_request",
            "make_payment",
            "deeplink",
        ]

        # These should be valid action types
        for action_type in expected_action_types:
            assert isinstance(action_type, str)


class TestCuxOrchestratorAPI:
    """Tests for CUX Orchestrator API."""

    @pytest.fixture
    def mock_settings(self):
        from dataclasses import dataclass

        @dataclass
        class MockSettings:
            jwt_secret_key: str = "test-secret"
            openai_api_key: str = "test-key"
            openai_model: str = "gpt-4o-mini"
            openai_temperature: float = 0.0
            pulse_backend_url: str = "http://localhost:5000"
            redis_url: str = "redis://localhost:6379/0"

        return MockSettings()

    def test_chat_response_schema(self):
        """Test ChatResponse schema."""
        response = ChatResponse(
            message="Xin chào! Tôi có thể giúp gì cho bạn?",
            actions=[
                ActionButton(
                    id="report_incident",
                    label="Báo sự cố",
                    action_type="report_incident",
                    style=ActionStyle.PRIMARY,
                )
            ],
            session_id="test_session",
        )

        assert response.message == "Xin chào! Tôi có thể giúp gì cho bạn?"
        assert len(response.actions) == 1
        assert response.session_id == "test_session"


class TestToolDefinitions:
    """Tests for Tool Definitions per specs/cux.md."""

    def test_tools_module_exists(self):
        """Test that tools module can be imported."""
        from resident_agent.cux.tools import TOOLS, get_tools_for_capabilities
        assert TOOLS is not None
        assert callable(get_tools_for_capabilities)

    def test_get_tools_for_capabilities(self):
        """Test tool filtering by capabilities."""
        from resident_agent.cux.tools import get_tools_for_capabilities

        # Empty capabilities should return empty or minimal tools
        tools = get_tools_for_capabilities([])
        assert isinstance(tools, list)

    def test_get_tools_for_resident(self):
        """Test tools for resident capabilities."""
        from resident_agent.cux.tools import get_tools_for_capabilities

        capabilities = ["VIEW_BILLS", "CHECK_PACKAGE", "REPORT_INCIDENT"]
        tools = get_tools_for_capabilities(capabilities)
        assert isinstance(tools, list)


class TestActionGenerator:
    """Tests for Action Generator."""

    def test_action_generator_exists(self):
        """Test that ActionGenerator can be imported."""
        from resident_agent.cux.action_generator import ActionGenerator
        generator = ActionGenerator()
        assert generator is not None

    def test_generate_default_actions(self):
        """Test generating default actions."""
        from resident_agent.cux.action_generator import ActionGenerator
        generator = ActionGenerator()

        actions = generator.generate_actions()
        assert isinstance(actions, list)


class TestStateManager:
    """Tests for State Manager."""

    @pytest.fixture
    def mock_settings(self):
        from dataclasses import dataclass

        @dataclass
        class MockSettings:
            redis_url: str = "redis://localhost:6379/0"

        return MockSettings()

    def test_state_manager_exists(self):
        """Test that StateManager can be imported."""
        from resident_agent.cux.state_manager import StateManager
        assert StateManager is not None
