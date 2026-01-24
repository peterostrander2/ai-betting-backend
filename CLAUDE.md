# CLAUDE.md - Project Instructions for AI Assistants

## User Environment
- **OS:** Mac
- **Terminal:** Use Mac Terminal commands (no Windows-specific instructions)

---

## Project Overview

**Bookie-o-em** - AI Sports Prop Betting Backend
**Version:** v14.6 / Engine v10.66 PRODUCTION HARDENED
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

### Playbook API v1 Endpoints (9 Total)

**Base URL:** `https://api.playbook-api.com/v1`
**Auth:** `api_key` query parameter (NOT Bearer header)
**Leagues:** NBA | NFL | CFB | MLB | NHL (uppercase)

| Endpoint | Purpose | Required Params |
|----------|---------|-----------------|
| `/health` | Health check | none |
| `/me` | Plan + usage info | `api_key` |
| `/teams` | Team metadata + injuries | `league`, `api_key` |
| `/injuries` | Injury report by team | `league`, `api_key` |
| `/splits` | Public betting splits (ticket% vs money%) | `league`, `api_key` |
| `/splits-history` | Historical splits | `league`, `date`, `api_key` |
| `/odds-games` | Schedule + gameId list | `league`, `api_key` |
| `/lines` | Current + opening lines (for true RLM) | `league`, `api_key` |
| `/games` | Detailed game objects | `league`, `date`, `api_key` |
| `/schedule` | Lightweight schedule | `league`, `api_key` |

### Odds API v4 Endpoints (7 Total)

**Base URL:** `https://api.the-odds-api.com/v4`
**Auth:** `apiKey` query parameter

| Endpoint | Purpose | Credits |
|----------|---------|---------|
| `/sports/{sport}/odds` | Live odds (spreads, totals, ML) | 1/call |
| `/sports/{sport}/events/{id}/odds` | Player props (46+ markets) | 1/call |
| `/sports/{sport}/scores` | Live & final scores | 1/call |
| `/sports/{sport}/odds?markets=alternate_*` | Alternate lines (hooks) | 1/call |
| `/sports/{sport}/odds?markets=team_totals` | Team over/unders | 1/call |
| `/historical/sports/{sport}/odds` | Opening lines | 10/call |
| `/sports/{sport}/events/{id}/markets` | Available markets | 1/call |

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

### Required (Core Betting APIs)
```bash
ODDS_API_KEY=xxx          # The Odds API - Live odds, props, scores
PLAYBOOK_API_KEY=xxx      # Playbook Sports API - Splits, sharp money, injuries
```

### Sports Data APIs
```bash
WEATHER_API_KEY=xxx       # Weather API - Game day weather (outdoor sports)
ASTRONOMY_API_ID=xxx      # Astronomy API - Moon phases, planetary hours (esoteric)
ASTRONOMY_API_SECRET=xxx  # Astronomy API secret
ROTOWIRE_API_KEY=xxx      # RotoWire - Starting lineups, referee assignments
```

### Alternative Data APIs
```bash
FRED_API_KEY=xxx          # Federal Reserve Economic Data - Economic indicators
FINNHUB_KEY=xxx           # Finnhub - Stock data, sportsbook sentiment
SERPAPI_KEY=xxx           # SerpAPI - Search results, news aggregation
TWITTER_BEARER=xxx        # Twitter/X API - Breaking news, injury reports
```

### Platform/Auth APIs
```bash
WHOP_API_KEY=xxx          # Whop - Membership/payment platform
API_AUTH_ENABLED=true     # Enable X-API-Key auth
API_AUTH_KEY=xxx          # Required if auth enabled
```

### Overrides
```bash
ODDS_API_BASE=xxx         # Override Odds API URL
PLAYBOOK_API_BASE=xxx     # Override Playbook API URL
```

### Railway Auto-Set
```bash
PORT=8000                 # Read via os.environ.get("PORT", 8000)
```

---

## All Available API Keys & Use Cases

### Core Betting APIs (CRITICAL)

| Key | Service | Purpose | Integration Status |
|-----|---------|---------|-------------------|
| `ODDS_API_KEY` | The Odds API | Live odds, player props, scores from 15+ books | ✅ Fully integrated |
| `PLAYBOOK_API_KEY` | Playbook API | Betting splits, sharp money, injuries, RLM | ✅ Fully integrated |

### Sports Data APIs

