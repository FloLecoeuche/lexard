"""DOCX text extractor using python-docx."""

from pathlib import Path
from xml.etree import ElementTree as ET

from docx import Document
from docx.oxml.ns import qn

from src.rag.extractors.base import BaseExtractor, ExtractedPage, ExtractionResult
from src.rag.normalize import normalize_text


class DOCXExtractor(BaseExtractor):
    """Extract text from DOCX files using python-docx.

    Detects page breaks (both explicit and section breaks) to split content
    into logical pages.
    """

    SUPPORTED_EXTENSIONS = {".docx"}

    # XML namespaces used in OOXML
    PAGE_BREAK_TAG = qn("w:br")
    SECTION_PROPS_TAG = qn("w:sectPr")

    def supports(self, file_path: Path) -> bool:
        """Check if file is a DOCX."""
        return file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS

    def extract(self, file_path: Path) -> ExtractionResult:
        """Extract text from DOCX file with page break detection.

        Args:
            file_path: Path to the DOCX file.

        Returns:
            ExtractionResult with extracted text split by pages.
        """
        errors: list[str] = []

        try:
            doc = Document(file_path)
            pages: list[list[str]] = [[]]  # List of pages, each page is list of text parts
            current_page = 0

            # Process paragraphs with page break detection
            for para in doc.paragraphs:
                # Check for page breaks within the paragraph
                has_page_break = self._has_page_break(para)

                if para.text.strip():
                    pages[current_page].append(para.text)

                if has_page_break:
                    current_page += 1
                    pages.append([])

            # Process tables (add to current page context)
            for table in doc.tables:
                for row in table.rows:
                    row_text = " | ".join(
                        cell.text.strip() for cell in row.cells if cell.text.strip()
                    )
                    if row_text:
                        # Tables are added to the last page
                        if pages:
                            pages[-1].append(row_text)

            # Convert to ExtractedPage objects
            extracted_pages: list[ExtractedPage] = []
            for i, page_parts in enumerate(pages):
                if page_parts:  # Skip empty pages
                    content = "\n".join(page_parts)
                    normalized_content = normalize_text(content)
                    if normalized_content:  # Only add non-empty pages
                        extracted_pages.append(ExtractedPage(
                            page_number=len(extracted_pages) + 1,
                            content=normalized_content,
                        ))

            # Ensure at least one page if we have content
            if not extracted_pages and any(pages):
                all_content = "\n".join(
                    part for page in pages for part in page
                )
                normalized = normalize_text(all_content)
                if normalized:
                    extracted_pages.append(ExtractedPage(
                        page_number=1,
                        content=normalized,
                    ))

            return ExtractionResult(
                filename=file_path.name,
                pages=extracted_pages,
                total_pages=len(extracted_pages),
                extraction_errors=errors,
                is_complete=True,
            )

        except Exception as e:
            errors.append(f"Document error: {str(e)}")
            return ExtractionResult(
                filename=file_path.name,
                pages=[],
                total_pages=0,
                extraction_errors=errors,
                is_complete=False,
            )

    def _has_page_break(self, paragraph) -> bool:
        """Check if paragraph contains a page break.

        Args:
            paragraph: python-docx paragraph object.

        Returns:
            True if paragraph contains a page break.
        """
        # Check for explicit page breaks (w:br with w:type="page")
        for run in paragraph.runs:
            for child in run._element:
                if child.tag == self.PAGE_BREAK_TAG:
                    break_type = child.get(qn("w:type"))
                    if break_type == "page":
                        return True

        # Check for section breaks (which also create new pages)
        p_elem = paragraph._element
        for child in p_elem:
            if child.tag == qn("w:pPr"):  # Paragraph properties
                for prop in child:
                    if prop.tag == self.SECTION_PROPS_TAG:
                        return True

        return False
