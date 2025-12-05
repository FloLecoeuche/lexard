"""
French language evaluation comparison report generation.

Compares English and French evaluation metrics to assess
multilingual support quality.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .metrics import EvaluationMetrics, TestResult


@dataclass
class LanguageComparison:
    """Comparison metrics between two languages."""

    english_metrics: EvaluationMetrics
    french_metrics: EvaluationMetrics

    @property
    def grounding_gap(self) -> float:
        """Absolute gap in grounding rate."""
        return abs(
            self.english_metrics.grounding_rate - self.french_metrics.grounding_rate
        )

    @property
    def hallucination_gap(self) -> float:
        """Absolute gap in hallucination rate."""
        return abs(
            self.english_metrics.hallucination_rate
            - self.french_metrics.hallucination_rate
        )

    @property
    def citation_gap(self) -> float:
        """Absolute gap in citation accuracy."""
        return abs(
            self.english_metrics.citation_accuracy
            - self.french_metrics.citation_accuracy
        )

    @property
    def pass_rate_gap(self) -> float:
        """Absolute gap in pass rate."""
        return abs(
            self.english_metrics.pass_rate - self.french_metrics.pass_rate
        )

    def is_production_ready(self) -> bool:
        """
        Check if French support meets production quality targets.

        Targets:
        - English grounding rate >= 90%
        - French grounding rate >= 85% (target: 90%)
        - English hallucination rate < 10%
        - French hallucination rate < 15% (target: <10%)
        - Gap between languages < 10%
        """
        # English baseline check
        en_ok = (
            self.english_metrics.grounding_rate >= 0.9
            and self.english_metrics.hallucination_rate < 0.1
        )

        # French targets (relaxed for MVP)
        fr_ok = (
            self.french_metrics.grounding_rate >= 0.85
            and self.french_metrics.hallucination_rate < 0.15
        )

        # Gap check
        gap_ok = (
            self.grounding_gap < 0.1
            and self.hallucination_gap < 0.1
        )

        return en_ok and fr_ok and gap_ok


def generate_comparison_report(
    en_metrics: EvaluationMetrics,
    fr_metrics: EvaluationMetrics,
    en_results: list[TestResult] | None = None,
    fr_results: list[TestResult] | None = None,
) -> str:
    """
    Generate markdown comparison report for English vs French.

    Args:
        en_metrics: English evaluation metrics
        fr_metrics: French evaluation metrics
        en_results: Optional English test results for details
        fr_results: Optional French test results for details

    Returns:
        Markdown formatted comparison report
    """
    comparison = LanguageComparison(en_metrics, fr_metrics)
    timestamp = datetime.now().isoformat()
    production_ready = comparison.is_production_ready()

    # Status indicators
    en_grounding_status = "PASS" if en_metrics.grounding_rate >= 0.9 else "FAIL"
    en_halluc_status = "PASS" if en_metrics.hallucination_rate < 0.1 else "FAIL"
    fr_grounding_status = "PASS" if fr_metrics.grounding_rate >= 0.85 else "FAIL"
    fr_halluc_status = "PASS" if fr_metrics.hallucination_rate < 0.15 else "FAIL"
    gap_grounding_status = "PASS" if comparison.grounding_gap < 0.1 else "FAIL"
    gap_halluc_status = "PASS" if comparison.hallucination_gap < 0.1 else "FAIL"

    report = f"""# French Language Support Evaluation Report

**Generated:** {timestamp}

## Summary

| Metric | English | French | Gap | Status |
|--------|---------|--------|-----|--------|
| Grounding Rate | {en_metrics.grounding_rate:.1%} | {fr_metrics.grounding_rate:.1%} | {comparison.grounding_gap:.1%} | {"PASS" if comparison.grounding_gap < 0.1 else "FAIL"} |
| Hallucination Rate | {en_metrics.hallucination_rate:.1%} | {fr_metrics.hallucination_rate:.1%} | {comparison.hallucination_gap:.1%} | {"PASS" if comparison.hallucination_gap < 0.1 else "FAIL"} |
| Citation Accuracy | {en_metrics.citation_accuracy:.1%} | {fr_metrics.citation_accuracy:.1%} | {comparison.citation_gap:.1%} | {"PASS" if comparison.citation_gap < 0.1 else "FAIL"} |
| Pass Rate | {en_metrics.pass_rate:.1%} | {fr_metrics.pass_rate:.1%} | {comparison.pass_rate_gap:.1%} | {"PASS" if comparison.pass_rate_gap < 0.15 else "FAIL"} |

## Quality Assessment

**French Support Status:** {"PRODUCTION READY" if production_ready else "NEEDS IMPROVEMENT"}

## Target Compliance

### English Baseline

| Target | Required | Actual | Status |
|--------|----------|--------|--------|
| Grounding Rate | >= 90% | {en_metrics.grounding_rate:.1%} | {en_grounding_status} |
| Hallucination Rate | < 10% | {en_metrics.hallucination_rate:.1%} | {en_halluc_status} |

### French Targets

| Target | Required | Actual | Status |
|--------|----------|--------|--------|
| Grounding Rate | >= 85% (target: 90%) | {fr_metrics.grounding_rate:.1%} | {fr_grounding_status} |
| Hallucination Rate | < 15% (target: <10%) | {fr_metrics.hallucination_rate:.1%} | {fr_halluc_status} |

### Language Gap Targets

