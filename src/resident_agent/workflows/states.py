"""
LangGraph State Definitions

TypedDict state definitions for all resident service workflows.
Each state represents the data flow through a LangGraph workflow.
"""

from typing import TypedDict, Annotated, Optional, Any, List
from langgraph.graph import add_messages


class IncidentState(TypedDict):
    """State for incident report workflow

    Handles reporting incidents like broken lights, water leaks, etc.
    """
    user_id: str
    session_id: str
    facility: str
    location: str
    severity: str
    ticket_id: Optional[str]
    message: str
    messages: Annotated[List[Any], add_messages]


class PackageState(TypedDict):
    """State for package check workflow

    Handles checking for packages waiting at the front desk.
    """
    user_id: str
    session_id: str
    packages: list
    message: str
    messages: Annotated[List[Any], add_messages]


class BillState(TypedDict):
    """State for bill viewing workflow

    Handles viewing unpaid bills and payment history.
    """
    user_id: str
    session_id: str
    bills: list
    total_amount: float
    message: str
    messages: Annotated[List[Any], add_messages]


class BookingState(TypedDict):
    """State for amenity booking workflow

    Handles booking amenities like tennis courts, swimming pools, etc.
    """
    user_id: str
    session_id: str
    facility: str
    datetime: str
    availability: bool
    confirmed: bool
    booking_id: Optional[str]
    message: str
    messages: Annotated[List[Any], add_messages]


class PaymentState(TypedDict):
    """State for payment flow workflow

    Handles processing payments for bills and services.
    """
    user_id: str
    session_id: str
    bill_id: str
    amount: float
    payment_method: str
    payment_status: str
    transaction_id: Optional[str]
    message: str
    messages: Annotated[List[Any], add_messages]


class ServiceRequestState(TypedDict):
    """State for service request workflow

    Handles general service requests like parking card registration.
    """
    user_id: str
    session_id: str
    service_type: str
    request_details: dict
    request_id: Optional[str]
    status: str
    message: str
    messages: Annotated[List[Any], add_messages]


class IncidentManagementState(TypedDict):
    """State for multi-step incident management workflow

    Handles full incident lifecycle: report, track, resolve.
    """
    user_id: str
    session_id: str
    ticket_id: Optional[str]
    incident_details: dict
    status: str
    assigned_to: Optional[str]
    resolution: Optional[str]
    message: str
    messages: Annotated[List[Any], add_messages]
