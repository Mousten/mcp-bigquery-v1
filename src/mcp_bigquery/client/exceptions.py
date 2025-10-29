"""Exceptions for the MCP BigQuery client."""


class MCPClientError(Exception):
    """Base exception for MCP client errors."""
    pass


class AuthenticationError(MCPClientError):
    """Raised when authentication fails (401)."""
    pass


class AuthorizationError(MCPClientError):
    """Raised when user lacks required permissions (403)."""
    pass


class ValidationError(MCPClientError):
    """Raised when request validation fails (400)."""
    pass


class ServerError(MCPClientError):
    """Raised when server returns an error (500+)."""
    pass


class NetworkError(MCPClientError):
    """Raised when network request fails."""
    pass
