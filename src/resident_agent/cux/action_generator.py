"""Action router and result formatter using LLM.

Handles:
- Action routing with LLM-based permission validation
- Tool result formatting as markdown
"""

import json
from typing import List, Optional, Dict, Any
import structlog

from resident_agent.auth.permission_mapper import PermissionMapper

logger = structlog.get_logger()


class ActionGenerator:
    """Route actions and format results using LLM."""

    def __init__(
        self,
        openai_client: Optional[Any] = None,
        prompts: Optional[Dict[str, str]] = None,
        tool_permissions: Optional[Dict[str, str]] = None,
        model: str = "gemini-2.5-flash",
    ):
        """Initialize ActionGenerator.

        Args:
            openai_client: OpenAI client for LLM calls
            prompts: Prompts dict loaded from prompts.yaml
            tool_permissions: Mapping of tool_name -> required permission
            model: LLM model to use 
        """
        self.openai_client = openai_client
        self.prompts = prompts or {}
        self.tool_permissions = tool_permissions or {}
        self.model = model or "gemini-2.5-flash"
        self.permission_mapper = PermissionMapper()

    async def resolve_action(
        self,
        action: str,
        permissions: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        """Use LLM to resolve action to tool with permission check.

        Args:
            action: Action type from UI (e.g., "view_bills", "report_incident")
            permissions: User's permissions from JWT

        Returns:
            Dict: {"allowed": bool, "tool": str, "params": dict, "message": str}
        """
        if not self.openai_client:
            return self._fallback_resolve_action(action, permissions)

        permissions = self.permission_mapper.normalize_permissions(permissions)

        # Build permission string
        perm_list = []
        for p in permissions:
            if p.get("resource") == "*":
                perm_list.append("ADMIN (full access)")
            else:
                perm_list.append(f"{p.get('resource')}.{p.get('action')}")
        perm_str = ", ".join(perm_list) if perm_list else "No permissions"

        # Build available tools string from tool_permissions
        tools_desc = []
        for tool, perm in self.tool_permissions.items():
            perm_display = perm if perm else "Public"
            tools_desc.append(f"- {tool} ({perm_display})")
        tools_str = "\n".join(tools_desc) if tools_desc else "No tools configured"

        # Get prompt template
        prompt_template = self.prompts.get("action_router", _DEFAULT_ACTION_ROUTER_PROMPT)
        prompt = prompt_template.format(
            action=action,
            permissions=perm_str,
            tools=tools_str,
        )

        try:
            response = await self.openai_client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0,
            )

            result = json.loads(response.choices[0].message.content)
            logger.debug("llm_action_resolved", action=action, result=result)
            return result

        except Exception as e:
            logger.error("llm_action_resolve_failed", action=action, error=str(e))
            return self._fallback_resolve_action(action, permissions)

    def _fallback_resolve_action(self, action: str, permissions: List[Dict[str, str]]) -> Dict[str, Any]:
        """Fallback action resolution without LLM."""
        permissions = self.permission_mapper.normalize_permissions(permissions)

        # Check for admin permission
        for p in permissions:
            if p.get("resource") == "*":
                # Admin: try to find matching tool
                tool = self._find_tool_for_action(action)
                if tool:
                    return {"allowed": True, "tool": tool, "params": {}}

        # Check permission for specific action
        tool = self._find_tool_for_action(action)
        if not tool:
            return {
                "allowed": False,
                "message": "Tôi không hỗ trợ hành động này. Vui lòng thử hành động khác."
            }

        required_perm = self.tool_permissions.get(tool)
        if not required_perm:
            # No permission required
            return {"allowed": True, "tool": tool, "params": {}}

        # Check if user has the required permission
        for p in permissions:
            key = f"{p.get('resource')}.{p.get('action')}"
            if key == required_perm:
                return {"allowed": True, "tool": tool, "params": {}}

        return {
            "allowed": False,
            "message": "Bạn không có quyền thực hiện hành động này."
        }

    def _find_tool_for_action(self, action: str) -> Optional[str]:
        """Find tool name for an action type."""
        # Direct match
        if action in self.tool_permissions:
            return action

        # Common action -> tool mappings
        action_to_tool = {
            "view_bills": "get_bills",
            "view_users": "get_users",
            "view_user_detail": "get_user_detail",
            "view_user_overview": "get_user_overview",
            "view_users_by_roles": "get_users_by_roles",
            "view_user_roles": "get_user_roles",
            "create_privileged_user": "create_privileged_user",
            "create_resident_user": "create_resident_user",
            "update_user_admin": "update_user_admin",
            "deactivate_user": "deactivate_user",
            "view_roles": "get_roles",
            "view_role_permissions": "get_role_permissions",
            "create_role": "create_role",
            "assign_user_role": "assign_user_role",
            "remove_user_role": "remove_user_role",
            "add_role_permission": "add_role_permission",
            "remove_role_permission": "remove_role_permission",
            "view_permissions_catalog": "get_permissions_catalog",
            "create_permission": "create_permission",
            "view_bill_detail": "get_bill_detail",
            "preview_utility_bill": "get_utility_preview",
            "create_bill": "create_bill",
            "notify_bill": "notify_bill_residents",
            "check_package": "get_packages",
            "view_package_detail": "get_package_detail",
            "delegate_pickup": "delegate_pickup",
            "delegate_pickup_by_id": "delegate_pickup_by_id",
            "revoke_delegation": "revoke_pickup_delegation",
            "lookup_delivery_code": "lookup_delivery_code",
            "lookup_parcel_resident": "lookup_parcel_resident",
            "generate_pickup_token": "generate_pickup_token",
            "view_bookings": "get_my_bookings",
            "view_bookings_queue": "get_bookings_queue",
            "approve_booking": "approve_booking",
            "reject_booking": "reject_booking",
            "view_incidents": "get_my_incidents",
            "report_incident": "create_incident",
            "view_ticket_queue": "get_tickets_queue",
            "update_ticket_status": "update_ticket_status",
            "update_ticket_severity": "update_ticket_severity",
            "assign_ticket": "assign_ticket",
            "approve_ticket": "approve_ticket",
            "reject_ticket": "reject_ticket",
            "complete_ticket": "complete_ticket",
            "book_amenity": "get_amenities",
            "view_amenities": "get_amenities",
            "view_notifications": "get_notifications",
            "view_payment_history": "get_payment_history",
            "record_manual_payment": "record_manual_payment",
            "view_announcements": "get_announcements",
            "view_announcement_detail": "get_announcement_detail",
            "create_announcement": "create_announcement",
            "view_requests": "get_my_requests",
            "view_requests_queue": "get_resident_requests_queue",
            "create_resident_request": "create_resident_request",
            "update_resident_request": "update_resident_request",
            "delete_resident_request": "delete_resident_request",
            "preverify_resident_request": "preverify_resident_request",
            "approve_resident_request": "approve_resident_request",
            "reject_resident_request": "reject_resident_request",
            "view_request_audit_logs": "get_resident_request_audit_logs",
            "view_resident_registries": "get_resident_registries",
            "view_resident_registry_detail": "get_resident_registry_detail",
            "create_resident_registry": "create_resident_registry",
            "delete_resident_registry": "delete_resident_registry",
            "bulk_update_resident_registry_status": "bulk_update_resident_registry_status",
            "view_building_overview": "get_building_overview",
            "view_blocks": "get_blocks",
            "view_block_floors": "get_block_floors",
            "view_units": "get_units",
            "view_unit_detail": "get_unit_detail",
            "create_unit": "create_unit",
            "update_unit_status": "update_unit_status",
            "view_resident_units": "get_resident_units",
            "assign_resident_to_unit": "assign_resident_to_unit",
            "view_access_cards": "get_access_cards",
            "view_access_card_detail": "get_access_card_detail",
            "create_access_card": "create_access_card",
            "update_access_card_status": "update_access_card_status",
            "delete_access_card": "delete_access_card",
            "view_community_events": "get_community_events",
            "view_community_event_detail": "get_community_event_detail",
            "create_community_event": "create_community_event",
            "register_community_event": "register_community_event",
            "view_surveys": "get_surveys",
            "register_visitor": "register_visitor",
        }
        return action_to_tool.get(action)

    async def format_tool_result(
        self,
        action: str,
        tool_name: str,
        result: Any,
    ) -> str:
        """Use LLM to format tool result as markdown.

        Args:
            action: Original action type
            tool_name: Tool that was executed
            result: Tool execution result

        Returns:
            Formatted markdown string in Vietnamese
        """
        if not self.openai_client:
            return self._simple_format_result(tool_name, result)

        prompt_template = self.prompts.get("result_formatter", _DEFAULT_RESULT_FORMATTER_PROMPT)
        result_str = json.dumps(result, ensure_ascii=False, indent=2)
        prompt = prompt_template.format(action=action, tool_name=tool_name, result=result_str)

        try:
            response = await self.openai_client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
            )
            return response.choices[0].message.content

        except Exception as e:
            logger.error("llm_format_failed", tool=tool_name, error=str(e))
            return self._simple_format_result(tool_name, result)

    def _simple_format_result(self, tool_name: str, result: Any) -> str:
        """Simple fallback formatter."""
        if isinstance(result, dict):
            if "error" in result:
                return f"❌ **Lỗi**: {result['error']}"
            if "data" in result:
                data = result["data"]
                if isinstance(data, list):
                    return f"## Kết quả\n\nTìm thấy **{len(data)}** mục."
            return f"```json\n{json.dumps(result, ensure_ascii=False, indent=2)}\n```"

        if isinstance(result, list):
            return f"## Kết quả\n\nTìm thấy **{len(result)}** mục."

        return str(result)

    async def generate_actions(
        self,
        last_tool: Optional[str] = None,
        permissions: Optional[List[Dict[str, str]]] = None,
        last_message: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Generate 3 contextual action suggestions using LLM.

        Args:
            last_tool: Last tool that was called
            permissions: User's permissions
            last_message: Last assistant message (for context)

        Returns:
            List of action dicts: [{"tool": str, "params": dict, "allowed": bool}]
        """
        if not self.openai_client:
            return self._fallback_actions()

        permissions = self.permission_mapper.normalize_permissions(permissions)

        # Build permission string
        perm_str = "No permissions"
        if permissions:
            perm_list = []
            for p in permissions:
                if p.get("resource") == "*":
                    perm_list.append("ADMIN")
                else:
                    perm_list.append(f"{p.get('resource')}.{p.get('action')}")
            perm_str = ", ".join(perm_list)

        # Get prompt template
        prompt_template = self.prompts.get("action_suggester", _DEFAULT_ACTION_SUGGESTER_PROMPT)
        prompt = prompt_template.format(
            last_tool=last_tool or "None",
            last_message=last_message or "None",
            permissions=perm_str,
        )

        try:
            response = await self.openai_client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.7,  # Higher temp for variety
            )

            result = json.loads(response.choices[0].message.content)
            actions = result.get("actions", [])
            logger.debug("llm_actions_generated", count=len(actions))
            return actions

        except Exception as e:
            logger.error("llm_action_generate_failed", error=str(e))
            return self._fallback_actions()

    def _fallback_actions(self) -> List[Dict[str, Any]]:
        """Default fallback actions."""
        return [
            {"tool": "get_bills", "params": {}, "allowed": True},
            {"tool": "get_packages", "params": {}, "allowed": True},
            {"tool": "create_incident", "params": {}, "allowed": True},
        ]


# Default prompts (used if not in prompts.yaml)
_DEFAULT_ACTION_ROUTER_PROMPT = """You are an action router for a Vietnamese resident services app.

Given an action and user permissions, decide:
1. Is this action allowed based on permissions?
2. If yes, which tool should be called?

User action: {action}
User permissions: {permissions}

Available tools:
{tools}

Respond in JSON: {{"allowed": true/false, "tool": "tool_name", "params": {{}}, "message": "friendly Vietnamese message if not allowed"}}

Examples:
- Action "view_bills" + permission "Bills.Read" -> {{"allowed": true, "tool": "get_bills", "params": {{}}}}
- Action "view_bills" + no Bills.Read -> {{"allowed": false, "message": "Bạn không có quyền xem hóa đơn."}}"""

_DEFAULT_RESULT_FORMATTER_PROMPT = """Format the following tool result as friendly Vietnamese markdown.

Action: {action}
Tool: {tool_name}
Result: {result}

Requirements:
- Write in Vietnamese, friendly tone
- Use markdown formatting (headers, tables, lists)
- If result is a list, show as formatted table
- Keep it concise but informative
- Do not include raw JSON"""

_DEFAULT_ACTION_SUGGESTER_PROMPT = """You are a smart action suggester for a Vietnamese resident services app.

Based on the conversation context, suggest 3 relevant next actions for the user.

## Context
- Last tool used: {last_tool}
- Last message: {last_message}
- User permissions: {permissions}

## Available tools
- get_bills: View utility bills
- get_bill_detail: View bill details
- get_utility_preview: Preview utility charges
- create_bill: Create a bill
- get_payment_history: View payment history
- record_manual_payment: Record a manual payment
- notify_bill_residents: Notify residents about a bill
- get_packages: Check packages
- get_package_detail: View package details
- delegate_pickup: Delegate package pickup
- delegate_pickup_by_id: Delegate package pickup by user ID
- revoke_pickup_delegation: Cancel pickup delegation
- lookup_delivery_code: Lookup resident by delivery code
- lookup_parcel_resident: Lookup resident in unit
- generate_pickup_token: Generate parcel pickup token
- get_amenities: View available facilities
- get_amenity_detail: View facility details
- get_amenity_categories: View facility categories
- get_my_bookings: View user's bookings
- book_amenity: Book a facility
- cancel_booking: Cancel a booking
- create_incident: Report an issue
- get_my_incidents: View reported issues
- get_incident_detail: View issue details
- get_tickets_queue: View operational ticket queue
- update_ticket_status: Update ticket status
- update_ticket_severity: Update ticket severity
- assign_ticket: Assign a ticket
- approve_ticket: Approve a ticket
- reject_ticket: Reject a ticket
- complete_ticket: Complete a ticket
- get_ticket_comments: View issue comments
- get_ticket_categories: View issue categories
- get_notifications: View notifications
- get_unread_notification_count: View unread notification count
- get_announcements: View building announcements
- get_announcement_detail: View announcement details
- create_announcement: Create a building announcement
- get_surveys: View surveys
- get_my_requests: View resident requests
- get_resident_requests_queue: View resident request queue
- create_resident_request: Create a resident request
- update_resident_request: Update a resident request
- delete_resident_request: Delete a resident request
- preverify_resident_request: Pre-verify a resident request
- approve_resident_request: Approve a resident request
- reject_resident_request: Reject a resident request
- get_resident_request_audit_logs: View resident request audit logs
- get_request_types: View request types
- register_visitor: Register a visitor
- get_profile: View profile

Respond in JSON format:
{{"actions": [
  {{"tool": "tool_name", "params": {{}}, "allowed": true}},
  ...
]}}

Rules:
- Suggest exactly 3 relevant tools based on conversation context
- Set "allowed": true (permissions already filtered)
- Order by relevance (most relevant first)"""
