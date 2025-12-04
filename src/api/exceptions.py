"""Custom exceptions for Lexard API."""

from typing import Optional


class LexardError(Exception):
    """Base exception for all Lexard errors."""

    code: str = "INTERNAL_ERROR"
    status_code: int = 500
    message: str = "An internal error occurred"

    def __init__(self, message: Optional[str] = None):
        self.message = message or self.__class__.message
        super().__init__(self.message)


class DocumentNotFoundError(LexardError):
    """Raised when a document is not found."""

    code = "DOCUMENT_NOT_FOUND"
    status_code = 404
    message = "Document not found"


class DocumentParseError(LexardError):
    """Raised when document parsing fails."""

    code = "DOCUMENT_PARSE_ERROR"
    status_code = 422
    message = "Failed to parse document"


class LLMUnavailableError(LexardError):
    """Raised when the LLM service is unavailable."""

    code = "LLM_UNAVAILABLE"
    status_code = 503
    message = "LLM service is unavailable"


class ValidationError(LexardError):
    """Raised when request validation fails."""

    code = "VALIDATION_ERROR"
    status_code = 400
    message = "Request validation failed"


class ServiceUnavailableError(LexardError):
    """Raised when an external service is unavailable."""

    code = "SERVICE_UNAVAILABLE"
    status_code = 503
    message = "Service unavailable"
