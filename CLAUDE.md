# CLAUDE.md - Project Instructions for AI Assistants

## User Environment
- **OS:** Mac
- **Terminal:** Use Mac Terminal commands (no Windows-specific instructions)

---

## Project Overview

**Bookie-o-em** - AI Sports Prop Betting Backend
**Version:** v14.2 PRODUCTION HARDENED
**Stack:** Python 3.11+, FastAPI, Railway deployment
**Frontend:** bookie-member-app (separate repo)
**Production URL:** https://web-production-7b2a.up.railway.app

---

## IMPORTANT: Paid APIs - Always Use These

**We pay for Odds API and Playbook API. Always use these for any data needs:**

| API | Purpose | Key |
|-----|---------|-----|
| **Odds API** | Live odds, lines, betting data, historical props | `ODDS_API_KEY` |
| **Playbook API** | Player stats, game logs, sharp money, splits (all 5 sports) | `PLAYBOOK_API_KEY` |

**Default to our paid APIs first.** These cover all 5 sports: **NBA, NFL, MLB, NHL, NCAAB**

**Exception:** You may suggest alternative APIs if:
1. You explain WHY it's better than our paid APIs (data not available, better quality, etc.)
2. You get approval before implementing
3. There's a clear benefit over what we're already paying for

### Playbook API v1 Endpoints

**Base URL:** `https://api.playbook-api.com/v1`
**Auth:** `api_key` query parameter (NOT Bearer header)
**Leagues:** NBA | NFL | CFB | MLB | NHL (uppercase)

| Endpoint | Purpose | Required Params |
|----------|---------|-----------------|
| `/health` | Health check | none |
| `/me` | Plan + usage info | `api_key` |
| `/teams` | Team metadata + injuries | `league`, `api_key` |
| `/injuries` | Injury report by team | `league`, `api_key` |
| `/splits` | Public betting splits | `league`, `api_key` |
| `/splits-history` | Historical splits | `league`, `date`, `api_key` |
| `/odds-games` | Schedule + gameId list | `league`, `api_key` |
| `/lines` | Current spread/total/ML | `league`, `api_key` |
| `/games` | Game objects from splits | `league`, `date`, `api_key` |

### API Usage Monitoring

**IMPORTANT:** Monitor API usage to avoid hitting limits, especially if community usage grows.

| Endpoint | Purpose |
|----------|---------|
| `GET /live/api-health` | Quick status check (for dashboards) |
| `GET /live/api-usage` | Combined usage with threshold warnings |
| `GET /live/playbook/usage` | Playbook plan + quota info |
| `GET /live/odds-api/usage` | Odds API requests remaining |

**Threshold Warning Levels:**
| Level | % Used | Emoji | Action |
|-------|--------|-------|--------|
| `HEALTHY` | < 25% | ✅ | None needed |
| `CAUTION_25` | 25-49% | 🟢 | Monitor |
| `CAUTION_50` | 50-74% | 🟡 | Watch closely |
| `CAUTION_75` | 75-89% | 🟠 | Consider upgrading |
| `CRITICAL` | 90%+ | 🚨 | UPGRADE NOW |

**Response includes:**
- `overall_status`: Worst status across all APIs
- `action_needed`: true if CRITICAL or CAUTION_75
- `alerts`: List of warning messages
- `summary`: Human-readable status message

**Odds API Info:**
- Resets monthly
- Free tier = 500 requests/month
- Headers: `x-requests-remaining`, `x-requests-used`

**Quick check command:**
```bash
curl "https://web-production-7b2a.up.railway.app/live/api-health" -H "X-API-Key: YOUR_KEY"
```

**Full details:**
```bash
curl "https://web-production-7b2a.up.railway.app/live/api-usage" -H "X-API-Key: YOUR_KEY"
```

---

## Authentication

**API Authentication is ENABLED.** Key stored in Railway environment variables (`API_AUTH_KEY`).
- All `/live/*` endpoints require `X-API-Key` header
- `/health` endpoint is public (for Railway health checks)

---

## Architecture

### Core Files (Active)

| File | Purpose |
|------|---------|
| `main.py` | FastAPI entry point, includes routers |
| `live_data_router.py` | All `/live/*` endpoints, JARVIS triggers, esoteric functions |
| `advanced_ml_backend.py` | 8 AI Models + 8 Pillars of Execution |

### Legacy Files (Reference Only - Do Not Modify)

| File | Status |
|------|--------|
| `new_endpoints.py` | DEPRECATED |
| `services/` | Legacy sync services |
| `prediction_api.py` | Old 8-model API |

---

## Signal Architecture (Dual Engine)

### Scoring Formula
```
SMASH PICK = AI_Models (0-8) + Pillars (0-8) + JARVIS (0-4) + Esoteric_Boost
```

### Components

1. **8 AI Models** (max 8 pts) - `advanced_ml_backend.py`
   - Ensemble, LSTM, Matchup, Monte Carlo, Line Movement, Rest/Fatigue, Injury, Betting Edge

2. **8 Pillars** (max 8 pts) - `advanced_ml_backend.py`
   - Sharp Split, Reverse Line, Hospital Fade, Situational Spot, Expert Consensus, Prop Correlation, Hook Discipline, Volume Discipline

3. **JARVIS Triggers** (max 4 pts) - `live_data_router.py:233-239`
   - Gematria signals: 2178, 201, 33, 93, 322
   - Weight: `boost / 5` (doubled from original /10)

4. **Esoteric Edge** (18 modules) - `live_data_router.py`
   - NOOSPHERE VELOCITY, GANN PHYSICS, SCALAR-SAVANT, OMNI-GLITCH

---

## Self-Improvement System (Auto-Grader)

The system learns and improves daily through the **Auto-Grader** feedback loop.

### How It Works

