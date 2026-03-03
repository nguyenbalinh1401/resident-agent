"""
Amenity Booking Workflow

LangGraph workflow for booking amenities like tennis courts,
swimming pools, and other facilities.
"""

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from .states import BookingState


async def check_availability(state: BookingState) -> BookingState:
    """Check if the facility is available at the requested time

    Queries the amenity booking system for availability.
    """
    # TODO: Integrate with actual amenity service
    # availability = await amenity_service.check_availability({
    #     "facility": state["facility"],
    #     "datetime": state["datetime"]
    # })

    # Mock availability check (randomly available for demo)
    import random
    state["availability"] = random.choice([True, True, False])  # 2/3 chance available

    if not state["availability"]:
        state["message"] = (
            f"Rất tiếc, {state['facility']} đã được đặt vào {state['datetime']}. "
            f"Vui lòng chọn khung giờ khác."
        )

    return state


async def request_confirmation(state: BookingState) -> BookingState:
    """Request user confirmation for the booking

    Presents the booking details and asks for confirmation.
    """
    if state["availability"]:
        state["message"] = (
            f"{state['facility']} còn trống vào {state['datetime']}. "
            f"Bạn có muốn đặt không?"
        )
    return state


async def confirm_booking(state: BookingState) -> BookingState:
    """Confirm and create the booking

    Creates the booking record in the database.
    """
    if not state.get("confirmed"):
        state["message"] = "Đã hủy đặt chỗ."
        return state

    # TODO: Integrate with actual amenity service
    # booking = await amenity_service.create_booking({
    #     "user_id": state["user_id"],
    #     "facility": state["facility"],
    #     "datetime": state["datetime"]
    # })

    # Mock booking creation
    state["booking_id"] = f"BK-{abs(hash(state['user_id'] + state['datetime'])) % 100000:05d}"
    state["message"] = (
        f"Đã đặt {state['facility']} thành công vào {state['datetime']}. "
        f"Mã đặt chỗ: #{state['booking_id']}"
    )

    return state


def should_confirm(state: BookingState) -> str:
    """Conditional routing based on availability

    Routes to request_confirmation if available,
    otherwise ends the workflow.
    """
    return "request_confirmation" if state.get("availability") else END


def should_book(state: BookingState) -> str:
    """Conditional routing based on user confirmation

    Routes to confirm_booking if confirmed,
    otherwise ends the workflow.
    """
    return "book" if state.get("confirmed") else END


def build_booking_graph() -> StateGraph:
    """Build amenity booking workflow graph

    Creates a StateGraph with the following flow:
    check_availability -> [should_confirm] -> request_confirmation -> [should_book] -> confirm_booking -> END
    """
    graph = StateGraph(BookingState)

    # Add nodes
    graph.add_node("check_availability", check_availability)
    graph.add_node("request_confirmation", request_confirmation)
    graph.add_node("confirm_booking", confirm_booking)

    # Add edges
    graph.add_conditional_edges(
        "check_availability",
        should_confirm,
        {
            "request_confirmation": "request_confirmation",
            END: END
        }
    )
    graph.add_conditional_edges(
        "request_confirmation",
        should_book,
        {
            "book": "confirm_booking",
            END: END
        }
    )

    # Set entry point
    graph.set_entry_point("check_availability")

    # Compile with memory saver for state persistence
    return graph.compile(checkpointer=MemorySaver())
