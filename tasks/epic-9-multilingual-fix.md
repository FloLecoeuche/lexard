# Epic 9: Multilingual Support Fix

## Overview

Fix the incomplete multilingual implementation from Epic 7. While Epic 7 created the infrastructure (bilingual prompts, language detection function, E5 prefix support in embeddings), the actual integration was never completed. This epic ensures French documents receive French responses and that the embedding model supports multilingual retrieval.

## Problem Statement

Current issues identified:

1. **Config still uses English-only embeddings**: `config/config.yaml` has `all-mpnet-base-v2` instead of `intfloat/multilingual-e5-base`
2. **RAG pipeline uses hardcoded English prompts**: `src/rag/pipeline.py` and `src/rag/llm.py` use `QA_SYSTEM_PROMPT` which is English-only
3. **Agent tools don't use bilingual prompts**: `SummarizerTool`, `RiskDetectorTool` don't call `get_prompt()` with detected language
4. **Language not passed through API**: Query/summarize/risk endpoints don't detect language or pass it to tools
5. **Response doesn't include detected language**: API responses don't inform UI of the language used

## Design Decision: Document Language Determines Response Language

**Rule**: The response language should match the **document language**, not the query language.

| Document | Query | Response |
|----------|-------|----------|
| French   | French | French |
| French   | English | **French** |
| English  | French | **English** |
| English  | English | English |

**Rationale**:
- Documents are the source of truth; answers come from document content
- Users querying French contracts expect French legal terms in responses
- Citations from French documents should be in French context
- Consistent UX: same document always produces same language responses

## Prerequisites

- Epic 8 US 8.1 completed (Upload Progress Tracking)
- All core functionality working
- Existing bilingual prompts in `src/agent/prompts.py`
- Language detection function in `src/rag/llm.py`

## User Stories

---

## US 9.1: Multilingual Embeddings Configuration

**Status:** ✅ Completed

### Description

Update configuration to use multilingual embedding model (`intfloat/multilingual-e5-base`) and create a migration script to re-embed existing documents.

### Context

The `all-mpnet-base-v2` model is English-only and produces poor semantic similarity for French text. The `intfloat/multilingual-e5-base` model:
- Supports 100+ languages including French and English
- Same 768 dimensions (no Qdrant schema change needed)
- Requires `query: ` and `passage: ` prefixes (already implemented in `EmbeddingService`)

### Tasks

- [ ] Update `config/config.yaml`:
  ```yaml
  embeddings:
    model: 'intfloat/multilingual-e5-base'
    batch_size: 32
    device: 'cpu'
    query_prefix: 'query: '
    document_prefix: 'passage: '
  ```
- [ ] Update `config/config.docker.yaml` with same changes
- [ ] Update `CLAUDE.md` to reflect new default embedding model
- [ ] Create migration script `scripts/migrate_embeddings.py`:
  - Load all documents from registry
  - Re-chunk if needed (or load existing chunks from Qdrant)
  - Re-embed with new model
  - Update vectors in Qdrant (delete old, insert new)
  - Add progress output for large migrations
- [ ] Test migration script with sample documents
- [ ] Document migration process in `docs/multilingual.md`

### Implementation Details

#### Migration Script

