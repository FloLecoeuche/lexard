"""Request and response schemas for Lexard API."""

from datetime import datetime
from typing import Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# =============================================================================
# Error Schemas
# =============================================================================


class ErrorDetail(BaseModel):
    """Error detail structure."""

    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Human-readable error message")
    trace_id: str = Field(..., description="Request trace ID for debugging")


class ErrorResponse(BaseModel):
    """Standard error response format."""

    error: ErrorDetail


# =============================================================================
# Health Schemas
# =============================================================================


class ServiceStatus(BaseModel):
    """Status of an individual service."""

    status: Literal["connected", "disconnected"]


class HealthResponse(BaseModel):
    """Health check response."""

    status: Literal["healthy", "degraded", "unhealthy"]
    version: str
    services: Dict[str, Literal["connected", "disconnected"]]


# =============================================================================
# Document Schemas
# =============================================================================


class DocumentUploadResponse(BaseModel):
    """Response after successful document upload."""

    document_id: str = Field(..., description="Unique document identifier")
    title: str = Field(..., description="Document title")
    page_count: Optional[int] = Field(None, description="Number of pages")
    chunk_count: Optional[int] = Field(None, description="Number of chunks created")
    version: int = Field(..., description="Document version number")
    uploaded_at: datetime = Field(..., description="Upload timestamp")

    model_config = {
        "json_schema_extra": {
            "example": {
                "document_id": "550e8400-e29b-41d4-a716-446655440000",
                "title": "Contract Agreement",
                "page_count": 10,
                "chunk_count": 45,
                "version": 1,
                "uploaded_at": "2025-01-15T10:30:00Z",
            }
        }
    }


class DocumentMetadata(BaseModel):
    """Document metadata for list responses."""

    id: str = Field(..., description="Document ID")
    title: str = Field(..., description="Document title")
    filename: str = Field(..., description="Original filename")
    page_count: Optional[int] = Field(None, description="Number of pages")
    chunk_count: Optional[int] = Field(None, description="Number of chunks")
    version: int = Field(..., description="Version number")
    uploaded_at: datetime = Field(..., description="Upload timestamp")
    status: str = Field(..., description="Processing status")

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "title": "Contract Agreement",
                "filename": "contract.pdf",
                "page_count": 10,
                "chunk_count": 45,
                "version": 1,
                "uploaded_at": "2025-01-15T10:30:00Z",
                "status": "processed",
            }
        }
    }


class DocumentDetailResponse(BaseModel):
    """Detailed document information."""

    id: str = Field(..., description="Document ID")
    title: str = Field(..., description="Document title")
    filename: str = Field(..., description="Original filename")
    file_hash: str = Field(..., description="SHA256 hash of file contents")
    page_count: Optional[int] = Field(None, description="Number of pages")
    chunk_count: Optional[int] = Field(None, description="Number of chunks")
    version: int = Field(..., description="Version number")
    parent_document_id: Optional[str] = Field(
        None, description="Parent document ID for versioning"
    )
    uploaded_at: datetime = Field(..., description="Upload timestamp")
    status: str = Field(..., description="Processing status")


class DocumentListResponse(BaseModel):
    """Response for document listing."""

    documents: List[DocumentMetadata] = Field(..., description="List of documents")
    total: int = Field(..., description="Total document count")


class DeleteResponse(BaseModel):
    """Response for successful deletion."""

    success: bool = Field(True, description="Operation success status")
    message: str = Field(..., description="Success message")

    model_config = {
        "json_schema_extra": {
            "example": {"success": True, "message": "Document deleted successfully"}
        }
    }


# =============================================================================
# Query Schemas
# =============================================================================


class QueryRequest(BaseModel):
    """Request for RAG query."""

    document_id: str = Field(..., description="Document ID to query against")
    question: str = Field(
        ..., min_length=1, max_length=1000, description="Question to answer"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "document_id": "550e8400-e29b-41d4-a716-446655440000",
                "question": "What are the termination conditions?",
            }
        }
    }


class CitationChunk(BaseModel):
    """Citation reference with source information."""

    content: str = Field(..., description="Text content of the cited chunk")
    page: int = Field(..., description="Page number in source document")
    chunk_index: int = Field(..., description="Index of chunk within document")
    score: float = Field(..., description="Relevance score from retrieval")


class QueryResponse(BaseModel):
    """Response for RAG query."""

    answer: str = Field(..., description="Generated answer")
    citation_chunks: List[CitationChunk] = Field(
        ..., description="Source citations for the answer"
    )
    confidence: Literal["high", "medium", "low"] = Field(
        ..., description="Confidence level based on retrieval quality"
    )
    language: Literal["en", "fr"] = Field(
        "en", description="Detected document language used for response"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "answer": "The contract can be terminated with 30 days written notice by either party.",
                "citation_chunks": [
                    {
                        "content": "Either party may terminate this agreement with 30 days written notice...",
                        "page": 5,
                        "chunk_index": 12,
                        "score": 0.92,
                    }
                ],
                "confidence": "high",
                "language": "en",
            }
        }
    }


# =============================================================================
# Summarization Schemas
# =============================================================================


class SummarizeRequest(BaseModel):
    """Request for document summarization."""

    document_id: str = Field(..., description="Document ID to summarize")
    style: Literal["executive", "detailed"] = Field(
        "executive", description="Summary style"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "document_id": "550e8400-e29b-41d4-a716-446655440000",
                "style": "executive",
            }
        }
    }