1. **Log Predictions** - Each pick is stored with adjustment factors used
2. **Grade Results** - After games, actual stats are compared to predictions
3. **Calculate Bias** - System identifies if it's over/under predicting
4. **Adjust Weights** - Weights are corrected to reduce future errors
5. **Persist Learning** - New weights saved for tomorrow's picks

### Key Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/live/grader/status` | GET | Check grader status |
| `/live/grader/weights/{sport}` | GET | Current learned weights |
| `/live/grader/bias/{sport}` | GET | See prediction bias |
| `/live/grader/performance/{sport}` | GET | Hit rate & MAE metrics |
| `/live/grader/run-audit` | POST | Trigger daily audit |
| `/live/grader/adjust-weights/{sport}` | POST | Manual weight adjustment |

### Bias Interpretation

| Bias Range | Status | Action |
|------------|--------|--------|
| -1.0 to +1.0 | ✅ Healthy | None needed |
| -2.0 to -1.0 or +1.0 to +2.0 | 🟡 Monitor | Watch next audit |
| Beyond ±2.0 | 🚨 Critical | Immediate adjustment |

- **Positive bias** = Predicting too HIGH
- **Negative bias** = Predicting too LOW

### Target Metrics

| Sport | Target MAE | Profitable Hit Rate |
|-------|------------|---------------------|
| NBA/NCAAB | < 3.0 pts | > 52% |
| NFL passing | < 15.0 yds | > 52% |
| All props | - | > 55% (🔥 SMASH) |

### Daily Audit

Run this daily after games complete to improve picks:
```bash
curl -X POST "https://web-production-7b2a.up.railway.app/live/grader/run-audit" \
  -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"days_back": 1, "apply_changes": true}'
```

### Check Performance

See how picks are doing over the last 7 days:
```bash
curl "https://web-production-7b2a.up.railway.app/live/grader/performance/nba?days_back=7" \
  -H "X-API-Key: YOUR_KEY"
```

### Daily Community Report

Every morning at 6 AM ET, the system grades picks and generates a report for your community.

**Get the daily report:**
```bash
curl "https://web-production-7b2a.up.railway.app/live/grader/daily-report" \
  -H "X-API-Key: YOUR_KEY"
```

**Report includes:**
- Overall performance (wins/losses/hit rate)
- Performance by sport
- What the system learned
- Improvements made to weights
- Ready-to-post community message

**Sample output:**
```
🔥 SMASH SPOT DAILY REPORT 🔥

📅 January 15, 2026 Results:
• Total Picks: 24
• Record: 14-10
• Hit Rate: 58.3%

SMASHING IT!

📚 What We Learned:
• NBA: Model performing well, minor tuning applied.

🔧 Improvements Made:
• Weights optimized for tomorrow.

Your community is in great hands. Keep riding the hot streak!

🎯 We grade EVERY pick at 6 AM and adjust our AI daily.
Whether we win or lose, we're always improving! 💪
```

**Status Levels:**
| Hit Rate | Status | Emoji |
|----------|--------|-------|
| 55%+ | SMASHING IT! | 🔥 |
| 52-54% | PROFITABLE DAY! | 💰 |
| 48-51% | BREAK-EVEN ZONE | 📊 |
| Below 48% | LEARNING DAY | 📈 |

---

## Coding Standards

### Python/FastAPI

```python
# Use async for all endpoint handlers
@router.get("/endpoint")
async def get_endpoint():
    pass

# Use httpx for async HTTP calls (not requests)
async with httpx.AsyncClient() as client:
    resp = await client.get(url)

# Environment variables with fallbacks
API_KEY = os.getenv("API_KEY", "")
if not API_KEY:
    logger.warning("API_KEY not set")

# Type hints for function signatures
async def fetch_data(sport: str) -> Dict[str, Any]:
    pass

# Consistent response schema
return {
    "sport": sport.upper(),
    "source": "playbook" | "odds_api" | "estimated",
    "count": len(data),
    "data": data
}
```

### Error Handling

```python
# Prefer explicit status codes over generic exceptions
if resp.status_code == 429:
    raise HTTPException(status_code=503, detail="Rate limited")

if resp.status_code != 200:
    raise HTTPException(status_code=502, detail=f"API error: {resp.status_code}")

# Use logging, not print statements
logger.info("Fetched %d games for %s", len(games), sport)
logger.exception("Failed to fetch: %s", e)
```

### Caching

```python
# Check cache first
cache_key = f"endpoint:{sport}"
cached = api_cache.get(cache_key)
if cached:
    return cached

# ... fetch data ...

# Cache before returning
api_cache.set(cache_key, result, ttl=300)  # 5 min default, 120 for best-bets
return result
```

---

## Environment Variables

### Required
```bash
ODDS_API_KEY=xxx          # The Odds API
PLAYBOOK_API_KEY=xxx      # Playbook Sports API
```

### Optional
```bash
API_AUTH_ENABLED=true     # Enable X-API-Key auth
API_AUTH_KEY=xxx          # Required if auth enabled
ODDS_API_BASE=xxx         # Override API URL
PLAYBOOK_API_BASE=xxx     # Override API URL
```

### Railway Auto-Set
```bash
PORT=8000                 # Read via os.environ.get("PORT", 8000)
```

---

## Deployment

### Railway Configuration

- `railway.toml` - Uses `startCommand = "python main.py"`
- `Procfile` - `web: python main.py`
- `Dockerfile` - `CMD ["python", "main.py"]`

**Important:** PORT must be read in Python, not shell expansion:
```python
# Correct
port = int(os.environ.get("PORT", 8000))

# Wrong - does not work on Railway
# uvicorn main:app --port ${PORT:-8000}
```

---

## API Endpoints

