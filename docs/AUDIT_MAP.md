# AUDIT_MAP.md - Integration & Signal Map (Single Source of Truth)

**Last Updated:** 2026-01-29
**Status:** PRODUCTION VERIFIED ✅

This document maps EVERY integration key to its modules, functions, endpoints, and validation methods.

---

## 🔌 INTEGRATION REGISTRY (14 Required)

### Core Paid APIs

| # | Integration | Env Var(s) | Module(s) | Function(s) | Endpoint(s) | Validation |
|---|-------------|------------|-----------|-------------|-------------|------------|
| 1 | **odds_api** | `ODDS_API_KEY`, `EXPO_PUBLIC_ODDS_API_KEY` | `live_data_router.py`, `odds_api.py` | `get_props()`, `get_games()`, `get_lines()` | `/live/best-bets/{sport}`, `/live/props/{sport}`, `/live/lines/{sport}`, `/live/odds/{sport}`, `/live/line-shop/{sport}` | HTTP GET to props endpoint, check `x-requests-remaining` header |
| 2 | **playbook_api** | `PLAYBOOK_API_KEY`, `EXPO_PUBLIC_PLAYBOOK_API_KEY` | `live_data_router.py`, `playbook_api.py` | `get_splits()`, `get_sharp()`, `get_injuries()` | `/live/sharp/{sport}`, `/live/splits/{sport}`, `/live/injuries/{sport}`, `/live/best-bets/{sport}` | HTTP GET to `/v1/health` endpoint |
| 3 | **balldontlie** | `BDL_API_KEY`, `BALLDONTLIE_API_KEY` | `alt_data_sources/balldontlie.py`, `result_fetcher.py`, `identity/player_resolver.py` | `search_player()`, `get_player_season_averages()`, `get_box_score()`, `grade_nba_prop()` | `/live/best-bets/NBA`, `/live/grader/run-audit`, `/live/picks/grading-summary` | HTTP GET to `/v1/players?per_page=1` |

**Note:** `BALLDONTLIE_API_KEY` or `BDL_API_KEY` REQUIRED in environment. No hardcoded fallback.

### Esoteric Engine APIs (20% scoring weight)

| # | Integration | Env Var(s) | Module(s) | Function(s) | Endpoint(s) | Validation |
|---|-------------|------------|-----------|-------------|-------------|------------|
| 4 | **weather_api** ⚠️ | `WEATHER_API_KEY`, `OPENWEATHER_API_KEY` | `alt_data_sources/weather.py` | `get_weather_for_game()`, `calculate_weather_impact()`, `is_weather_relevant()` | `/live/best-bets/NFL`, `/live/best-bets/MLB` | OPTIONAL - `WEATHER_ENABLED=false` by default |

**Note:** Weather is EXPLICITLY DISABLED. Returns `{"available": false, "reason": "FEATURE_DISABLED"}`. Enable with `WEATHER_ENABLED=true` when OpenWeather API integrated.
| 5 | **astronomy_api** | `ASTRONOMY_API_ID`, `EXPO_PUBLIC_ASTRONOMY_API_ID`, `ASTRONOMY_API_SECRET`, `EXPO_PUBLIC_ASTRONOMY_API_SECRET` | `esoteric_engine.py`, `astronomical_api.py`, `live_data_router.py` | `get_moon_phase()`, `get_void_of_course()`, `get_planetary_hours()` | `/live/esoteric-edge`, `/esoteric/today-energy`, `/live/best-bets/{sport}` | HTTP GET to astronomy API with credentials |
| 6 | **noaa_space_weather** | `NOAA_BASE_URL`, `EXPO_PUBLIC_NOAA_BASE_URL` | `esoteric_engine.py` | `get_kp_index()`, `get_solar_activity()`, `get_geomagnetic_data()` | `/live/esoteric-edge`, `/esoteric/today-energy`, `/live/best-bets/{sport}` | HTTP GET to NOAA public API (free, no auth) |

### Economic/Sentiment APIs

