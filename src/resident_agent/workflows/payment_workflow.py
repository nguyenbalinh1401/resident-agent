"""
Payment Flow Workflow

LangGraph workflow for processing payments for bills and services.
"""

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from .states import PaymentState


async def get_bill_details(state: PaymentState) -> PaymentState:
    """Get bill details for payment

    Retrieves the bill information and validates payment amount.
    """
    # TODO: Integrate with actual billing service
    # bill = await db.bills.get_by_id(state["bill_id"])

    # Mock bill data
    state["amount"] = state.get("amount", 1500000)
    state["message"] = f"Hóa đơn {state.get('bill_id', 'N/A')}: {state['amount']:,.0f} VND"

    return state


async def select_payment_method(state: PaymentState) -> PaymentState:
    """Select payment method

    Guides user to select a payment method.
    """
    state["payment_method"] = state.get("payment_method", "wallet")
    state["message"] += "\n\nPhương thức thanh toán đã chọn: Ví điện tử"

    return state


async def process_payment(state: PaymentState) -> PaymentState:
    """Process the payment

    Executes the payment transaction.
    """
    # TODO: Integrate with actual payment gateway
    # transaction = await payment_gateway.process({
    #     "amount": state["amount"],
    #     "method": state["payment_method"],
    #     "bill_id": state["bill_id"]
    # })

    # Mock payment processing
    import random
    success = random.choice([True, True, True, False])  # 75% success rate

    if success:
        state["payment_status"] = "completed"
        state["transaction_id"] = f"TXN-{abs(hash(state['bill_id'])) % 1000000:06d}"
        state["message"] = (
            f"\n✅ Thanh toán thành công!\n"
            f"Số tiền: {state['amount']:,.0f} VND\n"
            f"Mã giao dịch: {state['transaction_id']}\n"
            f"Phương thức: {state['payment_method']}"
        )
    else:
        state["payment_status"] = "failed"
        state["message"] = (
            f"\n❌ Thanh toán thất bại.\n"
            f"Vui lòng thử lại hoặc chọn phương thức thanh toán khác."
        )

    return state


async def update_bill_status(state: PaymentState) -> PaymentState:
    """Update bill status after payment

    Marks the bill as paid in the database.
    """
    if state.get("payment_status") == "completed":
        # TODO: Integrate with actual billing service
        # await db.bills.update(state["bill_id"], {"status": "paid"})
        state["message"] += "\n\nHóa đơn đã được đánh dấu đã thanh toán."

    return state


def should_update_bill(state: PaymentState) -> str:
    """Conditional routing based on payment status

    Routes to update_bill_status if payment succeeded,
    otherwise ends the workflow.
    """
    return "update" if state.get("payment_status") == "completed" else END


def build_payment_graph() -> StateGraph:
    """Build payment flow workflow graph

    Creates a StateGraph with the following flow:
    get_bill_details -> select_payment_method -> process_payment -> [should_update_bill] -> update_bill_status -> END
    """
    graph = StateGraph(PaymentState)

    # Add nodes
    graph.add_node("get_bill_details", get_bill_details)
    graph.add_node("select_payment_method", select_payment_method)
    graph.add_node("process_payment", process_payment)
    graph.add_node("update_bill_status", update_bill_status)

    # Add edges
    graph.add_edge("get_bill_details", "select_payment_method")
    graph.add_edge("select_payment_method", "process_payment")
    graph.add_conditional_edges(
        "process_payment",
        should_update_bill,
        {
            "update": "update_bill_status",
            END: END
        }
    )

    # Set entry point
    graph.set_entry_point("get_bill_details")

    # Compile with memory saver for state persistence
    return graph.compile(checkpointer=MemorySaver())