### Production Endpoints
```
GET /                           # API info
GET /health                     # Health check
GET /live/health                # Router health
GET /live/sharp/{sport}         # Sharp money (derived from splits)
GET /live/splits/{sport}        # Betting splits (cached 5m)
GET /live/injuries/{sport}      # Injury report (Playbook + ESPN)
GET /live/lines/{sport}         # Current lines spread/total/ML
GET /live/props/{sport}         # Player props (cached 5m)
GET /live/best-bets/{sport}     # AI best bets (cached 2m)
GET /live/esoteric-edge         # Esoteric analysis
GET /live/noosphere/status      # Noosphere velocity
GET /live/gann-physics-status   # GANN physics
GET /esoteric/today-energy      # Daily energy
```

### Frontend Compatibility Endpoints

**These endpoints match the frontend api.js expected method names.**

```
GET  /live/games/{sport}              # Live games with odds (alias for /lines)
GET  /live/slate/{sport}              # Today's game schedule
GET  /live/roster/{sport}/{team}      # Team roster with injuries
GET  /live/player/{player_name}       # Player stats, props, injury status
POST /live/predict-live               # AI prediction lookup
```

| Frontend Method | Backend Endpoint | Returns |
|-----------------|------------------|---------|
| `api.getLiveGames(sport)` | `GET /live/games/{sport}` | Games with odds |
| `api.getLiveSlate(sport)` | `GET /live/slate/{sport}` | Game schedule |
| `api.getRoster(sport, team)` | `GET /live/roster/{sport}/{team}` | Roster + injuries |
| `api.getPlayerStats(name)` | `GET /live/player/{name}?sport=nba` | Props + injury |
| `api.predictLive(data)` | `POST /live/predict-live` | AI prediction |

### Consolidated Endpoints (Server-Side Fetching)

**Use these endpoints to reduce client-side waterfalls. Each consolidates multiple API calls into one.**

```
GET /live/sport-dashboard/{sport}              # Dashboard: best-bets + splits + lines + injuries + sharp (6→1)
GET /live/game-details/{sport}/{game_id}       # Game view: lines + props + sharp + injuries + AI pick (5→1)
GET /live/parlay-builder-init/{sport}?user_id= # Parlay: recommended props + all props + correlations (3→1)
```

| Endpoint | Replaces | Cache TTL | Use Case |
|----------|----------|-----------|----------|
| `/sport-dashboard/{sport}` | 6 endpoints | 2m | Dashboard page load |
| `/game-details/{sport}/{game_id}` | 5 endpoints | 2m | Game detail modal |
| `/parlay-builder-init/{sport}` | 3 endpoints | 3m | Parlay builder init |

**Response Schema - sport-dashboard:**
```json
{
  "sport": "NBA",
  "best_bets": { "props": [], "game_picks": [] },
  "market_overview": { "lines": [], "splits": [], "sharp_signals": [] },
  "context": { "injuries": [] },
  "daily_energy": {...},
  "timestamp": "ISO",
  "cache_info": { "hit": false, "sources": {...} }
}
```

### Click-to-Bet Endpoints v2.0
```
GET  /live/sportsbooks                    # List 8 supported sportsbooks
GET  /live/line-shop/{sport}              # Line shopping across all books
GET  /live/betslip/generate               # Generate betslip for placing bet
GET  /live/quick-betslip/{sport}/{game}   # Quick betslip with user prefs
GET  /live/user/preferences/{user_id}     # Get user preferences
POST /live/user/preferences/{user_id}     # Save user preferences
POST /live/bets/track                     # Track a placed bet
POST /live/bets/grade/{bet_id}            # Grade bet (WIN/LOSS/PUSH)
GET  /live/bets/history                   # Bet history with stats
```
See `FRONTEND_HANDOFF_CLICK_TO_BET.md` for frontend integration guide.

### Parlay Builder Endpoints
```
GET    /live/parlay/{user_id}                   # Get current parlay slip
POST   /live/parlay/add                         # Add leg to parlay
DELETE /live/parlay/remove/{user_id}/{leg_id}   # Remove leg
DELETE /live/parlay/clear/{user_id}             # Clear parlay slip
POST   /live/parlay/place                       # Track placed parlay
POST   /live/parlay/grade/{parlay_id}           # Grade parlay (WIN/LOSS/PUSH)
GET    /live/parlay/history                     # Parlay history with stats
POST   /live/parlay/calculate                   # Preview odds calculation
```

### Management Endpoints
```
GET /live/cache/stats           # Cache statistics
GET /live/cache/clear           # Clear cache
GET /live/api-health            # Quick API status (for dashboards)
GET /live/api-usage             # Full API usage with warnings
GET /live/playbook/usage        # Playbook plan + quota
GET /live/playbook/health       # Playbook API health check
GET /live/odds-api/usage        # Odds API requests remaining
GET /live/lstm/status           # LSTM status
GET /live/grader/status         # Auto-grader status
GET /live/grader/weights/{sport}# Prediction weights
GET /live/scheduler/status      # Scheduler status
```

### Supported Sports
`nba`, `nfl`, `mlb`, `nhl`

---

## Testing

```bash
# Local
python main.py
curl http://localhost:8000/health

# Production
curl https://web-production-7b2a.up.railway.app/health
curl https://web-production-7b2a.up.railway.app/live/best-bets/nba
```

---

## Git Workflow

- Main production code is on `main` branch
- Feature branches: `claude/feature-name-xxxxx`
- Always commit with descriptive messages
- Push with `git push -u origin branch-name`

### PR Handoffs for External Repos

When providing file updates for PRs (especially for frontend repos), **always provide the complete file content** so the user can:
1. Go to GitHub web editor
2. Select all (Ctrl+A) and delete
3. Paste the complete new file
4. Commit/PR

**Do NOT** give partial instructions like "change X to Y" or "add this after line 5" - this creates guesswork. Always provide the full file ready to copy-paste.

**Always provide direct GitHub links** - don't give step-by-step navigation like "click src, then services, then api.js". Just provide the full URL:
- Edit file: `https://github.com/{owner}/{repo}/edit/{branch}/{path}`
- View file: `https://github.com/{owner}/{repo}/blob/{branch}/{path}`

