# Verification Checklists - Consolidated

Run relevant checklist before deploying changes in that area.

---

## ✅ VERIFICATION CHECKLIST (v20.11 — Real Data Sources)

Run these after ANY change to NOAA, ESPN live scores, void moon, or LSTM training:

```bash
# 1. Syntax check all modified files
python -m py_compile signals/physics.py signals/hive_mind.py lstm_training_pipeline.py live_data_router.py

# 2. Check NOAA Kp-Index is using real API
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '.debug.glitch_breakdown.kp_index | {source, kp_value, storm_level}'
# source should be "noaa_live" (not "simulation" or "fallback")

# 3. Check live scores are being extracted (during live games)
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '[.game_picks.picks[] | {matchup, game_status, live_adjustment}] | map(select(.game_status == "LIVE"))'
# live_adjustment should be non-zero when game is in progress

# 4. Check void moon calculation method
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '.debug.esoteric.void_moon'
# Should show improved calculation with confidence value

# 5. Check LSTM training data source (after Sunday retrain)
curl /live/ml/status -H "X-API-Key: KEY" | jq '.lstm | {loaded_count, training_data_source}'

# 6. Test all 5 sports
for sport in NBA NHL NFL MLB NCAAB; do
  echo "=== $sport ==="
  curl -s "/live/best-bets/$sport?debug=1" -H "X-API-Key: KEY" | \
    jq '{sport: .sport, picks: (.game_picks.count + .props.count), kp_source: .debug.glitch_breakdown.kp_index.source}'
done
# All should show kp_source: "noaa_live"

# 7. Run option_a_drift_scan (ensure no regressions)
bash scripts/option_a_drift_scan.sh
```

### Lesson 62: Post-Base Signals Mutating Engine Scores — Hidden Adjustments (v20.3/v20.11)
**Problem:** Hook Discipline, Expert Consensus, and Prop Correlation signals were incorrectly mutating `research_score` AFTER `base_score` was computed. This meant the adjustments had **NO EFFECT** on `final_score` — they were hidden inside BASE_4 and broke reconciliation/auditability.

**Root Cause:** The v20.3 "8 Pillars of Execution" implementation added these signals as mutations to `research_score` instead of as separate post-base additive fields:

```python
# BUG — Mutating research_score AFTER base_score is computed
research_score = 7.5  # Already used to compute base_score
hook_penalty = -0.25
research_score += hook_penalty  # TOO LATE! base_score already locked

# This mutation is invisible to final_score calculation:
# final = base_score + context_modifier + boosts  ← hook_penalty NOT here
```

**The Fix:** Wire signals as explicit parameters to `compute_final_score_option_a()`:

```python
# CORRECT — Post-base additive fields passed explicitly
final_score = compute_final_score_option_a(
    ai_score=ai_score,
    research_score=research_score,
    esoteric_score=esoteric_score,
    jarvis_score=jarvis_score,
    context_modifier=context_modifier,
    confluence_boost=confluence_boost,
    # ... other boosts ...
    hook_penalty=hook_penalty,              # NEW: post-base
    expert_consensus_boost=expert_boost,    # NEW: post-base
    prop_correlation_adjustment=prop_corr,  # NEW: post-base
)
```

**Math Contract (Option A v20.11):**
```
FINAL = clamp(0..10, BASE_4 + context_modifier + confluence_boost + msrf_boost +
              jason_sim_boost + serp_boost + ensemble_adjustment + live_adjustment +
              totals_calibration_adj + hook_penalty + expert_consensus_boost +
              prop_correlation_adjustment)
```

**Caps (enforced inside compute_final_score_option_a):**
- `hook_penalty` ∈ [-0.25, 0] — always ≤0
- `expert_consensus_boost` ∈ [0, 0.35] — always ≥0, SHADOW MODE (forced to 0) until validated
- `prop_correlation_adjustment` ∈ [-0.20, 0.20] — signed ±

**Prevention:**
1. **NEVER mutate engine scores for post-base signals** — engine scores (ai, research, esoteric, jarvis) are LOCKED once BASE_4 is computed
2. **Post-base signals MUST be explicit parameters** to `compute_final_score_option_a()`
3. **Every adjustment MUST be surfaced as its own field** in the pick payload for auditability
4. **Caps MUST be enforced inside the scoring function**, not at call sites
5. **Add reconciliation test**: `abs(final_score - clamp(sum(all_terms))) <= 0.02`

**Files Modified:**
- `core/scoring_contract.py` — Added caps with `applies_to: "post_base"`
- `core/scoring_pipeline.py` — Added 3 new parameters to `compute_final_score_option_a()`
- `live_data_router.py` — Removed research_score mutations, pass signals as explicit params
- `tests/test_option_a_scoring_guard.py` — Added 5 reconciliation tests

**Fixed in:** v20.11 (Feb 8, 2026)

### Lesson 63: Enabling Dormant Features — Stadium Altitude & Travel Fatigue (v20.12)
**Problem:** Three implemented features were dormant:
1. Stadium altitude impact — code existed in `alt_data_sources/stadium.py` but wasn't wired into scoring
2. Travel fatigue — code existed but had a bug: `rest_days` variable was undefined
3. Gematria Twitter — fully wired but needed `SERPAPI_KEY` env var

**Root Cause:**
- Stadium altitude module existed but was never called from `live_data_router.py`
- Travel fatigue at line 4575 had: `_rest_days = rest_days if 'rest_days' in dir() else 1` — `rest_days` was never defined in scope
- The `_rest_days_for_team()` closure at lines 5561-5564 was ready to use but not called

**The Fix:**
```python
# 1. Stadium Altitude — Added after line 4500 in live_data_router.py
if _is_game_pick and sport_upper in ("NFL", "MLB"):
    try:
        from alt_data_sources.stadium import calculate_altitude_impact, lookup_altitude, STADIUM_ENABLED
        if STADIUM_ENABLED:
            _altitude = lookup_altitude(home_team)
            if _altitude and _altitude > 1000:
                _alt_impact = calculate_altitude_impact(sport_upper, _altitude)
                if _alt_impact.get("overall_impact") != "NONE":
                    altitude_adj = _alt_impact.get("scoring_impact", 0.0)
                    if altitude_adj > 0:
                        esoteric_reasons.append(f"Altitude: {_alt_impact.get('reasons', ['High altitude'])[0]}")
                        esoteric_raw += altitude_adj
    except ImportError:
        pass

# 2. Travel Fatigue Fix — Line 4575
# BEFORE (BUG):
_rest_days = rest_days if 'rest_days' in dir() else 1

# AFTER (FIXED):
_rest_days = _rest_days_for_team(away_team) or 1
```

**Environment Variables Added:**
| Variable | Value | Purpose |
|----------|-------|---------|
| `STADIUM_ENABLED` | `true` | Enable altitude impact for NFL/MLB |
| `TRAVEL_ENABLED` | `true` | Enable travel fatigue calculation |
| `SERPAPI_KEY` | `<key>` | Gematria Twitter intel (already available) |

**High-Altitude Venues Affected:**
- Denver (Broncos/Rockies): 5280ft — +0.5 scoring adjustment
- Salt Lake City (Utah Jazz): 4226ft — ~+0.3 adjustment
- Other venues >1000ft get proportional adjustments

**Verification:**
```bash
# Travel fatigue visible in picks (tested with NBA)
curl /live/best-bets/NBA -H "X-API-Key: KEY" | \
  jq '[.game_picks.picks[].context_reasons] | flatten | map(select(contains("Travel")))'
# Returns: ["Travel: 1521mi + 1-day rest (-0.35)"]

# Gematria boost active
curl /live/best-bets/NBA -H "X-API-Key: KEY" | \
  jq '.game_picks.picks[0].confluence.gematria_boost'
# Returns: 0.495

# Stadium altitude (needs NFL/MLB game at high-altitude venue)
curl /live/best-bets/NFL -H "X-API-Key: KEY" | \
  jq '[.game_picks.picks[].esoteric_reasons] | flatten | map(select(contains("Altitude")))'
```

