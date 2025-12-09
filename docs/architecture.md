# Architecture Overview

Technical architecture and design decisions for Lexard.

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Client Layer                          │
│  ┌─────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐  │
│  │ Web UI  │   │ REST API │   │   MCP    │   │   CLI    │  │
│  └────┬────┘   └─────┬────┘   └────┬─────┘   └────┬─────┘  │
└───────┼──────────────┼─────────────┼──────────────┼─────────┘
        │              │             │              │
        └──────────────┴─────────────┴──────────────┘
                       │
        ┌──────────────▼──────────────┐
        │      FastAPI Application     │
        │  ┌────────────────────────┐ │
        │  │    Middleware Layer    │ │
        │  │  - Request ID          │ │
        │  │  - Error Handler       │ │
        │  │  - CORS                │ │
        │  └────────────────────────┘ │
        └──────────────┬──────────────┘
                       │
        ┌──────────────▼──────────────┐
        │      Agent Layer             │
        │  ┌────────────────────────┐ │
        │  │   LangGraph Agent      │ │
        │  │  - Intent Classifier   │ │
        │  │  - State Machine       │ │
        │  │  - Tool Orchestration  │ │
        │  └────────────────────────┘ │
        │       │           │          │
        │   ┌───▼───┐   ┌──▼─────┐   │
        │   │ Tools │   │ Memory │   │
        │   └───┬───┘   └────────┘   │
        └───────┼─────────────────────┘
                │
        ┌───────▼──────────────────────┐
        │      RAG Engine              │
        │  ┌────────────────────────┐ │
        │  │  1. Retriever          │ │
        │  │  2. Context Builder    │ │
        │  │  3. LLM Generator      │ │
        │  │  4. Guardrails         │ │
        │  └────────────────────────┘ │
        └──────────────┬───────────────┘
                       │
        ┌──────────────▼───────────────┐
        │      Data Layer              │
        │  ┌─────────┐   ┌──────────┐ │
        │  │ Qdrant  │   │  SQLite  │ │
        │  │(Vectors)│   │(Registry)│ │
        │  └─────────┘   └──────────┘ │
        └──────────────────────────────┘
                       │
        ┌──────────────▼───────────────┐
        │   External Services          │
        │  ┌─────────┐                 │
        │  │ Ollama  │  (Mistral 7B)   │
        │  └─────────┘                 │
        └──────────────────────────────┘
```

## Component Details

### 1. API Layer (FastAPI)

**Responsibilities:**

- HTTP request handling
- Input validation (Pydantic schemas)
- Response serialization
- Error handling
- Authentication (future)

**Key Files:**

- `src/api/main.py` - Application entry point
- `src/api/routes/` - Endpoint definitions
- `src/api/schemas.py` - Pydantic models
- `src/api/middleware.py` - Request processing

**Design Patterns:**

- Dependency injection via `Depends()`
- Lazy loading of services
- Error handling via middleware

---

### 2. Agent Layer (LangGraph)

**Responsibilities:**

- Intent classification
- Tool selection and execution
- Multi-step reasoning
- State management

**Key Files:**

- `src/agent/graph.py` - LangGraph state machine
- `src/agent/classifier.py` - Intent classification
- `src/agent/state.py` - Agent state definition
- `src/agent/tools/` - Tool implementations

**Flow:**

```
User Query
    │
    ▼
Intent Classifier
    │
    ├─► summarize → Summarizer Tool
    ├─► answer_question → RAG Search
    ├─► risk_analysis → Risk Detector
    ├─► compare_documents → Diff Tool
    └─► refuse → Reject
```

**Intents:**

- `summarize` - Document summarization
- `answer_question` - RAG-powered Q&A
- `risk_analysis` - Risk detection
- `compare_documents` - Document comparison
- `refuse` - Out-of-scope rejection

---

### 3. RAG Engine

**Responsibilities:**

- Document ingestion and chunking
- Embedding generation
- Vector similarity search
- Context building
- LLM prompting
- Citation extraction

**Pipeline:**

```
1. Query Embeddings
   ├─► sentence-transformers
   └─► 768-dim vector

