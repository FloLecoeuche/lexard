# Configuration Guide

Comprehensive configuration reference for Lexard.

## Configuration File

Lexard uses YAML configuration with environment variable overrides.

**Location:** `config/config.yaml`

## Environment Variables

All settings can be overridden with environment variables using:
- Prefix: `LEXARD_`
- Nesting: Double underscores `__`

**Examples:**

```bash
# Override LLM model
export LEXARD_LLM__MODEL=llama3:8b

# Override Qdrant host
export LEXARD_QDRANT__HOST=qdrant.example.com

# Override log level
export LEXARD_APP__LOG_LEVEL=debug
```

## Configuration Sections

### app

Application-level settings.

| Setting       | Type   | Default         | Description                              |
|---------------|--------|-----------------|------------------------------------------|
| `name`        | string | `"Lexard"`      | Application name                         |
| `environment` | string | `"development"` | Environment mode (`development` \| `production`) |
| `log_level`   | string | `"info"`        | Log level (`debug` \| `info` \| `warning` \| `error`) |

**Example:**

```yaml
app:
  name: 'Lexard'
  environment: 'development'
  log_level: 'info'
```

---

### llm

LLM (Language Model) configuration. Supports two providers:
- **Ollama**: Docker-based, simple setup (default)
- **OpenAI-compatible**: llama.cpp, vLLM, or any OpenAI-compatible API

| Setting          | Type   | Default                | Description                          |
|------------------|--------|------------------------|--------------------------------------|
| `provider`       | string | `"ollama"`             | LLM provider (`ollama` \| `openai`)  |
| `model`          | string | `"mistral:7b-instruct"`| Model name                           |
| `base_url`       | string | `"http://localhost:11434"` | API base URL                     |
| `temperature`    | float  | `0.1`                  | Generation temperature (0.0-2.0)     |
| `max_tokens`     | int    | `2048`                 | Maximum tokens in response           |
| `timeout_seconds`| int    | `30`                   | Request timeout in seconds           |

#### Provider: Ollama (Default)

```yaml
llm:
  provider: 'ollama'
  model: 'mistral:7b-instruct'
  base_url: 'http://localhost:11434'
  temperature: 0.1
  max_tokens: 2048
  timeout_seconds: 30
```

**Available Models:**

To see available models in your Ollama instance:

```bash
docker exec -it lexard-ollama ollama list
```

To pull additional models:

```bash
docker exec -it lexard-ollama ollama pull llama3:8b
```

#### Provider: OpenAI-compatible (llama.cpp, vLLM)

Use this for llama.cpp with Vulkan (recommended for AMD RDNA3/RDNA4 GPUs):

```yaml
llm:
  provider: 'openai'
  model: 'mistral'
  base_url: 'http://localhost:8080'
  temperature: 0.1
  max_tokens: 2048
  timeout_seconds: 60
```

The `openai` provider uses the `/v1/chat/completions` endpoint, compatible with:
- llama.cpp's `llama-server`
- vLLM
- Any OpenAI-compatible API

**For Docker deployments with host llama-server:**

```yaml
llm:
  provider: 'openai'
  model: 'mistral'
  base_url: 'http://host.docker.internal:8080'  # Access host from container
  timeout_seconds: 60
```

