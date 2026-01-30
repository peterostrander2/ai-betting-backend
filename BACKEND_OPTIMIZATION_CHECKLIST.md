# Backend 100% Verification Checklist
**Goal:** Prove every signal, engine, API, and tier is working correctly before moving to frontend.

---

## ✅ COMPLETED (Session 1)
- [x] Documentation organized (PROJECT_MAP, SCORING_LOGIC, etc.)
- [x] ET window fixed (00:01:00 start, capturing all games)
- [x] All 3 APIs configured (Odds, Playbook, BallDontLie)
- [x] Commit checklist with smoke tests
- [x] Invariant guardrails (numbering + runtime) with auto pre-commit hooks
- [x] Memory: All solutions must be automatic

---

## ✅ SESSION 2: ENGINE VERIFICATION (COMPLETED)

### 1. AI ENGINE (25% weight)
**File:** `advanced_ml_backend.py`
**Expected Range:** 4.0-8.5

**Verify:**
- [x] All 8 models running
- [x] Sharp money bonus (+0.5) applies when present
- [x] Signal strength bonus (0.25-1.0) calculates
- [x] Player data bonus (+0.25) when available
- [x] Scores in expected range (not stuck at defaults)
- [x] **ai_reasons array populated** (fixed in commit 1c9cf7d)

**Command:**
```bash
curl "https://web-production-7b2a.up.railway.app/live/best-bets/nba?debug=1&max_props=3" \
  -H "X-API-Key: bookie-prod-2026-xK9mP2nQ7vR4" | jq '.props.picks[0:3] | .[] | {
    player: .player_name,
    ai_score,
    ai_reasons
  }'
```

**Success:** AI scores 4.0-8.5, reasons show model outputs

---

### 2. RESEARCH ENGINE (30% weight)
**File:** `live_data_router.py` (research section)
**Expected Range:** 3.0-8.0

**Verify:**
- [x] Sharp money signals (STRONG=3.0, MODERATE=2.0, MILD=1.0) from Playbook
- [x] Line variance (>0.5=3pts, >0.2=2pts, else 1pt)
- [x] Public fade triggers (public≥65% AND divergence≥5% = 2pts)
- [x] Base score (real splits=3pts, estimated=2pts)
- [x] **NO double-counting** (sharp money ONLY here, not in Jarvis)

**Command:**
```bash
curl "https://web-production-7b2a.up.railway.app/live/best-bets/nba?debug=1&max_props=3" \
  -H "X-API-Key: bookie-prod-2026-xK9mP2nQ7vR4" | jq '.props.picks[0:3] | .[] | {
    player: .player_name,
    research_score,
    research_reasons,
    sharp_present: (.research_reasons | any(contains("Sharp")))
  }'
```

**Success:** Sharp money visible in reasons, scores 3.0-8.0

---

### 3. ESOTERIC ENGINE (20% weight)
**File:** `live_data_router.py` lines 2352-2435
**Expected Range:** 3.5-6.5 (games ~4.0, props ~5.5-6.0)

**Verify:**
- [x] Numerology (35% = 3.5pts max)
- [x] Astro (25% = 2.5pts max)
- [x] Fibonacci (15% = 1.5pts max) - uses magnitude
- [x] Vortex (15% = 1.5pts max) - uses magnitude × 10
- [x] Daily Edge (10% = 1.0pt max)
- [x] **Props use prop_line for magnitude** (NOT spread=0)
- [x] NOT stuck at ~1.1

**Command:**
```bash
curl "https://web-production-7b2a.up.railway.app/live/best-bets/nba?debug=1&max_props=3" \
  -H "X-API-Key: bookie-prod-2026-xK9mP2nQ7vR4" | jq '.props.picks[0:3] | .[] | {
    player: .player_name,
    esoteric_score,
    magnitude: .esoteric_breakdown.magnitude_input,
    prop_line: .line
  }'
```

**Success:** Esoteric 2.0-5.5, magnitude matches prop_line (not 0)

---

### 4. JARVIS ENGINE (15% weight)
**File:** `jarvis_savant_engine.py`
**Expected Range:** 1.0-10.0 (4.5 baseline when no triggers; can be lower with weak triggers + low gematria)

**Verify:**
- [x] 7-field contract present (jarvis_rs, jarvis_active, jarvis_hits_count, etc.)
- [x] Gematria triggers fire (2178, 201, 33, 93, 322)
- [x] Baseline 4.5 when inputs present but no triggers
- [x] jarvis_rs is None ONLY when jarvis_active is False
- [x] jarvis_fail_reasons explains low scores

