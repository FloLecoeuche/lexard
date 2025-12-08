#!/usr/bin/env python
"""Migration script to re-embed all documents with multilingual model.

This script re-embeds all existing documents using the new multilingual
embedding model (intfloat/multilingual-e5-base). This is necessary when
switching from all-mpnet-base-v2 to support French language.

Usage:
    python scripts/migrate_embeddings.py [--dry-run]

Options:
    --dry-run    Show what would be migrated without making changes

The script will:
1. Load all documents from the registry
2. For each document, retrieve the original text
3. Re-chunk the text (in case chunking parameters changed)
4. Generate new embeddings with the multilingual model
5. Delete old vectors from Qdrant
6. Index new vectors in Qdrant
"""

import argparse
import logging
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import get_settings
from src.db.qdrant import QdrantService
from src.db.sqlite import DocumentRegistry
from src.rag.chunking import Chunker
from src.rag.embeddings import EmbeddingService
from src.rag.extractors.factory import get_extractor, UnsupportedFormatError

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def migrate_document(
    doc_id: str,
    doc_title: str,
    doc_path: Path,
    embedding_service: EmbeddingService,
    qdrant_service: QdrantService,
    chunker: Chunker,
    dry_run: bool = False,
) -> bool:
    """Migrate a single document to new embeddings.

    Args:
        doc_id: Document ID
        doc_title: Document title
        doc_path: Path to original document file
        embedding_service: New embedding service instance
        qdrant_service: Qdrant service instance
        chunker: Chunker instance
        dry_run: If True, don't make any changes

    Returns:
        True if migration successful, False otherwise
    """
    try:
        logger.info(f"Migrating document: {doc_title} (ID: {doc_id})")

        # 1. Extract text from original file
        if not doc_path.exists():
            logger.error(f"Document file not found: {doc_path}")
            return False

        logger.info(f"Extracting text from: {doc_path}")
        try:
            extractor = get_extractor(doc_path)
            extraction_result = extractor.extract(doc_path)
        except UnsupportedFormatError as e:
            logger.error(f"Unsupported file format: {e}")
            return False

        if not extraction_result.pages:
            logger.error("Failed to extract text: no pages extracted")
            return False

        # 2. Re-chunk text
        full_text_len = len(extraction_result.full_text)
        logger.info(f"Chunking text ({full_text_len} chars)")
        chunks = chunker.chunk(extraction_result.pages)

        if not chunks:
            logger.error("No chunks generated")
            return False

        logger.info(f"Generated {len(chunks)} chunks")

        if dry_run:
            logger.info(f"[DRY RUN] Would re-embed {len(chunks)} chunks")
            return True

        # 3. Generate new embeddings with multilingual model
        logger.info("Generating embeddings with multilingual model")
        vectors = embedding_service.embed_documents(
            texts=[chunk.content for chunk in chunks],
            batch_size=32,
            show_progress=True,
        )

        logger.info(f"Generated {len(vectors)} embeddings")

        # 4. Delete old vectors from Qdrant
        logger.info("Deleting old vectors from Qdrant")
        deleted = qdrant_service.delete_by_document(doc_id)
        logger.info(f"Deleted {deleted} old vectors")

        # 5. Index new vectors
        logger.info("Indexing new vectors in Qdrant")
        inserted = qdrant_service.upsert_chunks(
            chunks=chunks,
            embeddings=vectors,
            document_id=doc_id,
            source_title=doc_title,
            deduplicate=False,  # We just deleted everything
        )

        logger.info(f"Inserted {inserted} vectors")
        logger.info(f"Successfully migrated document: {doc_title}")
        return True

    except Exception as e:
        logger.error(f"Failed to migrate document {doc_id}: {e}", exc_info=True)
        return False


def main():
    """Main migration process."""
    parser = argparse.ArgumentParser(
        description="Migrate embeddings to multilingual model"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be migrated without making changes",
    )
    args = parser.parse_args()

    dry_run = args.dry_run

    logger.info("=" * 80)
    logger.info("Starting embedding migration to multilingual model")
    if dry_run:
        logger.info("[DRY RUN MODE] No changes will be made")
    logger.info("=" * 80)

    try:
        # Load settings
        settings = get_settings()
        logger.info(f"Using embedding model: {settings.embeddings.model}")

        # Get prefix settings safely
        query_prefix = getattr(settings.embeddings, 'query_prefix', '')
        document_prefix = getattr(settings.embeddings, 'document_prefix', '')
        logger.info(f"Query prefix: '{query_prefix}'")
        logger.info(f"Document prefix: '{document_prefix}'")

        # Initialize services
        logger.info("Initializing services...")

        embedding_service = EmbeddingService(
            model_name=settings.embeddings.model,
            device=settings.embeddings.device,
            query_prefix=query_prefix,
            document_prefix=document_prefix,
        )

        qdrant_service = QdrantService()

        chunker = Chunker(
            chunk_size=settings.chunking.size,
            overlap=settings.chunking.overlap,
        )

        # Check Qdrant connection
        if not dry_run:
            if not qdrant_service.health_check():
                logger.error("Qdrant service is not available. Please start Qdrant first.")
                return 1

        # Initialize document registry
        registry_path = "data/lexard.db"
        if not Path(registry_path).exists():
            logger.error(f"Document registry not found at: {registry_path}")
            logger.error("No documents to migrate.")
            return 0

        registry = DocumentRegistry(registry_path)

        # Get all documents
        documents = registry.list_all()

        if not documents:
            logger.info("No documents found to migrate.")
            return 0

        # Filter to only processed documents
        processed_docs = [d for d in documents if d.status == "processed"]

        if not processed_docs:
            logger.info("No processed documents found to migrate.")
            return 0

        logger.info(f"Found {len(processed_docs)} documents to migrate")
        logger.info("=" * 80)

        # Migrate each document
        success_count = 0
        failed_count = 0
        skipped_count = 0

        for i, doc in enumerate(processed_docs, 1):
            logger.info(f"\n[{i}/{len(processed_docs)}] Processing: {doc.title}")

            # Construct path to uploaded file
            upload_dir = Path(settings.storage.upload_dir)
            doc_path = upload_dir / doc.filename

            if not doc_path.exists():
                logger.warning(f"Skipping - file not found: {doc_path}")
                skipped_count += 1
                continue

            success = migrate_document(
                doc_id=doc.id,
                doc_title=doc.title,
                doc_path=doc_path,
                embedding_service=embedding_service,
                qdrant_service=qdrant_service,
                chunker=chunker,
                dry_run=dry_run,
            )

            if success:
                success_count += 1
            else:
                failed_count += 1

        # Summary
        logger.info("=" * 80)
        logger.info("Migration complete!")
        logger.info(f"Successfully migrated: {success_count}/{len(processed_docs)}")
        if skipped_count > 0:
            logger.warning(f"Skipped (file not found): {skipped_count}/{len(processed_docs)}")
        if failed_count > 0:
            logger.warning(f"Failed to migrate: {failed_count}/{len(processed_docs)}")
        logger.info("=" * 80)

        return 0 if failed_count == 0 else 1

    except Exception as e:
        logger.error(f"Migration failed with error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
