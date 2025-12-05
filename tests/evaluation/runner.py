"""
Evaluation pipeline runner.
"""

import logging
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx

from .dataset import DatasetLoader, EvaluationDataset, TestCase
from .metrics import EvaluationMetrics, TestResult, calculate_metrics

logger = logging.getLogger(__name__)


class EvaluationRunner:
    """Run evaluation test cases against the API."""

    def __init__(
        self,
        api_url: str = "http://localhost:8000",
        timeout: float = 60.0,
    ):
        """
        Initialize evaluation runner.

        Args:
            api_url: Base URL for the Lexard API
            timeout: Request timeout in seconds
        """
        self.api_url = api_url.rstrip("/")
        self.timeout = timeout
        self.client = httpx.Client(timeout=timeout)
        self.loader = DatasetLoader()

    def __enter__(self) -> "EvaluationRunner":
        return self

    def __exit__(self, *args: Any) -> None:
        self.client.close()

    def check_api_health(self) -> bool:
        """Check if the API is available."""
        try:
            response = self.client.get(f"{self.api_url}/health")
            return response.status_code == 200
        except httpx.RequestError:
            return False

    def run_test_case(
        self,
        case: TestCase,
        document_id: str | None = None,
    ) -> TestResult:
        """
        Run a single test case and return results.

        Args:
            case: Test case to run
            document_id: Override document ID (if document needs to be uploaded first)

        Returns:
            TestResult with evaluation outcome
        """
        doc_id = document_id or case.document_id

        if not doc_id:
            return TestResult(
                case_id=case.id,
                category=case.category,
                passed=False,
                expected_behavior=case.expected.behavior,
                actual_behavior=None,
                has_citations=False,
                citation_count=0,
                confidence=None,
                hallucination_flagged=False,
                error="No document_id provided",
            )

        try:
            response = self.client.post(
                f"{self.api_url}/query",
                json={
                    "document_id": doc_id,
                    "question": case.question,
                },
            )

            if response.status_code != 200:
                return TestResult(
                    case_id=case.id,
                    category=case.category,
                    passed=False,
                    expected_behavior=case.expected.behavior,
                    actual_behavior=None,
                    has_citations=False,
                    citation_count=0,
                    confidence=None,
                    hallucination_flagged=False,
                    error=f"API error: {response.status_code}",
                    details={"response": response.text},
                )

            data = response.json()
            return self._evaluate_response(case, data)

        except httpx.RequestError as e:
            return TestResult(
                case_id=case.id,
                category=case.category,
                passed=False,
                expected_behavior=case.expected.behavior,
                actual_behavior=None,
                has_citations=False,
                citation_count=0,
                confidence=None,
                hallucination_flagged=False,
                error=f"Request failed: {e}",
            )

    def _evaluate_response(
        self,
        case: TestCase,
        response: dict[str, Any],
    ) -> TestResult:
        """Evaluate API response against expected results."""
        answer = response.get("answer", "")
        citations = response.get("citations", [])
        confidence = response.get("confidence")
        hallucination_flagged = response.get("hallucination_flagged", False)

        # Determine actual behavior
        refusal_indicators = [
            "cannot find",
            "no information",
            "not mentioned",
            "unable to find",
            "don't have",
            "not available",
            "outside the scope",
        ]
        is_refusal = any(
            indicator in answer.lower() for indicator in refusal_indicators
        )
        actual_behavior = "refuse" if is_refusal else "answer"

        # Check expectations
        passed = True
        failure_reasons: list[str] = []

        # Check behavior
        if case.expected.behavior:
            if case.expected.behavior != actual_behavior:
                passed = False
                failure_reasons.append(
                    f"Expected behavior '{case.expected.behavior}', "
                    f"got '{actual_behavior}'"
                )

        # Check answer_contains
        if case.expected.answer_contains and actual_behavior == "answer":
            answer_lower = answer.lower()
            for expected_text in case.expected.answer_contains:
                if expected_text.lower() not in answer_lower:
                    passed = False
                    failure_reasons.append(
                        f"Answer missing expected text: '{expected_text}'"
                    )

        # Check answer_not_contains
        if case.expected.answer_not_contains:
            answer_lower = answer.lower()
            for forbidden_text in case.expected.answer_not_contains:
                if forbidden_text.lower() in answer_lower:
                    passed = False
                    failure_reasons.append(
                        f"Answer contains forbidden text: '{forbidden_text}'"
                    )

        # Check citations
        if case.expected.must_have_citations:
            if not citations:
                passed = False
                failure_reasons.append("Expected citations but none found")

        # Check confidence
        confidence_order = {"low": 1, "medium": 2, "high": 3}
        if case.expected.min_confidence and confidence:
            min_level = confidence_order.get(case.expected.min_confidence, 0)
            actual_level = confidence_order.get(confidence, 0)
            if actual_level < min_level:
                passed = False
                failure_reasons.append(
                    f"Confidence {confidence} below minimum {case.expected.min_confidence}"
                )

        if case.expected.max_confidence and confidence:
            max_level = confidence_order.get(case.expected.max_confidence, 3)
            actual_level = confidence_order.get(confidence, 0)
            if actual_level > max_level:
                passed = False
                failure_reasons.append(
                    f"Confidence {confidence} above maximum {case.expected.max_confidence}"
                )

        return TestResult(
            case_id=case.id,
            category=case.category,
            passed=passed,
            expected_behavior=case.expected.behavior,
            actual_behavior=actual_behavior,
            has_citations=bool(citations),
            citation_count=len(citations),
            confidence=confidence,
            hallucination_flagged=hallucination_flagged,
            error="; ".join(failure_reasons) if failure_reasons else None,
            details={
                "expected_citations": case.expected.must_have_citations,
                "answer_preview": answer[:200] if answer else None,
                "response": response,
            },
        )

    def run_dataset(
        self,
        dataset: EvaluationDataset,
        document_map: dict[str, str] | None = None,
    ) -> tuple[list[TestResult], EvaluationMetrics]:
        """
        Run all test cases in a dataset.

        Args:
            dataset: Dataset to evaluate
            document_map: Mapping from document filename to document_id

        Returns:
            Tuple of (results list, computed metrics)
        """
        results: list[TestResult] = []
        document_map = document_map or {}

        logger.info(f"Running evaluation: {dataset.name}")
        logger.info(f"Total test cases: {len(dataset)}")

        for i, case in enumerate(dataset):
            logger.info(f"Running test case {i + 1}/{len(dataset)}: {case.id}")

            # Resolve document_id from map if needed
            doc_id = case.document_id
            if case.document and case.document in document_map:
                doc_id = document_map[case.document]

            result = self.run_test_case(case, doc_id)
            results.append(result)

            status = "PASS" if result.passed else "FAIL"
            logger.info(f"  [{status}] {case.id}: {result.error or 'OK'}")

        metrics = calculate_metrics(results)
        return results, metrics

    def run_from_file(
        self,
        filename: str,
        document_map: dict[str, str] | None = None,
    ) -> tuple[list[TestResult], EvaluationMetrics]:
        """
        Load and run a dataset from file.

        Args:
            filename: Name of the dataset file
            document_map: Mapping from document filename to document_id

        Returns:
            Tuple of (results list, computed metrics)
        """
        dataset = self.loader.load(filename)
        return self.run_dataset(dataset, document_map)

    def upload_test_document(self, filepath: Path | str) -> str | None:
        """
        Upload a test document and return its ID.

        Args:
            filepath: Path to the document file

        Returns:
            Document ID if successful, None otherwise
        """
        filepath = Path(filepath)
        if not filepath.exists():
            logger.error(f"Document not found: {filepath}")
            return None

        try:
            with open(filepath, "rb") as f:
                response = self.client.post(
                    f"{self.api_url}/upload",
                    files={"file": (filepath.name, f)},
                )

            if response.status_code == 200:
                data = response.json()
                return data.get("document_id")
            else:
                logger.error(f"Upload failed: {response.status_code}")
                return None

        except httpx.RequestError as e:
            logger.error(f"Upload request failed: {e}")
            return None


def run_evaluation(
    dataset_name: str = "contract_qa",
    api_url: str = "http://localhost:8000",
    document_map: dict[str, str] | None = None,
) -> tuple[list[TestResult], EvaluationMetrics]:
    """
    Convenience function to run an evaluation.

    Args:
        dataset_name: Name of the dataset file (without extension)
        api_url: Base URL for the API
        document_map: Mapping from document filename to document_id

    Returns:
        Tuple of (results list, computed metrics)
    """
    with EvaluationRunner(api_url=api_url) as runner:
        if not runner.check_api_health():
            raise RuntimeError(f"API not available at {api_url}")

        return runner.run_from_file(dataset_name, document_map)
