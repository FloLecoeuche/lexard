"""Document text extractors for PDF, DOCX, and TXT files."""

from src.rag.extractors.base import BaseExtractor, ExtractedPage, ExtractionResult
from src.rag.extractors.factory import get_extractor, UnsupportedFormatError
from src.rag.extractors.pdf import PDFExtractor
from src.rag.extractors.docx import DOCXExtractor
from src.rag.extractors.txt import TXTExtractor

__all__ = [
    "BaseExtractor",
    "ExtractedPage",
    "ExtractionResult",
    "get_extractor",
    "UnsupportedFormatError",
    "PDFExtractor",
    "DOCXExtractor",
    "TXTExtractor",
]
