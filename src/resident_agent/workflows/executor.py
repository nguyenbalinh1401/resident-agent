"""
LangGraph Executor Service

Executes LangGraph workflows with proper state management and error handling.
Provides a clean API for triggering workflows from the CUX Orchestrator.
"""

from typing import Any, Dict, Optional

from .registry import LangGraphRegistry, WorkflowName


class LangGraphExecutor:
    """Execute LangGraph workflows for resident services

    This executor manages workflow execution, state initialization,
    and error handling for all resident service workflows.
    """

    def __init__(self):
        """Initialize the executor and load all workflow graphs"""
        LangGraphRegistry.initialize()
        self.registry = LangGraphRegistry

    async def execute_workflow(
        self,
        workflow_name: WorkflowName,
        initial_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a LangGraph workflow and return final state

        Args:
            workflow_name: The workflow to execute
            initial_state: Initial state dictionary for the workflow

        Returns:
            Dict containing:
                - success: bool indicating if execution succeeded
                - state: The final workflow state (if successful)
                - message: User-facing message
                - error: Error message (if failed)
        """
        graph = self.registry.get_graph(workflow_name)
        if not graph:
            return {
                "success": False,
                "error": f"Workflow not found: {workflow_name}"
            }

        try:
            # Create config with thread_id for LangGraph checkpointer
            config = {"configurable": {"thread_id": initial_state.get("session_id", "default")}}

            # Invoke the graph with initial state and config
            result = await graph.ainvoke(initial_state, config)

            return {
                "success": True,
                "state": result,
                "message": result.get("message", "Workflow completed")
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Workflow execution failed: {str(e)}"
            }

    async def execute_intent_workflow(
        self,
        intent_type: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute workflow based on intent type

        Convenience method that maps intent types to workflows.

        Args:
            intent_type: The detected intent type (e.g., "incident_report")
            context: The execution context containing user_id, session_id, etc.

        Returns:
            Dict with execution results
        """
        workflow_name = self._intent_to_workflow(intent_type)
        if not workflow_name:
            return {
                "success": False,
                "error": f"No workflow mapped for intent: {intent_type}"
            }

        return await self.execute_workflow(workflow_name, context)

    def _intent_to_workflow(self, intent_type: str) -> Optional[WorkflowName]:
        """Map intent type to workflow name

        Args:
            intent_type: The intent type string

        Returns:
            Corresponding WorkflowName enum, or None if not found
        """
        mapping: Dict[str, WorkflowName] = {
            "incident_report": WorkflowName.INCIDENT_REPORT,
            "package_check": WorkflowName.PACKAGE_CHECK,
            "bill_view": WorkflowName.BILL_VIEW,
            "amenity_book": WorkflowName.AMENITY_BOOK,
            "service_request": WorkflowName.SERVICE_REQUEST,
            "incident_management": WorkflowName.INCIDENT_MANAGEMENT,
            "booking_flow": WorkflowName.BOOKING_FLOW,
            "payment_flow": WorkflowName.PAYMENT_FLOW,
        }
        return mapping.get(intent_type)

    def list_available_workflows(self) -> list[str]:
        """List all available workflow names

        Returns:
            List of workflow name strings
        """
        return [w.value for w in self.registry.list_workflows()]
