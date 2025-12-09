# Quickstart Guide

Get Lexard running in 5 minutes.

## Prerequisites

- Docker & Docker Compose
- Python 3.11+
- 8GB RAM minimum
- macOS, Linux, or Windows with WSL2

### GPU Support (Optional)

For GPU-accelerated inference:

- **NVIDIA**: CUDA toolkit and nvidia-docker
- **AMD**: ROCm 6.4+ or Vulkan SDK (see [AMD GPU Setup](#amd-gpu-setup-vulkan))

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/lexard.git
cd lexard
```

### 2. Choose your LLM backend

Lexard supports two LLM backends:

| Backend                  | Best For                         | Setup Complexity |
| ------------------------ | -------------------------------- | ---------------- |
| **Ollama** (recommended) | CPU, NVIDIA GPU, Intel/older AMD | Simple (Docker)  |
| **llama.cpp (Vulkan)**   | AMD RDNA4 GPUs (workaround)      | Manual build     |

#### Option A: Ollama (Recommended)

```bash
docker-compose up -d
```

This starts:

- Qdrant (vector database) on port 6333
- Ollama (local LLM) on port 11434

Pull the LLM model:

```bash
docker exec -it lexard-ollama ollama pull mistral:7b-instruct
```

#### Option B: llama.cpp with Vulkan (AMD RDNA4 Workaround)

> **Why this workaround?** AMD RDNA4 GPUs (gfx1201) have a known bug where ROCm HIP backend shows 100% idle GPU usage. Until this is fixed in ROCm/Ollama, use llama-server with Vulkan instead.

See [AMD GPU Setup](#amd-gpu-setup-vulkan) below for detailed instructions.

### 3. Set up Python environment

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

### 4. Configure the application

```bash
# The config file should already exist, but verify:
cat config/config.yaml
```

The default configuration works with Ollama. If you're using the **llama-server workaround** for AMD RDNA4 GPUs, see [AMD GPU Setup](#amd-gpu-setup-vulkan) for configuration changes.

See [Configuration Guide](configuration.md) for all customization options.

### 5. Start the API server

```bash
uvicorn src.api.main:app --reload
```

The API will be available at `http://localhost:8000`.

### 6. Verify installation

Open another terminal and check the health endpoint:

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{
  "status": "healthy",
  "version": "0.1.0",
  "services": {
    "qdrant": "connected",
    "ollama": "connected"
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
curl -X POST http://localhost:8000/risks \
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

## AMD GPU Setup (Vulkan)

AMD RDNA4 GPUs (RX 9070 series) and some RDNA3 GPUs have issues with ROCm's HIP backend (100% idle GPU usage bug). The workaround is to use llama.cpp with the Vulkan backend.

### Prerequisites

```bash
# Install Vulkan development libraries
sudo apt-get install -y libvulkan-dev glslc

# Verify Vulkan is working
vulkaninfo --summary
```

### Build llama.cpp with Vulkan

```bash
# Clone llama.cpp
cd /tmp
git clone --depth 1 https://github.com/ggerganov/llama.cpp.git
cd llama.cpp

# Build with Vulkan support
cmake -B build -DGGML_VULKAN=ON -DLLAMA_CURL=OFF
cmake --build build --config Release -j8

# Download a model
curl -L -o mistral-7b-instruct-v0.2.Q4_K_M.gguf \
  "https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF/resolve/main/mistral-7b-instruct-v0.2.Q4_K_M.gguf"
```

### Start llama-server

```bash
# Start llama-server with Vulkan on GPU 0
# -c 8192 sets context size (needed for document summarization)
GGML_VK_DEVICE=0 ./build/bin/llama-server \
  -m mistral-7b-instruct-v0.2.Q4_K_M.gguf \
  --host 0.0.0.0 --port 8080 -ngl 99 -c 8192
```

The server provides an OpenAI-compatible API at `http://localhost:8080`.

### Configure Lexard for llama-server

Update `config/config.yaml`:

```yaml
llm:
  provider: 'openai' # Use OpenAI-compatible API
  model: 'mistral'
  base_url: 'http://localhost:8080'
  temperature: 0.1
  max_tokens: 2048
  timeout_seconds: 60
```

### Docker Setup with llama-server

When using Docker with llama-server on the host:

1. Start llama-server on the host (as shown above)
2. Start only Qdrant and API containers:

```bash
docker-compose up -d
```

The docker-compose.yml is pre-configured to connect to `host.docker.internal:8080`.

### Verify GPU Usage

Check that the GPU idles correctly (should be ~5%, not 100%):

```bash
# For AMD GPUs
amd-smi monitor -p -u

# Expected idle output:
# GPU  POWER  GFX%
#   0   15 W    5 %
```

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
docker-compose logs api
```

### LLM connection errors

For Ollama:

```bash
curl http://localhost:11434/api/tags
```

For llama-server:

```bash
curl http://localhost:8080/health
```

### AMD GPU 100% usage at idle

This is a known ROCm HIP bug on RDNA4 GPUs. Use the Vulkan backend instead:

- See [AMD GPU Setup](#amd-gpu-setup-vulkan)
- Reference: [ROCm Issue #5706](https://github.com/ROCm/ROCm/issues/5706)

### Virtual environment issues on macOS

If you get "externally-managed-environment" errors, you're trying to install to system Python. Always activate the virtual environment first:

```bash
source .venv/bin/activate
```

For more issues, see the [Troubleshooting Guide](troubleshooting.md).
