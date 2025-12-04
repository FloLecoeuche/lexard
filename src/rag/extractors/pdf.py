"""PDF text extractor using pdfminer.six."""

from pathlib import Path

from pdfminer.high_level import extract_pages
from pdfminer.layout import LAParams, LTTextContainer

from src.rag.extractors.base import BaseExtractor, ExtractedPage, ExtractionResult
from src.rag.normalize import normalize_text


class PDFExtractor(BaseExtractor):
    """Extract text from PDF files using pdfminer.six."""

    SUPPORTED_EXTENSIONS = {".pdf"}

    def __init__(self) -> None:
        self.laparams = LAParams(
            line_margin=0.5,
            word_margin=0.1,
            char_margin=2.0,
            boxes_flow=0.5,
        )

    def supports(self, file_path: Path) -> bool:
        """Check if file is a PDF."""
        return file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS

    def extract(self, file_path: Path) -> ExtractionResult:
        """Extract text from PDF file page by page.

        Args:
            file_path: Path to the PDF file.

        Returns:
            ExtractionResult with pages and extraction metadata.
        """
        pages: list[ExtractedPage] = []
        errors: list[str] = []
        page_number = 0

        try:
            for page_layout in extract_pages(file_path, laparams=self.laparams):
                page_number += 1
                try:
                    page_text = self._extract_page_text(page_layout)
                    normalized_text = normalize_text(page_text)
                    pages.append(ExtractedPage(
                        page_number=page_number,
                        content=normalized_text,
                    ))
                except Exception as e:
                    errors.append(f"Page {page_number}: {str(e)}")
                    pages.append(ExtractedPage(
                        page_number=page_number,
                        content="",
                    ))
        except Exception as e:
            errors.append(f"Document error: {str(e)}")

        return ExtractionResult(
            filename=file_path.name,
            pages=pages,
            total_pages=page_number,
            extraction_errors=errors,
            is_complete=len(errors) == 0,
        )

    def _extract_page_text(self, page_layout) -> str:
        """Extract text from a single page layout.

        Args:
            page_layout: pdfminer page layout object.

        Returns:
            Extracted text from the page.
        """
        text_parts: list[str] = []

        for element in page_layout:
            if isinstance(element, LTTextContainer):
                text_parts.append(element.get_text())

        return "".join(text_parts)