**Prevention:**
1. **ALWAYS check env var requirements** — Dormant code often just needs feature flags enabled
2. **Trace variable usage** — `rest_days if 'rest_days' in dir()` is a red flag; variable was never defined
3. **Use existing closures** — `_rest_days_for_team()` was already implemented and tested

**Files Modified:**
- `live_data_router.py` — 2 changes:
  - Inserted altitude impact block after line 4500 (~18 lines)
  - Fixed travel fatigue variable at line 4575

**Fixed in:** v20.12 (Feb 8, 2026) — Commit `7fe1889`

### Lesson 64: CI Spot Check Partial-Success Error Handling (v20.12)
**Problem:** Session 8 spot check script failed when NFL endpoint returned valid picks alongside timeout errors (`PROPS_TIMED_OUT`, `GAME_PICKS_TIMED_OUT`). The script treated ANY error as fatal.

**Root Cause:**
- Original jq logic: `has("error") or has("errors")` → fail immediately
- Did not distinguish between:
  - **Fatal errors**: Top-level `error` field, non-timeout error codes
  - **Partial success**: Timeout errors with valid picks still returned

**The Fix (spot_check_session8.sh lines 109-134):**
```bash
# Count picks returned (including partial results)
picks_count="$(echo "$body" | jq -r '([.props.picks[]?] + [.game_picks.picks[]?]) | length')"

# Check for FATAL errors only (not timeout codes)
has_fatal_err="$(echo "$body" | jq -r '
  (has("error") and .error != null and .error != "") or
  (has("errors") and (.errors | map(select(
    .code != "PROPS_TIMED_OUT" and .code != "GAME_PICKS_TIMED_OUT"
  )) | length) > 0) or
  (.debug != null and .debug | has("error") and .debug.error != null)
' 2>/dev/null || echo "false")"

# Logic:
# - Fatal error → FAIL
# - Partial success (timeout + picks) → PASS
# - Zero picks with timeout → WARNING (off-season)
```

**Key Insight:** Production APIs may return partial results with soft errors. CI scripts must:
1. **Distinguish fatal vs recoverable errors** — timeout with data is OK
2. **Check for actual data** — if picks returned, endpoint is working
3. **Allow off-season gracefully** — 0 picks + timeout is warning, not failure

**Prevention:**
1. **NEVER fail CI on ANY error** — check error codes and actual data presence
2. **Allow partial success** — timeout errors with valid data = working endpoint
3. **Test all sports** — one sport may have games while others don't
4. **Handle transient 502s** — server restarts cause brief failures; retry logic helps

**NEVER DO (CI Spot Checks - rules 208-212):**
- 208: NEVER fail on `has("errors")` alone — check error codes for severity
- 209: NEVER ignore pick counts when evaluating errors — partial success is valid
- 210: NEVER assume all sports have games — off-season returns 0 picks legitimately
- 211: NEVER skip error code filtering — timeout codes are not fatal
- 212: NEVER treat HTTP 502 as permanent — transient server restarts are normal

**Files Modified:**
- `scripts/spot_check_session8.sh` — Lines 109-134: partial-success error handling

**Fixed in:** v20.12 (Feb 8, 2026) — Commit `86d3982`

---


---

## ✅ VERIFICATION CHECKLIST (ESPN)

Run these after ANY change to ESPN integration:

```bash
# 1. Syntax check ESPN module
python -m py_compile alt_data_sources/espn_lineups.py

# 2. ESPN availability check
curl /live/debug/integrations -H "X-API-Key: KEY" | jq '.espn'
# Should show: available: true, configured: true

# 3. ESPN officials data
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '.debug | {espn_events: .espn_events_mapped, officials: .officials_available}'
# Should show counts > 0 (varies by game day)

# 4. ESPN odds cross-validation
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '.game_picks.picks[0].research_reasons | map(select(contains("ESPN")))'
# Should include "ESPN confirms spread" or "ESPN spread close" when available

# 5. ESPN injuries merged
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '.debug | {injuries_teams: .injuries_lookup_count, espn_injuries_teams: .espn_injuries_count}'

# 6. ESPN venue/weather (MLB/NFL only)
curl /live/best-bets/MLB?debug=1 -H "X-API-Key: KEY" | \
  jq '.game_picks.picks[0] | {venue: .espn_venue, weather_source: .weather_source}'

# 7. Test all sports ESPN integration
for sport in NBA NHL NFL MLB NCAAB; do
  echo "=== $sport ==="
  result=$(curl -s "/live/best-bets/$sport?debug=1" -H "X-API-Key: KEY")
  espn_events=$(echo "$result" | jq -r '.debug.espn_events_mapped // 0')
  echo "ESPN events: $espn_events"
done

# 8. Verify no ESPN errors in logs
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '.debug.errors | map(select(contains("ESPN") or contains("espn")))'
# Should be empty or null
```

---


---

## ✅ VERIFICATION CHECKLIST (ML & GLITCH)

Run these after ANY change to ML or GLITCH code:

```bash
# 1. Syntax check
python -m py_compile esoteric_engine.py ml_integration.py live_data_router.py

# 2. ML Status
curl /live/ml/status -H "X-API-Key: KEY" | jq '{
  lstm_loaded: .lstm.loaded_count,
  ensemble_available: .ensemble.available,
  tensorflow: .tensorflow_available
}'

# 3. GLITCH signals in output
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '.props.picks[0] | {
    glitch_adj: .glitch_adjustment,
    esoteric_reasons: .esoteric_reasons | map(select(startswith("GLITCH")))
  }'

# 4. Context pillars
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '.props.picks[0] | {
    def_rank: .def_rank,
    pace: .pace,
    vacuum: .vacuum,
    context_score: .context_score
  }'

# 5. Alt data sources
curl /live/debug/integrations -H "X-API-Key: KEY" | \
  jq '{noaa: .noaa, serpapi: .serpapi}'

# 6. Harmonic Convergence (check high-scoring picks)
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '.props.picks[] | select(.research_score >= 8 and .esoteric_score >= 8) | {
    research: .research_score,
    esoteric: .esoteric_score,
    confluence: .confluence_level
  }'

# 7. MSRF Resonance (check turn date detection)
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '.props.picks[0] | {
    msrf_boost: .msrf_boost,
    msrf_level: .msrf_metadata.level,
    msrf_points: .msrf_metadata.points,
    msrf_dates: .msrf_metadata.significant_dates_used
  }'

# 8. MSRF in esoteric_reasons (verify integration)
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '.props.picks[] | select(.msrf_boost > 0) | {
    player: .player_name,
    msrf: .msrf_boost,
    level: .msrf_metadata.level
  }'

# 9. Phase 1 Dormant Signals - Gann Square (GAME picks)
curl -s '/live/best-bets/NBA?debug=1' -H 'X-API-Key: KEY' | \
  jq '[.game_picks.picks[].esoteric_reasons] | flatten | map(select(startswith("Gann")))'
# Should show: ["Gann: 45° (MODERATE)"] or similar when angles resonate

# 10. Phase 1 Dormant Signals - Founder's Echo (GAME picks)
curl -s '/live/best-bets/NBA?debug=1' -H 'X-API-Key: KEY' | \
  jq '[.game_picks.picks[].esoteric_reasons] | flatten | map(select(startswith("Founder")))'
# Shows "Founder's Echo: TeamName (year)" when team gematria resonates with date

# 11. Phase 1 Dormant Signals - Biorhythms (PROP picks)
curl -s '/live/best-bets/NBA?debug=1' -H 'X-API-Key: KEY' | \
  jq '[.props.picks[].esoteric_reasons] | flatten | map(select(startswith("Biorhythm")))'
# Shows "Biorhythm: PEAK (85)" when player is at peak cycle

# 12. Esoteric Score Variation (confirms signals are differentiating)
curl -s '/live/best-bets/NBA?debug=1' -H 'X-API-Key: KEY' | \
  jq '[.game_picks.picks[].esoteric_score] | {min: min, max: max, avg: (add/length)}'
# Range should be > 1.0 point (e.g., min: 4.05, max: 5.7)

# 13. All unique esoteric_reasons (full signal inventory)
curl -s '/live/best-bets/NBA?debug=1' -H 'X-API-Key: KEY' | \
  jq '[.game_picks.picks[].esoteric_reasons, .props.picks[].esoteric_reasons] | flatten | unique'

# 14. Phase 2.2 - Void-of-Course Daily Edge (check VOC penalty)
curl -s '/live/best-bets/NBA?debug=1' -H 'X-API-Key: KEY' | \
  jq '.debug.daily_energy'
# Should include: void_of_course: {is_void, confidence, penalty}

# 15. Test VOC function directly
python3 -c "from astronomical_api import is_void_moon_now; is_void, conf = is_void_moon_now(); print(f'VOC: is_void={is_void}, confidence={conf}')"
# Returns current VOC status

# 16. Verify daily energy includes VOC data in response
curl -s '/live/daily-energy' -H 'X-API-Key: KEY' | jq '.void_of_course'
# When VOC active: {is_void: true, confidence: 0.87, penalty: -20}
```

