"""MCP layer - Model Context Protocol server.

Provides JSON-RPC 2.0 interface for external tool integration.
"""

from src.mcp.errors import (
    ANALYSIS_FAILED,
    DOCUMENT_NOT_FOUND,
    INTERNAL_ERROR,
    INVALID_PARAMS,
    INVALID_REQUEST,
    METHOD_NOT_FOUND,
    PARSE_ERROR,
    JSONRPCError,
    make_error,
)
from src.mcp.methods import MCP_METHODS
from src.mcp.schemas import (
    AnalyzeDocumentParams,
    AnalyzeDocumentResult,
    AskQuestionParams,
    AskQuestionResult,
    CompareParams,
    CompareResult,
    JSONRPCRequest,
    JSONRPCResponse,
    ListDocumentsParams,
    ListDocumentsResult,
)
from src.mcp.server import router as mcp_router

__all__ = [
    # Router
    "mcp_router",
    # Methods
    "MCP_METHODS",
    # Errors
    "JSONRPCError",
    "make_error",
    "PARSE_ERROR",
    "INVALID_REQUEST",
    "METHOD_NOT_FOUND",
    "INVALID_PARAMS",
    "INTERNAL_ERROR",
    "DOCUMENT_NOT_FOUND",
    "ANALYSIS_FAILED",
    # Schemas
    "JSONRPCRequest",
    "JSONRPCResponse",
    "ListDocumentsParams",
    "ListDocumentsResult",
    "AnalyzeDocumentParams",
    "AnalyzeDocumentResult",
    "AskQuestionParams",
    "AskQuestionResult",
    "CompareParams",
    "CompareResult",
]