2. Retrieval (Qdrant)
   ├─► HNSW search
   ├─► top_k=8
   └─► score_threshold=0.4

3. Context Building
   ├─► Deduplicate chunks
   ├─► Sort by score
   └─► Format for LLM

4. Generation (Ollama)
   ├─► System prompt
   ├─► Context + Question
   └─► Generate answer

5. Citation Extraction
   ├─► Map answer → chunks
   └─► Return references
```

**Key Files:**

- `src/rag/pipeline.py` - Main pipeline
- `src/rag/retriever.py` - Vector search
- `src/rag/embeddings.py` - Embedding service
- `src/rag/context.py` - Context building
- `src/rag/llm.py` - LLM client and language detection
- `src/rag/chunking.py` - Text chunking
- `src/agent/prompts.py` - Bilingual prompt templates

---

### 4. Guardrails Layer

**Responsibilities:**

- Input validation (prompt injection)
- Output validation (hallucination)
- PII redaction
- Schema validation
- Metrics collection

**Pipeline:**

```
Input Validation:
  Query → Injection Detection → [Block or Pass]

Output Validation:
  1. Schema Validation
  2. Hallucination Detection (grounding check)
  3. PII Redaction
  4. Return validated response
```

**Key Files:**

- `src/guardrails/__init__.py` - Pipeline
- `src/guardrails/prompt_injection.py` - Input validation
- `src/guardrails/hallucination.py` - Grounding check
- `src/guardrails/pii.py` - PII filtering
- `src/guardrails/schema.py` - Schema validation

**Hallucination Detection:**

Uses semantic similarity between answer and citations:

```python
answer_embedding = model.encode(answer)
chunk_embeddings = model.encode(citation_chunks)
max_similarity = max(cosine_similarity(answer_embedding, chunk_embeddings))

if max_similarity < threshold:
    reject_as_hallucinated()
```

---

### 5. Data Layer

#### Qdrant (Vector Database)

**Purpose:** Store and search document embeddings

**Configuration:**

- Collection: `documents`
- Vector size: 768 dimensions
- Distance: Cosine similarity
- Index: HNSW (Hierarchical Navigable Small World)

**Schema:**

```python
{
    "id": "chunk-uuid",
    "vector": [0.1, 0.2, ..., 0.768],  # 768 dims
    "payload": {
        "document_id": "doc-uuid",
        "content": "chunk text",
        "page": 5,
        "chunk_index": 12,
        "source_title": "contract.pdf"
    }
}
```

#### SQLite (Document Registry)

**Purpose:** Track document metadata

**Schema:**

```sql
CREATE TABLE documents (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    filename TEXT NOT NULL,
    file_hash TEXT NOT NULL,
    page_count INTEGER,
    chunk_count INTEGER,
    version INTEGER DEFAULT 1,
    parent_document_id TEXT,
    uploaded_at TEXT NOT NULL,
    status TEXT DEFAULT 'pending'
);
```

**Statuses:**

- `pending` - Uploaded but not processed
- `processing` - Currently being indexed
- `processed` - Ready for queries
- `failed` - Processing error

---

### 6. External Services

#### LLM Service (Ollama or llama-server)

**Purpose:** Local LLM inference

**Model:** Mistral 7B Instruct

- Parameters: 7 billion
- Context window: 8k tokens
- Format: Instruct-tuned

**Option A: Ollama (Recommended)**

```bash
POST http://localhost:11434/api/generate
{
  "model": "mistral:7b-instruct",
  "prompt": "...",
  "stream": false
}
```

**Option B: llama-server (AMD RDNA4 Workaround)**

> AMD RDNA4 GPUs (gfx1201) have a ROCm HIP backend bug causing 100% idle GPU usage with Ollama. Use llama-server with Vulkan instead.

```bash
POST http://localhost:8080/v1/chat/completions
{
  "model": "mistral",
  "messages": [{"role": "user", "content": "..."}],
  "stream": false
}
```

See [Quickstart - AMD GPU Setup](quickstart.md#amd-gpu-setup-vulkan) for setup instructions.

---

## Design Decisions

### 1. Sovereignty First

**Decision:** No external API calls

**Rationale:**

- Data privacy for contract analysis
- No vendor lock-in
- Predictable costs
- Offline operation

**Implementation:**

- Local LLM (Ollama or llama-server)
- Local embeddings (sentence-transformers)
- Local vector DB (Qdrant)

---

### 2. Chunking Strategy

**Decision:** Fixed-size chunking with overlap

**Parameters:**

- Chunk size: 512 tokens
- Overlap: 50 tokens

**Rationale:**

- Simple and predictable
- Good balance of context vs. precision
- Overlap prevents information loss at boundaries

**Alternative considered:**

- Semantic chunking (rejected: too slow, less predictable)

---

### 3. Retrieval Strategy

**Decision:** Dense retrieval only (no hybrid)

**Parameters:**

- top_k: 8 chunks
- score_threshold: 0.4 (tuned for cross-lingual retrieval with multilingual-e5-base)

**Rationale:**

- Sufficient for contract analysis
- Faster than hybrid
- Less complex

**Future enhancement:**

- Add BM25 for hybrid search

---

### 4. Guardrails Approach

**Decision:** Post-generation validation

**Rationale:**

- More flexible than constrained generation
- Can retry on failure
- Better for hallucination detection

**Tradeoff:**

- Slower (requires retry)
- But: higher quality

---

### 5. Agent Architecture

**Decision:** LangGraph state machine

**Rationale:**

- Clear control flow
- Easy to debug
- Deterministic behavior
- Better than ReAct for this use case

**Flow:**

```
User Input → Classify Intent → Route to Tool → Execute → Return
```

---

## Performance Optimizations

### 1. Embedding Caching

Cache frequently queried embeddings:

```python
@lru_cache(maxsize=1000)
def embed_with_cache(text: str) -> list[float]:
    return model.encode(text)
