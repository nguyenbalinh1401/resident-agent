"""
Incident Report Workflow

LangGraph workflow for handling incident reports like broken lights,
water leaks, or other facility issues.
"""

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from .states import IncidentState


async def extract_incident_info(state: IncidentState) -> IncidentState:
    """Extract incident details from slots and user input

    Parses the user's message to identify:
    - The facility/equipment with issues
    - The location
    - Severity level
    """
    # In production, this would use NLP to extract from the message
    # For now, use defaults from the state
    state["facility"] = state.get("facility", "unknown")
    state["location"] = state.get("location", "unknown")
    state["severity"] = state.get("severity", "medium")
    return state


async def create_ticket(state: IncidentState) -> IncidentState:
    """Create a ticket in the database

    Generates a unique ticket ID and stores the incident details.
    """
    # TODO: Integrate with actual database service
    # ticket = await db.tickets.create({
    #     "user_id": state["user_id"],
    #     "facility": state["facility"],
    #     "location": state["location"],
    #     "severity": state["severity"],
    #     "status": "open"
    # })

    # Mock ticket creation
    state["ticket_id"] = f"T-{abs(hash(state['user_id'] + state['facility'])) % 100000:05d}"
    state["message"] = (
        f"Đã tiếp nhận báo cáo: {state['facility']} tại {state['location']}. "
        f"Mức độ: {state['severity']}. "
        f"Mã ticket: #{state['ticket_id']}"
    )
    return state


async def notify_maintenance(state: IncidentState) -> IncidentState:
    """Notify maintenance team if severity is high

    For high severity incidents, send immediate notifications
    to the maintenance team.
    """
    if state.get("severity") == "high":
        # TODO: Integrate with notification service
        # await notification_service.send_to_maintenance({
        #     "ticket_id": state["ticket_id"],
        #     "facility": state["facility"],
        #     "location": state["location"]
        # })
        state["message"] += " Đã thông báo khẩn cấp đến đội bảo trì."
    else:
        state["message"] += " Đội bảo trì sẽ xử lý trong vòng 24h."
    return state


def should_notify(state: IncidentState) -> str:
    """Conditional routing based on severity

    Routes to notify_maintenance if severity is high,
    otherwise skips to END.
    """
    return "notify" if state.get("severity") == "high" else END


def build_incident_graph() -> StateGraph:
    """Build incident report workflow graph

    Creates a StateGraph with the following flow:
    extract_info -> create_ticket -> [should_notify] -> notify_maintenance -> END
    """
    graph = StateGraph(IncidentState)

    # Add nodes
    graph.add_node("extract_info", extract_incident_info)
    graph.add_node("create_ticket", create_ticket)
    graph.add_node("notify_maintenance", notify_maintenance)

    # Add edges
    graph.add_edge("extract_info", "create_ticket")
    graph.add_conditional_edges(
        "create_ticket",
        should_notify,
        {
            "notify": "notify_maintenance",
            END: END
        }
    )

    # Set entry point
    graph.set_entry_point("extract_info")

    # Compile with memory saver for state persistence
    return graph.compile(checkpointer=MemorySaver())
