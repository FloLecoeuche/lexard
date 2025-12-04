# Epic 3: RAG Engine

## Overview

Implement the Retrieval-Augmented Generation pipeline that retrieves relevant chunks from Qdrant, builds context, generates answers using Ollama, and validates outputs with basic guardrails.

## Prerequisites

- Epic 1 completed (Foundation)
- Epic 2 completed (Ingestion Pipeline)
- Qdrant running with indexed documents
- Ollama running with mistral:7b-instruct model

## Architecture

```
User Query
    ↓
Query Embedding (sentence-transformers)
    ↓
Dense Retrieval (Qdrant top-k)
    ↓
Score Filtering (threshold: 0.7)
    ↓
Context Building (4-8 chunks)
    ↓
LLM Generation (Ollama)
    ↓
Guardrails Validation
    ↓
Response with Citations
```

## User Stories

---

## US 3.1: Dense Retrieval

**Status:** ✅ Completed

### Description

Implement semantic search over Qdrant to retrieve the most relevant chunks for a user query.

### Context

Retrieval parameters from PRD:

- top_k: 8
- score_threshold: 0.7 (cosine similarity)
- Filter by document_id when specified

### Tasks

- [ ] Create `src/rag/retriever.py`
- [ ] Implement query embedding using EmbeddingService
- [ ] Implement Qdrant similarity search
- [ ] Add score filtering (discard below threshold)
- [ ] Add document_id filtering
- [ ] Return chunks with scores and metadata

### Retriever Interface

```python
# src/rag/retriever.py
from dataclasses import dataclass
from src.rag.embeddings import EmbeddingService
from src.db.qdrant import QdrantService

@dataclass
class RetrievedChunk:
    content: str
    score: float
    page: int
    chunk_index: int
    document_id: str
    content_hash: str

class Retriever:
    def __init__(
        self,
        embedding_service: EmbeddingService,
        qdrant_service: QdrantService,
        top_k: int = 8,
        score_threshold: float = 0.7
    ):
        self.embedding_service = embedding_service
        self.qdrant_service = qdrant_service
        self.top_k = top_k
        self.score_threshold = score_threshold

    def retrieve(
        self,
        query: str,
        document_id: str | None = None
    ) -> list[RetrievedChunk]:
        """
        Retrieve relevant chunks for a query.

        Args:
            query: User's question
            document_id: Optional filter to specific document

        Returns:
            List of chunks sorted by relevance score (descending)
        """
        # 1. Embed query
        query_vector = self.embedding_service.embed_query(query)

        # 2. Build filter
        filter_conditions = None
        if document_id:
            filter_conditions = models.Filter(
                must=[
                    models.FieldCondition(
                        key="document_id",
                        match=models.MatchValue(value=document_id)
                    )
                ]
            )

        # 3. Search Qdrant
        results = self.qdrant_service.client.search(
            collection_name=self.qdrant_service.collection_name,
            query_vector=query_vector.tolist(),
            limit=self.top_k,
            query_filter=filter_conditions,
            with_payload=True,
            score_threshold=self.score_threshold
        )

        # 4. Convert to RetrievedChunk
        chunks = []
        for result in results:
            chunks.append(RetrievedChunk(
                content=result.payload["content"],
                score=result.score,
                page=result.payload["page"],
                chunk_index=result.payload["chunk_index"],
                document_id=result.payload["document_id"],
                content_hash=result.payload["content_hash"]
            ))

        return chunks
```

### Acceptance Criteria

- [ ] Query embedding is generated correctly
- [ ] Qdrant search returns relevant results
- [ ] Results are filtered by score threshold
- [ ] Document filter works when provided
- [ ] Empty results are handled gracefully
- [ ] Results are sorted by score (highest first)

### Files to Create

1. `src/rag/retriever.py`

### Test Cases

```python
def test_retrieval_returns_chunks():
    retriever = Retriever(embedding_service, qdrant_service)
    chunks = retriever.retrieve("What are the payment terms?")
    assert len(chunks) <= 8
    assert all(c.score >= 0.7 for c in chunks)

def test_retrieval_with_document_filter():
    retriever = Retriever(embedding_service, qdrant_service)
    chunks = retriever.retrieve("termination", document_id="doc-123")
    assert all(c.document_id == "doc-123" for c in chunks)

def test_retrieval_empty_results():
    retriever = Retriever(embedding_service, qdrant_service)
    chunks = retriever.retrieve("xyzzy gibberish query")
    assert chunks == []
```