```

### 2. Connection Pooling

Reuse HTTP connections to Ollama:

```python
client = httpx.Client(limits=httpx.Limits(max_connections=10))
```

### 3. Batch Processing

Process embeddings in batches:

```python
# Instead of: [embed(t) for t in texts]
embeddings = model.encode(texts, batch_size=32)
```

### 4. Lazy Loading

Load heavy models only when needed:

```python
def get_embedding_service():
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
```

---

## Scalability Considerations

### Vertical Scaling

- **CPU:** More cores → more workers
- **RAM:** Larger batches, more cache
- **GPU:** Faster embeddings (10x speedup)

### Horizontal Scaling

Current: Single-instance only

**To support multiple instances:**

1. **Shared Qdrant:** Deploy Qdrant as separate service
2. **Shared SQLite:** Migrate to PostgreSQL
3. **Load Balancer:** Distribute requests
4. **Session affinity:** Not required (stateless)

---

## Security Architecture

### Current

- No authentication (MVP)
- CORS enabled for all origins (dev)
- No rate limiting

### Production Requirements

1. **Authentication:** API keys or OAuth2
2. **Authorization:** Role-based access control
3. **Rate Limiting:** nginx or API middleware
4. **HTTPS:** TLS certificates required
5. **Input Sanitization:** Already implemented
6. **PII Redaction:** Already implemented

---

## Monitoring & Observability

### Metrics Exposed

- `/health` - Service health
- `/guardrails/metrics` - Validation stats
- `/performance/metrics` - Operation timings

### Logging

Structured JSON logs:

```json
{
  "timestamp": "2025-12-05T10:30:00Z",
  "level": "info",
  "message": "Document processed",
  "trace_id": "abc123",
  "document_id": "xyz789",
  "duration_ms": 1250
}
```

### Future Enhancements

- Prometheus metrics export
- OpenTelemetry tracing
- Error tracking (Sentry)

---

## Future Architecture Evolution

### Phase 1: Current (MVP)

- Single document queries
- Basic guardrails
- Local deployment

### Phase 2: Enhanced

- Multi-document queries
- Advanced reranking
- API authentication
- Streaming responses

### Phase 3: Enterprise

- Multi-tenant support
- Distributed deployment
- Custom model fine-tuning
- Advanced analytics

---

## Next Steps

- [API Reference](api.md) - REST API documentation
- [Development Guide](development.md) - Development setup
- [Deployment Guide](deployment.md) - Production deployment
