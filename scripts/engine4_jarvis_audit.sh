#!/bin/bash
# Engine 4 Jarvis Audit - Shell Wrapper
# Usage:
#   ./scripts/engine4_jarvis_audit.sh --local
#   ./scripts/engine4_jarvis_audit.sh --prod [sport]
#   API_KEY=xxx ./scripts/engine4_jarvis_audit.sh --prod nba

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

PROD_URL="${PROD_URL:-https://web-production-7b2a.up.railway.app}"

usage() {
    echo "Engine 4 Jarvis Audit Script"
    echo ""
    echo "Usage:"
    echo "  $0 --local                    Run local audit (synthetic picks)"
    echo "  $0 --prod [sport]             Run production audit (default: NBA)"
    echo "  $0 --help                     Show this help"
    echo ""
    echo "Environment Variables:"
    echo "  API_KEY    API key for production (required for --prod)"
    echo "  PROD_URL   Production URL (default: $PROD_URL)"
    echo ""
    echo "Examples:"
    echo "  $0 --local"
    echo "  API_KEY=xxx $0 --prod nba"
    echo "  API_KEY=xxx PROD_URL=http://localhost:8000 $0 --prod nhl"
}

run_local() {
    echo "======================================"
    echo "ENGINE 4 JARVIS AUDIT - LOCAL"
    echo "======================================"
    python3 scripts/engine4_jarvis_audit.py --local
}

run_prod() {
    SPORT="${1:-NBA}"
    if [ -z "$API_KEY" ]; then
        echo "ERROR: API_KEY environment variable required for production audit"
        exit 1
    fi

    echo "======================================"
    echo "ENGINE 4 JARVIS AUDIT - PRODUCTION"
    echo "URL: $PROD_URL"
    echo "Sport: $SPORT"
    echo "======================================"
    python3 scripts/engine4_jarvis_audit.py --url "$PROD_URL" --sport "$SPORT" --api-key "$API_KEY"
}

case "${1:-}" in
    --local)
        run_local
        ;;
    --prod)
        run_prod "${2:-NBA}"
        ;;
    --help|-h)
        usage
        ;;
    *)
        usage
        exit 1
        ;;
esac
