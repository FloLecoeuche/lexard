#!/bin/bash
# scripts/lexard.sh - One-command Lexard launcher
#
# Usage:
#   ./scripts/lexard.sh start   - Start all services
#   ./scripts/lexard.sh stop    - Stop all services
#   ./scripts/lexard.sh status  - Show service status
#   ./scripts/lexard.sh logs    - Follow all logs
#   ./scripts/lexard.sh logs --llama    - Follow llama-server logs
#   ./scripts/lexard.sh logs --docker   - Follow Docker logs
#   ./scripts/lexard.sh logs --tunnel   - Follow cloudflared logs
#
# See docs/quickstart.md for complete setup instructions.

set -e

# Paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PID_DIR="/tmp/lexard"
LOG_DIR="/tmp/lexard/logs"

# Service paths
LLAMA_SERVER="/home/flo/Dev/llama.cpp/build/bin/llama-server"
MODEL_PATH="/home/flo/Dev/llama.cpp/models/mistral-7b-instruct-v0.2.Q4_K_M.gguf"
TUNNEL_NAME="lexard-demo"

# Ports
LLAMA_PORT=8080
API_PORT=8000
QDRANT_PORT=6333

# PID files
LLAMA_PID_FILE="${PID_DIR}/llama-server.pid"
TUNNEL_PID_FILE="${PID_DIR}/cloudflared.pid"

# Log files
LLAMA_LOG="${LOG_DIR}/llama-server.log"
TUNNEL_LOG="${LOG_DIR}/cloudflared.log"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# Docker compose command (support both docker-compose and docker compose)
if command -v docker-compose &>/dev/null; then
    DOCKER_COMPOSE="docker-compose"
else
    DOCKER_COMPOSE="docker compose"
fi

# Helper functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_header() {
    echo ""
    echo -e "${BOLD}${CYAN}=== $1 ===${NC}"
    echo ""
}

# Ensure directories exist
ensure_dirs() {
    mkdir -p "${PID_DIR}"
    mkdir -p "${LOG_DIR}"
}

# Check if a process is running by PID file
is_running() {
    local pid_file="$1"
    if [[ -f "$pid_file" ]]; then
        local pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            return 0
        fi
    fi
    return 1
}

# Check if a port is in use
port_in_use() {
    local port="$1"
    if command -v ss &>/dev/null; then
        ss -tuln 2>/dev/null | grep -q ":${port} "
    elif command -v netstat &>/dev/null; then
        netstat -tuln 2>/dev/null | grep -q ":${port} "
    else
        # Fallback: try to connect
        timeout 1 bash -c "echo >/dev/tcp/127.0.0.1/${port}" 2>/dev/null
    fi
}

# Wait for health endpoint
wait_for_health() {
    local url="$1"
    local timeout_secs="${2:-60}"
    local service_name="${3:-service}"

    log_info "Waiting for ${service_name} to be ready..."

    local start_time=$(date +%s)
    while true; do
        if curl -s --max-time 2 "${url}" >/dev/null 2>&1; then
            log_success "${service_name} is ready"
            return 0
        fi

        local elapsed=$(($(date +%s) - start_time))
        if [[ $elapsed -ge $timeout_secs ]]; then
            log_error "${service_name} failed to start within ${timeout_secs}s"
            return 1
        fi

        sleep 2
    done
}

# ============================================================================
# PRE-FLIGHT CHECKS
# ============================================================================

check_vulkan() {
    log_info "Checking Vulkan availability..."

    if ! command -v vulkaninfo &>/dev/null; then
        log_error "vulkaninfo not found. Install vulkan-tools package."
        return 1
    fi

    if vulkaninfo --summary 2>/dev/null | grep -q "GPU"; then
        local gpu_name=$(vulkaninfo --summary 2>/dev/null | grep "deviceName" | head -1 | cut -d'=' -f2 | xargs)
        log_success "Vulkan GPU: ${gpu_name}"
        return 0
    else
        log_error "No Vulkan-capable GPU detected"
        return 1
    fi
}

check_model() {
    log_info "Checking model file..."

    if [[ -f "$MODEL_PATH" ]]; then
        local size=$(du -h "$MODEL_PATH" | cut -f1)
        log_success "Model found: $(basename "$MODEL_PATH") (${size})"
        return 0
    else
        log_error "Model not found: $MODEL_PATH"
        echo ""
        echo "Download the model:"
        echo "  mkdir -p ${PROJECT_DIR}/models"
        echo "  cd ${PROJECT_DIR}/models"
        echo "  curl -L -o mistral-7b-instruct-v0.2.Q4_K_M.gguf \\"
        echo '    "https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF/resolve/main/mistral-7b-instruct-v0.2.Q4_K_M.gguf"'
        return 1
    fi
}