---

## Key Decisions

1. **In-memory TTL cache** over Redis (single instance for now)
2. **Optional auth** disabled by default (enable in Railway env vars)
3. **JARVIS weight doubled** to 4 max points (was 2)
4. **Async httpx** over sync requests library
5. **Deterministic RNG** for fallback data (stable across requests)

---

## Common Tasks

### Add New Endpoint
1. Add route in `live_data_router.py`
2. Follow async pattern with caching
3. Use standardized response schema
4. Update HANDOFF.md if significant

### Modify Scoring
- AI Models: `advanced_ml_backend.py` → `MasterPredictionSystem`
- JARVIS: `live_data_router.py:233-239` → `JARVIS_TRIGGERS`
- Esoteric: `live_data_router.py` → `get_daily_energy()`

### Debug Deployment
1. Check Railway logs
2. Verify PORT is read via Python `os.environ.get()`
3. Ensure `railway.toml` uses `python main.py`

---

## Session Log: January 16, 2026 - Pre-Launch Audit

### What Was Done

**1. Critical Auto-Grader Bug Fixes**
Fixed 3 bugs that would have broken the self-improvement system in production:

| Bug | File | Fix |
|-----|------|-----|
| Singleton not used | `live_data_router.py` | Changed all grader endpoints to use `get_grader()` instead of `AutoGrader()` |
| Missing method | `auto_grader.py` | Added `get_audit_summary()` method |
| Scheduler disconnected | `main.py` | Connected scheduler to auto_grader on startup |

**2. Comprehensive System Audit**
Verified all components are integrated:

- **8 AI Models** in `advanced_ml_backend.py` - All present
- **5 Context Features** in `context_layer.py` - All present
- **10+ Esoteric Signals** in `esoteric_engine.py` - All present
- **LSTM Brain** in `lstm_brain.py` - Working with TF fallback
- **67 API Endpoints** in `live_data_router.py` - All verified

**3. Commit Pushed**
```
fix: Critical auto-grader bugs for production launch
```

---

## Launch Day Testing Checklist

Run these tests before going live:

### 1. Health Checks
```bash
# Backend health
curl "https://web-production-7b2a.up.railway.app/health"

# Live router health
curl "https://web-production-7b2a.up.railway.app/live/health" -H "X-API-Key: YOUR_KEY"

# API usage (check quotas)
curl "https://web-production-7b2a.up.railway.app/live/api-health" -H "X-API-Key: YOUR_KEY"
```

### 2. Core Data Endpoints
```bash
# Best bets (SMASH Spots)
curl "https://web-production-7b2a.up.railway.app/live/best-bets/nba" -H "X-API-Key: YOUR_KEY"

# Player props
curl "https://web-production-7b2a.up.railway.app/live/props/nba" -H "X-API-Key: YOUR_KEY"

# Splits
curl "https://web-production-7b2a.up.railway.app/live/splits/nba" -H "X-API-Key: YOUR_KEY"

# Lines
curl "https://web-production-7b2a.up.railway.app/live/lines/nba" -H "X-API-Key: YOUR_KEY"
```

### 3. Self-Improvement System
```bash
# Grader status (should show available: true)
curl "https://web-production-7b2a.up.railway.app/live/grader/status" -H "X-API-Key: YOUR_KEY"

# Scheduler status (should show available: true)
curl "https://web-production-7b2a.up.railway.app/live/scheduler/status" -H "X-API-Key: YOUR_KEY"

# Current weights
curl "https://web-production-7b2a.up.railway.app/live/grader/weights/nba" -H "X-API-Key: YOUR_KEY"

# Performance metrics
curl "https://web-production-7b2a.up.railway.app/live/grader/performance/nba" -H "X-API-Key: YOUR_KEY"

# Daily report
curl "https://web-production-7b2a.up.railway.app/live/grader/daily-report" -H "X-API-Key: YOUR_KEY"
```

### 4. Esoteric Features
```bash
# Today's energy
curl "https://web-production-7b2a.up.railway.app/esoteric/today-energy"

# Esoteric edge
curl "https://web-production-7b2a.up.railway.app/live/esoteric-edge" -H "X-API-Key: YOUR_KEY"

# Noosphere
curl "https://web-production-7b2a.up.railway.app/live/noosphere/status" -H "X-API-Key: YOUR_KEY"
```

### 5. Betting Features
```bash
# Line shopping
curl "https://web-production-7b2a.up.railway.app/live/line-shop/nba" -H "X-API-Key: YOUR_KEY"

# Sportsbooks list
curl "https://web-production-7b2a.up.railway.app/live/sportsbooks" -H "X-API-Key: YOUR_KEY"

# Affiliate links
curl "https://web-production-7b2a.up.railway.app/live/affiliate/links" -H "X-API-Key: YOUR_KEY"
```

### 6. Community Features
```bash
# Leaderboard
curl "https://web-production-7b2a.up.railway.app/live/community/leaderboard" -H "X-API-Key: YOUR_KEY"
```

### Expected Results

| Test | Expected |
|------|----------|
| `/health` | `{"status": "healthy"}` |
| `/live/grader/status` | `{"available": true, "predictions_logged": N}` |
| `/live/scheduler/status` | `{"available": true, "apscheduler_available": true}` |
| `/live/best-bets/nba` | Returns `props` and `game_picks` arrays |
| `/esoteric/today-energy` | Returns `betting_outlook` and `overall_energy` |

### If Tests Fail

1. Check Railway logs: `railway logs`
2. Verify environment variables are set
3. Check API quotas aren't exhausted
4. Restart Railway deployment if needed

---

## System Architecture Summary

