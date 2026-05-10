"""Tool definitions for LLM function calling.

These tools are passed to the LLM for function calling.
The LLM decides which tool to call based on user message.
"""

from typing import Dict, Any, Optional, Union, List
import structlog

from resident_agent.clients.pulse_client import PulseClient
from resident_agent.auth.permission_mapper import PermissionMapper

logger = structlog.get_logger()

CONFIRMATION_REQUIRED_TOOLS = {
    "delete_amenity": "xóa tiện ích",
    "notify_bill_residents": "gửi thông báo hóa đơn cho cư dân",
    "create_announcement": "tạo thông báo cho toàn hệ thống",
    "complete_ticket": "đánh dấu ticket đã hoàn tất",
    "delete_resident_request": "xóa yêu cầu cư dân",
    "approve_resident_request": "duyệt yêu cầu cư dân",
    "reject_resident_request": "từ chối yêu cầu cư dân",
}


def _require_confirmation(tool_name: str, params: Dict[str, Any]) -> None:
    """Block high-impact actions until explicit confirmation is provided."""
    action_label = CONFIRMATION_REQUIRED_TOOLS.get(tool_name)
    if not action_label:
        return

    if params.get("confirm") is True:
        return

    raise ValueError(
        f"Hành động '{action_label}' cần xác nhận rõ ràng. "
        f"Hãy gọi lại tool với `confirm=true` sau khi người dùng xác nhận."
    )


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
    if not isinstance(result, dict):
        return {"value": result}
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
    {
        "type": "function",
        "function": {
            "name": "get_users",
            "description": "View all users for admin or staff backoffice",
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
            "name": "get_user_detail",
            "description": "View user detail by ID",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "User ID"},
                },
                "required": ["user_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_user_overview",
            "description": "View user overview with roles and units",
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
            "name": "get_users_by_roles",
            "description": "Find users by role names",
            "parameters": {
                "type": "object",
                "properties": {
                    "roles": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of role names",
                    },
                },
                "required": ["roles"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_user_roles",
            "description": "View roles assigned to a user",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "User ID"},
                },
                "required": ["user_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_privileged_user",
            "description": "Create an admin or staff account",
            "parameters": {
                "type": "object",
                "properties": {
                    "full_name": {"type": "string", "description": "Full name"},
                    "email": {"type": "string", "description": "Email"},
                    "password": {"type": "string", "description": "Initial password"},
                    "role_name": {"type": "string", "description": "Role name: Admin or Staff"},
                    "phone_number": {"type": "string", "description": "Phone number (optional)"},
                },
                "required": ["full_name", "email", "password", "role_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_resident_user",
            "description": "Create a resident account from admin onboarding flow",
            "parameters": {
                "type": "object",
                "properties": {
                    "full_name": {"type": "string", "description": "Full name"},
                    "email": {"type": "string", "description": "Email"},
                    "password": {"type": "string", "description": "Initial password"},
                    "phone_number": {"type": "string", "description": "Phone number (optional)"},
                },
                "required": ["full_name", "email", "password"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_user_admin",
            "description": "Update user profile fields from admin or staff backoffice",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "User ID"},
                    "full_name": {"type": "string", "description": "Updated full name"},
                    "email": {"type": "string", "description": "Updated email"},
                    "status": {"type": "string", "description": "Updated account status"},
                },
                "required": ["user_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "deactivate_user",
            "description": "Deactivate a user account",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "User ID"},
                },
                "required": ["user_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_roles",
            "description": "View all roles",
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
            "name": "get_role_permissions",
            "description": "View permissions assigned to a role",
            "parameters": {
                "type": "object",
                "properties": {
                    "role_id": {"type": "string", "description": "Role ID"},
                },
                "required": ["role_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_role",
            "description": "Create a new role",
            "parameters": {
                "type": "object",
                "properties": {
                    "role_name": {"type": "string", "description": "Role name"},
                    "description": {"type": "string", "description": "Role description"},
                },
                "required": ["role_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "assign_user_role",
            "description": "Assign a role to a user",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "User ID"},
                    "role_id": {"type": "string", "description": "Role ID"},
                },
                "required": ["user_id", "role_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remove_user_role",
            "description": "Remove a role from a user",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "User ID"},
                    "role_id": {"type": "string", "description": "Role ID"},
                },
                "required": ["user_id", "role_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_role_permission",
            "description": "Add a permission to a role",
            "parameters": {
                "type": "object",
                "properties": {
                    "role_id": {"type": "string", "description": "Role ID"},
                    "permission_id": {"type": "string", "description": "Permission ID"},
                },
                "required": ["role_id", "permission_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remove_role_permission",
            "description": "Remove a permission from a role",
            "parameters": {
                "type": "object",
                "properties": {
                    "role_id": {"type": "string", "description": "Role ID"},
                    "permission_id": {"type": "string", "description": "Permission ID"},
                },
                "required": ["role_id", "permission_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_permissions_catalog",
            "description": "View permission catalog",
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
            "name": "create_permission",
            "description": "Create a new permission entry",
            "parameters": {
                "type": "object",
                "properties": {
                    "resource": {"type": "string", "description": "Permission resource"},
                    "action": {"type": "string", "description": "Permission action"},
                },
                "required": ["resource", "action"],
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
            "name": "get_utility_preview",
            "description": "Xem bảng tính thử điện nước trước khi tạo hóa đơn cho một căn hộ (Admin/Staff)",
            "parameters": {
                "type": "object",
                "properties": {
                    "unit_id": {"type": "string", "description": "ID của căn hộ"},
                    "billing_month": {"type": "string", "description": "Tháng cần xem thử (YYYY-MM-01)"},
                },
                "required": ["unit_id", "billing_month"],
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
            "name": "create_amenity",
            "description": "Tạo tiện ích mới cho tòa nhà. Chỉ dùng khi user có quyền quản trị phù hợp.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category_id": {"type": "string", "description": "ID danh mục tiện ích"},
                    "name": {"type": "string", "description": "Tên tiện ích"},
                    "type": {
                        "type": "string",
                        "description": "Loại tiện ích, ví dụ: SwimmingPool, Gym, MeetingRoom, BBQArea, Other",
                    },
                    "description": {"type": "string", "description": "Mô tả tiện ích"},
                    "capacity": {"type": "integer", "description": "Sức chứa"},
                    "require_approval": {"type": "boolean", "description": "Có yêu cầu duyệt booking không"},
                    "max_concurrent_bookings": {"type": "integer", "description": "Số booking đồng thời tối đa"},
                    "is_active": {"type": "boolean", "description": "Tiện ích có đang hoạt động không"},
                },
                "required": ["category_id", "name", "type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_amenity",
            "description": "Cập nhật một tiện ích hiện có. Nên lấy chi tiết tiện ích trước để điền đủ dữ liệu bắt buộc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "amenity_id": {"type": "string", "description": "ID tiện ích cần cập nhật"},
                    "category_id": {"type": "string", "description": "ID danh mục tiện ích"},
                    "name": {"type": "string", "description": "Tên tiện ích"},
                    "type": {"type": "string", "description": "Loại tiện ích"},
                    "description": {"type": "string", "description": "Mô tả tiện ích"},
                    "capacity": {"type": "integer", "description": "Sức chứa"},
                    "require_approval": {"type": "boolean", "description": "Có yêu cầu duyệt booking không"},
                    "max_concurrent_bookings": {"type": "integer", "description": "Số booking đồng thời tối đa"},
                    "is_active": {"type": "boolean", "description": "Trạng thái hoạt động"},
                },
                "required": [
                    "amenity_id",
                    "category_id",
                    "name",
                    "type",
                    "max_concurrent_bookings",
                    "is_active",
                ],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_amenity",
            "description": "Xóa một tiện ích theo ID. Chỉ dùng khi user xác nhận rõ ràng.",
            "parameters": {
                "type": "object",
                "properties": {
                    "amenity_id": {"type": "string", "description": "ID tiện ích cần xóa"},
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
                        "enum": ["Pending", "Approved", "Cancelled", "Completed"],
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
    {
        "type": "function",
        "function": {
            "name": "get_bookings_queue",
            "description": "View operational amenity booking queue for admin or staff",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "description": "Filter by booking status"},
                    "from_date": {"type": "string", "description": "Start date in YYYY-MM-DD"},
                    "to_date": {"type": "string", "description": "End date in YYYY-MM-DD"},
                    "amenity_id": {"type": "string", "description": "Filter by amenity ID"},
                    "user_id": {"type": "string", "description": "Filter by user ID"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "approve_booking",
            "description": "Approve an amenity booking",
            "parameters": {
                "type": "object",
                "properties": {
                    "booking_id": {"type": "string", "description": "Booking ID"},
                },
                "required": ["booking_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reject_booking",
            "description": "Reject an amenity booking with a reason",
            "parameters": {
                "type": "object",
                "properties": {
                    "booking_id": {"type": "string", "description": "Booking ID"},
                    "reason": {"type": "string", "description": "Reason for rejection"},
                },
                "required": ["booking_id", "reason"],
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
    {
        "type": "function",
        "function": {
            "name": "get_tickets_queue",
            "description": "Xem danh sách ticket vận hành dành cho admin/staff, có thể lọc theo trạng thái, mức độ và người báo",
            "parameters": {
                "type": "object",
                "properties": {
                    "reported_by": {"type": "string", "description": "Lọc theo user báo cáo (optional)"},
                    "category_id": {"type": "string", "description": "Lọc theo danh mục ticket (optional)"},
                    "status": {
                        "type": "string",
                        "enum": ["Open", "ManualReview", "InProgress", "Resolved", "Closed", "Cancelled"],
                        "description": "Lọc theo trạng thái ticket (optional)",
                    },
                    "severity": {
                        "type": "string",
                        "enum": ["Low", "Medium", "High", "Critical"],
                        "description": "Lọc theo mức độ nghiêm trọng (optional)",
                    },
                    "page": {"type": "integer", "description": "Trang hiện tại (optional)"},
                    "page_size": {"type": "integer", "description": "Số dòng mỗi trang (optional)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_ticket_status",
            "description": "Cập nhật trạng thái ticket cho admin/staff",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticket_id": {"type": "string", "description": "ID ticket"},
                    "status": {
                        "type": "string",
                        "enum": ["InProgress", "Resolved", "Closed", "Cancelled"],
                        "description": "Trạng thái mới",
                    },
                },
                "required": ["ticket_id", "status"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_ticket_severity",
            "description": "Cập nhật mức độ nghiêm trọng của ticket",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticket_id": {"type": "string", "description": "ID ticket"},
                    "severity": {
                        "type": "string",
                        "enum": ["Low", "Medium", "High", "Critical"],
                        "description": "Mức độ mới",
                    },
                },
                "required": ["ticket_id", "severity"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "assign_ticket",
            "description": "Giao ticket cho staff xử lý",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticket_id": {"type": "string", "description": "ID ticket"},
                    "assigned_to": {"type": "string", "description": "ID user staff được giao (optional)"},
                    "notes": {"type": "string", "description": "Ghi chú phân công (optional)"},
                },
                "required": ["ticket_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "approve_ticket",
            "description": "Phê duyệt ticket đang chờ xem xét",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticket_id": {"type": "string", "description": "ID ticket"},
                },
                "required": ["ticket_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reject_ticket",
            "description": "Từ chối ticket và ghi lý do",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticket_id": {"type": "string", "description": "ID ticket"},
                    "reason": {"type": "string", "description": "Lý do từ chối (optional)"},
                },
                "required": ["ticket_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "complete_ticket",
            "description": "Đánh dấu ticket là đã xử lý xong",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticket_id": {"type": "string", "description": "ID ticket"},
                    "note": {"type": "string", "description": "Ghi chú hoàn tất (optional)"},
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
                    "delegatee_id": {"type": "string", "description": "Resident user ID to receive the delegation"},
                },
                "required": ["package_id", "delegatee_id"],
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
    {
        "type": "function",
        "function": {
            "name": "delegate_pickup_by_id",
            "description": "Ủy quyền cho một cư dân khác trong cùng căn hộ nhận bưu kiện giúp bằng user ID",
            "parameters": {
                "type": "object",
                "properties": {
                    "package_id": {"type": "string", "description": "ID bưu kiện"},
                    "delegatee_id": {"type": "string", "description": "ID user của người được ủy quyền"},
                    "delegatee_id": {"type": "string", "description": "Resident user ID to receive the delegation"},
                },
                "required": ["package_id", "delegatee_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_delivery_code",
            "description": "Tra cứu delivery code để staff tìm đúng cư dân nhận bưu kiện",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Mã giao hàng / delivery code cần tra"},
                },
                "required": ["code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_parcel_resident",
            "description": "Tìm cư dân trong một căn hộ để hỗ trợ ủy quyền nhận bưu kiện",
            "parameters": {
                "type": "object",
                "properties": {
                    "unit_id": {"type": "string", "description": "ID căn hộ"},
                    "name": {"type": "string", "description": "Tên cư dân cần tìm"},
                },
                "required": ["unit_id", "name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_pickup_token",
            "description": "Tạo pickup token/QR để cư dân đưa cho lễ tân khi nhận bưu kiện",
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
    {
        "type": "function",
        "function": {
            "name": "get_announcement_detail",
            "description": "Xem chi tiết một thông báo",
            "parameters": {
                "type": "object",
                "properties": {
                    "announcement_id": {"type": "string", "description": "ID thông báo"},
                },
                "required": ["announcement_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_announcement",
            "description": "Tạo thông báo mới cho cư dân (Admin)",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Tiêu đề thông báo"},
                    "content": {"type": "string", "description": "Nội dung thông báo"},
                    "priority": {
                        "type": "string",
                        "enum": ["Low", "Normal", "High", "Urgent"],
                        "description": "Mức độ ưu tiên",
                    },
                },
                "required": ["title", "content"],
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
    {
        "type": "function",
        "function": {
            "name": "record_manual_payment",
            "description": "Ghi nhận thanh toán thủ công tại quầy cho một hóa đơn (Admin/Staff)",
            "parameters": {
                "type": "object",
                "properties": {
                    "bill_id": {"type": "string", "description": "ID hóa đơn"},
                    "paid_by": {"type": "string", "description": "ID cư dân hoặc người thanh toán"},
                    "amount_paid": {"type": "number", "description": "Số tiền đã thu"},
                    "payment_method": {
                        "type": "string",
                        "enum": ["Cash", "Bank Transfer"],
                        "description": "Phương thức thanh toán thủ công",
                    },
                },
                "required": ["bill_id", "paid_by", "amount_paid", "payment_method"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "notify_bill_residents",
            "description": "Gửi thông báo hóa đơn đến các cư dân của căn hộ (Admin)",
            "parameters": {
                "type": "object",
                "properties": {
                    "bill_id": {"type": "string", "description": "ID hóa đơn cần gửi thông báo"},
                },
                "required": ["bill_id"],
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
    {
        "type": "function",
        "function": {
            "name": "get_resident_requests_queue",
            "description": "Xem danh sách yêu cầu cư dân để admin hoặc manager xử lý",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["Pending", "Approved", "Rejected"],
                        "description": "Lọc theo trạng thái (optional)"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_resident_request",
            "description": "Tạo một yêu cầu cư dân mới",
            "parameters": {
                "type": "object",
                "properties": {
                    "requester_id": {"type": "string", "description": "ID người tạo yêu cầu"},
                    "request_type_id": {"type": "string", "description": "ID loại yêu cầu"},
                    "request_data_json": {"type": "string", "description": "Payload JSON dạng chuỗi"}
                },
                "required": ["request_type_id", "request_data_json"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_resident_request",
            "description": "Cập nhật payload JSON của một yêu cầu cư dân",
            "parameters": {
                "type": "object",
                "properties": {
                    "request_id": {"type": "string", "description": "ID yêu cầu"},
                    "request_data_json": {"type": "string", "description": "Payload JSON mới dạng chuỗi"}
                },
                "required": ["request_id", "request_data_json"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_resident_request",
            "description": "Xóa một yêu cầu cư dân",
            "parameters": {
                "type": "object",
                "properties": {
                    "request_id": {"type": "string", "description": "ID yêu cầu"}
                },
                "required": ["request_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "preverify_resident_request",
            "description": "Chạy kiểm tra nợ, quota và residency trước khi duyệt yêu cầu",
            "parameters": {
                "type": "object",
                "properties": {
                    "request_id": {"type": "string", "description": "ID yêu cầu"}
                },
                "required": ["request_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "approve_resident_request",
            "description": "Duyệt một yêu cầu cư dân",
            "parameters": {
                "type": "object",
                "properties": {
                    "request_id": {"type": "string", "description": "ID yêu cầu"},
                    "notes": {"type": "string", "description": "Ghi chú duyệt (optional)"}
                },
                "required": ["request_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "reject_resident_request",
            "description": "Từ chối một yêu cầu cư dân với lý do rõ ràng",
            "parameters": {
                "type": "object",
                "properties": {
                    "request_id": {"type": "string", "description": "ID yêu cầu"},
                    "reason": {"type": "string", "description": "Lý do từ chối"}
                },
                "required": ["request_id", "reason"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_resident_request_audit_logs",
            "description": "Xem lịch sử duyệt hoặc từ chối của một yêu cầu cư dân",
            "parameters": {
                "type": "object",
                "properties": {
                    "request_id": {"type": "string", "description": "ID yêu cầu"}
                },
                "required": ["request_id"]
            }
        }
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
            "name": "get_resident_registry_detail",
            "description": "View resident registry detail by ID",
            "parameters": {
                "type": "object",
                "properties": {
                    "registry_id": {"type": "string", "description": "Resident registry ID"},
                },
                "required": ["registry_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_resident_registry",
            "description": "Create a pre-approved resident registry entry",
            "parameters": {
                "type": "object",
                "properties": {
                    "phone_number": {"type": "string", "description": "Resident phone number"},
                    "unit_id": {"type": "string", "description": "Unit ID"},
                    "full_name": {"type": "string", "description": "Resident full name (optional)"},
                    "email": {"type": "string", "description": "Resident email (optional)"},
                },
                "required": ["phone_number", "unit_id"],
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
    {
        "type": "function",
        "function": {
            "name": "get_building_overview",
            "description": "View building overview",
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
            "name": "delete_resident_registry",
            "description": "Delete a resident registry entry",
            "parameters": {
                "type": "object",
                "properties": {
                    "registry_id": {"type": "string", "description": "Resident registry ID"},
                },
                "required": ["registry_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "bulk_update_resident_registry_status",
            "description": "Bulk update resident registry statuses",
            "parameters": {
                "type": "object",
                "properties": {
                    "registry_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of resident registry IDs",
                    },
                    "status": {
                        "type": "string",
                        "enum": ["Pending", "Verified", "Rejected"],
                        "description": "New status",
                    },
                },
                "required": ["registry_ids", "status"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_blocks",
            "description": "View building blocks",
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
            "name": "get_block_floors",
            "description": "View floors for a block",
            "parameters": {
                "type": "object",
                "properties": {
                    "block_id": {"type": "string", "description": "Block ID"},
                },
                "required": ["block_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_unit_detail",
            "description": "View unit detail",
            "parameters": {
                "type": "object",
                "properties": {
                    "unit_id": {"type": "string", "description": "Unit ID"},
                },
                "required": ["unit_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_unit",
            "description": "Create a new unit",
            "parameters": {
                "type": "object",
                "properties": {
                    "unit_number": {"type": "string", "description": "Unit number"},
                    "floor_id": {"type": "string", "description": "Floor ID (optional)"},
                    "unit_type_id": {"type": "string", "description": "Unit type ID (optional)"},
                },
                "required": ["unit_number"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_unit_status",
            "description": "Update unit status",
            "parameters": {
                "type": "object",
                "properties": {
                    "unit_id": {"type": "string", "description": "Unit ID"},
                    "status": {"type": "string", "description": "New unit status"},
                },
                "required": ["unit_id", "status"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_resident_units",
            "description": "View resident-unit mappings",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "User ID filter"},
                    "unit_id": {"type": "string", "description": "Unit ID filter"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "assign_resident_to_unit",
            "description": "Assign a resident to a unit",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "User ID"},
                    "unit_id": {"type": "string", "description": "Unit ID"},
                    "relationship": {"type": "string", "description": "Relationship to unit"},
                    "move_in_date": {"type": "string", "description": "Move-in date in YYYY-MM-DD"},
                },
                "required": ["user_id", "unit_id", "relationship"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_access_cards",
            "description": "View access cards in current scope",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "Optional user ID filter"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_access_card_detail",
            "description": "View access card detail",
            "parameters": {
                "type": "object",
                "properties": {
                    "card_id": {"type": "string", "description": "Access card ID"},
                },
                "required": ["card_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_access_card",
            "description": "Create a new access card",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "User ID"},
                    "card_number": {"type": "string", "description": "Card number"},
                    "unit_id": {"type": "string", "description": "Unit ID (optional)"},
                    "relationship": {"type": "string", "description": "Relationship to unit (optional)"},
                },
                "required": ["user_id", "card_number"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_access_card_status",
            "description": "Update access card status",
            "parameters": {
                "type": "object",
                "properties": {
                    "card_id": {"type": "string", "description": "Access card ID"},
                    "status": {"type": "string", "description": "New card status"},
                    "reason": {"type": "string", "description": "Reason (optional)"},
                },
                "required": ["card_id", "status"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_access_card",
            "description": "Delete an access card",
            "parameters": {
                "type": "object",
                "properties": {
                    "card_id": {"type": "string", "description": "Access card ID"},
                },
                "required": ["card_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_community_events",
            "description": "View community events",
            "parameters": {
                "type": "object",
                "properties": {
                    "include_unpublished": {"type": "boolean", "description": "Include unpublished events for privileged roles"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_community_event_detail",
            "description": "View community event detail",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {"type": "string", "description": "Community event ID"},
                },
                "required": ["event_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_community_event",
            "description": "Create a community event",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Event title"},
                    "description": {"type": "string", "description": "Event description"},
                    "location": {"type": "string", "description": "Event location"},
                    "start_at": {"type": "string", "description": "Start time in ISO format"},
                    "end_at": {"type": "string", "description": "End time in ISO format"},
                    "capacity": {"type": "integer", "description": "Event capacity"},
                    "is_published": {"type": "boolean", "description": "Publish immediately"},
                },
                "required": ["title", "description", "location", "start_at", "end_at", "capacity"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "register_community_event",
            "description": "Register current user for a community event",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {"type": "string", "description": "Community event ID"},
                },
                "required": ["event_id"],
            },
        },
    },
    # ==================== Vehicle Tools ====================
    {
        "type": "function",
        "function": {
            "name": "get_my_vehicles",
            "description": "Xem danh sách xe đã đăng ký của tôi (biển số, loại xe, trạng thái)",
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
            "name": "register_vehicle",
            "description": "Đăng ký phương tiện mới (ô tô, xe máy, etc.)",
            "parameters": {
                "type": "object",
                "properties": {
                    "plate_number": {"type": "string", "description": "Biển số xe"},
                    "brand": {"type": "string", "description": "Hãng xe/Hiệu xe"},
                    "color": {"type": "string", "description": "Màu xe"},
                    "vehicle_type": {
                        "type": "string", 
                        "enum": ["Car", "Motorcycle", "Bicycle", "Electric motorcycle"],
                        "description": "Loại phương tiện"
                    },
                },
                "required": ["plate_number", "brand", "color", "vehicle_type"],
            },
        },
    },
]


async def execute_tool(
    tool_name: str,
    params: dict,
    pulse_client: PulseClient,
    user_permissions: Optional[List[Dict[str, str]]] = None,
    attachments: Optional[List[Dict[str, Any]]] = None,
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

        elif tool_name == "get_users":
            result = _wrap_result(await pulse_client.get_users())

        elif tool_name == "get_user_detail":
            result = await pulse_client.get_user(params["user_id"])

        elif tool_name == "get_user_overview":
            result = _wrap_result(await pulse_client.get_user_overview())

        elif tool_name == "get_users_by_roles":
            result = _wrap_result(await pulse_client.get_users_by_roles(params["roles"]))

        elif tool_name == "get_user_roles":
            result = _wrap_result(await pulse_client.get_user_roles(params["user_id"]))

        elif tool_name == "create_privileged_user":
            result = await pulse_client.create_privileged_user(**params)

        elif tool_name == "create_resident_user":
            result = await pulse_client.create_resident_user(**params)

        elif tool_name == "update_user_admin":
            result = await pulse_client.update_user_admin(**params)

        elif tool_name == "deactivate_user":
            result = await pulse_client.deactivate_user(params["user_id"])

        elif tool_name == "get_roles":
            result = _wrap_result(await pulse_client.get_roles())

        elif tool_name == "get_role_permissions":
            result = _wrap_result(await pulse_client.get_role_permissions(params["role_id"]))

        elif tool_name == "create_role":
            result = await pulse_client.create_role(**params)

        elif tool_name == "assign_user_role":
            result = await pulse_client.assign_user_role(
                user_id=params["user_id"],
                role_id=params["role_id"],
            )

        elif tool_name == "remove_user_role":
            result = await pulse_client.remove_user_role(
                user_id=params["user_id"],
                role_id=params["role_id"],
            )

        elif tool_name == "add_role_permission":
            result = await pulse_client.add_role_permission(
                role_id=params["role_id"],
                permission_id=params["permission_id"],
            )

        elif tool_name == "remove_role_permission":
            result = await pulse_client.remove_role_permission(
                role_id=params["role_id"],
                permission_id=params["permission_id"],
            )

        elif tool_name == "get_permissions_catalog":
            result = _wrap_result(await pulse_client.get_permissions())

        elif tool_name == "create_permission":
            result = await pulse_client.create_permission(**params)

        # Bills tools
        elif tool_name == "get_bills":
            result = _wrap_result(await pulse_client.get_bills(**params))

        elif tool_name == "get_bill_detail":
            result = await pulse_client.get_bill(params["bill_id"])

        elif tool_name == "create_bill":
            result = await pulse_client.create_bill(**params)

        elif tool_name == "get_utility_preview":
            result = _wrap_result(await pulse_client.get_utility_preview(**params))

        elif tool_name == "get_fee_types":
            result = _wrap_result(await pulse_client.get_fee_types())

        # Amenity tools
        elif tool_name == "get_amenities":
            result = _wrap_result(await pulse_client.get_amenities(**params))

        elif tool_name == "get_amenity_detail":
            result = await pulse_client.get_amenity(params["amenity_id"])

        elif tool_name == "create_amenity":
            result = await pulse_client.create_amenity(**params)

        elif tool_name == "update_amenity":
            result = await pulse_client.update_amenity(**params)

        elif tool_name == "delete_amenity":
            result = await pulse_client.delete_amenity(params["amenity_id"])

        elif tool_name == "book_amenity":
            result = await pulse_client.create_booking(**params)

        elif tool_name == "get_my_bookings":
            result = _wrap_result(await pulse_client.get_bookings(**params))

        elif tool_name == "cancel_booking":
            result = await pulse_client.cancel_booking(params["booking_id"])

        elif tool_name == "get_bookings_queue":
            result = _wrap_result(await pulse_client.get_bookings_queue(**params))

        elif tool_name == "approve_booking":
            result = await pulse_client.approve_booking(params["booking_id"])

        elif tool_name == "reject_booking":
            result = await pulse_client.reject_booking(
                booking_id=params["booking_id"],
                reason=params["reason"],
            )

        # Incident tools
        elif tool_name == "create_incident":
            created_ticket = await pulse_client.create_ticket(**params)
            ticket_id = None
            if isinstance(created_ticket, dict):
                ticket_id = (
                    created_ticket.get("ticketId")
                    or created_ticket.get("id")
                    or created_ticket.get("value")
                )
            elif created_ticket is not None:
                ticket_id = created_ticket

            uploaded_images: List[str] = []
            if ticket_id and attachments:
                uploaded_images = await pulse_client.upload_ticket_images_from_attachments(
                    str(ticket_id),
                    attachments=attachments,
                    image_type="Before",
                )

            result = _wrap_result(created_ticket)
            if uploaded_images:
                result["uploadedImageUrls"] = uploaded_images

        elif tool_name == "get_my_incidents":
            result = _wrap_result(await pulse_client.get_my_incidents(**params))

        elif tool_name == "get_incident_detail":
            result = await pulse_client.get_my_incident(params["ticket_id"])

        elif tool_name == "get_tickets_queue":
            result = _wrap_result(await pulse_client.get_tickets(**params))

        elif tool_name == "update_ticket_status":
            result = await pulse_client.update_ticket_status(
                ticket_id=params["ticket_id"],
                status=params["status"],
            )

        elif tool_name == "update_ticket_severity":
            result = await pulse_client.update_ticket_severity(
                ticket_id=params["ticket_id"],
                severity=params["severity"],
            )

        elif tool_name == "assign_ticket":
            result = await pulse_client.assign_ticket(
                ticket_id=params["ticket_id"],
                assigned_to=params.get("assigned_to"),
                notes=params.get("notes"),
            )

        elif tool_name == "approve_ticket":
            result = await pulse_client.approve_ticket(params["ticket_id"])

        elif tool_name == "reject_ticket":
            result = await pulse_client.reject_ticket(
                ticket_id=params["ticket_id"],
                reason=params.get("reason"),
            )

        elif tool_name == "complete_ticket":
            result = await pulse_client.complete_ticket(
                ticket_id=params["ticket_id"],
                note=params.get("note"),
            )

        # Package tools
        elif tool_name == "get_packages":
            result = _wrap_result(await pulse_client.get_packages(**params))

        elif tool_name == "get_package_detail":
            result = await pulse_client.get_package(params["package_id"])

        elif tool_name == "delegate_pickup":
            delegatee_id = params.get("delegatee_id")
            if not delegatee_id:
                raise ValueError(
                    "delegate_pickup now requires delegatee_id. "
                    "Use lookup_parcel_resident first to find the resident user ID."
                )
            result = await pulse_client.delegate_pickup(
                parcel_id=params["package_id"],
                delegatee_id=delegatee_id,
            )

        elif tool_name == "revoke_pickup_delegation":
            result = await pulse_client.revoke_pickup_delegation(
                parcel_id=params["package_id"]
            )

        elif tool_name == "delegate_pickup_by_id":
            result = await pulse_client.delegate_pickup(
                parcel_id=params["package_id"],
                delegatee_id=params["delegatee_id"],
            )

        elif tool_name == "lookup_delivery_code":
            result = _wrap_result(await pulse_client.lookup_delivery_code(params["code"]))

        elif tool_name == "lookup_parcel_resident":
            result = _wrap_result(
                await pulse_client.lookup_parcel_resident(
                    unit_id=params["unit_id"],
                    name=params["name"],
                )
            )

        elif tool_name == "generate_pickup_token":
            result = await pulse_client.generate_pickup_token(params["package_id"])

        # Announcement tools
        elif tool_name == "get_announcements":
            result = _wrap_result(await pulse_client.get_announcements())

        elif tool_name == "get_announcement_detail":
            result = await pulse_client.get_announcement(params["announcement_id"])

        elif tool_name == "create_announcement":
            result = await pulse_client.create_announcement(
                title=params["title"],
                content=params["content"],
                priority=params.get("priority", "Normal"),
            )

        # Payment tools (read-only)
        elif tool_name == "get_payment_history":
            result = _wrap_result(
                await pulse_client.get_payment_history(
                    bill_id=params.get("bill_id"),
                    paid_by=params.get("paid_by"),
                    page=params.get("page", 1),
                    page_size=params.get("page_size", 20),
                )
            )

        elif tool_name == "record_manual_payment":
            result = await pulse_client.record_manual_payment(**params)

        elif tool_name == "notify_bill_residents":
            result = await pulse_client.notify_bill_residents(params["bill_id"])

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

        elif tool_name == "get_resident_requests_queue":
            result = _wrap_result(
                await pulse_client.get_resident_requests(status=params.get("status"))
            )

        elif tool_name == "create_resident_request":
            result = await pulse_client.create_resident_request(**params)

        elif tool_name == "update_resident_request":
            result = await pulse_client.update_resident_request(
                request_id=params["request_id"],
                request_data_json=params["request_data_json"],
            )

        elif tool_name == "delete_resident_request":
            result = await pulse_client.delete_resident_request(params["request_id"])

        elif tool_name == "preverify_resident_request":
            result = await pulse_client.preverify_resident_request(params["request_id"])

        elif tool_name == "approve_resident_request":
            result = await pulse_client.approve_resident_request(
                request_id=params["request_id"],
                notes=params.get("notes"),
            )

        elif tool_name == "reject_resident_request":
            result = await pulse_client.reject_resident_request(
                request_id=params["request_id"],
                reason=params["reason"],
            )

        elif tool_name == "get_resident_request_audit_logs":
            result = _wrap_result(
                await pulse_client.get_resident_request_audit_logs(params["request_id"])
            )

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

        elif tool_name == "get_resident_registry_detail":
            result = await pulse_client.get_resident_registry(params["registry_id"])

        elif tool_name == "create_resident_registry":
            result = await pulse_client.create_resident_registry(**params)

        elif tool_name == "approve_resident_verification":
            result = await pulse_client.update_resident_registry_status(
                registry_id=params["registry_id"], status=params["status"]
            )

        elif tool_name == "delete_resident_registry":
            result = await pulse_client.delete_resident_registry(params["registry_id"])

        elif tool_name == "bulk_update_resident_registry_status":
            result = await pulse_client.bulk_update_resident_registry_status(
                registry_ids=params["registry_ids"],
                status=params["status"],
            )

        elif tool_name == "request_resident_verification":
            result = await pulse_client.request_resident_verification(**params)

        # Unit tools (Admin)
        elif tool_name == "get_building_overview":
            result = await pulse_client.get_building_overview()

        elif tool_name == "get_blocks":
            result = _wrap_result(await pulse_client.get_blocks())

        elif tool_name == "get_block_floors":
            result = _wrap_result(await pulse_client.get_block_floors(params["block_id"]))

        elif tool_name == "get_units":
            result = await pulse_client.get_units(**params)

        elif tool_name == "get_unit_detail":
            result = await pulse_client.get_unit(params["unit_id"])

        elif tool_name == "create_unit":
            result = await pulse_client.create_unit(**params)

        elif tool_name == "update_unit_status":
            result = await pulse_client.update_unit_status(
                unit_id=params["unit_id"],
                status=params["status"],
            )

        elif tool_name == "get_resident_units":
            result = _wrap_result(await pulse_client.get_resident_units(**params))

        elif tool_name == "assign_resident_to_unit":
            result = await pulse_client.assign_resident_to_unit(**params)

        # Access card tools
        elif tool_name == "get_access_cards":
            result = _wrap_result(await pulse_client.get_access_cards(**params))

        elif tool_name == "get_access_card_detail":
            result = await pulse_client.get_access_card(params["card_id"])

        elif tool_name == "create_access_card":
            result = await pulse_client.create_access_card(**params)

        elif tool_name == "update_access_card_status":
            result = await pulse_client.update_access_card_status(
                card_id=params["card_id"],
                status=params["status"],
                reason=params.get("reason"),
            )

        elif tool_name == "delete_access_card":
            result = await pulse_client.delete_access_card(params["card_id"])

        # Community event tools
        elif tool_name == "get_community_events":
            result = _wrap_result(await pulse_client.get_community_events(**params))

        elif tool_name == "get_community_event_detail":
            result = await pulse_client.get_community_event(params["event_id"])

        elif tool_name == "create_community_event":
            result = await pulse_client.create_community_event(**params)

        elif tool_name == "register_community_event":
            result = await pulse_client.register_community_event(params["event_id"])

        # Vehicle tools
        elif tool_name == "get_my_vehicles":
            result = _wrap_result(await pulse_client.get_my_vehicles())

        elif tool_name == "register_vehicle":
            result = await pulse_client.register_vehicle(**params)

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
