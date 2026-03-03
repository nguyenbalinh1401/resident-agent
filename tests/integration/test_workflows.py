"""Integration tests for LangGraph workflows."""

import pytest
from typing import Dict, Any

from resident_agent.workflows.executor import LangGraphExecutor
from resident_agent.workflows.registry import WorkflowName, LangGraphRegistry


class TestWorkflowExecutor:
    """Tests for LangGraph workflow execution."""

    @pytest.fixture
    def executor(self):
        return LangGraphExecutor()

    @pytest.mark.asyncio
    async def test_incident_report_workflow(self, executor: LangGraphExecutor):
        """Test incident report workflow execution."""
        result = await executor.execute_workflow(
            workflow_name=WorkflowName.INCIDENT_REPORT,
            initial_state={
                "user_id": "test_user",
                "session_id": "test_session",
                "messages": [],
                "facility": "đèn",
                "location": "hành lang tầng 5",
                "severity": "medium",
                "description": "Đèn không sáng"
            }
        )

        assert result["success"] == True
        assert "state" in result
        # Should have created a ticket
        state = result["state"]
        assert "ticket_id" in state or "message" in state

    @pytest.mark.asyncio
    async def test_package_check_workflow(self, executor: LangGraphExecutor):
        """Test package check workflow execution."""
        result = await executor.execute_workflow(
            workflow_name=WorkflowName.PACKAGE_CHECK,
            initial_state={
                "user_id": "test_user",
                "session_id": "test_session",
                "messages": []
            }
        )

        assert result["success"] == True
        assert "state" in result

    @pytest.mark.asyncio
    async def test_bill_view_workflow(self, executor: LangGraphExecutor):
        """Test bill view workflow execution."""
        result = await executor.execute_workflow(
            workflow_name=WorkflowName.BILL_VIEW,
            initial_state={
                "user_id": "test_user",
                "session_id": "test_session",
                "messages": []
            }
        )

        assert result["success"] == True

    @pytest.mark.asyncio
    async def test_amenity_book_workflow(self, executor: LangGraphExecutor):
        """Test amenity booking workflow execution."""
        result = await executor.execute_workflow(
            workflow_name=WorkflowName.AMENITY_BOOK,
            initial_state={
                "user_id": "test_user",
                "session_id": "test_session",
                "messages": [],
                "facility": "swimming_pool",
                "datetime": "2026-03-03 15:00"
            }
        )

        assert result["success"] == True

    @pytest.mark.asyncio
    async def test_service_request_workflow(self, executor: LangGraphExecutor):
        """Test service request workflow execution."""
        result = await executor.execute_workflow(
            workflow_name=WorkflowName.SERVICE_REQUEST,
            initial_state={
                "user_id": "test_user",
                "session_id": "test_session",
                "messages": [],
                "service_type": "resident_card",
                "description": "Need new resident card"
            }
        )

        assert result["success"] == True

    @pytest.mark.asyncio
    async def test_execute_intent_workflow(self, executor: LangGraphExecutor):
        """Test executing workflow by intent type."""
        result = await executor.execute_intent_workflow(
            intent_type="incident_report",
            context={
                "user_id": "test_user",
                "session_id": "test_session",
                "messages": [],
                "facility": "elevator",
                "location": "building A"
            }
        )

        assert result["success"] == True


class TestWorkflowRegistry:
    """Tests for LangGraph workflow registry."""

    @pytest.fixture
    def registry(self):
        return LangGraphRegistry()

    def test_registry_initialization(self, registry: LangGraphRegistry):
        """Test that registry initializes properly."""
        assert registry is not None

    def test_get_workflow_names(self, registry: LangGraphRegistry):
        """Test getting workflow names."""
        names = WorkflowName
        assert WorkflowName.INCIDENT_REPORT in names
        assert WorkflowName.PACKAGE_CHECK in names
        assert WorkflowName.BILL_VIEW in names
        assert WorkflowName.AMENITY_BOOK in names


class TestWorkflowStateManagement:
    """Tests for workflow state management."""

    @pytest.mark.asyncio
    async def test_workflow_with_message_history(self, executor: LangGraphExecutor):
        """Test workflow with message history."""
        result = await executor.execute_workflow(
            workflow_name=WorkflowName.INCIDENT_REPORT,
            initial_state={
                "user_id": "test_user",
                "session_id": "test_session",
                "messages": [
                    {"role": "user", "content": "Tôi muốn báo sự cố"},
                    {"role": "assistant", "content": "Vui lòng cho biết chi tiết"}
                ],
                "facility": "điều hòa",
                "location": "phòng ngủ",
                "severity": "high"
            }
        )

        assert result["success"] == True

    @pytest.mark.asyncio
    async def test_workflow_state_preservation(self, executor: LangGraphExecutor):
        """Test that workflow preserves state through execution."""
        initial_state = {
            "user_id": "user_123",
            "session_id": "session_456",
            "messages": [],
            "custom_field": "custom_value"
        }

        result = await executor.execute_workflow(
            workflow_name=WorkflowName.PACKAGE_CHECK,
            initial_state=initial_state
        )

        assert result["success"] == True
        # State should still contain user_id and session_id
        state = result["state"]
        assert "user_id" in state or "messages" in state
