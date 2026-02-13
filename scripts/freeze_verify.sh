#!/usr/bin/env bash
# v20.20 Freeze Verification Script
# Validates contract compliance after deployment
#
# Usage:
#   API_KEY=your_key ./scripts/freeze_verify.sh
#   API_KEY=your_key EXPECTED_SHA=abc1234 ./scripts/freeze_verify.sh
#   API_KEY=your_key SPORT=NBA ./scripts/freeze_verify.sh

set -euo pipefail

API_KEY="${API_KEY:-}"
BASE="${API_BASE:-https://web-production-7b2a.up.railway.app}"
EXPECTED_SHA="${EXPECTED_SHA:-}"
SPORT="${SPORT:-NCAAB}"

if [[ -z "$API_KEY" ]]; then
  echo "ERROR: API_KEY required"
  echo "Usage: API_KEY=your_key ./scripts/freeze_verify.sh"
  exit 1
fi

echo "================================================"
echo "v20.20 FREEZE VERIFICATION"
echo "================================================"
echo "Base URL: $BASE"
echo "Sport: $SPORT"
echo "Expected SHA: ${EXPECTED_SHA:-'(not set)'}"
echo ""

echo "=== 1. HEALTH CHECK ==="
health=$(curl -s "$BASE/health")
echo "$health" | jq '{status: .status, version: .version, build_sha: .build_sha}'
echo ""

echo "=== 2. CRITICAL INTEGRATIONS ==="
# Critical integrations per core/integration_contract.py: odds_api, playbook_api, balldontlie, railway_storage, database
# Policy: odds_api, playbook_api, balldontlie, railway_storage must be VALIDATED
#         database may be VALIDATED or CONFIGURED (DB connection tested at startup, not per-request)

integrations_json=$(curl -s "$BASE/live/debug/integrations" -H "X-API-Key: $API_KEY")

# Display statuses (integrations are nested under .integrations key)
echo "$integrations_json" | jq '{
  odds_api: .integrations.odds_api.status_category,
  playbook_api: .integrations.playbook_api.status_category,
  balldontlie: .integrations.balldontlie.status_category,
  railway_storage: .integrations.railway_storage.status_category,
  database: .integrations.database.status_category
}'

# Hard gate: verify all 5 critical integrations exist and have acceptable status
integrations_pass=$(echo "$integrations_json" | jq '
  .integrations as $i |
  (($i.odds_api.status_category // "MISSING") == "VALIDATED") and
  (($i.playbook_api.status_category // "MISSING") == "VALIDATED") and
  (($i.balldontlie.status_category // "MISSING") == "VALIDATED") and
  (($i.railway_storage.status_category // "MISSING") == "VALIDATED") and
  ((($i.database.status_category // "MISSING") == "VALIDATED") or (($i.database.status_category // "MISSING") == "CONFIGURED"))
')

if [[ "$integrations_pass" != "true" ]]; then
  echo ""
  echo "❌ CRITICAL INTEGRATIONS GATE FAILED"
  echo "Required: odds_api, playbook_api, balldontlie, railway_storage = VALIDATED"
  echo "Required: database = VALIDATED or CONFIGURED"
  echo ""
  echo "Failed integrations:"
  echo "$integrations_json" | jq -r '
    .integrations as $i |
    [
      (if ($i.odds_api.status_category // "MISSING") != "VALIDATED" then "  - odds_api: \($i.odds_api.status_category // "MISSING")" else empty end),
      (if ($i.playbook_api.status_category // "MISSING") != "VALIDATED" then "  - playbook_api: \($i.playbook_api.status_category // "MISSING")" else empty end),
      (if ($i.balldontlie.status_category // "MISSING") != "VALIDATED" then "  - balldontlie: \($i.balldontlie.status_category // "MISSING")" else empty end),
      (if ($i.railway_storage.status_category // "MISSING") != "VALIDATED" then "  - railway_storage: \($i.railway_storage.status_category // "MISSING")" else empty end),
      (if (($i.database.status_category // "MISSING") != "VALIDATED") and (($i.database.status_category // "MISSING") != "CONFIGURED") then "  - database: \($i.database.status_category // "MISSING")" else empty end)
    ] | .[]
  '
  exit 1
fi
echo "✓ All critical integrations OK"
echo ""

echo "=== 3. CONTRACT VERIFICATION ($SPORT) ==="
result=$(curl -s "$BASE/live/best-bets/$SPORT?debug=1" -H "X-API-Key: $API_KEY" | jq --arg expected_sha "$EXPECTED_SHA" '
  # Extract values
  .debug as $d |
  .build_sha as $build |
  ($d.returned_pick_count_games // 0) as $games |
  ($d.returned_pick_count_props // 0) as $props |
  ($d.min_returned_final_score_games) as $min_games |
  ($d.min_returned_final_score_props) as $min_props |
  ($d.invariant_violations_dropped // 0) as $violations |
  ($d.hidden_tier_filtered_total // 0) as $hidden |
  [.game_picks.picks[].tier, .props.picks[].tier] as $tiers |

  # Hard gates
  ($violations == 0) as $gate_invariants |
  ($tiers | all(. == "TITANIUM_SMASH" or . == "GOLD_STAR" or . == "EDGE_LEAN")) as $gate_tiers |
  (if $games > 0 then ($min_games != null and $min_games >= 7.0) else true end) as $gate_games_score |
  (if $props > 0 then ($min_props != null and $min_props >= 6.5) else true end) as $gate_props_score |
  ($games + $props >= 1) as $smoke_non_empty |
  (if $expected_sha == "" then true else ($build | startswith($expected_sha)) end) as $gate_build_sha |

  # Diagnostic signal
  (if $hidden == 0 then "clean_upstream" else "filter_active_investigate" end) as $hidden_signal |

  {
    build_sha: $build,
    returned_games: $games,
    returned_props: $props,
    min_score_games: $min_games,
    min_score_props: $min_props,
    invariant_violations: $violations,
    hidden_tier_filtered: $hidden,
    tiers_returned: ($tiers | unique),

    gates: {
      invariants_ok: $gate_invariants,
      tiers_valid: $gate_tiers,
      games_score_ok: $gate_games_score,
      props_score_ok: $gate_props_score,
      smoke_valid: $smoke_non_empty,
      build_sha_ok: $gate_build_sha
    },

    hidden_tier_signal: $hidden_signal,

    PASS: ($gate_invariants and $gate_tiers and $gate_games_score and $gate_props_score and $smoke_non_empty and $gate_build_sha)
  }
')

echo "$result" | jq .
echo ""

# Extract PASS value and exit accordingly
pass=$(echo "$result" | jq -r '.PASS')

echo "================================================"
if [[ "$pass" == "true" ]]; then
  echo "✅ FREEZE VERIFICATION PASSED"
  echo "================================================"
  exit 0
else
  echo "❌ FREEZE VERIFICATION FAILED"
  echo "================================================"
  echo ""
  echo "Failed gates:"
  echo "$result" | jq '.gates | to_entries[] | select(.value == false) | "  - \(.key)"' -r
  exit 1
fi
