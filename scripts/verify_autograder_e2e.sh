#!/bin/bash
#
# verify_autograder_e2e.sh
# End-to-end verification of autograder pipeline
#
# This script proves that tomorrow's 6AM autograder will correctly grade
# today's picks by verifying:
# 1. Picks are persisted
# 2. Queue selector works
# 3. All picks can be resolved (dry-run passes)
#
# Exit codes:
#   0 = PASS (all validations succeeded)
#   1 = FAIL (validation errors found - unresolved picks or failures)
#   2 = PENDING (POST mode only: games not yet complete)
#
# Usage:
#   ./scripts/verify_autograder_e2e.sh [date] [--mode pre|post]
#   ./scripts/verify_autograder_e2e.sh 2026-01-26 --mode pre
#   ./scripts/verify_autograder_e2e.sh --mode post
#
# Mode semantics:
#   pre  (default) - Day-of verification. PASS if failed=0 AND unresolved=0 (pending OK)
#   post           - Next-day verification. PASS only if all picks graded
#
# Environment variables:
#   API_BASE - API base URL (default: http://localhost:8000)
#   API_KEY  - API key for authenticated endpoints (optional)

set -euo pipefail

# Configuration
API_BASE="${API_BASE:-http://localhost:8000}"
API_KEY="${API_KEY:-}"
MODE="pre"
DATE=""
SPORTS=("nba" "nfl" "mlb" "nhl" "ncaab")

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --mode)
            MODE="$2"
            shift 2
            ;;
        --mode=*)
            MODE="${1#*=}"
            shift
            ;;
        -*)
            echo "Unknown option: $1"
            exit 1
            ;;
        *)
            DATE="$1"
            shift
            ;;
    esac
done

# Default date to today if not specified
if [ -z "$DATE" ]; then
    DATE=$(date +%Y-%m-%d)
fi

# Validate mode
if [ "$MODE" != "pre" ] && [ "$MODE" != "post" ]; then
    echo "Invalid mode: $MODE (must be 'pre' or 'post')"
    exit 1
fi

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log_pass() {
    echo -e "${GREEN}[PASS]${NC} $1"
}

log_fail() {
    echo -e "${RED}[FAIL]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_pending() {
    echo -e "${YELLOW}[PENDING]${NC} $1"
}

# Build auth header if API_KEY is set
AUTH_HEADER=""
if [ -n "$API_KEY" ]; then
    AUTH_HEADER="-H X-API-Key:${API_KEY}"
fi

# Track overall status
OVERALL_STATUS="PASS"
PICKS_SAVED=0
QUEUE_COUNT=0
DRY_RUN_STATUS="UNKNOWN"

log "=== AUTOGRADER E2E VERIFICATION ==="
log "Date: $DATE"
log "Mode: $MODE"
log "API Base: $API_BASE"
log ""

# =============================================================================
# STEP 1: Health Check
# =============================================================================
log "Step 1: Checking API health..."

HEALTH=$(curl -sf "${API_BASE}/health" 2>/dev/null || echo '{"status":"error"}')
if echo "$HEALTH" | grep -q '"status":"healthy"'; then
    log_pass "API is healthy"
else
    log_fail "API health check failed"
    echo "$HEALTH"
    exit 1
fi

# =============================================================================
# STEP 2: Best Bets Available (ensures picks are generated)
# =============================================================================
log ""
log "Step 2: Verifying best-bets endpoints for all 5 sports..."

for SPORT in "${SPORTS[@]}"; do
    RESP=$(curl -sf $AUTH_HEADER "${API_BASE}/live/best-bets/${SPORT}" 2>/dev/null || echo '{"error":true}')

    if echo "$RESP" | grep -q '"error"'; then
        log_fail "/live/best-bets/${SPORT} returned error"
        OVERALL_STATUS="FAIL"
    else
        # Extract pick counts
        PROP_COUNT=$(echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('props',{}).get('count',0))" 2>/dev/null || echo "0")
        GAME_COUNT=$(echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('game_picks',{}).get('count',0))" 2>/dev/null || echo "0")
        TOTAL=$((PROP_COUNT + GAME_COUNT))
        PICKS_SAVED=$((PICKS_SAVED + TOTAL))
        SPORT_UPPER=$(echo "$SPORT" | tr '[:lower:]' '[:upper:]')
        log_pass "${SPORT_UPPER}: ${TOTAL} picks (${PROP_COUNT} props, ${GAME_COUNT} games)"
    fi
done

log "Total picks saved: ${PICKS_SAVED}"

# =============================================================================
# STEP 3: Grader & Scheduler Status
# =============================================================================
log ""
log "Step 3: Checking grader and scheduler status..."

GRADER_STATUS=$(curl -sf $AUTH_HEADER "${API_BASE}/live/grader/status" 2>/dev/null || echo '{"available":false}')
if echo "$GRADER_STATUS" | grep -q '"available":true'; then
    log_pass "Grader is available"
else
    log_fail "Grader not available"
    OVERALL_STATUS="FAIL"
fi

SCHEDULER_STATUS=$(curl -sf $AUTH_HEADER "${API_BASE}/live/scheduler/status" 2>/dev/null || echo '{"available":false}')
if echo "$SCHEDULER_STATUS" | grep -q '"available":true'; then
    log_pass "Scheduler is available"
else
    log_warn "Scheduler not available (may be disabled)"
fi

# =============================================================================
# STEP 4: Queue Selector Check
# =============================================================================
log ""
log "Step 4: Testing queue selector..."

QUEUE=$(curl -sf $AUTH_HEADER "${API_BASE}/live/grader/queue?date=${DATE}" 2>/dev/null || echo '{"error":true}')