| Key | Service | Purpose | Integration Status |
|-----|---------|---------|-------------------|
| `WEATHER_API_KEY` | WeatherAPI | Game day weather for outdoor sports (MLB, NFL) | ✅ Integrated |
| `ASTRONOMY_API_ID` | Astronomy API | Moon phases, void moon, planetary positions | ✅ Esoteric engine |
| `ASTRONOMY_API_SECRET` | Astronomy API | Auth secret for astronomy data | ✅ Esoteric engine |
| `ROTOWIRE_API_KEY` | RotoWire | Starting lineups, referee assignments, injuries | ⏳ Ready (needs key) |

### Alternative Data APIs (Edge Signals)

| Key | Service | Purpose | Potential Use |
|-----|---------|---------|---------------|
| `FRED_API_KEY` | Federal Reserve | Economic indicators, consumer sentiment | Economic cycle correlation with betting patterns |
| `FINNHUB_KEY` | Finnhub | Stock market data, company financials | Track DraftKings/FanDuel stock as sentiment proxy |
| `SERPAPI_KEY` | SerpAPI | Google search results | News aggregation, trending injury stories |
| `TWITTER_BEARER` | Twitter/X | Social media posts | Breaking news from beat reporters, injury alerts |

### Platform APIs

| Key | Service | Purpose | Integration Status |
|-----|---------|---------|-------------------|
| `WHOP_API_KEY` | Whop | Membership/payments | User subscription management |

### Alternative Data Integration Ideas

**FRED API (Economic Data):**
- Track Consumer Sentiment Index - correlates with public betting behavior
- Monitor unemployment data - affects discretionary spending on betting
- Interest rates impact on sportsbook stocks

**Finnhub API (Financial Data):**
- Track $DKNG (DraftKings) and $FLTR (Flutter/FanDuel) stock prices
- Large stock drops = potential operational issues
- Earnings reports affect odds accuracy

**SerpAPI (Search/News):**
- Aggregate injury news from Google News
- Monitor trending player names (breakout games)
- Track "upset" searches before games

**Twitter API (Social Signals):**
- Follow beat reporters for each team
- Breaking injury news (often 15-30 min before official)
- Player mood/confidence from social posts
- Public sentiment analysis on matchups

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

Props are now fetched on a smart schedule to minimize API credit usage:

**Weekdays (Mon-Fri):**
- **10 AM ET** - Fresh morning data for community
- **6 PM ET** - Evening refresh for goldilocks zone