See [Quickstart - AMD GPU Setup](quickstart.md#amd-gpu-setup-vulkan) for building llama.cpp with Vulkan

---

### embeddings

Embedding model configuration.

| Setting      | Type   | Default              | Description                          |
|--------------|--------|----------------------|--------------------------------------|
| `model`      | string | `"all-mpnet-base-v2"`| Sentence-transformers model name     |
| `batch_size` | int    | `32`                 | Batch size for embedding generation  |
| `device`     | string | `"cpu"`              | Device to use (`cpu` \| `cuda`)      |

**Example:**

```yaml
embeddings:
  model: 'all-mpnet-base-v2'
  batch_size: 32
  device: 'cpu'
```

**Model Notes:**

- `all-mpnet-base-v2`: 768 dimensions, best quality/performance balance
- For GPU: Set `device: 'cuda'` if NVIDIA GPU available
- Larger batch sizes improve throughput but use more memory

---

### chunking

Text chunking configuration.

| Setting  | Type   | Default  | Description                          |
|----------|--------|----------|--------------------------------------|
| `method` | string | `"fixed"`| Chunking method (currently only `fixed`) |
| `size`   | int    | `512`    | Chunk size in tokens                 |
| `overlap`| int    | `50`     | Overlap between chunks in tokens     |

**Example:**

```yaml
chunking:
  method: 'fixed'
  size: 512
  overlap: 50
```

**Recommendations:**

- Smaller chunks (256-512): Better for precise retrieval
- Larger chunks (512-1024): Better for context
- Overlap: 10-20% of chunk size prevents information loss

---

### qdrant

Qdrant vector database configuration.

| Setting      | Type   | Default        | Description                          |
|--------------|--------|----------------|--------------------------------------|
| `host`       | string | `"localhost"`  | Qdrant server hostname               |
| `port`       | int    | `6333`         | Qdrant HTTP API port                 |
| `collection` | string | `"documents"`  | Collection name for storing vectors  |

**Example:**

```yaml
qdrant:
  host: 'localhost'
  port: 6333
  collection: 'documents'
```

**Production Notes:**

For production, deploy Qdrant separately and configure:

```yaml
qdrant:
  host: 'qdrant.your-domain.com'
  port: 6333
  collection: 'documents_prod'
```

---

### retrieval

RAG retrieval configuration.

| Setting           | Type    | Default | Description                          |
|-------------------|---------|---------|--------------------------------------|
| `top_k`           | int     | `8`     | Number of chunks to retrieve         |
| `score_threshold` | float   | `0.7`   | Minimum similarity score (0.0-1.0)   |
| `rerank`          | boolean | `false` | Enable re-ranking (not implemented)  |

**Example:**

```yaml
retrieval:
  top_k: 8
  score_threshold: 0.7
  rerank: false
```

**Tuning Guide:**

- **top_k**: More chunks = more context but slower
  - 5-8: Good for focused queries
  - 10-15: Better for comprehensive answers
- **score_threshold**: Controls answer quality
  - 0.5-0.6: Permissive, more answers
  - 0.7-0.8: Balanced (recommended)
  - 0.8+: Strict, fewer but higher quality

---

### guardrails

Guardrails pipeline configuration.

| Setting                     | Type    | Default | Description                          |
|-----------------------------|---------|---------|--------------------------------------|
| `hallucination_threshold`   | float   | `0.8`   | Minimum grounding score (0.0-1.0)    |
| `enable_pii_filter`         | boolean | `true`  | Enable PII redaction                 |
| `max_retries`               | int     | `2`     | Max retries on validation failure    |

**Example:**

```yaml
guardrails:
  hallucination_threshold: 0.8
  enable_pii_filter: true
  max_retries: 2
```

**Hallucination Threshold:**

- `0.7`: Permissive, allows more responses
- `0.8`: Balanced (recommended)
- `0.9`: Strict, blocks more potentially hallucinated content

**PII Patterns Detected:**

When `enable_pii_filter: true`, the following patterns are redacted:
- IBAN numbers
- SSN (Social Security Numbers)
- Phone numbers
- Email addresses
- Credit card numbers
- IP addresses

---

### storage

File storage configuration.

| Setting             | Type   | Default            | Description                          |
|---------------------|--------|--------------------|--------------------------------------|
| `upload_dir`        | string | `"./data/uploads"` | Directory for uploaded files         |
| `max_file_size_mb`  | int    | `50`               | Maximum file size in megabytes       |

**Example:**

```yaml
storage:
  upload_dir: './data/uploads'
  max_file_size_mb: 50
```

**Notes:**

- Ensure the upload directory exists and is writable
- Files are stored temporarily during processing then deleted
- Persistent data is in Qdrant and SQLite

---

### server

FastAPI server configuration.

| Setting   | Type   | Default     | Description                          |
|-----------|--------|-------------|--------------------------------------|
| `host`    | string | `"0.0.0.0"` | Server bind address                  |
| `port`    | int    | `8000`      | Server port                          |
| `workers` | int    | `4`         | Number of worker processes           |

**Example:**

```yaml
server:
  host: '0.0.0.0'
  port: 8000
  workers: 4
```

**Production Notes:**

- `host: '0.0.0.0'` - Binds to all interfaces (required for Docker)
- `workers`: Set to number of CPU cores for production
- Use a reverse proxy (nginx) in production

---

## Complete Examples

### With Ollama (Default)

Full `config/config.yaml`:

```yaml
app:
  name: 'Lexard'
  environment: 'development'
  log_level: 'info'

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
  device: 'cpu'

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

### With llama.cpp (AMD GPU with Vulkan)

For AMD RDNA3/RDNA4 GPUs using llama-server:

```yaml
app:
  name: 'Lexard'
  environment: 'development'
  log_level: 'info'

llm:
  provider: 'openai'  # OpenAI-compatible API
  model: 'mistral'
  base_url: 'http://localhost:8080'  # llama-server
  temperature: 0.1
  max_tokens: 2048
  timeout_seconds: 60

embeddings:
  model: 'all-mpnet-base-v2'
  batch_size: 32
  device: 'cpu'  # CPU for embeddings (fast enough)

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

---

## Environment-Specific Configuration

### Development

Use the default configuration file with:

```yaml
app:
  environment: 'development'
  log_level: 'debug'
```

### Production

Create `config/config.prod.yaml`:

```yaml
app:
  environment: 'production'
  log_level: 'info'

llm:
  base_url: 'http://ollama-service:11434'
  timeout_seconds: 60

qdrant:
  host: 'qdrant-service'
  collection: 'documents_prod'

server:
  workers: 8
```

Load with environment variable:

```bash
export LEXARD_CONFIG_FILE=config/config.prod.yaml
```

---

## Configuration Validation

Lexard validates configuration on startup. If validation fails, you'll see an error message:

```
ConfigurationError: Invalid configuration: llm.temperature must be between 0.0 and 1.0
```

Common validation errors:

- Missing required fields
- Invalid value ranges
- Unreachable service URLs

---

## Next Steps

- [Deployment Guide](deployment.md) - Production deployment patterns
- [Development Guide](development.md) - Development environment setup
- [API Reference](api.md) - REST API documentation
