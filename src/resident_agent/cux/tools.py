"""Tool definitions for LLM function calling.

These tools are passed to the LLM for function calling.
The LLM decides which tool to call based on user message.
"""

from typing import Dict, Any, Optional, Union, List
import structlog

from resident_agent.clients.pulse_client import PulseClient

logger = structlog.get_logger()


def _wrap_result(result: Union[Dict, List, Any]) -> Dict[str, Any]:
    """Wrap result in dict if it's a list.

    ToolCall.result expects Dict[str, Any], but PulseClient methods
    return List[Dict] for collection endpoints. This helper ensures
    all results are wrapped in a dictionary.

    Args:
        result: Result from PulseClient call (dict, list, or other)

    Returns:
        Dict with 'data' key if input was a list, otherwise returns as-is
    """
    if isinstance(result, list):
        return {"data": result}
    return result

# Mock data for packages (when Pulse Backend endpoint unavailable)
MOCK_PACKAGES = [
    {
        "id": "pkg-001",
        "unitId": "unit-101",
        "recipientName": "Nguyễn Văn A",
        "status": "Arrived",
        "description": "Gói hàng từ Shopee",
        "arrivalTime": "2026-03-28T10:30:00Z",
        "loggedBy": "staff-001"
    },
    {
        "id": "pkg-002",
        "unitId": "unit-102",
        "recipientName": "Trần Thị B",
        "status": "Arrived",
        "description": "Gói hàng từ Lazada",
        "arrivalTime": "2026-03-29T14:15:00Z",
        "loggedBy": "staff-001"
    },
    {
        "id": "pkg-003",
        "unitId": "unit-101",
        "recipientName": "Nguyễn Văn A",
        "status": "PickedUp",
        "description": "Gói hàng từ Tiki",
        "arrivalTime": "2026-03-25T09:00:00Z",
        "loggedBy": "staff-002"
    },
]