check_llama_server() {
    log_info "Checking llama-server binary..."

    if [[ -x "$LLAMA_SERVER" ]]; then
        log_success "llama-server found: $LLAMA_SERVER"
        return 0
    else
        log_error "llama-server not found or not executable: $LLAMA_SERVER"
        echo ""
        echo "Build llama.cpp with Vulkan:"
        echo "  cd /home/flo/Dev/llama.cpp"
        echo "  cmake -B build -DGGML_VULKAN=ON"
        echo "  cmake --build build --config Release -j"
        return 1
    fi
}

check_ports() {
    log_info "Checking port availability..."
    local has_error=0
    local all_services_running=true

    for port in $LLAMA_PORT $API_PORT $QDRANT_PORT; do
        if port_in_use "$port"; then
            # Check if it's our service
            if [[ $port -eq $LLAMA_PORT ]] && is_running "$LLAMA_PID_FILE"; then
                log_warning "Port $port in use (llama-server already running)"
            elif [[ $port -eq $API_PORT ]] && docker ps --format '{{.Names}}' 2>/dev/null | grep -q "lexard-api"; then
                log_warning "Port $port in use (Lexard API already running)"
            elif [[ $port -eq $QDRANT_PORT ]] && docker ps --format '{{.Names}}' 2>/dev/null | grep -q "lexard-qdrant"; then
                log_warning "Port $port in use (Qdrant already running)"
            else
                log_error "Port $port is already in use"
                has_error=1
                all_services_running=false
            fi
        else
            all_services_running=false
        fi
    done

    if [[ $has_error -eq 0 ]]; then
        if [[ "$all_services_running" == "true" ]]; then
            log_success "All services already running"
        else
            log_success "Ports available: ${LLAMA_PORT}, ${API_PORT}, ${QDRANT_PORT}"
        fi
    fi

    return $has_error
}

check_cloudflared() {
    log_info "Checking cloudflared..."

    if ! command -v cloudflared &>/dev/null; then
        log_error "cloudflared not installed"
        echo ""
        echo "Install cloudflared:"
        echo "  sudo apt install cloudflared"
        return 1
    fi

    if cloudflared tunnel list 2>/dev/null | grep -q "${TUNNEL_NAME}"; then
        log_success "Tunnel '${TUNNEL_NAME}' exists"
        return 0
    else
        log_error "Tunnel '${TUNNEL_NAME}' not found"
        echo ""
        echo "Create the tunnel:"
        echo "  cloudflared login"
        echo "  cloudflared tunnel create ${TUNNEL_NAME}"
        return 1
    fi
}

check_docker() {
    log_info "Checking Docker daemon..."

    if ! command -v docker &>/dev/null; then
        log_error "Docker not installed"
        return 1
    fi

    if docker info >/dev/null 2>&1; then
        log_success "Docker daemon running"
        return 0
    else
        log_error "Docker daemon not running"
        echo ""
        echo "Start Docker:"
        echo "  sudo systemctl start docker"
        return 1
    fi
}

run_preflight() {
    log_header "Pre-flight Checks"

    local failed=0

    check_llama_server || failed=1
    check_model || failed=1
    check_vulkan || failed=1
    check_ports || failed=1
    check_docker || failed=1
    check_cloudflared || failed=1

    echo ""
    if [[ $failed -ne 0 ]]; then
        log_error "Pre-flight checks failed. Fix issues above and try again."
        return 1
    fi

    log_success "All pre-flight checks passed"
    return 0
}

# ============================================================================
# START COMMAND
# ============================================================================