**Weekends (Sat-Sun):**
- **10 AM ET** - Morning data
- **12 PM ET** - Noon games refresh
- **2 PM ET** - Afternoon games refresh
- **6 PM ET** - Evening games refresh

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
│  6 AM      → Daily Audit (grade picks, adjust weights) │
│  10 AM     → Props Fetch (daily - morning)             │
│  12 PM     → Props Fetch (weekends only - noon games)  │
│  2 PM      → Props Fetch (weekends only - afternoon)   │
│  6 PM      → Props Fetch (daily - evening)             │
│  Sun 3 AM  → Weekly Cleanup                            │
└─────────────────────────────────────────────────────────┘
```

### API Credit Savings

**Before (10-min cache):**
- ~8-12 API calls per `/best-bets` request (uncached)
- Worst case: 72-144 calls/hour per sport
- Monthly burn: thousands of credits

**After (scheduled fetch):**
- Weekdays: 2 fetches/day × 4 sports = 8 props fetches
- Weekends: 4 fetches/day × 4 sports = 16 props fetches
- ~10-15 calls per fetch = **~120-180 API calls/day**
- Monthly: ~4,000-5,000 calls (vs potentially 100k+)

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

## Session Log: January 18, 2026 - Ultimate Confluence Production v3

### The Problem

Zero actionable picks were being generated because:
1. **pillar_score was HARDCODED** to 2.0 (should be dynamic 0-8)
2. **Thresholds too high**: GOLD_STAR required 9.0+ (mathematically unreachable)
3. **Context modifiers not applied**: Vacuum, Refs, Weather calculated but not used
4. **No explainability**: No `reasons[]` showing WHY a pick scored high/low

### What Was Fixed

**1. Replaced Hardcoded pillar_score with 8 Pillars System**

| Pillar | Props Weight | Games Weight |
|--------|--------------|--------------|
| Sharp Money (STRONG) | +1.0 | +3.0 |
| Sharp Money (MODERATE) | +0.5 | +1.5 |
| Reverse Line Move (RLM) | +1.0 | +1.0 |
| Public Fade (>70%) | +0.5 | +0.5 |
| Goldilocks (spread 4-9) | +0.3 | +0.3 |
| Trap Gate (>15) | -1.0 | -1.0 |
| High Total (>230) | +0.2 | +0.2 |
| Multi-Pillar Confluence | +0.3 | +0.3 |

**2. Fixed Scoring Thresholds**

| Tier | Old | New |
|------|-----|-----|
| GOLD_STAR | >= 9.0 | >= 7.5 |
| EDGE_LEAN | >= 7.5 | >= 6.5 |
| MONITOR | >= 6.0 | >= 5.5 |
| PASS | < 6.0 | < 5.5 |

**3. Deflated Confluence Boosts**

| Level | Old Boost | New Boost |
|-------|-----------|-----------|
| IMMORTAL | +10 | +1.0 |
| JARVIS_PERFECT | +7 | +0.6 |
| PERFECT | +5 | +0.4 |
| STRONG | +3 | +0.3 |
| MODERATE | +1 | +0.0 |

**4. Added Explainability (reasons[] array)**

Every pick now includes a `reasons` array showing exactly why it scored:
```json
{
  "reasons": [
    "RESEARCH: Sharp Split (Game) +3.0",
    "RESEARCH: Reverse Line Move +1.0",
    "ESOTERIC: Jarvis Trigger 33 +0.4",
    "CONFLUENCE: Perfect Alignment +0.4"
  ]
}
```

**5. Volume Governor**
- Max 3 GOLD_STAR picks per category (prevents over-confidence)
- Fallback fill: Always return at least 3 actionable picks
- Governor actions tracked in reasons[]

**6. Fixed game picks base_ai**
- Changed from 4.5 to 5.0 (was causing games to score lower than props)

**7. Added Debug Mode**
```bash
curl "https://web-production-7b2a.up.railway.app/live/best-bets/nba?debug=1"
```

Returns diagnostic info: `games_pulled`, `candidates_scored`, `returned_picks`, `volume_governor_applied`

### Expected Results

| Metric | Before | After |
|--------|--------|-------|
| pillar_score | 2.0 (always) | 0-8 (dynamic) |
| research_score | 4.38 | 5.5-7.5 |
| FINAL score | 6.22 | 6.5-9.0 |
| Tier | MONITOR | EDGE_LEAN / GOLD_STAR |
| Actionable picks | 0% | 30-50% |

### Files Changed

```
jarvis_savant_engine.py   (MODIFIED - Thresholds, confluence boosts)
live_data_router.py       (MODIFIED - 8 Pillars, Volume Governor, debug mode)
CLAUDE.md                 (MODIFIED - Session log)
```

### Verification

After merging, run:
```bash
curl -s "https://web-production-7b2a.up.railway.app/live/best-bets/nba?debug=1" | \
  jq '(.picks // [])[0] | {tier, final_score, reasons}'
```

Expected: `tier` = "GOLD_STAR" or "EDGE_LEAN", `reasons[]` populated

---

## Session Log: January 20, 2026 - Props Scoring Fix v10.17

### The Problem

Props picks were returning empty for GOLD_STAR and EDGE_LEAN tiers.

Diagnostic commands showed:
- Game picks: EDGE_LEAN tier working correctly
- Props picks: All MONITOR tier (never reaching actionable thresholds)

### Root Cause Analysis

Props scoring was mathematically suppressed due to compounding multipliers:

| Factor | Props Value | Games Value |
|--------|-------------|-------------|
| base_ai | 5.8 | 5.8 |
| scope_mult (sharp pillars) | 0.5x | 1.0x |
| direction_mult (NEUTRAL) | 0.5x | N/A |
| **Combined final_mult** | **0.25x** | **1.0x** |

**Math for NEUTRAL prop with STRONG sharp:**
- Sharp boost = 1.0 × 0.5 × 0.5 = **0.25** (vs games 2.0)
- research_score = 5.8 + 0.25 = 6.05
- final = (6.05 × 0.67) + (5 × 0.33) = **5.7** → MONITOR

### What Was Fixed

**1. Doubled BASE_SHARP_SPLIT_BOOST and BASE_RLM_BOOST (1.0 → 2.0)**

| Constant | Old | New | Effect |
|----------|-----|-----|--------|
| BASE_SHARP_SPLIT_BOOST | 1.0 | 2.0 | ALIGNED props get 1.0 boost |
| BASE_RLM_BOOST | 1.0 | 2.0 | Reverse line move parity |

**2. Raised props base_ai (5.8 → 6.0)**

Props now start 0.2 higher to compensate for reduced pillar weights.

### Expected Results (After Fix)

| Prop Type | Old Final | New Final | Tier |
|-----------|-----------|-----------|------|
| ALIGNED + STRONG sharp | 6.5 | 7.2 | EDGE_LEAN |
| NEUTRAL + STRONG sharp | 5.7 | 6.5 | EDGE_LEAN |
| ALIGNED + multiple pillars | 6.8 | 7.6 | GOLD_STAR |

### Files Changed

```
live_data_router.py   (MODIFIED - v10.17 props scoring fix)
CLAUDE.md             (MODIFIED - Session log)
```

### Verification

After deploy, run:
```bash
curl -s "https://web-production-7b2a.up.railway.app/live/best-bets/nba" \
  -H "X-API-Key: YOUR_KEY" | jq '(.props.picks // [])[] | select(.tier == "GOLD_STAR" or .tier == "EDGE_LEAN") | {player_name, tier, smash_score}'