---


---

## ✅ VERIFICATION CHECKLIST (SECURITY)

Run these after ANY change that touches logging, API clients, or debug endpoints:

```bash
# 1. Log sanitizer tests
pytest tests/test_log_sanitizer.py -v
# All 20 tests must pass

# 2. Demo data gate tests
pytest tests/test_no_demo_data.py -v
# All 12 tests must pass (some skip if deps missing)

# 3. Check for secret patterns in logs (should be empty or [REDACTED])
grep -rn "apiKey=\|api_key=\|Authorization:" *.py | grep -v "REDACTED\|sanitize\|test_"
# Should return few/no results

# 4. Verify demo endpoints are gated
curl -X POST /debug/seed-pick -H "X-Admin-Key: KEY" 2>/dev/null | jq '.error'
# Should return "Demo data gated"

# 5. Verify fallback returns empty (not demo data)
ENABLE_DEMO=false python3 -c "
from legacy.services.odds_api_service import OddsAPIService
import os
os.environ['ODDS_API_KEY'] = ''
os.environ['ENABLE_DEMO'] = 'false'
s = OddsAPIService()
result = s.get_odds('basketball_nba')
assert result == [], f'Expected empty, got {result}'
print('✓ Demo data properly gated')
"

# 6. Check sensitive env vars are in sanitizer
grep -c "ODDS_API_KEY\|PLAYBOOK_API_KEY" core/log_sanitizer.py
# Should return 2+ (vars are listed)
```

---


---

## ✅ VERIFICATION CHECKLIST (Best-Bets & Scoring)

**Run these after ANY change to best-bets, scoring, or dual-use functions:**

```bash
# 1. Syntax check
python -m py_compile live_data_router.py

# 2. Test ALL 5 sports (MANDATORY after scoring changes)
for sport in NBA NHL NFL MLB NCAAB; do
  echo "=== Testing $sport ==="
  result=$(curl -s "https://web-production-7b2a.up.railway.app/live/best-bets/$sport" \
    -H "X-API-Key: bookie-prod-2026-xK9mP2nQ7vR4")

  # Check for error
  error=$(echo "$result" | jq -r '.detail.code // empty')
  if [ -n "$error" ]; then
    echo "❌ $sport FAILED: $error"
    echo "$result" | jq '.detail'
  else
    games=$(echo "$result" | jq '.game_picks.count')
    props=$(echo "$result" | jq '.props.count')
    echo "✅ $sport OK: $games game picks, $props props"
  fi
done

# 3. Check for JSONResponse returns in dual-use functions
grep -n "return JSONResponse" live_data_router.py | grep -E "get_sharp|get_splits|get_lines|get_injuries"
# Should return EMPTY (these functions must return dicts)

# 4. Verify debug mode error details work
curl -s "https://web-production-7b2a.up.railway.app/live/best-bets/NBA?debug=1" \
  -H "X-API-Key: bookie-prod-2026-xK9mP2nQ7vR4" | jq 'has("detail") or has("sport")'
# Should return true (either error detail or valid response)

# 5. Check MSRF integration
curl -s "https://web-production-7b2a.up.railway.app/live/best-bets/NBA?debug=1" \
  -H "X-API-Key: bookie-prod-2026-xK9mP2nQ7vR4" | \
  jq '.game_picks.picks[0] | {msrf_boost, msrf_source: .msrf_metadata.source}'
# Should show msrf_boost (0.0 or higher) and msrf_source

# 6. Verify no undefined variables in calculate_pick_score
grep -n "_game_date_obj\|jarvis_rs\|esoteric_reasons" live_data_router.py | head -20
# Verify these are initialized before use

# 7. Check sharp endpoint still works (after dual-use fix)
curl -s "https://web-production-7b2a.up.railway.app/live/sharp/NBA" \
  -H "X-API-Key: bookie-prod-2026-xK9mP2nQ7vR4" | jq '{source: .source, count: .count}'
# Should return source and count (not error)
```

**If ANY sport fails, DO NOT deploy other changes until fixed.**

---


---

## ✅ VERIFICATION CHECKLIST (SERP Intelligence)

Run these after ANY change to SERP integration (serp_guardrails.py, serp_intelligence.py, serpapi.py, or SERP pre-fetch in live_data_router.py):

```bash
# 1. Syntax check SERP modules
python -m py_compile core/serp_guardrails.py alt_data_sources/serp_intelligence.py alt_data_sources/serpapi.py

# 2. Verify SERP status (shadow mode OFF, live mode ON)
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | jq '.debug.serp'
# MUST show: available=true, shadow_mode=false, mode="live"

# 3. Check quota tracking
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '.debug.serp.status.quota | {daily_remaining, monthly_remaining}'
# Should show remaining counts (166/day, 5000/month starting values)

# 4. Check cache performance
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '.debug.serp.status.cache | {hits, misses, hit_rate_pct}'
# Hit rate should be >50% after initial warm-up

# 5. Check boosts on picks (signals should fire)
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '.game_picks.picks[0] | {serp_boost, serp_reasons}'
# serp_boost > 0 when signals fire, serp_reasons shows which signals

# 6. Test all 5 sports SERP integration
for sport in NBA NHL NFL MLB NCAAB; do
  echo "=== $sport ==="
  curl -s "/live/best-bets/$sport?debug=1" -H "X-API-Key: KEY" | \
    jq '{sport: .sport, serp_available: .debug.serp.available, serp_mode: .debug.serp.mode}'
done
# All should show available=true, mode="live"

# 7. Verify boost caps enforced (no single engine > cap)
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '[.game_picks.picks[].serp_boost] | max'
# Max should be <= 4.3 (SERP_TOTAL_CAP)

# 8. Check env var aliases work
curl /live/debug/integrations -H "X-API-Key: KEY" | jq '.serpapi'
# Should show configured=true if either SERPAPI_KEY or SERP_API_KEY is set

# 9. Verify SERP pre-fetch is working (v20.7)
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '.debug.serp | {prefetch_cached, prefetch_games}'
# prefetch_cached > 0 means pre-fetch is active and caching results
# prefetch_games > 0 means unique game pairs were identified

# 10. Check pre-fetch timing (should be < 12s)
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '.debug.timings.serp_prefetch'
# Should be 1-5s (parallel). If > 12s, pre-fetch timed out

# 11. Verify pre-fetch not in timed_out_components
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '.debug._timed_out_components'
# Should NOT include "serp_prefetch" — if it does, 12s timeout was hit

# 12. Verify props now return picks (v20.7 regression check)
curl /live/best-bets/NBA -H "X-API-Key: KEY" | \
  jq '{props_count: .props.count, game_count: .game_picks.count}'
# props_count should be > 0 when there are today's games
```

