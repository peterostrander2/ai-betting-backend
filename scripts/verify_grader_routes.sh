#!/bin/bash
# ============================================================
# GRADER ROUTES VERIFICATION
# Paste this entire block into Railway shell after deploy
# ============================================================

BACKEND="https://web-production-7b2a.up.railway.app"

echo ""
echo "========================================================"
echo "  GRADER ROUTES VERIFICATION"
echo "  $(date)"
echo "========================================================"
echo ""

# ----------------------------------------------------------
# TEST 1: Confirm new endpoints exist in main.py
# ----------------------------------------------------------
echo "TEST 1: CODE DEPLOYED"
echo "------------------------------"

echo -n "  [1a] /grader/weights/{sport} in main.py: "
if grep -q 'grader/weights/{sport}' main.py 2>/dev/null; then
  echo "PASS ✅"
else
  echo "FAIL ❌"
fi

echo -n "  [1b] /grader/bias/{sport} in main.py: "
if grep -q 'grader/bias/{sport}' main.py 2>/dev/null; then
  echo "PASS ✅"
else
  echo "FAIL ❌"
fi

echo -n "  [1c] /grader/run-audit in main.py: "
if grep -q 'grader/run-audit' main.py 2>/dev/null; then
  echo "PASS ✅"
else
  echo "FAIL ❌"
fi

echo -n "  [1d] /grader/performance/{sport} in main.py: "
if grep -q 'grader/performance/{sport}' main.py 2>/dev/null; then
  echo "PASS ✅"
else
  echo "FAIL ❌"
fi

echo ""

# ----------------------------------------------------------
# TEST 2: Hit every endpoint from inside the container
# ----------------------------------------------------------
echo "TEST 2: ENDPOINTS RESPOND (localhost)"
echo "------------------------------"

echo -n "  [2a] /grader/status: "
CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/grader/status)
echo "$CODE $([ "$CODE" = "200" ] && echo "✅" || echo "❌")"

echo -n "  [2b] /grader/weights/NBA: "
CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/grader/weights/NBA)
echo "$CODE $([ "$CODE" = "200" ] && echo "✅" || echo "❌")"

echo -n "  [2c] /grader/bias/NBA: "
CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/grader/bias/NBA)
echo "$CODE $([ "$CODE" = "200" ] && echo "✅" || echo "❌")"

echo -n "  [2d] /grader/run-audit (POST): "
CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8000/grader/run-audit)
echo "$CODE $([ "$CODE" = "200" ] && echo "✅" || echo "❌")"

echo -n "  [2e] /grader/performance/NBA: "
CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/grader/performance/NBA)
echo "$CODE $([ "$CODE" = "200" ] && echo "✅" || echo "❌")"

echo ""

# ----------------------------------------------------------
# TEST 3: Hit endpoints from outside (public URL, no auth)
# ----------------------------------------------------------
echo "TEST 3: ENDPOINTS RESPOND (public URL, no auth)"
echo "------------------------------"

echo -n "  [3a] /grader/status: "
CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BACKEND/grader/status")
echo "$CODE $([ "$CODE" = "200" ] && echo "✅" || echo "❌")"

echo -n "  [3b] /grader/weights/NBA: "
CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BACKEND/grader/weights/NBA")
echo "$CODE $([ "$CODE" = "200" ] && echo "✅" || echo "❌")"

echo -n "  [3c] /grader/bias/NBA: "
CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BACKEND/grader/bias/NBA")
echo "$CODE $([ "$CODE" = "200" ] && echo "✅" || echo "❌")"

echo -n "  [3d] /grader/run-audit (POST): "
CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BACKEND/grader/run-audit")
echo "$CODE $([ "$CODE" = "200" ] && echo "✅" || echo "❌")"

echo -n "  [3e] /grader/performance/NBA: "
CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BACKEND/grader/performance/NBA")
echo "$CODE $([ "$CODE" = "200" ] && echo "✅" || echo "❌")"

echo ""

# ----------------------------------------------------------
# TEST 4: Validate response content
# ----------------------------------------------------------
echo "TEST 4: RESPONSE CONTENT"
echo "------------------------------"

echo "  [4a] /grader/weights/NBA:"
curl -s http://localhost:8000/grader/weights/NBA | python3 -c "
import sys, json
data = json.load(sys.stdin)
if 'error' in data:
    print(f'    ERROR: {data[\"error\"]}')
    sys.exit(1)
sport = data.get('sport', '?')
weights = data.get('weights', {})
print(f'    Sport: {sport}')
print(f'    Stat types tracked: {len(weights)}')
for stat in ['points', 'spread', 'total']:
    if stat in weights:
        w = weights[stat]
        print(f'    {stat}: defense={w[\"defense\"]:.4f} pace={w[\"pace\"]:.4f} vacuum={w[\"vacuum\"]:.4f} lstm={w[\"lstm\"]:.4f}')
