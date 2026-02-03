# Session Handoff Document

**Project:** ai-betting-backend (Bookie-o-em)
**Version:** v14.2 PRODUCTION HARDENED
**Last Updated:** 2026-01-12
**Branch:** `main`
**Railway URL:** https://web-production-7b2a.up.railway.app

---

## Current State

The backend is **deployed and running** on Railway. All endpoints are functional and connected to the frontend (bookie-member-app).

### What Was Done This Session

1. **Fixed Railway PORT issue** - Changed from shell variable expansion to Python `os.environ.get()`
2. **Updated deployment files** - `railway.toml`, `Procfile`, `Dockerfile` all use `python main.py`
3. **Removed hardcoded API keys** - Now uses environment variables only with fallback warnings
4. **Added TTL caching** - 5-minute cache for API responses, 2-minute for best-bets
5. **Added optional authentication** - API key auth via `X-API-Key` header (disabled by default)
6. **Added LSTM status endpoint** - `/live/lstm/status` to check model availability
7. **Added auto-grader endpoints** - `/live/grader/status` and `/live/grader/weights/{sport}`
8. **Added scheduler status endpoint** - `/live/scheduler/status`
9. **Added cache management endpoints** - `/live/cache/stats` and `/live/cache/clear`
10. **Marked legacy files deprecated** - `new_endpoints.py` marked as deprecated
11. **Doubled JARVIS trigger weight** - Changed boost divisor from /10 to /5 (max +4 points)

---

## Signal Architecture (Dual Engine + Esoteric Edge)

### TIER 1: 8 AI Models (Max Score: 8 points)

| Model | Description | Weight |
|-------|-------------|--------|
| 1. Ensemble Stacking | XGBoost + LightGBM + RandomForest meta-learner | 1.0 |
| 2. LSTM Brain | TensorFlow RNN for time-series patterns | 1.0 |
| 3. Matchup Specific | Head-to-head historical analysis | 1.0 |
| 4. Monte Carlo | 10,000 simulations with variance modeling | 1.0 |
| 5. Line Movement | Steam moves, reverse line movement detection | 1.0 |
| 6. Rest/Fatigue | Back-to-back, travel, schedule analysis | 1.0 |
| 7. Injury Impact | Roster changes, minutes redistribution | 1.0 |
| 8. Betting Edge | Kelly Criterion, expected value calculation | 1.0 |

**Location:** `advanced_ml_backend.py` (class `MasterPredictionSystem`)

### TIER 2: 8 Pillars of Execution (Max Score: 8 points)

| Pillar | Signal | Scoring |
|--------|--------|---------|
| 1. Sharp Split Advantage | Sharp vs public money divergence | +1.0 if sharp > 65% |
| 2. Reverse Line Movement | Line moves against public money | +1.0 if detected |
| 3. Hospital Fade Protocol | Injury news + line adjustment | +1.0 if favorable |
| 4. Situational Spot | Schedule spots (B2B, rest advantage) | +1.0 if edge found |
| 5. Expert Consensus | Aggregated expert picks | +1.0 if 70%+ agree |
| 6. Prop Correlation | Player props + team totals correlation | +1.0 if aligned |
| 7. Hook Discipline | Avoid -3.5, +6.5 dead zones | +1.0 if clean number |
| 8. Volume Discipline | Unit sizing based on confidence | Multiplier |

**Location:** `advanced_ml_backend.py` (class `PillarsAnalyzer`)

### TIER 3: JARVIS Triggers (Max Score: 4 points)

Gematria-based signals with **doubled weight** (boost / 5):

| Number | Name | Boost | Tier | Final Score |
|--------|------|-------|------|-------------|
| 2178 | THE IMMORTAL | 20 | LEGENDARY | +4.0 |
| 201 | THE ORDER | 12 | HIGH | +2.4 |
| 33 | THE MASTER | 10 | HIGH | +2.0 |
| 93 | THE WILL | 10 | HIGH | +2.0 |
| 322 | THE SOCIETY | 10 | HIGH | +2.0 |

**Location:** `live_data_router.py:233-239`

### TIER 4: Esoteric Edge (18 Modules)

**NOOSPHERE VELOCITY (3 modules)**
- Insider Leak Detection
- Main Character Syndrome
- Phantom Injury Scanner

**GANN PHYSICS (3 modules)**
- 50% Retracement (reversal zones)
- Rule of Three (exhaustion patterns)
- Annulifier Cycle (7-day harmonics)

**SCALAR-SAVANT (6 modules)**
- Numerology (life path, master numbers)
- Moon Phase (lunar betting cycles)
- Tesla 3-6-9 (vortex math alignment)
- Power Numbers (11, 22, 33, 44...)
- Day of Week Energy
- Daily Energy Score

