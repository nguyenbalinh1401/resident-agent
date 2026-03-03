"""
Service Request Workflow

LangGraph workflow for general service requests like
parking card registration, document requests, etc.
"""

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from .states import ServiceRequestState


async def parse_request(state: ServiceRequestState) -> ServiceRequestState:
    """Parse the service request

    Identifies the type of service being requested and extracts details.
    """
    # TODO: Use NLP to parse the request
    state["service_type"] = state.get("service_type", "general")
    state["request_details"] = state.get("request_details", {})
    state["status"] = "pending"

    return state


async def validate_request(state: ServiceRequestState) -> ServiceRequestState:
    """Validate the service request

    Checks if the request is valid and can be processed.
    """
    # TODO: Implement validation logic
    service_type = state.get("service_type", "")

    if service_type == "parking_card":
        state["message"] = "Đăng ký thẻ gửi xe"
    elif service_type == "resident_card":
        state["message"] = "Đăng ký thẻ cư dân"
    elif service_type == "document":
        state["message"] = "Yêu cầu giấy tờ"
    else:
        state["message"] = "Yêu cầu dịch vụ chung"

    return state


async def create_request(state: ServiceRequestState) -> ServiceRequestState:
    """Create the service request in the database

    Generates a unique request ID and stores the request details.
    """
    # TODO: Integrate with actual database service
    # request = await db.service_requests.create({
    #     "user_id": state["user_id"],
    #     "service_type": state["service_type"],
    #     "details": state["request_details"]
    # })

    # Mock request creation
    state["request_id"] = f"SR-{abs(hash(state['user_id'] + state['service_type'])) % 100000:05d}"
    state["status"] = "submitted"
    state["message"] += f"\n\nĐã tạo yêu cầu: #{state['request_id']}"
    state["message"] += "\nBan quản lý sẽ liên hệ với bạn trong vòng 24h."

    return state


async def notify_staff(state: ServiceRequestState) -> ServiceRequestState:
    """Notify relevant staff about the request

    Sends notification to the appropriate department.
    """
    # TODO: Integrate with notification service
    # await notification_service.send_to_staff({
    #     "request_id": state["request_id"],
    #     "service_type": state["service_type"]
    # })

    state["status"] = "processing"
    return state


def build_service_request_graph() -> StateGraph:
    """Build service request workflow graph

    Creates a StateGraph with the following flow:
    parse_request -> validate_request -> create_request -> notify_staff -> END
    """
    graph = StateGraph(ServiceRequestState)

    # Add nodes
    graph.add_node("parse_request", parse_request)
    graph.add_node("validate_request", validate_request)
    graph.add_node("create_request", create_request)
    graph.add_node("notify_staff", notify_staff)

    # Add edges
    graph.add_edge("parse_request", "validate_request")
    graph.add_edge("validate_request", "create_request")
    graph.add_edge("create_request", "notify_staff")

    # Set entry point
    graph.set_entry_point("parse_request")

    # Compile with memory saver for state persistence
    return graph.compile(checkpointer=MemorySaver())
