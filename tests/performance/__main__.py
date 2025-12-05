"""CLI runner for performance benchmarks.

Run with: python -m tests.performance [options]
"""

import argparse
import sys
from pathlib import Path

from .benchmarks import PerformanceBenchmark
from .report import generate_performance_report, generate_json_report


def main():
    """Run performance benchmarks from command line."""
    parser = argparse.ArgumentParser(
        description="Run Lexard performance benchmarks"
    )
    parser.add_argument(
        "--api-url",
        default="http://localhost:8000",
        help="API base URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--document-id",
        help="Document ID to use for query benchmarks",
    )
    parser.add_argument(
        "--file",
        type=Path,
        help="File path for upload benchmark",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=10,
        help="Number of iterations for each benchmark (default: 10)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=10,
        help="Concurrency level for concurrent tests (default: 10)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output path for report (default: stdout)",
    )
    parser.add_argument(
        "--format",
        choices=["markdown", "json"],
        default="markdown",
        help="Output format (default: markdown)",
    )
    parser.add_argument(
        "--embeddings-only",
        action="store_true",
        help="Only run embeddings benchmark (doesn't require API)",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("Lexard Performance Benchmark Suite")
    print("=" * 60)
    print()

    with PerformanceBenchmark(api_url=args.api_url) as benchmark:
        results = {}

        if args.embeddings_only:
            # Only run embeddings benchmark
            print("Running embeddings benchmark...")
            result = benchmark.benchmark_embeddings(iterations=args.iterations)
            results["embeddings"] = result.to_dict()
            print(f"  P95: {result.p95_ms:.2f}ms")
            print(f"  Status: {'✅ PASS' if result.passed else '❌ FAIL'}")
        else:
            # Need document_id for most benchmarks
            if not args.document_id:
                print(
                    "Error: --document-id is required for full benchmarks",
                    file=sys.stderr,
                )
                print(
                    "Use --embeddings-only to run without a document",
                    file=sys.stderr,
                )
                sys.exit(1)

            # RAG query benchmark
            print(f"Running RAG query benchmark ({args.iterations} iterations)...")
            result = benchmark.benchmark_query(
                document_id=args.document_id,
                iterations=args.iterations,
            )
            results["rag_query"] = result.to_dict()
            print(f"  P95: {result.p95_ms:.2f}ms (target: {result.target_ms}ms)")
            print(f"  Status: {'✅ PASS' if result.passed else '❌ FAIL'}")
            print()

            # Upload benchmark (if file provided)
            if args.file:
                print(f"Running upload benchmark ({args.iterations} iterations)...")
                result = benchmark.benchmark_upload(
                    file_path=args.file,
                    iterations=min(args.iterations, 5),  # Limit upload iterations
                )
                results["upload"] = result.to_dict()
                print(f"  P95: {result.p95_ms:.2f}ms (target: {result.target_ms}ms)")
                print(f"  Status: {'✅ PASS' if result.passed else '❌ FAIL'}")
                print()

            # Embeddings benchmark
            print(f"Running embeddings benchmark ({args.iterations} iterations)...")
            result = benchmark.benchmark_embeddings(iterations=args.iterations)
            results["embeddings"] = result.to_dict()
            print(f"  P95: {result.p95_ms:.2f}ms (target: {result.target_ms}ms)")
            print(f"  Status: {'✅ PASS' if result.passed else '❌ FAIL'}")
            print()

            # Concurrent benchmark
            print(
                f"Running concurrent benchmark "
                f"(concurrency={args.concurrency})..."
            )
            result = benchmark.benchmark_concurrent(
                document_id=args.document_id,
                concurrency=args.concurrency,
            )
            results["concurrent"] = result.to_dict()
            print(f"  P95: {result.p95_ms:.2f}ms (target: {result.target_ms}ms)")
            print(f"  RPS: {result.requests_per_second:.2f}")
            print(f"  Status: {'✅ PASS' if result.passed else '❌ FAIL'}")
            print()

        # Generate report
        print("=" * 60)
        print("Generating report...")

        if args.format == "json":
            report = generate_json_report(results, args.output)
            if not args.output:
                import json
                print(json.dumps(report, indent=2))
        else:
            report = generate_performance_report(results, args.output)
            if not args.output:
                print(report)

        if args.output:
            print(f"Report saved to: {args.output}")

        # Exit with error code if any benchmark failed
        all_passed = all(
            r.get("passed", True)
            for r in results.values()
            if isinstance(r, dict)
        )
        sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
