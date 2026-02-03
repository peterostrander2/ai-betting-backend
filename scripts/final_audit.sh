#!/usr/bin/env bash
set -euo pipefail

BACKEND_DIR="${1:-/Users/apple/Desktop/ai-betting-backend-main}"
FRONTEND_DIR="${2:-/Users/apple/Desktop/bookie-member-app}"

printf "============================================\n"
printf "FINAL AUDIT - Checking for Any Gaps\n"
printf "============================================\n\n"

# GAP CHECK 1: Entry point clarity
printf "Gap Check 1: Is there a clear 'start here' for new sessions?\n\n"
printf "BACKEND:\n"
ls -1 "$BACKEND_DIR" | grep -E "^(README|CLAUDE|MASTER|SESSION)" || echo "  ⚠️ No README.md"
printf "\nFRONTEND:\n"
ls -1 "$FRONTEND_DIR" | grep -E "^(README|CLAUDE|MASTER|SESSION)" || echo "  ⚠️ No README.md"
printf "\n"

# GAP CHECK 2: Cross-repo sync
printf "Gap Check 2: Is there a way to verify frontend/backend contracts match?\n\n"
printf "BACKEND scoring contract:\n"
rg -n "MIN_FINAL|GOLD_STAR" "$BACKEND_DIR/core/scoring_contract.py" || echo "  ⚠️ No scoring contract match"
printf "\nFRONTEND scoring contract:\n"
rg -n "MIN_FINAL|GOLD_STAR" "$FRONTEND_DIR/core/frontend_scoring_contract.js" || echo "  ⚠️ No scoring contract match"
printf "\n"

# GAP CHECK 3: Recovery procedures
printf "Gap Check 3: Is there a 'what to do if things break' guide?\n"
ls -1 "$BACKEND_DIR/docs" | rg -i "recover|troubleshoot|debug" || echo "  ⚠️ No recovery guide"
ls -1 "$FRONTEND_DIR/docs" | rg -i "recover|troubleshoot|debug" || echo "  ⚠️ No recovery guide"
printf "\n"

# GAP CHECK 4: Session continuity
printf "Gap Check 4: Can a new Claude session quickly understand the system?\n\n"
printf "Checking for session start guides...\n"
ls -1 "$BACKEND_DIR" | grep -E "SESSION|START|ONBOARD" || echo "  ⚠️ No session guide"
ls -1 "$FRONTEND_DIR" | grep -E "SESSION|START|ONBOARD" || echo "  ⚠️ No session guide"
printf "\n"

# GAP CHECK 5: Repo identification
printf "Gap Check 5: Is it clear which repo is which?\n\n"
printf "BACKEND has identifier:\n"
grep -Ei "backend|bookie.*backend|ai-betting" "$BACKEND_DIR/README.md" 2>/dev/null | head -1 || echo "  ⚠️ No clear identifier in README"
printf "\nFRONTEND has identifier:\n"
grep -Ei "frontend|member.*app|bookie.*member" "$FRONTEND_DIR/README.md" 2>/dev/null | head -1 || echo "  ⚠️ No clear identifier in README"
printf "\n"

printf "============================================\n"
printf "RECOMMENDATIONS\n"
printf "============================================\n"