```

Expected: At least 1-3 EDGE_LEAN or GOLD_STAR props returned.

---

## Complete API Coverage (v10.65)

### Summary

We pay for **Odds API** and **Playbook API**. As of v10.65, we utilize ALL available features from both subscriptions.

### Odds API Endpoints (7 Total)

| Endpoint | Purpose | Credits | Used In |
|----------|---------|---------|---------|
| `/v4/sports/{sport}/odds` | Live odds from 15+ books | 1/call | `/live/lines`, `/live/best-bets` |
| `/v4/sports/{sport}/events/{id}/odds?markets=` | Player props (46+ markets) | 1/call | `/live/props`, `/live/best-bets` |
| `/v4/sports/{sport}/scores` | Live & final scores | 1/call | `/live/scores` (auto-grading) |
| `/v4/sports/{sport}/odds?oddsFormat=american&markets=alternate_spreads,alternate_totals` | Alternate lines (hooks) | 1/call | `/live/alternate-lines` |
| `/v4/sports/{sport}/odds?markets=team_totals` | Team over/unders | 1/call | `/live/team-totals` |
| `/v4/historical/sports/{sport}/odds` | Opening lines | 10/call | `/live/historical-odds` |
| `/v4/sports/{sport}/events/{id}/markets` | Available markets | 1/call | `/live/available-markets` |

### Player Prop Markets by Sport (46+ Total)

**NBA (13 markets):**
```
player_points, player_rebounds, player_assists, player_threes,
player_blocks, player_steals, player_turnovers,
player_points_rebounds_assists, player_points_rebounds,
player_points_assists, player_rebounds_assists,
player_double_double, player_first_basket
```

**NFL (14 markets):**
```
player_pass_tds, player_pass_yds, player_pass_completions, player_pass_attempts,
player_pass_interceptions, player_rush_yds, player_rush_attempts,
player_reception_yds, player_receptions, player_anytime_td,
player_kicking_points, player_field_goals_made,
player_tackles_assists, player_sacks
```

**MLB (11 markets):**
```
batter_hits, batter_total_bases, batter_rbis, batter_runs_scored,
batter_walks, batter_strikeouts, batter_stolen_bases,
pitcher_strikeouts, pitcher_hits_allowed, pitcher_walks,
pitcher_outs
```

**NHL (8 markets):**
```
player_points, player_assists, player_shots_on_goal,
player_blocked_shots, player_power_play_points,
goalie_saves, player_anytime_goalscorer,
player_first_goalscorer
```

### Playbook API Endpoints (9 Total)

| Endpoint | Purpose | Used In |
|----------|---------|---------|
| `/v1/splits` | Betting splits (ticket% vs money%) | `/live/splits`, `/live/sharp` |
| `/v1/lines` | Current + opening lines | True RLM detection |
| `/v1/injuries` | Injury reports | `/live/injuries` |
| `/v1/odds-games` | Game schedule with IDs | `/live/slate` |
| `/v1/teams` | Team metadata | `/live/playbook/teams` |
| `/v1/splits-history` | Historical splits | `/live/playbook/splits-history` |
| `/v1/games` | Detailed game objects | `/live/playbook/games` |
| `/v1/schedule` | Lightweight schedule | `/live/playbook/schedule` |
| `/v1/me` | Plan + usage info | `/live/playbook/usage` |

### Additional Data Sources

**RotoWire API (Optional):**
- Starting lineups
- Referee assignments
- Injury news

**Free APIs (Fallback):**
- ESPN (player stats for grading)
- BallDontLie (NBA backup)
- NOAA (space weather for esoteric)

### New Endpoints Added (v10.63-v10.65)

| Version | Endpoint | Purpose |
|---------|----------|---------|
| v10.64 | `GET /live/scores/{sport}` | Live/final scores for auto-grading |
| v10.64 | `GET /live/alternate-lines/{sport}` | Hook shopping (alt spreads/totals) |
| v10.64 | `GET /live/team-totals/{sport}` | Individual team over/unders |
| v10.64 | `GET /live/historical-odds/{sport}` | Opening lines (10 credits) |
| v10.64 | `GET /live/available-markets/{sport}/{event_id}` | Discover markets per game |
| v10.65 | `GET /live/period-markets/{sport}?period=q1` | First quarter/half betting |
| v10.65 | `GET /live/playbook/teams/{sport}` | Team metadata |
| v10.65 | `GET /live/playbook/schedule/{sport}` | Lightweight schedule |
| v10.65 | `GET /live/playbook/games/{sport}` | Detailed game objects |
| v10.65 | `GET /live/playbook/splits-history/{sport}?date=` | Historical splits |
| v10.65 | `GET /api-coverage` | Full API inventory summary |

### True RLM Detection (v10.63)

**What Changed:**
- Now fetch Playbook `/lines` endpoint in parallel with `/splits`
- Extract `opening_line` and `current_line` from lines data
- Calculate `line_movement = current - opening`
- Detect true RLM when public betting one way but line moved opposite

**Sharp Signal Response:**
```json
{
  "game_id": "abc123",
  "sharp_direction": "HOME",
  "money_pct": 63,
  "ticket_pct": 45,
  "rlm_detected": true,
  "line_movement": -1.5,
  "opening_line": -3.5,
  "current_line": -5.0
}
```

**RLM Pillar Scoring:**
```python
if rlm_detected and line_movement >= 0.5:
    movement_factor = min(2.0, 1.0 + (line_movement / 2.0))  # 1.0-2.0 based on movement
    boost = movement_factor * mw_rlm
    research_reasons.append(f"RESEARCH: RLM Confirmed ({opening_line:.1f}→{current_line:.1f}) +{boost:.2f}")
