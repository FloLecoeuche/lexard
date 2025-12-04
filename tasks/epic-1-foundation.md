# Epic 1: Foundation

## Overview

Set up the base infrastructure for the Lexard project including repository structure, Docker services, FastAPI skeleton, and configuration management.

## Prerequisites

- Python 3.11+
- Docker & Docker Compose
- Git repository initialized

## User Stories

---

## US 1.1: Repository Structure

**Status:** 🔲 Not Started

### Description

Create the base directory structure and Python package initialization for the Lexard project.

### Context

Lexard is a B2B RAG solution for contract analysis. The project uses:

- FastAPI for the API layer
- LangChain + LangGraph for RAG and agent orchestration
- Qdrant for vector storage
- Ollama for local LLM inference

### Tasks

- [ ] Create directory structure:
  ```
  lexard/
  ├── src/
  │   ├── __init__.py
  │   ├── api/
  │   │   └── __init__.py
  │   ├── agent/
  │   │   └── __init__.py
  │   ├── rag/
  │   │   └── __init__.py
  │   ├── guardrails/
  │   │   └── __init__.py
  │   ├── mcp/
  │   │   └── __init__.py
  │   └── db/
  │       └── __init__.py
  ├── tests/
  │   └── __init__.py
  ├── config/
  ├── ui/
  └── data/
      └── uploads/
  ```
- [ ] Create `.gitignore` for Python/Docker with entries for:
  - `__pycache__/`, `*.pyc`, `.pytest_cache/`
  - `.env`, `*.env`
  - `data/uploads/*` (but keep `data/uploads/.gitkeep`)
  - `.venv/`, `venv/`
  - `*.db`, `*.sqlite`
  - `.idea/`, `.vscode/`
- [ ] Create `data/uploads/.gitkeep` to preserve empty directory
- [ ] Create `pyproject.toml` with project metadata and dependencies

### Dependencies (pyproject.toml)

```toml
[project]
name = "lexard"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.104.0",
    "uvicorn[standard]>=0.24.0",
    "pydantic>=2.5.0",
    "pydantic-settings>=2.1.0",
    "pyyaml>=6.0",
    "langchain>=0.1.0",
    "langgraph>=0.0.40",
    "sentence-transformers>=2.2.0",
    "qdrant-client>=1.7.0",
    "pdfminer.six>=20221105",
    "python-docx>=1.1.0",
    "tiktoken>=0.5.0",
    "python-multipart>=0.0.6",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.21.0",
    "httpx>=0.25.0",
]
```

### Acceptance Criteria

- [ ] All directories exist with `__init__.py` files
- [ ] `.gitignore` correctly excludes Python artifacts and data files
- [ ] `pyproject.toml` is valid and can be used with `pip install -e .`
- [ ] Running `python -c "import src"` works without error

### Files to Create

1. `src/__init__.py`
2. `src/api/__init__.py`
3. `src/agent/__init__.py`
4. `src/rag/__init__.py`
5. `src/guardrails/__init__.py`
6. `src/mcp/__init__.py`
7. `src/db/__init__.py`
8. `tests/__init__.py`
9. `data/uploads/.gitkeep`
10. `.gitignore`
11. `pyproject.toml`

---

## US 1.2: Docker Compose Setup

**Status:** 🔲 Not Started

### Description

Create Docker Compose configuration to run Qdrant and Ollama services locally.

### Context

- **Qdrant**: Vector database for storing document embeddings
  - Port: 6333 (HTTP), 6334 (gRPC)
  - Needs persistent volume for data
- **Ollama**: Local LLM inference server
  - Port: 11434
  - Default model: `mistral:7b-instruct`
  - Needs volume for model storage

### Tasks

- [ ] Create `docker-compose.yml` with:
  - Qdrant service (qdrant/qdrant:latest)
  - Ollama service (ollama/ollama:latest)
  - Named volumes for persistence
  - Health checks
- [ ] Create `docker-compose.override.yml.example` for local customizations
- [ ] Add docker volumes to `.gitignore` if needed

### Docker Compose Specification

```yaml
version: '3.8'

services:
  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - '6333:6333'
      - '6334:6334'
    volumes:
      - qdrant_data:/qdrant/storage
    environment:
      - QDRANT__SERVICE__GRPC_PORT=6334
    healthcheck:
      test: ['CMD', 'curl', '-f', 'http://localhost:6333/health']
      interval: 30s
      timeout: 10s
      retries: 3

  ollama:
    image: ollama/ollama:latest
    ports:
      - '11434:11434'
    volumes:
      - ollama_data:/root/.ollama
    healthcheck:
      test: ['CMD', 'curl', '-f', 'http://localhost:11434/api/tags']
      interval: 30s
      timeout: 10s
      retries: 3

volumes:
  qdrant_data:
  ollama_data:
```

### Acceptance Criteria

- [ ] `docker-compose up -d` starts both services without error
- [ ] Qdrant is accessible at http://localhost:6333
- [ ] Ollama is accessible at http://localhost:11434
- [ ] Data persists after `docker-compose down` and `docker-compose up`
- [ ] Health checks pass for both services

### Files to Create

1. `docker-compose.yml`
2. `docker-compose.override.yml.example`

### Verification Commands

```bash
# Start services
docker-compose up -d

# Check health
curl http://localhost:6333/health
curl http://localhost:11434/api/tags

# Pull default model (run once)
docker exec -it lexard-ollama-1 ollama pull mistral:7b-instruct
```

---

## US 1.3: FastAPI Skeleton

**Status:** 🔲 Not Started

