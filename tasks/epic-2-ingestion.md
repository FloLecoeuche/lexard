# Epic 2: Ingestion Pipeline

## Overview

Implement the document ingestion pipeline that extracts text from documents, chunks them, generates embeddings, and stores them in Qdrant with metadata tracking in SQLite.

## Prerequisites

- Epic 1 completed (Foundation)
- Docker services running (Qdrant, Ollama)
- Configuration management working

## Architecture

```
Document (PDF/DOCX/TXT)
    ↓
Text Extraction (pdfminer/python-docx)
    ↓
Normalization (unicode, whitespace)
    ↓
Chunking (512 tokens, 50 overlap)
    ↓
Embedding Generation (sentence-transformers)
    ↓
Storage (Qdrant vectors + SQLite metadata)
```

## User Stories

---

## US 2.1: Text Extraction

**Status:** 🔲 Not Started

### Description

Implement text extraction from PDF, DOCX, and TXT files with proper error handling and page tracking.

### Context

Documents uploaded to Lexard need text extraction before processing. The extraction must:

- Preserve page boundaries for citation tracking
- Handle encoding issues gracefully
- Report extraction errors without crashing

### Tasks

- [ ] Create `src/rag/extractors/__init__.py`
- [ ] Create `src/rag/extractors/base.py` with abstract extractor interface
- [ ] Create `src/rag/extractors/pdf.py` using pdfminer.six
- [ ] Create `src/rag/extractors/docx.py` using python-docx
- [ ] Create `src/rag/extractors/txt.py` for plain text
- [ ] Create `src/rag/extractors/factory.py` for extractor selection
- [ ] Add text normalization (unicode NFKC, whitespace cleanup)

### Extractor Interface

```python
# src/rag/extractors/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

@dataclass
class ExtractedPage:
    page_number: int
    content: str

@dataclass
class ExtractionResult:
    filename: str
    pages: list[ExtractedPage]
    total_pages: int
    extraction_errors: list[str]  # Non-fatal errors
    is_complete: bool  # False if some pages failed

class BaseExtractor(ABC):
    @abstractmethod
    def extract(self, file_path: Path) -> ExtractionResult:
        """Extract text from document."""
        pass

    @abstractmethod
    def supports(self, file_path: Path) -> bool:
        """Check if extractor supports this file type."""
        pass
```

### PDF Extractor

```python
# src/rag/extractors/pdf.py
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer

class PDFExtractor(BaseExtractor):
    def extract(self, file_path: Path) -> ExtractionResult:
        # Extract text page by page
        # Handle extraction errors per page
        # Return ExtractionResult with page content
        pass
```

### Text Normalization

```python
import unicodedata
import re

def normalize_text(text: str) -> str:
    """Normalize extracted text."""
    # Unicode NFKC normalization
    text = unicodedata.normalize("NFKC", text)
    # Replace multiple whitespace with single space
    text = re.sub(r'\s+', ' ', text)
    # Strip leading/trailing whitespace
    text = text.strip()
    return text
```

### Acceptance Criteria

- [ ] PDF extraction returns text with page numbers
- [ ] DOCX extraction works for standard Word documents
- [ ] TXT extraction handles UTF-8 and common encodings
- [ ] Extraction errors are captured but don't crash the process
- [ ] Text is normalized (unicode, whitespace)
- [ ] Factory selects correct extractor by file extension

### Files to Create

1. `src/rag/__init__.py`
2. `src/rag/extractors/__init__.py`
3. `src/rag/extractors/base.py`
4. `src/rag/extractors/pdf.py`
5. `src/rag/extractors/docx.py`
6. `src/rag/extractors/txt.py`
7. `src/rag/extractors/factory.py`
8. `src/rag/normalize.py`

### Test Cases

```python
# tests/test_extractors.py
def test_pdf_extraction():
    result = PDFExtractor().extract(Path("tests/fixtures/sample.pdf"))
    assert result.total_pages > 0
    assert all(p.content for p in result.pages)

def test_unsupported_file():
    with pytest.raises(UnsupportedFormatError):
        get_extractor(Path("file.xyz"))
```

---

## US 2.2: Chunking

**Status:** 🔲 Not Started

### Description

Implement fixed-size text chunking with token counting and overlap for context preservation.

### Context

Chunking strategy from PRD:

- **Method:** Fixed-size
- **Size:** 512 tokens
- **Overlap:** 50 tokens
- Each chunk needs metadata: page, chunk_index, content_hash

### Tasks

- [ ] Create `src/rag/chunking.py`
- [ ] Implement token counting using tiktoken (cl100k_base encoding)
- [ ] Implement fixed-size chunker with overlap
- [ ] Generate chunk metadata (page tracking, index, hash)
- [ ] Handle edge cases (small documents, page boundaries)

### Chunker Interface

```python
# src/rag/chunking.py
from dataclasses import dataclass
import hashlib
import tiktoken

@dataclass
class Chunk:
    content: str
    chunk_index: int
    page: int  # Primary page (where chunk starts)
    pages: list[int]  # All pages this chunk spans
    token_count: int
    content_hash: str  # SHA256 of content for deduplication

class Chunker:
    def __init__(self, chunk_size: int = 512, overlap: int = 50):
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.tokenizer = tiktoken.get_encoding("cl100k_base")

    def chunk(self, pages: list[ExtractedPage]) -> list[Chunk]:
        """Split pages into overlapping chunks."""
        pass

    def _count_tokens(self, text: str) -> int:
        return len(self.tokenizer.encode(text))

    def _hash_content(self, content: str) -> str:
        return hashlib.sha256(content.encode()).hexdigest()
```

### Chunking Algorithm

1. Concatenate all page content with page markers
2. Split into sentences (preserve natural boundaries)
3. Accumulate sentences until reaching chunk_size tokens
4. When chunk is full:
   - Save chunk with metadata
   - Start new chunk with overlap tokens from previous
5. Track which pages each chunk spans

### Edge Cases

- Document smaller than chunk_size → single chunk
- Page boundary in middle of chunk → track all pages
- Empty pages → skip but maintain page numbering
- Very long sentences → split at token boundary

### Acceptance Criteria

- [ ] Chunks are approximately 512 tokens (±10%)
- [ ] Overlap is maintained between consecutive chunks
- [ ] Page numbers are correctly tracked
- [ ] Content hash is unique per unique content
- [ ] Small documents produce at least one chunk

### Files to Create

1. `src/rag/chunking.py`

### Test Cases

```python
def test_chunking_size():
    chunks = chunker.chunk(pages)
    for chunk in chunks[:-1]:  # Except last
        assert 450 < chunk.token_count < 570

def test_overlap():
    chunks = chunker.chunk(pages)
    for i in range(1, len(chunks)):
        # Check overlap exists between consecutive chunks
        assert chunks[i].content[:100] in chunks[i-1].content[-200:]

def test_content_hash():
    chunks = chunker.chunk(pages)
    hashes = [c.content_hash for c in chunks]
    assert len(hashes) == len(set(hashes))  # All unique
```

---

## US 2.3: Embeddings

**Status:** 🔲 Not Started

### Description

Implement embedding generation using sentence-transformers with batch processing and retry logic.

### Context

Embedding model: `all-mpnet-base-v2`

- Output dimension: 768
- Batch size: 32 (from config)
- Device: CPU by default (configurable)

### Tasks

- [ ] Create `src/rag/embeddings.py`
- [ ] Initialize sentence-transformers model (lazy loading)
- [ ] Implement batch embedding generation
- [ ] Add retry logic with exponential backoff
- [ ] Add progress tracking for large documents

### Embeddings Interface

```python
# src/rag/embeddings.py
from sentence_transformers import SentenceTransformer
import numpy as np
from tenacity import retry, stop_after_attempt, wait_exponential

class EmbeddingService:
    def __init__(self, model_name: str = "all-mpnet-base-v2", device: str = "cpu"):
        self._model = None
        self.model_name = model_name
        self.device = device

    @property
    def model(self) -> SentenceTransformer:
        """Lazy load model."""
        if self._model is None:
            self._model = SentenceTransformer(self.model_name, device=self.device)
        return self._model

    @property
    def dimension(self) -> int:
        return 768  # all-mpnet-base-v2 dimension

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def embed(self, texts: list[str], batch_size: int = 32) -> np.ndarray:
        """Generate embeddings for texts."""
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=len(texts) > 100,
            convert_to_numpy=True
        )
        return embeddings

    def embed_query(self, query: str) -> np.ndarray:
        """Embed a single query."""
        return self.embed([query])[0]
```

### Acceptance Criteria