```

### API Coverage Summary Endpoint

Check what APIs are configured and being used:

```bash
curl "https://web-production-7b2a.up.railway.app/api-coverage"
```

Response:
```json
{
  "odds_api": {
    "configured": true,
    "endpoints": ["odds", "events", "scores", "alternate_lines", "team_totals", "historical_odds", "available_markets"],
    "prop_markets": { "nba": 13, "nfl": 14, "mlb": 11, "nhl": 8, "total": 46 }
  },
  "playbook_api": {
    "configured": true,
    "endpoints": ["splits", "lines", "injuries", "odds-games", "teams", "splits-history", "games", "schedule", "me"]
  },
  "rotowire_api": {
    "configured": false,
    "features": ["starting_lineups", "referee_assignments", "injury_news"]
  }
}
```

---

## Session Log: January 23, 2026 - v10.48 Tier A/B Split + Action Leans

### What Was Done

**1. Tier A/B Split for /best-bets/all**

Separated picks into two tiers for better risk management:

| Tier | Name | Score Range | Max Picks | Max Units |
|------|------|-------------|-----------|-----------|
| **A** | Official Card | ≥ 7.05 (GOLD_STAR + EDGE_LEAN) | 14 | No limit |
| **B** | Action Leans | 6.70 ≤ score < 7.05 | 10 | 1.0 |

**2. Backwards Compatibility**

Existing clients reading `all_picks` + `summary` are unaffected:
- `all_picks` contains ONLY Tier A (Official Card)
- `summary.props_count / games_count / gold_star_count / edge_lean_count` = Tier A only

**3. New Response Fields**

```json
{
  "action_leans": {
    "count": 8,
    "picks": [...],
    "threshold_min": 6.70,
    "threshold_max": 7.05,
    "max_units": 1.0
  },
  "summary": {
    "official_count": 14,
    "action_leans_count": 8,
    "total_published_count": 22
  }
}
```

**4. Debug Block**

```json
{
  "debug": {
    "action_leans": {
      "threshold_min": 6.70,
      "threshold_max": 7.05,
      "max_published": 10,
      "candidates_before_filter": 25,
      "candidates_after_dedup": 18,
      "published": 8
    }
  }
}
```

**5. Hard Guarantees Enforced**

| Guarantee | Enforcement |
|-----------|-------------|
| Tier B score 6.70 ≤ x < 7.05 | Filter + validation |
| Tier B max 10 picks | Slice after dedup |
| Tier B units ≤ 1.0 | `min(units, 1.0)` |
| Tier B no GOLD_STAR/EDGE_LEAN badges | Filter check |
| Tier A max 14 picks | Slice |

**6. Safety Tests Added**

Three new tests in `test_api.py`:
- `test_tier_b_score_range()` - Validates 6.70 ≤ score < 7.05
- `test_tier_b_no_gold_star_badges()` - No forbidden badges/tiers
- `test_tier_b_max_units()` - Units ≤ 1.0

### Files Changed

```
live_data_router.py   (MODIFIED - v10.48 Tier A/B split, action_leans)
test_api.py           (MODIFIED - 3 new safety tests)
README.md             (MODIFIED - action_leans schema docs)
CLAUDE.md             (MODIFIED - Session log)
```

### Verification

```bash
# Test Tier A/B split
curl -s "https://web-production-7b2a.up.railway.app/live/best-bets/all?debug=1" \
  -H "X-API-Key: YOUR_KEY" | jq '{
    official: .all_picks.count,
    action_leans: .action_leans.count,
    total: .summary.total_published_count,
    debug_action_leans: .debug.action_leans
  }'