```
┌─────────────────────────────────────────────────────────────┐
│                    BOOKIE-O-EM v14.2                        │
├─────────────────────────────────────────────────────────────┤
│  main.py (FastAPI)                                          │
│    ├── live_data_router.py (67 endpoints)                   │
│    ├── scheduler_router (daily_scheduler.py)                │
│    └── esoteric endpoint (/esoteric/today-energy)           │
├─────────────────────────────────────────────────────────────┤
│  PREDICTION ENGINE                                          │
│    ├── advanced_ml_backend.py (8 AI Models)                 │
│    ├── lstm_brain.py (Neural Network)                       │
│    ├── context_layer.py (5 Context Features)                │
│    └── esoteric_engine.py (10+ Esoteric Signals)            │
├─────────────────────────────────────────────────────────────┤
│  SELF-IMPROVEMENT                                           │
│    ├── auto_grader.py (Feedback Loop)                       │
│    │     └── get_grader() singleton                         │
│    └── daily_scheduler.py (6 AM Audit)                      │
├─────────────────────────────────────────────────────────────┤
│  EXTERNAL APIs                                              │
│    ├── Odds API (odds, lines, props)                        │
│    └── Playbook API (splits, injuries, stats)               │
└─────────────────────────────────────────────────────────────┘
```

---

## Code Simplifier Agent

**Name:** code-simplifier
**Model:** opus
**Purpose:** Simplifies and refines code for clarity, consistency, and maintainability while preserving all functionality.

### When to Use
- After writing or modifying code
- To refine recently touched code sections
- To apply project standards consistently

### Principles

1. **Preserve Functionality**: Never change what code does - only how it does it
2. **Apply Project Standards**: Follow CLAUDE.md coding standards
3. **Enhance Clarity**: Reduce complexity, eliminate redundancy, improve naming
4. **Maintain Balance**: Avoid over-simplification that reduces maintainability
5. **Focus Scope**: Only refine recently modified code unless instructed otherwise

### Code Standards (Python)

- Use async functions with type hints
- Prefer explicit over implicit
- Choose clarity over brevity
- Remove unnecessary comments that describe obvious code

### What NOT to Do

- Change functionality or outputs
- Create overly clever solutions
- Combine too many concerns into single functions
- Remove helpful abstractions
- Prioritize "fewer lines" over readability

---

## Session Log: January 16, 2026 - Backend API Audit

### What Was Done

**1. Backend API Audit (76 Endpoints)**
Audited all FastAPI route handlers:

| File | Routes | Issues Found |
|------|--------|--------------|
| `main.py` | 7 | None |
| `live_data_router.py` | 69 | Missing input validation |

**2. Pydantic Validation Models Added**
Created `models/api_models.py` with request validation:

| Model | Validates |
|-------|-----------|
| `TrackBetRequest` | Sport codes, American odds format, required fields |
| `GradeBetRequest` | WIN/LOSS/PUSH enum |
| `ParlayLegRequest` | Odds format, sport, game_id |
| `PlaceParlayRequest` | Sportsbook required, stake >= 0 |
| `UserPreferencesRequest` | Nested notifications object |

**3. Endpoints Updated with Validation**
- `POST /bets/track` - Now validates odds (-110 valid, -50 invalid)
- `POST /bets/grade/{bet_id}` - Enum validation
- `POST /parlay/add` - Odds + sport validation
- `POST /parlay/place` - Required fields
- `POST /parlay/grade/{parlay_id}` - Enum validation
- `POST /user/preferences/{user_id}` - Nested object handling

### Files Changed

```
models/api_models.py          (NEW - Pydantic models)
models/__init__.py            (NEW - Package init)
live_data_router.py           (MODIFIED - Validation added)
```

---

## Session Log: January 17, 2026 - Server-Side Data Fetching

### What Was Done

**1. Created Consolidated Endpoints**

Added 3 new endpoints to reduce client-side API waterfalls:

| Endpoint | Replaces | Improvement |
|----------|----------|-------------|
| `GET /live/sport-dashboard/{sport}` | 6 calls (best-bets, splits, lines, injuries, sharp, props) | 83% reduction |
| `GET /live/game-details/{sport}/{game_id}` | 5 calls (lines, props, sharp, injuries, best-bets) | 80% reduction |
| `GET /live/parlay-builder-init/{sport}` | 3 calls (best-bets, props, correlations) | 67% reduction |

**Implementation Details:**
- Uses `asyncio.gather()` to fetch all data in parallel server-side
- Graceful error handling - returns partial data if individual fetches fail
- Caches consolidated response (2-3 minute TTL)
- User-specific data (parlay slip) fetched separately to maintain cache efficiency

**2. Marked `/learning/*` Endpoints as Deprecated**

All 6 endpoints marked with `deprecated=True`:
- `/learning/log-pick` → Use `/grader/*`
- `/learning/grade-pick` → Use `/grader/*`
- `/learning/performance` → Use `/grader/performance/{sport}`
- `/learning/weights` → Use `/grader/weights/{sport}`
- `/learning/adjust-weights` → Use `/grader/adjust-weights/{sport}`
- `/learning/recent-picks` → Use `/grader/*`

Will be removed in v15.0.

**3. Added Helper Functions**
- `get_parlay_correlations()` - Static correlation matrix for SGP
- `calculate_parlay_odds_internal()` - Parlay odds calculation helper

### Files Changed

```
live_data_router.py   (MODIFIED - Added 3 consolidated endpoints, deprecated /learning/*)
CLAUDE.md             (MODIFIED - Documented new endpoints + session log)
```

### Testing

```bash
# Test consolidated dashboard endpoint
curl "https://web-production-7b2a.up.railway.app/live/sport-dashboard/nba" -H "X-API-Key: YOUR_KEY"

# Test game details endpoint
curl "https://web-production-7b2a.up.railway.app/live/game-details/nba/GAME_ID" -H "X-API-Key: YOUR_KEY"

# Test parlay builder init
curl "https://web-production-7b2a.up.railway.app/live/parlay-builder-init/nba?user_id=test123" -H "X-API-Key: YOUR_KEY"
```

### Frontend Integration

Update frontend to use consolidated endpoints:

**Before (6 calls):**
```javascript
const bestBets = await fetch('/live/best-bets/nba');
const splits = await fetch('/live/splits/nba');
const lines = await fetch('/live/lines/nba');
const injuries = await fetch('/live/injuries/nba');
const sharp = await fetch('/live/sharp/nba');
```

**After (1 call):**
```javascript
const dashboard = await fetch('/live/sport-dashboard/nba');
// All data in: dashboard.best_bets, dashboard.market_overview, dashboard.context
```

---

## Session Log: January 17, 2026 - CLAUDE.md Cleanup

### What Was Done

**1. Removed Vercel/React Content**

Removed ~200 lines of frontend-focused content that didn't apply to this Python/FastAPI backend:

| Removed Section | Reason |
|-----------------|--------|
| Vercel Agent Skills (5 skills) | React/Next.js only, not Python |
| Agent Rules (Strict) | React-specific rules |
| react-best-practices docs | Frontend skill |
| react-strict-rules docs | Frontend skill |
| web-design-guidelines docs | UI/accessibility for frontend |
| vercel-deploy-claimable docs | Vercel deployment (we use Railway) |
| json-ui-composer docs | JSON UI generation |

**2. Cleaned Up Session Logs**

- Removed Vercel skills installation from Jan 16 log
- Kept Pydantic validation work (still relevant)
- Updated Code Standards to Python-specific

### Why This Change

This is a **Python/FastAPI backend deployed on Railway**, not a React/Next.js app on Vercel. The Vercel skills:
- Were installed but never applicable here
- Added confusion to the project instructions
- Should live in the frontend repo (`bookie-member-app`) if needed

---

## Python/FastAPI Best Practices

**ALWAYS apply these rules when working on this backend.**

### 1. Async & Performance (CRITICAL)

```python
# ✅ CORRECT: Use async for all handlers
@router.get("/endpoint")
async def get_endpoint():
    pass

# ✅ CORRECT: Use httpx for async HTTP calls
async with httpx.AsyncClient() as client:
    resp = await client.get(url)

# ❌ WRONG: Sync requests library blocks event loop
import requests
resp = requests.get(url)  # NEVER do this

# ✅ CORRECT: Parallel fetching with asyncio.gather
results = await asyncio.gather(
    fetch_data_1(),
    fetch_data_2(),
    fetch_data_3(),
    return_exceptions=True  # Don't fail all if one fails
)

# ❌ WRONG: Sequential fetching (waterfall)
data1 = await fetch_data_1()
data2 = await fetch_data_2()
data3 = await fetch_data_3()
```

### 2. Input Validation (CRITICAL)

```python
# ✅ CORRECT: Pydantic models for request validation
from pydantic import BaseModel, Field, validator

class TrackBetRequest(BaseModel):
    sport: str = Field(..., regex="^(NBA|NFL|MLB|NHL)$")
    odds: int = Field(..., le=-100) | Field(..., ge=100)
    stake: float = Field(default=0, ge=0)

@router.post("/bets/track")
async def track_bet(bet_data: TrackBetRequest):
    pass  # Pydantic validates before handler runs

# ✅ CORRECT: Validate and cap limits
limit = min(max(1, limit), 500)  # Between 1-500

# ❌ WRONG: Trust user input directly
limit = request.query_params.get("limit")  # Could be 999999
```

### 3. Error Handling (HIGH)

```python
# ✅ CORRECT: Explicit status codes
if resp.status_code == 429:
    raise HTTPException(status_code=503, detail="Rate limited")

if resp.status_code != 200:
    raise HTTPException(status_code=502, detail=f"API error: {resp.status_code}")

# ✅ CORRECT: Graceful degradation with fallback
try:
    data = await fetch_from_api()
except Exception:
    logger.exception("API failed, using fallback")
    data = generate_fallback_data()

# ❌ WRONG: Generic exception swallowing
try:
    data = await fetch_from_api()
except:
    pass  # Silent failure, returns None
```

### 4. Caching (HIGH)

```python
# ✅ CORRECT: Check cache first, set after fetch
cache_key = f"endpoint:{sport}"
cached = api_cache.get(cache_key)
if cached:
    return cached

data = await fetch_data()
api_cache.set(cache_key, data, ttl=300)  # 5 min default
return data

# Cache TTL guidelines:
# - best-bets: 120s (2 min) - changes frequently
# - splits/lines: 300s (5 min) - moderate
# - injuries: 300s (5 min) - moderate
# - consolidated endpoints: 120s (2 min) - match shortest TTL
```

### 5. Authentication (HIGH)

```python
# ✅ CORRECT: Auth on all mutating endpoints
@router.post("/bets/track")
async def track_bet(
    data: TrackBetRequest,
    auth: bool = Depends(verify_api_key)  # REQUIRED
):
    pass

# ✅ CORRECT: Auth on sensitive GET endpoints
@router.get("/bets/history")
async def get_history(auth: bool = Depends(verify_api_key)):
    pass

# Health checks are public (for Railway)
@router.get("/health")
async def health():  # No auth - must be accessible
    return {"status": "healthy"}
```

### 6. Response Normalization (MEDIUM)

```python
# ✅ CORRECT: Consistent response schema
return {
    "sport": sport.upper(),
    "source": "playbook" | "odds_api" | "fallback",
    "count": len(data),
    "data": data,
    "timestamp": datetime.now().isoformat()
}

# ✅ CORRECT: Include cache info for debugging
return {
    "data": data,
    "cache_info": {"hit": True, "ttl_remaining": 120}
}
```

### 7. Logging (MEDIUM)

```python
# ✅ CORRECT: Structured logging
logger.info("Fetched %d games for %s", len(games), sport)
logger.exception("Failed to fetch: %s", e)
logger.warning("Rate limited by %s", api_name)

# ❌ WRONG: Print statements
print(f"Got {len(games)} games")  # NEVER use print
```

