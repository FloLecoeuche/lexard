"""
CLI entry point for evaluation harness.

Usage:
    python -m tests.evaluation [OPTIONS]

Examples:
    python -m tests.evaluation
    python -m tests.evaluation --dataset contract_qa
    python -m tests.evaluation --api-url http://localhost:8000 --output-dir ./results
"""

import argparse
import logging
import sys
from pathlib import Path

from .dataset import DatasetLoader
from .runner import EvaluationRunner
from .report import save_report, generate_report


def setup_logging(verbose: bool = False) -> None:
    """Configure logging for evaluation run."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main() -> int:
    """Main entry point for evaluation CLI."""
    parser = argparse.ArgumentParser(
        description="Lexard Evaluation Harness",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--dataset",
        "-d",
        default="contract_qa",
        help="Dataset name to evaluate (default: contract_qa)",
    )

    parser.add_argument(
        "--api-url",
        default="http://localhost:8000",
        help="API base URL (default: http://localhost:8000)",
    )

    parser.add_argument(
        "--output-dir",
        "-o",
        default="data/eval/results",
        help="Output directory for reports (default: data/eval/results)",
    )

    parser.add_argument(
        "--format",
        "-f",
        nargs="+",
        choices=["md", "json"],
        default=["md", "json"],
        help="Report formats to generate (default: md json)",
    )

    parser.add_argument(
        "--list-datasets",
        "-l",
        action="store_true",
        help="List available datasets and exit",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Load dataset and show test cases without running",
    )

    parser.add_argument(
        "--document-id",
        help="Document ID to use for all test cases (overrides dataset)",
    )

    args = parser.parse_args()
    setup_logging(args.verbose)

    logger = logging.getLogger(__name__)

    # List datasets mode
    if args.list_datasets:
        loader = DatasetLoader()
        datasets = loader.list_datasets()
        print("Available datasets:")
        for ds in datasets:
            print(f"  - {ds}")
        return 0

    # Load dataset
    loader = DatasetLoader()
    try:
        dataset = loader.load(args.dataset)
    except FileNotFoundError as e:
        logger.error(f"Dataset not found: {e}")
        print(f"\nAvailable datasets: {', '.join(loader.list_datasets())}")
        return 1

    print(f"\n{'='*60}")
    print(f"Lexard Evaluation Harness")
    print(f"{'='*60}")
    print(f"Dataset: {dataset.name}")
    print(f"Version: {dataset.version}")
    print(f"Test cases: {len(dataset)}")
    print(f"Categories: {', '.join(dataset.get_categories())}")
    print(f"{'='*60}\n")

    # Dry run mode
    if args.dry_run:
        print("Test cases:")
        for i, case in enumerate(dataset, 1):
            print(f"  {i}. [{case.category}] {case.id}: {case.question[:50]}...")
        return 0

    # Check API availability
    with EvaluationRunner(api_url=args.api_url) as runner:
        if not runner.check_api_health():
            logger.error(f"API not available at {args.api_url}")
            print("\nMake sure the Lexard API is running:")
            print("  uvicorn src.api.main:app --reload")
            return 1

        print(f"API: {args.api_url} ✓")
        print()

        # Build document map if document_id provided
        document_map = None
        if args.document_id:
            # Map all documents to the provided ID
            document_map = {
                case.document: args.document_id
                for case in dataset
                if case.document
            }
            print(f"Using document ID: {args.document_id}")
            print()

        # Run evaluation
        print("Running evaluation...")
        results, metrics = runner.run_dataset(dataset, document_map)

        # Print summary
        print()
        print(f"{'='*60}")
        print("RESULTS SUMMARY")
        print(f"{'='*60}")
        print(f"Total: {metrics.total_cases}")
        print(f"Passed: {metrics.passed_cases}")
        print(f"Failed: {metrics.failed_cases}")
        print(f"Pass Rate: {metrics.pass_rate:.1%}")
        print()
        print(f"Grounding Rate: {metrics.grounding_rate:.1%} (target: ≥90%)")
        print(f"Hallucination Rate: {metrics.hallucination_rate:.1%} (target: <10%)")
        print(f"{'='*60}\n")

        # Check targets
        targets_met = (
            metrics.grounding_rate >= 0.9 and
            metrics.hallucination_rate < 0.1
        )

        if targets_met:
            print("✅ All targets met!")
        else:
            print("❌ Some targets not met:")
            if metrics.grounding_rate < 0.9:
                print(f"  - Grounding rate {metrics.grounding_rate:.1%} < 90%")
            if metrics.hallucination_rate >= 0.1:
                print(f"  - Hallucination rate {metrics.hallucination_rate:.1%} >= 10%")

        # Save reports
        output_dir = Path(args.output_dir)
        saved_files = save_report(
            metrics,
            results,
            output_dir,
            args.dataset,
            args.format,
        )

        print()
        print("Reports saved:")
        for path in saved_files:
            print(f"  - {path}")

        # Print markdown report to stdout
        if args.verbose:
            print()
            print(generate_report(metrics, results, dataset.name))

        return 0 if targets_met else 1


if __name__ == "__main__":
    sys.exit(main())