# Run safety tests
python test_api.py
```

---

## Session Log: January 23, 2026 - v10.63-v10.65 Complete API Coverage

### Goal

Maximize value from paid API subscriptions (Odds API and Playbook API) by ensuring ALL available features are utilized.

### What Was Done

**v10.63 - True RLM Detection**

The problem: Line history via Odds API was already implemented in legacy code (`playbook_api_service.py`) but not wired to current scoring.

The fix:
- Fetch Playbook `/lines` endpoint in parallel with `/splits` using `asyncio.gather()`
- Extract `opening_line` and `current_line` from lines data
- Calculate `line_movement = current - opening`
- Detect true RLM when public betting one way but line moved opposite
- Updated RLM pillar in `calculate_pick_score()` to use movement_factor scaling (1.0-2.0x)

New fields in sharp signals:
- `rlm_detected`: boolean
- `line_movement`: float (points moved)
- `opening_line`: float
- `current_line`: float

**v10.64 - Full Odds API Utilization**

Added endpoints for all Odds API features we're paying for:

| Endpoint | Purpose | Notes |
|----------|---------|-------|
| `GET /live/scores/{sport}` | Live & final scores | **CRITICAL** for auto-grading picks |
| `GET /live/alternate-lines/{sport}` | Hook shopping | alternate_spreads, alternate_totals |
| `GET /live/team-totals/{sport}` | Individual team O/U | Prop correlation |
| `GET /live/historical-odds/{sport}` | Opening lines | 10 credits/market (use sparingly) |
| `GET /live/available-markets/{sport}/{event_id}` | Market discovery | Know what's available per game |

Expanded player prop markets from ~16 to 46+:
- NBA: 13 markets (added blocks, steals, turnovers, combos, first basket)
- NFL: 14 markets (added tackles/assists, sacks, interceptions)
- MLB: 11 markets (added walks, strikeouts, stolen bases, pitcher outs)
- NHL: 8 markets (added blocked shots, power play points, anytime/first goalscorer)

**v10.65 - Complete API Coverage**

Added remaining Playbook API endpoints:

| Endpoint | Purpose |
|----------|---------|
| `GET /live/period-markets/{sport}?period=q1` | First quarter/half betting |
| `GET /live/playbook/teams/{sport}` | Team metadata |
| `GET /live/playbook/schedule/{sport}` | Lightweight schedule |
| `GET /live/playbook/games/{sport}` | Detailed game objects |
| `GET /live/playbook/splits-history/{sport}?date=` | Historical splits |
| `GET /api-coverage` | Full API inventory summary |

Period market support:
- NBA/NCAAB: q1, q2, q3, q4, h1, h2
- NFL: q1, q2, q3, q4, h1, h2
- MLB: 1st_5_innings, 1st_3_innings
- NHL: p1, p2, p3

### Files Changed

```
live_data_router.py   (MODIFIED - ~1000+ lines added for new endpoints)
main.py               (MODIFIED - ENGINE_VERSION = "v10.65")
```

### Commits

| Hash | Message |
|------|---------|
| b97637d | v10.63: True RLM detection using Playbook /lines |
| 58cf70a | v10.64: Full Odds API utilization (scores, props, alt lines) |
| 14aab2c | v10.65: Complete API coverage (period markets, Playbook full) |

### Testing

```bash
# Test API coverage summary
curl "https://web-production-7b2a.up.railway.app/api-coverage"

