# ML Models & GLITCH Protocol Reference

## 🧠 ML MODEL ACTIVATION & GLITCH PROTOCOL (v17.2)

**Implemented:** February 2026
**Status:** 100% Complete - All 19 features + 6 APIs active

This section documents the ML infrastructure and GLITCH Protocol esoteric signals that were dormant and have now been fully activated.

---

### INVARIANT 14: ML Model Activation (LSTM + Ensemble)

**RULE:** Props use LSTM models, Games use Ensemble model. Fallback to heuristic on failure.

**Architecture:**
```
PROPS:  LSTM (13 models) → ai_score adjustment ±3.0
GAMES:  XGBoost Ensemble → hit probability → confidence adjustment
```

**LSTM Models (13 weight files in `/models/`):**
| Sport | Stats | Files |
|-------|-------|-------|
| NBA | points, assists, rebounds | 3 |
| NFL | passing_yards, rushing_yards, receiving_yards | 3 |
| MLB | hits, total_bases, strikeouts | 3 |
| NHL | points, shots | 2 |
| NCAAB | points, rebounds | 2 |

**Key Files:**
```
ml_integration.py           # Core ML integration (725 LOC)
├── PropLSTMManager         # Lazy-loads LSTM models on demand
├── EnsembleModelManager    # XGBoost hit predictor for games
├── get_lstm_ai_score()     # Props: returns (ai_score, metadata)
└── get_ensemble_ai_score() # Games: returns (ai_score, metadata)

scripts/train_ensemble.py   # XGBoost training script (413 LOC)
daily_scheduler.py          # Retrain jobs (lines 458-476)
```

**Scheduler Jobs:**
| Job | Schedule | Threshold |
|-----|----------|-----------|
| LSTM Retrain | Sundays 4:00 AM ET | 500+ samples |
| Ensemble Retrain | Daily 6:45 AM ET | 100+ graded picks |

**Fallback Behavior:**
- If LSTM unavailable → Uses heuristic `base_ai = 5.0` with rule-based boosts
- If Ensemble unavailable → Uses heuristic game scoring
- All failures are SILENT to user (logged internally)

**Context Data Wiring (Pillars 13-15 → LSTM):**
```python
# live_data_router.py lines 3030-3054
game_data={
    "def_rank": DefensiveRankService.get_rank(...),   # Pillar 13
    "pace": PaceVectorService.get_game_pace(...),     # Pillar 14
    "vacuum": UsageVacuumService.calculate_vacuum(...) # Pillar 15
}
```

**Verification:**
```bash
# Check ML status
curl /live/ml/status -H "X-API-Key: KEY"
# Should show: lstm.loaded_count > 0, ensemble.available: true/false

# Check LSTM in pick metadata
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | jq '.props.picks[0].lstm_metadata'
```

---

### INVARIANT 15: GLITCH Protocol (6 Signals)

**RULE:** All 6 GLITCH signals must be wired into `get_glitch_aggregate()` and called from scoring.

**GLITCH Protocol Signals:**
| # | Signal | Weight | Source | Triggered When |
|---|--------|--------|--------|----------------|
| 1 | Chrome Resonance | 0.25 | Player birthday + game date | Chromatic interval is Perfect 5th/4th/Unison |
| 2 | Void Moon | 0.20 | Astronomical calculation | Moon is void-of-course |
| 3 | Noosphere Velocity | 0.15 | SerpAPI (Google Trends) | Search velocity > ±0.2 |
| 4 | Hurst Exponent | 0.25 | Line history analysis | H ≠ 0.5 (trending/mean-reverting) |
| 5 | Kp-Index | 0.25 | NOAA Space Weather API | Geomagnetic storm (Kp ≥ 5) |
| 6 | Benford Anomaly | 0.10 | Line value distribution | Chi-squared deviation ≥ 0.25 |

**v17.6 Benford Requirement:** Multi-book aggregation provides 10+ values (was dormant with only 3 values before).

**Key Files:**
```
esoteric_engine.py
├── calculate_chrome_resonance()    # Line 896
├── calculate_void_moon()           # Line 145
├── calculate_hurst_exponent()      # Line 313
├── get_schumann_frequency()        # Line 379 (Kp fallback)
└── get_glitch_aggregate()          # Line 1002 - COMBINES ALL 6

alt_data_sources/
├── noaa.py                         # NOAA Kp-Index client (FREE API)
│   ├── fetch_kp_index_live()       # 3-hour cache
│   └── get_kp_betting_signal()     # Betting interpretation
├── serpapi.py                      # SerpAPI client (already paid)
│   ├── get_search_trend()          # Google search volume
│   ├── get_team_buzz()             # Team comparison
│   └── get_noosphere_data()        # Hive mind velocity
└── __init__.py                     # Exports all signals

signals/math_glitch.py
└── check_benford_anomaly()         # First-digit distribution
```

**Integration Point (live_data_router.py lines 3321-3375):**
```python
# GLITCH signals adjust esoteric_score by ±0.75 max
glitch_result = get_glitch_aggregate(
    birth_date_str=player_birthday,
    game_date=game_date,
    game_time=game_datetime,
    line_history=line_history,
    value_for_benford=line_values,
    primary_value=prop_line
)
glitch_adjustment = (glitch_result["glitch_score_10"] - 5.0) * 0.15
esoteric_raw += glitch_adjustment
```

**API Configuration:**
| API | Env Var | Cost | Cache TTL |
|-----|---------|------|-----------|
| NOAA Space Weather | None (public) | FREE | 3 hours |
| SerpAPI | `SERPAPI_KEY` | Already paid | 30 minutes |

**Verification:**
```bash
# Check GLITCH in esoteric breakdown
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '.props.picks[0].esoteric_reasons'
# Should include: "GLITCH: chrome_resonance", "GLITCH: void_moon_warning", etc.

# Check alt_data_sources status
curl /live/debug/integrations -H "X-API-Key: KEY" | jq '.noaa, .serpapi'
```

---

### INVARIANT 16: 18-Pillar Scoring System (v20.0 - ALL PILLARS ACTIVE)

**RULE:** All 18 pillars must contribute to scoring. No pillar may be orphaned.

**Pillar Map:**
| # | Pillar | Engine | Weight | Implementation | Status |
|---|--------|--------|--------|----------------|--------|
| 1-8 | 8 AI Models | AI (15%) | Direct | `advanced_ml_backend.py` | ✅ |
| 9 | Sharp Money (RLM) | Research (20%) | Direct | Playbook API splits | ✅ |
| 10 | Line Variance | Research | Direct | Cross-book comparison | ✅ |
| 11 | Public Fade | Research | Direct | Ticket-money divergence | ✅ |
| 12 | Splits Base | Research | Direct | Real data presence boost | ✅ |
| 13 | Defensive Rank | Context (30%) | 50% | `DefensiveRankService` | ✅ Real values |
| 14 | Pace Vector | Context | 30% | `PaceVectorService` | ✅ Real values |
| 15 | Usage Vacuum | Context | 20% | `UsageVacuumService` + injuries | ✅ Real values |
| 16 | Officials | Research | Adjustment | `OfficialsService` + `officials_data.py` | ✅ ACTIVE (v17.8) |
| 17 | Park Factors | Esoteric | MLB only | `ParkFactorService` | ✅ |
| 18 | Live Context | Multiple | Adjustment | `alt_data_sources/live_signals.py` | ✅ ACTIVE (v20.0) |

**v20.0 Completion Status (Feb 2026):**
- ✅ **Pillars 13-15 now use REAL DATA** (not hardcoded defaults)
- ✅ **Injuries fetched in parallel** with props and game odds
- ✅ **Context calculation runs for ALL pick types** (PROP, GAME, SHARP)
- ✅ **Pillar 16 (Officials)** - ACTIVE with referee tendency database (v17.8)
  - 25 NBA referees with over_tendency, foul_rate, home_bias
  - 17 NFL referee crews with flag_rate, over_tendency
  - 15 NHL referees with penalty_rate, over_tendency
  - Adjustment range: -0.5 to +0.5 on research score
- ✅ **Pillar 18 (Live Context)** - ACTIVE with score momentum + line movement (v20.0)
  - Score momentum: Blowout/comeback detection (±0.25)
  - Live line movement: Sharp action detection (±0.30)
  - Combined cap: ±0.50
  - Only applies when game_status == "LIVE"

**Data Flow (v17.8):**
```
_best_bets_inner()
  │
  ├── Parallel Fetch (asyncio.gather)
  │     ├── get_props(sport)
  │     ├── fetch_game_odds()
  │     └── get_injuries(sport)
  │
  ├── Build _injuries_by_team lookup (handles Playbook + ESPN formats)
  ├── Build _officials_by_game lookup (ESPN Hidden API)
  │
  └── calculate_pick_score() [for ALL pick types]
        ├── Pillar 13: DefensiveRankService.get_rank()
        ├── Pillar 14: PaceVectorService.get_game_pace()
        ├── Pillar 15: UsageVacuumService.calculate_vacuum(_injuries_by_team)
        ├── Pillar 16: OfficialsService.get_officials_adjustment() ← v17.8
        └── Pillar 17: ParkFactorService (MLB only)
```

**Base Engine Weights (scoring_contract.py):**
```python
ENGINE_WEIGHTS = {
    "ai": 0.25,        # Pillars 1-8
    "research": 0.35,  # Pillars 9-12, 16
    "esoteric": 0.15,  # Pillar 17 + GLITCH (v20.19: reduced from 0.20)
    "jarvis": 0.25,    # Gematria triggers (v20.19: increased from 0.20)
}

CONTEXT_MODIFIER_CAP = 0.35  # Context is a bounded modifier, not a weighted engine
```