| # | Integration | Env Var(s) | Module(s) | Function(s) | Endpoint(s) | Validation |
|---|-------------|------------|-----------|-------------|-------------|------------|
| 7 | **fred_api** | `FRED_API_KEY` | `esoteric_engine.py` | `get_economic_sentiment()`, `get_consumer_confidence()` | `/live/esoteric-edge`, `/live/best-bets/{sport}` | HTTP GET to FRED API with key |
| 8 | **finnhub_api** | `FINNHUB_KEY`, `FINNHUB_API_KEY` | `esoteric_engine.py` | `get_sportsbook_stocks()`, `get_market_sentiment()` | `/live/esoteric-edge` | HTTP GET to Finnhub quote endpoint |
| 9 | **serpapi** | `SERPAPI_KEY`, `SERP_API_KEY` | `esoteric_engine.py` | `get_trending_topics()`, `get_news_sentiment()` | `/live/esoteric-edge`, `/live/best-bets/{sport}` | HTTP GET to SerpAPI with key |
| 10 | **twitter_api** | `TWITTER_BEARER`, `TWITTER_BEARER_TOKEN` | `esoteric_engine.py` | `get_injury_tweets()`, `get_breaking_news()` | `/live/esoteric-edge`, `/live/best-bets/{sport}` | HTTP GET to Twitter API v2 with bearer token |

### Platform APIs

| # | Integration | Env Var(s) | Module(s) | Function(s) | Endpoint(s) | Validation |
|---|-------------|------------|-----------|-------------|-------------|------------|
| 11 | **whop_api** | `WHOP_API_KEY` | `auth.py` | `verify_membership()`, `check_premium_access()` | `/auth/verify`, `/auth/webhook` | HTTP GET to Whop membership API |

### Infrastructure

| # | Integration | Env Var(s) | Module(s) | Function(s) | Endpoint(s) | Validation |
|---|-------------|------------|-----------|-------------|-------------|------------|
| 12 | **database** | `DATABASE_URL` | `database.py`, `models.py` | `get_connection()`, `execute_query()` | All endpoints | SQLAlchemy connection test |
| 13 | **redis** | `REDIS_URL` | `cache.py` | `get_cache()`, `set_cache()`, `invalidate()` | All endpoints | Redis PING command |
| 14 | **railway_storage** | `RAILWAY_VOLUME_MOUNT_PATH`, `GRADER_MOUNT_ROOT` | `storage_paths.py`, `data_dir.py`, `grader_store.py`, `pick_logger.py` | `persist_pick()`, `load_predictions()`, `get_storage_stats()` | `/live/best-bets/{sport}`, `/live/grader/status`, `/live/grader/run-audit`, `/internal/storage/health` | `os.path.ismount()` + write test |

---

## 🧠 SIGNAL ARCHITECTURE (4-Engine + Jason Sim)

### Engine 1: AI Score (25% weight)

| Signal | Module | Function | Input | Output | Baseline |
|--------|--------|----------|-------|--------|----------|
| 8 AI Models | `advanced_ml_backend.py` | `MasterPredictionSystem.predict()` | game_data, player_stats | 0-8 (scaled to 0-10) | 5.0 |
| Sharp Calibration | `live_data_router.py` | `_calibrate_ai_score()` | sharp_present, signal_strength | +0.25 to +1.5 | 0 |

### Engine 2: Research Score (30% weight)

| Signal | Module | Function | Input | Output | Baseline | No-Trigger Reason |
|--------|--------|----------|-------|--------|----------|-------------------|
| Sharp Money | `live_data_router.py` | `_compute_sharp_signal()` | playbook_splits | 0-3 pts | 0 | "NO_SHARP_DATA" |
| Line Variance | `live_data_router.py` | `_compute_line_variance()` | odds_api_lines | 0-3 pts | 0 | "INSUFFICIENT_BOOKS" |
| Public Fade | `live_data_router.py` | `_compute_public_fade()` | ticket_pct, money_pct | 0-2 pts | 0 | "NO_FADE_SIGNAL" |
| Base Score | `live_data_router.py` | N/A | has_real_splits | 2.0-3.0 | 2.0 | N/A |