### Description

Create the base FastAPI application with health endpoint, CORS configuration, structured logging, and error handling middleware.

### Context

The API will serve:

- Document upload and processing
- RAG queries with citations
- Document summarization and comparison
- MCP interface (separate endpoint)

### Tasks

- [ ] Create `src/api/main.py` with FastAPI app
- [ ] Implement `GET /health` endpoint returning service status
- [ ] Configure CORS for local development
- [ ] Create `src/api/middleware.py` with:
  - Request ID middleware (adds trace_id to each request)
  - Error handling middleware
- [ ] Create `src/api/logging.py` with JSON structured logging
- [ ] Create `src/api/schemas.py` with base response models
- [ ] Create `src/api/exceptions.py` with custom exceptions

### API Specifications

**GET /health**

```json
{
  "status": "healthy",
  "version": "0.1.0",
  "services": {
    "qdrant": "connected" | "disconnected",
    "ollama": "connected" | "disconnected"
  }
}
```

**Error Response Schema**

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable message",
    "trace_id": "uuid"
  }
}
```

### Logging Format

```json
{
  "timestamp": "2025-12-04T10:30:00Z",
  "level": "info",
  "trace_id": "uuid",
  "event": "request_received",
  "method": "GET",
  "path": "/health",
  "duration_ms": 12
}
```

### Acceptance Criteria

- [ ] `uvicorn src.api.main:app --reload` starts the server
- [ ] `GET /health` returns 200 with status JSON
- [ ] All requests have a `X-Trace-ID` response header
- [ ] Errors return consistent JSON format with trace_id
- [ ] Logs are JSON formatted with trace_id

### Files to Create

1. `src/api/main.py`
2. `src/api/middleware.py`
3. `src/api/logging.py`
4. `src/api/schemas.py`
5. `src/api/exceptions.py`

### Code Structure

```python
# src/api/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Lexard", version="0.1.0")

# CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    ...
```

---

## US 1.4: Configuration Management

**Status:** 🔲 Not Started

### Description

Implement externalized configuration using YAML files with Pydantic validation and environment variable overrides.

### Context

All settings should be configurable without code changes:

- LLM provider and model settings
- Embeddings model configuration
- Chunking parameters
- Qdrant connection details
- Retrieval parameters
- Server settings

### Tasks

- [ ] Create `config/config.yaml` with all settings
- [ ] Create `config/config.example.yaml` (template without secrets)
- [ ] Create `src/config.py` with Pydantic settings models
- [ ] Implement config loader that:
  - Loads from YAML file
  - Allows environment variable overrides (prefix: `LEXARD_`)
  - Validates all settings
- [ ] Add config to `.gitignore` but keep example

### Configuration Schema

```yaml
# config/config.yaml
app:
  name: 'Lexard'
  environment: 'development' # development | production
  log_level: 'info' # debug | info | warning | error

llm:
  provider: 'ollama'
  model: 'mistral:7b-instruct'
  base_url: 'http://localhost:11434'
  temperature: 0.1
  max_tokens: 2048
  timeout_seconds: 30

embeddings:
  model: 'all-mpnet-base-v2'
  batch_size: 32
  device: 'cpu' # cpu | cuda

chunking:
  method: 'fixed'
  size: 512
  overlap: 50

qdrant:
  host: 'localhost'
  port: 6333
  collection: 'documents'

retrieval:
  top_k: 8
  score_threshold: 0.7
  rerank: false

guardrails:
  hallucination_threshold: 0.8
  enable_pii_filter: true
  max_retries: 2

storage:
  upload_dir: './data/uploads'
  max_file_size_mb: 50

server:
  host: '0.0.0.0'
  port: 8000
  workers: 4
```

### Pydantic Models

```python
# src/config.py
from pydantic import BaseModel
from pydantic_settings import BaseSettings

class AppConfig(BaseModel):
    name: str = "Lexard"
    environment: str = "development"
    log_level: str = "info"

class LLMConfig(BaseModel):
    provider: str = "ollama"
    model: str = "mistral:7b-instruct"
    base_url: str = "http://localhost:11434"
    temperature: float = 0.1
    max_tokens: int = 2048
    timeout_seconds: int = 30

# ... other config classes

class Settings(BaseSettings):
    app: AppConfig = AppConfig()
    llm: LLMConfig = LLMConfig()
    # ... other configs

    class Config:
        env_prefix = "LEXARD_"
        env_nested_delimiter = "__"
```

### Environment Variable Override Examples

```bash
LEXARD_APP__ENVIRONMENT=production
LEXARD_LLM__MODEL=llama3:8b
LEXARD_QDRANT__HOST=qdrant.production.local
```

### Acceptance Criteria

- [ ] `config/config.yaml` exists with all settings
- [ ] `from src.config import get_settings` works
- [ ] Settings are validated (invalid values raise errors)
- [ ] Environment variables override YAML values
- [ ] Missing config file raises clear error message

### Files to Create

1. `config/config.yaml`
2. `config/config.example.yaml`
3. `src/config.py`

### Verification

```python
from src.config import get_settings

settings = get_settings()
assert settings.llm.model == "mistral:7b-instruct"
assert settings.qdrant.port == 6333
```

---

## Definition of Done (Epic 1)

- [ ] All 4 User Stories completed
- [ ] `docker-compose up -d` starts Qdrant and Ollama
- [ ] `uvicorn src.api.main:app` starts the API
- [ ] `/health` endpoint works and checks service connectivity
- [ ] Configuration loads from YAML with env overrides
- [ ] All code follows Python best practices
