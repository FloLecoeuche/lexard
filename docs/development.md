# Development Guide

Set up Lexard for local development and contribute to the project.

## Prerequisites

- Python 3.11 or later
- Docker & Docker Compose
- Git
- 8GB RAM minimum
- macOS, Linux, or Windows with WSL2

## Initial Setup

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/lexard.git
cd lexard
```

### 2. Create virtual environment

**Important for macOS users:** Always use a virtual environment as system-wide pip installs are blocked.

```bash
# Create virtual environment
python -m venv .venv

# Activate it
source .venv/bin/activate  # macOS/Linux
# or on Windows:
.venv\Scripts\activate
```

### 3. Install dependencies

```bash
# Install all dependencies including dev tools
pip install -e ".[dev]"
```

This installs:
- Core dependencies (FastAPI, LangChain, etc.)
- Development tools (pytest, black, ruff, mypy)
- The project in editable mode

### 4. Start backend services

```bash
docker-compose up -d
```

This starts:
- **Qdrant** on port 6333 (vector database)
- **Ollama** on port 11434 (local LLM)

### 5. Pull the LLM model

```bash
docker exec -it lexard-ollama ollama pull mistral:7b-instruct
```

### 6. Configure the application

The configuration file should already exist at `config/config.yaml`. Verify it:

```bash
cat config/config.yaml
```

For development, the defaults work fine.

### 7. Run the application

```bash
uvicorn src.api.main:app --reload
```

The API will be available at `http://localhost:8000`.

---

## Project Structure

```
lexard/
├── src/
│   ├── api/              # FastAPI application
│   │   ├── main.py       # App entry point
│   │   ├── routes/       # API endpoints
│   │   ├── schemas.py    # Pydantic models
│   │   ├── exceptions.py # Custom exceptions
│   │   └── middleware.py # Request middleware
│   ├── agent/            # LangGraph agent system
│   │   ├── graph.py      # State machine
│   │   ├── intent.py     # Intent classifier
│   │   └── tools/        # Agent tools
│   ├── rag/              # RAG engine
│   │   ├── pipeline.py   # RAG pipeline
│   │   ├── retriever.py  # Vector retrieval
│   │   ├── embeddings.py # Embedding generation
│   │   ├── chunking.py   # Text chunking
│   │   ├── context.py    # Context building
│   │   ├── llm.py        # LLM client
│   │   └── extractors/   # Text extractors
│   ├── guardrails/       # Output validation
│   │   ├── __init__.py   # Pipeline
│   │   ├── hallucination.py
│   │   ├── pii.py
│   │   ├── schema.py
│   │   └── prompt_injection.py
│   ├── mcp/              # MCP server
│   │   └── server.py
│   ├── db/               # Database services
│   │   ├── qdrant.py     # Vector DB
│   │   └── sqlite.py     # Document registry
│   └── config.py         # Configuration management
├── ui/                   # Web interface
│   └── static/
│       ├── index.html
│       └── style.css
├── tests/                # Test suite
│   ├── evaluation/       # Evaluation harness
│   ├── red_team/         # Adversarial tests
│   ├── performance/      # Benchmarks
│   └── unit/             # Unit tests
├── tasks/                # User stories & progress
│   ├── PROGRESS.md
│   └── epic-*.md
├── config/
│   └── config.yaml       # Configuration file
├── data/                 # Data directory
│   ├── uploads/          # Uploaded files
│   └── eval/             # Evaluation datasets
├── docker-compose.yml    # Service orchestration
├── pyproject.toml        # Python dependencies
└── README.md
```

---

## Development Workflow

### Git Workflow (Gitflow)

We use Gitflow for branch management:

**Branches:**
- `main` - Production-ready code
- `develop` - Integration branch
- `feature/<name>` - New features
- `fix/<name>` - Bug fixes

**Creating a feature branch:**

```bash
# Start from develop
git checkout develop
git pull

# Create feature branch
git checkout -b feature/us-X.X-short-description

# Make changes and commit
git add .
git commit -m "feat(scope): description"

# Push and create PR
git push -u origin feature/us-X.X-short-description
```

**Conventional Commits:**

Use conventional commit format:

```
type(scope): description

Types:
- feat: New feature
- fix: Bug fix
- docs: Documentation
- refactor: Code refactoring
- test: Tests
- chore: Maintenance
```

Examples:

```bash
git commit -m "feat(api): add document comparison endpoint"
git commit -m "fix(rag): handle empty query results"
git commit -m "docs(api): update endpoint descriptions"
git commit -m "refactor(embeddings): optimize batch processing"
git commit -m "test(guardrails): add PII redaction tests"
```

---

