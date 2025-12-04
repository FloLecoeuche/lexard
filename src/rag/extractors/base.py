"""Base extractor interface and data classes."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ExtractedPage:
    """Represents a single extracted page from a document."""

    page_number: int
    content: str


@dataclass
class ExtractionResult:
    """Result of text extraction from a document."""

    filename: str
    pages: list[ExtractedPage]
    total_pages: int
    extraction_errors: list[str] = field(default_factory=list)
    is_complete: bool = True

    @property
    def full_text(self) -> str:
        """Concatenate all page content."""
        return "\n\n".join(page.content for page in self.pages if page.content)


class BaseExtractor(ABC):
    """Abstract base class for document text extractors."""

    @abstractmethod
    def extract(self, file_path: Path) -> ExtractionResult:
        """Extract text from document.

        Args:
            file_path: Path to the document file.

        Returns:
            ExtractionResult containing pages and metadata.
        """
        pass

    @abstractmethod
    def supports(self, file_path: Path) -> bool:
        """Check if extractor supports this file type.

        Args:
            file_path: Path to the document file.

        Returns:
            True if this extractor can handle the file type.
        """
        pass
