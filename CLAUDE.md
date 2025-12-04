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

Progress is tracked in `PROGRESS.md` using Scrum-style Epics and User Stories.

### Current Phase: 1 – Foundation

See `PROGRESS.md` for detailed task status.

## Conventions

- **Commits:** Conventional commits (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`)
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

## Workflow Rules

- **NEVER use git commands without explicit user request** (no add, commit, push, etc.)
- Wait for user approval before any git operations
- Conventional commits format when asked: `type(scope): description`

## User Story Completion Rules

**CRITICAL: Every US must be verified by actual testing, not just implementation review.**

When completing a User Story:

1. **Test each acceptance criterion** with actual verification
2. **Document test results** before marking US as complete
3. **Never assume** acceptance criteria pass because tasks were implemented correctly
