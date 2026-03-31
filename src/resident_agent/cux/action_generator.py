"""Action button generator for chat responses.

Generates contextual action buttons based on:
- Last tool called
- User capabilities
- Conversation context
"""

from typing import List, Optional, Dict, Any
import structlog

from resident_agent.schemas.chat_schemas import ActionButton, ActionStyle

logger = structlog.get_logger()


class ActionGenerator:
    """Generate action buttons based on context."""

    # Action templates organized by context
    ACTION_TEMPLATES = {
        # After viewing bills
        "get_bills": [
            {
                "label": "💳 Thanh toán",
                "action_type": "make_payment",
                "style": ActionStyle.PRIMARY,
            },
            {
                "label": "📄 Xem chi tiết",
                "action_type": "view_bill_detail",
                "style": ActionStyle.SECONDARY,
            },
        ],
        # After viewing bill detail
        "get_bill_detail": [
            {
                "label": "💳 Thanh toán",
                "action_type": "make_payment",
                "style": ActionStyle.PRIMARY,
            },
        ],
        # After viewing amenities
        "get_amenities": [
            {
                "label": "📅 Đặt chỗ",
                "action_type": "book_amenity",
                "style": ActionStyle.PRIMARY,
            },
        ],
        # After booking
        "book_amenity": [
            {
                "label": "📋 Xem lịch đặt",
                "action_type": "view_bookings",
                "style": ActionStyle.SECONDARY,
            },
            {
                "label": "❌ Hủy đặt chỗ",
                "action_type": "cancel_booking",
                "style": ActionStyle.OUTLINE,
            },
        ],
        # After viewing bookings
        "get_my_bookings": [
            {
                "label": "📅 Đặt thêm",
                "action_type": "book_amenity",
                "style": ActionStyle.PRIMARY,
            },
        ],
        # After creating incident
        "create_incident": [
            {
                "label": "📋 Theo dõi phiếu",
                "action_type": "view_incidents",
                "style": ActionStyle.SECONDARY,
            },
        ],
        # After viewing incidents
        "get_my_incidents": [
            {
                "label": "🔧 Báo sự cố mới",
                "action_type": "report_incident",
                "style": ActionStyle.PRIMARY,
            },
        ],
        # After viewing packages
        "get_packages": [
            {
                "label": "📦 Chi tiết",
                "action_type": "view_package_detail",
                "style": ActionStyle.SECONDARY,
            },
        ],
    }

    # Default quick actions (shown when no specific context)
    DEFAULT_ACTIONS = [
        {
            "label": "🔧 Báo sự cố",
            "action_type": "report_incident",
            "style": ActionStyle.PRIMARY,
        },
        {
            "label": "📦 Bưu kiện",
            "action_type": "check_package",
            "style": ActionStyle.SECONDARY,
        },
        {
            "label": "💳 Hóa đơn",
            "action_type": "view_bills",
            "style": ActionStyle.SECONDARY,
        },
        {
            "label": "🏊 Đặt tiện ích",
            "action_type": "book_amenity",
            "style": ActionStyle.OUTLINE,
        },
    ]

    # Map capability to default actions
    CAPABILITY_ACTIONS = {
        "INCIDENT_REPORT": {
            "label": "🔧 Báo sự cố",
            "action_type": "report_incident",
            "style": ActionStyle.PRIMARY,
        },
        "PACKAGE_VIEW": {
            "label": "📦 Bưu kiện",
            "action_type": "check_package",
            "style": ActionStyle.SECONDARY,
        },
        "BILLS_VIEW": {
            "label": "💳 Hóa đơn",
            "action_type": "view_bills",
            "style": ActionStyle.SECONDARY,
        },
        "AMENITY_BOOK": {
            "label": "🏊 Đặt tiện ích",
            "action_type": "book_amenity",
            "style": ActionStyle.OUTLINE,
        },
        "AMENITY_VIEW": {
            "label": "🏊 Xem tiện ích",
            "action_type": "view_amenities",
            "style": ActionStyle.OUTLINE,
        },
    }

    def generate_actions(
        self,
        last_tool: Optional[str] = None,
        capabilities: Optional[List[str]] = None,
        tool_result: Optional[Dict[str, Any]] = None,
        max_actions: int = 4,
    ) -> List[ActionButton]:
        """Generate action buttons based on context.

        Args:
            last_tool: Name of the last tool called
            capabilities: User's capabilities
            tool_result: Result from the last tool call
            max_actions: Maximum number of actions to return

        Returns:
            List of ActionButton objects
        """
        actions = []

        # If we have context from last tool, use contextual actions
        if last_tool and last_tool in self.ACTION_TEMPLATES:
            template_actions = self.ACTION_TEMPLATES[last_tool]

            for action_template in template_actions:
                if self._check_capability(action_template["action_type"], capabilities):
                    actions.append(
                        ActionButton(
                            id=action_template["action_type"],
                            label=action_template["label"],
                            action_type=action_template["action_type"],
                            style=action_template["style"],
                        )
                    )

        # If we don't have contextual actions, use capability-based defaults
        if not actions:
            actions = self._get_default_actions_for_capabilities(capabilities or [])

        # Limit to max_actions
        return actions[:max_actions]

    def _check_capability(
        self,
        action_type: str,
        capabilities: Optional[List[str]],
    ) -> bool:
        """Check if user has capability for an action.

        Args:
            action_type: Action type to check
            capabilities: User's capabilities

        Returns:
            True if user has the capability
        """
        if not capabilities:
            return True  # Allow if no capability filter

        if "*" in capabilities or "admin" in capabilities:
            return True

        # Map action types to capabilities
        action_to_capability = {
            "make_payment": "BILLS_PAY",
            "view_bills": "BILLS_VIEW",
            "view_bill_detail": "BILLS_VIEW",
            "book_amenity": "AMENITY_BOOK",
            "cancel_booking": "AMENITY_BOOK",
            "view_amenities": "AMENITY_VIEW",
            "view_bookings": "AMENITY_VIEW",
            "report_incident": "INCIDENT_REPORT",
            "view_incidents": "INCIDENT_VIEW",
            "check_package": "PACKAGE_VIEW",
            "view_package_detail": "PACKAGE_VIEW",
        }

        required_cap = action_to_capability.get(action_type)
        if required_cap:
            return required_cap in capabilities

        return True  # Allow unknown actions

    def _get_default_actions_for_capabilities(
        self,
        capabilities: List[str],
    ) -> List[ActionButton]:
        """Get default actions filtered by capabilities.

        Args:
            capabilities: User's capabilities

        Returns:
            List of ActionButton objects
        """
        actions = []

        for cap in capabilities:
            if cap in self.CAPABILITY_ACTIONS:
                action = self.CAPABILITY_ACTIONS[cap]
                actions.append(
                    ActionButton(
                        id=action["action_type"],
                        label=action["label"],
                        action_type=action["action_type"],
                        style=action["style"],
                    )
                )

        # If no capability-based actions, return defaults
        if not actions:
            for action in self.DEFAULT_ACTIONS:
                actions.append(
                    ActionButton(
                        id=action["action_type"],
                        label=action["label"],
                        action_type=action["action_type"],
                        style=action["style"],
                    )
                )

        return actions

    def get_navigation_actions(self) -> List[ActionButton]:
        """Get navigation actions for general navigation.

        Returns:
            List of navigation ActionButton objects
        """
        return [
            ActionButton(
                id="go_home",
                label="🏠 Trang chủ",
                action_type="navigate",
                params={"screen": "home"},
                style=ActionStyle.SECONDARY,
            ),
            ActionButton(
                id="go_profile",
                label="👤 Tài khoản",
                action_type="navigate",
                params={"screen": "profile"},
                style=ActionStyle.OUTLINE,
            ),
        ]
