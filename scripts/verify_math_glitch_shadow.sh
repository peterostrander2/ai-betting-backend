#!/usr/bin/env bash
#
# VERIFY MATH GLITCH SHADOW CONFLUENCE (v20.22)
# ==============================================
# Analyzes 7 days of shadow confluence data to determine if math signals
# should be promoted to full confluence boost in v21.
#
# Usage:
#   ./scripts/verify_math_glitch_shadow.sh
#   SHADOW_LOG_PATH=/custom/path.jsonl ./scripts/verify_math_glitch_shadow.sh
#
# Promotion Criteria:
#   - Fire rate: 3-15% (too rare = irrelevant, too common = noise)
#   - Outcome delta: Positive correlation with better outcomes
#   - Calibration: Higher final_score when would_apply=true
#
set -euo pipefail

# ============================================================
# CONFIGURATION
# ============================================================
SHADOW_LOG="${SHADOW_LOG_PATH:-/data/shadow/math_glitch_confluence.jsonl}"

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# ============================================================
# CHECK FILE EXISTS
# ============================================================
echo ""
echo "Math Glitch Confluence Shadow Analysis"
echo "======================================="
echo ""

if [[ ! -f "$SHADOW_LOG" ]]; then
    echo -e "${RED}ERROR: Shadow log not found at: $SHADOW_LOG${NC}"
    echo "Shadow logging starts after v20.22 deployment."
    echo "Wait for picks to be generated before running this analysis."
    exit 1
fi

# ============================================================
# BASIC STATS
# ============================================================
TOTAL=$(wc -l < "$SHADOW_LOG" | tr -d ' ')
echo "Total entries: $TOTAL"
echo ""

if [[ "$TOTAL" -lt 10 ]]; then
    echo -e "${YELLOW}WARNING: Only $TOTAL entries. Need more data for reliable analysis.${NC}"
    echo "Recommend waiting until at least 100 entries accumulated."
    echo ""
fi

# ============================================================
# FIRE RATE
# ============================================================
WOULD_APPLY=$(grep -c '"would_apply": true' "$SHADOW_LOG" || echo "0")
WOULD_NOT=$(grep -c '"would_apply": false' "$SHADOW_LOG" || echo "0")

if [[ "$TOTAL" -gt 0 ]]; then
    FIRE_RATE=$(echo "scale=2; $WOULD_APPLY * 100 / $TOTAL" | bc)
else
    FIRE_RATE="0.00"
fi

echo -e "${CYAN}Fire Rate Analysis${NC}"
echo "-------------------"
echo "would_apply=true:  $WOULD_APPLY"
echo "would_apply=false: $WOULD_NOT"
echo "Fire rate: ${FIRE_RATE}%"
echo ""

# Evaluate fire rate
if (( $(echo "$FIRE_RATE < 3" | bc -l) )); then
    echo -e "${YELLOW}ASSESSMENT: Fire rate too low (<3%) - signal may be irrelevant${NC}"
elif (( $(echo "$FIRE_RATE > 15" | bc -l) )); then
    echo -e "${YELLOW}ASSESSMENT: Fire rate too high (>15%) - signal may be noise${NC}"
else
    echo -e "${GREEN}ASSESSMENT: Fire rate in target range (3-15%)${NC}"
fi
echo ""

# ============================================================
# AVERAGE FINAL SCORE COMPARISON
# ============================================================
echo -e "${CYAN}Final Score Analysis${NC}"
echo "--------------------"

if [[ "$WOULD_APPLY" -gt 0 ]]; then
    AVG_WITH=$(grep '"would_apply": true' "$SHADOW_LOG" | \
        jq -s 'map(.final_score // 0) | add / length')
    echo "Avg final_score (would_apply=true):  $AVG_WITH"
else
    AVG_WITH="N/A"
    echo "Avg final_score (would_apply=true):  N/A (no samples)"
fi

if [[ "$WOULD_NOT" -gt 0 ]]; then
    AVG_WITHOUT=$(grep '"would_apply": false' "$SHADOW_LOG" | \
        jq -s 'map(.final_score // 0) | add / length')
    echo "Avg final_score (would_apply=false): $AVG_WITHOUT"
else
    AVG_WITHOUT="N/A"
    echo "Avg final_score (would_apply=false): N/A (no samples)"
fi

