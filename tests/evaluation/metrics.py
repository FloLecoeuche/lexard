"""
Metric calculations for evaluation.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class EvaluationMetrics:
    """Computed metrics from evaluation run."""

    total_cases: int = 0
    passed_cases: int = 0
    failed_cases: int = 0

    # Grounding metrics
    grounding_rate: float = 0.0  # % of answers with valid citations
    hallucination_rate: float = 0.0  # % of answers flagged as hallucinated

    # Refusal metrics
    refusal_count: int = 0
    refusal_rate: float = 0.0  # % of responses that were refusals
    appropriate_refusals: int = 0
    inappropriate_refusals: int = 0
    refusal_appropriateness: float = 0.0  # % of refusals that were correct

    # Citation metrics
    citation_accuracy: float = 0.0  # % of citations that match expected

    # Confidence metrics
    average_confidence: float = 0.0
    confidence_distribution: dict[str, int] = field(default_factory=dict)

    # Category breakdown
    category_results: dict[str, dict[str, Any]] = field(default_factory=dict)

    @property
    def pass_rate(self) -> float:
        """Overall pass rate."""
        if self.total_cases == 0:
            return 0.0
        return self.passed_cases / self.total_cases

    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to dictionary for serialization."""
        return {
            "total_cases": self.total_cases,
            "passed_cases": self.passed_cases,
            "failed_cases": self.failed_cases,
            "pass_rate": f"{self.pass_rate:.1%}",
            "grounding_rate": f"{self.grounding_rate:.1%}",
            "hallucination_rate": f"{self.hallucination_rate:.1%}",
            "refusal_count": self.refusal_count,
            "refusal_rate": f"{self.refusal_rate:.1%}",
            "refusal_appropriateness": f"{self.refusal_appropriateness:.1%}",
            "citation_accuracy": f"{self.citation_accuracy:.1%}",
            "average_confidence": f"{self.average_confidence:.2f}",
            "confidence_distribution": self.confidence_distribution,
            "category_results": self.category_results,
        }


@dataclass
class TestResult:
    """Result of a single test case evaluation."""

    case_id: str
    category: str
    passed: bool
    expected_behavior: str | None
    actual_behavior: str | None
    has_citations: bool
    citation_count: int
    confidence: str | None
    hallucination_flagged: bool
    error: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


def calculate_grounding_rate(results: list[TestResult]) -> float:
    """
    Calculate percentage of answers that have citations.

    Args:
        results: List of test results

    Returns:
        Grounding rate as a float between 0 and 1
    """
    if not results:
        return 0.0

    # Only count non-refusal responses
    answerable_results = [
        r for r in results if r.actual_behavior != "refuse"
    ]

    if not answerable_results:
        return 0.0

    with_citations = sum(1 for r in answerable_results if r.has_citations)
    return with_citations / len(answerable_results)


def calculate_hallucination_rate(results: list[TestResult]) -> float:
    """
    Calculate percentage of answers flagged as hallucinated.

    Args:
        results: List of test results

    Returns:
        Hallucination rate as a float between 0 and 1
    """
    if not results:
        return 0.0

    # Only count non-refusal responses
    answerable_results = [
        r for r in results if r.actual_behavior != "refuse"
    ]

    if not answerable_results:
        return 0.0

    hallucinated = sum(1 for r in answerable_results if r.hallucination_flagged)
    return hallucinated / len(answerable_results)


def calculate_refusal_metrics(
    results: list[TestResult],
) -> tuple[float, float, int, int]:
    """
    Calculate refusal-related metrics.

    Args:
        results: List of test results

    Returns:
        Tuple of (refusal_rate, appropriateness, appropriate_count, inappropriate_count)
    """
    if not results:
        return 0.0, 0.0, 0, 0

    refusals = [r for r in results if r.actual_behavior == "refuse"]
    refusal_rate = len(refusals) / len(results) if results else 0.0

    # Count appropriate vs inappropriate refusals
    appropriate = sum(
        1 for r in refusals if r.expected_behavior == "refuse"
    )
    inappropriate = len(refusals) - appropriate

    appropriateness = appropriate / len(refusals) if refusals else 0.0

    return refusal_rate, appropriateness, appropriate, inappropriate


def calculate_citation_accuracy(results: list[TestResult]) -> float:
    """
    Calculate accuracy of citations.

    This measures how often citations are present when expected.

    Args:
        results: List of test results

    Returns:
        Citation accuracy as a float between 0 and 1
    """
    if not results:
        return 0.0

    # Count cases where citations were expected
    expected_citations = [
        r for r in results
        if r.details.get("expected_citations", False)
    ]

    if not expected_citations:
        return 1.0  # No citations expected, so accuracy is perfect

    correct = sum(1 for r in expected_citations if r.has_citations)
    return correct / len(expected_citations)


def calculate_confidence_distribution(
    results: list[TestResult],
) -> dict[str, int]:
    """
    Calculate distribution of confidence levels.

    Args:
        results: List of test results

    Returns:
        Dictionary mapping confidence level to count
    """
    distribution: dict[str, int] = {"low": 0, "medium": 0, "high": 0, "unknown": 0}

    for result in results:
        level = result.confidence or "unknown"
        if level in distribution:
            distribution[level] += 1
        else:
            distribution["unknown"] += 1

    return distribution


def calculate_average_confidence(results: list[TestResult]) -> float:
    """
    Calculate average confidence as a numeric value.

    Maps low=0.33, medium=0.66, high=1.0

    Args:
        results: List of test results

    Returns:
        Average confidence as float between 0 and 1
    """
    confidence_map = {"low": 0.33, "medium": 0.66, "high": 1.0}

    values = [
        confidence_map.get(r.confidence or "", 0.0)
        for r in results
        if r.confidence in confidence_map
    ]

    if not values:
        return 0.0

    return sum(values) / len(values)


def calculate_category_results(
    results: list[TestResult],
) -> dict[str, dict[str, Any]]:
    """
    Calculate metrics broken down by category.

    Args:
        results: List of test results

    Returns:
        Dictionary mapping category to metrics dict
    """
    categories: dict[str, list[TestResult]] = {}

    for result in results:
        if result.category not in categories:
            categories[result.category] = []
        categories[result.category].append(result)

    category_metrics: dict[str, dict[str, Any]] = {}

    for category, cat_results in categories.items():
        passed = sum(1 for r in cat_results if r.passed)
        total = len(cat_results)
        category_metrics[category] = {
            "total": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": f"{passed / total:.1%}" if total > 0 else "N/A",
        }

    return category_metrics


def calculate_metrics(results: list[TestResult]) -> EvaluationMetrics:
    """
    Calculate all evaluation metrics from test results.

    Args:
        results: List of test results

    Returns:
        EvaluationMetrics with all computed values
    """
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed

    refusal_rate, refusal_appropriateness, appropriate, inappropriate = (
        calculate_refusal_metrics(results)
    )
    refusal_count = sum(1 for r in results if r.actual_behavior == "refuse")

    return EvaluationMetrics(
        total_cases=total,
        passed_cases=passed,
        failed_cases=failed,
        grounding_rate=calculate_grounding_rate(results),
        hallucination_rate=calculate_hallucination_rate(results),
        refusal_count=refusal_count,
        refusal_rate=refusal_rate,
        appropriate_refusals=appropriate,
        inappropriate_refusals=inappropriate,
        refusal_appropriateness=refusal_appropriateness,
        citation_accuracy=calculate_citation_accuracy(results),
        average_confidence=calculate_average_confidence(results),
        confidence_distribution=calculate_confidence_distribution(results),
        category_results=calculate_category_results(results),
    )
