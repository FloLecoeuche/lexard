"""
Dataset loading and management for evaluation.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator, Literal

import yaml


@dataclass
class ExpectedResult:
    """Expected result for a test case."""

    behavior: Literal["answer", "refuse"] | None = None
    answer_contains: list[str] = field(default_factory=list)
    answer_not_contains: list[str] = field(default_factory=list)
    must_have_citations: bool = False
    min_confidence: Literal["low", "medium", "high"] | None = None
    max_confidence: Literal["low", "medium", "high"] | None = None


@dataclass
class TestCase:
    """A single evaluation test case."""

    id: str
    category: str
    question: str
    document: str | None = None
    document_id: str | None = None
    expected: ExpectedResult = field(default_factory=ExpectedResult)
    description: str = ""
    tags: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TestCase":
        """Create TestCase from dictionary."""
        expected_data = data.get("expected", {})
        expected = ExpectedResult(
            behavior=expected_data.get("behavior"),
            answer_contains=expected_data.get("answer_contains", []),
            answer_not_contains=expected_data.get("answer_not_contains", []),
            must_have_citations=expected_data.get("must_have_citations", False),
            min_confidence=expected_data.get("min_confidence"),
            max_confidence=expected_data.get("max_confidence"),
        )

        return cls(
            id=data["id"],
            category=data["category"],
            question=data["question"],
            document=data.get("document"),
            document_id=data.get("document_id"),
            expected=expected,
            description=data.get("description", ""),
            tags=data.get("tags", []),
        )


@dataclass
class EvaluationDataset:
    """A collection of test cases with metadata."""

    name: str
    version: str
    description: str
    test_cases: list[TestCase]
    language: str = "en"  # Default to English

    def __len__(self) -> int:
        return len(self.test_cases)

    def __iter__(self) -> Iterator[TestCase]:
        return iter(self.test_cases)

    def filter_by_category(self, category: str) -> list[TestCase]:
        """Filter test cases by category."""
        return [tc for tc in self.test_cases if tc.category == category]

    def filter_by_tags(self, tags: list[str]) -> list[TestCase]:
        """Filter test cases that have any of the specified tags."""
        return [tc for tc in self.test_cases if any(t in tc.tags for t in tags)]

    def get_categories(self) -> list[str]:
        """Get unique categories in the dataset."""
        return list(set(tc.category for tc in self.test_cases))


class DatasetLoader:
    """Load evaluation datasets from YAML files."""

    def __init__(self, data_dir: Path | str | None = None):
        """
        Initialize dataset loader.

        Args:
            data_dir: Directory containing evaluation datasets.
                     Defaults to data/eval/ relative to project root.
        """
        if data_dir is None:
            # Default to data/eval/ relative to project root
            project_root = Path(__file__).parent.parent.parent
            self.data_dir = project_root / "data" / "eval"
        else:
            self.data_dir = Path(data_dir)

    def load(self, filename: str) -> EvaluationDataset:
        """
        Load a dataset from a YAML file.

        Args:
            filename: Name of the YAML file (with or without extension)

        Returns:
            EvaluationDataset with loaded test cases
        """
        if not filename.endswith((".yaml", ".yml")):
            filename = f"{filename}.yaml"

        filepath = self.data_dir / filename
        if not filepath.exists():
            raise FileNotFoundError(f"Dataset not found: {filepath}")

        with open(filepath) as f:
            data = yaml.safe_load(f)

        metadata = data.get("metadata", {})
        test_cases = [
            TestCase.from_dict(tc) for tc in data.get("test_cases", [])
        ]

        return EvaluationDataset(
            name=metadata.get("name", filename),
            version=metadata.get("version", "1.0"),
            description=metadata.get("description", ""),
            test_cases=test_cases,
            language=metadata.get("language", "en"),
        )

    def load_all(self) -> list[EvaluationDataset]:
        """Load all datasets from the data directory."""
        datasets = []
        for filepath in self.data_dir.glob("*.yaml"):
            if filepath.name.startswith("_"):
                continue  # Skip files starting with underscore
            datasets.append(self.load(filepath.name))
        return datasets

    def list_datasets(self) -> list[str]:
        """List available dataset files."""
        return [
            f.stem
            for f in self.data_dir.glob("*.yaml")
            if not f.name.startswith("_")
        ]
