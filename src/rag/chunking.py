"""Text chunking with token counting and overlap."""

import hashlib
from dataclasses import dataclass

import tiktoken

from src.rag.extractors.base import ExtractedPage


@dataclass
class Chunk:
    """Represents a text chunk with metadata."""

    content: str
    chunk_index: int
    page: int  # Primary page (where chunk starts)
    pages: list[int]  # All pages this chunk spans
    token_count: int
    content_hash: str  # SHA256 of content for deduplication


class Chunker:
    """Fixed-size text chunker with overlap.

    Splits extracted pages into overlapping chunks of approximately
    chunk_size tokens, with overlap tokens carried over between chunks.
    """

    def __init__(self, chunk_size: int = 512, overlap: int = 50):
        """Initialize chunker.

        Args:
            chunk_size: Target number of tokens per chunk.
            overlap: Number of tokens to overlap between consecutive chunks.
        """
        self.chunk_size = chunk_size
        self.overlap = overlap
        self._tokenizer: tiktoken.Encoding | None = None

    @property
    def tokenizer(self) -> tiktoken.Encoding:
        """Lazy load tokenizer."""
        if self._tokenizer is None:
            self._tokenizer = tiktoken.get_encoding("cl100k_base")
        return self._tokenizer

    def chunk(self, pages: list[ExtractedPage]) -> list[Chunk]:
        """Split pages into overlapping chunks.

        Args:
            pages: List of extracted pages with content and page numbers.

        Returns:
            List of Chunk objects with metadata.
        """
        if not pages:
            return []

        # Build a list of (token, page_number) pairs
        token_page_pairs: list[tuple[int, int]] = []
        for page in pages:
            if not page.content:
                continue
            tokens = self.tokenizer.encode(page.content)
            for token in tokens:
                token_page_pairs.append((token, page.page_number))

        if not token_page_pairs:
            return []

        chunks: list[Chunk] = []
        start_idx = 0
        chunk_index = 0

        while start_idx < len(token_page_pairs):
            # Determine end index for this chunk
            end_idx = min(start_idx + self.chunk_size, len(token_page_pairs))

            # Extract tokens and pages for this chunk
            chunk_tokens = [tp[0] for tp in token_page_pairs[start_idx:end_idx]]
            chunk_pages = [tp[1] for tp in token_page_pairs[start_idx:end_idx]]

            # Decode tokens back to text
            content = self.tokenizer.decode(chunk_tokens)

            # Get unique pages this chunk spans (in order)
            unique_pages = []
            for p in chunk_pages:
                if not unique_pages or unique_pages[-1] != p:
                    unique_pages.append(p)

            # Create chunk
            chunk = Chunk(
                content=content,
                chunk_index=chunk_index,
                page=unique_pages[0],  # Primary page where chunk starts
                pages=unique_pages,
                token_count=len(chunk_tokens),
                content_hash=self._hash_content(content),
            )
            chunks.append(chunk)

            # Move start index, accounting for overlap
            # If we've reached the end, break
            if end_idx >= len(token_page_pairs):
                break

            # Next chunk starts (chunk_size - overlap) tokens after current start
            start_idx = start_idx + self.chunk_size - self.overlap
            chunk_index += 1

        return chunks

    def count_tokens(self, text: str) -> int:
        """Count tokens in text.

        Args:
            text: Text to tokenize.

        Returns:
            Number of tokens.
        """
        return len(self.tokenizer.encode(text))

    def _hash_content(self, content: str) -> str:
        """Generate SHA256 hash of content.

        Args:
            content: Text content to hash.

        Returns:
            Hexadecimal SHA256 hash.
        """
        return hashlib.sha256(content.encode()).hexdigest()