# Compare if both have data
if [[ "$AVG_WITH" != "N/A" && "$AVG_WITHOUT" != "N/A" ]]; then
    DELTA=$(echo "scale=2; $AVG_WITH - $AVG_WITHOUT" | bc)
    echo ""
    if (( $(echo "$DELTA > 0" | bc -l) )); then
        echo -e "${GREEN}DELTA: +$DELTA (picks with math confluence have HIGHER scores)${NC}"
    elif (( $(echo "$DELTA < 0" | bc -l) )); then
        echo -e "${YELLOW}DELTA: $DELTA (picks with math confluence have LOWER scores)${NC}"
    else
        echo "DELTA: 0 (no difference)"
    fi
fi
echo ""

# ============================================================
# TIER DISTRIBUTION WHEN WOULD_APPLY
# ============================================================
echo -e "${CYAN}Tier Distribution (when would_apply=true)${NC}"
echo "------------------------------------------"

if [[ "$WOULD_APPLY" -gt 0 ]]; then
    grep '"would_apply": true' "$SHADOW_LOG" | \
        jq -r '.tier' | sort | uniq -c | sort -rn
else
    echo "No samples with would_apply=true"
fi
echo ""

# ============================================================
# SIGNAL COMBINATIONS
# ============================================================
echo -e "${CYAN}Signal Combinations (when would_apply=true)${NC}"
echo "--------------------------------------------"

if [[ "$WOULD_APPLY" -gt 0 ]]; then
    grep '"would_apply": true' "$SHADOW_LOG" | \
        jq -r '.signals | sort | join("+")' | sort | uniq -c | sort -rn | head -10
else
    echo "No samples with would_apply=true"
fi
echo ""

# ============================================================
# SPORT BREAKDOWN
# ============================================================
echo -e "${CYAN}Fire Rate by Sport${NC}"
echo "-------------------"

for SPORT in NBA NFL NHL MLB NCAAB; do
    SPORT_TOTAL=$(grep "\"sport\": \"$SPORT\"" "$SHADOW_LOG" | wc -l | tr -d ' ')
    SPORT_APPLY=$(grep "\"sport\": \"$SPORT\"" "$SHADOW_LOG" | grep -c '"would_apply": true' || echo "0")
    if [[ "$SPORT_TOTAL" -gt 0 ]]; then
        SPORT_RATE=$(echo "scale=2; $SPORT_APPLY * 100 / $SPORT_TOTAL" | bc)
        echo "$SPORT: $SPORT_APPLY / $SPORT_TOTAL (${SPORT_RATE}%)"
    fi
done
echo ""

# ============================================================
# RECENT ENTRIES
# ============================================================
echo -e "${CYAN}Recent Entries (last 5)${NC}"
echo "------------------------"
tail -5 "$SHADOW_LOG" | jq -c '{ts: .timestamp, sport: .sport, would_apply: .would_apply, signals: .signals, boost: .boost, tier: .tier}'
echo ""

# ============================================================
# PROMOTION RECOMMENDATION
# ============================================================
echo "=============================================="
echo -e "${CYAN}PROMOTION DECISION${NC}"
echo "=============================================="
echo ""

# Check criteria
PROMOTE=true
REASONS=()

# 1. Fire rate
if (( $(echo "$FIRE_RATE < 3 || $FIRE_RATE > 15" | bc -l) )); then
    PROMOTE=false
    REASONS+=("Fire rate outside target range (3-15%)")
fi

# 2. Score delta
if [[ "$AVG_WITH" != "N/A" && "$AVG_WITHOUT" != "N/A" ]]; then
    DELTA=$(echo "scale=2; $AVG_WITH - $AVG_WITHOUT" | bc)
    if (( $(echo "$DELTA < 0" | bc -l) )); then
        PROMOTE=false
        REASONS+=("Negative score delta (math confluence correlated with LOWER scores)")
    fi
fi

# 3. Minimum samples
if [[ "$WOULD_APPLY" -lt 20 ]]; then
    PROMOTE=false
    REASONS+=("Insufficient samples (need at least 20 would_apply=true)")
fi

if [[ "$PROMOTE" == true ]]; then
    echo -e "${GREEN}RECOMMEND: PROMOTE to v21${NC}"
    echo ""
    echo "Add MATH_GLITCH_CONFLUENCE to scoring_contract.py with +0.5 boost."
    echo ""
else
    echo -e "${YELLOW}DO NOT PROMOTE - Needs more time or investigation${NC}"
    echo ""
    echo "Reasons:"
    for REASON in "${REASONS[@]}"; do
        echo "  - $REASON"
    done
    echo ""
    echo "Continue shadow monitoring and re-evaluate in 7 days."
fi
echo ""