---

## US 3.2: Context Building

**Status:** ✅ Completed

### Description

Build the context window from retrieved chunks, formatting them for LLM consumption.

### Context

Context building requirements:

- Use 4-8 chunks (configurable)
- Format with clear chunk boundaries
- Include citation markers for reference
- Respect LLM context window limits

### Tasks

- [ ] Create `src/rag/context.py`
- [ ] Implement context builder that formats chunks
- [ ] Add token counting to respect limits
- [ ] Include citation markers (e.g., [1], [2])
- [ ] Handle case with no relevant chunks

### Context Builder Interface

```python
# src/rag/context.py
from dataclasses import dataclass

@dataclass
class Citation:
    index: int  # [1], [2], etc.
    page: int
    chunk_index: int
    document_id: str
    excerpt: str  # First 100 chars for reference

@dataclass
class BuiltContext:
    context_text: str
    citations: list[Citation]
    chunk_count: int
    total_tokens: int
    has_relevant_content: bool

class ContextBuilder:
    def __init__(
        self,
        max_chunks: int = 8,
        max_tokens: int = 3000  # Leave room for prompt + response
    ):
        self.max_chunks = max_chunks
        self.max_tokens = max_tokens
        self.tokenizer = tiktoken.get_encoding("cl100k_base")

    def build(self, chunks: list[RetrievedChunk]) -> BuiltContext:
        """
        Build context from retrieved chunks.

        Returns:
            BuiltContext with formatted text and citations
        """
        if not chunks:
            return BuiltContext(
                context_text="",
                citations=[],
                chunk_count=0,
                total_tokens=0,
                has_relevant_content=False
            )

        context_parts = []
        citations = []
        total_tokens = 0

        for i, chunk in enumerate(chunks[:self.max_chunks]):
            # Check token limit
            chunk_tokens = len(self.tokenizer.encode(chunk.content))
            if total_tokens + chunk_tokens > self.max_tokens:
                break

            # Add formatted chunk
            citation_marker = f"[{i + 1}]"
            context_parts.append(f"{citation_marker} {chunk.content}")

            # Record citation
            citations.append(Citation(
                index=i + 1,
                page=chunk.page,
                chunk_index=chunk.chunk_index,
                document_id=chunk.document_id,
                excerpt=chunk.content[:100] + "..." if len(chunk.content) > 100 else chunk.content
            ))

            total_tokens += chunk_tokens

        context_text = "\n\n".join(context_parts)

        return BuiltContext(
            context_text=context_text,
            citations=citations,
            chunk_count=len(citations),
            total_tokens=total_tokens,
            has_relevant_content=True
        )
```

### Context Format Example

```
[1] The payment terms require net-30 payment from invoice date. Late payments
incur a 1.5% monthly interest charge...

[2] In case of dispute, the parties agree to first attempt mediation before
pursuing legal action...

[3] This agreement may be terminated by either party with 60 days written
notice...
```

### Acceptance Criteria

- [ ] Chunks are formatted with citation markers
- [ ] Token limit is respected
- [ ] Citations list is generated with metadata
- [ ] Empty chunk list is handled gracefully
- [ ] Context indicates if relevant content exists

### Files to Create

1. `src/rag/context.py`

### Test Cases

```python
def test_context_building():
    chunks = [mock_chunk(content="test content", page=1)]
    context = builder.build(chunks)
    assert "[1]" in context.context_text
    assert len(context.citations) == 1

def test_token_limit():
    large_chunks = [mock_chunk(content="x" * 1000) for _ in range(10)]
    context = builder.build(large_chunks)
    assert context.total_tokens <= 3000

def test_empty_chunks():
    context = builder.build([])
    assert context.has_relevant_content is False
```

---

## US 3.3: LLM Integration

**Status:** ✅ Completed

### Description

Implement Ollama client for local LLM inference with proper error handling and timeout management.

### Context

LLM configuration from PRD:

- Provider: Ollama
- Model: mistral:7b-instruct
- Temperature: 0.1
- Max tokens: 2048
- Timeout: 30 seconds

### Tasks

- [ ] Create `src/rag/llm.py`
- [ ] Implement Ollama HTTP client
- [ ] Create prompt templates for Q&A
- [ ] Handle timeouts and connection errors
- [ ] Add response parsing

### LLM Client Interface

```python
# src/rag/llm.py
import httpx
from dataclasses import dataclass

@dataclass
class LLMResponse:
    content: str
    model: str
    total_tokens: int | None
    finish_reason: str

class OllamaClient:
    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "mistral:7b-instruct",
        temperature: float = 0.1,
        max_tokens: int = 2048,
        timeout: int = 30
    ):
        self.base_url = base_url
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout

    def generate(self, prompt: str, system_prompt: str | None = None) -> LLMResponse:
        """
        Generate response from Ollama.

        Args:
            prompt: User prompt with context
            system_prompt: Optional system instructions

        Returns:
            LLMResponse with generated text

        Raises:
            LLMTimeoutError: If request times out
            LLMConnectionError: If Ollama is unavailable
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.base_url}/api/chat",
                    json={
                        "model": self.model,
                        "messages": messages,
                        "stream": False,
                        "options": {
                            "temperature": self.temperature,
                            "num_predict": self.max_tokens
                        }
                    }
                )
                response.raise_for_status()
                data = response.json()

                return LLMResponse(
                    content=data["message"]["content"],
                    model=data["model"],
                    total_tokens=data.get("eval_count"),
                    finish_reason="stop"
                )

        except httpx.TimeoutException:
            raise LLMTimeoutError(f"Ollama request timed out after {self.timeout}s")
        except httpx.ConnectError:
            raise LLMConnectionError("Failed to connect to Ollama")

    def health_check(self) -> bool:
        """Check if Ollama is accessible and model is loaded."""
        try:
            with httpx.Client(timeout=5) as client:
                response = client.get(f"{self.base_url}/api/tags")
                if response.status_code == 200:
                    models = response.json().get("models", [])
                    return any(m["name"].startswith(self.model.split(":")[0]) for m in models)
        except Exception:
            pass
        return False

class LLMTimeoutError(Exception):
    pass

class LLMConnectionError(Exception):
    pass
```

### System Prompt (Q&A)

```python
QA_SYSTEM_PROMPT = """You are an enterprise contract analyst assistant.

RULES:
1. ONLY answer based on the retrieved document chunks provided
2. ALWAYS cite the specific chunk(s) that support your answer using [1], [2], etc.
3. If no chunk supports the answer, respond: "I cannot find information about this in the provided documents."
4. NEVER fabricate information, clauses, or terms
5. When uncertain, express uncertainty rather than guessing

FORMAT:
- Provide clear, concise answers
- List citations at the end as [Chunk X, Page Y]
"""
```

### Acceptance Criteria

- [ ] Ollama client connects and generates responses
- [ ] System prompt is applied correctly
- [ ] Timeout errors are raised after configured duration
- [ ] Connection errors are handled gracefully
- [ ] Health check correctly reports model availability

### Files to Create

1. `src/rag/llm.py`

### Test Cases

```python
def test_generate_response():
    client = OllamaClient()
    response = client.generate("What is 2+2?")
    assert response.content
    assert response.model.startswith("mistral")

def test_system_prompt():
    client = OllamaClient()
    response = client.generate(
        "Hello",
        system_prompt="Always respond in French"
    )
    # Response should be in French

def test_health_check():
    client = OllamaClient()
    assert client.health_check() in [True, False]
```

---

## US 3.4: Response Generation

**Status:** ✅ Completed

### Description

Implement the complete RAG flow that combines retrieval, context building, and LLM generation to produce grounded answers with citations.

### Context

The RAG pipeline should:

1. Retrieve relevant chunks
2. Build context with citations
3. Generate answer using LLM
4. Format response with citations
5. Handle "no relevant content" case

### Tasks

- [ ] Create `src/rag/pipeline.py`
- [ ] Implement end-to-end RAG flow
- [ ] Create response formatting with citations
- [ ] Handle low-relevance responses
- [ ] Add confidence scoring

### RAG Pipeline Interface

