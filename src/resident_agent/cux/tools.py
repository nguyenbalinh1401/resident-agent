"""Tool definitions for LLM function calling.

These tools are passed to the LLM for function calling.
The LLM decides which tool to call based on user message.
"""

from typing import Dict, Any, Optional, Union, List
import structlog

from resident_agent.clients.pulse_client import PulseClient
from resident_agent.auth.permission_mapper import PermissionMapper

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
            "name": "create_bill",
            "description": "Tạo hóa đơn tháng mới cho căn hộ (Admin/Staff)",
            "parameters": {
                "type": "object",
                "properties": {
                    "unit_id": {"type": "string", "description": "ID của căn hộ"},
                    "billing_month": {"type": "string", "description": "Tháng của hóa đơn (YYYY-MM-01)"},
                    "due_date": {"type": "string", "description": "Hạn thanh toán (YYYY-MM-DD)"},
                    "details": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "feeTypeId": {"type": "string", "description": "ID loại phí"},
                                "subtotal": {"type": "number", "description": "Thành tiền"},
                                "quantity": {"type": "number", "description": "Số lượng (optional)"},
                                "unitPrice": {"type": "number", "description": "Đơn giá (optional)"},
                                "oldIndex": {"type": "number", "description": "Chỉ số cũ (optional - cho điện/nước)"},
                                "newIndex": {"type": "number", "description": "Chỉ số mới (optional - cho điện/nước)"},
                            },
                            "required": ["feeTypeId", "subtotal"],
                        },
                        "description": "Danh sách các khoản phí",
                    },
                },
                "required": ["unit_id", "billing_month", "due_date", "details"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_fee_types",
            "description": "Xem danh sách các loại phí (Phí quản lý, điện, nước, gửi xe, etc.) - dùng khi tạo hóa đơn",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
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
    {
        "type": "function",
        "function": {
            "name": "get_package_detail",
            "description": "Xem chi tiết một bưu kiện (thông tin người nhận, trạng thái, lịch sử)",
            "parameters": {
                "type": "object",
                "properties": {
                    "package_id": {"type": "string", "description": "ID của bưu kiện"},
                },
                "required": ["package_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delegate_pickup",
            "description": "Ủy quyền người khác nhận bưu kiện giúp",
            "parameters": {
                "type": "object",
                "properties": {
                    "package_id": {"type": "string", "description": "ID bưu kiện"},
                    "delegate_name": {"type": "string", "description": "Tên người nhận ủy quyền"},
                    "delegate_phone": {"type": "string", "description": "Số điện thoại người nhận ủy quyền"},
                },
                "required": ["package_id", "delegate_name", "delegate_phone"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "revoke_pickup_delegation",
            "description": "Hủy ủy quyền nhận bưu kiện",
            "parameters": {
                "type": "object",
                "properties": {
                    "package_id": {"type": "string", "description": "ID bưu kiện"},
                },
                "required": ["package_id"],
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
    # ==================== Payment Tools ====================
    {
        "type": "function",
        "function": {
            "name": "get_payment_history",
            "description": "Xem lịch sử thanh toán (các giao dịch đã thực hiện)",
            "parameters": {
                "type": "object",
                "properties": {
                    "bill_id": {"type": "string", "description": "Lọc theo ID hóa đơn (optional)"},
                },
                "required": [],
            },
        },
    },
    # ==================== Notification Tools ====================
    {
        "type": "function",
        "function": {
            "name": "get_notifications",
            "description": "Xem danh sách thông báo (báo mới, nhắc nhở, cảnh báo)",
            "parameters": {
                "type": "object",
                "properties": {
                    "is_read": {
                        "type": "boolean",
                        "description": "Lọc theo đã đọc (true) hoặc chưa đọc (false), bỏ qua để xem tất cả",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mark_notification_read",
            "description": "Đánh dấu đã đọc một thông báo",
            "parameters": {
                "type": "object",
                "properties": {
                    "notification_id": {"type": "string", "description": "ID của thông báo"},
                },
                "required": ["notification_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mark_all_notifications_read",
            "description": "Đánh dấu đã đọc tất cả thông báo",
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
            "name": "get_unread_notification_count",
            "description": "Xem số lượng thông báo chưa đọc",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    # ==================== Ticket Comment Tools ====================
    {
        "type": "function",
        "function": {
            "name": "get_ticket_comments",
            "description": "Xem bình luận/cập nhật trên phiếu báo sự cố",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticket_id": {"type": "string", "description": "ID phiếu báo sự cố"},
                },
                "required": ["ticket_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_ticket_comment",
            "description": "Thêm bình luận/cập nhật cho phiếu báo sự cố",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticket_id": {"type": "string", "description": "ID phiếu báo sự cố"},
                    "content": {"type": "string", "description": "Nội dung bình luận"},
                },
                "required": ["ticket_id", "content"],
            },
        },
    },
    # ==================== Reference Data Tools ====================
    {
        "type": "function",
        "function": {
            "name": "get_ticket_categories",
            "description": "Xem danh mục sự cố (điện, nước, thang máy, an ninh, etc.) - dùng khi báo sự cố",
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
            "name": "get_amenity_categories",
            "description": "Xem danh mục tiện ích (thể thao, giải trí, sinh hoạt, etc.) - dùng khi tìm tiện ích",
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
            "name": "get_request_types",
            "description": "Xem các loại yêu cầu có thể tạo (thẻ cư dân, xe, đổi chỗ đỗ, đăng ký khách)",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    # ==================== Survey Tools ====================
    {
        "type": "function",
        "function": {
            "name": "get_surveys",
            "description": "Xem các khảo sát đang mở từ ban quản lý",
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
            "name": "submit_survey_answer",
            "description": "Gửi câu trả lời khảo sát",
            "parameters": {
                "type": "object",
                "properties": {
                    "survey_id": {"type": "string", "description": "ID khảo sát"},
                    "answers": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "Danh sách câu trả lời",
                    },
                },
                "required": ["survey_id", "answers"],
            },
        },
    },
    # ==================== Visitor Registration Tools ====================
    {
        "type": "function",
        "function": {
            "name": "register_visitor",
            "description": "Đăng ký khách đến thăm",
            "parameters": {
                "type": "object",
                "properties": {
                    "visitor_name": {"type": "string", "description": "Tên khách"},
                    "visitor_phone": {"type": "string", "description": "Số điện thoại khách"},
                    "visit_date": {"type": "string", "description": "Ngày đến (YYYY-MM-DD)"},
                    "purpose": {"type": "string", "description": "Mục đích đến thăm (optional)"},
                },
                "required": ["visitor_name", "visitor_phone", "visit_date"],
            },
        },
    },
    # ==================== Resident Request Tools ====================
    {
        "type": "function",
        "function": {
            "name": "get_my_requests",
            "description": "Xem danh sách yêu cầu của tôi (đăng ký thẻ cư dân, đăng ký xe, đăng ký khách, etc.)",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["Pending", "Approved", "Rejected"],
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
            "name": "get_request_detail",
            "description": "Xem chi tiết một yêu cầu (trạng thái, thông tin, lý do từ chối nếu có)",
            "parameters": {
                "type": "object",
                "properties": {
                    "request_id": {"type": "string", "description": "ID của yêu cầu"},
                },
                "required": ["request_id"],
            },
        },
    },
    # ==================== Resident Registries (Admin) ====================
    {
        "type": "function",
        "function": {
            "name": "get_resident_registries",
            "description": "Xem danh sách cư dân trong danh sách chờ/đã phê duyệt (Admin)",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["Pending", "Verified", "Rejected"],
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
            "name": "request_resident_verification",
            "description": "Gửi yêu cầu xác thực cư dân cho căn hộ (Resident)",
            "parameters": {
                "type": "object",
                "properties": {
                    "unit_id": {"type": "string", "description": "ID căn hộ"},
                    "full_name": {"type": "string", "description": "Họ tên cư dân"},
                    "phone_number": {"type": "string", "description": "Số điện thoại"},
                },
                "required": ["unit_id", "full_name", "phone_number"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "approve_resident_verification",
            "description": "Phê duyệt yêu cầu xác thực cư dân (Admin)",
            "parameters": {
                "type": "object",
                "properties": {
                    "registry_id": {"type": "string", "description": "ID của yêu cầu xác thực"},
                    "status": {
                        "type": "string",
                        "enum": ["Verified", "Rejected"],
                        "description": "Trạng thái mới (Verified: Duyệt, Rejected: Từ chối)",
                    },
                },
                "required": ["registry_id", "status"],
            },
        },
    },
    # ==================== Units ====================
    {
        "type": "function",
        "function": {
            "name": "get_units",
            "description": "Xem danh sách các căn hộ/phòng trong tòa nhà (Admin)",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
]


async def execute_tool(
    tool_name: str,
    params: dict,
    pulse_client: PulseClient,
    user_permissions: Optional[List[Dict[str, str]]] = None,
) -> dict:
    """Execute a tool by calling the Pulse Backend API.

    Args:
        tool_name: Name of the tool to execute
        params: Tool parameters
        pulse_client: Authenticated PulseClient instance (injected via dependency)
        user_permissions: List of user permissions for RBAC verification

    Returns:
        Tool execution result

    Raises:
        PermissionError: If user doesn't have permission to execute the tool
        Exception: If tool execution fails
    """
    logger.info("executing_tool", tool=tool_name, params=params)

    # RBAC Verification
    permission_mapper = PermissionMapper()
    if not permission_mapper.check_tool_permission(tool_name, user_permissions or []):
        logger.warning(
            "tool_execution_denied",
            tool=tool_name,
            user_permissions=user_permissions,
        )
        raise PermissionError(f"You do not have permission to use tool: {tool_name}")

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

        elif tool_name == "create_bill":
            result = await pulse_client.create_bill(**params)

        elif tool_name == "get_fee_types":
            result = _wrap_result(await pulse_client.get_fee_types())

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
            result = _wrap_result(await pulse_client.get_packages(**params))

        elif tool_name == "get_package_detail":
            result = await pulse_client.get_package(params["package_id"])

        elif tool_name == "delegate_pickup":
            result = await pulse_client.delegate_pickup(
                parcel_id=params["package_id"],
                delegate_name=params["delegate_name"],
                delegate_phone=params["delegate_phone"],
            )

        elif tool_name == "revoke_pickup_delegation":
            result = await pulse_client.revoke_pickup_delegation(
                parcel_id=params["package_id"]
            )

        # Announcement tools
        elif tool_name == "get_announcements":
            result = _wrap_result(await pulse_client.get_announcements())

        # Payment tools (read-only)
        elif tool_name == "get_payment_history":
            result = _wrap_result(
                await pulse_client.get_payment_history(bill_id=params.get("bill_id"))
            )

        # Notification tools
        elif tool_name == "get_notifications":
            is_read = params.get("is_read")
            result = _wrap_result(
                await pulse_client.get_notifications(unread_only=(is_read is False))
            )

        elif tool_name == "mark_notification_read":
            result = await pulse_client.mark_notification_read(
                params["notification_id"]
            )

        elif tool_name == "mark_all_notifications_read":
            result = await pulse_client.mark_all_notifications_read()

        elif tool_name == "get_unread_notification_count":
            result = await pulse_client.get_unread_notification_count()

        # Ticket comment tools
        elif tool_name == "get_ticket_comments":
            result = _wrap_result(
                await pulse_client.get_ticket_comments(params["ticket_id"])
            )

        elif tool_name == "add_ticket_comment":
            result = await pulse_client.add_ticket_comment(
                ticket_id=params["ticket_id"], content=params["content"]
            )

        # Reference data tools
        elif tool_name == "get_ticket_categories":
            result = _wrap_result(await pulse_client.get_ticket_categories())

        elif tool_name == "get_amenity_categories":
            result = _wrap_result(await pulse_client.get_amenity_categories())

        elif tool_name == "get_request_types":
            result = _wrap_result(await pulse_client.get_request_types())

        # Survey tools
        elif tool_name == "get_surveys":
            result = _wrap_result(await pulse_client.get_surveys())

        elif tool_name == "submit_survey_answer":
            result = await pulse_client.submit_survey_answer(
                survey_id=params["survey_id"], answers=params["answers"]
            )

        # Visitor registration tools
        elif tool_name == "register_visitor":
            result = await pulse_client.register_visitor(
                visitor_name=params["visitor_name"],
                visitor_phone=params["visitor_phone"],
                visit_date=params["visit_date"],
                purpose=params.get("purpose"),
            )

        # Resident request tools
        elif tool_name == "get_my_requests":
            result = _wrap_result(
                await pulse_client.get_resident_requests(status=params.get("status"))
            )

        elif tool_name == "get_request_detail":
            result = await pulse_client.get_resident_request(params["request_id"])

        # Resident registry tools (Admin)
        elif tool_name == "get_resident_registries":
            result = _wrap_result(await pulse_client.get_resident_registries(**params))

        elif tool_name == "approve_resident_verification":
            result = await pulse_client.update_resident_registry_status(
                registry_id=params["registry_id"], status=params["status"]
            )

        elif tool_name == "request_resident_verification":
            result = await pulse_client.request_resident_verification(**params)

        # Unit tools (Admin)
        elif tool_name == "get_units":
            result = _wrap_result(await pulse_client.get_units())

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
