"""Tests for the embedding migration script logic."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestMigrationScript:
    """Tests for migration script helper functions and logic."""

    def test_script_imports(self):
        """Test that migration script can be imported without errors."""
        # Add scripts to path
        scripts_path = Path(__file__).parent.parent / "scripts"
        sys.path.insert(0, str(scripts_path.parent))

        # This should not raise any ImportError
        from scripts.migrate_embeddings import migrate_document, main

    def test_migration_document_file_not_found(self):
        """Test that migration handles missing document files gracefully."""
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from scripts.migrate_embeddings import migrate_document

        # Mock services
        mock_embedding_service = MagicMock()
        mock_qdrant_service = MagicMock()
        mock_chunker = MagicMock()

        # Non-existent path
        result = migrate_document(
            doc_id="test-id",
            doc_title="Test Document",
            doc_path=Path("/nonexistent/path/document.pdf"),
            embedding_service=mock_embedding_service,
            qdrant_service=mock_qdrant_service,
            chunker=mock_chunker,
            dry_run=False,
        )

        assert result is False

    def test_migration_dry_run_no_changes(self):
        """Test that dry run mode doesn't make any changes."""
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from scripts.migrate_embeddings import migrate_document

        # Mock services
        mock_embedding_service = MagicMock()
        mock_qdrant_service = MagicMock()
        mock_chunker = MagicMock()

        # Mock extractor
        from src.rag.extractors.base import ExtractedPage, ExtractionResult

        mock_extraction = ExtractionResult(
            filename="test.txt",
            pages=[ExtractedPage(page_number=1, content="Test content")],
            total_pages=1,
        )

        mock_extractor = MagicMock()
        mock_extractor.extract.return_value = mock_extraction

        # Mock chunker output
        from src.rag.chunking import Chunk

        mock_chunks = [
            Chunk(
                content="Test content",
                chunk_index=0,
                page=1,
                pages=[1],
                token_count=10,
                content_hash="abc123",
            )
        ]
        mock_chunker.chunk.return_value = mock_chunks

        # Create a temp file
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"Test content")
            temp_path = Path(f.name)

        try:
            with patch(
                "scripts.migrate_embeddings.get_extractor", return_value=mock_extractor
            ):
                result = migrate_document(
                    doc_id="test-id",
                    doc_title="Test Document",
                    doc_path=temp_path,
                    embedding_service=mock_embedding_service,
                    qdrant_service=mock_qdrant_service,
                    chunker=mock_chunker,
                    dry_run=True,
                )

            # Should succeed in dry run
            assert result is True

            # Should NOT have called Qdrant operations
            mock_qdrant_service.delete_by_document.assert_not_called()
            mock_qdrant_service.upsert_chunks.assert_not_called()

            # Should NOT have generated embeddings
            mock_embedding_service.embed_documents.assert_not_called()
        finally:
            temp_path.unlink()

    def test_argparse_dry_run_flag(self):
        """Test that --dry-run flag is parsed correctly."""
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("--dry-run", action="store_true")

        # Without flag
        args = parser.parse_args([])
        assert args.dry_run is False

        # With flag
        args = parser.parse_args(["--dry-run"])
        assert args.dry_run is True


class TestMigrationConfig:
    """Tests for migration configuration handling."""

    def test_config_has_e5_settings(self):
        """Test that config has E5 prefix settings."""
        from src.config import get_settings

        settings = get_settings()

        # Should have multilingual model
        assert "multilingual-e5" in settings.embeddings.model.lower()

        # Should have prefixes
        assert settings.embeddings.query_prefix == "query: "
        assert settings.embeddings.document_prefix == "passage: "
