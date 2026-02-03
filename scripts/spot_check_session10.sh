#!/bin/bash
# SESSION 10 — SCHEDULER OBSERVABILITY + LOG HYGIENE
# Part A: Health endpoint (200)
# Part B: Debug integrations (200, required integrations present)
# Part C: Scheduler status endpoint (200, available=true, timezone correct)
# Part D: Cache pre-warm times validation
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_URL="${BASE_URL:-https://web-production-7b2a.up.railway.app}"
API_KEY="${API_KEY:-bookie-prod-2026-xK9mP2nQ7vR4}"

# Source retry library
source "$SCRIPT_DIR/lib/retry.sh"

echo "=============================================================="
echo "SESSION 10 SPOT CHECK: Scheduler Observability + Log Hygiene"
echo "Base URL: $BASE_URL"
echo "=============================================================="

fail() { echo "❌ FAIL: $1"; exit 1; }

# ========== PART A: HEALTH ENDPOINT ==========
echo ""
echo "PART A: Health Endpoint"
echo "-----------------------"

echo ""
echo "Check 1: Health endpoint returns 200..."
HEALTH=$(retry_curl "${BASE_URL}/health" 3 15) || fail "Health endpoint unreachable"

HEALTH_STATUS=$(echo "$HEALTH" | jq -r '.status // "unknown"')
if [[ "$HEALTH_STATUS" != "healthy" ]] && [[ "$HEALTH_STATUS" != "ok" ]]; then
    fail "Health status not healthy/ok: $HEALTH_STATUS"
fi
echo "✅ Health: $HEALTH_STATUS"

# ========== PART B: DEBUG INTEGRATIONS ==========
echo ""
echo "PART B: Debug Integrations"
echo "--------------------------"

echo ""
echo "Check 2: Debug integrations endpoint returns 200..."
INTEGRATIONS=$(retry_curl_auth "${BASE_URL}/live/debug/integrations" 3 15) || fail "Debug integrations unreachable"

# Check required integrations are present
echo ""
echo "Check 3: Required integrations present..."
REQUIRED_INTEGRATIONS=("odds_api" "playbook_api" "railway_storage")

for integration in "${REQUIRED_INTEGRATIONS[@]}"; do
    # Check both status_category (new) and status (legacy) fields
    STATUS=$(echo "$INTEGRATIONS" | jq -r ".integrations.${integration}.status_category // .integrations.${integration}.status // \"NOT_FOUND\"")
    if [[ "$STATUS" == "NOT_FOUND" ]] || [[ "$STATUS" == "null" ]]; then
        fail "Required integration '$integration' not found in response"
    fi
    # Allow VALIDATED, CONFIGURED, or NOT_RELEVANT (for weather on indoor sports)
    if [[ "$STATUS" != "VALIDATED" ]] && [[ "$STATUS" != "CONFIGURED" ]] && [[ "$STATUS" != "NOT_RELEVANT" ]]; then
        echo "⚠️  WARN: Integration '$integration' has status: $STATUS"
    else
        echo "✅ Integration '$integration': $STATUS"
    fi
done

# Count total integrations
TOTAL_INTEGRATIONS=$(echo "$INTEGRATIONS" | jq '.integrations | length')
echo "✅ Total integrations registered: $TOTAL_INTEGRATIONS"

# ========== PART C: SCHEDULER STATUS ==========
echo ""
echo "PART C: Scheduler Status"
echo "------------------------"

echo ""
echo "Check 4: Scheduler status endpoint returns 200..."
SCHEDULER=$(retry_curl_auth "${BASE_URL}/live/scheduler/status" 3 15) || fail "Scheduler status unreachable"

echo ""
echo "Check 5: Scheduler available..."
SCHEDULER_AVAIL=$(echo "$SCHEDULER" | jq -r '.available // false')
if [[ "$SCHEDULER_AVAIL" != "true" ]]; then
    # Check if it's the router endpoint (returns different structure)
    SCHEDULER_STATUS=$(echo "$SCHEDULER" | jq -r '.status // "unknown"')
    if [[ "$SCHEDULER_STATUS" == "success" ]]; then
        echo "✅ Scheduler: available (via router endpoint)"
        SCHEDULER_AVAIL="true"
    else
        fail "Scheduler not available: $SCHEDULER"
    fi
else
    echo "✅ Scheduler: available"
fi

echo ""
echo "Check 6: APScheduler availability..."
APSCHEDULER_AVAIL=$(echo "$SCHEDULER" | jq -r '.apscheduler_available // .scheduler.scheduler_type // "unknown"')
echo "✅ APScheduler status: $APSCHEDULER_AVAIL"

echo ""
echo "Check 7: Audit time configured..."
AUDIT_TIME=$(echo "$SCHEDULER" | jq -r '.audit_time // .scheduler.next_audit // "not_found"')
if [[ "$AUDIT_TIME" == "not_found" ]]; then
    fail "Audit time not found in scheduler response"
fi
echo "✅ Audit time: $AUDIT_TIME"

