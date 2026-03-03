"""
Package Check Workflow

LangGraph workflow for checking packages waiting at the front desk.
"""

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from .states import PackageState


async def query_packages(state: PackageState) -> PackageState:
    """Query database for packages belonging to the user

    Retrieves all packages waiting for pickup at the front desk.
    """
    # TODO: Integrate with actual database service
    # packages = await db.packages.query({
    #     "user_id": state["user_id"],
    #     "status": "waiting"
    # })

    # Mock package data
    state["packages"] = [
        {
            "package_id": "P-1001",
            "sender": "Shopee",
            "received_date": "2026-03-01",
            "location": "Front Desk"
        },
        {
            "package_id": "P-1002",
            "sender": "Lazada",
            "received_date": "2026-03-02",
            "location": "Front Desk"
        }
    ]

    package_count = len(state["packages"])
    if package_count == 0:
        state["message"] = "Bạn hiện không có bưu kiện nào chờ nhận."
    elif package_count == 1:
        state["message"] = f"Bạn có 1 bưu kiện chờ nhận tại quầy lễ tân."
    else:
        state["message"] = f"Bạn có {package_count} bưu kiện chờ nhận tại quầy lễ tân."

    return state


async def format_package_details(state: PackageState) -> PackageState:
    """Format package details for the response

    Adds detailed information about each package to the message.
    """
    if not state.get("packages"):
        return state

    details = "\n\nChi tiết bưu kiện:\n"
    for pkg in state["packages"]:
        details += f"• {pkg.get('package_id', 'N/A')} - {pkg.get('sender', 'N/A')} - Ng nhận: {pkg.get('received_date', 'N/A')}\n"

    state["message"] += details
    return state


def build_package_graph() -> StateGraph:
    """Build package check workflow graph

    Creates a StateGraph with the following flow:
    query_packages -> format_package_details -> END
    """
    graph = StateGraph(PackageState)

    # Add nodes
    graph.add_node("query_packages", query_packages)
    graph.add_node("format_package_details", format_package_details)

    # Add edges
    graph.add_edge("query_packages", "format_package_details")
    graph.set_entry_point("query_packages")

    # Compile with memory saver for state persistence
    return graph.compile(checkpointer=MemorySaver())