**Verification - Check REAL Values (Not Defaults):**
```bash
# 1. Check context layer has REAL values (not defaults)
# Default def_rank=16, pace=100.0, vacuum=0.0 - if ALL picks show these, it's broken
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | jq '[.game_picks.picks[0:3][] | {
  matchup: .matchup,
  def_rank: .context_layer.def_rank,
  pace: .context_layer.pace,
  vacuum: .context_layer.vacuum,
  context_score: .context_score,
  context_modifier: .context_modifier
}]'
# SHOULD show varying def_rank (1-30), varying pace (94-104), context_score + modifier vary

# 2. Check injuries are loaded
curl /live/injuries/NBA -H "X-API-Key: KEY" | jq '{source: .source, count: .count, teams: [.data[].teamName]}'
# SHOULD show source: "playbook", count > 0, teams list

# 3. Check all engines in pick output
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | jq '.game_picks.picks[0] | {
  ai: .ai_score,
  research: .research_score,
  esoteric: .esoteric_score,
  jarvis: .jarvis_score,
  context_modifier: .context_modifier,
  officials: .context_layer.officials_adjustment,
  park: .context_layer.park_adjustment
}'
```

**Key Files (v17.8):**
| File | Lines | Purpose |
|------|-------|---------|
| `live_data_router.py` | 4172-4227 | Parallel fetch including injuries |
| `live_data_router.py` | 4201-4227 | Build _injuries_by_team (Playbook + ESPN format) |
| `live_data_router.py` | 4055-4106 | Pillar 16: Officials tendency integration (v17.8) |
| `live_data_router.py` | 3139-3183 | Context calculation for ALL pick types |
| `context_layer.py` | 413-472 | DefensiveRankService |
| `context_layer.py` | 543-635 | PaceVectorService |
| `context_layer.py` | 637-706 | UsageVacuumService |
| `context_layer.py` | 713-763 | ParkFactorService |
| `context_layer.py` | 2176-2248 | OfficialsService.get_officials_adjustment() (v17.8) |
| `officials_data.py` | All | Referee tendency database (25 NBA, 17 NFL, 15 NHL refs) |

---

### INVARIANT 17: Harmonic Convergence (+1.5 Boost)

**RULE:** When Research ≥ 8.0 AND Esoteric ≥ 8.0, add +1.5 "Golden Boost"

**Implementation (live_data_router.py lines 3424-3435):**
```python
HARMONIC_THRESHOLD = 8.0
HARMONIC_BOOST = 1.5

if research_score >= HARMONIC_THRESHOLD and esoteric_score >= HARMONIC_THRESHOLD:
    confluence = {
        "level": "HARMONIC_CONVERGENCE",
        "boost": confluence.get("boost", 0) + HARMONIC_BOOST,
        ...
    }
```

**Rationale:** When both analytical (Research/Math) and intuitive (Esoteric/Magic) signals strongly agree, this represents exceptional alignment worthy of extra confidence.

---

### INVARIANT 18: Secret Redaction (Log Sanitizer)

**RULE:** API keys, tokens, and auth headers MUST NEVER appear in logs.

**Implementation:** `core/log_sanitizer.py` (NEW - Feb 2026)

**Sensitive Data Classes:**
| Category | Examples | Redaction |
|----------|----------|-----------|
| Headers | `X-API-Key`, `Authorization`, `Cookie` | → `[REDACTED]` |
| Query Params | `apiKey`, `api_key`, `token`, `secret` | → `[REDACTED]` |
| Env Var Values | `ODDS_API_KEY`, `PLAYBOOK_API_KEY`, etc. | → `[REDACTED]` |
| Token Patterns | Bearer tokens, JWTs, long alphanumeric | → `[REDACTED]` |

**Key Functions:**
```python
from core.log_sanitizer import (
    sanitize_headers,    # Dict[str, Any] → Dict[str, str] with sensitive values redacted
    sanitize_dict,       # Recursively redacts api_key, token, etc.
    sanitize_url,        # Redacts ?apiKey=xxx query params
    sanitize,            # Text sanitization for Bearer/JWT/alphanumeric
    safe_log_request,    # Safe HTTP request logging
    safe_log_response,   # Safe HTTP response logging
)
```

**Files Updated:**
| File | Line | Change |
|------|------|--------|
| `playbook_api.py` | 211 | Uses `sanitize_dict(query_params)` |
| `live_data_router.py` | 6653 | Uses `params={}` not `?apiKey=` in URL |
| `legacy/services/odds_api_service.py` | 30 | Changed `key[:8]...` to `[REDACTED]` |

**NEVER:**
- Log `request.headers` without sanitizing
- Construct URLs with `?apiKey=VALUE` (use `params={}` dict)
- Log partial keys like `key[:8]...` (reconnaissance risk)
- Print exception messages that might contain secrets

**Tests:** `tests/test_log_sanitizer.py` (20 tests)

**Verification:**
```bash
# Run sanitizer tests
pytest tests/test_log_sanitizer.py -v

# Check no secrets in recent logs
railway logs | grep -i "apikey\|authorization\|bearer" | head -5
# Should return empty or only "[REDACTED]"
```

---

### INVARIANT 19: Demo Data Hard Gate

**RULE:** Sample/demo/fallback data ONLY returned when explicitly enabled.

**Implementation:** Gated behind `ENABLE_DEMO=true` env var OR `mode=demo` query param.

**What's Gated:**
| Location | Demo Data | Gate |
|----------|-----------|------|
| `legacy/services/odds_api_service.py` | Lakers/Warriors demo game | `ENABLE_DEMO=true` |
| `main.py:/debug/seed-pick` | Fake LeBron/LAL pick | `mode=demo` or `ENABLE_DEMO` |
| `main.py:/debug/seed-pick-and-grade` | Fake LeBron/LAL pick | `mode=demo` or `ENABLE_DEMO` |
| `main.py:/debug/e2e-proof` | Test pick with `e2e_` prefix | `mode=demo` or `ENABLE_DEMO` |
| `live_data_router.py:_DEPRECATED_*` | Sample matchups | `ENABLE_DEMO=true` |

**Behavior When Live Data Unavailable:**
| Scenario | Before | After |
|----------|--------|-------|
| No `ODDS_API_KEY` | Demo Lakers/Warriors game | Empty `[]` |
| API returns error | Demo fallback data | Empty `[]` + error logged |
| No games scheduled | Demo data | Empty `[]` |

**Endpoint Response When Gated:**
```json
{
  "error": "Demo data gated",
  "detail": "Set mode=demo query param or ENABLE_DEMO=true env var"
}
```
HTTP 403 Forbidden

**NEVER:**
- Return sample picks without explicit demo flag
- Use hardcoded player data (LeBron, Mahomes) in production responses
- Fall back to demo on API failure (return empty instead)

**Tests:** `tests/test_no_demo_data.py` (12 tests)

**Verification:**
```bash
# Debug endpoints should be blocked without flag
curl -X POST /debug/seed-pick -H "X-Admin-Key: KEY"
# Should return 403 "Demo data gated"

# With flag should work
curl -X POST "/debug/seed-pick?mode=demo" -H "X-Admin-Key: KEY"
# Should return seeded pick

# Best-bets should never have sample data
curl /live/best-bets/NHL -H "X-API-Key: KEY" | jq '.props.picks[].matchup'
# Should never show "Lakers @ Celtics" or other hardcoded matchups
```

---

### INVARIANT 20: MSRF Confluence Boost (v17.2)

**RULE:** MSRF (Mathematical Sequence Resonance Framework) calculates turn date resonance and adds confluence boost when mathematically significant.

**Implementation:** `signals/msrf_resonance.py` → `get_msrf_confluence_boost()`

**Mathematical Constants:**
| Constant | Value | Significance |
|----------|-------|--------------|
| `OPH_PI` | 3.14159... | Circle constant, cycles |
| `OPH_PHI` | 1.618... | Golden Ratio, natural growth |
| `OPH_CRV` | 2.618... | Phi² (curved growth) |
| `OPH_HEP` | 7.0 | Heptagon (7-fold symmetry) |

**MSRF Number Lists:**
| List | Count | Examples |
|------|-------|----------|
| `MSRF_NORMAL` | ~250 | 666, 777, 888, 2178 |
| `MSRF_IMPORTANT` | 36 | 144, 432, 720, 1080, 2520 |
| `MSRF_VORTEX` | 19 | 21.7, 144.3, 217.8 |

**16 Operations:** Transform time intervals (Y1, Y2, Y3) between last 3 significant dates using constants, then project forward to check if game date aligns.

**Boost Levels (added to confluence):**
| Level | Points Required | Boost | Triggered |
|-------|----------------|-------|-----------|
| EXTREME_RESONANCE | ≥ 8 | +1.0 | ✅ |
| HIGH_RESONANCE | ≥ 5 | +0.5 | ✅ |
| MODERATE_RESONANCE | ≥ 3 | +0.25 | ✅ |
| MILD_RESONANCE | ≥ 1 | +0.0 | ❌ |
| NO_RESONANCE | 0 | +0.0 | ❌ |

**Data Sources:**
1. **Stored Predictions:** High-confidence hits from `/data/grader/predictions.jsonl` (min_score ≥ 7.5)
2. **BallDontLie (NBA only):** Player standout games (points ≥ 150% of average)

