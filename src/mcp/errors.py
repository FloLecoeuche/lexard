"""JSON-RPC 2.0 error definitions for MCP server.

Standard JSON-RPC error codes:
- -32700: Parse error
- -32600: Invalid request
- -32601: Method not found
- -32602: Invalid params
- -32603: Internal error

Custom error codes (-32000 to -32099):
- -32000: Document not found
- -32001: Analysis failed
"""

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class JSONRPCError:
    """JSON-RPC 2.0 error object."""

    code: int
    message: str
    data: Optional[Any] = None

    def to_dict(self) -> dict:
        """Convert to JSON-RPC error format."""
        result = {"code": self.code, "message": self.message}
        if self.data is not None:
            result["data"] = self.data
        return result


# Standard JSON-RPC errors
PARSE_ERROR = JSONRPCError(code=-32700, message="Parse error")
INVALID_REQUEST = JSONRPCError(code=-32600, message="Invalid request")
METHOD_NOT_FOUND = JSONRPCError(code=-32601, message="Method not found")
INVALID_PARAMS = JSONRPCError(code=-32602, message="Invalid params")
INTERNAL_ERROR = JSONRPCError(code=-32603, message="Internal error")

# Custom application errors
DOCUMENT_NOT_FOUND = JSONRPCError(code=-32000, message="Document not found")
ANALYSIS_FAILED = JSONRPCError(code=-32001, message="Analysis failed")


def make_error(base_error: JSONRPCError, data: Any = None) -> JSONRPCError:
    """Create a new error with optional data.

    Args:
        base_error: Base error to copy
        data: Additional error data

    Returns:
        New JSONRPCError with data
    """
    return JSONRPCError(code=base_error.code, message=base_error.message, data=data)
