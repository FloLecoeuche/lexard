# Epic 16: One-Command Launcher

## Overview

Create a comprehensive launcher script that starts all Lexard services (llama-server with Vulkan, Docker containers, Cloudflare tunnel) with a single command. This enables easy demo deployments via SSH without complex manual steps.

## Prerequisites

- Epic 14 completed (Cloudflare tunnel setup)
- llama.cpp built with Vulkan at `/home/flo/Dev/llama.cpp/build/bin/`
- Model file at `/home/flo/Dev/llama.cpp/models/mistral-7b-instruct-v0.2.Q4_K_M.gguf`
- Named Cloudflare tunnel `lexard-demo` configured
- Vulkan SDK installed on the host

## User Stories

---

## US 16.1: Launcher Script

**Status:** ✅ Completed

### Description

Create a robust `scripts/lexard.sh` script with start/stop/status/logs commands that manages all Lexard services as background processes.

### Context

The use case is SSH-based demo deployment: wake PC over LAN, SSH in, run one command to start everything. Services should persist after SSH disconnect. The script must handle:
- llama-server (Vulkan backend on AMD RDNA4)
- Docker containers (Qdrant + API)
- Cloudflare tunnel (named tunnel `lexard-demo`)

### Tasks

- [x] Create `scripts/lexard.sh` with subcommands: `start`, `stop`, `status`, `logs`
- [x] Implement pre-flight checks:
  - [x] Vulkan availability (`vulkaninfo --summary`)
  - [x] Model file exists
  - [x] Port availability (8080, 8000, 6333)
  - [x] cloudflared installed and tunnel exists
  - [x] Docker daemon running
- [x] Implement `start` command:
  - [x] Start llama-server in background with PID tracking
  - [x] Wait for llama-server health check (`/health` endpoint)
  - [x] Start Docker services (`docker compose up -d`)
  - [x] Wait for API health check (`localhost:8000/health`)
  - [x] Start cloudflared tunnel in background with PID tracking
  - [x] Display final status with public URL
- [x] Implement `stop` command:
  - [x] Graceful shutdown of cloudflared
  - [x] Stop Docker services (`docker compose down`)
  - [x] Graceful shutdown of llama-server
  - [x] Clean up PID files
- [x] Implement `status` command:
  - [x] Show running state of each service
  - [x] Show health check results
  - [x] Show public tunnel URL if running
  - [x] Show GPU utilization (via `amd-smi` if available)
- [x] Implement `logs` command:
  - [x] Follow logs from all services (llama-server, docker, cloudflared)
  - [x] Support `--llama`, `--docker`, `--tunnel` flags to filter
- [x] Store PID files in `/tmp/lexard/` for process tracking
- [x] Add colorized output for better UX

### Implementation Details

**Script structure:**
```bash
#!/bin/bash
# scripts/lexard.sh - One-command Lexard launcher

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PID_DIR="/tmp/lexard"
LOG_DIR="/tmp/lexard/logs"

# Paths
LLAMA_SERVER="/home/flo/Dev/llama.cpp/build/bin/llama-server"
MODEL_PATH="/home/flo/Dev/llama.cpp/models/mistral-7b-instruct-v0.2.Q4_K_M.gguf"
TUNNEL_NAME="lexard-demo"

# Commands: start, stop, status, logs
```

**PID file locations:**
- `/tmp/lexard/llama-server.pid`
- `/tmp/lexard/cloudflared.pid`

**Log file locations:**
- `/tmp/lexard/logs/llama-server.log`
- `/tmp/lexard/logs/cloudflared.log`

### Acceptance Criteria

- [x] `./scripts/lexard.sh start` launches all services and displays public URL
- [x] `./scripts/lexard.sh stop` cleanly shuts down all services
- [x] `./scripts/lexard.sh status` shows health of all components
- [x] `./scripts/lexard.sh logs` follows combined logs
- [x] Services persist after SSH disconnect
- [x] Pre-flight checks fail gracefully with clear error messages
- [x] Script is idempotent (running `start` twice doesn't break anything)

### Tests

- **Manual:** Test full start/stop cycle ✅
- **Manual:** Test SSH disconnect and reconnect, verify services still running ✅
- **Manual:** Test status command shows correct state ✅
- **Manual:** Test pre-flight failures (missing model, port in use, etc.) ✅

### Files to Create/Modify

1. `scripts/lexard.sh` - Main launcher script (new) ✅

---

## US 16.2: Documentation Update

**Status:** ✅ Completed

### Description

Update documentation to reflect the new one-command launcher workflow. Model stays in llama.cpp directory (not in project).

### Context

The model file is stored in `/home/flo/Dev/llama.cpp/models/` (outside the lexard project) to avoid duplication and keep large files separate from the codebase. Documentation should guide users through the complete setup process.

### Tasks

- [x] Update `docs/quickstart.md`:
  - [x] Add "One-Command Start" section at top
  - [x] Update AMD GPU setup to reference llama.cpp models directory
  - [x] Add model download instructions
- [x] Update `config/config.example.yaml` with llama-server config comment
- [x] Update `docker-compose.yml` header comment with new launcher command

### Acceptance Criteria

- [x] `docs/quickstart.md` has clear one-command start instructions
- [x] Documentation references correct model path (`/home/flo/Dev/llama.cpp/models/`)
- [x] Documentation matches actual script behavior

### Tests

- **Manual:** Follow quickstart guide on fresh setup

### Files to Create/Modify

1. `docs/quickstart.md` - Add one-command section (modify) ✅
2. `config/config.example.yaml` - Add llama-server config comment (modify) ✅
3. `docker-compose.yml` - Update header comment (modify) ✅

---

## Definition of Done (Epic 16)

- [x] All User Stories completed (2/2 US)
- [x] `./scripts/lexard.sh start` launches complete stack with one command
- [x] `./scripts/lexard.sh stop` cleanly shuts down everything
- [x] `./scripts/lexard.sh status` shows health of all services
- [x] Services persist after SSH disconnect
- [x] Model stored in llama.cpp directory (separate from project)
- [x] Documentation updated with new workflow
- [x] Pre-flight checks catch common setup issues