**Integration Point:** `live_data_router.py:3567-3591` (after Harmonic Convergence, before confluence_boost extraction)

**Output Fields (debug mode):**
```python
{
    "msrf_boost": float,        # 0.0, 0.25, 0.5, or 1.0
    "msrf_metadata": {
        "source": "msrf_live",
        "level": "HIGH_RESONANCE",
        "points": 5.5,
        "matching_operations": [...],
        "significant_dates_used": ["2025-11-15", "2025-12-24", "2026-01-15"]
    }
}
```

**Feature Flag:** `MSRF_ENABLED` env var (default: `true`)

**Verification:**
```bash
# Check MSRF in pick output
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '.props.picks[0] | {msrf_boost, msrf_level: .msrf_metadata.level, msrf_points: .msrf_metadata.points}'

# Check MSRF in esoteric_reasons
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '.props.picks[0].esoteric_reasons | map(select(startswith("MSRF")))'
```

**NEVER:**
- Add MSRF boost without sufficient significant dates (need 3+)
- Call MSRF for indoor sports without player/team context
- Modify MSRF number lists without understanding sacred number theory

---

### INVARIANT 21: Dual-Use Functions Must Return Dicts (v17.2)

**RULE:** Functions that are BOTH endpoint handlers AND called internally MUST return dicts, not JSONResponse.

**Why:** FastAPI auto-serializes dicts to JSON for endpoint responses. When a function returns `JSONResponse`, internal callers cannot use `.get()` or other dict methods on the return value.

**Affected Functions (live_data_router.py):**
| Function | Line | Endpoint | Internal Callers |
|----------|------|----------|------------------|
| `get_sharp_money()` | 1758 | `/live/sharp/{sport}` | `_best_bets_inner()` line 2580 |
| `get_splits()` | 1992 | `/live/splits/{sport}` | `_best_bets_inner()`, dashboard |
| `get_lines()` | 2100+ | `/live/lines/{sport}` | dashboard |
| `get_injuries()` | 2200+ | `/live/injuries/{sport}` | dashboard |

**Pattern to Avoid:**
```python
@router.get("/endpoint")
async def my_function():
    result = {"data": [...]}
    return JSONResponse(result)  # ❌ WRONG - breaks internal callers
```

**Correct Pattern:**
```python
@router.get("/endpoint")
async def my_function():
    result = {"data": [...]}
    return result  # ✅ FastAPI auto-serializes for endpoints, internal callers get dict
```

**When to Use JSONResponse:**
- Custom status codes: `return JSONResponse(content=data, status_code=201)`
- Custom headers: `return JSONResponse(content=data, headers={"X-Custom": "value"})`
- Custom media type: `return JSONResponse(content=data, media_type="application/xml")`

**Verification:**
```bash
# Find all JSONResponse returns in endpoint handlers
grep -n "return JSONResponse" live_data_router.py | head -20

# Check if those functions are called internally
# For each function, grep for calls outside the decorator
```

**Test All Sports After Changes:**
```bash
# After ANY change to dual-use functions, test ALL sports:
for sport in NBA NHL NFL MLB NCAAB; do
  echo "Testing $sport..."
  curl -s "/live/best-bets/$sport" -H "X-API-Key: KEY" | jq '{sport: .sport, picks: (.game_picks.count + .props.count)}'
done
```

**Fixed in:** Commit `d7279e9` (Feb 2026)

---

### INVARIANT 22: ESPN Data Integration (v17.3)

**RULE:** ESPN data is a FREE secondary source for cross-validation and supplementation, NOT a replacement.

**Data Usage Hierarchy:**
| Data Type | Primary Source | ESPN Role | Integration |
|-----------|---------------|-----------|-------------|
| **Odds** | Odds API | Cross-validation | +0.25-0.5 research boost when confirmed |
| **Injuries** | Playbook API | Supplement | Merge into `_injuries_by_team` |
| **Officials** | ESPN (primary) | Primary for Pillar 16 | `_officials_by_game` lookup |
| **Weather** | Weather API | Fallback | Only for MLB/NFL when primary fails |
| **Venue** | ESPN | Supplementary | Indoor/outdoor, grass/turf info |

**Implementation Requirements:**
1. **Batch Parallel Fetching** - NEVER fetch ESPN data synchronously in scoring loop
2. **Graceful Fallback** - ESPN data unavailable → continue without it (no errors)
3. **Team Name Normalization** - Case-insensitive matching, handle accents
4. **Closure Access** - Scoring function accesses via closure from `_best_bets_inner()`

**Lookup Variables (defined in `_best_bets_inner()`):**
```python
_espn_events_by_teams = {}    # (home_lower, away_lower) → event_id
_officials_by_game = {}       # (home_lower, away_lower) → officials dict
_espn_odds_by_game = {}       # (home_lower, away_lower) → odds dict
_espn_injuries_supplement = {} # team_name → list of injuries
_espn_venue_by_game = {}      # (home_lower, away_lower) → venue dict (MLB/NFL only)
```

**ESPN Cache TTL:** 5 minutes (per-request cache, not global)

**Sport Support:**
| Sport | Officials | Odds | Injuries | Venue/Weather |
|-------|-----------|------|----------|---------------|
| NBA | ✅ | ✅ | ✅ | ❌ (indoor) |
| NFL | ✅ | ✅ | ✅ | ✅ |
| MLB | ✅ | ✅ | ✅ | ✅ |
| NHL | ✅ | ✅ | ✅ | ❌ (indoor) |
| NCAAB | ✅ | ✅ | ✅ | ❌ (indoor) |

**Verification:**
```bash
# Check ESPN integration active
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '{espn_events: .debug.espn_events_mapped, officials: .debug.officials_available, espn_odds: .debug.espn_odds_count}'

# Verify cross-validation in research_reasons
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '.game_picks.picks[0].research_reasons | map(select(contains("ESPN")))'
```

**NEVER:**
- Replace Odds API with ESPN odds (ESPN is secondary validation only)
- Fetch ESPN data inside the scoring loop (batch before scoring)
- Skip team name normalization (causes lookup misses)
- Assume ESPN has all data (refs assigned late, not all games covered)

---

### INVARIANT 23: SERP Intelligence Integration (v17.4)

**RULE:** SERP betting intelligence provides search-trend signals that boost engine scores. Default is LIVE MODE (not shadow mode).

**Implementation:**
- `core/serp_guardrails.py` - Central config, quota tracking, boost caps, shadow mode control
- `alt_data_sources/serp_intelligence.py` - 5 signal detectors mapped to 4 base engines
- `alt_data_sources/serpapi.py` - SerpAPI client with cache and timeout from guardrails

**Configuration (serp_guardrails.py):**
```python
SERP_SHADOW_MODE = False      # LIVE MODE by default (boosts applied)
SERP_INTEL_ENABLED = True     # Feature flag
SERP_PROPS_ENABLED = False    # v20.9: Props SERP disabled (saves ~60% daily quota)
SERP_DAILY_QUOTA = 166        # 5000/30 days
SERP_MONTHLY_QUOTA = 5000     # Monthly API calls
SERP_TIMEOUT = 2.0            # Strict 2s timeout
SERP_CACHE_TTL = 5400         # 90 minutes cache
```

**Boost Caps (Code-Enforced):**
| Engine | Max Boost | Signal Type |
|--------|-----------|-------------|
| AI | 0.8 | Silent Spike (high search + low news) |
| Research | 1.3 | Sharp Chatter (RLM, sharp money mentions) |
| Esoteric | 0.6 | Noosphere (search velocity momentum) |
| Jarvis | 0.7 | Narrative (revenge, rivalry, playoff) |
| Context | 0.9 | Situational (B2B, rest, travel) |
| **TOTAL** | **4.3** | Combined max across all engines |

**Signal → Engine Mapping:**
```
detect_silent_spike()   → AI engine      (high search + low news = insider activity)
detect_sharp_chatter()  → Research engine (sharp money, RLM mentions)
detect_narrative()      → Jarvis engine   (revenge games, rivalries)
detect_situational()    → Context modifier (B2B, rest advantage, travel)
detect_noosphere()      → Esoteric engine (search trend velocity)
```

**Integration Point (live_data_router.py:3715-3750):**
```python
serp_intel = get_serp_betting_intelligence(sport, home_team, away_team, pick_side)
if serp_intel.get("available"):
    serp_boosts = serp_intel.get("boosts", {})
    serp_boost_total = sum(serp_boosts.values())
    confluence["boost"] += serp_boost_total  # Added to confluence
```

**Required Pick Output Fields:**
```python
{
    "serp_boost": float,           # Total SERP boost applied
    "serp_reasons": List[str],     # ["SERP[context]: Situational: b2b", ...]
    "serp_shadow_mode": bool,      # False when live
}
```

**Debug Output (debug.serp):**
```json
{
  "available": true,
  "shadow_mode": false,
  "mode": "live",
  "status": {
    "enabled": true,
    "quota": {"daily_remaining": 80, "monthly_remaining": 4800},
    "cache": {"hits": 1000, "misses": 150, "hit_rate_pct": 87.0}
  }
}
```

**Verification:**
```bash
# Check SERP status
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | jq '.debug.serp'
# Expected: available=true, shadow_mode=false, mode="live"

# Check boosts on picks
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '.game_picks.picks[0] | {serp_boost, serp_reasons}'
# Expected: serp_boost > 0 when signals fire

# Test all sports
for sport in NBA NHL NFL MLB NCAAB; do
  echo "=== $sport ==="
  curl -s "/live/best-bets/$sport?debug=1" -H "X-API-Key: KEY" | \
    jq '{sport: .sport, serp_mode: .debug.serp.mode}'
done
```