**Command:**
```bash
curl "https://web-production-7b2a.up.railway.app/live/best-bets/nba?debug=1&max_props=3" \
  -H "X-API-Key: bookie-prod-2026-xK9mP2nQ7vR4" | jq '.props.picks[0:3] | .[] | {
    player: .player_name,
    jarvis_rs,
    jarvis_active,
    jarvis_hits: .jarvis_hits_count,
    jarvis_triggers: .jarvis_triggers_hit
  }'
```

**Success:** Contract complete, scores 4.5-10.0, triggers firing

---

## ✅ SESSION 3: POST-PICK LAYERS (COMPLETED)

### 5. JASON SIM BOOST
**File:** `jason_sim_confluence.py`
**Range:** Can be negative

**Verify:**
- [x] Spreads/ML: win%≥61% gets +0.3 to +0.5
- [x] Spreads/ML: win%≤52% + base<7.2 gets -0.2 to -0.5 penalty
- [x] Totals: high variance reduces confidence
- [x] Props: boost ONLY if base≥6.8 + environment supports
- [x] All fields present (jason_sim_available, jason_sim_boost, jason_sim_reasons, etc.)

**Command:**
```bash
curl "https://web-production-7b2a.up.railway.app/live/best-bets/nba?debug=1&max_props=3" \
  -H "X-API-Key: bookie-prod-2026-xK9mP2nQ7vR4" | jq '.props.picks[0:3] | .[] | {
    player: .player_name,
    base_score,
    jason_sim_boost,
    jason_reasons: .jason_sim_reasons,
    final_score
  }'
```

**Success:** Boost applied, can be negative, reasons explain

---

### 6. CONFLUENCE BOOST
**Logic:** alignment = 1 - |research - esoteric| / 10

**Verify:**
- [x] STRONG (+3.0): alignment≥80% AND (jarvis_active OR sharp OR jason≠0)
- [x] MODERATE (+1.0): alignment≥60%
- [x] DIVERGENT (0): alignment<60%
- [x] Active signal gate prevents free +3 for mediocre engines

**Command:**
```bash
curl "https://web-production-7b2a.up.railway.app/live/best-bets/nba?debug=1&max_props=3" \
  -H "X-API-Key: bookie-prod-2026-xK9mP2nQ7vR4" | jq '.props.picks[0:3] | .[] | {
    player: .player_name,
    research_score,
    esoteric_score,
    confluence_boost,
    calculated_alignment: (1 - ((.research_score - .esoteric_score) | abs) / 10)
  }'
```

**Success:** Boost matches alignment, gated appropriately

---

## ⚠️ SESSION 4: CONTEXT MODIFIERS (NOT INTEGRATED)

**Investigation Complete (Jan 30, 2026):** These features exist in codebase but are NOT integrated into the scoring path.

### 7. VACUUM SCORE
**Status:** ❌ NOT IMPLEMENTED

**Finding:** No `vacuum_score` code exists in the codebase. This feature was planned but never built.

**Decision Needed:** Build from scratch or remove from checklist.

---

### 8. WEATHER CONTEXT
**Status:** ✅ FULLY IMPLEMENTED but ❌ NOT INTEGRATED

**Location:** `alt_data_sources/weather.py`
**Function:** `get_weather_context(sport, home_team, venue, lat, lon)`

**Features:**
- Indoor sport detection (NBA, NHL, NCAAB → `NOT_RELEVANT`)
- NFL dome detection → `NOT_RELEVANT`
- Score modifier bounded [-0.35, 0.0]
- WeatherAPI.com integration with 10-min cache

**Issue:** `get_weather_context()` is NEVER called from `live_data_router.py`

**Plan Available:** See `/Users/apple/.claude/plans/sorted-petting-hare.md` for integration plan

**Behavior for NBA:** Returns `{"status": "NOT_RELEVANT", "reason": "Indoor sport", "score_modifier": 0.0}`

---

### 9. REST DAYS & HOME/AWAY
**Status:** EXISTS but ❌ NOT INTEGRATED

**Locations:**
- `rest_days`: `alt_data_sources/travel.py` - NOT called from scoring path
- `home_away`: `lstm_brain.py`, `context_layer.py` - Used internally for LSTM, NOT exposed in API

**Decision Needed:** Integrate into scoring path or remove from checklist.