```python
# src/rag/pipeline.py
from dataclasses import dataclass
from enum import Enum

class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

@dataclass
class CitationChunk:
    content: str
    page: int
    chunk_index: int
    score: float

@dataclass
class RAGResponse:
    answer: str
    citation_chunks: list[CitationChunk]
    confidence: Confidence
    has_relevant_content: bool

class RAGPipeline:
    def __init__(
        self,
        retriever: Retriever,
        context_builder: ContextBuilder,
        llm_client: OllamaClient
    ):
        self.retriever = retriever
        self.context_builder = context_builder
        self.llm_client = llm_client

    def query(
        self,
        question: str,
        document_id: str | None = None
    ) -> RAGResponse:
        """
        Execute RAG query and return grounded answer.

        Args:
            question: User's question
            document_id: Optional document filter

        Returns:
            RAGResponse with answer and citations
        """
        # 1. Retrieve relevant chunks
        chunks = self.retriever.retrieve(question, document_id)

        # 2. Handle no results
        if not chunks:
            return RAGResponse(
                answer="I could not find relevant information in the provided documents to answer this question.",
                citation_chunks=[],
                confidence=Confidence.LOW,
                has_relevant_content=False
            )

        # 3. Build context
        context = self.context_builder.build(chunks)

        # 4. Generate prompt
        prompt = self._build_prompt(question, context.context_text)

        # 5. Call LLM
        llm_response = self.llm_client.generate(
            prompt=prompt,
            system_prompt=QA_SYSTEM_PROMPT
        )

        # 6. Calculate confidence
        avg_score = sum(c.score for c in chunks) / len(chunks)
        confidence = self._score_to_confidence(avg_score)

        # 7. Build response
        return RAGResponse(
            answer=llm_response.content,
            citation_chunks=[
                CitationChunk(
                    content=c.content,
                    page=c.page,
                    chunk_index=c.chunk_index,
                    score=c.score
                )
                for c in chunks
            ],
            confidence=confidence,
            has_relevant_content=True
        )

    def _build_prompt(self, question: str, context: str) -> str:
        return f"""Based on the following document excerpts, answer the question.

DOCUMENT EXCERPTS:
{context}

QUESTION: {question}

Provide a clear answer with citations to the relevant excerpts."""

    def _score_to_confidence(self, avg_score: float) -> Confidence:
        if avg_score >= 0.85:
            return Confidence.HIGH
        elif avg_score >= 0.75:
            return Confidence.MEDIUM
        else:
            return Confidence.LOW
```

### Acceptance Criteria

- [ ] Complete RAG flow works end-to-end
- [ ] Answers include citations from context
- [ ] No-results case returns appropriate message
- [ ] Confidence reflects retrieval quality
- [ ] Response format matches API specification

### Files to Create

1. `src/rag/pipeline.py`

### Test Cases

```python
def test_rag_pipeline():
    pipeline = RAGPipeline(retriever, context_builder, llm_client)
    response = pipeline.query("What are the payment terms?", "doc-123")
    assert response.answer
    assert response.has_relevant_content

def test_rag_no_results():
    pipeline = RAGPipeline(retriever, context_builder, llm_client)
    response = pipeline.query("xyzzy gibberish", "doc-123")
    assert not response.has_relevant_content
    assert response.confidence == Confidence.LOW

def test_confidence_scoring():
    # Mock high-scoring chunks
    response = pipeline.query("exact match query")
    assert response.confidence == Confidence.HIGH
```

---

## US 3.5: Basic Guardrails

**Status:** ✅ Completed

### Description

Implement output validation to ensure responses are grounded and properly formatted.

### Context

Guardrails from PRD:

- Output schema validation
- Hallucination detection (check for citations)
- Low-relevance refusal

### Tasks

- [ ] Create `src/guardrails/validators.py`
- [ ] Implement schema validation for responses
- [ ] Implement basic hallucination detection
- [ ] Add citation verification
- [ ] Create refusal response for unsafe outputs

### Guardrails Interface

