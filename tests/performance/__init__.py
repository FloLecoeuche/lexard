"""Performance benchmarking suite for Lexard."""

from .benchmarks import PerformanceBenchmark, BenchmarkResult
from .report import generate_performance_report

__all__ = [
    "PerformanceBenchmark",
    "BenchmarkResult",
    "generate_performance_report",
]