---

### SESSION 4 SUMMARY

| Feature | Code Exists | Integrated | Action |
|---------|-------------|------------|--------|
| `vacuum_score` | ❌ No | N/A | Build or Remove |
| `weather_context` | ✅ Yes | ❌ No | Integrate per plan |
| `rest_days` | ✅ Yes | ❌ No | Integrate or Remove |
| `home_away` | ✅ Yes | ❌ No | Expose or Remove |

**Next Step:** Decide which features to integrate vs. skip for MVP.

---

## 🎯 SESSION 5: API INTEGRATION

### 10. ODDS API
**Verify:**
- [ ] Live odds fetching
- [ ] Props retrieved
- [ ] ET filter applied BEFORE scoring
- [ ] Integration status: configured + reachable

**Commands:**
```bash
# Integration status
curl "https://web-production-7b2a.up.railway.app/live/debug/integrations" \
  -H "X-API-Key: bookie-prod-2026-xK9mP2nQ7vR4" | jq '.integrations.odds_api'

# Verify props present
curl "https://web-production-7b2a.up.railway.app/live/best-bets/nba?debug=1" \
  -H "X-API-Key: bookie-prod-2026-xK9mP2nQ7vR4" | jq '{
    props_after_et: .debug.date_window_et.events_after_props,
    props_returned: .props.count
  }'
```

**Success:** Configured, props flowing, ET filter working

---

### 11. PLAYBOOK API
**Verify:**
- [ ] Sharp money in picks
- [ ] Betting splits data
- [ ] Injury data
- [ ] Integration status

**Commands:**
```bash
# Integration status
curl "https://web-production-7b2a.up.railway.app/live/debug/integrations" \
  -H "X-API-Key: bookie-prod-2026-xK9mP2nQ7vR4" | jq '.integrations.playbook_api'

# Sharp money in picks
curl "https://web-production-7b2a.up.railway.app/live/best-bets/nba?debug=1" \
  -H "X-API-Key: bookie-prod-2026-xK9mP2nQ7vR4" | \
  jq '.props.picks[] | select(.research_reasons[] | contains("Sharp")) | {
    player: .player_name,
    sharp_signal: (.research_reasons[] | select(contains("Sharp")))
  }' | head -20
```

**Success:** Configured, sharp signals visible in picks

---

### 12. BALLDONTLIE API
**Verify:**
- [ ] Integration configured
- [ ] Player stats fetching
- [ ] Grading integration
- [ ] No "(not set" errors in logs

**Commands:**
```bash
# Integration status
curl "https://web-production-7b2a.up.railway.app/live/debug/integrations" \
  -H "X-API-Key: bookie-prod-2026-xK9mP2nQ7vR4" | jq '.integrations.balldontlie'

# Check Railway logs for BDL errors
# Look for: [BDL STARTUP] messages
```

**Success:** Configured, no startup errors

---

## 🎯 SESSION 6: TIER ASSIGNMENT

### 13. TITANIUM_SMASH
**Rule:** ≥3 of 4 engines ≥8.0 (STRICT)
**File:** `core/titanium.py` (single source of truth)

**Verify:**
- [ ] Uses core/titanium.py
- [ ] Boundary: 3/4 at 8.0 = TRUE, 2/4 = FALSE
- [ ] Overrides all other tiers

**Command:**
```bash
curl "https://web-production-7b2a.up.railway.app/live/best-bets/nba?debug=1" \
  -H "X-API-Key: bookie-prod-2026-xK9mP2nQ7vR4" | jq '.props.picks[] | select(.tier == "TITANIUM_SMASH") | {
    player: .player_name,
    tier,
    final_score,
    engines_above_8: ([.ai_score, .research_score, .esoteric_score, .jarvis_rs] | map(select(. >= 8.0)) | length),
    ai: .ai_score,
    research: .research_score,
    esoteric: .esoteric_score,
    jarvis: .jarvis_rs
  }'
```

**Success:** TITANIUM picks have 3+ engines ≥8.0

---

### 14. GOLD_STAR
**Rule:** Score ≥7.5 + ALL hard gates pass

**Verify:**
- [ ] ai_score ≥6.8
- [ ] research_score ≥5.5
- [ ] jarvis_score ≥6.5
- [ ] esoteric_score ≥4.0
- [ ] Downgrades to EDGE_LEAN if any gate fails

