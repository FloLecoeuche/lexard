"""JSON-RPC 2.0 request/response schemas for MCP server."""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator


# =============================================================================
# JSON-RPC Base Schemas
# =============================================================================


class JSONRPCRequest(BaseModel):
    """JSON-RPC 2.0 request format."""

    jsonrpc: Literal["2.0"] = Field(..., description="JSON-RPC version")
    method: str = Field(..., description="Method name to invoke")
    params: Optional[Dict[str, Any]] = Field(
        default=None, description="Method parameters"
    )
    id: Optional[Union[str, int]] = Field(
        default=None, description="Request ID (null for notifications)"
    )

    @field_validator("jsonrpc")
    @classmethod
    def validate_jsonrpc(cls, v: str) -> str:
        if v != "2.0":
            raise ValueError("jsonrpc must be '2.0'")
        return v


class JSONRPCErrorDetail(BaseModel):
    """JSON-RPC 2.0 error detail."""

    code: int = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    data: Optional[Any] = Field(default=None, description="Additional error data")


class JSONRPCResponse(BaseModel):
    """JSON-RPC 2.0 response format."""

    jsonrpc: Literal["2.0"] = "2.0"
    result: Optional[Any] = Field(default=None, description="Success result")
    error: Optional[JSONRPCErrorDetail] = Field(default=None, description="Error detail")
    id: Optional[Union[str, int]] = Field(
        default=None, description="Request ID (matches request)"
    )


# =============================================================================
# MCP Method Parameter Schemas
# =============================================================================


class ListDocumentsParams(BaseModel):
    """Parameters for list_documents method."""

    # No parameters required
    pass


class AnalyzeDocumentParams(BaseModel):
    """Parameters for analyze_document method."""

    document_id: str = Field(..., description="Document ID to analyze")
    analysis_type: Literal["summary", "risks", "metadata"] = Field(
        ..., description="Type of analysis to perform"
    )


class AskQuestionParams(BaseModel):
    """Parameters for ask_question method."""

    document_id: str = Field(..., description="Document ID to query")
    question: str = Field(..., description="Question to answer")


class CompareParams(BaseModel):
    """Parameters for compare method."""

    doc_a: str = Field(..., description="First document ID")
    doc_b: str = Field(..., description="Second document ID")


# =============================================================================
# MCP Method Result Schemas
# =============================================================================


class DocumentInfo(BaseModel):
    """Document information for MCP responses."""

    id: str
    title: str
    uploaded_at: datetime
    page_count: Optional[int] = None
    version: int = 1


class ListDocumentsResult(BaseModel):
    """Result for list_documents method."""

    documents: List[DocumentInfo]


class AnalyzeDocumentResult(BaseModel):
    """Result for analyze_document method."""

    analysis: str
    risk_level: Optional[Literal["low", "medium", "high"]] = None
    citations: List[str] = Field(default_factory=list)


class AskQuestionResult(BaseModel):
    """Result for ask_question method."""

    answer: str
    citation_chunks: List[str]
    confidence: Literal["high", "medium", "low"]


class DifferenceInfo(BaseModel):
    """Difference information for compare result."""

    section: str
    doc_a_content: str
    doc_b_content: str
    similarity_score: float


class CompareResult(BaseModel):
    """Result for compare method."""

    differences: List[DifferenceInfo]