# Test scores endpoint (for auto-grading)
curl "https://web-production-7b2a.up.railway.app/live/scores/nba" -H "X-API-Key: YOUR_KEY"

# Test period markets
curl "https://web-production-7b2a.up.railway.app/live/period-markets/nba?period=q1" -H "X-API-Key: YOUR_KEY"

# Test Playbook teams
curl "https://web-production-7b2a.up.railway.app/live/playbook/teams/nba" -H "X-API-Key: YOUR_KEY"
```

### API Coverage Summary

After v10.65, we now utilize:

**Odds API (7 endpoints, 46+ prop markets):**
- ✅ Live odds (spreads, totals, moneylines)
- ✅ Player props (all 46 markets)
- ✅ Scores (live + final)
- ✅ Alternate lines (hook shopping)
- ✅ Team totals
- ✅ Historical odds (opening lines)
- ✅ Available markets (per-game discovery)

**Playbook API (9 endpoints):**
- ✅ Splits (ticket% vs money%)
- ✅ Lines (opening + current for true RLM)
- ✅ Injuries
- ✅ Odds-games (schedule with IDs)
- ✅ Teams (metadata)
- ✅ Schedule (lightweight)
- ✅ Games (detailed objects)
- ✅ Splits-history (historical)
- ✅ Me (usage/quota)

**Optional (RotoWire):**
- ⏳ Starting lineups (not configured)
- ⏳ Referee assignments (not configured)
- ⏳ Injury news (not configured)

---

## Session Log: January 23, 2026 - v10.66 Alternative Data Integration

### Goal

Integrate all available API keys (Twitter, Finnhub, SerpAPI, FRED) into the scoring pipeline to gain additional edge signals beyond traditional betting data.

### What Was Done

**Created `alt_data_sources/` module with 5 files:**

| File | Purpose | Data Provided |
|------|---------|---------------|
| `twitter_api.py` | Twitter/X API integration | Breaking injury alerts, sentiment analysis |
| `finnhub_api.py` | Stock market data | Sportsbook sentiment (DKNG, FLTR), institutional moves |
| `serpapi_news.py` | Google News aggregation | Trending injury stories, player buzz |
| `fred_api.py` | Federal Reserve data | Economic indicators, consumer confidence |
| `integration.py` | Unified context provider | Combined scoring adjustments |

**Scoring Pipeline Integration:**

The alternative data flows into three scoring pillars:

1. **Hospital Fade Pillar Boost** (+0.25 to +0.5)
   - When Twitter/SerpAPI detect high-confidence injury news
   - Supplements official injury data with breaking news

2. **Alternative Sharp Signal** (+1.0 to +1.5)
   - When Finnhub detects institutional movement in sportsbook stocks
   - Only applies when no traditional sharp signal is detected
   - Acts as proxy for "smart money" sentiment

3. **Esoteric Alt Data Component** (-0.3 to +0.5)
   - FRED economic sentiment (consumer confidence)
   - News momentum (trending stories)
   - Adds to esoteric score calculation

**Data Flow:**
```
get_best_bets()
    ↓
get_alternative_data_context(sport, teams)
    ↓
Parallel fetch: Twitter + Finnhub + SerpAPI + FRED
    ↓
Calculate scoring_adjustments:
    - hospital_fade_boost
    - sharp_alternative
    - esoteric_alt_data
    ↓
Apply in calculate_pick_score():
    - pillar_boost += hospital_fade_boost (when injuries detected)
    - pillar_boost += sharp_alternative (when no traditional sharp)
    - esoteric_raw += esoteric_alt_data