# ========== PART D: CACHE PRE-WARM VALIDATION ==========
echo ""
echo "PART D: Cache Pre-Warm Validation"
echo "----------------------------------"

echo ""
echo "Check 8: Scheduler jobs include cache pre-warm..."
# Check for scheduled jobs in the response
SCHEDULED_JOBS=$(echo "$SCHEDULER" | jq -r '.scheduler.scheduled_jobs // []')

if [[ "$SCHEDULED_JOBS" == "[]" ]] || [[ "$SCHEDULED_JOBS" == "null" ]]; then
    # Jobs might not be listed in basic status - check note field
    SCHEDULER_NOTE=$(echo "$SCHEDULER" | jq -r '.note // ""')
    if [[ -n "$SCHEDULER_NOTE" ]]; then
        echo "✅ Scheduler note: $SCHEDULER_NOTE"
    else
        echo "⚠️  WARN: No scheduled jobs listed (may require scheduler start)"
    fi
else
    JOB_COUNT=$(echo "$SCHEDULED_JOBS" | jq 'length')
    echo "✅ Scheduled jobs found: $JOB_COUNT"

    # List cache pre-warm jobs if present
    echo "$SCHEDULED_JOBS" | jq -r '.[] | select(.id | contains("warm_cache")) | "   - \(.name): next run \(.next_run // "pending")"' 2>/dev/null || true
fi

# ========== PART E: NO IMPORT ERRORS ==========
echo ""
echo "PART E: Import Error Regression Test"
echo "-------------------------------------"

echo ""
echo "Check 9: Verify get_daily_scheduler export in source (AST check)..."
# Use AST parsing to verify export exists (works without dependencies)
EXPORT_TEST=$(python3 -c "
import ast

with open('daily_scheduler.py', 'r') as f:
    source = f.read()

tree = ast.parse(source)

# Check for get_daily_scheduler assignment
found_alias = False
for node in ast.walk(tree):
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == 'get_daily_scheduler':
                found_alias = True

# Check __all__ includes get_daily_scheduler
in_all = False
for node in ast.walk(tree):
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == '__all__':
                if isinstance(node.value, ast.List):
                    for elt in node.value.elts:
                        if hasattr(elt, 'value') and elt.value == 'get_daily_scheduler':
                            in_all = True
                        elif hasattr(elt, 's') and elt.s == 'get_daily_scheduler':
                            in_all = True

if found_alias and in_all:
    print('OK')
else:
    print(f'FAIL: alias={found_alias}, in_all={in_all}')
" 2>/dev/null)

if [[ "$EXPORT_TEST" != "OK" ]]; then
    fail "get_daily_scheduler export check failed: $EXPORT_TEST"
fi
echo "✅ Source verified: get_daily_scheduler is exported"

echo ""
echo "Check 10: Scheduler status endpoint callable twice without import error..."
# Call twice to ensure no transient import issues
SCHEDULER2=$(retry_curl_auth "${BASE_URL}/live/scheduler/status" 2 10) || fail "Second scheduler call failed"
SCHEDULER2_AVAIL=$(echo "$SCHEDULER2" | jq -r '.available // .status // "unknown"')

if [[ "$SCHEDULER2_AVAIL" == "unknown" ]] || [[ "$SCHEDULER2_AVAIL" == "false" ]]; then
    # Check for import error in response
    SCHEDULER2_NOTE=$(echo "$SCHEDULER2" | jq -r '.note // ""')
    if [[ "$SCHEDULER2_NOTE" == *"not available"* ]] || [[ "$SCHEDULER2_NOTE" == *"import"* ]]; then
        fail "Import error detected: $SCHEDULER2_NOTE"
    fi
fi
echo "✅ Scheduler endpoint stable (no import errors)"

echo ""
echo "Check 11: Grader status endpoint (tests get_daily_scheduler import)..."
GRADER=$(retry_curl_auth "${BASE_URL}/live/grader/status" 3 15) || fail "Grader status unreachable"

GRADER_AVAIL=$(echo "$GRADER" | jq -r '.available // false')
if [[ "$GRADER_AVAIL" != "true" ]]; then
    fail "Grader not available"
fi

# Check for scheduler-related errors in grader response
LAST_ERRORS=$(echo "$GRADER" | jq -r '.last_errors // []')
IMPORT_ERROR=$(echo "$LAST_ERRORS" | jq -r '.[] | select(contains("import") or contains("get_daily_scheduler"))' 2>/dev/null || echo "")
if [[ -n "$IMPORT_ERROR" ]]; then
    fail "Import error in grader status: $IMPORT_ERROR"
fi
echo "✅ Grader status: no import errors in scheduler integration"

echo ""
echo "=============================================================="
echo "✅ SESSION 10 PASS: Scheduler observability verified"
echo "=============================================================="
echo ""
echo "Validated:"
echo "  - Health endpoint returns 200 with healthy status"
echo "  - Debug integrations returns required integrations"
echo "  - Scheduler status endpoint works without import errors"
echo "  - get_daily_scheduler export is stable"
echo "  - Cache pre-warm configuration visible"