```python
# scripts/migrate_embeddings.py
"""Re-embed all documents with multilingual model.

Usage:
    python scripts/migrate_embeddings.py [--dry-run]

This script is necessary when switching from all-mpnet-base-v2 to
intfloat/multilingual-e5-base for French language support.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import get_settings
from src.db.sqlite import DocumentRegistry
from src.db.qdrant import QdrantService
from src.rag.embeddings import EmbeddingService


async def migrate_embeddings(dry_run: bool = False):
    """Re-embed all documents with the configured embedding model."""
    settings = get_settings()

    print(f"Migration target model: {settings.embeddings.model}")
    print(f"Query prefix: '{settings.embeddings.query_prefix}'")
    print(f"Document prefix: '{settings.embeddings.document_prefix}'")

    if dry_run:
        print("\n[DRY RUN] No changes will be made.\n")

    # Initialize services
    registry = DocumentRegistry()
    qdrant = QdrantService()
    embedding_service = EmbeddingService(
        model_name=settings.embeddings.model,
        device=settings.embeddings.device,
        query_prefix=settings.embeddings.query_prefix,
        document_prefix=settings.embeddings.document_prefix,
    )

    # Get all processed documents
    documents = [d for d in registry.list_all() if d.status == "processed"]
    print(f"Found {len(documents)} processed documents to migrate.\n")

    if not documents:
        print("No documents to migrate.")
        return

    for i, doc in enumerate(documents, 1):
        print(f"[{i}/{len(documents)}] Migrating: {doc.title} ({doc.id})")

        # Get existing chunks from Qdrant
        chunks = await qdrant.get_chunks_by_document(doc.id)
        if not chunks:
            print(f"  WARNING: No chunks found for document {doc.id}")
            continue

        print(f"  Found {len(chunks)} chunks")

        if dry_run:
            print(f"  [DRY RUN] Would re-embed {len(chunks)} chunks")
            continue

        # Extract text content from chunks
        texts = [chunk.content for chunk in chunks]

        # Re-embed with new model
        print(f"  Generating embeddings...")
        embeddings = embedding_service.embed_documents(texts)

        # Delete old vectors
        print(f"  Deleting old vectors...")
        await qdrant.delete_by_document_id(doc.id)

        # Insert new vectors
        print(f"  Inserting new vectors...")
        await qdrant.upsert_chunks(doc.id, chunks, embeddings)

        print(f"  Done!")

    print(f"\nMigration complete! {len(documents)} documents processed.")


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    asyncio.run(migrate_embeddings(dry_run=dry_run))
```

### Acceptance Criteria

- [ ] `config/config.yaml` uses `intfloat/multilingual-e5-base`
- [ ] E5 prefixes configured (`query: ` and `passage: `)
- [ ] Migration script runs without errors
- [ ] Migration script has `--dry-run` option
- [ ] Existing documents can be re-embedded
- [ ] French queries return relevant French chunks
- [ ] English queries still work correctly
- [ ] Documentation updated

### Tests

- **Modified:** `tests/test_embeddings.py` - Update for new model name
- **New:** `tests/test_migration.py` - Test migration script logic (mock Qdrant)
- **Run:** `pytest tests/test_embeddings.py tests/test_migration.py -v`

> Note: Migration script is primarily tested manually with `--dry-run`. Unit test validates helper functions only.

### Files to Modify

1. `config/config.yaml` - Update embeddings config
2. `config/config.docker.yaml` - Update embeddings config
3. `CLAUDE.md` - Update embeddings documentation
4. `scripts/migrate_embeddings.py` - Enhance existing script
5. `docs/multilingual.md` - Add migration instructions

---

## US 9.2: Language-Aware RAG Pipeline

**Status:** ✅ Completed

### Description

Update the RAG pipeline to detect **document language** from retrieved chunks and use appropriate bilingual prompts for LLM generation, ensuring French documents always receive French responses regardless of query language.

### Context

Current flow (broken):
```
Any Query → English Prompt → LLM → English Response
```

Target flow:
```
Query → Retrieve Chunks → Detect Language from Chunks → Localized Prompt → LLM → Localized Response
```

**Key Design**: Language is detected from the **retrieved document chunks**, not from the query. This ensures:
- French document + English query → French response
- English document + French query → English response

The infrastructure exists:
- `detect_language()` in `src/rag/llm.py`
- `get_prompt()` in `src/agent/prompts.py`
- Bilingual prompts for all operations

But the RAG pipeline doesn't use them.

### Tasks