```python
# src/guardrails/validators.py
from dataclasses import dataclass
from enum import Enum

class ValidationResult(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"

@dataclass
class GuardrailsResult:
    status: ValidationResult
    issues: list[str]
    sanitized_response: str | None  # If we need to modify the response

class ResponseValidator:
    def __init__(self, require_citations: bool = True):
        self.require_citations = require_citations

    def validate(self, response: RAGResponse) -> GuardrailsResult:
        """
        Validate RAG response for safety and grounding.

        Checks:
        1. Response has content
        2. Citations are present (if required)
        3. Response doesn't claim to have information not in chunks
        """
        issues = []

        # Check 1: Response has content
        if not response.answer or len(response.answer.strip()) < 10:
            issues.append("Response is empty or too short")

        # Check 2: Citations present
        if self.require_citations and response.has_relevant_content:
            if not self._has_citations(response.answer):
                issues.append("Response lacks citation markers")

        # Check 3: Basic hallucination check
        if response.has_relevant_content:
            hallucination_check = self._check_hallucination(response)
            if hallucination_check:
                issues.append(hallucination_check)

        # Determine status
        if not issues:
            status = ValidationResult.PASS
        elif any("hallucination" in i.lower() for i in issues):
            status = ValidationResult.FAIL
        else:
            status = ValidationResult.WARNING

        return GuardrailsResult(
            status=status,
            issues=issues,
            sanitized_response=self._sanitize_if_needed(response, issues)
        )

    def _has_citations(self, text: str) -> bool:
        """Check if response contains citation markers like [1], [2]."""
        import re
        return bool(re.search(r'\[\d+\]', text))

    def _check_hallucination(self, response: RAGResponse) -> str | None:
        """
        Basic hallucination check.
        More sophisticated checks would use NLI models.
        """
        # Check for phrases that indicate uncertain or made-up info
        suspicious_phrases = [
            "I believe",
            "I think",
            "probably",
            "might be",
            "it's possible that",
            "generally speaking",
        ]

        answer_lower = response.answer.lower()
        for phrase in suspicious_phrases:
            if phrase.lower() in answer_lower and not response.citation_chunks:
                return f"Possible hallucination: uses uncertain language '{phrase}' without citations"

        return None

    def _sanitize_if_needed(self, response: RAGResponse, issues: list[str]) -> str | None:
        """Return sanitized response if needed."""
        if any("hallucination" in i.lower() for i in issues):
            return "I cannot provide a reliable answer based on the available documents. Please rephrase your question."
        return None

# Convenience function
def get_refusal_response() -> RAGResponse:
    """Return standard refusal response."""
    return RAGResponse(
        answer="I cannot answer based on the provided documents.",
        citation_chunks=[],
        confidence=Confidence.LOW,
        has_relevant_content=False
    )
```

### Acceptance Criteria

- [ ] Schema validation catches malformed responses
- [ ] Citation check detects missing citations
- [ ] Basic hallucination patterns are flagged
- [ ] Failed validation returns sanitized response
- [ ] Refusal response is properly formatted

### Files to Create

1. `src/guardrails/__init__.py`
2. `src/guardrails/validators.py`

### Test Cases

```python
def test_valid_response():
    response = RAGResponse(
        answer="According to [1], the payment is due in 30 days.",
        citation_chunks=[mock_chunk],
        confidence=Confidence.HIGH,
        has_relevant_content=True
    )
    result = validator.validate(response)
    assert result.status == ValidationResult.PASS

def test_missing_citations():
    response = RAGResponse(
        answer="The payment is due in 30 days.",
        citation_chunks=[mock_chunk],
        confidence=Confidence.HIGH,
        has_relevant_content=True
    )
    result = validator.validate(response)
    assert "citation" in result.issues[0].lower()

def test_hallucination_detection():
    response = RAGResponse(
        answer="I think it might be 30 days, probably.",
        citation_chunks=[],
        confidence=Confidence.LOW,
        has_relevant_content=True
    )
    result = validator.validate(response)
    assert result.status == ValidationResult.FAIL
```

---

## Definition of Done (Epic 3)

- [ ] All 5 User Stories completed
- [ ] Retrieval returns relevant chunks with scores
- [ ] Context is properly formatted with citations
- [ ] Ollama generates grounded responses
- [ ] Complete RAG pipeline works end-to-end
- [ ] Guardrails validate and sanitize outputs
- [ ] Integration test: query → grounded answer with citations