### Engine 3: Esoteric Score (20% weight)

| Signal | Weight | Module | Function | Input | Output | Baseline | No-Trigger Reason |
|--------|--------|--------|----------|-------|--------|----------|-------------------|
| Numerology | 35% | `esoteric_engine.py` | `compute_numerology()` | day_of_year, game_str, prop_line, player_name | 0-3.5 | 1.0 | "NEUTRAL_DAY" |
| Astro/Moon | 25% | `esoteric_engine.py`, `astronomical_api.py` | `get_vedic_score()` | moon_phase, planetary_hours | 0-2.5 | 1.0 | "ASTRO_API_UNAVAILABLE" |
| Fibonacci | 15% | `esoteric_engine.py` | `calculate_fibonacci_alignment()` | magnitude (spread/prop_line/total) | 0-1.5 | 0.3 | "NO_FIB_ALIGNMENT" |
| Vortex | 15% | `esoteric_engine.py` | `calculate_vortex_pattern()` | magnitude × 10 | 0-1.5 | 0.3 | "NO_VORTEX_PATTERN" |
| Daily Edge | 10% | `esoteric_engine.py` | `get_daily_energy()` | date, sport | 0-1.0 | 0.4 | "NEUTRAL_ENERGY" |

**Magnitude Fallback (CRITICAL for props):**
```python
if player_name:  # PROP
    magnitude = abs(prop_line) or abs(spread) or abs(total/10) or 0
else:  # GAME
    magnitude = abs(spread) or abs(total/10) or abs(prop_line) or 0
```

### Engine 4: Jarvis Score (15% weight)

| Signal | Module | Function | Input | Output | Baseline | No-Trigger Reason |
|--------|--------|----------|-------|--------|----------|-------------------|
| Gematria Triggers | `jarvis_savant_engine.py` | `check_gematria()` | team_names, player_name | +0.5-2.0 per trigger | 0 | "NO_GEMATRIA_HIT" |
| Mid-Spread Goldilocks | `jarvis_savant_engine.py` | `check_goldilocks()` | spread | +1.0-2.0 | 0 | "SPREAD_OUT_OF_RANGE" |
| Trap Detection | `jarvis_savant_engine.py` | `detect_trap()` | public_pct, line_movement | +0.5-1.5 | 0 | "NO_TRAP_DETECTED" |
| Sacred Numbers | `jarvis_savant_engine.py` | `check_sacred()` | all numeric inputs | +0.25-1.0 | 0 | "NO_SACRED_NUMBERS" |

**7-Field Contract (MANDATORY):**
```python
{
    "jarvis_rs": float | None,        # 0-10 when active, None when inputs missing
    "jarvis_active": bool,            # True if triggers fired
    "jarvis_hits_count": int,         # Count of triggers hit
    "jarvis_triggers_hit": List[str], # Names of triggers that fired
    "jarvis_reasons": List[str],      # Why it triggered
    "jarvis_fail_reasons": List[str], # Explain low score / no triggers
    "jarvis_inputs_used": Dict,       # Tracks all inputs (spread, total, etc.)
}
```

**Baseline Floor:** 4.5 when inputs present but no triggers fire

### Jason Sim 2.0 (Post-Pick Confluence)

| Field | Required | Module | Description |
|-------|----------|--------|-------------|
| `jason_win_pct_home` | ✅ | `live_data_router.py` | Home team win % from 1000 sims |
| `jason_win_pct_away` | ✅ | `live_data_router.py` | Away team win % from 1000 sims |
| `jason_projected_total` | ✅ | `live_data_router.py` | Projected game total |
| `jason_projected_pace` | ❌ Optional | `live_data_router.py` | Pace factor |
| `jason_variance_flag` | ✅ | `live_data_router.py` | LOW/MED/HIGH variance |
| `jason_injury_state` | ✅ | `live_data_router.py` | CONFIRMED_ONLY (no questionable) |
| `jason_sim_count` | ✅ | `live_data_router.py` | Number of simulations (1000) |

