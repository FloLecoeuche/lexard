"""
Evaluation harness for Lexard contract analysis system.

This module provides:
- Test dataset loading and management
- Metric calculations (grounding, hallucination, refusal rates)
- Automated evaluation pipeline
- Report generation
"""

from .dataset import DatasetLoader, TestCase
from .metrics import EvaluationMetrics, calculate_metrics
from .runner import EvaluationRunner
from .report import generate_report

__all__ = [
    "DatasetLoader",
    "TestCase",
    "EvaluationMetrics",
    "calculate_metrics",
    "EvaluationRunner",
    "generate_report",
]