class SummarizeResponse(BaseModel):
    """Response for document summarization."""

    summary: str = Field(..., description="Generated summary text")
    key_points: List[str] = Field(..., description="Key points extracted")
    word_count: int = Field(..., description="Word count of the summary")
    language: Literal["en", "fr"] = Field(
        "en", description="Detected document language used for response"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "summary": "This is a service agreement between Company A and Company B...",
                "key_points": [
                    "3-year contract term",
                    "Monthly payment of $10,000",
                    "30-day termination notice required",
                ],
                "word_count": 150,
                "language": "en",
            }
        }
    }


# =============================================================================
# Risk Analysis Schemas
# =============================================================================


class RiskRequest(BaseModel):
    """Request for risk analysis."""

    document_id: str = Field(..., description="Document ID to analyze")

    model_config = {
        "json_schema_extra": {
            "example": {"document_id": "550e8400-e29b-41d4-a716-446655440000"}
        }
    }


class RiskItem(BaseModel):
    """A single identified risk."""

    category: Literal[
        "legal_liability",
        "financial_penalty",
        "data_protection",
        "termination",
        "ambiguous_language",
        "other",
    ] = Field(..., description="Risk category")
    severity: Literal["low", "medium", "high"] = Field(
        ..., description="Risk severity level"
    )
    description: str = Field(..., description="Description of the risk")
    clause_excerpt: str = Field(..., description="Relevant clause text")
    page: int = Field(..., description="Page number where risk was found")
    recommendation: Optional[str] = Field(None, description="Suggested mitigation")


class RiskResponse(BaseModel):
    """Response for risk analysis."""

    risks: List[RiskItem] = Field(..., description="List of identified risks")
    overall_risk_level: Literal["low", "medium", "high"] = Field(
        ..., description="Aggregated risk level"
    )
    language: Literal["en", "fr"] = Field(
        "en", description="Detected document language used for analysis"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "risks": [
                    {
                        "category": "financial_penalty",
                        "severity": "high",
                        "description": "Unlimited liability clause with no cap",
                        "clause_excerpt": "The Service Provider shall be liable for all damages...",
                        "page": 5,
                        "recommendation": "Negotiate a liability cap",
                    }
                ],
                "overall_risk_level": "high",
                "language": "en",
            }
        }
    }


# =============================================================================
# Comparison Schemas
# =============================================================================


class CompareRequest(BaseModel):
    """Request for document comparison."""

    doc_a: str = Field(..., description="First document ID")
    doc_b: str = Field(..., description="Second document ID")

    model_config = {
        "json_schema_extra": {
            "example": {
                "doc_a": "550e8400-e29b-41d4-a716-446655440000",
                "doc_b": "660e8400-e29b-41d4-a716-446655440001",
            }
        }
    }


class DifferenceItem(BaseModel):
    """A difference between two document sections."""

    section: str = Field(..., description="Section identifier")
    doc_a_excerpt: str = Field(..., description="Text from document A")
    doc_b_excerpt: str = Field(..., description="Text from document B")
    change_type: Literal["added", "removed", "modified"] = Field(
        ..., description="Type of change"
    )
    similarity: float = Field(..., description="Similarity score between sections")


class CompareResponse(BaseModel):
    """Response for document comparison."""

    differences: List[DifferenceItem] = Field(..., description="List of differences")
    overall_similarity: float = Field(
        ..., description="Overall document similarity score"
    )
    language: Literal["en", "fr"] = Field(
        "en", description="Detected document language used for comparison"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "differences": [
                    {
                        "section": "Termination Clause",
                        "doc_a_excerpt": "30 days notice required...",
                        "doc_b_excerpt": "60 days notice required...",
                        "change_type": "modified",
                        "similarity": 0.75,
                    }
                ],
                "overall_similarity": 0.85,
                "language": "en",
            }
        }
    }


# =============================================================================
# Generic Success Response
# =============================================================================


class SuccessResponse(BaseModel):
    """Generic success response."""

    success: bool = True
    message: Optional[str] = None


# =============================================================================
# Guardrails Metrics Schema
# =============================================================================


# =============================================================================
# Async Operation Schemas
# =============================================================================


class AsyncOperationResponse(BaseModel):
    """Response for async operations with progress tracking."""

    operation_id: str = Field(..., description="Operation ID for progress tracking")
    status: Literal["processing", "complete", "failed"] = Field(
        "processing", description="Current operation status"
    )
    message: str = Field("", description="Human-readable status message")

    model_config = {
        "json_schema_extra": {
            "example": {
                "operation_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "processing",
                "message": "Query started. Subscribe to /operations/{operation_id}/progress for updates.",
            }
        }
    }


class GuardrailsMetricsResponse(BaseModel):
    """Response for guardrails metrics endpoint."""

    total_inputs: int = Field(..., description="Total inputs processed")
    total_outputs: int = Field(..., description="Total outputs processed")
    injection_blocks: int = Field(..., description="Inputs blocked due to injection")
    hallucination_blocks: int = Field(..., description="Outputs blocked due to hallucination")
    schema_failures: int = Field(..., description="Outputs blocked due to schema validation")
    pii_redactions: int = Field(..., description="Outputs with PII redacted")
    input_block_rate: float = Field(..., description="Percentage of inputs blocked")
    output_block_rate: float = Field(..., description="Percentage of outputs blocked")

    model_config = {
        "json_schema_extra": {
            "example": {
                "total_inputs": 100,
                "total_outputs": 95,
                "injection_blocks": 5,
                "hallucination_blocks": 2,
                "schema_failures": 1,
                "pii_redactions": 10,
                "input_block_rate": 5.0,
                "output_block_rate": 3.16,
            }
        }
    }