- [ ] Model loads successfully (lazy initialization)
- [ ] Batch embedding works for lists of texts
- [ ] Single query embedding works
- [ ] Retry logic handles transient failures
- [ ] Embeddings have correct dimension (768)

### Files to Create

1. `src/rag/embeddings.py`

### Dependencies to Add

```
sentence-transformers>=2.2.0
tenacity>=8.2.0
```

### Test Cases

```python
def test_embedding_dimension():
    service = EmbeddingService()
    embedding = service.embed_query("test query")
    assert embedding.shape == (768,)

def test_batch_embedding():
    service = EmbeddingService()
    texts = ["text 1", "text 2", "text 3"]
    embeddings = service.embed(texts)
    assert embeddings.shape == (3, 768)
```

---

## US 2.4: Qdrant Indexing

**Status:** 🔲 Not Started

### Description

Implement Qdrant collection management and vector upsert with metadata.

### Context

Qdrant configuration from PRD:

- Collection: `documents`
- Index: HNSW
- Distance: Cosine
- HNSW params: ef_construct=128, ef_search=40, m=16

### Tasks

- [ ] Create `src/db/qdrant.py`
- [ ] Implement collection creation with HNSW config
- [ ] Implement vector upsert with payload (metadata)
- [ ] Implement deduplication by content_hash
- [ ] Add connection health check
- [ ] Handle connection errors gracefully

### Qdrant Client Interface

```python
# src/db/qdrant.py
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct,
    HnswConfigDiff, OptimizersConfigDiff
)
import uuid

class QdrantService:
    def __init__(self, host: str = "localhost", port: int = 6333):
        self.client = QdrantClient(host=host, port=port)
        self.collection_name = "documents"

    def ensure_collection(self, vector_size: int = 768) -> None:
        """Create collection if it doesn't exist."""
        collections = self.client.get_collections().collections
        if not any(c.name == self.collection_name for c in collections):
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=vector_size,
                    distance=Distance.COSINE
                ),
                hnsw_config=HnswConfigDiff(
                    m=16,
                    ef_construct=128,
                )
            )

    def upsert_chunks(
        self,
        chunks: list[Chunk],
        embeddings: np.ndarray,
        document_id: str
    ) -> int:
        """Upsert chunks with embeddings. Returns count of inserted."""
        points = []
        for chunk, embedding in zip(chunks, embeddings):
            point_id = str(uuid.uuid4())
            points.append(PointStruct(
                id=point_id,
                vector=embedding.tolist(),
                payload={
                    "document_id": document_id,
                    "content": chunk.content,
                    "page": chunk.page,
                    "chunk_index": chunk.chunk_index,
                    "content_hash": chunk.content_hash,
                }
            ))

        self.client.upsert(
            collection_name=self.collection_name,
            points=points
        )
        return len(points)

    def delete_by_document(self, document_id: str) -> None:
        """Delete all chunks for a document."""
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_id",
                            match=models.MatchValue(value=document_id)
                        )
                    ]
                )
            )
        )

    def health_check(self) -> bool:
        """Check if Qdrant is accessible."""
        try:
            self.client.get_collections()
            return True
        except Exception:
            return False
```

### Payload Schema

```json
{
  "document_id": "uuid",
  "content": "chunk text content",
  "page": 1,
  "chunk_index": 0,
  "content_hash": "sha256hash",
  "source_title": "document.pdf",
  "version": 1,
  "uploaded_at": "2025-12-04T10:00:00Z"
}
```

### Acceptance Criteria

- [ ] Collection is created with correct HNSW config
- [ ] Vectors are upserted with all metadata
- [ ] Duplicate content_hash chunks are handled
- [ ] Document deletion removes all related chunks
- [ ] Health check correctly reports connectivity

### Files to Create

1. `src/db/__init__.py`
2. `src/db/qdrant.py`

### Test Cases

```python
def test_collection_creation():
    service = QdrantService()
    service.ensure_collection()
    collections = service.client.get_collections().collections
    assert any(c.name == "documents" for c in collections)

def test_upsert_and_delete():
    service = QdrantService()
    # Upsert chunks
    count = service.upsert_chunks(chunks, embeddings, "doc-1")
    assert count == len(chunks)
    # Delete
    service.delete_by_document("doc-1")
```

---

## US 2.5: Document Registry

**Status:** 🔲 Not Started