```

### Files Changed

```
alt_data_sources/__init__.py     (NEW)
alt_data_sources/twitter_api.py  (NEW - 350 lines)
alt_data_sources/finnhub_api.py  (NEW - 320 lines)
alt_data_sources/serpapi_news.py (NEW - 280 lines)
alt_data_sources/fred_api.py     (NEW - 250 lines)
alt_data_sources/integration.py  (NEW - 300 lines)
env_config.py                    (MODIFIED - Added 5 new API keys)
live_data_router.py              (MODIFIED - Integration into scoring)
main.py                          (MODIFIED - ENGINE_VERSION = "v10.66")
CLAUDE.md                        (MODIFIED - Documentation)
```

### Environment Variables Required

Add these to Railway to activate:

```bash
TWITTER_BEARER=xxx        # Twitter API bearer token
FINNHUB_KEY=xxx          # Finnhub stock data API key
SERPAPI_KEY=xxx          # SerpAPI (Google Search) key
FRED_API_KEY=xxx         # Federal Reserve data API key
WHOP_API_KEY=xxx         # Whop membership platform
```

### Testing

```bash
# Check API coverage (shows which alt data sources are configured)
curl "https://web-production-7b2a.up.railway.app/api-coverage" -H "X-API-Key: YOUR_KEY"

# Response includes:
# "alternative_data_apis": {
#   "twitter": {"configured": true/false, ...},
#   "finnhub": {"configured": true/false, ...},
#   "serpapi": {"configured": true/false, ...},
#   "fred": {"configured": true/false, ...}
# }
```

### Expected Impact

| Signal | When Active | Boost | Use Case |
|--------|-------------|-------|----------|
| Breaking Injury News | Twitter detects OUT/DOUBTFUL | +0.25 to +0.5 | Hospital fade pillar |
| Institutional Sentiment | DKNG stock spike + no sharp | +1.0 to +1.5 | Alternative sharp signal |
| Economic Tailwind | Consumer confidence high | +0.25 | Esoteric score |
| Economic Headwind | Consumer confidence low | -0.15 | Esoteric score |
| News Momentum | Many trending stories | +0.2 | Esoteric score |

---

## Session Log: January 23, 2026 - v10.66 Alternative Data APIs Fully Configured

### What Was Done

**All 4 Alternative Data APIs Successfully Configured in Railway:**

| API | Env Variable | Status | Features |
|-----|--------------|--------|----------|
| Twitter/X | `TWITTER_BEARER` | ✅ Active | injury_alerts, sentiment |
| Finnhub | `FINNHUB_KEY` | ✅ Active | sportsbook_sentiment, market_sentiment |
| SerpAPI | `SERPAPI_KEY` | ✅ Active | injury_news, trending |
| FRED | `FRED_API_KEY` | ✅ Active | economic_sentiment, consumer_confidence |

**Issue Fixed:** Railway environment variables had leading spaces in names (` FRED_API_KEY` instead of `FRED_API_KEY`). Fixed by deleting and re-adding without spaces.

### Verification Endpoints

```bash
# Check all API configurations
curl "https://web-production-7b2a.up.railway.app/live/env-check" -H "X-API-Key: YOUR_KEY"

# Full API coverage summary
curl "https://web-production-7b2a.up.railway.app/live/api-coverage" -H "X-API-Key: YOUR_KEY"
```

### Best-Bets Test Results (NBA)

| Category | Count | Tiers |
|----------|-------|-------|
| Game Picks | 6 | 2 GOLD_STAR, 4 EDGE_LEAN |
| Prop Picks | 5 | 2 GOLD_STAR, 3 EDGE_LEAN |

Sample picks:
- GOLD_STAR (7.78): Pelicans @ Grizzlies
- GOLD_STAR (7.77): Rockets @ Pistons
- GOLD_STAR (7.63): Jock Landale threes under 1.5
- GOLD_STAR (7.62): Jaden Ivey points under 8.5

### Complete Railway Environment Variables

```bash
# Core APIs (CRITICAL)
ODDS_API_KEY=xxx              # Live odds, props, scores
PLAYBOOK_API_KEY=xxx          # Splits, sharp money, injuries

# Alternative Data APIs (v10.66)
TWITTER_BEARER=xxx            # Breaking injury news
FINNHUB_KEY=xxx               # Sportsbook stock sentiment
SERPAPI_KEY=xxx               # Google News aggregation
FRED_API_KEY=xxx              # Economic indicators

# Other APIs
WEATHER_API_KEY=xxx           # Game day weather
ASTRONOMY_API_ID=xxx          # Moon phases, planetary hours
ASTRONOMY_API_SECRET=xxx      # Astronomy auth

# Platform
API_AUTH_ENABLED=true
API_AUTH_KEY=xxx
DATABASE_URL=xxx
WHOP_API_KEY=xxx
```

### System Status

- **Engine Version:** v10.66
- **All Core APIs:** ✅ Configured
- **All Alternative Data APIs:** ✅ Configured
- **Scoring Pipeline:** ✅ Fully operational
- **Production URL:** https://web-production-7b2a.up.railway.app

---
