# Epic 16: One-Command Launcher

## Overview

Create a comprehensive launcher script that starts all Lexard services (llama-server with Vulkan, Docker containers, Cloudflare tunnel) with a single command. This enables easy demo deployments via SSH without complex manual steps.

## Prerequisites

- Epic 14 completed (Cloudflare tunnel setup)
- llama.cpp built with Vulkan at `/home/flo/Dev/llama.cpp/build/bin/`
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

- [ ] Create `scripts/lexard.sh` with subcommands: `start`, `stop`, `status`, `logs`
- [ ] Implement pre-flight checks:
  - [ ] Vulkan availability (`vulkaninfo --summary`)
  - [ ] Model file exists (`models/mistral-7b-instruct-v0.2.Q4_K_M.gguf`)
  - [ ] Port availability (8080, 8000, 6333)
  - [ ] cloudflared installed and tunnel exists
  - [ ] Docker daemon running
- [ ] Implement `start` command:
  - [ ] Start llama-server in background with PID tracking
  - [ ] Wait for llama-server health check (`/health` endpoint)
  - [ ] Start Docker services (`docker-compose up -d`)
  - [ ] Wait for API health check (`localhost:8000/health`)
  - [ ] Start cloudflared tunnel in background with PID tracking
  - [ ] Display final status with public URL
- [ ] Implement `stop` command:
  - [ ] Graceful shutdown of cloudflared
  - [ ] Stop Docker services (`docker-compose down`)
  - [ ] Graceful shutdown of llama-server
  - [ ] Clean up PID files
- [ ] Implement `status` command:
  - [ ] Show running state of each service
  - [ ] Show health check results
  - [ ] Show public tunnel URL if running
  - [ ] Show GPU utilization (via `amd-smi` if available)
- [ ] Implement `logs` command:
  - [ ] Follow logs from all services (llama-server, docker, cloudflared)
  - [ ] Support `--llama`, `--docker`, `--tunnel` flags to filter
- [ ] Store PID files in `/tmp/lexard/` for process tracking
- [ ] Add colorized output for better UX

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
MODEL_PATH="${PROJECT_DIR}/models/mistral-7b-instruct-v0.2.Q4_K_M.gguf"
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

- [ ] `./scripts/lexard.sh start` launches all services and displays public URL
- [ ] `./scripts/lexard.sh stop` cleanly shuts down all services
- [ ] `./scripts/lexard.sh status` shows health of all components
- [ ] `./scripts/lexard.sh logs` follows combined logs
- [ ] Services persist after SSH disconnect
- [ ] Pre-flight checks fail gracefully with clear error messages
- [ ] Script is idempotent (running `start` twice doesn't break anything)

### Tests

- **Manual:** Test full start/stop cycle
- **Manual:** Test SSH disconnect and reconnect, verify services still running
- **Manual:** Test status command shows correct state
- **Manual:** Test pre-flight failures (missing model, port in use, etc.)

### Files to Create/Modify

1. `scripts/lexard.sh` - Main launcher script (new)

---

## US 16.2: Model Setup & Documentation

**Status:** 🔲 Not Started

### Description

Create the `models/` directory structure, update `.gitignore`, and update documentation to reflect the new one-command launcher workflow.

### Context

The model file should be stored in a dedicated `models/` directory within the project for easy path management. Documentation should guide users through the complete setup process.

### Tasks

- [ ] Create `models/` directory with `.gitkeep`
- [ ] Create `models/README.md` with download instructions
- [ ] Update `.gitignore` to exclude model files (`models/*.gguf`)
- [ ] Update `docs/quickstart.md`:
  - [ ] Add "One-Command Start" section
  - [ ] Update AMD GPU setup to reference `models/` directory
  - [ ] Add model download instructions to `models/` folder
- [ ] Update `config/config.yaml` to use `models/` path (commented example)
- [ ] Update `docker-compose.yml` header comment with new launcher command

### Implementation Details

**models/README.md content:**
```markdown
# Models Directory

This directory contains LLM model files (not tracked in git).

## Download Mistral 7B

```bash
curl -L -o mistral-7b-instruct-v0.2.Q4_K_M.gguf \
  "https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF/resolve/main/mistral-7b-instruct-v0.2.Q4_K_M.gguf"
```

File size: ~4.4 GB
```

**.gitignore additions:**
```
# Models (large files, download separately)
models/*.gguf
models/*.bin
!models/.gitkeep
!models/README.md
```

### Acceptance Criteria

- [ ] `models/` directory exists with `.gitkeep` and `README.md`
- [ ] Model files (*.gguf) are gitignored
- [ ] `docs/quickstart.md` has clear one-command start instructions
- [ ] Documentation matches actual script behavior

### Tests

- **Manual:** Verify `.gitignore` excludes model files
- **Manual:** Follow quickstart guide on fresh setup

### Files to Create/Modify

1. `models/.gitkeep` - Keep empty directory in git (new)
2. `models/README.md` - Model download instructions (new)
3. `.gitignore` - Add models exclusion (modify)
4. `docs/quickstart.md` - Add one-command section (modify)
5. `docker-compose.yml` - Update header comment (modify)

---

## Definition of Done (Epic 16)

- [ ] All User Stories completed (2/2 US)
- [ ] `./scripts/lexard.sh start` launches complete stack with one command
- [ ] `./scripts/lexard.sh stop` cleanly shuts down everything
- [ ] `./scripts/lexard.sh status` shows health of all services
- [ ] Services persist after SSH disconnect
- [ ] Model stored in `models/` directory (gitignored)
- [ ] Documentation updated with new workflow
- [ ] Pre-flight checks catch common setup issues