- [ ] Update `src/rag/llm.py`:
  - Create bilingual `QA_SYSTEM_PROMPTS` dict (en/fr)
  - Create bilingual `QA_USER_PROMPTS` dict (en/fr)
  - Update `build_qa_prompt()` to accept `language` parameter
  - Add `get_qa_system_prompt(language)` function
  - Add `detect_language_from_chunks(chunks)` helper function
- [ ] Update `src/rag/pipeline.py`:
  - Add `language` parameter to `RAGPipeline.query()` (optional override)
  - **Detect language from retrieved chunks** (not from query)
  - Pass language to prompt building
  - Include detected language in `RAGResponse`
- [ ] Update `src/rag/pipeline.py` `RAGResponse`:
  - Add `language: str` field to response dataclass
- [ ] Update `src/api/routes/query.py`:
  - Pass detected language through pipeline
  - Include `language` in API response
- [ ] Update `src/api/schemas.py`:
  - Add `language` field to `QueryResponse`
- [ ] Add unit tests for language-aware prompts

### Implementation Details

#### Updated LLM Prompts

```python
# src/rag/llm.py

QA_SYSTEM_PROMPTS = {
    "en": """You are an enterprise contract analyst assistant.

RULES:
1. ONLY answer based on the retrieved document chunks provided
2. ALWAYS cite the specific chunk(s) that support your answer using [1], [2], etc.
3. If no chunk supports the answer, respond: "I cannot find information about this in the provided documents."
4. NEVER fabricate information, clauses, or terms
5. When uncertain, express uncertainty rather than guessing

FORMAT:
- Provide clear, concise answers
- List citations at the end as [Chunk X, Page Y]
""",
    "fr": """Vous etes un assistant d'analyse de contrats d'entreprise.

REGLES:
1. Repondez UNIQUEMENT en vous basant sur les extraits de documents fournis
2. CITEZ TOUJOURS les extraits specifiques qui appuient votre reponse avec [1], [2], etc.
3. Si aucun extrait ne permet de repondre, dites: "Je ne trouve pas cette information dans les documents fournis."
4. Ne JAMAIS inventer d'informations, de clauses ou de termes
5. En cas d'incertitude, exprimez votre doute plutot que de deviner

FORMAT:
- Fournissez des reponses claires et concises
- Listez les citations a la fin sous forme [Extrait X, Page Y]
""",
}

QA_USER_PROMPTS = {
    "en": """Based on the following document excerpts, answer the question.

DOCUMENT EXCERPTS:
{context}

QUESTION: {question}

Provide a clear answer with citations to the relevant excerpts.""",
    "fr": """En vous basant sur les extraits de documents suivants, repondez a la question.

EXTRAITS DE DOCUMENTS:
{context}

QUESTION: {question}

Fournissez une reponse claire avec des citations vers les extraits pertinents.""",
}


def get_qa_system_prompt(language: str = "en") -> str:
    """Get QA system prompt in specified language."""
    return QA_SYSTEM_PROMPTS.get(language, QA_SYSTEM_PROMPTS["en"])


def build_qa_prompt(question: str, context: str, language: str = "en") -> str:
    """Build a Q&A prompt with context in specified language."""
    template = QA_USER_PROMPTS.get(language, QA_USER_PROMPTS["en"])
    return template.format(context=context, question=question)


def detect_language_from_chunks(chunks: list) -> str:
    """Detect language from retrieved document chunks.

    Samples text from multiple chunks to get reliable detection.
    This ensures response language matches document language,
    regardless of query language.

    Args:
        chunks: List of RetrievedChunk objects

    Returns:
        'fr' for French, 'en' for English (default)
    """
    if not chunks:
        return "en"

    # Sample text from first few chunks (more reliable than single chunk)
    sample_texts = [chunk.content for chunk in chunks[:3]]
    combined_sample = " ".join(sample_texts)[:1000]  # Limit to 1000 chars

    return detect_language(combined_sample)
```

#### Updated RAGResponse

