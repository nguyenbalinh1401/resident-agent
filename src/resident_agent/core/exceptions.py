"""Custom exceptions for Resident Agent."""


class PulseAPIError(Exception):
    """Exception raised for Pulse Backend API errors."""

    def __init__(self, message: str, status_code: int = None, details: dict = None):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class AuthenticationError(Exception):
    """Exception raised for authentication failures."""

    def __init__(self, message: str = "Authentication failed"):
        self.message = message
        super().__init__(self.message)


class CuxError(Exception):
    """Exception raised for CUX orchestrator errors."""

    def __init__(self, message: str, details: dict = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class ToolExecutionError(Exception):
    """Exception raised when tool execution fails."""

    def __init__(self, tool_name: str, message: str, params: dict = None):
        self.tool_name = tool_name
        self.message = message
        self.params = params or {}
        super().__init__(f"Tool '{tool_name}' failed: {message}")