if len(weights) > 0:
    print('    PASS ✅')
else:
    print('    FAIL ❌ — no weights returned')
" 2>/dev/null || echo "    FAIL ❌ — endpoint returned invalid JSON"

echo ""
echo "  [4b] /grader/bias/NBA?days_back=7:"
curl -s "http://localhost:8000/grader/bias/NBA?days_back=7" | python3 -c "
import sys, json
data = json.load(sys.stdin)
if 'error' in data:
    print(f'    ERROR: {data[\"error\"]}')
    sys.exit(0)
bias = data.get('bias', {})
if 'error' in bias:
    print(f'    No graded NBA data in last 7 days: {bias[\"error\"]}')
    print('    (Normal if no NBA picks were graded recently)')
    sys.exit(0)
overall = bias.get('overall', {})
factors = bias.get('factor_bias', {})
sample = bias.get('sample_size', 0)
print(f'    Sample size: {sample} picks')
print(f'    Hit rate: {overall.get(\"hit_rate\", \"?\")}%')
print(f'    Mean error: {overall.get(\"mean_error\", \"?\")}')
print(f'    Factors tracked: {list(factors.keys())}')
print('    PASS ✅')
" 2>/dev/null || echo "    FAIL ❌ — endpoint returned invalid JSON"

echo ""
echo "  [4c] /grader/performance/NBA?days_back=3:"
curl -s "http://localhost:8000/grader/performance/NBA?days_back=3" | python3 -c "
import sys, json
data = json.load(sys.stdin)
if 'error' in data:
    print(f'    ERROR: {data[\"error\"]}')
    sys.exit(1)
current = data.get('current', {})
history = data.get('daily_history', {})
print(f'    Total predictions: {current.get(\"total_predictions\", 0)}')
print(f'    Graded: {current.get(\"total_graded\", 0)}')
print(f'    Hit rate: {current.get(\"hit_rate\", 0)}%')
print(f'    Profitable (>52%%): {current.get(\"profitable\", False)}')
print(f'    Days in history: {len(history)}')
print('    PASS ✅')
" 2>/dev/null || echo "    FAIL ❌ — endpoint returned invalid JSON"

echo ""

# ----------------------------------------------------------
# TEST 5: Run audit and check it works
# ----------------------------------------------------------
echo "TEST 5: LIVE AUDIT TRIGGER"
echo "------------------------------"

echo "  Triggering /grader/run-audit..."
curl -s -X POST http://localhost:8000/grader/run-audit | python3 -c "
import sys, json
data = json.load(sys.stdin)
if 'error' in data:
    print(f'    ERROR: {data[\"error\"]}')
    sys.exit(1)
results = data.get('results', {})
print(f'    Audit status: {data.get(\"audit\", \"?\")}')
for sport, info in results.items():
    status = info.get('status', '?')
    sample = info.get('sample_size', 0)
    hit_rate = info.get('bias_summary', {}).get('hit_rate', '?')
    changes = info.get('weight_changes', {})
    moved = sum(1 for v in changes.values() if isinstance(v, dict) and v.get('delta', 0) != 0)
    print(f'    [{sport}] status={status} sample={sample} hit_rate={hit_rate}% weights_moved={moved}')
print('    PASS ✅')
" 2>/dev/null || echo "    FAIL ❌ — audit returned invalid response"

echo ""

# ----------------------------------------------------------
# TEST 6: All sports work
# ----------------------------------------------------------
echo "TEST 6: ALL SPORTS"
echo "------------------------------"

for SPORT in NBA NHL NFL MLB NCAAB; do
  echo -n "  [$SPORT] weights: "
  CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:8000/grader/weights/$SPORT")
  echo -n "$CODE "
  echo -n "| bias: "
  CODE2=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:8000/grader/bias/$SPORT")
  echo -n "$CODE2 "
  echo -n "| performance: "
  CODE3=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:8000/grader/performance/$SPORT")
  echo "$CODE3 $([ "$CODE" = "200" ] && [ "$CODE2" = "200" ] && [ "$CODE3" = "200" ] && echo "✅" || echo "❌")"
done

echo ""

# ----------------------------------------------------------
# BOOKMARK URLS
# ----------------------------------------------------------
echo "========================================================"
echo "  ALL DONE — BOOKMARK THESE URLS"
echo "========================================================"
echo ""
echo "  Status:        $BACKEND/grader/status"
echo "  NBA Weights:   $BACKEND/grader/weights/NBA"
echo "  NBA Bias:      $BACKEND/grader/bias/NBA?days_back=3"
echo "  NBA Perf:      $BACKEND/grader/performance/NBA?days_back=7"
echo "  Run Audit:     curl -X POST $BACKEND/grader/run-audit"
echo ""
echo "  Replace NBA with NFL, MLB, NHL, or NCAAB for other sports."
echo "========================================================"
echo ""