```python
# src/rag/pipeline.py

@dataclass
class RAGResponse:
    """Response from RAG pipeline."""
    answer: str
    citation_chunks: list[CitationChunk]
    confidence: Confidence
    has_relevant_content: bool
    language: str = "en"  # Detected/used language
```

#### Updated Query Method

```python
# src/rag/pipeline.py

def query(
    self,
    question: str,
    document_id: str | None = None,
    language: str | None = None,
) -> RAGResponse:
    """Execute RAG query and return grounded answer.

    Args:
        question: User's question
        document_id: Optional document filter
        language: Language for response. If None, auto-detected from document chunks.

    Note:
        Language is detected from the DOCUMENT content (retrieved chunks),
        not from the query. This ensures French documents always get French
        responses, even when queried in English.
    """
    from src.rag.llm import (
        detect_language_from_chunks,
        get_qa_system_prompt,
        build_qa_prompt,
    )

    logger.info(
        "Processing RAG query",
        extra={
            "question_length": len(question),
            "document_id": document_id,
        },
    )

    # 1. Retrieve relevant chunks
    chunks = self.retriever.retrieve(question, document_id)

    # 2. Handle no results
    if not chunks:
        logger.info("No relevant chunks found for query")
        return RAGResponse(
            answer="I could not find relevant information in the provided documents.",
            citation_chunks=[],
            confidence=Confidence.LOW,
            has_relevant_content=False,
            language="en",  # Default for no-content response
        )

    # 3. Detect language from DOCUMENT CHUNKS (not query)
    if language is None:
        language = detect_language_from_chunks(chunks)

    logger.info(
        "Detected document language",
        extra={"language": language, "chunk_count": len(chunks)},
    )

    # 4. Build context
    context = self.context_builder.build(chunks)

    # 5. Generate answer with language-aware prompts
    prompt = build_qa_prompt(question, context.context_text, language=language)
    system_prompt = get_qa_system_prompt(language=language)

    response = self.llm_client.generate(
        prompt=prompt,
        system_prompt=system_prompt,
    )

    # 6. Calculate confidence and build citations
    confidence = self._calculate_confidence(chunks)
    citation_chunks = self._build_citation_chunks(chunks, context)

    return RAGResponse(
        answer=response.content,
        citation_chunks=citation_chunks,
        confidence=confidence,
        has_relevant_content=True,
        language=language,
    )
```

### Acceptance Criteria

- [ ] Language detected from **document chunks**, not query
- [ ] French document + English query → French response
- [ ] French document + French query → French response
- [ ] English document + French query → English response
- [ ] English document + English query → English response
- [ ] API response includes `language` field
- [ ] Language detection accuracy >95% (use langdetect)
- [ ] Unit tests pass for both languages
- [ ] No regression in English query quality

### Tests

- **Modified:** `tests/test_pipeline.py` - Add language detection and response tests
- **Modified:** `tests/test_llm.py` - Test `detect_language_from_chunks()` and bilingual prompts
- **Run:** `pytest tests/test_pipeline.py tests/test_llm.py -v`

> Note: Test French doc + English query → French response (key behavior).

### Files to Modify

1. `src/rag/llm.py` - Add bilingual prompts, `detect_language_from_chunks()`
2. `src/rag/pipeline.py` - Language-aware query method
3. `src/api/routes/query.py` - Pass language through
4. `src/api/schemas.py` - Add language to response
5. `tests/test_rag_pipeline.py` - Add language tests

---

## US 9.3: Language-Aware Agent Tools

**Status:** ✅ Completed

### Description

Update agent tools (SummarizerTool, RiskDetectorTool, DiffTool) to use bilingual prompts based on detected **document language** (not query language).

### Context

Agent tools currently use hardcoded English prompts. The bilingual prompts exist in `src/agent/prompts.py` but tools don't use them:

- `CHUNK_SUMMARY_PROMPTS` - For summarization
- `AGGREGATION_PROMPTS` - For summary aggregation
- `RISK_ANALYSIS_PROMPTS` - For risk detection
- `DIFF_PROMPTS` - For document comparison

**Key Design**: Same as US 9.2, language is detected from **document content**, ensuring:
- French document → French summary/analysis
- English document → English summary/analysis

### Tasks

- [ ] Update `src/agent/tools/summarizer.py`:
  - Add `language` parameter to `summarize()` method (optional override)
  - **Detect language from document chunks** if not provided
  - Use `get_prompt("chunk_summary", language)` for chunk summaries
  - Use `get_prompt("aggregation", language)` for final summary
  - Return language in result
- [ ] Update `src/agent/tools/risk_detector.py`:
  - Add `language` parameter to `analyze()` method (optional override)
  - **Detect language from document chunks** if not provided
  - Use `get_prompt("risk_analysis", language)` for analysis
  - Return language in result
- [ ] Update `src/agent/tools/diff.py`:
  - Add `language` parameter to `compare()` method (optional override)
  - **Detect language from first document's chunks** if not provided
  - Use `get_prompt("diff", language)` for comparison
  - Return language in result
- [ ] Update API routes to pass language:
  - `src/api/routes/analysis.py` - Language auto-detected in tools
- [ ] Update response schemas:
  - Add `language` field to `SummarizeResponse`
  - Add `language` field to `RiskResponse`
  - Add `language` field to `CompareResponse`
- [ ] Add tests for French tool operations

### Implementation Details

#### Summarizer Tool Update

```python
# src/agent/tools/summarizer.py

from src.agent.prompts import get_prompt
from src.rag.llm import detect_language_from_chunks

class SummarizerTool:
    async def summarize(
        self,
        document_id: str,
        style: str = "executive",
        language: str | None = None,
    ) -> SummaryResult:
        """Generate document summary.

        Args:
            document_id: Document to summarize
            style: Summary style (executive, detailed)
            language: Output language. If None, detected from document content.

        Note:
            Language is detected from the DOCUMENT content (chunks),
            ensuring French documents always get French summaries.
        """
        # Get document chunks
        chunks = await self.qdrant_service.get_chunks_by_document(document_id)
        if not chunks:
            raise ValueError(f"No chunks found for document {document_id}")

        # Detect language from DOCUMENT CHUNKS if not provided
        if language is None:
            language = detect_language_from_chunks(chunks)

        logger.info(f"Summarizing document {document_id} in {language}")

        # Summarize chunks with language-aware prompts
        chunk_summaries = []
        for chunk in chunks:
            prompt = get_prompt("chunk_summary", language, content=chunk.content)
            response = self.llm_client.generate(prompt)
            chunk_summaries.append(response.content)

        # Aggregate summaries
        combined = "\n\n".join(chunk_summaries)
        aggregation_prompt = get_prompt("aggregation", language, summaries=combined)
        final_response = self.llm_client.generate(aggregation_prompt)

        return SummaryResult(
            executive_summary=final_response.content,
            key_points=self._extract_key_points(final_response.content),
            word_count=len(final_response.content.split()),
            language=language,
        )
```

#### API Route Update

```python
# src/api/routes/analysis.py

@router.post("/summarize")
async def summarize_document(req: SummarizeRequest, request: Request) -> SummarizeResponse:
    # ... validation ...

    # Language detection happens inside tool if not provided
    result = await summarizer.summarize(
        document_id=req.document_id,
        style=req.style,
        # language=None means auto-detect from document
    )

    return SummarizeResponse(
        summary=result.executive_summary,
        key_points=result.key_points,
        word_count=result.word_count,
        language=result.language,  # Include detected language
    )
```

### Acceptance Criteria