start_llama_server() {
    log_header "Starting llama-server"

    if is_running "$LLAMA_PID_FILE"; then
        log_warning "llama-server already running (PID: $(cat "$LLAMA_PID_FILE"))"
        return 0
    fi

    # Check if llama-server is running externally (not via this script)
    if curl -s --max-time 2 "http://localhost:${LLAMA_PORT}/health" >/dev/null 2>&1; then
        log_warning "llama-server already running (external process)"
        # Try to find and record the PID
        local external_pid=$(pgrep -f "llama-server.*--port.*${LLAMA_PORT}" | head -1)
        if [[ -n "$external_pid" ]]; then
            echo "$external_pid" > "$LLAMA_PID_FILE"
            log_info "Recorded PID: $external_pid"
        fi
        return 0
    fi

    log_info "Launching llama-server with Vulkan backend..."

    # Start llama-server in background
    nohup "$LLAMA_SERVER" \
        --model "$MODEL_PATH" \
        --port "$LLAMA_PORT" \
        --host 0.0.0.0 \
        --n-gpu-layers 99 \
        --ctx-size 4096 \
        > "$LLAMA_LOG" 2>&1 &

    local pid=$!
    echo "$pid" > "$LLAMA_PID_FILE"

    log_info "llama-server started (PID: $pid)"

    # Wait for health
    if wait_for_health "http://localhost:${LLAMA_PORT}/health" 90 "llama-server"; then
        return 0
    else
        log_error "llama-server failed to start. Check logs: $LLAMA_LOG"
        return 1
    fi
}

start_docker_services() {
    log_header "Starting Docker Services"

    # Check if already running
    if docker ps --format '{{.Names}}' 2>/dev/null | grep -q "lexard-api"; then
        if curl -s --max-time 2 "http://localhost:${API_PORT}/health" >/dev/null 2>&1; then
            log_warning "Docker services already running and healthy"
            return 0
        fi
    fi

    cd "$PROJECT_DIR"

    log_info "Starting Qdrant and API containers..."
    $DOCKER_COMPOSE up -d

    # Wait for API health
    if wait_for_health "http://localhost:${API_PORT}/health" 60 "Lexard API"; then
        return 0
    else
        log_error "API failed to start. Check logs: $DOCKER_COMPOSE logs api"
        return 1
    fi
}

start_tunnel() {
    log_header "Starting Cloudflare Tunnel"

    if is_running "$TUNNEL_PID_FILE"; then
        log_warning "cloudflared already running (PID: $(cat "$TUNNEL_PID_FILE"))"
        return 0
    fi

    log_info "Starting tunnel '${TUNNEL_NAME}'..."

    # Start cloudflared in background
    nohup cloudflared tunnel run "${TUNNEL_NAME}" > "$TUNNEL_LOG" 2>&1 &

    local pid=$!
    echo "$pid" > "$TUNNEL_PID_FILE"

    log_info "cloudflared started (PID: $pid)"

    # Wait a moment for tunnel to establish
    sleep 5

    if is_running "$TUNNEL_PID_FILE"; then
        log_success "Tunnel started successfully"
        return 0
    else
        log_error "Tunnel failed to start. Check logs: $TUNNEL_LOG"
        return 1
    fi
}

get_tunnel_url() {
    # Try to get the URL from cloudflared tunnel info
    local url=$(cloudflared tunnel info "${TUNNEL_NAME}" 2>/dev/null | grep -oP 'https://[a-zA-Z0-9.-]+\.trycloudflare\.com' | head -1)

    if [[ -z "$url" ]]; then
        # Fallback: check if there's a configured hostname
        url=$(cloudflared tunnel info "${TUNNEL_NAME}" 2>/dev/null | grep -oP 'https://[a-zA-Z0-9.-]+\.[a-zA-Z]+' | head -1)
    fi

    echo "$url"
}

show_start_summary() {
    log_header "Lexard Services Started"

    echo -e "  ${GREEN}●${NC} llama-server   http://localhost:${LLAMA_PORT}"
    echo -e "  ${GREEN}●${NC} Qdrant         http://localhost:${QDRANT_PORT}"
    echo -e "  ${GREEN}●${NC} Lexard API     http://localhost:${API_PORT}"

    local tunnel_url=$(get_tunnel_url)
    if [[ -n "$tunnel_url" ]]; then
        echo ""
        echo -e "  ${GREEN}●${NC} Public URL     ${BOLD}${tunnel_url}${NC}"
    else
        echo ""
        echo -e "  ${YELLOW}●${NC} Tunnel         Running (check cloudflared dashboard for URL)"
    fi

    echo ""
    log_success "All services running! Services persist after SSH disconnect."
    echo ""
    echo "Useful commands:"
    echo "  ./scripts/lexard.sh status  - Check service health"
    echo "  ./scripts/lexard.sh logs    - Follow all logs"
    echo "  ./scripts/lexard.sh stop    - Stop all services"
}

cmd_start() {
    ensure_dirs

    if ! run_preflight; then
        exit 1
    fi

    if ! start_llama_server; then
        exit 1
    fi

    if ! start_docker_services; then
        exit 1
    fi

    if ! start_tunnel; then
        exit 1
    fi

    show_start_summary
}

