"""Plain text file extractor."""

from pathlib import Path

from src.rag.extractors.base import BaseExtractor, ExtractedPage, ExtractionResult
from src.rag.normalize import normalize_text


class TXTExtractor(BaseExtractor):
    """Extract text from plain text files.

    Supports UTF-8 and common encodings with fallback.
    """

    SUPPORTED_EXTENSIONS = {".txt", ".text", ".md", ".markdown"}
    ENCODINGS = ["utf-8", "utf-8-sig", "latin-1", "cp1252", "iso-8859-1"]

    def supports(self, file_path: Path) -> bool:
        """Check if file is a plain text file."""
        return file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS

    def extract(self, file_path: Path) -> ExtractionResult:
        """Extract text from plain text file.

        Tries multiple encodings to handle various text files.

        Args:
            file_path: Path to the text file.

        Returns:
            ExtractionResult with extracted text.
        """
        errors: list[str] = []
        content = ""

        for encoding in self.ENCODINGS:
            try:
                content = file_path.read_text(encoding=encoding)
                break
            except UnicodeDecodeError:
                continue
            except Exception as e:
                errors.append(f"Read error with {encoding}: {str(e)}")

        if not content and not errors:
            errors.append("Failed to decode file with any supported encoding")

        normalized_text = normalize_text(content) if content else ""

        pages = [ExtractedPage(page_number=1, content=normalized_text)] if normalized_text else []

        return ExtractionResult(
            filename=file_path.name,
            pages=pages,
            total_pages=1 if pages else 0,
            extraction_errors=errors,
            is_complete=len(errors) == 0 and bool(content),
        )
