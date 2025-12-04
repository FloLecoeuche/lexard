"""Base response schemas for Lexard API."""

from typing import Dict, Literal, Optional

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    """Error detail structure."""

    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Human-readable error message")
    trace_id: str = Field(..., description="Request trace ID for debugging")


class ErrorResponse(BaseModel):
    """Standard error response format."""

    error: ErrorDetail


class ServiceStatus(BaseModel):
    """Status of an individual service."""

    status: Literal["connected", "disconnected"]


class HealthResponse(BaseModel):
    """Health check response."""

    status: Literal["healthy", "degraded", "unhealthy"]
    version: str
    services: Dict[str, Literal["connected", "disconnected"]]


class SuccessResponse(BaseModel):
    """Generic success response."""

    success: bool = True
    message: Optional[str] = None
