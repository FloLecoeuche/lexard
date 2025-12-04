# Lexard - AI Contract Analyst

## Project Overview

Lexard is a sovereign, self-hosted B2B RAG solution for contract analysis. It ingests documents (PDF, DOCX, TXT), processes them through a vector database, and provides risk analysis, summaries, Q&A with citations, and document comparison.

## Tech Stack

- **Backend:** Python 3.11, FastAPI
- **Agent:** LangChain + LangGraph
- **Vector DB:** Qdrant (HNSW, cosine, 768-dim)
- **Embeddings:** sentence-transformers `all-mpnet-base-v2`
- **LLM:** Ollama `mistral:7b-instruct` (sovereign, no external APIs)
- **Guardrails:** guardrails-ai + regex filters
- **Storage:** SQLite (document registry), local filesystem
- **Interface:** MCP (JSON-RPC 2.0), REST API, minimal Web UI

## Key Architecture Decisions

1. **Sovereignty first:** No external API calls. Local LLM only. Graceful error on LLM unavailability (no cloud fallback).
2. **Chunking:** Fixed 512 tokens, 50 token overlap.
3. **Retrieval:** top_k=8, score_threshold=0.7. Return "I cannot find..." if no chunks meet threshold.
4. **Guardrails:** Validate all outputs. Block hallucinations, redact PII patterns (IBAN, SSN).

## API Endpoints

| Method | Endpoint   | Purpose                     |
| ------ | ---------- | --------------------------- |
| GET    | /health    | Service health check        |
| POST   | /upload    | Ingest document             |
| POST   | /query     | Ask question with citations |
| POST   | /summarize | Generate document summary   |
| POST   | /compare   | Compare two documents       |

## Agent Intents

- `summarize` → Summarizer tool
- `answer_question` → RAG Search
- `risk_analysis` → Risk Detector
- `compare_documents` → Diff Tool
- `refuse` → Reject out-of-scope

## Project Structure (Target)

```
lexard/
├── src/
│   ├── api/           # FastAPI routes
│   ├── agent/         # LangGraph state machine
│   ├── rag/           # Retrieval, embeddings, chunking
│   ├── guardrails/    # Output validation
│   ├── mcp/           # MCP server
│   └── db/            # Qdrant + SQLite
├── ui/                # Minimal web interface
├── tests/
├── config/
│   └── config.yaml
├── docker-compose.yml
└── PRD.md
```

## Development Tracking

Progress is tracked in `tasks/PROGRESS.md` using Epics and User Stories.

### Current Phase

See `tasks/PROGRESS.md` for detailed task status.

## Development Workflow

### Before Starting Any Epic

1. Ensure all previous epic US are complete
2. Run `docker-compose up -d` and verify services are healthy
3. Check `/health` endpoint responds (after US 1.3)

### Working on a User Story

1. **Read** the complete US file in `tasks/epic-X-*.md`
2. **Verify** prerequisites (previous US completed, services running)
3. **Implement** tasks in order (they may have dependencies)
4. **Test** each acceptance criterion with actual verification
5. **Document** test results before marking complete
6. **Update** US status to ✅ in the epic file
7. **Update** `tasks/PROGRESS.md` with completion info

**Checklist before marking complete:**

- [ ] Feature works end-to-end (manual test)
- [ ] Code runs without errors
- [ ] No hardcoded values (use config)
- [ ] All acceptance criteria verified (never assume)

## Code Patterns

### Async I/O

All external calls (Qdrant, Ollama, file I/O) must use async/await.

### Dependency Injection

Use FastAPI `Depends()` for services:

```python
@app.get("/health")
async def health(settings: Settings = Depends(get_settings)):
    ...
```

### Type Hints

Required on all function signatures:

```python
async def query_documents(question: str, doc_id: UUID) -> QueryResponse:
    ...
```

### Imports

Group in order: stdlib → third-party → local. One blank line between groups.

```python
import os
from uuid import UUID

from fastapi import FastAPI, Depends
from pydantic import BaseModel

from src.config import get_settings
from src.api.schemas import QueryResponse
```

## Error Handling

Use custom exceptions from `src/api/exceptions.py`:

| Exception               | HTTP Status | When                      |
| ----------------------- | ----------- | ------------------------- |
| `DocumentNotFoundError` | 404         | Document ID doesn't exist |
| `DocumentParseError`    | 422         | Failed to extract text    |
| `LLMUnavailableError`   | 503         | Ollama not responding     |
| `ValidationError`       | 400         | Invalid request data      |

Always return the standard error schema:

```json
{
  "error": {
    "code": "DOCUMENT_NOT_FOUND",
    "message": "Document with ID xyz not found",
    "trace_id": "uuid"
  }
}
```

## Common Pitfalls

1. **Don't import heavy models at module level** — lazy load sentence-transformers to avoid slow startup
2. **Don't block the event loop** — use `run_in_executor` for CPU-bound work (embeddings generation)
3. **Don't hardcode paths/URLs** — always use config
4. **Don't skip service availability checks** — verify Qdrant/Ollama before operations
5. **Don't forget trace_id** — include in all error responses and logs

## Conventions

- **Config:** All settings externalized to `config/config.yaml`
- **Logging:** JSON structured logs with trace_id
- **Errors:** Consistent error schema with code, message, trace_id

## Quick Commands

```bash
# Start services
docker-compose up -d

# Run API
uvicorn src.api.main:app --reload

# Run tests
pytest tests/ -v
```

## Critical Constraints

- Never make external API calls (sovereignty)
- Always provide citations for answers
- Block hallucinations (target: 90%+ detection)
- Max file size: 50MB
- Response time: <3s for queries, <15s for ingestion (10 pages)

## Git Workflow (Gitflow)

### Branch Structure

| Branch           | Purpose               | Merges to |
| ---------------- | --------------------- | --------- |
| `main`           | Production-ready code | —         |
| `develop`        | Integration branch    | `main`    |
| `feature/<name>` | New features          | `develop` |
| `fix/<name>`     | Bug fixes             | `develop` |

### Branch Naming

- Features: `feature/us-1.1-repository-structure`
- Fixes: `fix/config-loading-error`
- Use US number when applicable

### Workflow

1. **Create feature branch** from `develop`: `git checkout -b feature/us-X.X-name develop`
2. **Implement** the User Story
3. **Ask user** before any commit
4. **Commit** with conventional format: `type(scope): description`
5. **Ask user** before merge to `develop`
6. **Delete** feature branch after merge

### Rules

- **NEVER** commit, merge, or push without explicit user approval
- **NEVER** work directly on `main` or `develop`
- **ALWAYS** ask before any git operation
- **ALWAYS** use conventional commits: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`

## File Naming

| Type        | Convention         | Example                   |
| ----------- | ------------------ | ------------------------- |
| Modules     | `snake_case.py`    | `document_parser.py`      |
| Classes     | `PascalCase`       | `DocumentParser`          |
| Constants   | `UPPER_SNAKE_CASE` | `MAX_FILE_SIZE`           |
| Test files  | `test_<module>.py` | `test_document_parser.py` |
| Config keys | `snake_case`       | `max_file_size_mb`        |
