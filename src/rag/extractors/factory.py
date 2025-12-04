"""Factory for selecting the appropriate document extractor."""

from pathlib import Path

from src.rag.extractors.base import BaseExtractor
from src.rag.extractors.pdf import PDFExtractor
from src.rag.extractors.docx import DOCXExtractor
from src.rag.extractors.txt import TXTExtractor


class UnsupportedFormatError(Exception):
    """Raised when a file format is not supported for extraction."""

    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path
        self.extension = file_path.suffix.lower()
        super().__init__(
            f"Unsupported file format: {self.extension} (file: {file_path.name})"
        )


_EXTRACTORS: list[BaseExtractor] = [
    PDFExtractor(),
    DOCXExtractor(),
    TXTExtractor(),
]


def get_extractor(file_path: Path) -> BaseExtractor:
    """Get the appropriate extractor for a file.

    Args:
        file_path: Path to the document file.

    Returns:
        An extractor instance that can handle the file type.

    Raises:
        UnsupportedFormatError: If no extractor supports the file type.
    """
    file_path = Path(file_path)

    for extractor in _EXTRACTORS:
        if extractor.supports(file_path):
            return extractor

    raise UnsupportedFormatError(file_path)


def get_supported_extensions() -> set[str]:
    """Get all supported file extensions.

    Returns:
        Set of supported file extensions (e.g., {'.pdf', '.docx', '.txt'}).
    """
    extensions: set[str] = set()
    for extractor in _EXTRACTORS:
        if hasattr(extractor, "SUPPORTED_EXTENSIONS"):
            extensions.update(extractor.SUPPORTED_EXTENSIONS)
    return extensions
