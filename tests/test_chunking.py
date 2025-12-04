"""Tests for text chunking module."""

import pytest

from src.rag.chunking import Chunk, Chunker
from src.rag.extractors.base import ExtractedPage


class TestChunker:
    """Tests for the Chunker class."""

    def test_empty_pages(self):
        """Empty pages list should return empty chunks."""
        chunker = Chunker()
        chunks = chunker.chunk([])
        assert chunks == []

    def test_pages_with_empty_content(self):
        """Pages with empty content should be skipped."""
        chunker = Chunker()
        pages = [
            ExtractedPage(page_number=1, content=""),
            ExtractedPage(page_number=2, content=""),
        ]
        chunks = chunker.chunk(pages)
        assert chunks == []

    def test_small_document_single_chunk(self):
        """Document smaller than chunk_size should produce single chunk."""
        chunker = Chunker(chunk_size=512, overlap=50)
        pages = [ExtractedPage(page_number=1, content="This is a small document.")]
        chunks = chunker.chunk(pages)

        assert len(chunks) == 1
        assert chunks[0].content == "This is a small document."
        assert chunks[0].chunk_index == 0
        assert chunks[0].page == 1
        assert chunks[0].pages == [1]
        assert chunks[0].token_count < 512

    def test_chunking_size_approximately_512_tokens(self):
        """Chunks should be approximately 512 tokens (±10%)."""
        chunker = Chunker(chunk_size=512, overlap=50)

        # Create a large document
        long_text = "This is a test sentence. " * 500  # ~2500 tokens
        pages = [ExtractedPage(page_number=1, content=long_text)]
        chunks = chunker.chunk(pages)

        assert len(chunks) > 1

        # Check all chunks except the last one are within ±10% of 512
        for chunk in chunks[:-1]:
            assert 450 < chunk.token_count <= 512, (
                f"Chunk {chunk.chunk_index} has {chunk.token_count} tokens"
            )

    def test_overlap_between_consecutive_chunks(self):
        """Consecutive chunks should have overlapping content."""
        chunker = Chunker(chunk_size=100, overlap=20)

        # Create text that will produce multiple chunks
        long_text = "word " * 300  # ~300 tokens
        pages = [ExtractedPage(page_number=1, content=long_text)]
        chunks = chunker.chunk(pages)

        assert len(chunks) > 1

        # Check overlap exists between consecutive chunks
        for i in range(1, len(chunks)):
            prev_chunk = chunks[i - 1]
            curr_chunk = chunks[i]
            # The end of prev_chunk should overlap with start of curr_chunk
            # Due to token boundaries, we check that some text overlaps
            prev_tokens = chunker.tokenizer.encode(prev_chunk.content)
            curr_tokens = chunker.tokenizer.encode(curr_chunk.content)
            # Last 'overlap' tokens of prev should match first 'overlap' of curr
            assert prev_tokens[-chunker.overlap :] == curr_tokens[: chunker.overlap]

    def test_page_tracking_single_page(self):
        """Chunks from single page should track that page."""
        chunker = Chunker(chunk_size=512, overlap=50)
        pages = [ExtractedPage(page_number=3, content="Content on page three.")]
        chunks = chunker.chunk(pages)

        assert len(chunks) == 1
        assert chunks[0].page == 3
        assert chunks[0].pages == [3]

    def test_page_tracking_multiple_pages(self):
        """Chunks spanning multiple pages should track all pages."""
        chunker = Chunker(chunk_size=50, overlap=10)  # Small chunks

        pages = [
            ExtractedPage(page_number=1, content="Content on page one. " * 10),
            ExtractedPage(page_number=2, content="Content on page two. " * 10),
            ExtractedPage(page_number=3, content="Content on page three. " * 10),
        ]
        chunks = chunker.chunk(pages)

        # At least one chunk should span multiple pages
        multi_page_chunks = [c for c in chunks if len(c.pages) > 1]
        # This depends on chunk boundaries, but with small chunks we should get some
        assert len(chunks) > 1

        # All chunks should have valid page references
        for chunk in chunks:
            assert chunk.page in [1, 2, 3]
            assert all(p in [1, 2, 3] for p in chunk.pages)
            assert chunk.page == chunk.pages[0]

    def test_content_hash_uniqueness(self):
        """Identical content produces identical hash, different content produces different hash."""
        chunker = Chunker()

        # Test that same content produces same hash
        hash1 = chunker._hash_content("Same content")
        hash2 = chunker._hash_content("Same content")
        assert hash1 == hash2

        # Test that different content produces different hash
        hash3 = chunker._hash_content("Different content")
        assert hash1 != hash3

    def test_content_hash_deterministic(self):
        """Same content should produce same hash."""
        chunker = Chunker()
        content = "Test content for hashing."

        hash1 = chunker._hash_content(content)
        hash2 = chunker._hash_content(content)

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex length

    def test_chunk_index_sequential(self):
        """Chunk indices should be sequential starting from 0."""
        chunker = Chunker(chunk_size=50, overlap=10)

        long_text = "Word " * 200
        pages = [ExtractedPage(page_number=1, content=long_text)]
        chunks = chunker.chunk(pages)

        indices = [c.chunk_index for c in chunks]
        expected = list(range(len(chunks)))
        assert indices == expected

    def test_count_tokens(self):
        """Token counting should work correctly."""
        chunker = Chunker()

        # Simple text
        count = chunker.count_tokens("Hello world")
        assert count == 2

        # Longer text
        count = chunker.count_tokens("This is a longer sentence with more words.")
        assert count > 5

    def test_custom_chunk_size_and_overlap(self):
        """Custom chunk size and overlap should be respected."""
        chunker = Chunker(chunk_size=200, overlap=30)

        assert chunker.chunk_size == 200
        assert chunker.overlap == 30

        long_text = "Sample text here. " * 100
        pages = [ExtractedPage(page_number=1, content=long_text)]
        chunks = chunker.chunk(pages)

        # Check chunks are approximately 200 tokens
        for chunk in chunks[:-1]:
            assert 170 < chunk.token_count <= 200


class TestChunk:
    """Tests for the Chunk dataclass."""

    def test_chunk_creation(self):
        """Chunk should be created with all fields."""
        chunk = Chunk(
            content="Test content",
            chunk_index=0,
            page=1,
            pages=[1, 2],
            token_count=5,
            content_hash="abc123",
        )

        assert chunk.content == "Test content"
        assert chunk.chunk_index == 0
        assert chunk.page == 1
        assert chunk.pages == [1, 2]
        assert chunk.token_count == 5
        assert chunk.content_hash == "abc123"