- [ ] SummarizerTool uses French prompts for French documents
- [ ] RiskDetectorTool uses French prompts for French documents
- [ ] DiffTool uses French prompts when comparing French documents
- [ ] Language auto-detected from document content
- [ ] API responses include `language` field
- [ ] French summaries are in French
- [ ] French risk analysis is in French
- [ ] English functionality unchanged
- [ ] Unit tests pass for both languages

### Tests

- **Modified:** `tests/test_summarizer.py` - Add French summarization tests
- **Modified:** `tests/test_risk_detector.py` - Add French risk analysis tests
- **Modified:** `tests/test_diff.py` - Add French comparison tests
- **Run:** `pytest tests/test_summarizer.py tests/test_risk_detector.py tests/test_diff.py -v`

> Note: Mock LLM responses to verify correct prompts are selected based on language.

### Files to Modify

1. `src/agent/tools/summarizer.py` - Language-aware summarization
2. `src/agent/tools/risk_detector.py` - Language-aware risk analysis
3. `src/agent/tools/diff.py` - Language-aware comparison
4. `src/api/routes/analysis.py` - Pass language through
5. `src/api/schemas.py` - Add language to responses
6. `tests/test_agent_tools.py` - Add French tests

---

## US 9.4: Web UI Language Display

**Status:** ✅ Completed

### Description

Update the Web UI to display the detected language and show responses appropriately for French content.

### Context

The UI should:
- Show which language was detected for the query/document
- Display responses in the detected language
- Potentially allow manual language override

### Tasks

- [ ] Update query response handling in UI:
  - Display detected language badge (EN/FR)
  - Style citations appropriately for language
- [ ] Update summarize response handling:
  - Show language indicator
- [ ] Update risk analysis response handling:
  - Show language indicator
  - Translate severity labels if needed (or keep consistent)
- [ ] Add language indicator component:
  - Small badge showing "EN" or "FR"
  - Tooltip explaining auto-detection
- [ ] Optional: Add manual language selector:
  - Dropdown to override detected language
  - Pass to API as query parameter

### Implementation Details

#### Language Badge Component

```tsx
// ui/src/components/LanguageBadge.tsx

interface LanguageBadgeProps {
  language: string;
}

export function LanguageBadge({ language }: LanguageBadgeProps) {
  const label = language === 'fr' ? 'FR' : 'EN';
  const title = language === 'fr'
    ? 'Reponse en francais (detecte automatiquement)'
    : 'Response in English (auto-detected)';

  return (
    <span
      className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800"
      title={title}
    >
      {label}
    </span>
  );
}
```

#### Query Response Update

```tsx
// In QueryPanel.tsx or similar

{response && (
  <div className="mt-4">
    <div className="flex items-center gap-2 mb-2">
      <h3 className="font-semibold">Answer</h3>
      {response.language && <LanguageBadge language={response.language} />}
    </div>
    <p className="text-gray-700">{response.answer}</p>
    {/* ... citations ... */}
  </div>
)}
```

### Acceptance Criteria

- [ ] Language badge displayed for query responses
- [ ] Language badge displayed for summaries
- [ ] Language badge displayed for risk analysis
- [ ] Badge shows "FR" for French, "EN" for English
- [ ] Tooltip explains auto-detection
- [ ] UI renders French text correctly (accents, etc.)
- [ ] No layout issues with French content

### Tests

- **None:** UI-only changes (no Python backend tests)
- **Manual:** Verify language badge displays correctly for EN/FR responses
- **Run:** Manual browser testing with French and English documents

> Note: UI is a single HTML file. No automated frontend tests in this project.

### Files to Modify

1. `ui/src/components/LanguageBadge.tsx` - New component
2. `ui/src/components/QueryPanel.tsx` - Add language display
3. `ui/src/components/SummaryPanel.tsx` - Add language display
4. `ui/src/components/RiskPanel.tsx` - Add language display
5. `ui/src/types.ts` - Update response types with language

---

## US 9.5: Integration Testing & Documentation

**Status:** ✅ Completed

