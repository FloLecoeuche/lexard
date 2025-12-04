"""Output validation guardrails for RAG responses.

Validates responses for grounding, citations, and potential hallucinations.
"""

import logging
import re
from dataclasses import dataclass
from enum import Enum

from src.rag.pipeline import Confidence, RAGResponse

logger = logging.getLogger(__name__)


class ValidationResult(str, Enum):
    """Result of guardrail validation."""

    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"


@dataclass
class GuardrailsResult:
    """Result of guardrail validation.

    Attributes:
        status: Overall validation status (pass/fail/warning)
        issues: List of identified issues
        sanitized_response: Modified response if sanitization was needed
    """

    status: ValidationResult
    issues: list[str]
    sanitized_response: str | None


class ResponseValidator:
    """Validator for RAG responses.

    Checks responses for:
    - Proper content (not empty or too short)
    - Citation markers when relevant content exists
    - Basic hallucination patterns (uncertain language without citations)

    Attributes:
        require_citations: Whether to require citation markers in responses
        min_response_length: Minimum response length in characters
    """

    # Phrases that indicate uncertain or potentially hallucinated content
    SUSPICIOUS_PHRASES = [
        "i believe",
        "i think",
        "probably",
        "might be",
        "it's possible that",
        "generally speaking",
        "typically",
        "usually",
        "in most cases",
        "as far as i know",
    ]

    # Citation pattern: [1], [2], etc.
    CITATION_PATTERN = re.compile(r"\[\d+\]")

    def __init__(
        self,
        require_citations: bool = True,
        min_response_length: int = 10,
    ):
        """Initialize ResponseValidator.

        Args:
            require_citations: Whether to require citation markers
            min_response_length: Minimum acceptable response length
        """
        self.require_citations = require_citations
        self.min_response_length = min_response_length

    def validate(self, response: RAGResponse) -> GuardrailsResult:
        """Validate RAG response for safety and grounding.

        Performs three checks:
        1. Response has sufficient content
        2. Citations are present (if required and relevant content exists)
        3. Response doesn't use uncertain language without citations

        Args:
            response: RAG response to validate

        Returns:
            GuardrailsResult with status, issues, and optional sanitized response
        """
        issues: list[str] = []

        # Check 1: Response has content
        content_issue = self._validate_content(response)
        if content_issue:
            issues.append(content_issue)

        # Check 2: Citations present (only when we have relevant content)
        if self.require_citations and response.has_relevant_content:
            citation_issue = self._validate_citations(response)
            if citation_issue:
                issues.append(citation_issue)

        # Check 3: Basic hallucination check
        if response.has_relevant_content:
            hallucination_issue = self._check_hallucination(response)
            if hallucination_issue:
                issues.append(hallucination_issue)

        # Determine status
        status = self._determine_status(issues)

        # Get sanitized response if needed
        sanitized = self._sanitize_if_needed(response, issues, status)

        logger.info(
            "Validation complete",
            extra={
                "status": status.value,
                "issue_count": len(issues),
                "sanitized": sanitized is not None,
            },
        )

        return GuardrailsResult(
            status=status,
            issues=issues,
            sanitized_response=sanitized,
        )

    def _validate_content(self, response: RAGResponse) -> str | None:
        """Check if response has sufficient content.

        Args:
            response: RAG response to check

        Returns:
            Issue description if validation fails, None otherwise
        """
        if not response.answer or not response.answer.strip():
            return "Response is empty"

        if len(response.answer.strip()) < self.min_response_length:
            return f"Response is too short (minimum {self.min_response_length} characters)"

        return None

    def _validate_citations(self, response: RAGResponse) -> str | None:
        """Check if response contains citation markers.

        Args:
            response: RAG response to check

        Returns:
            Issue description if validation fails, None otherwise
        """
        if not self._has_citations(response.answer):
            return "Response lacks citation markers (expected [1], [2], etc.)"
        return None

    def _has_citations(self, text: str) -> bool:
        """Check if text contains citation markers like [1], [2].

        Args:
            text: Text to check for citations

        Returns:
            True if citation markers found, False otherwise
        """
        return bool(self.CITATION_PATTERN.search(text))

    def _check_hallucination(self, response: RAGResponse) -> str | None:
        """Perform basic hallucination detection.

        Checks for uncertain language that might indicate the model
        is guessing rather than grounding in the source documents.

        More sophisticated implementations would use NLI models.

        Args:
            response: RAG response to check

        Returns:
            Issue description if potential hallucination detected, None otherwise
        """
        answer_lower = response.answer.lower()

        for phrase in self.SUSPICIOUS_PHRASES:
            if phrase in answer_lower:
                # Check if there are citations nearby (within ~100 chars)
                # If citations present, uncertain language is less concerning
                if not response.citation_chunks:
                    return (
                        f"Possible hallucination: uses uncertain language "
                        f"'{phrase}' without supporting citations"
                    )

        return None

    def _determine_status(self, issues: list[str]) -> ValidationResult:
        """Determine overall validation status from issues.

        Args:
            issues: List of validation issues

        Returns:
            ValidationResult based on issue severity
        """
        if not issues:
            return ValidationResult.PASS

        # Hallucination issues are failures
        if any("hallucination" in issue.lower() for issue in issues):
            return ValidationResult.FAIL

        # Empty response is a failure
        if any("empty" in issue.lower() for issue in issues):
            return ValidationResult.FAIL

        # Other issues are warnings
        return ValidationResult.WARNING

    def _sanitize_if_needed(
        self,
        response: RAGResponse,
        issues: list[str],
        status: ValidationResult,
    ) -> str | None:
        """Return sanitized response if needed.

        For failed validations, returns a safe refusal response.

        Args:
            response: Original RAG response
            issues: List of validation issues
            status: Validation status

        Returns:
            Sanitized response string if needed, None otherwise
        """
        if status == ValidationResult.FAIL:
            return (
                "I cannot provide a reliable answer based on the available documents. "
                "Please rephrase your question or provide additional context."
            )
        return None


def get_refusal_response() -> RAGResponse:
    """Return standard refusal response for unsafe/invalid queries.

    Use this when a query should be refused entirely.

    Returns:
        RAGResponse with refusal message and low confidence
    """
    return RAGResponse(
        answer="I cannot answer based on the provided documents.",
        citation_chunks=[],
        confidence=Confidence.LOW,
        has_relevant_content=False,
    )
