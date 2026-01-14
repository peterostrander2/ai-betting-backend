# CLAUDE.md - Project Instructions for AI Assistants

## Project Overview

**Bookie-o-em** - AI Sports Prop Betting Backend
**Version:** v15.0 JARVIS SAVANT EDITION
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

## Signal Architecture (JARVIS SAVANT ENGINE v7.3)

### Confluence Scoring System
```
┌─────────────────────────────────────────────────────────────┐
│  RESEARCH SCORE (0-10)        ESOTERIC SCORE (0-10)        │
│  ├─ 8 AI Models (0-8)         ├─ Gematria (52% weight)     │
│  └─ 8 Pillars (0-8)           ├─ Public Fade (-13%)        │
│      scaled to 0-10           ├─ Mid-Spread (+20%)         │
│                               ├─ Moon/Numerology            │
│                               └─ Tesla/Fibonacci/Vortex     │
│                                                              │
│  BLENDED = 0.67 × (RS/10) + 0.33 × (ES/10) + confluence    │
│                                                              │
│  BET TIERS:                                                  │
│  ≥72% → GOLD_STAR (2u)  |  ≥68% → EDGE_LEAN (1u)           │
│  ≥60% → MONITOR         |  <60% → PASS                      │
└─────────────────────────────────────────────────────────────┘
```

### Components

1. **8 AI Models** (max 8 pts) - `advanced_ml_backend.py`
   - Ensemble, LSTM, Matchup, Monte Carlo, Line Movement, Rest/Fatigue, Injury, Betting Edge

2. **8 Pillars** (max 8 pts) - `advanced_ml_backend.py`
   - Sharp Split, Reverse Line, Hospital Fade, Situational Spot, Expert Consensus, Prop Correlation, Hook Discipline, Volume Discipline

3. **JARVIS Savant Engine** (full system) - `live_data_router.py:673-1618`
   - `JarvisSavantEngine` class with complete confluence scoring
   - Gematria signals: 2178 (IMMORTAL), 201, 33, 93, 322
   - Public Fade: -13% when ≥65% on chalk
   - Mid-Spread Amplifier: +20% for +4 to +9 (Goldilocks zone)
   - Large Spread Trap: -20% for ≥14 pts
   - NHL Dog Protocol: 0.5u ML when RS ≥9.3 + public ≥65%
   - Dynamic weights: 30-55% gematria based on triggers

4. **Confluence Levels** - `calculate_confluence()`
   - IMMORTAL: 2178 + both ≥7.5 + aligned ≥80% → +10 boost
   - JARVIS_PERFECT: Trigger + both ≥7.5 + aligned → +7 boost
   - PERFECT: Both ≥7.5 + aligned ≥80% → +5 boost
   - STRONG: Both high OR aligned ≥70% → +3 boost
   - MODERATE: Aligned ≥60% → +1 boost
   - DIVERGENT: Models disagree → +0 boost

5. **Esoteric Edge** (18 modules) - `live_data_router.py`
   - NOOSPHERE VELOCITY, GANN PHYSICS, Moon Phase, Tesla 3-6-9, Fibonacci, Vortex Math

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
GET /live/sharp/{sport}         # Sharp money (cached 5m)
GET /live/splits/{sport}        # Betting splits (cached 5m)
GET /live/props/{sport}         # Player props (cached 5m)
GET /live/best-bets/{sport}     # AI best bets with confluence (cached 2m)
GET /live/esoteric-edge         # Esoteric analysis
GET /live/noosphere/status      # Noosphere velocity
GET /live/gann-physics-status   # GANN physics
GET /esoteric/today-energy      # Daily energy
```

### JARVIS Savant Engine Endpoints
```
GET /live/validate-immortal     # 2178 mathematical proof
GET /live/jarvis-triggers       # All trigger numbers and properties
GET /live/check-trigger/{value} # Test any number for triggers
GET /live/confluence/{sport}    # Detailed confluence analysis
```

### Click-to-Bet Endpoints (NEW)
```
GET /live/sportsbooks           # List supported sportsbooks
GET /live/line-shop/{sport}     # Line shopping across all books
GET /live/betslip/generate      # Generate betslip for placing bet
```
See `FRONTEND_HANDOFF_CLICK_TO_BET.md` for frontend integration guide.

### Management Endpoints
```
GET /live/cache/stats           # Cache statistics
GET /live/cache/clear           # Clear cache
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
- Pillars: `advanced_ml_backend.py` → `PillarsAnalyzer`
- JARVIS Engine: `live_data_router.py:673-1618` → `JarvisSavantEngine`
- Triggers: `live_data_router.py:544-550` → `JARVIS_TRIGGERS`
- Confluence: `live_data_router.py` → `calculate_confluence()`
- Gematria: `live_data_router.py` → `calculate_gematria_signal()`
- Public Fade: `live_data_router.py` → `calculate_public_fade_signal()`
- Spread Zones: `live_data_router.py` → `calculate_mid_spread_signal()`, `calculate_large_spread_trap()`
- Esoteric: `live_data_router.py` → `get_daily_energy()`

### JARVIS Weights (Dynamic)
```python
# Normal weights
gematria: 30%, numerology: 20%, astro: 15%, vedic: 10%, sacred: 10%, fib_phi: 8%, vortex: 7%

# When JARVIS triggered
gematria: 45%, numerology: 18%, astro: 12%, vedic: 8%, sacred: 5%, fib_phi: 6%, vortex: 6%

# When IMMORTAL (2178) detected
gematria: 55%, numerology: 15%, astro: 10%, vedic: 5%, sacred: 5%, fib_phi: 5%, vortex: 5%
```

### Debug Deployment
1. Check Railway logs
2. Verify PORT is read via Python `os.environ.get()`
3. Ensure `railway.toml` uses `python main.py`