### Description

Comprehensive integration tests for multilingual functionality and documentation updates.

### Tasks

- [ ] Create integration tests:
  - `tests/integration/test_french_workflow.py`
  - Test French document upload
  - Test French query → French response
  - Test French summarization
  - Test French risk analysis
  - Test mixed language scenarios
- [ ] Create E2E tests:
  - `tests/e2e/test_multilingual_e2e.py`
  - Full workflow: upload FR doc → query FR → get FR response
  - Verify language field in responses
- [ ] Update evaluation harness:
  - Add French test cases to `data/eval/`
  - Calculate French-specific metrics
  - Compare EN vs FR performance
- [ ] Update documentation:
  - `docs/multilingual.md` - Complete guide
  - `README.md` - Mention French support
  - `CLAUDE.md` - Update embeddings reference
- [ ] Create French test documents:
  - `data/test/contrat_nda_fr.txt` - Sample French NDA
  - `data/test/contrat_service_fr.txt` - Sample French service contract

### Test Cases

```python
# tests/integration/test_french_workflow.py

import pytest
from src.rag.llm import detect_language, detect_language_from_chunks
from src.rag.pipeline import RAGPipeline

class TestFrenchWorkflow:

    def test_language_detection_french(self):
        """Test French language detection."""
        assert detect_language("Quelle est la periode de preavis?") == "fr"
        assert detect_language("Quels sont les risques financiers?") == "fr"

    def test_language_detection_english(self):
        """Test English language detection."""
        assert detect_language("What is the notice period?") == "en"
        assert detect_language("What are the financial risks?") == "en"

    @pytest.mark.asyncio
    async def test_french_document_french_query_french_response(
        self, rag_pipeline, french_document
    ):
        """Test: French document + French query = French response."""
        result = rag_pipeline.query(
            question="Quelle est la duree du contrat?",
            document_id=french_document.id,
        )

        assert result.language == "fr"
        # Response should contain French words
        assert any(word in result.answer.lower() for word in ["contrat", "duree", "mois", "annee"])

    @pytest.mark.asyncio
    async def test_french_document_english_query_french_response(
        self, rag_pipeline, french_document
    ):
        """Test: French document + English query = French response.

        This is the KEY test - language follows the DOCUMENT, not the query.
        """
        result = rag_pipeline.query(
            question="What is the contract duration?",  # English query
            document_id=french_document.id,  # French document
        )

        # Response should be in FRENCH (document language)
        assert result.language == "fr"
        # Response should contain French words, not English
        assert any(word in result.answer.lower() for word in ["contrat", "duree", "mois"])

    @pytest.mark.asyncio
    async def test_english_document_french_query_english_response(
        self, rag_pipeline, english_document
    ):
        """Test: English document + French query = English response."""
        result = rag_pipeline.query(
            question="Quelle est la duree du contrat?",  # French query
            document_id=english_document.id,  # English document
        )

        # Response should be in ENGLISH (document language)
        assert result.language == "en"

    @pytest.mark.asyncio
    async def test_english_document_english_query_english_response(
        self, rag_pipeline, english_document
    ):
        """Test: English document + English query = English response."""
        result = rag_pipeline.query(
            question="What is the contract duration?",
            document_id=english_document.id,
        )

        assert result.language == "en"
```

### Documentation Structure

```markdown
# docs/multilingual.md

# Multilingual Support

Lexard supports French and English document analysis.

## Supported Languages

| Language | Code | Embeddings | Prompts | Guardrails |
|----------|------|------------|---------|------------|
| English  | en   | ✅         | ✅      | ✅         |
| French   | fr   | ✅         | ✅      | ✅         |

## How It Works

1. **Embeddings**: Uses `intfloat/multilingual-e5-base` model for cross-lingual retrieval
2. **Language Detection**: Automatic from document content via `langdetect`
3. **Prompts**: Bilingual prompts for all operations
4. **Response Language**: Matches **document** language (not query language)

## Language Detection Rule

**Response language always matches the document language**, regardless of query language:

| Document | Query | Response |
|----------|-------|----------|
| French   | French | French |
| French   | English | **French** |
| English  | French | **English** |
| English  | English | English |

This ensures:
- Consistent responses for the same document
- French legal terminology preserved in French contracts
- Citations match document language

## Configuration

```yaml
embeddings:
  model: 'intfloat/multilingual-e5-base'
  query_prefix: 'query: '
  document_prefix: 'passage: '
