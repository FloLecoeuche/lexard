"""Schema validation for RAG responses.

Validates response structures to ensure all required fields are present
and values are within acceptable ranges.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Valid confidence levels
VALID_CONFIDENCE_LEVELS = {"high", "medium", "low"}

# Valid risk levels
VALID_RISK_LEVELS = {"high", "medium", "low"}

# Valid risk categories
VALID_RISK_CATEGORIES = {
    "legal_liability",
    "financial_penalty",
    "data_protection",
    "termination",
    "ambiguous_language",
    "other",
}

# Valid change types for document comparison
VALID_CHANGE_TYPES = {"added", "removed", "modified"}


@dataclass
class SchemaValidationResult:
    """Result of schema validation.

    Attributes:
        is_valid: Whether the response passes schema validation
        errors: List of validation error messages
        warnings: List of validation warning messages
    """

    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        """Number of validation errors."""
        return len(self.errors)


class SchemaValidator:
    """Validates response schemas for different response types.

    Checks that:
    - Required fields are present
    - Values are within expected ranges
    - Citations are properly formatted
    - Confidence and risk levels are valid
    """

    def validate(self, response: dict[str, Any], response_type: str = "query") -> SchemaValidationResult:
        """Validate a response against its schema.

        Args:
            response: Response dictionary to validate
            response_type: Type of response ("query", "summarize", "risk", "compare")

        Returns:
            SchemaValidationResult with validation status
        """
        validators = {
            "query": self._validate_query_response,
            "summarize": self._validate_summarize_response,
            "risk": self._validate_risk_response,
            "compare": self._validate_compare_response,
        }

        validator = validators.get(response_type)
        if not validator:
            logger.warning(f"Unknown response type: {response_type}")
            return SchemaValidationResult(
                is_valid=False,
                errors=[f"Unknown response type: {response_type}"],
            )

        return validator(response)

    def _validate_query_response(self, response: dict[str, Any]) -> SchemaValidationResult:
        """Validate query/Q&A response schema.

        Required fields:
        - answer: non-empty string
        - citation_chunks: list of citation objects
        - confidence: one of high/medium/low
        """
        errors: list[str] = []
        warnings: list[str] = []

        # Check answer field
        if "answer" not in response:
            errors.append("Missing required field: answer")
        elif not isinstance(response["answer"], str):
            errors.append("Field 'answer' must be a string")
        elif not response["answer"].strip():
            errors.append("Field 'answer' cannot be empty")

        # Check confidence field
        if "confidence" not in response:
            errors.append("Missing required field: confidence")
        elif response["confidence"] not in VALID_CONFIDENCE_LEVELS:
            errors.append(
                f"Invalid confidence level: {response['confidence']}. "
                f"Must be one of: {VALID_CONFIDENCE_LEVELS}"
            )

        # Check citation_chunks field
        if "citation_chunks" not in response:
            errors.append("Missing required field: citation_chunks")
        elif not isinstance(response["citation_chunks"], list):
            errors.append("Field 'citation_chunks' must be a list")
        else:
            # Validate each citation
            for i, citation in enumerate(response["citation_chunks"]):
                citation_errors = self._validate_citation(citation, i)
                errors.extend(citation_errors)

            # Warning if no citations but high confidence
            if not response["citation_chunks"] and response.get("confidence") == "high":
                warnings.append("High confidence response with no citations")

        is_valid = len(errors) == 0

        if errors:
            logger.warning(
                "Query response validation failed",
                extra={"error_count": len(errors), "errors": errors},
            )

        return SchemaValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
        )

    def _validate_citation(self, citation: Any, index: int) -> list[str]:
        """Validate a single citation object.

        Required fields:
        - content: non-empty string
        - score: float between 0 and 1
        """
        errors: list[str] = []
        prefix = f"citation_chunks[{index}]"

        if not isinstance(citation, dict):
            return [f"{prefix}: must be an object"]

        # Check content
        if "content" not in citation:
            errors.append(f"{prefix}: missing 'content' field")
        elif not isinstance(citation["content"], str):
            errors.append(f"{prefix}: 'content' must be a string")
        elif not citation["content"].strip():
            errors.append(f"{prefix}: 'content' cannot be empty")

        # Check score
        if "score" in citation:
            score = citation["score"]
            if not isinstance(score, (int, float)):
                errors.append(f"{prefix}: 'score' must be a number")
            elif not 0.0 <= score <= 1.0:
                errors.append(f"{prefix}: 'score' must be between 0 and 1, got {score}")

        return errors

    def _validate_summarize_response(self, response: dict[str, Any]) -> SchemaValidationResult:
        """Validate summarize response schema.

        Required fields:
        - summary: non-empty string
        - key_points: list of strings
        - word_count: positive integer
        """
        errors: list[str] = []
        warnings: list[str] = []

        # Check summary field
        if "summary" not in response:
            errors.append("Missing required field: summary")
        elif not isinstance(response["summary"], str):
            errors.append("Field 'summary' must be a string")
        elif not response["summary"].strip():
            errors.append("Field 'summary' cannot be empty")

        # Check key_points field
        if "key_points" not in response:
            errors.append("Missing required field: key_points")
        elif not isinstance(response["key_points"], list):
            errors.append("Field 'key_points' must be a list")
        else:
            for i, point in enumerate(response["key_points"]):
                if not isinstance(point, str):
                    errors.append(f"key_points[{i}] must be a string")
                elif not point.strip():
                    warnings.append(f"key_points[{i}] is empty")

        # Check word_count field
        if "word_count" not in response:
            errors.append("Missing required field: word_count")
        elif not isinstance(response["word_count"], int):
            errors.append("Field 'word_count' must be an integer")
        elif response["word_count"] < 0:
            errors.append("Field 'word_count' cannot be negative")

        is_valid = len(errors) == 0
        return SchemaValidationResult(is_valid=is_valid, errors=errors, warnings=warnings)

    def _validate_risk_response(self, response: dict[str, Any]) -> SchemaValidationResult:
        """Validate risk analysis response schema.

        Required fields:
        - risks: list of risk items
        - overall_risk_level: one of high/medium/low
        """
        errors: list[str] = []
        warnings: list[str] = []

        # Check overall_risk_level
        if "overall_risk_level" not in response:
            errors.append("Missing required field: overall_risk_level")
        elif response["overall_risk_level"] not in VALID_RISK_LEVELS:
            errors.append(
                f"Invalid overall_risk_level: {response['overall_risk_level']}. "
                f"Must be one of: {VALID_RISK_LEVELS}"
            )

        # Check risks field
        if "risks" not in response:
            errors.append("Missing required field: risks")
        elif not isinstance(response["risks"], list):
            errors.append("Field 'risks' must be a list")
        else:
            for i, risk in enumerate(response["risks"]):
                risk_errors = self._validate_risk_item(risk, i)
                errors.extend(risk_errors)

        is_valid = len(errors) == 0
        return SchemaValidationResult(is_valid=is_valid, errors=errors, warnings=warnings)

    def _validate_risk_item(self, risk: Any, index: int) -> list[str]:
        """Validate a single risk item.

        Required fields:
        - category: valid risk category
        - severity: one of high/medium/low
        - description: non-empty string
        - clause_excerpt: non-empty string
        """
        errors: list[str] = []
        prefix = f"risks[{index}]"

        if not isinstance(risk, dict):
            return [f"{prefix}: must be an object"]

        # Check category
        if "category" not in risk:
            errors.append(f"{prefix}: missing 'category' field")
        elif risk["category"] not in VALID_RISK_CATEGORIES:
            errors.append(
                f"{prefix}: invalid category '{risk['category']}'. "
                f"Must be one of: {VALID_RISK_CATEGORIES}"
            )

        # Check severity
        if "severity" not in risk:
            errors.append(f"{prefix}: missing 'severity' field")
        elif risk["severity"] not in VALID_RISK_LEVELS:
            errors.append(
                f"{prefix}: invalid severity '{risk['severity']}'. "
                f"Must be one of: {VALID_RISK_LEVELS}"
            )

        # Check description
        if "description" not in risk:
            errors.append(f"{prefix}: missing 'description' field")
        elif not isinstance(risk["description"], str) or not risk["description"].strip():
            errors.append(f"{prefix}: 'description' must be a non-empty string")

        # Check clause_excerpt
        if "clause_excerpt" not in risk:
            errors.append(f"{prefix}: missing 'clause_excerpt' field")
        elif not isinstance(risk["clause_excerpt"], str) or not risk["clause_excerpt"].strip():
            errors.append(f"{prefix}: 'clause_excerpt' must be a non-empty string")

        return errors

    def _validate_compare_response(self, response: dict[str, Any]) -> SchemaValidationResult:
        """Validate document comparison response schema.

        Required fields:
        - differences: list of difference items
        - overall_similarity: float between 0 and 1
        """
        errors: list[str] = []
        warnings: list[str] = []

        # Check overall_similarity
        if "overall_similarity" not in response:
            errors.append("Missing required field: overall_similarity")
        else:
            sim = response["overall_similarity"]
            if not isinstance(sim, (int, float)):
                errors.append("Field 'overall_similarity' must be a number")
            elif not 0.0 <= sim <= 1.0:
                errors.append(f"Field 'overall_similarity' must be between 0 and 1, got {sim}")

        # Check differences field
        if "differences" not in response:
            errors.append("Missing required field: differences")
        elif not isinstance(response["differences"], list):
            errors.append("Field 'differences' must be a list")
        else:
            for i, diff in enumerate(response["differences"]):
                diff_errors = self._validate_difference_item(diff, i)
                errors.extend(diff_errors)

        is_valid = len(errors) == 0
        return SchemaValidationResult(is_valid=is_valid, errors=errors, warnings=warnings)

    def _validate_difference_item(self, diff: Any, index: int) -> list[str]:
        """Validate a single difference item.

        Required fields:
        - section: non-empty string
        - doc_a_excerpt: string
        - doc_b_excerpt: string
        - change_type: one of added/removed/modified
        - similarity: float between 0 and 1
        """
        errors: list[str] = []
        prefix = f"differences[{index}]"

        if not isinstance(diff, dict):
            return [f"{prefix}: must be an object"]

        # Check section
        if "section" not in diff:
            errors.append(f"{prefix}: missing 'section' field")
        elif not isinstance(diff["section"], str) or not diff["section"].strip():
            errors.append(f"{prefix}: 'section' must be a non-empty string")

        # Check change_type
        if "change_type" not in diff:
            errors.append(f"{prefix}: missing 'change_type' field")
        elif diff["change_type"] not in VALID_CHANGE_TYPES:
            errors.append(
                f"{prefix}: invalid change_type '{diff['change_type']}'. "
                f"Must be one of: {VALID_CHANGE_TYPES}"
            )

        # Check similarity
        if "similarity" in diff:
            sim = diff["similarity"]
            if not isinstance(sim, (int, float)):
                errors.append(f"{prefix}: 'similarity' must be a number")
            elif not 0.0 <= sim <= 1.0:
                errors.append(f"{prefix}: 'similarity' must be between 0 and 1")

        return errors