**OMNI-GLITCH (6 modules)**
- Additional esoteric indicators
- Pattern recognition
- Temporal anomalies

**Location:** `live_data_router.py` (functions: `calculate_date_numerology`, `get_moon_phase`, `get_daily_energy`)

---

## Confluence Scoring Formula

```
SMASH PICK Score = AI_Models (0-8) + Pillars (0-8) + JARVIS (0-4) + Esoteric_Boost

Where:
- AI_Models: Sum of 8 model predictions (max 8.0)
- Pillars: Sum of 8 pillar signals (max 8.0)
- JARVIS: trigger["boost"] / 5 (max 4.0 for IMMORTAL)
- Esoteric_Boost: Daily energy modifiers

CONFIDENCE LEVELS:
- SMASH (10.0+): Maximum conviction - all signals aligned
- HIGH (8.0-9.9): Strong conviction - most signals agree
- MEDIUM (6.0-7.9): Moderate conviction - proceed with caution
- LOW (<6.0): Weak signal - consider passing
```

---

## API Endpoints

### Core Endpoints (Production)

```
GET /                           # Root - API info
GET /health                     # Health check
GET /live/health                # Live router health
GET /live/sharp/{sport}         # Sharp money signals (cached 5m)
GET /live/splits/{sport}        # Betting splits (cached 5m)
GET /live/props/{sport}         # Player props (cached 5m)
GET /live/best-bets/{sport}     # AI-scored best bets (cached 2m)
GET /live/esoteric-edge         # Esoteric analysis
GET /live/noosphere/status      # Global consciousness
GET /live/gann-physics-status   # GANN physics
GET /esoteric/today-energy      # Today's energy
```

### Management Endpoints (New)

```
GET /live/cache/stats           # Cache statistics
GET /live/cache/clear           # Clear cache
GET /live/lstm/status           # LSTM model status
GET /live/grader/status         # Auto-grader status
GET /live/grader/weights/{sport}# Current prediction weights
GET /live/scheduler/status      # Daily scheduler status
```

### Supported Sports
`nba`, `nfl`, `mlb`, `nhl`

---

## Environment Variables

### Required for Railway

```bash
ODDS_API_KEY=your_odds_api_key      # The Odds API
PLAYBOOK_API_KEY=your_playbook_key  # Playbook Sports API
```

### Optional

```bash
# Authentication (disabled by default)
API_AUTH_ENABLED=true               # Enable API key auth
API_AUTH_KEY=your_secret_key        # Required if auth enabled

# Override API URLs
ODDS_API_BASE=https://api.the-odds-api.com/v4
PLAYBOOK_API_BASE=https://api.playbook-api.com/v1
```

---

## Key Files

