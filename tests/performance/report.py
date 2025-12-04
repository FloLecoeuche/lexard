"""Performance report generation for Lexard benchmarks."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .benchmarks import BenchmarkResult, ConcurrencyResult


def generate_performance_report(
    results: dict[str, Any],
    output_path: Path | None = None,
) -> str:
    """Generate a markdown performance report from benchmark results.

    Args:
        results: Dictionary of benchmark results from PerformanceBenchmark
        output_path: Optional path to save the report

    Returns:
        Markdown report string
    """
    timestamp = datetime.now().isoformat()

    # Calculate overall status
    all_passed = all(
        r.get("passed", True)
        for r in results.values()
        if isinstance(r, dict)
    )
    status_emoji = "✅" if all_passed else "❌"

    report = f"""# Performance Report

**Generated:** {timestamp}
**Overall Status:** {status_emoji} {"All targets met" if all_passed else "Some targets missed"}

## Summary

| Benchmark | P95 (ms) | Target (ms) | Status |
|-----------|----------|-------------|--------|
"""

    # Add summary rows
    for name, result in results.items():
        if isinstance(result, dict):
            p95 = result.get("p95_ms", "N/A")
            target = result.get("target_ms", "N/A")
            passed = result.get("passed", True)
            status = "✅" if passed else "❌"

            if isinstance(p95, (int, float)):
                p95 = f"{p95:.2f}"
            if isinstance(target, (int, float)):
                target = f"{target:.0f}"

            report += f"| {name} | {p95} | {target} | {status} |\n"

    report += "\n## Detailed Results\n"

    # Add detailed results for each benchmark
    for name, result in results.items():
        if isinstance(result, dict):
            report += f"\n### {name.replace('_', ' ').title()}\n\n"

            # Latency stats
            if "min_ms" in result:
                report += "**Latency Statistics:**\n\n"
                report += "| Metric | Value (ms) |\n"
                report += "|--------|------------|\n"
                report += f"| Min | {result.get('min_ms', 'N/A'):.2f} |\n"
                report += f"| Max | {result.get('max_ms', 'N/A'):.2f} |\n"
                report += f"| Mean | {result.get('mean_ms', 'N/A'):.2f} |\n"
                report += f"| Median | {result.get('median_ms', 'N/A'):.2f} |\n"
                report += f"| P95 | {result.get('p95_ms', 'N/A'):.2f} |\n"
                if "p99_ms" in result:
                    report += f"| P99 | {result.get('p99_ms', 'N/A'):.2f} |\n"
                report += "\n"

            # Concurrency stats
            if "concurrency" in result:
                report += "**Concurrency Statistics:**\n\n"
                report += f"- Concurrency Level: {result.get('concurrency')}\n"
                report += f"- Total Requests: {result.get('total_requests')}\n"
                report += f"- Successful: {result.get('successful_requests')}\n"
                report += f"- Failed: {result.get('failed_requests')}\n"
                report += f"- Requests/sec: {result.get('requests_per_second', 0):.2f}\n"
                report += "\n"

            # Errors
            if result.get("errors"):
                report += "**Errors:**\n\n"
                for error in result["errors"]:
                    report += f"- {error}\n"
                report += "\n"

    # Performance targets section
    report += """## Performance Targets

| Metric | Target | Description |
|--------|--------|-------------|
| RAG Query P95 | < 3000ms | End-to-end query response time |
| Document Ingestion (10 pages) | < 15000ms | Time to process and index |
| Embedding per Chunk | < 500ms | Single chunk embedding time |
| Concurrent (10 req) P95 | < 5000ms | 10 simultaneous requests |

"""

    # Save to file if path provided
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report)

    return report


def generate_json_report(
    results: dict[str, Any],
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Generate a JSON performance report from benchmark results.

    Args:
        results: Dictionary of benchmark results from PerformanceBenchmark
        output_path: Optional path to save the JSON report

    Returns:
        JSON-serializable dictionary with report data
    """
    report = {
        "generated_at": datetime.now().isoformat(),
        "benchmarks": results,
        "summary": {
            "total_benchmarks": len(results),
            "passed": sum(
                1 for r in results.values()
                if isinstance(r, dict) and r.get("passed", True)
            ),
            "failed": sum(
                1 for r in results.values()
                if isinstance(r, dict) and not r.get("passed", True)
            ),
        },
    }

    report["summary"]["all_passed"] = (
        report["summary"]["passed"] == report["summary"]["total_benchmarks"]
    )

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2))

    return report


def format_benchmark_result(result: BenchmarkResult | ConcurrencyResult) -> str:
    """Format a single benchmark result for display.

    Args:
        result: Benchmark result to format

    Returns:
        Formatted string representation
    """
    status = "✅ PASS" if result.passed else "❌ FAIL"

    if isinstance(result, ConcurrencyResult):
        return f"""
{result.name}: {status}
  Concurrency: {result.concurrency}
  P95: {result.p95_ms:.2f}ms (target: {result.target_ms}ms)
  RPS: {result.requests_per_second:.2f}
  Success Rate: {result.successful_requests}/{result.total_requests}
"""
    else:
        lines = [
            f"\n{result.name}: {status}",
            f"  Iterations: {result.iterations}",
            f"  P95: {result.p95_ms:.2f}ms (target: {result.target_ms}ms)",
            f"  Mean: {result.mean_ms:.2f}ms",
            f"  Range: {result.min_ms:.2f}ms - {result.max_ms:.2f}ms",
        ]
        if result.errors:
            lines.append(f"  Errors: {len(result.errors)}")
        return "\n".join(lines)
