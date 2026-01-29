#!/bin/bash
#
# System Verification Script
# Run this anytime to verify all systems are operational
#

set -e

API_KEY="${API_KEY:-bookie-prod-2026-xK9mP2nQ7vR4}"
BASE_URL="https://web-production-7b2a.up.railway.app"

echo "============================================================"
echo "BOOKIE-O-EM SYSTEM VERIFICATION"
echo "============================================================"
echo

# Check 1: Health endpoint
echo "1. HEALTH CHECK"
HEALTH=$(curl -s "$BASE_URL/health")
echo "   $HEALTH"
echo

# Check 2: /debug/time
echo "2. ET TIMEZONE (/debug/time)"
TIME_DATA=$(curl -s "$BASE_URL/live/debug/time" -H "X-API-Key: $API_KEY")
ET_DATE=$(echo "$TIME_DATA" | python3 -c "import json, sys; print(json.load(sys.stdin)['et_date'])")
echo "   et_date: $ET_DATE"
echo

# Check 3: Best-bets NBA
echo "3. BEST-BETS NBA"
NBA_DATA=$(curl -s "$BASE_URL/live/best-bets/NBA?max_props=3&max_games=3" -H "X-API-Key: $API_KEY")
NBA_PROPS=$(echo "$NBA_DATA" | python3 -c "import json, sys; d=json.load(sys.stdin); print(d['props']['count'])")
NBA_GAMES=$(echo "$NBA_DATA" | python3 -c "import json, sys; d=json.load(sys.stdin); print(d['game_picks']['count'])")
echo "   Props: $NBA_PROPS"
echo "   Game picks: $NBA_GAMES"
echo

# Check 4: Best-bets NHL
echo "4. BEST-BETS NHL"
NHL_DATA=$(curl -s "$BASE_URL/live/best-bets/NHL?max_props=3&max_games=3" -H "X-API-Key: $API_KEY")
NHL_PROPS=$(echo "$NHL_DATA" | python3 -c "import json, sys; d=json.load(sys.stdin); print(d['props']['count'])")
NHL_GAMES=$(echo "$NHL_DATA" | python3 -c "import json, sys; d=json.load(sys.stdin); print(d['game_picks']['count'])")
echo "   Props: $NHL_PROPS"
echo "   Game picks: $NHL_GAMES"
echo

# Check 5: ET filtering match
echo "5. ET FILTERING VERIFICATION"
NBA_DEBUG=$(curl -s "$BASE_URL/live/best-bets/NBA?debug=1" -H "X-API-Key: $API_KEY")
FILTER_DATE=$(echo "$NBA_DEBUG" | python3 -c "import json, sys; d=json.load(sys.stdin); print(d['debug']['date_window_et']['filter_date'])")
if [ "$ET_DATE" == "$FILTER_DATE" ]; then
    echo "   ✓ PASS: filter_date ($FILTER_DATE) == et_date ($ET_DATE)"
else
    echo "   ✗ FAIL: filter_date ($FILTER_DATE) != et_date ($ET_DATE)"
    exit 1
fi
echo

# Check 6: Autograder
echo "6. AUTOGRADER STATUS"
GRADER=$(curl -s "$BASE_URL/live/grader/status" -H "X-API-Key: $API_KEY")
GRADER_AVAILABLE=$(echo "$GRADER" | python3 -c "import json, sys; print(json.load(sys.stdin)['available'])")
PREDICTIONS=$(echo "$GRADER" | python3 -c "import json, sys; print(json.load(sys.stdin)['pick_logger']['predictions_logged'])")
PENDING=$(echo "$GRADER" | python3 -c "import json, sys; print(json.load(sys.stdin)['pick_logger']['pending_to_grade'])")
echo "   Available: $GRADER_AVAILABLE"
echo "   Predictions logged: $PREDICTIONS"
echo "   Pending to grade: $PENDING"
echo

# Check 7: Autograder dry-run
echo "7. AUTOGRADER DRY-RUN (pre-mode)"
DRYRUN=$(curl -s -X POST "$BASE_URL/live/grader/dry-run" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"date":"'$ET_DATE'","mode":"pre"}')
TOTAL=$(echo "$DRYRUN" | python3 -c "import json, sys; print(json.load(sys.stdin)['total'])")
FAILED=$(echo "$DRYRUN" | python3 -c "import json, sys; print(json.load(sys.stdin)['failed'])")
PRE_PASS=$(echo "$DRYRUN" | python3 -c "import json, sys; print(json.load(sys.stdin)['pre_mode_pass'])")
echo "   Total picks: $TOTAL"
echo "   Failed: $FAILED"
echo "   pre_mode_pass: $PRE_PASS"
echo

echo "============================================================"
if [ "$GRADER_AVAILABLE" == "True" ] && [ "$PRE_PASS" == "True" ] && [ "$FAILED" == "0" ]; then
    echo "✓ ALL SYSTEMS OPERATIONAL"
else
    echo "✗ SYSTEM ISSUES DETECTED"
    exit 1
fi
echo "============================================================"
