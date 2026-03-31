"""Tool definitions for LLM function calling.

These tools are passed to the LLM for function calling.
The LLM decides which tool to call based on user message.
"""

from typing import Dict, Any, Optional
import structlog

from resident_agent.clients.pulse_client import PulseClient, PulseConfig

logger = structlog.get_logger()

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


def get_tools_for_capabilities(
    capabilities: list[str],
) -> list[dict]:
    """Filter tools based on user capabilities.

    Args:
        capabilities: List of capability strings the user has access to

    Returns:
        Filtered list of tools the user can use
    """
    # Map capabilities to tool names
    capability_to_tool = {
        "PROFILE_VIEW": ["get_profile", "get_bill_detail"],
        "PROFILE_UPDATE": ["update_contact"],
        "BILLS_VIEW": ["get_bills", "get_bill_detail"],
        "BILLS_PAY": ["make_payment"],
        "AMENITY_VIEW": ["get_amenities", "get_amenity_detail", "get_my_bookings"],
        "AMENITY_BOOK": ["book_amenity", "cancel_booking"],
        "INCIDENT_REPORT": ["create_incident"],
        "INCIDENT_VIEW": ["get_my_incidents", "get_incident_detail"],
        "PACKAGE_VIEW": ["get_packages"],
        "NOTIFICATION_VIEW": ["get_announcements"],
    }

    # Start with tools everyone can use
    allowed_tool_names = {"get_profile"}

    # Add tools based on capabilities
    for cap in capabilities:
        if cap in capability_to_tool:
            allowed_tool_names.update(capability_to_tool[cap])

    # If user has wildcard capability, return all tools
    if "*" in capabilities or "admin" in capabilities:
        return TOOLS

    # Filter and return tools
    return [
        tool
        for tool in TOOLS
        if tool["function"]["name"] in allowed_tool_names
    ]


async def execute_tool(
    tool_name: str,
    params: dict,
    pulse_token: str,
    pulse_backend_url: str = "http://localhost:8080",
) -> dict:
    """Execute a tool by calling the Pulse Backend API.

    Args:
        tool_name: Name of the tool to execute
        params: Tool parameters
        pulse_token: JWT token for Pulse Backend
        pulse_backend_url: Base URL for Pulse Backend

    Returns:
        Tool execution result

    Raises:
        Exception: If tool execution fails
    """
    logger.info("executing_tool", tool=tool_name, params=params)

    config = PulseConfig(base_url=pulse_backend_url, token=pulse_token)

    async with PulseClient(config) as client:
        # Profile tools
        if tool_name == "get_profile":
            return await client.get_current_user()

        if tool_name == "update_contact":
            return await client.update_profile(**params)

        # Bills tools
        if tool_name == "get_bills":
            return await client.get_bills(**params)

        if tool_name == "get_bill_detail":
            return await client.get_bill(params["bill_id"])

        if tool_name == "make_payment":
            return await client.create_payment(**params)

        # Amenity tools
        if tool_name == "get_amenities":
            return await client.get_amenities(**params)

        if tool_name == "get_amenity_detail":
            return await client.get_amenity(params["amenity_id"])

        if tool_name == "book_amenity":
            return await client.create_booking(**params)

        if tool_name == "get_my_bookings":
            return await client.get_bookings(**params)

        if tool_name == "cancel_booking":
            return await client.cancel_booking(params["booking_id"])

        # Incident tools
        if tool_name == "create_incident":
            return await client.create_ticket(**params)

        if tool_name == "get_my_incidents":
            return await client.get_tickets(**params)

        if tool_name == "get_incident_detail":
            return await client.get_ticket(params["ticket_id"])

        # Package tools
        if tool_name == "get_packages":
            # Use mock data since Pulse Backend Packages endpoint is not available
            status_filter = params.get("status")
            if status_filter:
                filtered = [p for p in MOCK_PACKAGES if p["status"] == status_filter]
                return {"packages": filtered, "total": len(filtered), "mock": True}
            return {"packages": MOCK_PACKAGES, "total": len(MOCK_PACKAGES), "mock": True}

        # Announcement tools
        if tool_name == "get_announcements":
            limit = params.get("limit", 10)
            return await client.get_announcements(limit=limit)

        # Unknown tool
        raise ValueError(f"Unknown tool: {tool_name}")
