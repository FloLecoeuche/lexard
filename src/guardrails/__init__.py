"""Guardrails layer - Input and output validation.

Provides a unified validation pipeline that includes:
- Prompt injection detection (input)
- Hallucination detection (output)
- PII filtering (output)
- Schema validation (output)
- Metrics collection
"""

import logging
from dataclasses import dataclass, field
from typing import Any

from src.config import GuardrailsConfig

from src.guardrails.hallucination import (
    GroundingResult,
    HallucinationDetector,
)
from src.guardrails.pii import (
    PIIFilter,
    PIIFilterResult,
    PIIMatch,
)
from src.guardrails.prompt_injection import (
    InjectionDetectionResult,
    InjectionDetector,
    InjectionSeverity,
)
from src.guardrails.schema import (
    SchemaValidationResult,
    SchemaValidator,
)
from src.guardrails.validators import (
    GuardrailsResult,
    ResponseValidator,
    ValidationResult,
    get_refusal_response,
)

logger = logging.getLogger(__name__)

__all__ = [
    # Legacy validators
    "GuardrailsResult",
    "ResponseValidator",
    "ValidationResult",
    "get_refusal_response",
    # Hallucination
    "GroundingResult",
    "HallucinationDetector",
    # PII
    "PIIFilter",
    "PIIFilterResult",
    "PIIMatch",
    # Prompt injection
    "InjectionDetectionResult",
    "InjectionDetector",
    "InjectionSeverity",
    # Schema
    "SchemaValidationResult",
    "SchemaValidator",
    # Unified pipeline
    "GuardrailsPipeline",
    "PipelineResult",
    "GuardrailsMetrics",
]


@dataclass
class GuardrailsMetrics:
    """Metrics for guardrails pipeline.

    Tracks rejection counts by type for monitoring and alerting.

    Attributes:
        total_inputs: Total inputs processed
        total_outputs: Total outputs processed
        injection_blocks: Input rejections due to injection
        hallucination_blocks: Output rejections due to hallucination
        schema_failures: Output rejections due to schema validation
        pii_redactions: Outputs that had PII redacted
    """

    total_inputs: int = 0
    total_outputs: int = 0
    injection_blocks: int = 0
    hallucination_blocks: int = 0
    schema_failures: int = 0
    pii_redactions: int = 0

    def to_dict(self) -> dict[str, int]:
        """Convert metrics to dictionary for logging/API."""
        return {
            "total_inputs": self.total_inputs,
            "total_outputs": self.total_outputs,
            "injection_blocks": self.injection_blocks,
            "hallucination_blocks": self.hallucination_blocks,
            "schema_failures": self.schema_failures,
            "pii_redactions": self.pii_redactions,
        }

    @property
    def input_block_rate(self) -> float:
        """Percentage of inputs blocked."""
        if self.total_inputs == 0:
            return 0.0
        return self.injection_blocks / self.total_inputs * 100

    @property
    def output_block_rate(self) -> float:
        """Percentage of outputs blocked (hallucination + schema)."""
        if self.total_outputs == 0:
            return 0.0
        return (self.hallucination_blocks + self.schema_failures) / self.total_outputs * 100


@dataclass
class PipelineResult:
    """Result from the unified guardrails pipeline.

    Attributes:
        passed: Whether validation passed overall
        blocked_reason: Reason for blocking if not passed
        injection_result: Result from injection detection (input)
        grounding_result: Result from hallucination detection (output)
        schema_result: Result from schema validation (output)
        pii_result: Result from PII filtering (output)
        sanitized_response: Modified response after PII filtering
        retry_count: Number of retries attempted
    """

    passed: bool
    blocked_reason: str | None = None
    injection_result: InjectionDetectionResult | None = None
    grounding_result: GroundingResult | None = None
    schema_result: SchemaValidationResult | None = None
    pii_result: PIIFilterResult | None = None
    sanitized_response: dict[str, Any] | None = None
    retry_count: int = 0


