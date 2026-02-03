# Sports Betting API - Claude Code Context

> Master documentation index for the sports betting API project.
> Last updated: 2026-02-02 (v17.9)

## Quick Links

| Document | Purpose |
|----------|---------|
| [LESSONS.md](./LESSONS.md) | Mistakes made and how to avoid them |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | System architecture and signal flow |
| [DEPLOYMENT.md](./DEPLOYMENT.md) | Deployment gates and verification |
| [INVARIANTS.md](./INVARIANTS.md) | Rules that must never be violated |

---

## Project Overview

This is an esoteric sports betting signal API that combines traditional analytics with unconventional signals (astrology, numerology, physics-based indicators).

### Key Components

| Component | File | Purpose |
|-----------|------|---------|
| Live Data Router | `live_data_router.py` | Main API routing, pick scoring |
| Esoteric Engine | `esoteric_engine.py` | GLITCH protocol, Fibonacci, physics signals |
| Database | `database.py` | PostgreSQL connection, line history, season extremes |
| Scheduler | `daily_scheduler.py` | Cron jobs for data collection |
| Physics Signals | `signals/physics.py` | Hurst exponent, chaos indicators |
| Officials Data | `officials_data.py` | Referee tendency database (v17.8) |
| Context Layer | `context_layer.py` | Pillars 13-17 services |

### Current Version: v17.9

**Changes in v17.9:**
- Weather: Now applies to research_score (was bypassing engines)
- Altitude: StadiumAltitudeService wired to esoteric_score
- Travel/B2B: ESPN rest_days now wired to context_score

**Changes in v17.8:**
- Completed Pillar 16: Officials Tendency Integration
- Added referee tendency database (25 NBA, 17 NFL, 15 NHL refs)
- Officials adjustments now applied to Research engine score

**Changes in v17.7:**
- Wired Hurst Exponent to line_history from database
- Wired Fibonacci Retracement to season_extremes from database

---

## GLITCH Protocol Status

| Signal | Weight | Status | Data Source |
|--------|--------|--------|-------------|
| Chrome Resonance | 0.25 | ACTIVE | Birth date calculation |
| Void Moon | 0.20 | ACTIVE | Astronomical API |
| Noosphere Velocity | 0.15 | ACTIVE | Real-time calculation |
| Hurst Exponent | 0.25 | ACTIVE (v17.7) | `line_snapshots` table |
| Kp-Index | 0.25 | ACTIVE | Space weather API |
| Benford Anomaly | 0.10 | ACTIVE (v17.6) | Line values analysis |

**Total weights exceed 1.0** - signals are normalized in `get_glitch_aggregate()`.

---

## Database Schema (Critical Tables)

### line_snapshots
```sql
-- Stores historical line values for Hurst calculation
-- Needs 10+ rows per event_id for Hurst to activate
CREATE TABLE line_snapshots (
    id SERIAL PRIMARY KEY,
    event_id VARCHAR(255) NOT NULL,
    value_type VARCHAR(50) NOT NULL,  -- 'spread', 'total', 'moneyline'
    value DECIMAL(10,2) NOT NULL,
    captured_at TIMESTAMP DEFAULT NOW()
);
```

### season_extremes
```sql
-- Stores season high/low for Fibonacci retracement
-- Populated by 5 AM ET daily scheduler job
CREATE TABLE season_extremes (
    id SERIAL PRIMARY KEY,
    sport VARCHAR(50) NOT NULL,
    season VARCHAR(20) NOT NULL,      -- '2025-26' format
    stat_type VARCHAR(50) NOT NULL,   -- 'spread', 'total'
    season_high DECIMAL(10,2),
    season_low DECIMAL(10,2),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

---

## Critical Functions

### `calculate_pick_score()` in live_data_router.py
- Main scoring function (~line 3200-3700)
- Calls GLITCH aggregate
- Applies esoteric boosts
- **INVARIANT**: Must always wrap DB calls in try/except

### `get_glitch_aggregate()` in esoteric_engine.py
- Combines all GLITCH signals
- **INVARIANT**: Returns valid result even if all inputs are None

### `calculate_hurst_exponent()` in signals/physics.py
- Requires `len(line_history) >= 10`
- Returns H value between 0 and 1
- H > 0.5 = trending, H < 0.5 = mean-reverting

### `calculate_fibonacci_retracement()` in esoteric_engine.py
- Requires season_high and season_low
- Checks if current line is near 23.6%, 38.2%, 50%, 61.8%, 78.6% levels

---

## Environment Variables

```bash
DB_ENABLED=true          # Enable database features
DATABASE_URL=postgres:// # PostgreSQL connection string
API_KEY=xxx              # API authentication
```

---

## Common Commands

```bash
# Syntax check
python -m py_compile live_data_router.py

