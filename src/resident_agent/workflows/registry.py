"""
LangGraph Workflow Registry

Central registry for all LangGraph workflow graphs.
Provides initialization and lookup of compiled workflow graphs.
"""

from enum import Enum
from typing import Optional, Any


class WorkflowName(str, Enum):
    """Names of all available workflows"""
    INCIDENT_REPORT = "incident_report"
    PACKAGE_CHECK = "package_check"
    BILL_VIEW = "bill_view"
    AMENITY_BOOK = "amenity_book"
    SERVICE_REQUEST = "service_request"
    INCIDENT_MANAGEMENT = "incident_management"
    BOOKING_FLOW = "booking_flow"
    PAYMENT_FLOW = "payment_flow"


class LangGraphRegistry:
    """Registry for LangGraph compiled workflow graphs

    Manages the lifecycle of workflow graphs and provides
    lookup by workflow name.
    """

    _graphs: dict[WorkflowName, Any] = {}
    _initialized = False

    @classmethod
    def initialize(cls):
        """Initialize all workflow graphs

        Must be called before using get_graph().
        Safe to call multiple times (idempotent).
        """
        if cls._initialized:
            return

        # Import workflow builders here to avoid circular imports
        from .incident_workflow import build_incident_graph
        from .package_workflow import build_package_graph
        from .bill_workflow import build_bill_graph
        from .booking_workflow import build_booking_graph
        from .payment_workflow import build_payment_graph
        from .service_request_workflow import build_service_request_graph
        from .incident_management_workflow import build_incident_management_graph

        cls._graphs = {
            WorkflowName.INCIDENT_REPORT: build_incident_graph(),
            WorkflowName.PACKAGE_CHECK: build_package_graph(),
            WorkflowName.BILL_VIEW: build_bill_graph(),
            WorkflowName.AMENITY_BOOK: build_booking_graph(),
            WorkflowName.SERVICE_REQUEST: build_service_request_graph(),
            WorkflowName.INCIDENT_MANAGEMENT: build_incident_management_graph(),
            WorkflowName.BOOKING_FLOW: build_booking_graph(),
            WorkflowName.PAYMENT_FLOW: build_payment_graph(),
        }
        cls._initialized = True

    @classmethod
    def get_graph(cls, name: WorkflowName) -> Optional[Any]:
        """Get compiled workflow graph by name

        Args:
            name: The workflow name to look up

        Returns:
            The compiled StateGraph, or None if not found
        """
        if not cls._initialized:
            cls.initialize()
        return cls._graphs.get(name)

    @classmethod
    def list_workflows(cls) -> list[WorkflowName]:
        """List all available workflow names

        Returns:
            List of registered workflow names
        """
        if not cls._initialized:
            cls.initialize()
        return list(cls._graphs.keys())

    @classmethod
    def reset(cls):
        """Reset the registry (useful for testing)

        Clears all registered graphs and requires re-initialization.
        """
        cls._graphs.clear()
        cls._initialized = False