# ============================================================================
# STOP COMMAND
# ============================================================================

stop_tunnel() {
    log_info "Stopping cloudflared..."

    if is_running "$TUNNEL_PID_FILE"; then
        local pid=$(cat "$TUNNEL_PID_FILE")
        kill "$pid" 2>/dev/null || true
        rm -f "$TUNNEL_PID_FILE"
        log_success "cloudflared stopped (was PID: $pid)"
    else
        log_warning "cloudflared not running"
    fi
}

stop_docker_services() {
    log_info "Stopping Docker services..."

    cd "$PROJECT_DIR"
    $DOCKER_COMPOSE down

    log_success "Docker services stopped"
}

stop_llama_server() {
    log_info "Stopping llama-server..."

    if is_running "$LLAMA_PID_FILE"; then
        local pid=$(cat "$LLAMA_PID_FILE")
        kill "$pid" 2>/dev/null || true

        # Wait for graceful shutdown
        local wait_count=0
        while kill -0 "$pid" 2>/dev/null && [[ $wait_count -lt 10 ]]; do
            sleep 1
            wait_count=$((wait_count + 1))
        done

        # Force kill if still running
        if kill -0 "$pid" 2>/dev/null; then
            kill -9 "$pid" 2>/dev/null || true
            log_warning "llama-server force killed (PID: $pid)"
        else
            log_success "llama-server stopped (was PID: $pid)"
        fi

        rm -f "$LLAMA_PID_FILE"
    else
        log_warning "llama-server not running"
    fi
}

