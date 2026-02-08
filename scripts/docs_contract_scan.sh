#!/bin/bash
# Docs contract scan - scoring contract drift checks

set -e

fail() {
  echo "ERROR: $1"
  exit 1
}

DOCS=(
  "CLAUDE.md"
  "SCORING_LOGIC.md"
  "docs/AUDIT_MAP.md"
  "docs/ENDPOINT_CONTRACT.md"
  "docs/API_INTEGRATION_PLAN.md"
)

# Forbidden phrases (allowed only when explicitly marked as forbidden/blocked)
FORBIDDEN_PATTERNS=(
  "BASE_5"
  "5-engine"
  "five-engine"
  "context weight"
  "context_weight"
  "ENGINE_WEIGHTS\\[\\\"context\\\"\\]"
)

ALLOW_CONTEXT="forbidden|block|blocked|drift scan|do not|never"

for doc in "${DOCS[@]}"; do
  if [ ! -f "$doc" ]; then
    continue
  fi
  for pat in "${FORBIDDEN_PATTERNS[@]}"; do
    if rg -n "$pat" "$doc" >/tmp/docs_contract_forbidden 2>/dev/null; then
      FILTERED=$(cat /tmp/docs_contract_forbidden | rg -v -i "$ALLOW_CONTEXT" || true)
      if [[ "$pat" == "BASE_5" || "$pat" == "5-engine" || "$pat" == "five-engine" ]]; then
        FILTERED=$(echo "$FILTERED" | rg -vi "No BASE_5|option_a_drift|BASE_5 introduced" || true)
        FILTERED=$(echo "$FILTERED" | rg -i "weight|engine|formula|score|=" || true)
      fi
      if [[ "$pat" == "ENGINE_WEIGHTS\\[\\\"context\\\"\\]" ]]; then
        FILTERED=$(echo "$FILTERED" | rg -i "use|used|set|equals|=" || true)
      fi
      if [ -n "$FILTERED" ]; then
        echo "Forbidden scoring reference in $doc: $pat"
        echo "$FILTERED"
        fail "Docs contract drift detected"
      fi
    fi
  done
done

# Pull canonical values from core/scoring_contract.py
read -r AI_W RESEARCH_W ESOTERIC_W JARVIS_W CONTEXT_CAP MSRF_CAP SERP_CAP JASON_CAP <<<"$(python3 - <<'PY'
from core.scoring_contract import ENGINE_WEIGHTS, CONTEXT_MODIFIER_CAP, MSRF_BOOST_CAP, SERP_BOOST_CAP_TOTAL, JASON_SIM_BOOST_CAP
print(
    ENGINE_WEIGHTS["ai"],
    ENGINE_WEIGHTS["research"],
    ENGINE_WEIGHTS["esoteric"],
    ENGINE_WEIGHTS["jarvis"],
    CONTEXT_MODIFIER_CAP,
    MSRF_BOOST_CAP,
    SERP_BOOST_CAP_TOTAL,
    JASON_SIM_BOOST_CAP,
)
PY
)"

# Check that docs mention Option A weights + context cap
WEIGHTS_REGEX="ai.*${AI_W}|AI.*${AI_W}"
RESEARCH_REGEX="research.*${RESEARCH_W}|Research.*${RESEARCH_W}"
ESOTERIC_REGEX="esoteric.*${ESOTERIC_W}|Esoteric.*${ESOTERIC_W}"
JARVIS_REGEX="jarvis.*${JARVIS_W}|Jarvis.*${JARVIS_W}"
CONTEXT_REGEX="context.*${CONTEXT_CAP}|±${CONTEXT_CAP}"

FOUND_WEIGHTS=0
FOUND_CONTEXT=0

for doc in "${DOCS[@]}"; do
  if [ ! -f "$doc" ]; then
    continue
  fi
  if rg -n -i "$WEIGHTS_REGEX" "$doc" >/dev/null 2>&1 && \
     rg -n -i "$RESEARCH_REGEX" "$doc" >/dev/null 2>&1 && \
     rg -n -i "$ESOTERIC_REGEX" "$doc" >/dev/null 2>&1 && \
     rg -n -i "$JARVIS_REGEX" "$doc" >/dev/null 2>&1; then
    FOUND_WEIGHTS=1
  fi
  if rg -n -i "$CONTEXT_REGEX" "$doc" >/dev/null 2>&1; then
    FOUND_CONTEXT=1
  fi

done

if [ "$FOUND_WEIGHTS" != "1" ]; then
  fail "Option A weights not documented with canonical values"
fi

if [ "$FOUND_CONTEXT" != "1" ]; then
  fail "Context modifier cap not documented with canonical value"
fi

# Check required additive terms in at least one doc
REQUIRED_TERMS=(
  "base_4"
  "context_modifier"
  "confluence_boost"
  "msrf_boost"
  "jason_sim_boost"
  "serp_boost"
  "ensemble_adjustment"
)

MISSING=()
for term in "${REQUIRED_TERMS[@]}"; do
  FOUND=0
  for doc in "${DOCS[@]}"; do
    if [ ! -f "$doc" ]; then
      continue
    fi
    if rg -n "$term" "$doc" >/dev/null 2>&1; then
      FOUND=1
      break
    fi
  done
  if [ "$FOUND" != "1" ]; then
    MISSING+=("$term")
  fi

done

if [ ${#MISSING[@]} -gt 0 ]; then
  echo "Missing additive term documentation: ${MISSING[*]}"
  fail "Docs contract missing additive terms"
fi

echo "Docs contract scan: PASS"