```

## Migration from English-Only

If upgrading from `all-mpnet-base-v2`:

```bash
python scripts/migrate_embeddings.py
```

## API Response

All responses include a `language` field indicating detected document language:

```json
{
  "answer": "La duree du contrat est de 12 mois.",
  "language": "fr",
  "citation_chunks": [...]
}
```

## Cross-Language Queries

You can query French documents in English (and vice versa):

```bash
# English query on French document - response will be in French
curl -X POST /query -d '{
  "document_id": "french-contract-123",
  "question": "What is the notice period?"
}'
# Response: {"answer": "Le preavis est de 30 jours...", "language": "fr"}
```
```

### Acceptance Criteria

- [ ] Integration tests pass for French workflow
- [ ] E2E tests pass for complete French pipeline
- [ ] French test documents created
- [ ] Evaluation harness includes French metrics
- [ ] `docs/multilingual.md` comprehensive
- [ ] README mentions French support
- [ ] CLAUDE.md reflects current embedding model
- [ ] All existing English tests still pass

### Tests

- **New:** `tests/integration/test_french_workflow.py` - French language workflow tests
- **New:** `tests/e2e/test_multilingual_e2e.py` - End-to-end multilingual tests
- **Run:** `pytest tests/integration/test_french_workflow.py tests/e2e/test_multilingual_e2e.py -v`

> Note: This US is primarily about creating tests. Run full test suite at the end.

### Files to Create/Modify

1. `tests/integration/test_french_workflow.py` - New
2. `tests/e2e/test_multilingual_e2e.py` - New
3. `data/test/contrat_nda_fr.txt` - New
4. `data/test/contrat_service_fr.txt` - New
5. `data/eval/french_qa.yaml` - New or update
6. `docs/multilingual.md` - Update
7. `README.md` - Update
8. `CLAUDE.md` - Update

---

## Definition of Done (Epic 9)

- [ ] All 5 User Stories completed
- [ ] `intfloat/multilingual-e5-base` configured and working
- [ ] Migration script successfully re-embeds documents
- [ ] French queries receive French responses
- [ ] French summaries are in French
- [ ] French risk analysis is in French
- [ ] API responses include `language` field
- [ ] UI displays language indicator
- [ ] English functionality has no regression
- [ ] Integration tests pass
- [ ] E2E tests pass
- [ ] Documentation complete
- [ ] All acceptance criteria verified

## Estimated Effort

| US  | Description                      | Complexity |
|-----|----------------------------------|------------|
| 9.1 | Multilingual Embeddings Config   | Medium     |
| 9.2 | Language-Aware RAG Pipeline      | Medium     |
| 9.3 | Language-Aware Agent Tools       | Medium     |
| 9.4 | Web UI Language Display          | Low        |
| 9.5 | Integration Testing & Docs       | Medium     |

## Dependencies

```
US 9.1 (Embeddings)
    ↓
US 9.2 (RAG Pipeline) ──→ US 9.4 (UI)
    ↓
US 9.3 (Agent Tools) ──→ US 9.4 (UI)
    ↓
US 9.5 (Testing & Docs)
```

US 9.1 must be completed first (embeddings are foundational).
US 9.2 and 9.3 can be done in parallel after 9.1.
US 9.4 can start after 9.2/9.3 expose language in API.
US 9.5 should be done last to validate everything.
