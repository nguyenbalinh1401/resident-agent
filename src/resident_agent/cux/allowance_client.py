"""Allowance client for checking user permissions and capabilities.

This module handles:
- Fetching user allowances from the allowance service
- Checking if user has required capabilities
- Providing alternative suggestions when capability is denied
"""

from typing import Dict, List, Any, Optional
import structlog

logger = structlog.get_logger()


class AllowanceClient:
    """Client for checking user allowances and capabilities.

    In production, this would connect to the actual allowance service.
    For now, uses mock data for testing.
    """

    # Default capabilities by role
    DEFAULT_CAPABILITIES = {
        "resident": [
            "REPORT_INCIDENT",
            "CHECK_PACKAGE",
            "VIEW_BILLS",
            "BOOK_AMENITY",
            "SERVICE_REQUEST",
            "GENERAL_QA",
        ],
        "staff": [
            "REPORT_INCIDENT",
            "CHECK_PACKAGE",
            "VIEW_BILLS",
            "BOOK_AMENITY",
            "SERVICE_REQUEST",
            "GENERAL_QA",
            "APPROVE_BOOKING",
            "VIEW_ALL_TICKETS",
            "MANAGE_AMENITIES",
        ],
        "admin": [
            # Admin has all capabilities
            "*"  # Wildcard for all
        ],
    }

    def __init__(self, allowance_service_url: Optional[str] = None):
        """Initialize allowance client.

        Args:
            allowance_service_url: URL of the allowance service (optional)
        """
        self.allowance_service_url = allowance_service_url
        # In-memory cache for allowances
        self._cache: Dict[str, Dict[str, Any]] = {}

    async def get_allowance(self, user_id: str) -> Dict[str, Any]:
        """Get user's allowance (capabilities and roles).

        Args:
            user_id: User identifier

        Returns:
            Dict with allowed_capabilities, roles, and metadata
        """
        # Check cache first
        if user_id in self._cache:
            return self._cache[user_id]

        # In production, this would call the allowance service
        # For now, return default capabilities based on user_id pattern
        allowance = await self._fetch_allowance(user_id)

        # Cache the result
        self._cache[user_id] = allowance

        return allowance

    async def _fetch_allowance(self, user_id: str) -> Dict[str, Any]:
        """Fetch allowance from service or return default.

        Args:
            user_id: User identifier

        Returns:
            Allowance dict with capabilities and roles
        """
        # Mock implementation - in production, call actual service
        # Determine role from user_id pattern (for testing)
        if user_id.startswith("admin_"):
            role = "admin"
        elif user_id.startswith("staff_"):
            role = "staff"
        else:
            role = "resident"

        capabilities = self.DEFAULT_CAPABILITIES.get(role, self.DEFAULT_CAPABILITIES["resident"])

        return {
            "user_id": user_id,
            "allowed_capabilities": capabilities,
            "roles": [role],
            "tier": "free",
            "metadata": {
                "source": "mock",
                "fetched_at": "2026-03-02T00:00:00Z"
            }
        }

    def check_capability(
        self,
        required_capability: str,
        allowance: Dict[str, Any]
    ) -> bool:
        """Check if user has a specific capability.

        Args:
            required_capability: Capability to check
            allowance: User's allowance dict

        Returns:
            True if user has capability, False otherwise
        """
        allowed = allowance.get("allowed_capabilities", [])
        roles = allowance.get("roles", [])

        # Admin has all capabilities
        if "admin" in roles or "*" in allowed:
            return True

        return required_capability in allowed

    def suggest_alternatives(
        self,
        denied_capability: str,
        allowance: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        """Suggest alternative capabilities user can use.

        Args:
            denied_capability: Capability that was denied
            allowance: User's allowance dict

        Returns:
            List of alternative capability suggestions
        """
        # Map denied capabilities to related allowed ones
        related_capabilities = {
            "APPROVE_BOOKING": ["BOOK_AMENITY", "VIEW_BILLS"],
            "MANAGE_AMENITIES": ["BOOK_AMENITY", "VIEW_BILLS"],
            "VIEW_ALL_TICKETS": ["REPORT_INCIDENT"],
        }

        alternatives = []
        allowed = set(allowance.get("allowed_capabilities", []))

        for alt_cap in related_capabilities.get(denied_capability, []):
            if alt_cap in allowed:
                alternatives.append({
                    "capability": alt_cap,
                    "label": self._capability_to_label(alt_cap),
                    "description": self._capability_to_description(alt_cap)
                })

        return alternatives

    def _capability_to_label(self, capability: str) -> str:
        """Convert capability ID to user-friendly label."""
        labels = {
            "REPORT_INCIDENT": "🔧 Báo sự cố",
            "CHECK_PACKAGE": "📦 Kiểm tra bưu kiện",
            "VIEW_BILLS": "💳 Xem hóa đơn",
            "BOOK_AMENITY": "🏊 Đặt chỗ tiện ích",
            "SERVICE_REQUEST": "📋 Yêu cầu dịch vụ",
            "GENERAL_QA": "❓ Hỏi đáp chung",
        }
        return labels.get(capability, capability)

    def _capability_to_description(self, capability: str) -> str:
        """Convert capability ID to description."""
        descriptions = {
            "REPORT_INCIDENT": "Báo cáo sự cố bảo trì",
            "CHECK_PACKAGE": "Kiểm tra tình trạng bưu kiện",
            "VIEW_BILLS": "Xem hóa đơn chưa thanh toán",
            "BOOK_AMENITY": "Đặt chỗ bể bơi, gym, sân tennis",
            "SERVICE_REQUEST": "Yêu cầu thẻ cư dân, dịch vụ khác",
            "GENERAL_QA": "Hỏi đáp về quy định, dịch vụ",
        }
        return descriptions.get(capability, "")

    def clear_cache(self, user_id: Optional[str] = None) -> None:
        """Clear allowance cache.

        Args:
            user_id: Specific user to clear, or None for all
        """
        if user_id:
            self._cache.pop(user_id, None)
        else:
            self._cache.clear()
