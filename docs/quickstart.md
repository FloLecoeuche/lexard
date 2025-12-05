# Quickstart Guide

Get Lexard running in 5 minutes.

## Prerequisites

- Docker & Docker Compose
- Python 3.11+
- 8GB RAM minimum
- macOS, Linux, or Windows with WSL2

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/lexard.git
cd lexard
```

### 2. Start backend services

```bash
docker-compose up -d
```

This starts:
- Qdrant (vector database) on port 6333
- Ollama (local LLM) on port 11434

### 3. Pull the LLM model

```bash
docker exec -it lexard-ollama ollama pull mistral:7b-instruct
```

This downloads the Mistral 7B model (~4.1GB). It may take a few minutes depending on your connection.

### 4. Set up Python environment

**Important:** On macOS, always use a virtual environment as system-wide pip installs are blocked.

```bash
# Create virtual environment
python -m venv .venv

# Activate it
source .venv/bin/activate  # macOS/Linux
# or on Windows: .venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"
```

### 5. Configure the application

```bash
# The config file should already exist, but verify:
cat config/config.yaml
```

The default configuration works for local development. See [Configuration Guide](configuration.md) for customization options.

### 6. Start the API server

```bash
uvicorn src.api.main:app --reload
```

The API will be available at `http://localhost:8000`.

### 7. Verify installation

Open another terminal and check the health endpoint:

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "ok",
  "services": {
    "qdrant": "healthy",
    "ollama": "healthy"
  }
}
```

## Your First Document

### Upload a document

```bash
curl -X POST http://localhost:8000/upload \
  -F "file=@/path/to/your/contract.pdf"
```

Response:
```json
{
  "document_id": "uuid-here",
  "title": "contract.pdf",
  "page_count": 10,
  "chunk_count": 45,
  "status": "indexed"
}
```

Save the `document_id` for the next step.

### Ask a question

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "document_id": "uuid-here",
    "question": "What is the termination notice period?"
  }'
```

Response:
```json
{
  "answer": "The termination notice period is 30 days...",
  "confidence": "high",
  "citations": [
    {
      "chunk_id": "chunk-123",
      "text": "Either party may terminate this agreement with 30 days written notice...",
      "score": 0.89,
      "page": 5
    }
  ]
}
```

### Generate a summary

```bash
curl -X POST http://localhost:8000/summarize \
  -H "Content-Type: application/json" \
  -d '{
    "document_id": "uuid-here"
  }'
```

### Analyze risks

```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "document_id": "uuid-here"
  }'
```

## Using the Web UI

Open your browser and navigate to:

```
http://localhost:8000
```

The web UI provides:
- Document upload interface
- Interactive question answering
- Document summarization
- Risk analysis visualization

## Next Steps

- [API Reference](api.md) - Complete API documentation
- [Configuration Guide](configuration.md) - Customize settings
- [Development Guide](development.md) - Set up for development
- [Deployment Guide](deployment.md) - Deploy to production

## Troubleshooting

### Services not starting

Check Docker services are running:
```bash
docker-compose ps
```

View logs:
```bash
docker-compose logs qdrant
docker-compose logs ollama
```

### Model not found error

Ensure the Mistral model is downloaded:
```bash
docker exec -it lexard-ollama ollama list
```

If not present, pull it again:
```bash
docker exec -it lexard-ollama ollama pull mistral:7b-instruct
```

### Connection refused errors

Verify services are healthy:
```bash
curl http://localhost:6333/healthz  # Qdrant
curl http://localhost:11434/api/tags  # Ollama
```

### Virtual environment issues on macOS

If you get "externally-managed-environment" errors, you're trying to install to system Python. Always activate the virtual environment first:
```bash
source .venv/bin/activate
```

For more issues, see the [Troubleshooting Guide](troubleshooting.md).
