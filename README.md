# Lexard

**Sovereign, self-hosted AI contract analysis powered by RAG**

Lexard is a B2B document intelligence solution that provides contract analysis, risk detection, Q&A with citations, and document comparison - all running locally without external API dependencies.

## Features

- **Document Ingestion** - Upload and process PDF, DOCX, and TXT files
- **RAG-Powered Q&A** - Ask questions about contracts with cited sources
- **Risk Analysis** - Identify legal, financial, and operational risks
- **Document Summarization** - Generate executive or detailed summaries
- **Document Comparison** - Compare two contracts and identify differences
- **Guardrails** - Hallucination detection, PII redaction, prompt injection blocking
- **Sovereign Architecture** - No external APIs, all processing runs locally

## Quick Start

Get Lexard running in 5 minutes:

```bash
# Clone repository
git clone https://github.com/yourusername/lexard.git
cd lexard

# Start services
docker-compose up -d

# Pull LLM model
docker exec -it lexard-ollama ollama pull mistral:7b-instruct

# Create virtual environment (required on macOS)
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"

# Start API
uvicorn src.api.main:app --reload
```

Visit [http://localhost:8000](http://localhost:8000) to use the web interface.

## Architecture

```
┌─────────────┐
│   Web UI    │
└──────┬──────┘
       │
┌──────▼──────────┐
│   FastAPI       │
│   REST API      │
└──────┬──────────┘
       │
┌──────▼──────────┐      ┌─────────────┐
│   LangGraph     │──────│   Ollama    │
│   Agent         │      │  (Mistral)  │
└──────┬──────────┘      └─────────────┘
       │
┌──────▼──────────┐      ┌─────────────┐
│   RAG Engine    │──────│   Qdrant    │
│   + Guardrails  │      │  (Vectors)  │
└─────────────────┘      └─────────────┘
```

**Tech Stack:**
- **Backend:** Python 3.11, FastAPI
- **Agent:** LangChain + LangGraph
- **Vector DB:** Qdrant (HNSW, cosine similarity)
- **Embeddings:** sentence-transformers `all-mpnet-base-v2`
- **LLM:** Ollama `mistral:7b-instruct` (local, no external APIs)
- **Guardrails:** guardrails-ai + custom validators
- **Storage:** SQLite (document registry), local filesystem

## API Examples

### Upload a Document

```bash
curl -X POST http://localhost:8000/upload \
  -F "file=@contract.pdf"
```

### Ask a Question

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "document_id": "your-document-id",
    "question": "What is the termination notice period?"
  }'
```

Response:

```json
{
  "answer": "The termination notice period is 30 days...",
  "confidence": "high",
  "citation_chunks": [
    {
      "content": "Either party may terminate with 30 days notice...",
      "page": 5,
      "score": 0.89
    }
  ]
}
```

### Analyze Risks

```bash
curl -X POST http://localhost:8000/risks \
  -H "Content-Type: application/json" \
  -d '{"document_id": "your-document-id"}'
```

### Compare Documents

```bash
curl -X POST http://localhost:8000/compare \
  -H "Content-Type: application/json" \
  -d '{
    "doc_a": "document-id-1",
    "doc_b": "document-id-2"
  }'
```

## Documentation

- **[Quickstart Guide](docs/quickstart.md)** - Get started in 5 minutes
- **[API Reference](docs/api.md)** - Complete REST API documentation
- **[Configuration Guide](docs/configuration.md)** - Configuration options
- **[Development Guide](docs/development.md)** - Development setup
- **[Deployment Guide](docs/deployment.md)** - Production deployment
- **[Troubleshooting](docs/troubleshooting.md)** - Common issues and solutions

## Interactive API Documentation

Once running, visit:

- **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)

## Requirements

- Python 3.11+
- Docker & Docker Compose
- 8GB RAM minimum (16GB recommended)
- 50GB disk space (for models and data)
- macOS, Linux, or Windows with WSL2

## Project Status

Lexard is under active development. Current phase: **Epic 6 - Hardening**

- ✅ Core ingestion pipeline
- ✅ RAG engine with citations
- ✅ LangGraph agent system
- ✅ REST API + Web UI + MCP server
- ✅ Advanced guardrails
- ✅ Evaluation harness
- ✅ Red team testing
- ✅ Performance optimization
- 🔶 Documentation (in progress)

See [tasks/PROGRESS.md](tasks/PROGRESS.md) for detailed status.

## Performance Targets

- **Query latency:** < 3s (P95, with local LLM)
- **Document ingestion:** < 15s for 10-page document
- **Embedding generation:** < 500ms per chunk
- **Concurrent requests:** 10 simultaneous queries
- **Hallucination detection:** 90%+ accuracy

## Security & Sovereignty

- **No external API calls** - All processing is local
- **PII redaction** - Automatic redaction of sensitive patterns (IBAN, SSN, etc.)
- **Prompt injection blocking** - Detects and blocks injection attempts
- **Hallucination detection** - Validates answers are grounded in source documents
- **Schema validation** - Ensures response consistency

## Development

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- Git

### Setup

```bash
# Clone and enter directory
git clone https://github.com/yourusername/lexard.git
cd lexard

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install with dev dependencies
pip install -e ".[dev]"

# Start services
docker-compose up -d

# Pull LLM model
docker exec -it lexard-ollama ollama pull mistral:7b-instruct

# Run tests
pytest tests/ -v

# Start development server
uvicorn src.api.main:app --reload
```

### Git Workflow

We use Gitflow:

```bash
# Create feature branch
git checkout -b feature/my-feature develop

# Make changes and commit
git commit -m "feat(scope): description"

# Push and create PR to develop
git push -u origin feature/my-feature
```

See [docs/development.md](docs/development.md) for details.

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch (`feature/amazing-feature`)
3. Follow conventional commits (`feat:`, `fix:`, `docs:`, etc.)
4. Write tests for new features
5. Ensure all tests pass: `pytest tests/ -v`
6. Submit a pull request to `develop`

## Roadmap

- [ ] Multi-document queries
- [ ] Custom risk categories
- [ ] Document versioning
- [ ] API authentication
- [ ] Multi-language support
- [ ] Advanced reranking
- [ ] Streaming responses

## License

MIT License - see [LICENSE](LICENSE) for details.

## Support

- **Documentation:** [docs/](docs/)
- **Issues:** [GitHub Issues](https://github.com/yourusername/lexard/issues)
- **Discussions:** [GitHub Discussions](https://github.com/yourusername/lexard/discussions)

## Acknowledgments

Built with:
- [FastAPI](https://fastapi.tiangolo.com/)
- [LangChain](https://www.langchain.com/)
- [LangGraph](https://www.langchain.com/langgraph)
- [Qdrant](https://qdrant.tech/)
- [Ollama](https://ollama.com/)
- [sentence-transformers](https://www.sbert.net/)

---

**Made with ❤️ for contract analysis without compromising data sovereignty**