**NEVER:**
- Set `SERP_SHADOW_MODE=True` in production (disables all boosts)
- Skip quota checks before API calls
- Exceed boost caps (enforced in `cap_boost()` and `cap_total_boost()`)
- Make SERP calls inside scoring loop without try/except
- Forget to add both `SERPAPI_KEY` and `SERP_API_KEY` to env var checks

---

### INVARIANT 24: Trap Learning Loop (v19.0)

**RULE:** Pre-game traps define conditional rules that automatically adjust engine weights based on post-game results.

**Implementation:**
- `trap_learning_loop.py` - Core module (~800 lines): TrapDefinition, TrapEvaluation, TrapLearningLoop
- `trap_router.py` - API endpoints (~400 lines): CRUD for traps, dry-run, history
- `daily_scheduler.py` - Evaluation job at 6:15 AM ET (after grading at 6:00 AM)

**Storage (JSONL on Railway volume):**
```
/data/trap_learning/
├── traps.jsonl              # Trap definitions
├── evaluations.jsonl        # Evaluation history (condition_met, action_taken)
└── adjustments.jsonl        # Weight change audit trail
```

**Supported Engines (5 total):**
| Engine | Parameters | Range |
|--------|------------|-------|
| **research** | `weight_public_fade`, `weight_sharp_money`, `weight_line_variance`, `splits_base` | 0.0-3.0 |
| **esoteric** | `weight_gematria`, `weight_astro`, `weight_fib`, `weight_vortex`, `weight_daily_edge`, `weight_glitch` | 0.0-1.0 |
| **jarvis** | `trigger_boost_2178`, `trigger_boost_201`, `trigger_boost_33`, `trigger_boost_93`, `trigger_boost_322`, `trigger_boost_666`, `trigger_boost_1656`, `trigger_boost_552`, `trigger_boost_138`, `baseline_score` | 0.0-20.0 |
| **context** | `weight_def_rank`, `weight_pace`, `weight_vacuum` | 0.1-0.7 |
| **ai** | `lstm_weight`, `ensemble_weight` | 0.1-0.4 |

**Safety Guards (Code-Enforced):**
| Guard | Value | Purpose |
|-------|-------|---------|
| `MAX_SINGLE_ADJUSTMENT` | 5% (0.05) | Prevent large swings |
| `MAX_CUMULATIVE_ADJUSTMENT` | 15% (0.15) | Lifetime cap per trap |
| `cooldown_hours` | 24 (default) | Min time between triggers |
| `max_triggers_per_week` | 3 (default) | Rate limiting |
| `DECAY_FACTOR` | 0.7 | Each trigger = 70% of previous |

**Condition Language:**
```json
{
    "operator": "AND",
    "conditions": [
        {"field": "result", "comparator": "==", "value": "win"},
        {"field": "margin", "comparator": ">=", "value": 20}
    ]
}
```

**Supported Condition Fields:**
| Category | Fields |
|----------|--------|
| **Outcome** | `result`, `margin`, `total_points`, `spread_result`, `over_under_result` |
| **Date** | `day_number`, `numerology_day`, `day_of_week`, `month` |
| **Gematria** | `name_sum_cipher`, `city_sum_cipher`, `combined_cipher` |
| **Scores** | `ai_score_was`, `research_score_was`, `jarvis_score_was`, `final_score_was` |

**API Endpoints:**
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/live/traps/` | POST | Create new trap |
| `/live/traps/` | GET | List traps (filter by sport, status) |
| `/live/traps/{trap_id}` | GET | Get trap details + evaluation history |
| `/live/traps/{trap_id}/status` | PUT | Update status (ACTIVE, PAUSED, RETIRED) |
| `/live/traps/evaluate/dry-run` | POST | Test trap without applying |
| `/live/traps/history/{engine}` | GET | Adjustment history by engine |
| `/live/traps/stats/summary` | GET | Aggregate statistics |

**Example Traps:**
```json
// Trap 1: Dallas Blowout → Reduce Public Fade weight
{
    "trap_id": "dallas-blowout-public-fade",
    "name": "Dallas Blowout Reduces Public Fade Weight",
    "sport": "NBA",
    "team": "Dallas Mavericks",
    "condition": {
        "operator": "AND",
        "conditions": [
            {"field": "result", "comparator": "==", "value": "win"},
            {"field": "margin", "comparator": ">=", "value": 20}
        ]
    },
    "action": {"type": "WEIGHT_ADJUST", "delta": -0.01},
    "target_engine": "research",
    "target_parameter": "weight_public_fade"
}

// Trap 2: Rangers Numerology → Trigger cipher audit
{
    "trap_id": "rangers-1day-cipher-audit",
    "name": "Rangers Day 1 Loss Triggers Cipher Audit",
    "sport": "MLB",
    "team": "Texas Rangers",
    "condition": {
        "operator": "AND",
        "conditions": [
            {"field": "result", "comparator": "==", "value": "loss"},
            {"field": "numerology_day", "comparator": "==", "value": 1}
        ]
    },
    "action": {"type": "AUDIT_TRIGGER", "audit_type": "cipher_comparison"},
    "target_engine": "jarvis",
    "target_parameter": "name_vs_city_cipher"
}

// Trap 3: Phoenix 1656 Cycle → Reduce trigger boost on loss
{
    "trap_id": "phoenix-1656-validation",
    "name": "1656 Trigger Loss Adjustment",
    "sport": "ALL",
    "condition": {
        "operator": "AND",
        "conditions": [
            {"field": "combined_cipher", "comparator": "==", "value": 1656},
            {"field": "jarvis_score_was", "comparator": ">=", "value": 7.0},
            {"field": "result", "comparator": "==", "value": "loss"}
        ]
    },
    "action": {"type": "WEIGHT_ADJUST", "delta": -0.5},
    "target_engine": "jarvis",
    "target_parameter": "trigger_boost_1656"
}
```

**Scheduler Integration (daily_scheduler.py):**
```python
# v19.0: Post-game trap evaluation (daily at 6:15 AM ET, after grading)
self.scheduler.add_job(
    self._run_trap_evaluation,
    CronTrigger(hour=6, minute=15, timezone="America/New_York"),
    id="trap_evaluation",
    name="Post-Game Trap Evaluation"
)
```

**Key Functions:**
```python
from trap_learning_loop import (
    get_trap_loop,           # Singleton access
    TrapLearningLoop,        # Main class
    TrapDefinition,          # Dataclass for trap config
    TrapEvaluation,          # Dataclass for evaluation result
    enrich_game_result,      # Add numerology/gematria fields
    calculate_numerology_day,# Reduce date to single digit
    calculate_team_gematria, # Team name cipher values
    SUPPORTED_ENGINES,       # Engine→parameter→range mapping
    CONDITION_FIELDS,        # Valid condition fields
)
```

**Verification:**
```bash
# 1. List active traps
curl /live/traps/ -H "X-API-Key: KEY"

# 2. Create a test trap
curl -X POST /live/traps/ -H "X-API-Key: KEY" -H "Content-Type: application/json" -d '{
  "name": "Test Trap",
  "sport": "NBA",
  "condition": {"operator": "AND", "conditions": [
    {"field": "margin", "comparator": ">=", "value": 10}
  ]},
  "action": {"type": "WEIGHT_ADJUST", "delta": -0.01},
  "target_engine": "research",
  "target_parameter": "weight_public_fade"
}'

# 3. Dry-run evaluation
curl -X POST /live/traps/evaluate/dry-run -H "X-API-Key: KEY" -H "Content-Type: application/json" -d '{
  "trap_id": "test-trap",
  "game_result": {"margin": 25, "result": "win"}
}'

# 4. Check adjustment history
curl /live/traps/history/research -H "X-API-Key: KEY"

# 5. Get summary stats
curl /live/traps/stats/summary -H "X-API-Key: KEY"