if echo "$QUEUE" | grep -q '"error"'; then
    log_fail "Queue selector endpoint failed"
    OVERALL_STATUS="FAIL"
else
    QUEUE_COUNT=$(echo "$QUEUE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('total',0))" 2>/dev/null || echo "0")
    log_pass "Queue contains ${QUEUE_COUNT} ungraded picks"

    # Show breakdown by sport
    echo "$QUEUE" | python3 -c "
import sys, json
d = json.load(sys.stdin)
for sport, count in d.get('by_sport', {}).items():
    print(f'       {sport}: {count} picks')
" 2>/dev/null || true
fi

# =============================================================================
# STEP 5: Dry-Run Validation (THE KEY PROOF)
# =============================================================================
log ""
log "Step 5: Running dry-run validation (mode=${MODE})..."
log "        This proves all picks can be graded tomorrow."

DRY_RUN=$(curl -sf -X POST $AUTH_HEADER \
    -H "Content-Type: application/json" \
    -d "{\"date\":\"${DATE}\",\"mode\":\"${MODE}\",\"sports\":[\"NBA\",\"NFL\",\"MLB\",\"NHL\",\"NCAAB\"]}" \
    "${API_BASE}/live/grader/dry-run" 2>/dev/null || echo '{"overall_status":"ERROR"}')

DRY_RUN_STATUS=$(echo "$DRY_RUN" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('overall_status','ERROR'))" 2>/dev/null || echo "ERROR")
FAILED=$(echo "$DRY_RUN" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('summary',{}).get('failed',0))" 2>/dev/null || echo "0")
UNRESOLVED=$(echo "$DRY_RUN" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('summary',{}).get('unresolved',0))" 2>/dev/null || echo "0")
PENDING=$(echo "$DRY_RUN" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('summary',{}).get('pending',0))" 2>/dev/null || echo "0")
GRADED=$(echo "$DRY_RUN" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('summary',{}).get('graded',0))" 2>/dev/null || echo "0")
PRE_MODE_PASS=$(echo "$DRY_RUN" | python3 -c "import sys,json; d=json.load(sys.stdin); print('true' if d.get('pre_mode_pass',False) else 'false')" 2>/dev/null || echo "false")

log "       Graded: ${GRADED}, Pending: ${PENDING}, Failed: ${FAILED}, Unresolved: ${UNRESOLVED}"

# Show unresolved picks if any
if [ "$UNRESOLVED" != "0" ]; then
    log_fail "Unresolved picks found:"
    echo "$DRY_RUN" | python3 -c "
import sys, json
d = json.load(sys.stdin)
for up in d.get('unresolved_picks', [])[:5]:
    print(f'       {up.get(\"pick_id\")}: {up.get(\"reason\")} - {up.get(\"player\",\"N/A\")}')
" 2>/dev/null || true
fi

# Show failed picks if any
if [ "$FAILED" != "0" ]; then
    log_fail "Failed picks found:"
    echo "$DRY_RUN" | python3 -c "
import sys, json
d = json.load(sys.stdin)
for fp in d.get('failed_picks', [])[:5]:
    print(f'       {fp.get(\"pick_id\")}: {fp.get(\"reason\")} - {fp.get(\"player\",\"N/A\")}')
" 2>/dev/null || true
fi

# Determine status based on mode
if [ "$MODE" = "pre" ]; then
    # PRE mode: PASS if failed=0 AND unresolved=0 (pending is OK)
    if [ "$PRE_MODE_PASS" = "true" ]; then
        if [ "$PENDING" != "0" ]; then
            log_pending "Games not yet complete - picks are valid and ready for grading"
        else
            log_pass "All picks validated and graded"
        fi
    else
        log_fail "Validation errors found (failed=${FAILED}, unresolved=${UNRESOLVED})"
        OVERALL_STATUS="FAIL"
    fi
else
    # POST mode: PASS only if all graded
    if [ "$FAILED" = "0" ] && [ "$UNRESOLVED" = "0" ] && [ "$PENDING" = "0" ]; then
        log_pass "All picks validated and graded"
    elif [ "$FAILED" != "0" ] || [ "$UNRESOLVED" != "0" ]; then
        log_fail "Validation errors found (failed=${FAILED}, unresolved=${UNRESOLVED})"
        OVERALL_STATUS="FAIL"
    else
        log_pending "${PENDING} picks still pending grading"
        OVERALL_STATUS="PENDING"
    fi
fi

# =============================================================================
# FINAL SUMMARY
# =============================================================================
log ""
log "=== VERIFICATION SUMMARY ==="
log "Date: ${DATE}"
log "Mode: ${MODE}"
log "Picks saved: ${PICKS_SAVED}"
log "Queue count: ${QUEUE_COUNT}"
log "Dry-run: graded=${GRADED}, pending=${PENDING}, failed=${FAILED}, unresolved=${UNRESOLVED}"
log ""

# Exit based on overall status
case "$OVERALL_STATUS" in
    "PASS")
        echo -e "${GREEN}=== VERIFICATION PASSED ===${NC}"
        if [ "$MODE" = "pre" ]; then
            echo "All picks are valid and ready for grading."
            echo "Tomorrow's 6AM autograder will successfully grade these picks."
        else
            echo "All picks have been successfully graded."
        fi
        exit 0
        ;;
    "PENDING")
        echo -e "${YELLOW}=== VERIFICATION PENDING ===${NC}"
        echo "All picks are valid, but games haven't completed yet."
        if [ "$MODE" = "post" ]; then
            echo "Run again after games finish for full validation."
        fi
        exit 2
        ;;
    "FAIL")
        echo -e "${RED}=== VERIFICATION FAILED ===${NC}"
        echo "Some picks cannot be resolved. Fix before tomorrow's grader runs."
        exit 1
        ;;
esac