### 8. Type Hints (MEDIUM)

```python
# ✅ CORRECT: Full type hints
async def fetch_data(sport: str, limit: int = 50) -> Dict[str, Any]:
    pass

async def get_games(sport: str) -> List[Dict[str, Any]]:
    pass

# ❌ WRONG: Missing types
async def fetch_data(sport, limit=50):
    pass
```

### Pre-Commit Checklist

Before committing any backend code, verify:

- [ ] All handlers use `async def`?
- [ ] Using `httpx` not `requests`?
- [ ] Pydantic validation on POST endpoints?
- [ ] `verify_api_key` on mutating endpoints?
- [ ] Cache check before expensive operations?
- [ ] Proper error handling with HTTPException?
- [ ] Logging instead of print statements?
- [ ] Type hints on function signatures?
- [ ] Limit parameters capped (max 500)?
- [ ] Parallel fetching where possible (asyncio.gather)?

### Quick Reference

| Practice | Implementation |
|----------|----------------|
| Async endpoints | All handlers use `async def` |
| HTTP client | httpx.AsyncClient (not requests) |
| Validation | Pydantic models in `models/api_models.py` |
| Caching | HybridCache with TTL (5 min default) |
| Error handling | HTTPException with status codes |
| Logging | logger.info/warning/exception |
| Auth | `Depends(verify_api_key)` on POST |
| Limits | Cap at 500, validate with min/max |
| Parallel fetch | asyncio.gather(return_exceptions=True) |

---

## Session Log: January 17, 2026 - Backend API Audit

### What Was Done

**1. Complete Endpoint Inventory (83 routes)**

| File | Endpoints | Status |
|------|-----------|--------|
| `main.py` | 6 | Clean |
| `live_data_router.py` | 72 active, 6 deprecated | Fixed |

**2. Security Fixes (P0 Critical)**

Added `verify_api_key` auth to all mutating endpoints:
- `POST /bets/track`
- `POST /bets/grade/{bet_id}`
- `POST /parlay/add`
- `POST /parlay/place`
- `POST /parlay/grade/{parlay_id}`
- `POST /community/vote`
- `POST /affiliate/configure`

**3. DoS Prevention (P0 Critical)**

Added max limit validation to history endpoints:
- `GET /bets/history` - Max 500 results
- `GET /parlay/history` - Max 500 results

**4. Verified Waterfall Elimination**

Consolidated endpoints correctly use `asyncio.gather()`:
- `/sport-dashboard/{sport}` - 5 parallel fetches
- `/game-details/{sport}/{game_id}` - 5 parallel fetches
- `/parlay-builder-init/{sport}` - 2 parallel fetches

### Issues Identified (Future Work)

| Priority | Issue | Status |
|----------|-------|--------|
| P2 | In-memory storage leak risk | Monitor |
| P2 | No pagination on lists | TODO |
| P3 | Response schema inconsistency | Minor |

### Files Changed

```
live_data_router.py   (MODIFIED - Auth + validation)
CLAUDE.md             (MODIFIED - Session log)
```

---

## Session Log: January 18, 2026 - Frontend Compatibility Endpoints

### What Was Done

**1. Frontend API Audit**

Identified gaps between frontend api.js and backend:
- Frontend calling endpoints that don't exist
- Missing methods in api.js for existing endpoints
- Fallback/mock data flowing when live APIs should be used

**2. Created 5 Frontend Compatibility Endpoints**

| Endpoint | Purpose | Data Source |
|----------|---------|-------------|
| `GET /live/games/{sport}` | Live games with odds | Wraps `/lines` with frontend-friendly schema |
| `GET /live/slate/{sport}` | Today's schedule | Derived from `/lines` |
| `GET /live/roster/{sport}/{team}` | Team roster | Injuries data filtered by team |
| `GET /live/player/{player_name}` | Player lookup | Props + injuries combined |
| `POST /live/predict-live` | AI prediction | Filters `/best-bets` by player/game |

**3. All Endpoints Follow Best Practices**

- ✅ `verify_api_key` auth
- ✅ Caching (180-300s TTL)
- ✅ `asyncio.gather()` for parallel fetches
- ✅ Consistent response schemas
- ✅ Type hints and docstrings

### Frontend Integration

Frontend api.js can now use these without changes:

```javascript
// These now work directly
api.getLiveGames('nba')     → GET /live/games/nba
api.getLiveSlate('nba')     → GET /live/slate/nba
api.getRoster('nba', 'lakers') → GET /live/roster/nba/lakers
api.getPlayerStats('lebron')  → GET /live/player/lebron?sport=nba
api.predictLive({...})      → POST /live/predict-live
```

### Files Changed

```
live_data_router.py   (MODIFIED - Added 5 endpoints, +382 lines)
CLAUDE.md             (MODIFIED - Documentation + session log)
```

---

## Session Log: January 18, 2026 - API Integration & Optimization

### What Was Done

**1. Removed ALL Fake/Sample Data**

The backend was generating fake data when APIs failed. This was removed because fake data is useless for real betting decisions.

| Removed | Endpoint |
|---------|----------|
| `generate_fallback_sharp()` | `/live/sharp/{sport}` |
| `generate_fallback_line_shop()` | `/live/line-shop/{sport}` |
| `generate_fallback_betslip()` | `/live/betslip/generate` |
| Fake props from player_birth_data | `/live/props/{sport}` |
| Sample props/game picks | `/live/best-bets/{sport}` |

**2. Added API Diagnostics to Response**

`/live/best-bets/{sport}` now returns diagnostic info:

```json
{
  "api_status": {
    "odds_api_configured": true,
    "playbook_api_configured": true,
    "props_source": "odds_api",
    "props_games_found": 7,
    "sharp_source": "playbook"
  },
  "data_message": "Live data retrieved: 10 prop picks, 10 game picks"
}
```

**3. Cache TTL Set to 10 Minutes (Testing Mode)**

