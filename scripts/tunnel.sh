#!/bin/bash
# Cloudflare Tunnel Helper for Lexard
#
# Usage:
#   ./scripts/tunnel.sh          - Run named tunnel (requires prior setup)
#   ./scripts/tunnel.sh --quick  - Quick tunnel with temporary URL (no setup needed)
#   ./scripts/tunnel.sh --help   - Show this help
#
# See docs/INTERNET_EXPOSURE.md for complete setup instructions.

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
LOCAL_URL="http://localhost:8000"
TUNNEL_NAME="lexard-demo"

show_help() {
    echo "Cloudflare Tunnel Helper for Lexard"
    echo ""
    echo "Usage:"
    echo "  ./scripts/tunnel.sh          Run named tunnel '${TUNNEL_NAME}'"
    echo "  ./scripts/tunnel.sh --quick  Quick tunnel with temporary URL"
    echo "  ./scripts/tunnel.sh --help   Show this help"
    echo ""
    echo "Quick tunnel requires no setup - just run and share the URL."
    echo "Named tunnel requires prior setup (see docs/INTERNET_EXPOSURE.md)."
}

check_cloudflared() {
    if ! command -v cloudflared &> /dev/null; then
        echo -e "${RED}Error: cloudflared is not installed${NC}"
        echo ""
        echo "Install it with:"
        echo "  Linux:  sudo apt install cloudflared"
        echo "  macOS:  brew install cloudflared"
        echo "  Windows: winget install Cloudflare.cloudflared"
        echo ""
        echo "See docs/INTERNET_EXPOSURE.md for detailed instructions."
        exit 1
    fi
}

check_lexard() {
    echo -e "${BLUE}Checking if Lexard is running...${NC}"

    if curl -s --max-time 5 "${LOCAL_URL}/health" > /dev/null 2>&1; then
        echo -e "${GREEN}Lexard is running at ${LOCAL_URL}${NC}"
    else
        echo -e "${YELLOW}Warning: Cannot reach Lexard at ${LOCAL_URL}${NC}"
        echo ""
        echo "Make sure Lexard is running:"
        echo "  docker-compose up -d"
        echo ""
        read -p "Continue anyway? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
}

show_security_reminder() {
    echo ""
    echo -e "${YELLOW}=== Security Reminder ===${NC}"
    echo ""
    echo "Before sharing the URL with testers:"
    echo "  1. Change the default password in config/config.yaml"
    echo "  2. Restart the API: docker-compose restart api"
    echo "  3. Test login works with new password"
    echo ""
    echo "To stop the tunnel: Press Ctrl+C or run 'pkill cloudflared'"
    echo ""
}

run_quick_tunnel() {
    echo -e "${GREEN}Starting quick tunnel (temporary URL)...${NC}"
    echo ""
    echo "A random URL will be generated. Share it with testers."
    echo "The URL changes each time you restart the tunnel."
    echo ""

    show_security_reminder

    echo -e "${BLUE}Starting tunnel...${NC}"
    echo ""
    cloudflared tunnel --url "${LOCAL_URL}"
}

run_named_tunnel() {
    echo -e "${GREEN}Starting named tunnel '${TUNNEL_NAME}'...${NC}"
    echo ""

    # Check if tunnel exists
    if ! cloudflared tunnel list 2>/dev/null | grep -q "${TUNNEL_NAME}"; then
        echo -e "${RED}Error: Tunnel '${TUNNEL_NAME}' not found${NC}"
        echo ""
        echo "Create it first with:"
        echo "  cloudflared login"
        echo "  cloudflared tunnel create ${TUNNEL_NAME}"
        echo ""
        echo "Or use --quick for a temporary URL without setup."
        exit 1
    fi

    show_security_reminder

    echo -e "${BLUE}Starting tunnel...${NC}"
    echo ""
    cloudflared tunnel run "${TUNNEL_NAME}"
}

# Main script
main() {
    case "${1:-}" in
        --help|-h)
            show_help
            exit 0
            ;;
        --quick|-q)
            check_cloudflared
            check_lexard
            run_quick_tunnel
            ;;
        "")
            check_cloudflared
            check_lexard
            run_named_tunnel
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

main "$@"