**Command:**
```bash
curl "https://web-production-7b2a.up.railway.app/live/best-bets/nba?debug=1" \
  -H "X-API-Key: bookie-prod-2026-xK9mP2nQ7vR4" | jq '.props.picks[] | select(.tier == "GOLD_STAR") | {
    player: .player_name,
    tier,
    final_score,
    ai: .ai_score,
    research: .research_score,
    jarvis: .jarvis_rs,
    esoteric: .esoteric_score,
    gates_pass: (
      (.ai_score >= 6.8) and
      (.research_score >= 5.5) and
      (.jarvis_rs >= 6.5) and
      (.esoteric_score >= 4.0)
    )
  }'
```

**Success:** GOLD_STAR picks pass all gates

---

### 15. EDGE_LEAN
**Rule:** Score ≥6.5, default tier

**Command:**
```bash
curl "https://web-production-7b2a.up.railway.app/live/best-bets/nba?debug=1" \
  -H "X-API-Key: bookie-prod-2026-xK9mP2nQ7vR4" | jq '.props.picks[] | select(.tier == "EDGE_LEAN") | {
    player: .player_name,
    tier,
    final_score
  }' | head -20
```

**Success:** EDGE_LEAN picks are 6.5+

---

## 🎯 SESSION 7: OUTPUT FILTERING

### 16. PIPELINE VERIFICATION
**File:** `live_data_router.py` lines 3532-3560

**Verify:**
- [ ] Deduplication (by pick_id)
- [ ] Score filter (≥6.5)
- [ ] Contradiction gate
- [ ] Top N selection

**Command:**
```bash
curl "https://web-production-7b2a.up.railway.app/live/best-bets/nba?debug=1" \
  -H "X-API-Key: bookie-prod-2026-xK9mP2nQ7vR4" | jq '{
    props_analyzed: .debug.date_window_et.events_after_props,
    props_returned: .props.count,
    games_analyzed: .debug.date_window_et.events_after_games,
    games_returned: .game_picks.count,
    filtered_below_6_5: .debug.filtered_below_6_5_total,
    contradictions_blocked: .debug.contradiction_blocked_total
  }'
```

**Success:** Pipeline numbers make sense, no excessive filtering

---

## 🎯 SESSION 8: GRADING & PERSISTENCE

### 17. PICK PERSISTENCE
**Path:** `/app/grader_data/grader/predictions.jsonl`

**Verify:**
- [ ] Writes to correct path
- [ ] Atomic JSONL appends
- [ ] Survives container restart

**Commands:**
```bash
# Storage health
curl "https://web-production-7b2a.up.railway.app/internal/storage/health" \
  -H "X-API-Key: bookie-prod-2026-xK9mP2nQ7vR4"

# Before restart
BEFORE=$(curl -s "https://web-production-7b2a.up.railway.app/live/grader/status" \
  -H "X-API-Key: bookie-prod-2026-xK9mP2nQ7vR4" | jq '.total_predictions')

# Restart container in Railway dashboard
# Wait 2 minutes

# After restart
AFTER=$(curl -s "https://web-production-7b2a.up.railway.app/live/grader/status" \
  -H "X-API-Key: bookie-prod-2026-xK9mP2nQ7vR4" | jq '.total_predictions')

# Assert: BEFORE == AFTER
```

**Success:** Pick count survives restart

---

### 18. AUTO-GRADER
**Schedule:** Every 30 minutes

**Verify:**
- [ ] Job runs on schedule
- [ ] Uses BallDontLie for NBA
- [ ] Weight learning updates
- [ ] No errors in logs

**Commands:**
```bash
# Grader status
curl "https://web-production-7b2a.up.railway.app/live/grader/status" \
  -H "X-API-Key: bookie-prod-2026-xK9mP2nQ7vR4"

# Check Railway logs for scheduler
# Look for: "Auto-grading enabled: runs every 30 minutes"
```

**Success:** Grader runs, picks graded, weights update

---

## 🎯 SESSION 9: SCORE DISTRIBUTION

### 19. THRESHOLD ANALYSIS
**Current:** final_score ≥6.5

**Verify:**
- [ ] How many picks 6.0-6.5?
- [ ] Is threshold too strict?
- [ ] Should we lower to 6.0?