cleanup_pid_files() {
    log_info "Cleaning up PID files..."
    rm -f "${PID_DIR}"/*.pid 2>/dev/null || true
}

cmd_stop() {
    log_header "Stopping Lexard Services"

    stop_tunnel
    stop_docker_services
    stop_llama_server
    cleanup_pid_files

    echo ""
    log_success "All services stopped"
}

# ============================================================================
# STATUS COMMAND
# ============================================================================

check_service_health() {
    local name="$1"
    local url="$2"
    local pid_file="$3"

    local status_icon="${RED}●${NC}"
    local status_text="stopped"
    local extra_info=""

    if [[ -n "$pid_file" ]] && is_running "$pid_file"; then
        local pid=$(cat "$pid_file")
        extra_info="PID: $pid"

        if curl -s --max-time 2 "$url" >/dev/null 2>&1; then
            status_icon="${GREEN}●${NC}"
            status_text="healthy"
        else
            status_icon="${YELLOW}●${NC}"
            status_text="running (unhealthy)"
        fi
    elif curl -s --max-time 2 "$url" >/dev/null 2>&1; then
        status_icon="${GREEN}●${NC}"
        status_text="healthy"
    fi

    printf "  ${status_icon} %-15s %-20s %s\n" "$name" "$status_text" "$extra_info"
}

check_docker_service() {
    local name="$1"
    local container="$2"
    local url="$3"

    local status_icon="${RED}●${NC}"
    local status_text="stopped"
    local extra_info=""

    if docker ps --format '{{.Names}}' 2>/dev/null | grep -q "$container"; then
        extra_info="container: $container"

        if curl -s --max-time 2 "$url" >/dev/null 2>&1; then
            status_icon="${GREEN}●${NC}"
            status_text="healthy"
        else
            status_icon="${YELLOW}●${NC}"
            status_text="running (unhealthy)"
        fi
    fi

    printf "  ${status_icon} %-15s %-20s %s\n" "$name" "$status_text" "$extra_info"
}

check_gpu_utilization() {
    log_info "GPU Utilization:"

    if command -v amd-smi &>/dev/null; then
        amd-smi monitor -ptu 2>/dev/null | head -5 || log_warning "Could not read GPU stats"
    elif command -v rocm-smi &>/dev/null; then
        rocm-smi --showuse 2>/dev/null | head -10 || log_warning "Could not read GPU stats"
    else
        log_warning "amd-smi/rocm-smi not available for GPU monitoring"
    fi
}

cmd_status() {
    log_header "Lexard Service Status"

    echo -e "  ${BOLD}Service          Status               Info${NC}"
    echo "  ─────────────────────────────────────────────────────────"

    check_service_health "llama-server" "http://localhost:${LLAMA_PORT}/health" "$LLAMA_PID_FILE"
    check_docker_service "Qdrant" "lexard-qdrant" "http://localhost:${QDRANT_PORT}/health"
    check_docker_service "Lexard API" "lexard-api" "http://localhost:${API_PORT}/health"

    # Tunnel status
    local tunnel_icon="${RED}●${NC}"
    local tunnel_status="stopped"
    local tunnel_info=""

    if is_running "$TUNNEL_PID_FILE"; then
        tunnel_icon="${GREEN}●${NC}"
        tunnel_status="running"
        tunnel_info="PID: $(cat "$TUNNEL_PID_FILE")"
    fi

    printf "  ${tunnel_icon} %-15s %-20s %s\n" "Tunnel" "$tunnel_status" "$tunnel_info"

    echo ""

    # Show tunnel URL if running
    if is_running "$TUNNEL_PID_FILE"; then
        local tunnel_url=$(get_tunnel_url)
        if [[ -n "$tunnel_url" ]]; then
            echo -e "  ${BOLD}Public URL:${NC} ${tunnel_url}"
            echo ""
        fi
    fi

    # GPU info
    check_gpu_utilization
}

# ============================================================================
# LOGS COMMAND
# ============================================================================

cmd_logs() {
    local filter="${1:-}"

    case "$filter" in
        --llama)
            log_header "llama-server Logs"
            if [[ -f "$LLAMA_LOG" ]]; then
                tail -f "$LLAMA_LOG"
            else
                log_error "Log file not found: $LLAMA_LOG"
                exit 1
            fi
            ;;
        --docker)
            log_header "Docker Logs"
            cd "$PROJECT_DIR"
            $DOCKER_COMPOSE logs -f
            ;;
        --tunnel)
            log_header "Cloudflare Tunnel Logs"
            if [[ -f "$TUNNEL_LOG" ]]; then
                tail -f "$TUNNEL_LOG"
            else
                log_error "Log file not found: $TUNNEL_LOG"
                exit 1
            fi
            ;;
        "")
            log_header "All Logs (Ctrl+C to exit)"

            # Create named pipes for merging logs
            local tmp_dir=$(mktemp -d)
            trap "rm -rf $tmp_dir" EXIT

            # Start background log tailers
            if [[ -f "$LLAMA_LOG" ]]; then
                tail -f "$LLAMA_LOG" | sed 's/^/[llama] /' &
            fi

            if [[ -f "$TUNNEL_LOG" ]]; then
                tail -f "$TUNNEL_LOG" | sed 's/^/[tunnel] /' &
            fi

            cd "$PROJECT_DIR"
            $DOCKER_COMPOSE logs -f 2>/dev/null | sed 's/^/[docker] /' &

            # Wait for Ctrl+C
            wait
            ;;
        *)
            log_error "Unknown filter: $filter"
            echo ""
            echo "Available filters:"
            echo "  --llama   llama-server logs"
            echo "  --docker  Docker container logs"
            echo "  --tunnel  Cloudflare tunnel logs"
            exit 1
            ;;
    esac
}

# ============================================================================
# HELP
# ============================================================================

show_help() {
    echo "Lexard One-Command Launcher"
    echo ""
    echo "Usage: ./scripts/lexard.sh <command> [options]"
    echo ""
    echo "Commands:"
    echo "  start    Start all services (llama-server, Docker, tunnel)"
    echo "  stop     Stop all services"
    echo "  status   Show service status and health"
    echo "  logs     Follow all logs"
    echo ""
    echo "Log filters:"
    echo "  logs --llama    Follow llama-server logs only"
    echo "  logs --docker   Follow Docker logs only"
    echo "  logs --tunnel   Follow cloudflared logs only"
    echo ""
    echo "Services managed:"
    echo "  - llama-server (Vulkan backend, port ${LLAMA_PORT})"
    echo "  - Qdrant vector database (port ${QDRANT_PORT})"
    echo "  - Lexard API (port ${API_PORT})"
    echo "  - Cloudflare tunnel (${TUNNEL_NAME})"
    echo ""
    echo "Example workflow:"
    echo "  1. ./scripts/lexard.sh start   # Start everything"
    echo "  2. Share the public URL with testers"
    echo "  3. ./scripts/lexard.sh status  # Monitor health"
    echo "  4. ./scripts/lexard.sh stop    # Stop when done"
}

# ============================================================================
# MAIN
# ============================================================================

main() {
    case "${1:-}" in
        start)
            cmd_start
            ;;
        stop)
            cmd_stop
            ;;
        status)
            cmd_status
            ;;
        logs)
            cmd_logs "${2:-}"
            ;;
        --help|-h|help)
            show_help
            ;;
        "")
            show_help
            exit 1
            ;;
        *)
            log_error "Unknown command: $1"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

main "$@"
