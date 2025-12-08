"""Utility functions for E2E tests."""
from typing import Any


def assert_query_response_valid(data: dict[str, Any]) -> None:
    """Validate query response structure and content.

    Args:
        data: Response data from /query endpoint

    Raises:
        AssertionError: If response is invalid
    """
    # Check required fields
    assert "answer" in data, "Response missing 'answer' field"
    assert "confidence" in data, "Response missing 'confidence' field"
    assert "citation_chunks" in data, "Response missing 'citation_chunks' field"

    # Validate answer
    assert len(data["answer"]) > 0, "Answer is empty"
    assert isinstance(data["answer"], str), "Answer must be string"

    # Validate confidence
    assert data["confidence"] in ["low", "medium", "high"], \
        f"Invalid confidence level: {data['confidence']}"

    # Validate citations
    assert isinstance(data["citation_chunks"], list), "citation_chunks must be list"
    assert len(data["citation_chunks"]) > 0, "No citations provided"

    for i, citation in enumerate(data["citation_chunks"]):
        assert "content" in citation, f"Citation {i} missing 'content'"
        assert "page" in citation, f"Citation {i} missing 'page'"
        assert "score" in citation, f"Citation {i} missing 'score'"
        assert citation["score"] >= 0.7, \
            f"Citation {i} score {citation['score']} below threshold 0.7"


def assert_summary_response_valid(data: dict[str, Any]) -> None:
    """Validate summary response structure and content.

    Args:
        data: Response data from /summarize endpoint

    Raises:
        AssertionError: If response is invalid
    """
    assert "summary" in data, "Response missing 'summary' field"
    assert len(data["summary"]) > 100, "Summary too short (< 100 chars)"

    if "key_points" in data:
        assert isinstance(data["key_points"], list), "key_points must be list"
        assert len(data["key_points"]) >= 3, "Should have at least 3 key points"


def assert_risk_response_valid(data: dict[str, Any]) -> None:
    """Validate risk analysis response structure and content.

    Args:
        data: Response data from /risks endpoint

    Raises:
        AssertionError: If response is invalid
    """
    assert "risks" in data, "Response missing 'risks' field"
    assert isinstance(data["risks"], list), "risks must be list"

    for i, risk in enumerate(data["risks"]):
        assert "category" in risk, f"Risk {i} missing 'category'"
        assert "severity" in risk, f"Risk {i} missing 'severity'"
        assert "description" in risk, f"Risk {i} missing 'description'"
        assert risk["severity"] in ["low", "medium", "high", "critical"], \
            f"Risk {i} has invalid severity: {risk['severity']}"


def assert_comparison_response_valid(data: dict[str, Any]) -> None:
    """Validate document comparison response structure.

    Args:
        data: Response data from /compare endpoint

    Raises:
        AssertionError: If response is invalid
    """
    assert "differences" in data, "Response missing 'differences' field"
    assert isinstance(data["differences"], list), "differences must be list"
    assert "overall_similarity" in data, "Response missing 'overall_similarity' field"

    # Can be empty if documents are identical
    for i, diff in enumerate(data["differences"]):
        assert "section" in diff, f"Difference {i} missing 'section'"
        assert "change_type" in diff, f"Difference {i} missing 'change_type'"
        assert "similarity" in diff, f"Difference {i} missing 'similarity'"
        assert "doc_a_excerpt" in diff, f"Difference {i} missing 'doc_a_excerpt'"
        assert "doc_b_excerpt" in diff, f"Difference {i} missing 'doc_b_excerpt'"


def contains_french_text(text: str) -> bool:
    """Check if text contains French language indicators.

    Args:
        text: Text to check

    Returns:
        True if text appears to be in French
    """
    french_indicators = [
        "le", "la", "de", "et", "est", "des", "les", "un", "une",
        "dans", "pour", "que", "qui", "avec", "par", "sur", "être"
    ]
    text_lower = text.lower()
    matches = sum(1 for word in french_indicators if f" {word} " in f" {text_lower} ")
    return matches >= 3  # At least 3 French words


def assert_error_response_valid(
    response_data: dict[str, Any],
    expected_code: str | None = None
) -> None:
    """Validate error response structure.

    Args:
        response_data: Response data
        expected_code: Optional expected error code

    Raises:
        AssertionError: If error response is invalid
    """
    assert "error" in response_data, "Error response missing 'error' field"
    error = response_data["error"]

    assert "code" in error, "Error missing 'code'"
    assert "message" in error, "Error missing 'message'"
    assert "trace_id" in error, "Error missing 'trace_id'"

    if expected_code:
        assert error["code"] == expected_code, \
            f"Expected error code '{expected_code}', got '{error['code']}'"