**Boost Rules:**
| Condition | Action |
|-----------|--------|
| Spread/ML: pick-side win% ≥61% | +0.5 boost |
| Spread/ML: pick-side win% ≤55% | -0.3 downgrade |
| Spread/ML: pick-side win% ≤52% AND base_score <7.2 | BLOCK pick |
| Totals: variance HIGH | Reduce confidence (-0.2) |
| Totals: variance LOW/MED | Increase confidence (+0.2) |
| Props: base_prop_score ≥6.8 AND env supports | +0.25 boost |
| Props: base_prop_score <6.8 | No boost (0) |

---

## 📊 PHYSICS & HIVE MIND SIGNALS

### Physics Layer (in `esoteric_engine.py`)

| Signal | Function | Input | Output | API Source |
|--------|----------|-------|--------|------------|
| Gann Square of Nine | `calculate_gann_square()` | spread, total | angle_resonance (0-1) | None (math) |
| 50% Fibonacci Retrace | `calculate_fib_retracement()` | line, season_range | zone_strength (0-1) | None (math) |
| Schumann Resonance | `get_schumann_frequency()` | current_time | resonance_factor (0.8-1.2) | NOAA |
| Barometric Drag | `get_barometric_impact()` | venue, elevation | drag_factor (0.9-1.1) | Weather API |
| Hurst Exponent | `calculate_hurst()` | price_series | trending/reverting (0-1) | Historical data |
| Kp-Index | `get_kp_index()` | current_time | geomagnetic_activity (0-9) | NOAA Space Weather |

### Hive Mind Layer (in `esoteric_engine.py`)

| Signal | Function | Input | Output | API Source |
|--------|----------|-------|--------|------------|
| Noosphere Velocity | `get_noosphere_velocity()` | game_teams, date | collective_sentiment (0-1) | Twitter, SerpAPI |
| Void Moon | `get_void_of_course()` | game_time | is_void (bool), duration | Astronomy API |
| Linguistic Divergence | `analyze_sentiment_divergence()` | news_articles | divergence_score (0-1) | SerpAPI, Twitter |

### Market Signals (in `live_data_router.py`)

| Signal | Function | Input | Output | API Source |
|--------|----------|-------|--------|------------|
| Reverse Line Movement | `detect_rlm()` | line_history, public_pct | rlm_signal (bool) | Playbook + Odds API |
| Teammate Void | `check_teammate_void()` | player_props, same_team | is_void (bool) | Odds API props |
| Correlation Matrix | `get_correlations()` | prop_types, sport | correlation (0-1) | Static data |
| Benford Anomaly | `check_benford()` | numeric_data | anomaly_score (0-1) | None (math) |

---

## 🔒 NON-NEGOTIABLE INVARIANTS

### 1. ET Day Window (MANDATORY)
```python
from core.time_et import filter_events_et, et_day_bounds

# Window: 00:01:00 ET to 23:59:00 ET (inclusive)
# Applied BEFORE: scoring, grading, storage, best-bets selection
# Single source: core/time_et.py
```

### 2. Score Threshold (6.5 MINIMUM)
```python
# NEVER show or store picks with final_score < 6.5
# Filter applied in: live_data_router.py after scoring
# Verified by: test_min_score_filter.py
```

### 3. Titanium 3-of-4 Rule (STRICT)
```python
from core.titanium import compute_titanium_flag

# ONLY award TITANIUM_SMASH when ≥3 of 4 engines ≥8.0
# 1/4 → FALSE (always)
# 2/4 → FALSE (always)
# 3/4 → TRUE (mandatory)
# 4/4 → TRUE (mandatory)
```