## Running Tests

### Unit Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/unit/test_chunking.py -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html
```

### Evaluation Harness

```bash
# Run evaluation suite
python -m tests.evaluation

# Results saved to data/eval/results/
```

### Red Team Tests

```bash
# Run adversarial tests
pytest tests/red_team/ -v
```

### Performance Benchmarks

```bash
# Run performance benchmarks
python -m tests.performance
```

---

## Code Quality

### Linting & Formatting

```bash
# Format code with black
black src/ tests/

# Lint with ruff
ruff check src/ tests/

# Type checking with mypy
mypy src/
```

### Pre-commit Hooks

Install pre-commit hooks (recommended):

```bash
pip install pre-commit
pre-commit install
```

This runs formatting and linting on every commit.

---

## Debugging

### Enable Debug Logging

In `config/config.yaml`:

```yaml
app:
  log_level: 'debug'
```

Or via environment variable:

```bash
export LEXARD_APP__LOG_LEVEL=debug
uvicorn src.api.main:app --reload
```

### Interactive Debugging

Use Python's debugger:

```python
import pdb; pdb.set_trace()
```

Or VS Code's debugger with this `.vscode/launch.json`:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Uvicorn",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": [
        "src.api.main:app",
        "--reload"
      ],
      "jinja": true,
      "justMyCode": false
    }
  ]
}
```

### View Logs

```bash
# API logs (if running via uvicorn)
# Logs appear in terminal

# Docker service logs
docker-compose logs qdrant
docker-compose logs ollama

# Follow logs
docker-compose logs -f
```

---

## Working with Services

### Qdrant

**View collections:**

```bash
curl http://localhost:6333/collections
```

**View collection info:**

```bash
curl http://localhost:6333/collections/documents
```

**Qdrant dashboard:**

Open [http://localhost:6333/dashboard](http://localhost:6333/dashboard)

### Ollama

**List models:**

```bash
docker exec -it lexard-ollama ollama list
```

**Pull new model:**

```bash
docker exec -it lexard-ollama ollama pull llama3:8b
```

**Test model:**

```bash
docker exec -it lexard-ollama ollama run mistral:7b-instruct "Hello"
```

### Database

**SQLite database location:**

```
./data/documents.db
```

**Inspect with sqlite3:**

```bash
sqlite3 data/documents.db

# List tables
.tables

# View documents
SELECT * FROM documents;

# Exit
.quit
```

---

## Adding New Features

### 1. Create Feature Branch

```bash
git checkout -b feature/new-feature develop
```

### 2. Implement Feature

Follow existing patterns:
- Use type hints
- Add docstrings
- Write tests
- Follow code style

### 3. Test Your Changes

```bash
pytest tests/ -v
black src/
ruff check src/
```

### 4. Commit and Push

```bash
git add .
git commit -m "feat(scope): add new feature"
git push -u origin feature/new-feature
```

### 5. Create Pull Request

- Target: `develop` branch
- Include description of changes
- Reference any related issues

---

## Common Development Tasks

### Reset Database

```bash
# Remove SQLite database
rm data/documents.db

# Reset Qdrant collection
curl -X DELETE http://localhost:6333/collections/documents

# Restart application (it will recreate)
```

### Change LLM Model

In `config/config.yaml`:

```yaml
llm:
  model: 'llama3:8b'
```

Pull the model:

```bash
docker exec -it lexard-ollama ollama pull llama3:8b
```

Restart the application.

### Add New Dependency

```bash
# Edit pyproject.toml
# Add dependency to dependencies array

# Reinstall
pip install -e ".[dev]"

# Update lock file (if using)
pip freeze > requirements.txt
```

### Generate OpenAPI Schema

```bash
# Start the application
uvicorn src.api.main:app --reload

# Access schema
curl http://localhost:8000/openapi.json > openapi.json
```

---

## Troubleshooting Development Issues

### Import errors

Make sure you installed in editable mode:

```bash
pip install -e ".[dev]"
```

### Services not starting

```bash
# Check Docker status
docker-compose ps

# Restart services
docker-compose down
docker-compose up -d
```

### Port conflicts

If ports 8000, 6333, or 11434 are in use:

```bash
# Find process using port
lsof -i :8000

# Kill it or change port in config
```

### Virtual environment issues

Always activate the virtual environment:

```bash
source .venv/bin/activate
```

On macOS, system Python is externally-managed and won't allow direct installs.

---

## Next Steps

- [Configuration Guide](configuration.md) - Customize settings
- [API Reference](api.md) - API documentation
- [Deployment Guide](deployment.md) - Production deployment
- [Troubleshooting](troubleshooting.md) - Common issues