### Description

Implement SQLite-based document metadata storage for tracking uploaded documents.

### Context

SQLite stores document metadata (not vectors):

- Document ID, title, filename
- File hash for deduplication
- Page count, chunk count
- Version tracking for updates
- Processing status

### Tasks

- [ ] Create `src/db/sqlite.py`
- [ ] Implement database initialization with schema
- [ ] Implement CRUD operations for documents
- [ ] Add version tracking (parent_document_id)
- [ ] Add file hash checking for deduplication

### Database Schema

```sql
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    filename TEXT NOT NULL,
    file_hash TEXT NOT NULL,
    page_count INTEGER,
    chunk_count INTEGER,
    version INTEGER DEFAULT 1,
    parent_document_id TEXT REFERENCES documents(id),
    uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'processing'  -- processing | processed | failed
);

CREATE INDEX IF NOT EXISTS idx_file_hash ON documents(file_hash);
CREATE INDEX IF NOT EXISTS idx_parent_document ON documents(parent_document_id);
CREATE INDEX IF NOT EXISTS idx_status ON documents(status);
```

### Document Registry Interface

```python
# src/db/sqlite.py
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import uuid

@dataclass
class Document:
    id: str
    title: str
    filename: str
    file_hash: str
    page_count: int | None
    chunk_count: int | None
    version: int
    parent_document_id: str | None
    uploaded_at: datetime
    status: str  # processing | processed | failed

class DocumentRegistry:
    def __init__(self, db_path: str = "data/lexard.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema."""
        with self._get_connection() as conn:
            conn.executescript(SCHEMA_SQL)

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def create(
        self,
        title: str,
        filename: str,
        file_hash: str,
        parent_document_id: str | None = None
    ) -> Document:
        """Create new document record."""
        doc_id = str(uuid.uuid4())
        version = 1
        if parent_document_id:
            parent = self.get(parent_document_id)
            version = parent.version + 1 if parent else 1

        with self._get_connection() as conn:
            conn.execute(
                """INSERT INTO documents
                   (id, title, filename, file_hash, version, parent_document_id)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (doc_id, title, filename, file_hash, version, parent_document_id)
            )
        return self.get(doc_id)

    def get(self, doc_id: str) -> Document | None:
        """Get document by ID."""
        pass

    def get_by_hash(self, file_hash: str) -> Document | None:
        """Get document by file hash (for dedup)."""
        pass

    def update_status(
        self,
        doc_id: str,
        status: str,
        page_count: int | None = None,
        chunk_count: int | None = None
    ) -> None:
        """Update document processing status."""
        pass

    def list_all(self, limit: int = 100, offset: int = 0) -> list[Document]:
        """List all documents with pagination."""
        pass

    def delete(self, doc_id: str) -> bool:
        """Delete document record."""
        pass
```

### Acceptance Criteria

- [ ] Database file is created in `data/` directory
- [ ] Schema is applied on first run
- [ ] CRUD operations work correctly
- [ ] File hash lookup works for deduplication
- [ ] Version increments correctly for re-uploads
- [ ] Pagination works for list operation

### Files to Create

1. `src/db/sqlite.py`

### Test Cases

```python
def test_create_document():
    registry = DocumentRegistry(":memory:")
    doc = registry.create("Test Doc", "test.pdf", "abc123")
    assert doc.id is not None
    assert doc.version == 1
    assert doc.status == "processing"

def test_version_increment():
    registry = DocumentRegistry(":memory:")
    doc1 = registry.create("Doc", "doc.pdf", "hash1")
    doc2 = registry.create("Doc v2", "doc.pdf", "hash2", parent_document_id=doc1.id)
    assert doc2.version == 2

def test_dedup_by_hash():
    registry = DocumentRegistry(":memory:")
    doc1 = registry.create("Doc", "doc.pdf", "samehash")
    existing = registry.get_by_hash("samehash")
    assert existing.id == doc1.id
```

---

## Definition of Done (Epic 2)

- [ ] All 5 User Stories completed
- [ ] PDF, DOCX, TXT extraction working
- [ ] Chunking produces correct token-sized chunks with overlap
- [ ] Embeddings generate 768-dim vectors
- [ ] Qdrant stores and retrieves vectors
- [ ] SQLite tracks document metadata
- [ ] Integration test: upload file → chunks in Qdrant + metadata in SQLite