⚠️ **REMINDER: Change to 5 minutes before going live!**

```python
api_cache.set(cache_key, result, ttl=600)  # Currently 10 min for testing
# Change to ttl=300 (5 min) for production
```

**4. Fetch ALL Games for Props**

Changed from fetching only first 5 games to fetching ALL games so no smash picks are missed.

```python
for event in events:  # Fetch ALL games - don't miss any smash picks
```

### API Keys & Configuration

**Railway Environment Variables (8 pillars project):**
```
ODDS_API_KEY=ceb2e3a6a3302e0f38fd0d34150294e9
PLAYBOOK_API_KEY=pbk_d6f65d6a74c53d5ef9b455a9a147c853b82b
```

**Odds API:** 20K credits/month, used for live odds and player props
**Playbook API:** Betting splits, sharp money signals, injuries

### How the APIs Work Together

| API | Role | Data Provided |
|-----|------|---------------|
| **Odds API** | "What can I bet on?" | Live odds, lines, player props from 15+ sportsbooks |
| **Playbook API** | "What should I bet on?" | Betting splits, sharp money detection, injuries |

**Sharp Money Detection:**
- Playbook provides ticket% vs money%
- When money% ≠ ticket%, sharps are moving
- Example: 58% bets on Lakers, 63% money → Sharps on Lakers
- This feeds the `SHARP_MONEY` badge on picks

### API Usage

**Per `/best-bets` call (uncached):**
- ~1 call for sharp money
- ~1 call for events list
- ~N calls for props (one per game, typically 5-10)
- ~1 call for game odds
- **Total: ~8-12 API calls**

**With 10-min cache:** ~48-72 calls/hour max
**With 5-min cache:** ~96-144 calls/hour max

### Testing the Endpoint

```bash
# Test best-bets
curl "https://web-production-7b2a.up.railway.app/live/best-bets/nba" \
  -H "X-API-Key: YOUR_BACKEND_API_KEY"

# Check API usage
curl "https://web-production-7b2a.up.railway.app/live/api-usage" \
  -H "X-API-Key: YOUR_BACKEND_API_KEY"

# Test Odds API directly
curl "https://api.the-odds-api.com/v4/sports/basketball_nba/odds?apiKey=YOUR_ODDS_KEY&regions=us&markets=h2h"

# Test Playbook API directly
curl "https://api.playbook-api.com/v1/splits?league=NBA&api_key=YOUR_PLAYBOOK_KEY"
```

### Response Schema for Frontend

Each pick in `props.picks[]` contains:

```json
{
  "player_name": "LeBron James",
  "stat_type": "player_assists",
  "line": 7.5,
  "over_under": "over",
  "odds": -140,
  "smash_score": 6.29,
  "predicted_value": 9.5,
  "confidence": "MEDIUM",
  "badges": ["SHARP_MONEY", "JARVIS_TRIGGER"],
  "rationale": "LeBron James prop analysis: Sharp money detected...",
  "game": "Los Angeles Lakers @ Portland Trail Blazers",
  "game_time": "2026-01-18T03:13:00Z",
  "source": "odds_api"
}
```

### Before Going Live Checklist

- [ ] Change cache TTL from 10 min → 5 min in `live_data_router.py`
- [ ] Verify Railway is using "8 pillars" project (not "devoted-inspiration")
- [ ] Test all endpoints return real data
- [ ] Monitor API usage first few days

### Railway Setup

**Correct project:** 8 pillars
**Production URL:** https://web-production-7b2a.up.railway.app
**Deleted:** devoted-inspiration (was unused)

---

## Session Log: January 18, 2026 - Scheduled Props Fetching (API Credit Optimization)

### What Was Done

**1. Added Scheduled Props Fetching**

Props are now fetched only twice daily to minimize API credit usage:
- **10 AM ET** - Fresh morning data for community
- **6 PM ET** - Evening refresh for goldilocks zone (news updates)

**2. Updated Cache TTL**

| Endpoint | Old TTL | New TTL | Reason |
|----------|---------|---------|--------|
| `/props/{sport}` | 10 min | **8 hours** | Refreshed by scheduler only |
| Other endpoints | 10 min | 10 min | Still testing mode |

**3. New Scheduler Jobs**

```
┌─────────────────────────────────────────────────────────┐
│  DAILY SCHEDULER v2.0                                   │
├─────────────────────────────────────────────────────────┤
│  6 AM   → Daily Audit (grade picks, adjust weights)    │
│  10 AM  → Props Fetch (all sports, fresh for morning)  │
│  6 PM   → Props Fetch (refresh for evening games)      │
│  Sun 3AM → Weekly Cleanup                              │
└─────────────────────────────────────────────────────────┘
```

### API Credit Savings

**Before (10-min cache):**
- ~8-12 API calls per `/best-bets` request (uncached)
- Worst case: 72-144 calls/hour per sport
- Monthly burn: thousands of credits

**After (scheduled fetch):**
- 2 fetches per day × 4 sports = 8 total props fetches
- ~10-15 calls per fetch = **~100 API calls/day**
- Monthly: ~3,000 calls (vs potentially 100k+)

### New Endpoints

| Endpoint | Purpose |
|----------|---------|
| `POST /scheduler/run-props-fetch` | Manually trigger props refresh |
| `GET /scheduler/status` | Shows next scheduled props fetch |

### Manual Props Refresh

If you need fresh props outside of 10 AM / 6 PM:

```bash
curl -X POST "https://web-production-7b2a.up.railway.app/scheduler/run-props-fetch" \
  -H "X-API-Key: YOUR_KEY"
```

### Files Changed

```
daily_scheduler.py    (MODIFIED - Added PropsFetchJob, 10am+6pm schedule)
live_data_router.py   (MODIFIED - Added cache.delete(), 8-hour props TTL)
CLAUDE.md             (MODIFIED - Session log)
```

---