**Command:**
```bash
curl "https://web-production-7b2a.up.railway.app/live/best-bets/nba?debug=1" \
  -H "X-API-Key: bookie-prod-2026-xK9mP2nQ7vR4" | jq '{
    total_analyzed: (.debug.date_window_et.events_after_props + .debug.date_window_et.events_after_games),
    total_returned: (.props.count + .game_picks.count),
    filtered_below_6_5: .debug.filtered_below_6_5_total,
    filter_rate: ((.debug.filtered_below_6_5_total / (.props.count + .game_picks.count + .debug.filtered_below_6_5_total)) * 100 | round)
  }'
```

**Success:** Filter rate reasonable (<80%), not losing great picks

---

### 20. ENGINE RANGES
**Expected Ranges:**
- AI: 4.0-8.5
- Research: 2.5-8.0
- Esoteric: 3.5-6.5 (games ~4.0, props ~5.5-6.0)
- Jarvis: 4.5-10.0

**Command:**
```bash
curl "https://web-production-7b2a.up.railway.app/live/best-bets/nba?debug=1" \
  -H "X-API-Key: bookie-prod-2026-xK9mP2nQ7vR4" | jq '{
    ai: {
      min: ([.props.picks[].ai_score] | min),
      max: ([.props.picks[].ai_score] | max),
      avg: ([.props.picks[].ai_score] | add / length | . * 100 | round / 100)
    },
    research: {
      min: ([.props.picks[].research_score] | min),
      max: ([.props.picks[].research_score] | max),
      avg: ([.props.picks[].research_score] | add / length | . * 100 | round / 100)
    },
    esoteric: {
      min: ([.props.picks[].esoteric_score] | min),
      max: ([.props.picks[].esoteric_score] | max),
      avg: ([.props.picks[].esoteric_score] | add / length | . * 100 | round / 100)
    },
    jarvis: {
      min: ([.props.picks[].jarvis_rs] | min),
      max: ([.props.picks[].jarvis_rs] | max),
      avg: ([.props.picks[].jarvis_rs] | add / length | . * 100 | round / 100)
    }
  }'
```

**Success:** All engines in expected ranges, esoteric NOT ~1.1

---

## 🎯 SESSION 10: PICK VOLUME

### 21. LIMITS CHECK
**Current:** max_props=10, max_games=10

**Verify:**
- [ ] Are limits too restrictive?
- [ ] Filtering 100+ good picks?
- [ ] Should increase to 20 or 50?

**Command:**
```bash
curl "https://web-production-7b2a.up.railway.app/live/best-bets/nba?debug=1" \
  -H "X-API-Key: bookie-prod-2026-xK9mP2nQ7vR4" | jq '{
    props_potential: (.props.count + .debug.filtered_below_6_5_total),
    props_returned: .props.count,
    props_limit: 10,
    games_potential: (.game_picks.count + .debug.filtered_below_6_5_total),
    games_returned: .game_picks.count,
    games_limit: 10
  }'
```

**Discussion:** Should we increase limits if quality maintained?

---

## 🎯 FINAL: PRODUCTION SANITY CHECK

### 22. FULL SYSTEM CHECK

**Run:**
```bash
./scripts/prod_sanity_check.sh
```

**Verify:**
- [ ] All 17 checks passing
- [ ] No Railway errors
- [ ] Health endpoint 200 OK
- [ ] All integrations configured

---

## 📋 SUCCESS CRITERIA

Backend is 100% verified when:

✅ **Engines:** All 4 engines returning scores in expected ranges
✅ **APIs:** All 3 APIs visible in picks (sharp money, player stats, odds)
⚠️ **Context:** Vacuum/weather/rest - NOT INTEGRATED (see Session 4 notes)
✅ **Tiers:** TITANIUM uses core/titanium.py, all gates enforced
✅ **Separation:** NO double-counting (sharp money ONLY in Research)
✅ **Esoteric:** NOT stuck at ~1.1 for props (magnitude uses prop_line)
✅ **Grading:** Auto-grader runs every 30 min, picks persist across restart
✅ **Distribution:** Score ranges healthy, not all bunched at 6.5
✅ **Volume:** Pick limits appropriate, not losing quality picks
✅ **Sanity:** All 17 prod checks passing

**Note on Context Modifiers:** Weather, rest_days, and home_away code EXISTS but is NOT integrated into the scoring path. These are optional enhancements for future. Vacuum_score does not exist.

---

## 🚀 AFTER 100% VERIFICATION

Once every check passes:
- Backend is bulletproof
- All signals firing correctly
- All APIs utilized properly
- **Ready for frontend development**

---

**Work through this checklist session by session. Check off items as verified. Fix anything broken. Then move to frontend with confidence.**
