#!/usr/bin/env python
"""Migration script to re-embed all documents with multilingual model.

This script re-embeds all existing documents using the new multilingual
embedding model (intfloat/multilingual-e5-base). This is necessary when
switching from all-mpnet-base-v2 to support French language.

Usage:
    python scripts/migrate_embeddings.py

The script will:
1. Load all documents from the registry
2. For each document, retrieve the original text
3. Re-chunk the text (in case chunking parameters changed)
4. Generate new embeddings with the multilingual model
5. Delete old vectors from Qdrant
6. Index new vectors in Qdrant
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import get_settings
from src.db.qdrant import QdrantService
from src.db.sqlite import DocumentRegistry
from src.ingestion.chunker import chunk_text
from src.ingestion.parser import extract_text
from src.rag.embeddings import EmbeddingService

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def migrate_document(
    doc_id: str,
    doc_title: str,
    doc_path: Path,
    embedding_service: EmbeddingService,
    qdrant_service: QdrantService,
    settings,
) -> bool:
    """Migrate a single document to new embeddings.

    Args:
        doc_id: Document ID
        doc_title: Document title
        doc_path: Path to original document file
        embedding_service: New embedding service instance
        qdrant_service: Qdrant service instance
        settings: Application settings

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
        text_result = extract_text(doc_path)

        if not text_result.success or not text_result.text:
            logger.error(f"Failed to extract text: {text_result.error}")
            return False

        # 2. Re-chunk text
        logger.info(f"Chunking text ({len(text_result.text)} chars)")
        chunks = await chunk_text(
            text_result.text,
            chunk_size=settings.chunking.size,
            overlap=settings.chunking.overlap,
        )

        if not chunks:
            logger.error("No chunks generated")
            return False

        logger.info(f"Generated {len(chunks)} chunks")

        # 3. Generate new embeddings with multilingual model
        logger.info("Generating embeddings with multilingual model")
        vectors = embedding_service.embed_documents(
            texts=[chunk.content for chunk in chunks],
            batch_size=settings.embeddings.batch_size,
            show_progress=True,
        )

        logger.info(f"Generated {len(vectors)} embeddings")

        # 4. Delete old vectors from Qdrant
        logger.info("Deleting old vectors from Qdrant")
        deleted = await qdrant_service.delete_by_document_id(doc_id)
        logger.info(f"Deleted {deleted} old vectors")

        # 5. Index new vectors
        logger.info("Indexing new vectors in Qdrant")
        await qdrant_service.index_chunks(doc_id, chunks, vectors)

        logger.info(f"Successfully migrated document: {doc_title}")
        return True

    except Exception as e:
        logger.error(f"Failed to migrate document {doc_id}: {e}", exc_info=True)
        return False


async def main():
    """Main migration process."""
    logger.info("=" * 80)
    logger.info("Starting embedding migration to multilingual model")
    logger.info("=" * 80)

    try:
        # Load settings
        settings = get_settings()
        logger.info(f"Using embedding model: {settings.embeddings.model}")
        logger.info(f"Query prefix: '{settings.embeddings.query_prefix}'")
        logger.info(f"Document prefix: '{settings.embeddings.document_prefix}'")

        # Initialize services
        logger.info("Initializing services...")

        embedding_service = EmbeddingService(
            model_name=settings.embeddings.model,
            device=settings.embeddings.device,
            query_prefix=settings.embeddings.query_prefix,
            document_prefix=settings.embeddings.document_prefix,
        )

        qdrant_service = QdrantService()

        # Check Qdrant connection
        if not await qdrant_service.health_check():
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
        documents = registry.list_documents()

        if not documents:
            logger.info("No documents found to migrate.")
            return 0

        logger.info(f"Found {len(documents)} documents to migrate")
        logger.info("=" * 80)

        # Migrate each document
        success_count = 0
        failed_count = 0

        for i, doc in enumerate(documents, 1):
            logger.info(f"\n[{i}/{len(documents)}] Processing: {doc.title}")

            # Construct path to uploaded file
            upload_dir = Path(settings.storage.upload_dir)
            doc_path = upload_dir / doc.filename

            success = await migrate_document(
                doc_id=doc.id,
                doc_title=doc.title,
                doc_path=doc_path,
                embedding_service=embedding_service,
                qdrant_service=qdrant_service,
                settings=settings,
            )

            if success:
                success_count += 1
            else:
                failed_count += 1

        # Summary
        logger.info("=" * 80)
        logger.info("Migration complete!")
        logger.info(f"Successfully migrated: {success_count}/{len(documents)}")
        if failed_count > 0:
            logger.warning(f"Failed to migrate: {failed_count}/{len(documents)}")
        logger.info("=" * 80)

        return 0 if failed_count == 0 else 1

    except Exception as e:
        logger.error(f"Migration failed with error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
