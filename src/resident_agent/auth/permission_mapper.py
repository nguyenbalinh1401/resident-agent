"""Permission to Tool Mapping.

Loads configuration from YAML and provides:
- Permission → Tool conversion
- Permission → Actions lookup
- Tool → Permission lookup
- Tool permission validation
"""

from typing import List, Dict, Set, Optional
from pathlib import Path
import yaml
import structlog

logger = structlog.get_logger()


class PermissionMapper:
    """Direct mapping from API permissions to tools.

    Loads configuration from YAML and provides:
    - Permission → Tool conversion
    - Permission → Actions lookup
    """

    def __init__(self, config_path: str = "configs/permissions.yaml"):
        self.config_path = Path(config_path)
        self._config = self._load_config()

    def _load_config(self) -> dict:
        """Load configuration from YAML file."""
        try:
            with open(self.config_path) as f:
                return yaml.safe_load(f) or {}
        except FileNotFoundError:
            logger.warning("permission_config_not_found", path=str(self.config_path))
            return {}

    def reload(self) -> None:
        """Reload configuration from file."""
        self._config = self._load_config()
        logger.info("permission_mapper_reloaded")

    def permissions_to_tools(
        self,
        permissions: List[Dict[str, str]],
    ) -> List[str]:
        """Convert API permissions to tool names.

        Args:
            permissions: List of {"resource": str, "action": str} from API

        Returns:
            List of tool names the user can use, or ["*"] for admin access
        """
        if not permissions:
            return self._config.get("default_tools", ["get_profile"])

        tool_names: Set[str] = set(self._config.get("default_tools", ["get_profile"]))
        mapping = self._config.get("permission_to_tools", {})

        for p in permissions:
            # Check for admin permission (resource = "*")
            if p.get("resource") == "*":
                logger.debug("admin_permission_detected", permission=p)
                return "*"

            key = f"{p.get('resource')}.{p.get('action')}"

            # Check explicit mapping
            if key in mapping:
                tool_names.update(mapping[key])
            else:
                # Fallback: dynamic mapping using naming convention
                tools = self._dynamic_map(p.get("resource", ""), p.get("action", ""))
                tool_names.update(tools)

        logger.debug(
            "permissions_mapped_to_tools",
            input_permissions=permissions,
            output_tools=list(tool_names),
        )
        return list(tool_names)

    def _dynamic_map(self, resource: str, action: str) -> List[str]:
        """Dynamic fallback mapping using naming convention.

        Args:
            resource: Resource name (e.g., "Bills", "Tickets")
            action: Action name (e.g., "Read", "Write")

        Returns:
            List of tool names based on naming convention
        """
        resource_lower = resource.lower()

        if action == "Read":
            return [f"get_{resource_lower}", f"get_{resource_lower}_detail"]
        elif action == "Write":
            return [f"create_{resource_lower}", f"update_{resource_lower}"]
        return []

    def get_filtered_tools(self, permissions: List[Dict[str, str]]) -> List[dict]:
        """Get filtered tool definitions for LLM.

        Args:
            permissions: List of {"resource": str, "action": str} from API

        Returns:
            Filtered list of tool definitions
        """
        from resident_agent.cux.tools import TOOLS

        tool_names = self.permissions_to_tools(permissions)

        if tool_names == "*":
            return TOOLS

        return [t for t in TOOLS if t["function"]["name"] in tool_names]

    def get_role_permission_preset(self, role: Optional[str]) -> List[Dict[str, str]]:
        """Get local permission preset for a role."""
        if not role:
            return []

        presets = self._config.get("role_permission_presets", {})
        return presets.get(role, presets.get(role.title(), [])) or []

    def constrain_permissions_to_role(
        self,
        role: Optional[str],
        permissions: List[Dict[str, str]],
    ) -> List[Dict[str, str]]:
        """Constrain backend permissions to a local role preset.

        This keeps agent capabilities aligned with the signed-in role even if
        the upstream permissions endpoint returns a broader permission catalog.
        """
        preset = self.get_role_permission_preset(role)
        if not preset:
            return permissions

        if any(p.get("resource") == "*" for p in preset):
            return preset

        allowed = {
            f"{p.get('resource')}.{p.get('action')}"
            for p in preset
        }

        if not permissions:
            return preset

        constrained = [
            p for p in permissions
            if f"{p.get('resource')}.{p.get('action')}" in allowed
        ]

        # Merge preset-only synthetic permissions so the agent can expose
        # role-scoped operational tools even when the upstream API only
        # returns a coarse permission catalog.
        existing = {
            f"{p.get('resource')}.{p.get('action')}"
            for p in constrained
        }
        merged = constrained + [
            p for p in preset
            if f"{p.get('resource')}.{p.get('action')}" not in existing
        ]
        return merged or preset

    def get_tool_permission(self, tool_name: str) -> Optional[str]:
        """Get required permission for a tool.

        Args:
            tool_name: Name of the tool

        Returns:
            Required permission string (e.g., "Bills.Read") or None if no permission required
        """
        tool_permissions = self._config.get("tool_to_permission", {})
        return tool_permissions.get(tool_name)

    def check_tool_permission(
        self,
        tool_name: str,
        user_permissions: List[Dict[str, str]],
    ) -> bool:
        """Check if user has permission to use a tool.

        Args:
            tool_name: Name of the tool
            user_permissions: User's permissions from JWT (list of {"resource": str, "action": str})

        Returns:
            True if user can use the tool
        """
        required = self.get_tool_permission(tool_name)

        # No permission required for this tool
        if not required:
            return True

        if not user_permissions:
            return False

        # Check for admin permission (resource = "*")
        for p in user_permissions:
            if p.get("resource") == "*":
                logger.debug("admin_permission_granted", tool=tool_name)
                return True

        # Check specific permission
        for p in user_permissions:
            key = f"{p.get('resource')}.{p.get('action')}"
            if key == required:
                return True

        logger.debug(
            "tool_permission_denied",
            tool=tool_name,
            required_permission=required,
        )
        return False
