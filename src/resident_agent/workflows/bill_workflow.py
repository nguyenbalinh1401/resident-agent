"""
Bill View Workflow

LangGraph workflow for viewing bills and payment history.
"""

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from .states import BillState


async def query_bills(state: BillState) -> BillState:
    """Query database for unpaid bills

    Retrieves all unpaid bills for the user's account.
    """
    # TODO: Integrate with actual database service
    # bills = await db.bills.query({
    #     "user_id": state["user_id"],
    #     "status": "unpaid"
    # })

    # Mock bill data
    state["bills"] = [
        {
            "bill_id": "B-202603",
            "type": "Electricity",
            "amount": 450000,
            "due_date": "2026-03-15",
            "status": "unpaid"
        },
        {
            "bill_id": "B-202604",
            "type": "Water",
            "amount": 120000,
            "due_date": "2026-03-20",
            "status": "unpaid"
        },
        {
            "bill_id": "B-202605",
            "type": "Service Fee",
            "amount": 1500000,
            "due_date": "2026-03-10",
            "status": "unpaid"
        }
    ]

    # Calculate total
    state["total_amount"] = sum(bill["amount"] for bill in state["bills"])

    bill_count = len(state["bills"])
    if bill_count == 0:
        state["message"] = "Bạn không có hóa đơn nào chưa thanh toán."
    else:
        state["message"] = (
            f"Bạn có {bill_count} hóa đơn chưa thanh toán. "
            f"Tổng cộng: {state['total_amount']:,.0f} VND."
        )

    return state


async def format_bill_details(state: BillState) -> BillState:
    """Format bill details for the response

    Adds detailed information about each bill to the message.
    """
    if not state.get("bills"):
        return state

    details = "\n\nChi tiết hóa đơn:\n"
    for bill in state["bills"]:
        details += (
            f"• {bill.get('bill_id', 'N/A')} - {bill.get('type', 'N/A')} - "
            f"{bill.get('amount', 0):,.0f} VND - "
            f"Hạn hạn: {bill.get('due_date', 'N/A')}\n"
        )

    state["message"] += "\n" + details
    state["message"] += "\nBạn có muốn thanh toán ngay không?"

    return state


def build_bill_graph() -> StateGraph:
    """Build bill view workflow graph

    Creates a StateGraph with the following flow:
    query_bills -> format_bill_details -> END
    """
    graph = StateGraph(BillState)

    # Add nodes
    graph.add_node("query_bills", query_bills)
    graph.add_node("format_bill_details", format_bill_details)

    # Add edges
    graph.add_edge("query_bills", "format_bill_details")
    graph.set_entry_point("query_bills")

    # Compile with memory saver for state persistence
    return graph.compile(checkpointer=MemorySaver())