# Tool definitions following OpenAI's function calling format
TOOLS = [
    # ==================== Profile Tools ====================
    {
        "type": "function",
        "function": {
            "name": "get_profile",
            "description": "Xem thông tin căn hộ và thông tin cá nhân của user",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_contact",
            "description": "Cập nhật thông tin liên hệ (số điện thoại, email)",
            "parameters": {
                "type": "object",
                "properties": {
                    "phone": {"type": "string", "description": "Số điện thoại mới"},
                    "email": {"type": "string", "description": "Email mới"},
                },
                "required": [],
            },
        },
    },
    # ==================== Bills & Payment Tools ====================
    {
        "type": "function",
        "function": {
            "name": "get_bills",
            "description": "Xem danh sách hóa đơn (phí quản lý, điện, nước, etc.)",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["Unpaid", "Paid", "Overdue"],
                        "description": "Lọc theo trạng thái hóa đơn",
                    },
                    "unit_id": {"type": "string", "description": "ID căn hộ (optional)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_bill_detail",
            "description": "Xem chi tiết một hóa đơn cụ thể",
            "parameters": {
                "type": "object",
                "properties": {
                    "bill_id": {"type": "string", "description": "ID của hóa đơn"},
                },
                "required": ["bill_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "make_payment",
            "description": "Thanh toán hóa đơn",
            "parameters": {
                "type": "object",
                "properties": {
                    "bill_id": {"type": "string", "description": "ID hóa đơn cần thanh toán"},
                    "amount": {"type": "number", "description": "Số tiền thanh toán"},
                    "payment_method": {
                        "type": "string",
                        "enum": ["VNPay", "Momo", "BankTransfer", "Cash"],
                        "description": "Phương thức thanh toán",
                    },
                },
                "required": ["bill_id", "amount"],
            },
        },
    },
    # ==================== Booking Tools ====================
    {
        "type": "function",
        "function": {
            "name": "get_amenities",
            "description": "Xem danh sách tiện ích có thể đặt chỗ (hồ bơi, gym, sân tennis, etc.)",
            "parameters": {
                "type": "object",
                "properties": {
                    "category_id": {"type": "string", "description": "ID danh mục tiện ích (optional)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_amenity_detail",
            "description": "Xem chi tiết một tiện ích và lịch trống",
            "parameters": {
                "type": "object",
                "properties": {
                    "amenity_id": {"type": "string", "description": "ID tiện ích"},
                },
                "required": ["amenity_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "book_amenity",
            "description": "Đặt chỗ tiện ích",
            "parameters": {
                "type": "object",
                "properties": {
                    "amenity_id": {"type": "string", "description": "ID tiện ích cần đặt"},
                    "booking_date": {"type": "string", "description": "Ngày đặt chỗ (YYYY-MM-DD)"},
                    "start_time": {"type": "string", "description": "Giờ bắt đầu (HH:MM)"},
                    "end_time": {"type": "string", "description": "Giờ kết thúc (HH:MM)"},
                },
                "required": ["amenity_id", "booking_date", "start_time", "end_time"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_my_bookings",
            "description": "Xem danh sách đặt chỗ của tôi",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["Pending", "Confirmed", "Cancelled", "Completed"],
                        "description": "Lọc theo trạng thái",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_booking",
            "description": "Hủy đặt chỗ",
            "parameters": {
                "type": "object",
                "properties": {
                    "booking_id": {"type": "string", "description": "ID đặt chỗ cần hủy"},
                },
                "required": ["booking_id"],
            },
        },
    },
    # ==================== Incident Tools ====================
    {
        "type": "function",
        "function": {
            "name": "create_incident",
            "description": "Báo cáo sự cố/vấn đề (điện, nước, máy lạnh, thang máy, etc.)",
            "parameters": {
                "type": "object",
                "properties": {
                    "category_id": {"type": "string", "description": "ID danh mục sự cố"},
                    "description": {"type": "string", "description": "Mô tả chi tiết sự cố"},
                    "severity": {
                        "type": "string",
                        "enum": ["Low", "Medium", "High", "Critical"],
                        "description": "Mức độ nghiêm trọng",
                    },
                    "images": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Danh sách URL hình ảnh",
                    },
                },
                "required": ["category_id", "description"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_my_incidents",
            "description": "Xem danh sách phiếu báo sự cố của tôi",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["Pending", "InProgress", "Resolved", "Closed"],
                        "description": "Lọc theo trạng thái",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_incident_detail",
            "description": "Xem chi tiết một phiếu báo sự cố",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticket_id": {"type": "string", "description": "ID phiếu báo sự cố"},
                },
                "required": ["ticket_id"],
            },
        },
    },
    # ==================== Package Tools ====================
    {
        "type": "function",
        "function": {
            "name": "get_packages",
            "description": "Kiểm tra bưu kiện đã nhận/chưa nhận",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["Arrived", "PickedUp"],
                        "description": "Lọc theo trạng thái",
                    },
                },
                "required": [],
            },
        },
    },
    # ==================== Announcement Tools ====================
    {
        "type": "function",
        "function": {
            "name": "get_announcements",
            "description": "Xem thông báo từ ban quản lý tòa nhà",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Số lượng thông báo tối đa (default: 10)",
                    },
                },
                "required": [],
            },
        },
    },
]


async def execute_tool(
    tool_name: str,
    params: dict,
    pulse_client: PulseClient,
) -> dict:
    """Execute a tool by calling the Pulse Backend API.

    Args:
        tool_name: Name of the tool to execute
        params: Tool parameters
        pulse_client: Authenticated PulseClient instance (injected via dependency)

    Returns:
        Tool execution result

    Raises:
        Exception: If tool execution fails
    """
    logger.info("executing_tool", tool=tool_name, params=params)

    try:
        # Profile tools
        if tool_name == "get_profile":
            result = await pulse_client.get_current_user()

        elif tool_name == "update_contact":
            result = await pulse_client.update_profile(**params)

        # Bills tools
        elif tool_name == "get_bills":
            result = _wrap_result(await pulse_client.get_bills(**params))

        elif tool_name == "get_bill_detail":
            result = await pulse_client.get_bill(params["bill_id"])

        elif tool_name == "make_payment":
            result = await pulse_client.create_payment(**params)

        # Amenity tools
        elif tool_name == "get_amenities":
            result = _wrap_result(await pulse_client.get_amenities(**params))

        elif tool_name == "get_amenity_detail":
            result = await pulse_client.get_amenity(params["amenity_id"])

        elif tool_name == "book_amenity":
            result = await pulse_client.create_booking(**params)

        elif tool_name == "get_my_bookings":
            result = _wrap_result(await pulse_client.get_bookings(**params))

        elif tool_name == "cancel_booking":
            result = await pulse_client.cancel_booking(params["booking_id"])

        # Incident tools
        elif tool_name == "create_incident":
            result = await pulse_client.create_ticket(**params)

        elif tool_name == "get_my_incidents":
            result = _wrap_result(await pulse_client.get_tickets(**params))

        elif tool_name == "get_incident_detail":
            result = await pulse_client.get_ticket(params["ticket_id"])

        # Package tools
        elif tool_name == "get_packages":
            # Use mock data since Pulse Backend Packages endpoint is not available
            status_filter = params.get("status")
            if status_filter:
                filtered = [p for p in MOCK_PACKAGES if p["status"] == status_filter]
                result = {"data": filtered, "total": len(filtered), "mock": True}
            else:
                result = {"data": MOCK_PACKAGES, "total": len(MOCK_PACKAGES), "mock": True}

        # Announcement tools
        elif tool_name == "get_announcements":
            result = _wrap_result(await pulse_client.get_announcements())

        else:
            raise ValueError(f"Unknown tool: {tool_name}")

    except Exception as e:
        logger.error("tool_execution_failed", tool=tool_name, error=str(e))
        raise

    logger.debug(
        "tool_execution_result",
        tool=tool_name,
        result_type=type(result).__name__,
        result_preview=str(result)[:200] if result else None,
    )
    return result