| File | Purpose | Status |
|------|---------|--------|
| `main.py` | FastAPI entry point | Active - v14.2 |
| `live_data_router.py` | All /live/* endpoints, JARVIS triggers | Active - ~980 lines |
| `advanced_ml_backend.py` | 8 AI Models + 8 Pillars | Active - ~850 lines |
| `Procfile` | Railway start command | `python main.py` |
| `railway.toml` | Railway config | `startCommand = "python main.py"` |
| `Dockerfile` | Docker build | `CMD ["python", "main.py"]` |

### Legacy Files (Reference Only)

| File | Description |
|------|-------------|
| `new_endpoints.py` | DEPRECATED - use live_data_router.py |
| `services/` | Legacy sync services - router has async impl |
| `prediction_api.py` | Old 8-model API |

---

## Architecture

### Data Flow

```
Request → main.py → live_data_router.py → Cache Check
                                        ↓ (miss)
                                   External APIs (Odds/Playbook)
                                        ↓
                    ← Cache + Response (standardized schema)
```

### TTL Cache

- Default 5 minutes for API responses
- 2 minutes for best-bets (includes daily energy)
- Cache stats and clear endpoints available

### Optional Authentication

- Disabled by default
- Enable with `API_AUTH_ENABLED=true` and `API_AUTH_KEY=...`
- Clients send `X-API-Key` header

### Response Schema

```json
{
  "sport": "NBA",
  "source": "playbook" | "odds_api" | "estimated" | "ai_model",
  "count": 5,
  "data": [...],
  "timestamp": "2026-01-12T..."
}
```

---

## Frontend Connection

**Frontend:** bookie-member-app
**Backend URL:** `https://web-production-7b2a.up.railway.app`

The frontend is configured to use this backend URL. All `/live/*` endpoints are available.

---

## Future Work

### High Priority
1. ~~**Enable authentication**~~ ✅ DONE - Auth wired to all `/live/*` endpoints
2. ~~**Add Redis caching**~~ ✅ DONE - Hybrid cache with Redis backend + in-memory fallback
3. ~~**Database for predictions**~~ ✅ DONE - PostgreSQL models for auto-grader
4. ~~**Enable daily scheduler**~~ ✅ DONE - Auto-starts on app launch
5. ~~**Integrate LSTM predictions**~~ ✅ READY - Code complete, needs `BALLDONTLIE_API_KEY` + training
6. ~~**Add monitoring**~~ ✅ DONE - Prometheus metrics at `/metrics`
7. ~~**Clean up legacy files**~~ ✅ DONE - Moved to `legacy/` folder

### How to Enable Redis Caching (Railway)
1. Add a Redis service in Railway dashboard
2. Railway automatically sets `REDIS_URL` environment variable
3. The app auto-detects Redis and switches from in-memory to Redis backend
4. Check `/live/cache/stats` to verify: `"backend": "redis"`

### How to Enable PostgreSQL Database (Railway)
1. Add a PostgreSQL service in Railway dashboard
2. Railway automatically sets `DATABASE_URL` environment variable
3. Tables are auto-created on startup (predictions, weights, bias_history, daily_energy)
4. Check `/database/status` to verify: `"enabled": true`

### Daily Scheduler
Scheduler auto-starts on app launch. Endpoints:
- `GET /scheduler/status` - Check scheduler status
- `POST /scheduler/start` - Start scheduler
- `POST /scheduler/stop` - Stop scheduler
- `POST /scheduler/run-audit` - Manually trigger daily audit
- `POST /scheduler/run-cleanup` - Manually trigger cleanup

### LSTM Training - All 5 Sports
Uses your existing Playbook API and Odds API for all sports:
- **Playbook API**: Player game logs for NBA, NFL, MLB, NHL, NCAAB
- **Odds API**: Historical prop lines

No additional API keys needed - uses `PLAYBOOK_API_KEY` and `ODDS_API_KEY` already in Railway.

Run training: `python lstm_training_pipeline.py`
Check status: `GET /live/lstm/status`

### Prometheus Monitoring
Metrics available at `/metrics` endpoint:
- `bookie_requests_total` - HTTP request counts
- `bookie_request_latency_seconds` - Request latency histogram
- `bookie_predictions_total` - Predictions made
- `bookie_smash_picks_total` - SMASH picks generated
- `bookie_cache_hits_total` / `bookie_cache_misses_total`
- `bookie_external_api_calls_total` - External API calls
- `bookie_scheduler_runs_total` - Scheduler job runs
- Check status: `GET /metrics/status`

### How to Enable Authentication (Railway)
Set these environment variables in Railway:
```bash
API_AUTH_ENABLED=true
API_AUTH_KEY=your-secret-key-here
```
Clients must then pass `X-API-Key: your-secret-key-here` header.
The root `/health` endpoint remains public for Railway health checks.

### Medium Priority
4. **Database for predictions** - PostgreSQL for auto-grader storage
5. **Enable daily scheduler** - Automatic weight adjustments
6. **Add monitoring** - Prometheus metrics, alerting

### Low Priority
7. **Refactor services/** - Upgrade to async if needed
8. **Clean up legacy files** - Remove deprecated code

---

## Testing Commands

```bash
# Health check
curl https://web-production-7b2a.up.railway.app/health

# Sharp money
curl https://web-production-7b2a.up.railway.app/live/sharp/nba

# Best bets
curl https://web-production-7b2a.up.railway.app/live/best-bets/nba

# Cache stats
curl https://web-production-7b2a.up.railway.app/live/cache/stats

# LSTM status
curl https://web-production-7b2a.up.railway.app/live/lstm/status

# Esoteric edge
curl https://web-production-7b2a.up.railway.app/live/esoteric-edge
```

---

## Git History (Recent)

```
dd860d1 v14.2: Add caching, auth, and management endpoints
6d3937c Fix railway.toml: use python main.py instead of shell variable
c6166a0 Fix Procfile: use python main.py instead of shell variable
bcdd7fd Fix PORT handling: use Python os.environ instead of shell expansion
dbf3128 Fix Dockerfile: use shell form CMD for proper PORT variable expansion
```

---

## Quick Reference: What Each Score Means

| Score | Label | Action |
|-------|-------|--------|
| 10.0+ | SMASH | Max units, all signals aligned |
| 8.0-9.9 | HIGH | Strong play, 2-3 units |
| 6.0-7.9 | MEDIUM | Standard play, 1-2 units |
| <6.0 | LOW | Pass or small play |

---

*Last handoff: 2026-01-12*
*Version: v14.2 PRODUCTION HARDENED*