### 4. Component Baseline + Reason (MANDATORY)
```python
# Every component must output:
# - Non-zero baseline when not triggered
# - Explicit "no-trigger reason" field

# Example:
{
    "jarvis_rs": 4.5,  # Baseline, not 0
    "jarvis_active": False,
    "jarvis_fail_reasons": ["NO_GEMATRIA_HIT", "SPREAD_OUT_OF_RANGE"]
}
```

### 5. Jason Sim Required Fields
```python
# Per-game required:
jason_fields = [
    "jason_win_pct_home",
    "jason_win_pct_away",
    "jason_projected_total",
    "jason_variance_flag",
    "jason_injury_state",  # CONFIRMED_ONLY
    "jason_sim_count",
]
```

### 6. Persistence on Railway Volume
```python
# ALL storage under: RAILWAY_VOLUME_MOUNT_PATH (/app/grader_data)
# Structure:
# /app/grader_data/grader/predictions.jsonl
# /app/grader_data/grader_data/weights.json
# /app/grader_data/audit_logs/audit_{date}.json
```

### 7. Zero 500s Policy
```python
# Endpoints: FAIL SOFT (return partial data, never crash)
# Health/Debug: FAIL LOUD (explicit errors for missing integrations)
```

---

## ✅ VALIDATION ENDPOINTS

| Endpoint | Purpose | Auth Required |
|----------|---------|---------------|
| `GET /live/debug/integrations` | Full integration status | Yes |
| `GET /live/debug/integrations?quick=true` | Quick configured list | Yes |
| `GET /internal/storage/health` | Railway volume status | No |
| `GET /live/grader/status` | Autograder status | Yes |
| `GET /live/debug/time` | ET timezone verification | Yes |
| `GET /health` | Basic health check | No |

---

## 🧪 REQUIRED TESTS

| Test File | Purpose | Invariant |
|-----------|---------|-----------|
| `test_et_day_window_filter.py` | ET filtering before scoring | #1 |
| `test_min_score_filter.py` | No picks <6.5 stored/returned | #2 |
| `test_titanium_strict.py` | 3/4 rule enforcement | #3 |
| `test_component_baselines.py` | Non-zero baselines + reasons | #4 |
| `test_jason_sim_fields.py` | All required fields present | #5 |
| `test_persistence_volume_path.py` | Railway volume persistence | #6 |
| `test_integrations_registry_complete.py` | All env vars in registry | #7 |

---

## 📋 OUTPUT CONTRACT

Every pick from `/live/best-bets/{sport}` MUST include:

```json
{
  "pick_id": "12char_hex",
  "final_score": 7.5,
  "tier": "GOLD_STAR",

  "ai_score": 7.8,
  "research_score": 7.2,
  "esoteric_score": 6.5,
  "jarvis_score": 6.8,

  "titanium_triggered": false,
  "titanium_count": 2,
  "titanium_qualified_engines": ["ai", "research"],

  "jason_sim": {
    "win_pct_home": 58.2,
    "win_pct_away": 41.8,
    "projected_total": 226.5,
    "variance_flag": "MED",
    "injury_state": "CONFIRMED_ONLY",
    "sim_count": 1000,
    "confluence_reasons": ["HOME_EDGE_STRONG"]
  },

  "api_sources_used": ["odds_api", "playbook_api", "balldontlie"],

  "esoteric_breakdown": {
    "numerology": 1.2,
    "astro": 0.8,
    "fibonacci": 0.4,
    "vortex": 0.3,
    "daily_edge": 0.6,
    "magnitude_input": 25.5
  },

  "jarvis_breakdown": {
    "jarvis_rs": 6.8,
    "jarvis_active": true,
    "jarvis_hits_count": 2,
    "jarvis_triggers_hit": ["GEMATRIA_33", "GOLDILOCKS"],
    "jarvis_reasons": ["Team gematria hit 33", "Spread 4.5 in goldilocks range"],
    "jarvis_fail_reasons": [],
    "jarvis_inputs_used": {"spread": 4.5, "total": 226.5}
  }
}
```

---

**Document maintained by:** Backend Team
**Enforcement:** `integration_registry.py`, `core/invariants.py`, test suite