| Metric | Max Gap | Actual Gap | Status |
|--------|---------|------------|--------|
| Grounding Rate | < 10% | {comparison.grounding_gap:.1%} | {gap_grounding_status} |
| Hallucination Rate | < 10% | {comparison.hallucination_gap:.1%} | {gap_halluc_status} |

## Detailed Metrics

### English Results

- **Total Cases:** {en_metrics.total_cases}
- **Passed:** {en_metrics.passed_cases}
- **Failed:** {en_metrics.failed_cases}
- **Refusal Rate:** {en_metrics.refusal_rate:.1%}
- **Refusal Appropriateness:** {en_metrics.refusal_appropriateness:.1%}

### French Results

- **Total Cases:** {fr_metrics.total_cases}
- **Passed:** {fr_metrics.passed_cases}
- **Failed:** {fr_metrics.failed_cases}
- **Refusal Rate:** {fr_metrics.refusal_rate:.1%}
- **Refusal Appropriateness:** {fr_metrics.refusal_appropriateness:.1%}

## Recommendations

{_generate_recommendations(comparison)}

---

*Report generated by Lexard French Evaluation Module*
"""

    return report


def _generate_recommendations(comparison: LanguageComparison) -> str:
    """Generate recommendations based on comparison results."""
    recommendations: list[str] = []

    # Check English baseline
    if comparison.english_metrics.grounding_rate < 0.9:
        recommendations.append(
            "- English grounding rate below target. Review retrieval quality."
        )
    if comparison.english_metrics.hallucination_rate >= 0.1:
        recommendations.append(
            "- English hallucination rate above target. Strengthen guardrails."
        )

    # Check French targets
    if comparison.french_metrics.grounding_rate < 0.85:
        recommendations.append(
            "- French grounding rate below minimum. Check multilingual embeddings quality."
        )
    elif comparison.french_metrics.grounding_rate < 0.9:
        recommendations.append(
            "- French grounding rate below optimal. Consider fine-tuning embeddings."
        )

    if comparison.french_metrics.hallucination_rate >= 0.15:
        recommendations.append(
            "- French hallucination rate above tolerance. Review French prompt templates."
        )
    elif comparison.french_metrics.hallucination_rate >= 0.1:
        recommendations.append(
            "- French hallucination rate above target. Minor guardrail adjustments needed."
        )

    # Check gaps
    if comparison.grounding_gap >= 0.1:
        recommendations.append(
            "- Large grounding gap between languages. Multilingual embeddings may need tuning."
        )
    if comparison.hallucination_gap >= 0.1:
        recommendations.append(
            "- Large hallucination gap. French guardrails may need strengthening."
        )

    if not recommendations:
        recommendations.append(
            "- All metrics within acceptable ranges. French support is production ready."
        )

    return "\n".join(recommendations)


def generate_json_comparison_report(
    en_metrics: EvaluationMetrics,
    fr_metrics: EvaluationMetrics,
) -> dict[str, Any]:
    """
    Generate JSON comparison report.

    Args:
        en_metrics: English evaluation metrics
        fr_metrics: French evaluation metrics

    Returns:
        Dictionary with comparison data
    """
    comparison = LanguageComparison(en_metrics, fr_metrics)

    return {
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "report_type": "french_comparison",
        },
        "summary": {
            "production_ready": comparison.is_production_ready(),
            "gaps": {
                "grounding": comparison.grounding_gap,
                "hallucination": comparison.hallucination_gap,
                "citation": comparison.citation_gap,
                "pass_rate": comparison.pass_rate_gap,
            },
        },
        "english": {
            "total_cases": en_metrics.total_cases,
            "pass_rate": en_metrics.pass_rate,
            "grounding_rate": en_metrics.grounding_rate,
            "hallucination_rate": en_metrics.hallucination_rate,
            "citation_accuracy": en_metrics.citation_accuracy,
            "refusal_rate": en_metrics.refusal_rate,
        },
        "french": {
            "total_cases": fr_metrics.total_cases,
            "pass_rate": fr_metrics.pass_rate,
            "grounding_rate": fr_metrics.grounding_rate,
            "hallucination_rate": fr_metrics.hallucination_rate,
            "citation_accuracy": fr_metrics.citation_accuracy,
            "refusal_rate": fr_metrics.refusal_rate,
        },
        "targets": {
            "english": {
                "grounding_rate": {
                    "target": 0.9,
                    "actual": en_metrics.grounding_rate,
                    "passed": en_metrics.grounding_rate >= 0.9,
                },
                "hallucination_rate": {
                    "target": 0.1,
                    "actual": en_metrics.hallucination_rate,
                    "passed": en_metrics.hallucination_rate < 0.1,
                },
            },
            "french": {
                "grounding_rate": {
                    "target": 0.85,
                    "actual": fr_metrics.grounding_rate,
                    "passed": fr_metrics.grounding_rate >= 0.85,
                },
                "hallucination_rate": {
                    "target": 0.15,
                    "actual": fr_metrics.hallucination_rate,
                    "passed": fr_metrics.hallucination_rate < 0.15,
                },
            },
            "gaps": {
                "grounding_rate": {
                    "max_gap": 0.1,
                    "actual_gap": comparison.grounding_gap,
                    "passed": comparison.grounding_gap < 0.1,
                },
                "hallucination_rate": {
                    "max_gap": 0.1,
                    "actual_gap": comparison.hallucination_gap,
                    "passed": comparison.hallucination_gap < 0.1,
                },
            },
        },
    }
