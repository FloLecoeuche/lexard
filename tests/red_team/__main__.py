"""CLI entry point for red team testing.

Usage:
    python -m tests.red_team [--api-url URL] [--dataset PATH] [--document-id ID] [--output PATH]

Examples:
    # Run injection tests only (no API required)
    python -m tests.red_team

    # Run with custom dataset
    python -m tests.red_team --dataset data/eval/red_team.yaml

    # Run full API tests
    python -m tests.red_team --document-id abc123 --dataset data/eval/red_team.yaml

    # Save report to file
    python -m tests.red_team --output reports/red_team_report.md
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

from .runner import (
    RedTeamRunner,
    generate_report_markdown,
    run_red_team_tests,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> int:
    """Main entry point for red team testing CLI."""
    parser = argparse.ArgumentParser(
        description="Run red team adversarial tests against Lexard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--api-url",
        default="http://localhost:8000",
        help="Base URL for the Lexard API (default: http://localhost:8000)",
    )

    parser.add_argument(
        "--dataset",
        type=Path,
        help="Path to the red team dataset YAML file",
    )

    parser.add_argument(
        "--document-id",
        help="Document ID to use for API tests (required for full API testing)",
    )

    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Path to save the markdown report",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )

    parser.add_argument(
        "--injection-only",
        action="store_true",
        help="Run only injection detection tests (no API required)",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Print header
    print("=" * 60)
    print("Lexard Red Team Testing Suite")
    print("=" * 60)
    print(f"Timestamp: {datetime.utcnow().isoformat()}")
    print(f"API URL: {args.api_url}")
    print()

    try:
        with RedTeamRunner(api_url=args.api_url) as runner:
            # Check API health if doing API tests
            if args.document_id and not args.injection_only:
                if not runner.check_api_health():
                    logger.error(f"API not available at {args.api_url}")
                    print(f"ERROR: API not available at {args.api_url}")
                    print("Run with --injection-only to test without API")
                    return 1
                print("API health check: OK")
                print()

            # Run tests
            if args.injection_only or not args.document_id:
                print("Running injection detection tests...")
                print()
                report = runner.run_all_injection_tests(args.dataset)
            else:
                print(f"Running full API tests against document: {args.document_id}")
                print()
                if not args.dataset:
                    logger.error("Dataset path required for API tests")
                    print("ERROR: --dataset required for API tests")
                    return 1
                report = runner.run_all_api_tests(args.dataset, args.document_id)

        # Print summary
        print()
        print("=" * 60)
        print("RESULTS SUMMARY")
        print("=" * 60)
        print(f"Total Tests:  {report.total_tests}")
        print(f"Passed:       {report.passed}")
        print(f"Failed:       {report.failed}")
        print(f"Errors:       {report.errors}")
        print(f"Skipped:      {report.skipped}")
        print(f"Pass Rate:    {report.pass_rate:.1%}")
        print()

        # Print critical/high failures
        if report.critical_failures:
            print("CRITICAL FAILURES:")
            for result in report.critical_failures:
                print(f"  - {result.test_case.id}: {result.test_case.name}")
            print()

        if report.high_failures:
            print("HIGH SEVERITY FAILURES:")
            for result in report.high_failures:
                print(f"  - {result.test_case.id}: {result.test_case.name}")
            print()

        # Generate and optionally save report
        markdown_report = generate_report_markdown(report)

        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with open(args.output, "w") as f:
                f.write(markdown_report)
            print(f"Report saved to: {args.output}")
        else:
            # Print detailed failures
            if report.failed > 0:
                print()
                print("FAILED TEST DETAILS:")
                print("-" * 40)
                for result in report.results:
                    if result.status.value == "failed":
                        print(f"ID: {result.test_case.id}")
                        print(f"Name: {result.test_case.name}")
                        print(f"Category: {result.test_case.category}")
                        print(f"Severity: {result.test_case.severity.value}")
                        print(f"Expected: {result.test_case.expected_behavior}")
                        print(f"Actual: {result.actual_behavior}")
                        print(f"Input: {result.test_case.input_text[:80]}...")
                        print("-" * 40)

        # Determine exit code
        if report.critical_failures or report.high_failures:
            print()
            print("RESULT: FAIL (critical/high severity failures detected)")
            return 1
        elif report.failed > 0:
            print()
            print("RESULT: WARNING (some tests failed)")
            return 0  # Exit 0 for low/medium failures
        else:
            print()
            print("RESULT: PASS (all tests passed)")
            return 0

    except Exception as e:
        logger.exception("Red team testing failed")
        print(f"ERROR: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