class GuardrailsPipeline:
    """Unified validation pipeline for RAG inputs and outputs.

    Combines all guardrails components into a single pipeline:
    1. Input validation: Prompt injection detection
    2. Output validation: Hallucination, schema, PII

    Supports retry mechanism for validation failures.

    Attributes:
        hallucination: HallucinationDetector instance
        pii: PIIFilter instance
        schema: SchemaValidator instance
        injection: InjectionDetector instance
        max_retries: Maximum retry attempts on validation failure
        metrics: Pipeline metrics tracker
    """

    def __init__(
        self,
        config: GuardrailsConfig | None = None,
        hallucination_threshold: float | None = None,
        enable_pii_filter: bool | None = None,
        max_retries: int | None = None,
    ):
        """Initialize GuardrailsPipeline.

        Args:
            config: GuardrailsConfig instance or None for defaults
            hallucination_threshold: Override hallucination threshold
            enable_pii_filter: Override PII filter enabled
            max_retries: Override max retries
        """
        # Use config values with explicit overrides
        if config:
            threshold = hallucination_threshold if hallucination_threshold is not None else config.hallucination_threshold
            pii_enabled = enable_pii_filter if enable_pii_filter is not None else config.enable_pii_filter
            retries = max_retries if max_retries is not None else config.max_retries
        else:
            threshold = hallucination_threshold if hallucination_threshold is not None else 0.8
            pii_enabled = enable_pii_filter if enable_pii_filter is not None else True
            retries = max_retries if max_retries is not None else 2

        self.hallucination = HallucinationDetector(threshold=threshold)
        self.pii = PIIFilter(enabled=pii_enabled)
        self.schema = SchemaValidator()
        self.injection = InjectionDetector()
        self.max_retries = retries
        self.metrics = GuardrailsMetrics()

    def validate_input(self, query: str) -> PipelineResult:
        """Validate user input before processing.

        Checks for prompt injection attempts.

        Args:
            query: User query string

        Returns:
            PipelineResult with validation status
        """
        self.metrics.total_inputs += 1

        injection_result = self.injection.detect(query)

        if injection_result.is_injection:
            self.metrics.injection_blocks += 1
            logger.warning(
                "Input blocked by guardrails",
                extra={
                    "reason": "prompt_injection",
                    "severity": injection_result.severity.value if injection_result.severity else None,
                    "description": injection_result.description,
                },
            )
            return PipelineResult(
                passed=False,
                blocked_reason=f"Blocked: potential prompt injection ({injection_result.description})",
                injection_result=injection_result,
            )

        return PipelineResult(
            passed=True,
            injection_result=injection_result,
        )

    def validate_output(
        self,
        response: dict[str, Any],
        citation_chunks: list[str],
        response_type: str = "query",
    ) -> PipelineResult:
        """Validate LLM output before returning to user.

        Performs:
        1. Schema validation
        2. Hallucination check (for query responses with answer field)
        3. PII redaction

        Args:
            response: Response dictionary to validate
            citation_chunks: Citation text chunks for grounding check
            response_type: Type of response ("query", "summarize", "risk", "compare")

        Returns:
            PipelineResult with validation status and sanitized response
        """
        self.metrics.total_outputs += 1

        # 1. Schema validation
        schema_result = self.schema.validate(response, response_type)
        if not schema_result.is_valid:
            self.metrics.schema_failures += 1
            logger.warning(
                "Output blocked by guardrails",
                extra={
                    "reason": "schema_validation",
                    "errors": schema_result.errors,
                },
            )
            return PipelineResult(
                passed=False,
                blocked_reason=f"Invalid response schema: {'; '.join(schema_result.errors)}",
                schema_result=schema_result,
            )

        # 2. Hallucination check (only for responses with answer field)
        grounding_result = None
        if "answer" in response and citation_chunks:
            grounding_result = self.hallucination.check_grounding(
                response["answer"],
                citation_chunks,
            )

            if not grounding_result.is_grounded:
                self.metrics.hallucination_blocks += 1
                logger.warning(
                    "Output blocked by guardrails",
                    extra={
                        "reason": "hallucination",
                        "grounding_score": grounding_result.grounding_score,
                        "threshold": self.hallucination.threshold,
                    },
                )
                return PipelineResult(
                    passed=False,
                    blocked_reason=f"Response not grounded in citations (score: {grounding_result.grounding_score:.2f})",
                    grounding_result=grounding_result,
                    schema_result=schema_result,
                )

        # 3. PII redaction
        sanitized = response.copy()
        pii_result = None

        # Redact PII from text fields
        text_fields = ["answer", "summary"]
        for field in text_fields:
            if field in sanitized and isinstance(sanitized[field], str):
                pii_result = self.pii.redact(sanitized[field])
                if pii_result.was_filtered:
                    self.metrics.pii_redactions += 1
                    sanitized[field] = pii_result.filtered_text
                    logger.info(
                        "PII redacted from response",
                        extra={
                            "field": field,
                            "patterns_found": list(pii_result.patterns_found),
                        },
                    )

        return PipelineResult(
            passed=True,
            grounding_result=grounding_result,
            schema_result=schema_result,
            pii_result=pii_result,
            sanitized_response=sanitized,
        )

    def get_metrics(self) -> dict[str, int]:
        """Get current metrics as dictionary.

        Returns:
            Dictionary of metric names to values
        """
        return self.metrics.to_dict()

    def reset_metrics(self) -> None:
        """Reset all metrics to zero."""
        self.metrics = GuardrailsMetrics()