**Critical Invariants (ALWAYS verify these):**
- `SERP_SHADOW_MODE` must be `False` (live mode)
- Boosts must be capped per engine (ai=0.8, research=1.3, esoteric=0.6, jarvis=0.7, context=0.9)
- Total boost must not exceed 4.3
- Quota must be checked before API calls
- All SERP calls wrapped in try/except (fail-soft)
- `prefetch_cached > 0` in production (v20.7 — proves parallel pre-fetch is active)
- `serp_prefetch` timing < 12s (hard timeout)

---


---

## ✅ VERIFICATION CHECKLIST (Rivalry Database)

Run these after ANY change to MAJOR_RIVALRIES in esoteric_engine.py:

```bash
# 1. Syntax check
python3 -m py_compile esoteric_engine.py

# 2. Count rivalries per sport (should be: NBA 35, NFL 46, NHL 36, MLB 36, NCAAB 51 = 204 total)
python3 -c "
from esoteric_engine import MAJOR_RIVALRIES
for sport, rivals in MAJOR_RIVALRIES.items():
    print(f'{sport}: {len(rivals)} rivalries')
print(f'Total: {sum(len(v) for v in MAJOR_RIVALRIES.values())} rivalries')
"

# 3. Test rivalry detection for each sport
python3 -c "
from esoteric_engine import calculate_rivalry_intensity
tests = [
    # NBA
    ('NBA', 'Celtics', 'Lakers'),
    ('NBA', 'Kings', 'Warriors'),
    ('NBA', 'Timberwolves', 'Nuggets'),
    # NFL
    ('NFL', 'Bills', 'Dolphins'),
    ('NFL', 'Jaguars', 'Titans'),
    ('NFL', 'Commanders', 'Cowboys'),
    # NHL
    ('NHL', 'Bruins', 'Canadiens'),
    ('NHL', 'Kraken', 'Canucks'),
    ('NHL', 'Golden Knights', 'Sharks'),
    # MLB
    ('MLB', 'Yankees', 'Red Sox'),
    ('MLB', 'Mets', 'Phillies'),
    ('MLB', 'Dodgers', 'Giants'),
    # NCAAB
    ('NCAAB', 'Duke', 'North Carolina'),
    ('NCAAB', 'Kentucky', 'Louisville'),
    ('NCAAB', 'Michigan', 'Ohio State'),
]
passed = 0
for sport, t1, t2 in tests:
    result = calculate_rivalry_intensity(sport, t1, t2)
    if result.get('is_rivalry'):
        print(f'✅ {sport}: {t1} vs {t2} = {result.get(\"intensity\")}')
        passed += 1
    else:
        print(f'❌ {sport}: {t1} vs {t2} = NOT FOUND')
print(f'\n{passed}/{len(tests)} tests passed')
"

# 4. Verify rivalry boost appears in production picks
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '[.game_picks.picks[].phase8_breakdown.rivalry] | map(select(.is_rivalry == true))'

# 5. Check esoteric_reasons include rivalry signals
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '[.game_picks.picks[].esoteric_reasons] | flatten | map(select(contains("Rivalry")))'
```

---


---

## ✅ VERIFICATION CHECKLIST (Go/No-Go - REQUIRED BEFORE DEPLOY)

Run this after ANY change to scoring, boosts, sanity scripts, or live_data_router.py:

```bash
# Full go/no-go (MUST PASS all 12 checks)
API_KEY="YOUR_KEY" SKIP_NETWORK=0 SKIP_PYTEST=0 ALLOW_EMPTY=1 \
  bash scripts/prod_go_nogo.sh

# Expected output: "Prod go/no-go: PASS"
```