# 6. Check scheduler job registered
curl /live/scheduler/status -H "X-API-Key: KEY" | jq '.jobs[] | select(.id == "trap_evaluation")'
```

**NEVER:**
- Exceed `MAX_SINGLE_ADJUSTMENT` (5%) per trigger
- Bypass cooldown period (24h default)
- Create traps targeting invalid engine/parameter combinations
- Skip safety validation in `_validate_adjustment_safety()`
- Modify `SUPPORTED_ENGINES` without updating trap_router validation
- Apply adjustments without logging to `adjustments.jsonl`

---

### INVARIANT 25: Complete Learning System (v19.1)

**RULE:** Every signal contribution MUST be tracked for learning. AutoGrader and Trap Learning Loop MUST NOT conflict.

**Philosophy:** "Competition + variance. Learning loop baked in via fused upgrades."

**Implementation:**
- `auto_grader.py` - Statistical/reactive learning (daily 6:00 AM ET)
- `trap_learning_loop.py` - Hypothesis-driven/proactive learning (daily 6:15 AM ET)
- `live_data_router.py` - Pick persistence with full signal tracking

**Two Learning Systems (Complementary):**
| System | Type | Schedule | What It Learns |
|--------|------|----------|----------------|
| **AutoGrader** | Statistical/Reactive | 6:00 AM ET | Bias from prediction errors → adjusts context modifier calibration |
| **Trap Learning Loop** | Hypothesis/Proactive | 6:15 AM ET | Conditional rules → adjusts research/esoteric/jarvis weights |

**Signal Tracking Coverage (28 signals - 100% coverage):**
| Category | Count | Signals | Learning System |
|----------|-------|---------|-----------------|
| Context Layer | 5 | defense, pace, vacuum, lstm, officials | AutoGrader |
| Research Engine | 3 | sharp_money, public_fade, line_variance | AutoGrader + Traps |
| GLITCH Protocol | 6 | chrome_resonance, void_moon, noosphere, hurst, kp_index, benford | AutoGrader |
| Esoteric Engine | 14 | numerology, astro, fib_alignment, fib_retracement, vortex, daily_edge, biorhythms, gann, founders_echo, lunar, mercury, rivalry, streak, solar | AutoGrader + Traps |
| **Total** | **28** | All signals tracked | Full coverage |

**PredictionRecord Fields (auto_grader.py lines 52-95):**
```python
@dataclass
class PredictionRecord:
    # Core
    prediction_id: str
    sport: str
    player_name: str
    stat_type: str
    predicted_value: float
    actual_value: Optional[float] = None
    line: Optional[float] = None
    timestamp: str = ""

    # Pick type (for differentiated learning)
    pick_type: str = ""  # PROP, SPREAD, TOTAL, MONEYLINE, SHARP

    # Context Layer (Pillars 13-15)
    defense_adjustment: float = 0.0
    pace_adjustment: float = 0.0
    vacuum_adjustment: float = 0.0
    lstm_adjustment: float = 0.0
    officials_adjustment: float = 0.0

    # Research Engine Signals (GAP 1 fix)
    sharp_money_adjustment: float = 0.0
    public_fade_adjustment: float = 0.0
    line_variance_adjustment: float = 0.0

    # GLITCH Protocol Signals (GAP 2 fix)
    glitch_signals: Optional[Dict[str, float]] = None  # chrome_resonance, void_moon, etc.

    # Esoteric Contributions (GAP 2 fix)
    esoteric_contributions: Optional[Dict[str, float]] = None  # numerology, astro, etc.

    # Outcome
    hit: Optional[bool] = None
    error: Optional[float] = None
```

**Bias Calculation (auto_grader.py calculate_bias()):**
- Calculates bias for ALL 28 signals (not just 5)
- Supports confidence decay (70% per day - older picks weighted less)
- Supports pick_type filtering (PROP vs GAME analysis separately)
- Returns `pick_type_breakdown` for differentiated learning

**Trap-AutoGrader Reconciliation:**
- Before AutoGrader adjusts a weight, it checks if Trap Learning Loop recently adjusted it
- 24-hour lookback window for reconciliation
- If trap adjusted in last 24h, AutoGrader SKIPS that parameter
- Prevents conflicting adjustments

**Key Functions:**
```python
from auto_grader import (
    get_grader,                          # Singleton access
    PredictionRecord,                    # Full signal tracking
    AutoGrader.calculate_bias,           # All 28 signals
    AutoGrader.adjust_weights_with_reconciliation,  # Trap-safe adjustment
    AutoGrader.check_trap_reconciliation,  # Check for recent trap adjustments
)

from trap_learning_loop import (
    get_trap_loop,                       # Singleton access
    has_recent_trap_adjustment,          # Check for recent adjustments
    get_recent_parameter_adjustments,    # Get adjustments for engine/parameter
)
```

**Verification:**
```bash
# 1. Check all signal fields in pick output
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | jq '.game_picks.picks[0] | {
  research_breakdown: .research_breakdown,
  glitch_signals: .glitch_signals,
  esoteric_contributions: .esoteric_contributions
}'

# 2. Verify bias calculation includes all signals
curl /live/grader/bias/NBA?days_back=1 -H "X-API-Key: KEY" | jq '.factor_bias | keys'
# Should include: defense, pace, vacuum, lstm, officials, sharp_money, public_fade, line_variance, glitch, esoteric

# 3. Check reconciliation in adjustment result
curl -X POST /live/grader/adjust/NBA -H "X-API-Key: KEY" | jq '.reconciliation'
# Shows which parameters were skipped due to recent trap adjustments

# 4. Check pick_type breakdown
curl /live/grader/bias/NBA?days_back=7 -H "X-API-Key: KEY" | jq '.pick_type_breakdown'
# Shows hit_rate and mean_error by pick type (PROP, SPREAD, TOTAL, etc.)
```

**NEVER:**
- Add a new signal without tracking it in PredictionRecord
- Skip signal persistence in live_data_router.py pick logging
- Let AutoGrader override recent trap adjustments (reconciliation mandatory)
- Calculate bias for only some signals (must be ALL 28)
- Assume pick_type is "GAME" for game picks (actual values: SPREAD, MONEYLINE, TOTAL, SHARP)

**Files Modified (v19.1):**
| File | Lines | Change |
|------|-------|--------|
| `auto_grader.py` | 52-95 | Expanded PredictionRecord with 28 signal fields |
| `auto_grader.py` | 237-290 | Updated log_prediction() to accept new fields |
| `auto_grader.py` | 395-555 | Expanded calculate_bias() for all signals + confidence decay |
| `auto_grader.py` | 556-630 | Updated _calculate_factor_bias() for weighted calculations |
| `auto_grader.py` | 716-825 | Added reconciliation methods |
| `trap_learning_loop.py` | 677-722 | Added has_recent_trap_adjustment(), get_recent_parameter_adjustments() |
| `live_data_router.py` | 4887-4899 | Added glitch_signals, esoteric_contributions to scoring result |
| `live_data_router.py` | 6390-6420 | Updated pick persistence with all signal fields |

### INVARIANT 26: Total Boost Cap (v20.6)

**RULE:** The sum of all additive boosts (confluence + msrf + jason_sim + serp) MUST be capped at `TOTAL_BOOST_CAP` (1.5) before being added to `base_score`. Context modifier is excluded from this cap.

**Why This Exists:**
Individual boost caps (confluence 10.0, msrf 1.0, jason_sim 1.5, serp 4.3) allowed a theoretical max of 16.8 additional points. In practice, picks with mediocre base scores (~6.5) were being inflated to 10.0 through boost stacking, eliminating score differentiation. TOTAL_BOOST_CAP ensures boosts improve good picks but can't rescue bad ones.

**Implementation:**
```python
# In core/scoring_pipeline.py:compute_final_score_option_a()
total_boosts = confluence_boost + msrf_boost + jason_sim_boost + serp_boost
if total_boosts > TOTAL_BOOST_CAP:
    total_boosts = TOTAL_BOOST_CAP
