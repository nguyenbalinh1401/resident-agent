"""
Incident Management Workflow

Multi-step LangGraph workflow for full incident lifecycle management:
reporting, tracking, and resolution.
"""

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from .states import IncidentManagementState


async def receive_report(state: IncidentManagementState) -> IncidentManagementState:
    """Receive and log the incident report

    Creates a new ticket in the database.
    """
    # TODO: Integrate with database service
    # ticket = await db.tickets.create({
    #     "user_id": state["user_id"],
    #     "details": state["incident_details"]
    # })

    # Mock ticket creation
    state["ticket_id"] = f"IM-{abs(hash(state['user_id'])) % 100000:05d}"
    state["status"] = "open"
    state["message"] = f"Đã tiếp nhận báo cáo. Mã ticket: #{state['ticket_id']}"

    return state


async def assign_ticket(state: IncidentManagementState) -> IncidentManagementState:
    """Assign the ticket to appropriate staff

    Routes the incident to the relevant department.
    """
    # TODO: Integrate with assignment service
    # assignment = await assignment_service.assign({
    #     "ticket_id": state["ticket_id"],
    #     "incident_type": state["incident_details"].get("type")
    # })

    # Mock assignment
    state["assigned_to"] = "Maintenance Team"
    state["status"] = "assigned"
    state["message"] += f"\nĐã phân cho: {state['assigned_to']}"

    return state


async def check_ticket_exists(state: IncidentManagementState) -> IncidentManagementState:
    """Check if this is a new report or status check

    Determines if we need to create a new ticket or check existing.
    """
    if state.get("ticket_id"):
        state["message"] = f"Kiểm tra trạng thái ticket: #{state['ticket_id']}"
    else:
        state["message"] = "Tạo ticket mới"

    return state


async def update_status(state: IncidentManagementState) -> IncidentManagementState:
    """Update ticket status

    Updates the current status of the incident.
    """
    if state.get("ticket_id"):
        # TODO: Integrate with database service
        # ticket = await db.tickets.get_by_id(state["ticket_id"])
        state["status"] = "in_progress"
        state["message"] = f"Trạng thái: {state['status']}"

    return state


async def complete_ticket(state: IncidentManagementState) -> IncidentManagementState:
    """Complete the ticket

    Marks the incident as resolved.
    """
    if state.get("resolution"):
        # TODO: Integrate with database service
        # await db.tickets.update(state["ticket_id"], {
        #     "status": "completed",
        #     "resolution": state["resolution"]
        # })
        state["status"] = "completed"
        state["message"] = f"Ticket #{state['ticket_id']} đã hoàn thành."
        state["message"] += f"\nGiải pháp: {state['resolution']}"

    return state


def should_create_or_check(state: IncidentManagementState) -> str:
    """Conditional routing based on existing ticket

    Routes to receive_report if no ticket exists,
    otherwise to update_status.
    """
    return "check" if state.get("ticket_id") else "create"


def should_complete(state: IncidentManagementState) -> str:
    """Conditional routing based on resolution

    Routes to complete_ticket if resolution is provided,
    otherwise ends the workflow.
    """
    return "complete" if state.get("resolution") else END


def build_incident_management_graph() -> StateGraph:
    """Build incident management workflow graph

    Creates a StateGraph with the following flow:
    check_ticket_exists -> [should_create_or_check] -> receive_report/assign_ticket OR update_status -> [should_complete] -> complete_ticket -> END
    """
    graph = StateGraph(IncidentManagementState)

    # Add nodes
    graph.add_node("check_ticket_exists", check_ticket_exists)
    graph.add_node("receive_report", receive_report)
    graph.add_node("assign_ticket", assign_ticket)
    graph.add_node("update_status", update_status)
    graph.add_node("complete_ticket", complete_ticket)

    # Add edges
    graph.add_conditional_edges(
        "check_ticket_exists",
        should_create_or_check,
        {
            "create": "receive_report",
            "check": "update_status"
        }
    )
    graph.add_edge("receive_report", "assign_ticket")
    graph.add_edge("assign_ticket", "update_status")
    graph.add_conditional_edges(
        "update_status",
        should_complete,
        {
            "complete": "complete_ticket",
            END: END
        }
    )

    # Set entry point
    graph.set_entry_point("check_ticket_exists")

    # Compile with memory saver for state persistence
    return graph.compile(checkpointer=MemorySaver())