# Run locally
uvicorn live_data_router:app --reload

# Check logs
railway logs

# Deploy
git push origin main  # Auto-deploys via Railway
```

---

## 17 Pillars Status

| Pillar | Name | Engine | Status |
|--------|------|--------|--------|
| 1-8 | AI Models | AI (15%) | ✅ ACTIVE |
| 9 | Sharp Money (RLM) | Research (20%) | ✅ ACTIVE |
| 10 | Line Variance | Research | ✅ ACTIVE |
| 11 | Public Fade | Research | ✅ ACTIVE |
| 12 | Splits Base | Research | ✅ ACTIVE |
| 13 | Defensive Rank | Context (30%) | ✅ ACTIVE |
| 14 | Pace Vector | Context | ✅ ACTIVE |
| 15 | Usage Vacuum | Context | ✅ ACTIVE |
| 16 | Officials | Research | ✅ ACTIVE (v17.8) |
| 17 | Park Factors | Esoteric | ✅ ACTIVE (MLB only) |

**All 17 pillars now complete!**

---

## Officials Data (Pillar 16)

### Referee Tendency Database

| Sport | Refs | Key Metrics |
|-------|------|-------------|
| NBA | 25 | over_tendency, foul_rate, home_bias |
| NFL | 17 | over_tendency, flag_rate, home_bias |
| NHL | 15 | over_tendency, penalty_rate, home_bias |
| MLB | 0 | N/A (umpires work differently) |
| NCAAB | 0 | N/A (insufficient data) |

### Adjustment Logic

```python
# Total bets (Over/Under)
if over_tendency > 52%: boost Over picks
if over_tendency < 48%: boost Under picks

# Spread/ML bets
if home_bias > 1.5%: boost home team picks
if home_bias < -1.5%: boost away team picks
```

### Adjustment Range: -0.5 to +0.5 on research score

---

## Alt Data Integration (v17.9)

Three alt_data modules wired to scoring pipeline:

| Signal | Target Score | Adjustment Range | Sports |
|--------|--------------|------------------|--------|
| Weather | research_score | -0.5 to 0.0 | NFL, MLB, NCAAF |
| Altitude | esoteric_score | -0.3 to +0.5 | All |
| Travel/B2B | context_score | -0.5 to 0.0 | All |

### Weather Integration

Weather modifier now applies to research_score (market doesn't fully price weather):
- Wind, rain, snow, extreme temps affect outdoor games
- Scaled by 0.5 and capped at -0.5 (negative only)
- Appears in `research_reasons` as "Weather: Wind 18mph"

### Altitude Integration (StadiumAltitudeService)

High-altitude venues in `context_layer.py`:

| Venue | Altitude | Effect |
|-------|----------|--------|
| Denver (Broncos/Nuggets/Rockies/Avalanche) | 5280ft | +0.25 NFL, +0.5 MLB Over |
| Utah (Jazz) | 4226ft | +0.15 NBA/NHL |
| Air Force | 6621ft | +0.25 NCAAF |
| Wyoming | 7220ft | +0.25 NCAAF |

### Travel/B2B Integration

ESPN `rest_days_by_team` now wired to travel module:

| Condition | Adjustment | Reason |
|-----------|------------|--------|
| B2B (rest=0) | -0.5 | "B2B: Back-to-back game" |
| 1-day rest + 1500mi travel | -0.35 | "Travel: 1800mi + 1-day rest" |
| HIGH fatigue impact | -0.4 | "Travel: [reasons]" |
| MEDIUM + 1000mi | -0.2 | "Travel: 1200mi distance" |

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| v17.9 | 2026-02-02 | Weather, Altitude & Travel/B2B integration |
| v17.8 | 2026-02-02 | Pillar 16: Officials tendency integration |
| v17.7 | 2026-02-02 | Wire Hurst & Fibonacci to DB |
| v17.6 | 2026-01-xx | Add Benford anomaly, line_snapshots schema |
| v17.5 | 2026-01-xx | GLITCH protocol foundation |