final_score = base_score + context_modifier + total_boosts
final_score = max(0.0, min(10.0, final_score))
```

**Constants (core/scoring_contract.py):**
- `TOTAL_BOOST_CAP = 1.5` — max sum of 4 boosts
- `SERP_BOOST_CAP_TOTAL = 4.3` — individual SERP cap (still applies first)
- `CONFLUENCE_BOOST_CAP = 10.0` — individual confluence cap
- `MSRF_BOOST_CAP = 1.0` — individual MSRF cap
- `JASON_SIM_BOOST_CAP = 1.5` — individual Jason cap

**Test Guard:** `tests/test_option_a_scoring_guard.py:test_compute_final_score_caps_serp_and_clamps_final`

**NEVER:**
- Remove or increase `TOTAL_BOOST_CAP` without analyzing production score distributions
- Include context_modifier in the total boost cap (it's a bounded modifier, not a boost)
- Add a new boost component without including it in the total cap sum

---

## 📚 MASTER FILE INDEX (ML & GLITCH)

### Core ML Files
| File | Purpose | Key Functions |
|------|---------|---------------|
| `ml_integration.py` | ML model management | `get_lstm_ai_score()`, `get_ensemble_ai_score()` |
| `lstm_brain.py` | LSTM model wrapper | `LSTMBrain.predict_from_context()` |
| `scripts/train_ensemble.py` | Ensemble training | Run with `--min-picks 100` |
| `models/*.weights.h5` | 13 LSTM weight files | Loaded on-demand |

### Phase 1 Dormant Signals (Activated v17.5 - Feb 2026)
| File | Function | Pick Type | Boost | Integration Line |
|------|----------|-----------|-------|------------------|
| `esoteric_engine.py` | `calculate_biorhythms()` | PROP | +0.3/+0.15/-0.2 | `live_data_router.py:3614-3642` |
| `esoteric_engine.py` | `analyze_spread_gann()` | GAME | +0.25/+0.15/+0.1 | `live_data_router.py:3647-3673` |
| `esoteric_engine.py` | `check_founders_echo()` | GAME | +0.2/+0.35 | `live_data_router.py:3678-3707` |

### Phase 2.2 - Void-of-Course Daily Edge (Activated v17.5 - Feb 2026)
| File | Function | Purpose | Integration Line |
|------|----------|---------|------------------|
| `astronomical_api.py` | `is_void_moon_now()` | VOC moon detection | `live_data_router.py:1431-1445` |
| `live_data_router.py` | `get_daily_energy()` | Daily Edge scoring | Lines 1397-1456 |

**VOC Penalty Logic:**
- When `is_void_moon_now()` returns `is_void=True` AND `confidence > 0.5`
- Apply `-20` penalty to `energy_score`
- This can push `daily_edge_score` from HIGH to MEDIUM or MEDIUM to LOW
- Traditional astrological wisdom: avoid initiating new bets during VOC periods

### Phase 3 - Vortex Math, Benford Activation & Line History (v17.6 - Feb 2026)
| File | Function | Purpose | Integration Line |
|------|----------|---------|------------------|
| `esoteric_engine.py` | `calculate_vortex_energy()` | Tesla 3-6-9 resonance | `live_data_router.py:3688-3710` |
| `live_data_router.py` | `_extract_benford_values_from_game()` | Multi-book line aggregation | Lines 3152-3205 |
| `database.py` | `LineSnapshot`, `SeasonExtreme` | Line history storage | Database models |
| `daily_scheduler.py` | `_run_line_snapshot_capture()` | 30-min line snapshots | Scheduler job |
| `daily_scheduler.py` | `_run_update_season_extremes()` | Daily 5 AM extremes | Scheduler job |

**Vortex Math Implementation:**
```python
# Tesla 3-6-9 sacred geometry analysis
calculate_vortex_energy(value, context="spread"|"total"|"prop"|"general")
# Returns:
{
    "vortex_score": 5.0-9.0,      # Baseline 5.0
    "digital_root": int,          # Single digit reduction
    "is_tesla_aligned": bool,     # Digital root is 3, 6, or 9
    "is_perfect_vortex": bool,    # Contains 369/396/639/693/936/963
    "is_golden_vortex": bool,     # Within 5% of phi multiples
    "triggered": bool,            # Score >= 7.0
    "signal": str,                # PERFECT_VORTEX|TESLA_ALIGNED|GOLDEN_RATIO|NEUTRAL
}
```

**Vortex Boost Logic:**
| Condition | Boost | Signal |
|-----------|-------|--------|
| Perfect vortex (369 sequence) | +0.3 | `PERFECT_VORTEX` |
| Tesla aligned (root=3,6,9) | +0.2 | `TESLA_ALIGNED` |
| Golden ratio (phi aligned) | +0.1 | `GOLDEN_RATIO` |
| Neutral | +0.0 | `NEUTRAL` |

**Benford Anomaly Fix (v17.6):**
- **Problem:** Only 3 values (prop_line, spread, total) - always < 10, Benford never ran
- **Solution:** `_extract_benford_values_from_game()` extracts from multi-book data:
  - Direct values: prop_line, spread, total (3 values)
  - Multi-book spreads: `game.bookmakers[].markets[spreads].outcomes[].point` (5-10 values)
  - Multi-book totals: `game.bookmakers[].markets[totals].outcomes[].point` (5-10 values)
  - **Result:** 10-25 unique values for Benford analysis
- **Pass `game_bookmakers` parameter** to `calculate_pick_score()` at all 3 call sites

**Line History Schema (v17.6):**
```sql
-- Table 1: Line snapshots for Hurst Exponent (needs 20+ sequential values)
CREATE TABLE line_snapshots (
    id SERIAL PRIMARY KEY,
    event_id VARCHAR(100) NOT NULL,
    sport VARCHAR(20) NOT NULL,
    home_team VARCHAR(100),
    away_team VARCHAR(100),
    book VARCHAR(50),
    spread DECIMAL(5,2),
    spread_odds INTEGER,
    total DECIMAL(6,2),
    total_odds INTEGER,
    public_pct DECIMAL(5,2),
    money_pct DECIMAL(5,2),
    captured_at TIMESTAMP WITH TIME ZONE NOT NULL,
    game_start_time TIMESTAMP WITH TIME ZONE
);

-- Table 2: Season extremes for Fibonacci Retracement
CREATE TABLE season_extremes (
    id SERIAL PRIMARY KEY,
    sport VARCHAR(20) NOT NULL,
    season VARCHAR(20) NOT NULL,
    stat_type VARCHAR(50) NOT NULL,
    subject_id VARCHAR(100),
    subject_name VARCHAR(100),
    season_high DECIMAL(8,2),
    season_low DECIMAL(8,2),
    current_value DECIMAL(8,2),
    updated_at TIMESTAMP WITH TIME ZONE
);
```

**Line History Scheduler Jobs:**
| Job | Schedule | Purpose |
|-----|----------|---------|
| `_run_line_snapshot_capture()` | Every 30 minutes | Capture spread/total from Odds API |
| `_run_update_season_extremes()` | Daily 5 AM ET | Calculate season high/low |

**Line History Helper Functions (database.py):**
```python
save_line_snapshot(db, event_id, sport, ...)     # Save snapshot
get_line_history(db, event_id, limit=30)          # Get history dicts
get_line_history_values(db, event_id, "spread")   # Raw floats for Hurst
update_season_extreme(db, sport, season, ...)     # Update high/low
get_season_extreme(db, sport, season, stat_type)  # Get extremes for Fib
```

**Esoteric Engine Signal Status (17/17 active as of v18.2):**
| Signal | Status | Notes |
|--------|--------|-------|
| Numerology | ✅ ACTIVE | `calculate_generic_numerology()` |
| Astro | ✅ ACTIVE | Vedic astrology |
| Fibonacci Alignment | ✅ ACTIVE | `calculate_fibonacci_alignment()` - checks if line IS Fib number |
| Fibonacci Retracement | ✅ WIRED (v17.7) | `calculate_fibonacci_retracement()` - season range position |
| Vortex | ✅ ACTIVE (v17.6) | Tesla 3-6-9 via `calculate_vortex_energy()` |
| Daily Edge | ✅ ACTIVE + VOC (v17.5) | Daily energy score with VOC penalty |
| GLITCH (6 signals) | ✅ ACTIVE | `get_glitch_aggregate()` |
| Biorhythms | ✅ ACTIVE (v17.5) | Props only, player birth cycles |
| Gann Square | ✅ ACTIVE (v17.5) | Games only, sacred geometry |
| Founder's Echo | ✅ ACTIVE (v17.5) | Games only, team gematria |
| Hurst Exponent | ✅ WIRED (v17.7) | Line history passed to GLITCH (needs 10+ snapshots) |
| Benford Anomaly | ✅ ACTIVATED (v17.6) | Multi-book aggregation now provides 10+ values |
| **Lunar Phase** | ✅ ACTIVE (v18.2) | Full/New moon detection via `calculate_lunar_phase_intensity()` |
| **Mercury Retrograde** | ✅ ACTIVE (v18.2) | 2026 retrograde periods via `check_mercury_retrograde()` |
| **Rivalry Intensity** | ✅ ACTIVE (v18.2) | Major rivalry detection via `calculate_rivalry_intensity()` |
| **Streak Momentum** | ✅ ACTIVE (v18.2) | Win/loss streak analysis via `calculate_streak_momentum()` |
| **Solar Flare** | ✅ ACTIVE (v18.2) | NOAA X-ray flux via `get_solar_flare_status()` |

### Phase 8 - Advanced Esoteric Signals (v18.2 - Feb 2026)
| File | Function | Purpose | Trigger Condition |
|------|----------|---------|-------------------|
| `esoteric_engine.py` | `calculate_lunar_phase_intensity()` | Moon phase impact on scoring | Full moon (0.45-0.55) or New moon (0.0-0.05) |
| `esoteric_engine.py` | `check_mercury_retrograde()` | Retrograde caution signal | During 2026 retrograde periods |
| `esoteric_engine.py` | `calculate_rivalry_intensity()` | Major rivalry detection | Historic rivalry matchups |
| `esoteric_engine.py` | `calculate_streak_momentum()` | Team streak analysis | 2+ game win/loss streaks |
| `alt_data_sources/noaa.py` | `get_solar_flare_status()` | Solar activity chaos boost | X-class or M-class flare |
| `esoteric_engine.py` | `get_phase8_esoteric_signals()` | AGGREGATES ALL 5 | Entry point for Phase 8 |

**Phase 8 Signal Integration (live_data_router.py lines 4039-4106):**
```python
phase8_full_result = get_phase8_esoteric_signals(
    game_datetime=game_datetime,
    game_date=_game_date_obj,
    sport=sport,
    home_team=home_team,
    away_team=away_team,
    pick_type=pick_type,
    pick_side=pick_side,
    team_streak_data=_team_streak_data
)
phase8_boost = phase8_full_result.get("total_boost", 0.0)
esoteric_raw += phase8_boost
```

**Phase 8 Output Fields:**
```python
{
    "phase8_boost": float,
    "phase8_reasons": List[str],
    "phase8_breakdown": {
        "lunar": {"phase": "FULL/NEW/QUARTER", "boost_over": float, "boost_under": float},
        "mercury": {"is_retrograde": bool, "adjustment": float},
        "rivalry": {"is_rivalry": bool, "intensity": str, "under_boost": float},
        "streak": {"momentum": str, "for_boost": float},
        "solar": {"class": "X/M/QUIET", "chaos_boost": float}
    }
}
```

**v18.2 Bug Fixes Applied:**
1. Timezone-aware `ref_date` in `calculate_lunar_phase_intensity()` (line 1422-1426)
2. `weather_data = None` initialization at line 3345

### GLITCH Protocol Files
| File | Purpose | Key Functions |
|------|---------|---------------|
| `esoteric_engine.py` | GLITCH aggregator + Phase 1-3 signals | `get_glitch_aggregate()`, `calculate_chrome_resonance()`, `calculate_biorhythms()`, `analyze_spread_gann()`, `check_founders_echo()`, `calculate_vortex_energy()` |
| `alt_data_sources/noaa.py` | Kp-Index client | `fetch_kp_index_live()`, `get_kp_betting_signal()` |
| `alt_data_sources/serpapi.py` | Noosphere client | `get_noosphere_data()`, `get_team_buzz()` |
| `signals/math_glitch.py` | Benford analysis | `check_benford_anomaly()` |
| `signals/physics.py` | Hurst exponent | `calculate_hurst_exponent()` |
| `signals/hive_mind.py` | Void moon | `get_void_moon()` |
| `database.py` | Line history schema (v17.6) | `LineSnapshot`, `SeasonExtreme`, `save_line_snapshot()`, `get_line_history_values()` |
| `daily_scheduler.py` | Line history capture (v17.6) | `_run_line_snapshot_capture()`, `_run_update_season_extremes()` |

### Trap Learning Loop Files (v19.0)
| File | Purpose | Key Functions |
|------|---------|---------------|
| `trap_learning_loop.py` | Core trap system (~800 LOC) | `TrapLearningLoop`, `TrapDefinition`, `TrapEvaluation`, `get_trap_loop()`, `enrich_game_result()`, `calculate_numerology_day()`, `calculate_team_gematria()` |
| `trap_router.py` | API endpoints (~400 LOC) | `create_trap()`, `list_traps()`, `get_trap()`, `update_trap_status()`, `dry_run_evaluation()`, `get_adjustment_history()` |
| `daily_scheduler.py` | Trap evaluation job | `_run_trap_evaluation()`, `_fetch_yesterday_results()` |

**Trap Data Flow:**
```
PRE-GAME                         POST-GAME (6:15 AM ET)
   │                                    │
Create Trap ───────────────────► Evaluate Traps
   │                                    │
   │  {condition, action,          Game Results
   │   target_engine,                   │
   │   target_parameter}           Check Conditions
   │                                    │
   └──────────────────────────► Apply Adjustments
                                        │
                                  Log & Audit
```

**Trap Definition Schema:**
```python
@dataclass
class TrapDefinition:
    trap_id: str                    # "dallas-blowout-public-fade"
    name: str                       # Human-readable name
    sport: str                      # NBA, NFL, MLB, NHL, NCAAB, ALL
    team: Optional[str]             # Specific team or None for all
    condition: Dict                 # JSON condition object
    action: Dict                    # What to do when triggered
    target_engine: str              # ai, research, esoteric, jarvis, context
    target_parameter: str           # Specific weight/parameter
    adjustment_cap: float = 0.05    # Max 5% per trigger
    cooldown_hours: int = 24        # Min time between triggers
    max_triggers_per_week: int = 3  # Rate limiting
    status: str = "ACTIVE"          # ACTIVE, PAUSED, RETIRED
```

### Complete Learning System Files (v20.2)
| File | Purpose | Key Functions/Classes |
|------|---------|----------------------|
| `auto_grader.py` | Statistical learning (6:00 AM ET) | `AutoGrader`, `PredictionRecord`, `calculate_bias()`, `adjust_weights_with_reconciliation()`, `check_trap_reconciliation()`, `_initialize_weights()`, `_convert_pick_to_record()` |
| `trap_learning_loop.py` | Hypothesis learning (6:15 AM ET) | `TrapLearningLoop`, `has_recent_trap_adjustment()`, `get_recent_parameter_adjustments()` |
| `grader_store.py` | Pick persistence | `persist_pick()`, `load_predictions()` |
| `live_data_router.py` | Signal extraction for learning | Lines 4887-4899 (glitch_signals), Lines 6390-6420 (pick persistence) |

**Critical auto_grader.py Lines (v20.2):**
| Line Range | Function | Purpose |
|------------|----------|---------|
| 173-210 | `_initialize_weights()` | **MUST include game_stat_types (spread, total, moneyline, sharp)** |
| 261-318 | `_convert_pick_to_record()` | Sets `stat_type = pick_type.lower()` for game picks |
| 534-634 | `calculate_bias()` | Filters by `record.stat_type == stat_type` (exact match) |
| 787-866 | `adjust_weights()` | Falls back to "points" if stat_type missing (line 802-803) |
| 1035-1078 | `run_daily_audit()` | Iterates over game_stat_types = ["spread", "total", "moneyline", "sharp"] |

**stat_type Mapping (v20.2):**
| Pick Type | stat_type Value | Source |
|-----------|-----------------|--------|
| PROP | "points", "rebounds", etc. | `pick.get("stat_type", ...)` |
| SPREAD | "spread" | `pick_type.lower()` |
| TOTAL | "total" | `pick_type.lower()` |
| MONEYLINE | "moneyline" | `pick_type.lower()` |
| SHARP | "sharp" | `pick_type.lower()` |

**PredictionRecord Signal Tracking (28 signals - 100% coverage):**
```python
@dataclass
class PredictionRecord:
    # Core fields
    prediction_id: str
    sport: str
    player_name: str
    stat_type: str
    predicted_value: float
    actual_value: Optional[float] = None
    pick_type: str = ""  # PROP, SPREAD, TOTAL, MONEYLINE, SHARP

    # Context Layer (Pillars 13-15)
    defense_adjustment: float = 0.0
    pace_adjustment: float = 0.0
    vacuum_adjustment: float = 0.0
    lstm_adjustment: float = 0.0
    officials_adjustment: float = 0.0

    # Research Engine Signals
    sharp_money_adjustment: float = 0.0
    public_fade_adjustment: float = 0.0
    line_variance_adjustment: float = 0.0

    # GLITCH Protocol Signals (6 signals)
    glitch_signals: Optional[Dict[str, float]] = None
    # chrome_resonance, void_moon, noosphere, hurst, kp_index, benford

    # Esoteric Contributions (14 signals)
    esoteric_contributions: Optional[Dict[str, float]] = None
    # numerology, astro, fib_alignment, fib_retracement, vortex, daily_edge,
    # biorhythms, gann, founders_echo, lunar, mercury, rivalry, streak, solar
```

**Trap-AutoGrader Reconciliation Flow:**
```
AutoGrader (6:00 AM ET)
    │
    ├── Calculate bias for ALL 28 signals
    │   (with 70% confidence decay per day)
    │
    ├── Before adjusting any parameter:
    │   check_trap_reconciliation(engine, parameter)
    │       │
    │       └── has_recent_trap_adjustment(engine, parameter, lookback=24h)
    │           │
    │           └── If trap adjusted in last 24h → SKIP this parameter
    │
    └── Apply remaining adjustments
        (only parameters NOT recently adjusted by traps)

Trap Learning Loop (6:15 AM ET)
    │
    ├── Evaluate pre-game traps against results
    │
    └── Apply conditional adjustments
        (logged to adjustments.jsonl)
```

### Context Layer Files
| File | Purpose | Key Classes |
|------|---------|-------------|
| `context_layer.py` | Pillars 13-17 | `DefensiveRankService`, `PaceVectorService`, `UsageVacuumService`, `OfficialsService`, `ParkFactorService` |

### Scoring Contract
| File | Purpose |
|------|---------|
| `core/scoring_contract.py` | Single source of truth for weights, thresholds, gates |

### Master Specification
| File | Purpose |
|------|---------|
| `docs/JARVIS_SAVANT_MASTER_SPEC.md` | Full master spec + integration audit + missing API map |

### Security Files (Added Feb 2026)
| File | Purpose | Key Functions |
|------|---------|---------------|
| `core/log_sanitizer.py` | Centralized secret redaction | `sanitize_headers()`, `sanitize_dict()`, `sanitize_url()` |
| `tests/test_log_sanitizer.py` | 20 tests for sanitizer | Tests headers, dicts, URLs, tokens |
| `tests/test_no_demo_data.py` | 12 tests for demo gate | Tests fallback behavior, endpoint gating |

### MSRF Files (Added Feb 2026)
| File | Purpose | Key Functions |
|------|---------|---------------|
| `signals/msrf_resonance.py` | Turn date resonance (~565 LOC) | `calculate_msrf_resonance()`, `get_msrf_confluence_boost()` |
| `signals/__init__.py` | Exports MSRF functions | `MSRF_ENABLED`, `MSRF_NORMAL`, `MSRF_IMPORTANT`, `MSRF_VORTEX` |
| `docs/MSRF_INTEGRATION_PLAN.md` | Implementation plan | Reference for MSRF architecture decisions |

**MSRF Data Flow:**
```
get_significant_dates()
  ├── get_significant_dates_from_predictions() → /data/grader/predictions.jsonl
  └── get_significant_dates_from_player_history() → BallDontLie API (NBA only)
        ↓
calculate_msrf_resonance(dates, game_date)
  ├── 16 operations × 3 intervals → transformed values
  └── Match against MSRF_NORMAL/IMPORTANT/VORTEX → points
        ↓
get_msrf_confluence_boost() → (boost, metadata)
        ↓
live_data_router.py:3567 → adds to confluence["boost"]
```

### SERP Intelligence Files (Added Feb 2026 - v17.4)
| File | Purpose | Key Functions |
|------|---------|---------------|
| `core/serp_guardrails.py` | Central config, quota, caps (~354 LOC) | `check_quota_available()`, `apply_shadow_mode()`, `cap_boost()`, `get_serp_status()` |
| `alt_data_sources/serp_intelligence.py` | Engine-aligned signal detection (~823 LOC) | `get_serp_betting_intelligence()`, `get_serp_prop_intelligence()`, `detect_*()` |
| `alt_data_sources/serpapi.py` | SerpAPI client with guardrails (~326 LOC) | `get_search_trend()`, `get_team_buzz()`, `get_player_buzz()`, `get_noosphere_data()` |

**SERP Signal Detectors:**
| Function | Engine | What It Detects |
|----------|--------|-----------------|
| `detect_silent_spike()` | AI | High search volume + low news (insider activity) |
| `detect_sharp_chatter()` | Research | Sharp money, RLM mentions in search |
| `detect_narrative()` | Jarvis | Revenge games, rivalries, playoff implications |
| `detect_situational()` | Context | B2B, rest advantage, travel fatigue |
| `detect_noosphere()` | Esoteric | Search trend velocity between teams |

**SERP Data Flow (v20.7 — Parallel Pre-Fetch):**
```
_best_bets_inner() — BEFORE scoring loop:
  │
  ├── Extract unique (home, away) pairs from raw_games + prop_games
  │
  ├── ThreadPoolExecutor(max_workers=16)
  │     └── _prefetch_serp_game(home, away, target) × 2 per game
  │           └── get_serp_betting_intelligence(sport, home, away, target)
  │                 ├── detect_silent_spike(team, sport) → AI boost
  │                 ├── detect_sharp_chatter(team, sport) → Research boost
  │                 ├── detect_narrative(home, away, sport) → Jarvis boost
  │                 ├── detect_situational(team, sport, b2b, rest) → Context boost
  │                 └── detect_noosphere(home, away) → Esoteric boost
  │
  └── _serp_game_cache[(home_lower, away_lower, target_lower)] = result

calculate_pick_score() — DURING scoring loop:
  │
  ├── Game bets: Check _serp_game_cache first (cache hit ~0ms)
  │     └── Fallback: get_serp_betting_intelligence() if cache miss
  │
  └── Prop bets: get_serp_prop_intelligence() inline (per-player, not pre-fetchable)
        ↓
  cap_total_boost(boosts) → enforce 4.3 total cap
        ↓
  apply_shadow_mode(boosts) → zero if shadow mode (currently OFF)
        ↓
  confluence["boost"] += serp_boost_total
```

**SERP Query Templates (SPORT_QUERIES):**
- NBA: `"{team} sharp money"`, `"{team} reverse line movement"`, `"{team1} vs {team2} rivalry"`
- NFL: `"{team} sharp action"`, `"{team} weather game"`, `"{team} short week"`
- MLB: `"{team} sharp money MLB"`, `"{team} bullpen tired"`, `"{team} pennant race"`
- NHL: `"{team} sharp money NHL"`, `"{team} back to back NHL"`
- NCAAB: `"{team} sharp money college basketball"`, `"{team} tournament"`

---

### ESPN Hidden API Files (Added Feb 2026 - v17.3)
| File | Purpose | Key Functions |
|------|---------|---------------|
| `alt_data_sources/espn_lineups.py` | ESPN Hidden API client (~600 LOC) | See functions below |
| `alt_data_sources/__init__.py` | ESPN exports | `ESPN_AVAILABLE`, all ESPN functions |

**ESPN Functions:**
| Function | Purpose | Returns |
|----------|---------|---------|
| `get_espn_scoreboard()` | Today's games | Events list with IDs |
| `get_espn_event_id()` | Find event by teams | ESPN event ID |
| `get_officials_for_event()` | Referee assignments | Officials list (Pillar 16) |
| `get_officials_for_game()` | Officials by team names | Officials data |
| `get_espn_odds()` | Spread, ML, O/U | Odds dict (cross-validation) |
| `get_espn_injuries()` | Inline injury data | Injuries list |
| `get_espn_player_stats()` | Box scores | Player stats by team |
| `get_espn_venue_info()` | Venue, weather, attendance | Venue dict |
| `get_game_summary_enriched()` | All data in one call | Combined dict |
| `get_all_games_enriched()` | Batch for all games | List of enriched games |

**ESPN Endpoints (FREE - No Auth Required):**
```
Scoreboard:  https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard
Summary:     https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/summary?event={id}
Officials:   https://sports.core.api.espn.com/v2/sports/{sport}/leagues/{league}/events/{id}/competitions/{id}/officials
Teams:       https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/teams/{abbrev}
```

**Sport/League Mapping:**
```python
SPORT_MAPPING = {
    "NBA": {"sport": "basketball", "league": "nba"},
    "NFL": {"sport": "football", "league": "nfl"},
    "MLB": {"sport": "baseball", "league": "mlb"},
    "NHL": {"sport": "hockey", "league": "nhl"},
    "NCAAB": {"sport": "basketball", "league": "mens-college-basketball"},
}
```

**ESPN Data Flow (v17.3):**
```
_best_bets_inner() parallel fetch:
├── Props (Odds API)
├── Games (Odds API)
├── Injuries (Playbook)
├── ESPN Scoreboard
│   └── Build _espn_events_by_teams lookup
│
├── ESPN Officials (batch for all events)
│   └── Build _officials_by_game lookup
│
└── ESPN Enriched (batch for all events)
    ├── Odds → _espn_odds_by_game (cross-validation)
    ├── Injuries → _espn_injuries_supplement (merge with Playbook)
    └── Venue/Weather → _espn_venue_by_game (MLB/NFL outdoor)

Scoring Integration:
├── Research Engine: +0.25-0.5 boost when ESPN confirms spread/total
├── Injuries: ESPN injuries merged into _injuries_by_team
├── Weather: ESPN venue/weather as fallback for outdoor sports
└── Officials: Pillar 16 adjustment from referee tendencies
```

**Reference:** https://scrapecreators.com/blog/espn-api-free-sports-data

### Dual-Use Functions (Endpoint + Internal) - CRITICAL
| Function | Line | Endpoint | Internal Callers | Return Type |
|----------|------|----------|------------------|-------------|
| `get_sharp_money()` | 1758 | `/live/sharp/{sport}` | `_best_bets_inner:2580` | dict ✅ |
| `get_splits()` | 1992 | `/live/splits/{sport}` | dashboard | dict ✅ |
| `get_lines()` | 2100+ | `/live/lines/{sport}` | dashboard | dict ✅ |
| `get_injuries()` | 2200+ | `/live/injuries/{sport}` | dashboard | dict ✅ |

**Rule:** ALL functions in this table MUST return dicts, NOT JSONResponse. FastAPI auto-serializes.

### Go/No-Go Sanity Scripts (v20.4)
| Script | Purpose | Key Checks |
|--------|---------|------------|
| `scripts/prod_go_nogo.sh` | Master orchestrator | Runs all 12 checks, fails fast |
| `scripts/option_a_drift_scan.sh` | Scoring formula guard | No BASE_5, no context-as-engine |
| `scripts/audit_drift_scan.sh` | Unauthorized boost guard | No literal +/-0.5 outside ensemble |
| `scripts/endpoint_matrix_sanity.sh` | Endpoint contract | All sports, required fields, math check |
| `scripts/docs_contract_scan.sh` | Documentation sync | Required fields documented |
| `scripts/env_drift_scan.sh` | Environment config | Required env vars set |
| `scripts/learning_loop_sanity.sh` | Auto grader health | Grader available, weights loaded |
| `scripts/learning_sanity_check.sh` | Weights initialized | All stat types have weights |
| `scripts/live_sanity_check.sh` | Best-bets health | Returns valid JSON structure |
| `scripts/api_proof_check.sh` | Production API | API responding with 200 |

**Critical Line Number Filters (audit_drift_scan.sh):**
```bash
# Allowed ensemble adjustment lines in live_data_router.py:
# - 4753-4754: ensemble_reasons extend
# - 4756-4757: boost (+0.5) fallback
# - 4760-4762: penalty (-0.5) fallback
rg -v "live_data_router.py:475[34]" | \
rg -v "live_data_router.py:475[67]" | \
rg -v "live_data_router.py:476[012]"
```

**Math Formula (endpoint_matrix_sanity.sh line 93-97):**
```jq
($p.base_4_score + $p.context_modifier + $p.confluence_boost +
 $p.msrf_boost + $p.jason_sim_boost + $p.serp_boost +
 ($p.ensemble_adjustment // 0) + ($p.live_adjustment // 0) +
 ($p.totals_calibration_adj // 0)) as $raw |
($raw | if . > 10 then 10 else . end) as $capped |
($p.final_score - $capped) | abs
# Must be < 0.02
```
**Every field that adjusts final_score MUST appear in this formula.** If you add a new adjustment to the scoring pipeline, you MUST: (1) surface it as its own field in the pick payload, (2) add it to this formula with `// 0` null handling.

### Key Debugging Locations
| Location | Line | Purpose |
|----------|------|---------|
| `get_best_bets()` exception handler | 2536-2547 | Catches all best-bets crashes, logs traceback |
| `_best_bets_inner()` | 2546+ | Main best-bets logic, 3000+ lines |
| `calculate_pick_score()` | 3084+ | Nested scoring function, ~900 lines |
| `calculate_jarvis_engine_score()` | 2622+ | Jarvis scoring, can return `jarvis_rs: None` |

### Debugging Commands
```bash
# Get detailed error info from best-bets
curl "/live/best-bets/NBA?debug=1" -H "X-API-Key: KEY" | jq '.detail'

# Check if endpoint returns JSONResponse (should NOT for internal calls)
# If you see "JSONResponse object has no attribute 'get'" - function returns wrong type

# Test all 5 sports after ANY scoring change
for sport in NBA NHL NFL MLB NCAAB; do
  echo "=== $sport ==="
  curl -s "/live/best-bets/$sport" -H "X-API-Key: KEY" | \
    jq '{sport: .sport, games: .game_picks.count, props: .props.count, error: .detail.code}'
done
```

---