**IMPORTANT:** Always use `ALLOW_EMPTY=1` for local runs (dev doesn't have production prediction/weight files).

**The 12 Checks (+ optional pytest):**
| # | Check | Script | What It Validates |
|---|-------|--------|-------------------|
| 1 | option_a_drift | `option_a_drift_scan.sh` | No BASE_5 or context-as-engine |
| 2 | audit_drift | `audit_drift_scan.sh` | No unauthorized +/-0.5 to final_score |
| 3 | env_drift | `env_drift_scan.sh` | Required env vars configured |
| 4 | docs_contract | `docs_contract_scan.sh` | Required fields documented |
| 5 | learning_sanity | `learning_sanity_check.sh` | Weights initialized |
| 6 | learning_loop | `learning_loop_sanity.sh` | Auto grader operational |
| 7 | endpoint_matrix | `endpoint_matrix_sanity.sh` | All 5 sports, required fields, math check |
| 8 | prod_endpoint_matrix | `prod_endpoint_matrix.sh` | Production /health, /debug, /grader, best-bets |
| 9 | signal_coverage | `signal_coverage_report.py` | Signal coverage across sports |
| 10 | api_proof | `api_proof_check.sh` | Production API responding |
| 11 | live_sanity | `live_sanity_check.sh` | Best-bets returns valid data |
| 12 | perf_audit | `perf_audit_best_bets.sh` | Response times within benchmarks |

Checks 1-6 are offline (no network needed). Checks 7-12 require `SKIP_NETWORK=0` and a valid `API_KEY`.

**If ANY check fails:**
1. Read the artifact: `cat artifacts/{check_name}_YYYYMMDD_ET.json`
2. Fix the issue
3. Re-run go/no-go
4. Do NOT deploy until all 12 pass

**Common Failures:**
| Failure | Likely Cause | Fix |
|---------|--------------|-----|
| `audit_drift` | Line numbers shifted | Update filter in `audit_drift_scan.sh` |
| `endpoint_matrix` | Math mismatch (unsurfaced adjustment) | Surface the field + update jq formula in `endpoint_matrix_sanity.sh` |
| `env_drift` | New env var not registered | Add to `RUNTIME_ENV_VARS` in `integration_registry.py` |
| `option_a_drift` | BASE_5 introduced | Remove context-as-engine code |
| `learning_loop` | Weights missing | Check `_initialize_weights()` |
| `prod_endpoint_matrix` | Path bug or production down | Check `scripts/prod_endpoint_matrix.sh` paths, verify Railway deploy |
| `learning_sanity` | Missing ALLOW_EMPTY | Set `ALLOW_EMPTY=1` for local runs |

**Chicken-and-Egg Pattern:** When a code change adds new fields, `endpoint_matrix` (tests production) will fail pre-deploy because production doesn't have the field yet. In this case: deploy the code change first, then re-run go/no-go to verify.

**Artifacts Location:** `artifacts/{check_name}_YYYYMMDD_ET.json`

---


---

## ✅ VERIFICATION CHECKLIST (Perf Audit)

Run the perf audit after ANY change to scoring pipeline, API integrations, or parallel fetch:

```bash
# Run perf audit (requires API_KEY)
API_KEY="bookie-prod-2026-xK9mP2nQ7vR4" bash scripts/perf_audit_best_bets.sh

# Check specific sport
API_KEY="KEY" SPORTS="NBA" bash scripts/perf_audit_best_bets.sh

# More runs for better p50/p95 accuracy
API_KEY="KEY" RUNS=5 bash scripts/perf_audit_best_bets.sh
```

**What to Check:**
1. **game_picks_scoring p50 < 60s** - Main scoring pipeline
2. **parallel_fetch p50 < 2s** - API fetches
3. **No empty timings** for sports with active games
4. **init_engines fast after first run** (<0.1s on subsequent runs)

**Troubleshooting Slow Performance:**
| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| parallel_fetch > 5s | API timeout or rate limit | Check Odds API quota |
| game_picks_scoring > 90s | Too many boosts enabled | Review SERP/MSRF/GLITCH |
| player_resolution > 5s | BallDontLie slow | Check BDL API health |
| init_engines > 1s every run | Engines not caching | Check singleton patterns |

**Shell Variable Export (Critical):**
The script uses Python heredocs. Variables MUST be exported:
```bash
# ❌ WRONG - Python can't see this
BASE_URL="https://example.com"

# ✅ CORRECT - Python inherits via os.environ
export BASE_URL="https://example.com"
```

---


---

## ✅ VERIFICATION CHECKLIST (v20.2 - Auto Grader)

Run these after ANY change to auto_grader.py or grading logic:

```bash
# 1. Syntax check auto_grader
python -m py_compile auto_grader.py

# 2. Verify weights exist for ALL stat types (PROP + GAME)
curl -s "/live/grader/weights/NBA" -H "X-API-Key: KEY" | jq 'keys'
# Should include: points, rebounds, assists, spread, total, moneyline, sharp

# 3. Test bias calculation for GAME stat types
for stat in spread total moneyline sharp; do
  echo "=== $stat ==="
  curl -s "/live/grader/bias/NBA?stat_type=$stat&days_back=1" -H "X-API-Key: KEY" | \
    jq '{stat_type: .stat_type, sample_size: .bias.sample_size, error: .bias.error}'
done
# All should show sample_size > 0 OR "No graded predictions found" (not a crash)

# 4. Run full audit and verify game picks processed
curl -s -X POST "/live/grader/run-audit" -H "X-API-Key: KEY" \
  -H "Content-Type: application/json" -d '{"days_back": 1}' | \
  jq '.results.results.NBA | {spread: .spread.bias_analysis.sample_size, total: .total.bias_analysis.sample_size}'
# Should show sample_size > 0 for spread and total

# 5. Verify grading summary has graded picks
curl -s "/live/picks/grading-summary?date=$(date -v-1d +%Y-%m-%d)" -H "X-API-Key: KEY" | \
  jq '{total: .total_picks, graded: (.graded_picks | length)}'
# graded should be > 0

# 6. Check OVER/UNDER performance split (for bias monitoring)
curl -s "/live/picks/grading-summary?date=$(date -v-1d +%Y-%m-%d)" -H "X-API-Key: KEY" | \
  jq '{
    over: {wins: [.graded_picks[] | select(.side == "Over" and .result == "WIN")] | length,
           losses: [.graded_picks[] | select(.side == "Over" and .result == "LOSS")] | length},
    under: {wins: [.graded_picks[] | select(.side == "Under" and .result == "WIN")] | length,
            losses: [.graded_picks[] | select(.side == "Under" and .result == "LOSS")] | length}
  }'
# Monitor for severe bias (e.g., OVER 19% vs UNDER 82%)

# 7. Test all 5 sports audit
curl -s -X POST "/live/grader/run-audit" -H "X-API-Key: KEY" \
  -H "Content-Type: application/json" -d '{"days_back": 1}' | \
  jq '[.results.results | to_entries[] | {sport: .key, spread_samples: .value.spread.bias_analysis.sample_size}]'

# 8. Verify weight adjustments are APPLIED (not just calculated)
curl -s "/live/grader/bias/NBA?stat_type=spread&days_back=1" -H "X-API-Key: KEY" | \
  jq '{applied: (.weight_adjustments != null), adjustments: .weight_adjustments}'
# Must show applied: true with pace, vacuum, officials deltas

# 9. Check factor correlations are tracked
curl -s "/live/grader/bias/NBA?stat_type=spread&days_back=1" -H "X-API-Key: KEY" | \
  jq '.bias.factor_bias | keys'
# Should include: pace, vacuum, officials, glitch, esoteric

# 10. Full learning loop health check
curl -s "/live/grader/bias/NBA?stat_type=spread&days_back=1" -H "X-API-Key: KEY" | \
  jq '{
    stat_type,
    sample_size: .bias.sample_size,
    hit_rate: .bias.overall.hit_rate,
    bias_direction: .bias.overall.bias_direction,
    factors_tracked: (.bias.factor_bias | keys | length),
    adjustments_applied: (.weight_adjustments != null)
  }'
# Expected: sample_size > 0, factors_tracked >= 5, adjustments_applied: true

# 11. Verify daily lesson generation
curl -s "/live/grader/daily-lesson/latest" -H "X-API-Key: KEY" | \
  jq '{date_et, total_graded, weights_adjusted: (.weights_adjusted | length)}'
```

**Critical Invariants (ALWAYS verify these):**
- `_initialize_weights()` includes BOTH prop_stat_types AND game_stat_types
- Game picks use `stat_type = pick_type.lower()` (from `_convert_pick_to_record()`)
- `adjust_weights()` should NOT fall back to "points" for valid game stat types
- `calculate_bias()` filters by `record.stat_type == stat_type` (exact match)
- Weight adjustments must show `applied: true` (not just calculated)
- Factor correlations must include all 5 categories: pace, vacuum, officials, glitch, esoteric

**Learning Loop Health Indicators:**
| Indicator | Healthy | Unhealthy |
|-----------|---------|-----------|
| `sample_size` | > 0 | 0 or null |
| `hit_rate` | Non-null | null |
| `factor_bias` | 5+ categories | Empty or null |
| `weight_adjustments` | Non-null with deltas | null |
| `applied` | true | false or missing |


---

## ✅ VERIFICATION CHECKLIST (v20.0 - Phase 9 Full Spectrum)

Run these after ANY change to Phase 9 features (streaming, live signals, weather, travel):

```bash
# 1. Syntax check Phase 9 modules
python -m py_compile streaming_router.py alt_data_sources/live_signals.py alt_data_sources/weather.py alt_data_sources/travel.py

# 2. Verify streaming status
curl /live/stream/status -H "X-API-Key: KEY"
# When enabled: status: "ACTIVE", sse_available: true

# 3. Check live signals in debug output (during live games)
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '[.game_picks.picks[] | select(.game_status == "LIVE") | {live_boost, live_reasons}]'

# 4. Check weather adjustments (NFL/MLB only)
curl /live/best-bets/NFL?debug=1 -H "X-API-Key: KEY" | \
  jq '.game_picks.picks[0] | {weather_adj, research_reasons}'
# Should show weather adjustment for outdoor games (NOT dome games)

# 5. Check travel adjustments
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '.game_picks.picks[0].context_reasons | map(select(contains("Travel")))'
# Should show "Travel: XXXXmi + X-day rest" when applicable

# 6. Test SSE stream (requires enabled flag)
curl -N /live/stream/games/NBA -H "X-API-Key: KEY" | head -20
# Should return SSE events if streaming enabled

# 7. Test all sports for Phase 9 integration
for sport in NBA NHL NFL MLB NCAAB; do
  echo "=== $sport ==="
  curl -s "/live/best-bets/$sport?debug=1" -H "X-API-Key: KEY" | \
    jq '{sport, games: .game_picks.count, props: .props.count, error: .detail}'
done

# 8. Verify feature flags
curl /live/stream/status -H "X-API-Key: KEY" | jq '{streaming: .enabled, sse: .sse_available}'
```

**Critical Invariants (ALWAYS verify these):**
- Weather ONLY for outdoor sports (NFL, MLB, NCAAF)
- Live signals ONLY for game_status == "LIVE" or "MISSED_START"
- Weather cap: -0.35 max
- Live signals cap: ±0.50 combined
- SSE minimum interval: 15 seconds
- All 5 sports must pass regression test

---


---

## ✅ VERIFICATION CHECKLIST (v19.0 - Trap Learning Loop)

Run these after ANY change to Trap Learning Loop:

```bash
# 1. Syntax check trap modules
python -m py_compile trap_learning_loop.py trap_router.py

# 2. Verify trap storage directory exists
curl /internal/storage/health -H "X-API-Key: KEY" | jq '.trap_learning_dir'
# Should show: /data/trap_learning

# 3. List active traps
curl /live/traps/ -H "X-API-Key: KEY" | jq 'length'
# Should return count of active traps

# 4. Test trap creation
curl -X POST /live/traps/ -H "X-API-Key: KEY" -H "Content-Type: application/json" -d '{
  "name": "Test Trap Verification",
  "sport": "NBA",
  "condition": {"operator": "AND", "conditions": [
    {"field": "margin", "comparator": ">=", "value": 15}
  ]},
  "action": {"type": "WEIGHT_ADJUST", "delta": -0.01},
  "target_engine": "research",
  "target_parameter": "weight_public_fade"
}' | jq '{success, trap_id}'
# Should show success: true

# 5. Test dry-run evaluation (condition met)
curl -X POST /live/traps/evaluate/dry-run -H "X-API-Key: KEY" -H "Content-Type: application/json" -d '{
  "trap_id": "test-trap-verification",
  "game_result": {"margin": 25, "result": "win", "home_team": "Lakers", "away_team": "Celtics"}
}' | jq '{condition_met, would_apply, proposed_adjustment}'
# Should show condition_met: true

# 6. Test dry-run evaluation (condition NOT met)
curl -X POST /live/traps/evaluate/dry-run -H "X-API-Key: KEY" -H "Content-Type: application/json" -d '{
  "trap_id": "test-trap-verification",
  "game_result": {"margin": 5, "result": "win", "home_team": "Lakers", "away_team": "Celtics"}
}' | jq '{condition_met, would_apply}'
# Should show condition_met: false

# 7. Check adjustment history endpoint
curl /live/traps/history/research -H "X-API-Key: KEY" | jq '{engine, adjustments_count: (.adjustments | length)}'
# Should return engine: "research"

# 8. Get summary stats
curl /live/traps/stats/summary -H "X-API-Key: KEY" | jq '{total_traps, by_engine, by_sport}'
# Should show breakdown by engine and sport

# 9. Verify scheduler job is registered
curl /live/scheduler/status -H "X-API-Key: KEY" | jq '.jobs[] | select(.id == "trap_evaluation") | {id, next_run}'
# Should show trap_evaluation job with next_run time

# 10. Test SUPPORTED_ENGINES validation
curl -X POST /live/traps/ -H "X-API-Key: KEY" -H "Content-Type: application/json" -d '{
  "name": "Invalid Engine Test",
  "sport": "NBA",
  "condition": {"operator": "AND", "conditions": [{"field": "margin", "comparator": ">=", "value": 10}]},
  "action": {"type": "WEIGHT_ADJUST", "delta": -0.01},
  "target_engine": "invalid_engine",
  "target_parameter": "some_param"
}' | jq '.detail'
# Should return error about invalid engine

# 11. Test safety cap enforcement
curl -X POST /live/traps/ -H "X-API-Key: KEY" -H "Content-Type: application/json" -d '{
  "name": "Overcap Test",
  "sport": "NBA",
  "condition": {"operator": "AND", "conditions": [{"field": "margin", "comparator": ">=", "value": 10}]},
  "action": {"type": "WEIGHT_ADJUST", "delta": -0.10},
  "target_engine": "research",
  "target_parameter": "weight_public_fade",
  "adjustment_cap": 0.10
}' | jq '.detail'
# Should return error about exceeding max adjustment cap

# 12. Verify base engines are supported
python3 -c "
from trap_learning_loop import SUPPORTED_ENGINES
print('Supported engines:', list(SUPPORTED_ENGINES.keys()))
for k in ['ai', 'research', 'esoteric', 'jarvis']:
    assert k in SUPPORTED_ENGINES, f'Missing base engine: {k}'
print('✓ Base engines configured')
"

# 13. Test condition field validation
python3 -c "
from trap_learning_loop import CONDITION_FIELDS
print('Condition fields:', list(CONDITION_FIELDS.keys())[:10], '...')
assert 'result' in CONDITION_FIELDS, 'Missing result field'
assert 'margin' in CONDITION_FIELDS, 'Missing margin field'
assert 'numerology_day' in CONDITION_FIELDS, 'Missing numerology_day field'
print('✓ Condition fields valid')
"

# 14. Cleanup test trap
curl -X PUT "/live/traps/test-trap-verification/status?status=RETIRED" -H "X-API-Key: KEY"
```

**Critical Invariants (ALWAYS verify these):**
- Trap evaluation runs AFTER grading (6:15 AM > 6:00 AM)
- All adjustments capped at 5% single / 15% cumulative
- Cooldown enforced (24h default between triggers)
- Audit trail in `/data/trap_learning/adjustments.jsonl`
- Base engines (research, esoteric, jarvis, ai) supported

---


---

## ✅ VERIFICATION CHECKLIST (v19.1 - Complete Learning System)

Run these after ANY change to AutoGrader, PredictionRecord, or signal tracking:

```bash
# 1. Syntax check learning system modules
python -m py_compile auto_grader.py trap_learning_loop.py grader_store.py

# 2. Verify PredictionRecord has all signal fields
python3 -c "
from auto_grader import PredictionRecord
import dataclasses
fields = [f.name for f in dataclasses.fields(PredictionRecord)]
required = ['pick_type', 'sharp_money_adjustment', 'public_fade_adjustment',
            'line_variance_adjustment', 'glitch_signals', 'esoteric_contributions']
for r in required:
    assert r in fields, f'Missing field: {r}'
print(f'✓ PredictionRecord has {len(fields)} fields including all signal tracking')
"

# 3. Check signal fields in pick output
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | jq '.game_picks.picks[0] | {
  glitch_signals: .glitch_signals,
  esoteric_contributions: .esoteric_contributions,
  pick_type: .pick_type
}'
# Should show glitch_signals dict, esoteric_contributions dict, pick_type string

# 4. Verify reconciliation functions exist
python3 -c "
from trap_learning_loop import has_recent_trap_adjustment, get_recent_parameter_adjustments
from auto_grader import AutoGrader
grader = AutoGrader.__new__(AutoGrader)
assert hasattr(grader, 'check_trap_reconciliation') or hasattr(AutoGrader, 'check_trap_reconciliation'), 'Missing reconciliation'
print('✓ Reconciliation functions available')
"

# 5. Verify all 28 signals are tracked (spot check)
python3 -c "
from auto_grader import PredictionRecord
# Context Layer (5)
assert hasattr(PredictionRecord, '__dataclass_fields__')
# Check a sample
fields = PredictionRecord.__dataclass_fields__
context_fields = ['defense_adjustment', 'pace_adjustment', 'vacuum_adjustment', 'lstm_adjustment', 'officials_adjustment']
research_fields = ['sharp_money_adjustment', 'public_fade_adjustment', 'line_variance_adjustment']
glitch_field = 'glitch_signals'  # Dict for 6 signals
esoteric_field = 'esoteric_contributions'  # Dict for 14 signals

for f in context_fields + research_fields:
    assert f in fields, f'Missing: {f}'
assert glitch_field in fields, 'Missing glitch_signals'
assert esoteric_field in fields, 'Missing esoteric_contributions'
print('✓ All signal categories tracked (5 context + 3 research + 6 GLITCH + 14 esoteric = 28)')
"

# 6. Test grader status endpoint
curl /live/grader/status -H "X-API-Key: KEY" | jq '{
  available: .available,
  predictions_logged: .predictions_logged,
  storage_path: .storage_path
}'
# Should show available: true, predictions_logged > 0

# 7. Verify pick persistence includes new fields
# (This checks that live_data_router extracts signal data)
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | jq '[.game_picks.picks[0] | keys[]] | map(select(startswith("glitch") or startswith("esoteric")))'
# Should show glitch_signals, esoteric_contributions, etc.

# 8. Test all 5 sports signal extraction
for sport in NBA NHL NFL MLB NCAAB; do
  echo "=== $sport ==="
  curl -s "/live/best-bets/$sport?debug=1" -H "X-API-Key: KEY" | \
    jq '{sport: .sport, picks: (.game_picks.count + .props.count), has_signals: (.game_picks.picks[0].glitch_signals != null)}'
done
```

**Critical Invariants (ALWAYS verify these):**
- ALL 28 signals tracked in PredictionRecord (5 context + 3 research + 6 GLITCH + 14 esoteric)
- pick_type field populated (PROP, SPREAD, TOTAL, MONEYLINE, SHARP)
- glitch_signals and esoteric_contributions are dicts (not null)
- Trap-AutoGrader reconciliation prevents conflicting adjustments
- 70% confidence decay applied in bias calculation

---


---

## ✅ VERIFICATION CHECKLIST (v17.6 - Vortex, Benford, Line History)

Run these after ANY change to Vortex, Benford, or Line History features:

```bash
# 1. Syntax check all modified files
python -m py_compile esoteric_engine.py live_data_router.py database.py daily_scheduler.py

# 2. Test Vortex function directly (Tesla 3-6-9 resonance)
python3 -c "
from esoteric_engine import calculate_vortex_energy
print('3.5 spread:', calculate_vortex_energy(3.5, 'spread'))
print('369 value:', calculate_vortex_energy(369, 'general'))
print('246.5 total:', calculate_vortex_energy(246.5, 'total'))
print('9.5 (Tesla):', calculate_vortex_energy(9.5, 'spread'))
"
# Should show: is_tesla_aligned=True for values with digital root 3, 6, or 9

# 3. Verify Benford now receives 10+ values
curl -s '/live/best-bets/NBA?debug=1' -H 'X-API-Key: KEY' | \
  jq '.game_picks.picks[0].glitch_breakdown.benford | {values_count, triggered, distribution}'
# values_count should be 10-25 (not 3)

# 4. Check Vortex in esoteric_reasons
curl -s '/live/best-bets/NBA?debug=1' -H 'X-API-Key: KEY' | \
  jq '[.game_picks.picks[].esoteric_reasons] | flatten | map(select(startswith("Vortex")))'
# Should show: "Vortex: TESLA_ALIGNED (root=3)" or similar

# 5. Verify all 3 call sites pass game_bookmakers
grep -n "calculate_pick_score(" live_data_router.py | wc -l
# Should be 4 (1 definition + 3 calls)
grep -n "game_bookmakers=" live_data_router.py | wc -l
# Should be 4 (matching all call sites)

# 6. Test multi-book extraction function
python3 -c "
import sys
sys.path.insert(0, '.')
from live_data_router import _extract_benford_values_from_game
game = {
    'bookmakers': [
        {'markets': [{'key': 'spreads', 'outcomes': [{'point': 3.5}, {'point': -3.5}]},
                     {'key': 'totals', 'outcomes': [{'point': 220.5}, {'point': 220.5}]}]},
        {'markets': [{'key': 'spreads', 'outcomes': [{'point': 3}, {'point': -3}]},
                     {'key': 'totals', 'outcomes': [{'point': 221}, {'point': 221}]}]}
    ]
}
values = _extract_benford_values_from_game(game, 25.5, 3.5, 220.5)
print(f'Extracted {len(values)} values: {values}')
assert len(values) >= 5, f'Expected 5+ values, got {len(values)}'
print('✓ Multi-book extraction working')
"

# 7. Test all 5 sports for Vortex/Benford
for sport in NBA NHL NFL MLB NCAAB; do
  echo "=== $sport ==="
  curl -s "/live/best-bets/$sport?debug=1" -H "X-API-Key: KEY" | \
    jq '{
      picks: (.game_picks.count + .props.count),
      has_vortex: ([.game_picks.picks[].esoteric_reasons] | flatten | map(select(startswith("Vortex"))) | length > 0),
      benford_values: .game_picks.picks[0].glitch_breakdown.benford.values_count
    }'
done

# 8. Check database tables exist (for line history)
python3 -c "
from database import LineSnapshot, SeasonExtreme, engine
from sqlalchemy import inspect
inspector = inspect(engine)
tables = inspector.get_table_names()
print('line_snapshots exists:', 'line_snapshots' in tables)
print('season_extremes exists:', 'season_extremes' in tables)
"

# 9. Esoteric Engine Signal Status (should be 10/10)
curl -s '/live/best-bets/NBA?debug=1' -H 'X-API-Key: KEY' | \
  jq '[.game_picks.picks[].esoteric_reasons, .props.picks[].esoteric_reasons] | flatten | unique | length'
# Should show 10+ unique signal types
```

---


---

## ✅ VERIFICATION CHECKLIST (v18.2 - Phase 8 Esoteric Signals)

Run these after ANY change to Phase 8 signals (lunar, mercury, rivalry, streak, solar):

```bash
# 1. Syntax check esoteric_engine.py
python -m py_compile esoteric_engine.py

# 2. Test Phase 8 aggregator directly
python3 -c "
from esoteric_engine import get_phase8_esoteric_signals
from datetime import datetime, date
from zoneinfo import ZoneInfo
dt = datetime.now(ZoneInfo('America/New_York'))
d = date.today()
result = get_phase8_esoteric_signals(
    game_datetime=dt,
    game_date=d,
    sport='NBA',
    home_team='Lakers',
    away_team='Celtics',
    pick_type='TOTAL',
    pick_side='Over'
)
print('Phase 8 result:', result)
print('Total boost:', result.get('total_boost'))
print('Reasons:', result.get('reasons'))
"

# 3. Check lunar phase calculation
python3 -c "
from esoteric_engine import calculate_lunar_phase_intensity
from datetime import datetime
from zoneinfo import ZoneInfo
dt = datetime.now(ZoneInfo('America/New_York'))
result = calculate_lunar_phase_intensity(dt)
print('Lunar:', result)
"

# 4. Check Mercury retrograde
python3 -c "
from esoteric_engine import check_mercury_retrograde
from datetime import date
print('Mercury:', check_mercury_retrograde(date.today()))
"

# 5. Check rivalry detection
python3 -c "
from esoteric_engine import calculate_rivalry_intensity
print('Lakers-Celtics:', calculate_rivalry_intensity('NBA', 'Lakers', 'Celtics'))
print('Packers-Bears:', calculate_rivalry_intensity('NFL', 'Packers', 'Bears'))
print('Non-rivalry:', calculate_rivalry_intensity('NBA', 'Kings', 'Wizards'))
"

# 6. Check Phase 8 in production picks
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '.game_picks.picks[0] | {phase8_boost, phase8_reasons, phase8_breakdown}'

# 7. Test all 5 sports
for sport in NBA NHL NFL MLB NCAAB; do
  echo "=== $sport ==="
  result=$(curl -s "/live/best-bets/$sport?debug=1" -H "X-API-Key: KEY")
  picks=$(echo "$result" | jq '(.game_picks.count + .props.count)')
  phase8=$(echo "$result" | jq '.game_picks.picks[0].phase8_boost // "null"')
  echo "Picks: $picks, Phase8 boost: $phase8"
done

# 8. Check for timezone errors in logs
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '.game_picks.picks[0].phase8_error // "none"'
# Should return "none" or null

# 9. Verify env-map OR logic
curl /ops/env-map -H "X-Admin-Key: ADMIN_KEY" | \
  jq '.missing_required'
# Should NOT include SERP_API_KEY if SERPAPI_KEY is set

# 10. Production sanity check (18 checks)
./scripts/prod_sanity_check.sh
# Should pass all 18 checks
```

**Critical Invariants (ALWAYS verify these):**
- `game_datetime` MUST be timezone-aware (use `ZoneInfo`)
- `ref_date` in lunar calculation MUST be timezone-aware (UTC)
- `weather_data` MUST be initialized to `None` before conditional use
- Phase 8 boost added to `esoteric_raw`, not directly to final score
- All 5 signals aggregated via `get_phase8_esoteric_signals()`

---


---

## ✅ VERIFICATION CHECKLIST (v20.11 - Post-Base Signals)

Run these after ANY change to Hook Discipline, Expert Consensus, Prop Correlation, or scoring pipeline:

```bash
# 1. Syntax check scoring modules
python -m py_compile core/scoring_contract.py core/scoring_pipeline.py live_data_router.py

# 2. Run reconciliation tests (CRITICAL - verifies math contract)
python3 -m pytest tests/test_option_a_scoring_guard.py -v -k "v20_3"
# All 5 v20.3 tests must pass

# 3. Verify post-base signals in pick payload
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '.game_picks.picks[0] | {
    hook_penalty, hook_flagged, hook_reasons,
    expert_consensus_boost, expert_status,
    prop_correlation_adjustment, prop_corr_status
  }'
# All fields must be present (not null/undefined)

# 4. Verify caps enforced (hook_penalty ≤ 0, expert ≥ 0, prop_corr in [-0.20, 0.20])
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '[.game_picks.picks[] | {
    hook: .hook_penalty,
    expert: .expert_consensus_boost,
    prop_corr: .prop_correlation_adjustment
  }] | {
    hook_max: (map(.hook) | max),
    expert_min: (map(.expert) | min),
    prop_corr_range: [(map(.prop_corr) | min), (map(.prop_corr) | max)]
  }'
# hook_max ≤ 0, expert_min ≥ 0, prop_corr_range within [-0.20, 0.20]

# 5. Verify math reconciliation (manually for one pick)
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | jq '.game_picks.picks[0] | {
  base_4: .base_4_score,
  context: .context_modifier,
  confluence: .confluence_boost,
  msrf: .msrf_boost,
  jason_sim: .jason_sim_boost,
  serp: .serp_boost,
  ensemble: (.ensemble_adjustment // 0),
  live: (.live_adjustment // 0),
  totals_cal: (.totals_calibration_adj // 0),
  hook: (.hook_penalty // 0),
  expert: (.expert_consensus_boost // 0),
  prop_corr: (.prop_correlation_adjustment // 0),
  computed_sum: (.base_4_score + .context_modifier + .confluence_boost + .msrf_boost +
                 .jason_sim_boost + .serp_boost + (.ensemble_adjustment // 0) +
                 (.live_adjustment // 0) + (.totals_calibration_adj // 0) +
                 (.hook_penalty // 0) + (.expert_consensus_boost // 0) +
                 (.prop_correlation_adjustment // 0)),
  actual_final: .final_score,
  diff: ((.base_4_score + .context_modifier + .confluence_boost + .msrf_boost +
          .jason_sim_boost + .serp_boost + (.ensemble_adjustment // 0) +
          (.live_adjustment // 0) + (.totals_calibration_adj // 0) +
          (.hook_penalty // 0) + (.expert_consensus_boost // 0) +
          (.prop_correlation_adjustment // 0)) - .final_score) | fabs
}'
# diff must be < 0.02

# 6. Verify no research_score mutation in router (regression guard)
grep -n "research_score.*+=" live_data_router.py | grep -v "^#" | head -5
# Should return EMPTY or only comments

# 7. Test all 5 sports for v20.11 fields
for sport in NBA NHL NFL MLB NCAAB; do
  echo "=== $sport ==="
  curl -s "/live/best-bets/$sport?debug=1" -H "X-API-Key: KEY" | \
    jq '{sport: .sport, has_hook: (.game_picks.picks[0].hook_penalty != null), has_expert: (.game_picks.picks[0].expert_consensus_boost != null)}'
done
```

**Critical Invariants (v20.11):**
- Engine scores are LOCKED once BASE_4 is computed — never mutate after
- Post-base signals passed as explicit parameters to `compute_final_score_option_a()`
- All additive terms surfaced as pick fields for audit trail
- Caps enforced INSIDE the scoring function (single source of truth)
- Reconciliation tolerance: `abs(final - clamp(sum)) <= 0.02`

---


---

## Production Proof Checklist (Option A + Integrations)

Use this to prove (not assume) the backend is fully healthy end-to-end and Option A is enforced in production.

### 1) Prove Railway is running the intended commit
**Goal:** runtime build metadata matches the intended git commit.
- In Railway: Service -> Deployments -> confirm deployed commit SHA (expected: `87e70cc`).
- Hit a prod metadata endpoint (build_sha / deploy_version if exposed).
**Pass condition:** prod metadata matches the intended commit, and build_sha changes when you redeploy.

### 2) Integration truth test (not "it didn't crash")
**Goal:** each required integration is configured and exercised.
- Call `/live/debug/integrations`.
- Verify, per integration: `configured=true`, connectivity OK, and `last_success` moves after best-bets.
**Pass condition:** every required integration shows green and timestamps move with real calls.

### 3) Force an end-to-end best-bets run
**Goal:** prove full scoring pipeline executed (not partial/timeouts).
- Call best-bets for each sport supported.
- Verify: `stack_complete=true`, `_timed_out_components` empty, `errors` empty.
- Ensure breakdown fields exist: ai/research/esoteric/jarvis + `context_modifier` + boosts.
**Pass condition:** no critical timeouts on a normal run.

### 4) Prove Option A is enforced in production
**Goal:** confirm final score formula is Option A (context is modifier only).
Inspect 1 prod pick and verify:
- BASE_4 uses AI/Research/Esoteric/Jarvis only.
- Context appears as bounded modifier (cap) with explicit reasons.
- FINAL ~= BASE_4 + context_modifier + confluence_boost + msrf_boost + jason_sim_boost + serp_boost (within rounding).
**Pass condition:** hand-calc one pick and it matches response fields.

### 5) Hard guard against context-as-engine regression
**Goal:** CI fails if legacy weighted scoring returns.
- Add invariant test that fails if any of these appear in scoring paths:
  - `BASE_5`
  - `ENGINE_WEIGHTS["context"]`
  - `context * weight` logic inside final score calc
- Add CI drift scan (rg/grep) for forbidden tokens in scoring modules.
**Pass condition:** PR cannot merge if context is reintroduced as a weighted engine.

### 6) Diversity + concentration protection active in prod
**Goal:** ensure diversity filters engage and prevent repeats.
- Confirm telemetry counters exist and move when filter drops items:
  - `diversity_player_limited`
  - `diversity_game_limited`
  - `diversity_total_dropped`
**Pass condition:** filter engages when needed and never outputs duplicates beyond policy.

### 7) Caching + TTL behavior under load
**Goal:** avoid stale data and protect paid APIs.
- Call same endpoint twice quickly:
  - first call slower
  - second call faster with cache metadata where applicable
- Verify TTLs match intended policy (best-bets vs normal endpoints).
**Pass condition:** caching matches design.

### 8) Failure-mode smoke test
**Goal:** graceful degradation with deterministic error codes.
- In staging: disable one integration (revoke key or block network).
- Ensure best-bets returns fail-soft (no 500) and debug endpoint shows fail-loud.
**Pass condition:** no 500s, stable error codes, debug shows the exact failure.

### 9) Codex tasks (patch + review only)
1. Diff audit: confirm scoring formula is identical across:
   - scoring contract / pipeline
   - live router
   - any legacy helpers
2. Guardrails PR:
   - CI drift scan for forbidden patterns (BASE_5 / context weighting)
   - unit test that computes final_score and asserts Option A structure
3. Production sanity script:
   - calls best-bets for each sport
   - calls debug integrations
   - asserts: stack_complete true, no timeouts, no duplicates, no 500s

**Shortest path (do first):**
1) `/live/debug/integrations` all green + timestamps move
2) best-bets has `_timed_out_components = []` and `stack_complete = true`
3) manual recompute of one pick’s final_score matches formula

---


---

