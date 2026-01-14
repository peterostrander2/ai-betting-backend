# CLAUDE.md - Project Instructions for AI Assistants

## Project Overview

**Bookie-o-em** - AI Sports Prop Betting Backend
**Version:** v14.2 PRODUCTION HARDENED
**Stack:** Python 3.11+, FastAPI, Railway deployment
**Frontend:** bookie-member-app (separate repo)
**Production URL:** https://web-production-7b2a.up.railway.app

---

## Current Status & Running TODO

### Completed (Backend)
- [x] API Authentication enabled (`X-API-Key` header on all `/live/*` endpoints)
- [x] MasterPredictionSystem integrated (8 AI Models + 8 Pillars scoring)
- [x] `/live/best-bets/{sport}` returns TWO categories: `props` + `game_picks`
- [x] JARVIS Savant Engine v7.3 (gematria 52%, public fade, mid-spread amplifier)
- [x] Confluence System v10.1 (IMMORTAL, JARVIS_PERFECT, PERFECT, STRONG, MODERATE tiers)
- [x] Tesla 3-6-9 alignment check
- [x] 33 divisibility / master number detection
- [x] 2178 THE IMMORTAL detection
- [x] Dual-score display (Research + Esoteric separate)
- [x] Fallback when Odds API props returns 422
- [x] Redis caching (optional), PostgreSQL database (optional)
- [x] Auto-grader scheduler for pick tracking

### Completed (Frontend - bookie-member-app)
- [x] Create `GameSmashList.jsx` - Game picks component (spreads, totals, ML)
- [x] Create `PropsSmashList.jsx` - Player props component
- [x] Create `SmashSpotsPage.jsx` - Unified page with tabs
- [x] Update `App.jsx` routing to use SmashSpotsPage
- [ ] Add `VITE_API_KEY` to Vercel/deployment env vars (if not done)

### Future Enhancements
- [ ] Click-to-bet deep links for sportsbooks
- [ ] Historical performance tracking dashboard
- [ ] Push notifications for SMASH-tier picks
- [ ] Parlay builder with correlation warnings

### API Response Structure (best-bets)
```json
{
  "sport": "NBA",
  "props": {
    "count": 5,
    "total_analyzed": 20,
    "picks": [{
      "player_name": "...",
      "market": "player_points",
      "confidence": 85,
      "total_score": 22.5,
      "scoring_breakdown": {
        "ai_models": 6.5,
        "pillars": 5.0,
        "jarvis": 3.5,
        "esoteric": 1.5,
        "confluence_boost": 5.0
      },
      "dual_scores": {
        "research": 11.5,
        "esoteric": 5.0
      },
      "confluence": {
        "level": "PERFECT",
        "boost": 5,
        "alignment_pct": 85.0
      },
      "bet_recommendation": {
        "tier": "GOLD_STAR",
        "units": 2.0,
        "confluence_tier": "PERFECT"
      }
    }]
  },
  "game_picks": {
    "count": 3,
    "total_analyzed": 10,
    "picks": [{ "team": "Lakers", "market": "spreads", "confidence": 78, ... }]
  },
  "daily_energy": { "flow": "YANG", "theme": "..." },
  "timestamp": "2024-01-14T..."
}
```

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

## Signal Architecture (Dual Engine + Confluence v10.1)

### Scoring Formula
```
TOTAL_SCORE = Research (0-16) + Esoteric (0-6) + Confluence_Boost (0-10)

Where:
- Research = AI_Models (0-8) + Pillars (0-8)
- Esoteric = JARVIS (0-4) + Esoteric_Boost (0-2)
- Confluence = Alignment between Research & Esoteric (0-10)

Max Possible: 32 points (with IMMORTAL confluence)
```

### Components

1. **8 AI Models** (max 8 pts) - `advanced_ml_backend.py`
   - Ensemble, LSTM, Matchup, Monte Carlo, Line Movement, Rest/Fatigue, Injury, Betting Edge

2. **8 Pillars** (max 8 pts) - `advanced_ml_backend.py`
   - Sharp Split, Reverse Line, Hospital Fade, Situational Spot, Expert Consensus, Prop Correlation, Hook Discipline, Volume Discipline

3. **JARVIS Savant Engine v7.3** (max 4 pts) - `live_data_router.py`
   - Gematria (52% weight): Team name analysis, sacred number detection
   - Sacred triggers: 2178 (IMMORTAL), 201, 33, 93, 322
   - Public Fade: -13% when public ≥65% on chalk
   - Mid-Spread Amplifier: +20% for lines +4 to +9
   - Large Spread Trap: -20% for lines ≥14
   - Blended Probability: 67% Ritual Score + 33% Quantitative

4. **Esoteric Edge** (max 2 pts) - `live_data_router.py`
   - Daily energy score, moon phase, Tesla 3-6-9 alignment
   - Power numbers (11, 22, 33), date numerology

5. **Confluence System v10.1** (max 10 pts boost) - `live_data_router.py`
   - Measures alignment between Research Model and Esoteric Edge
   - Levels: IMMORTAL (+10), JARVIS_PERFECT (+7), PERFECT (+5), STRONG (+3), MODERATE (+1), DIVERGENT (+0)
   - Tesla 3-6-9 alignment check
   - 33 divisibility/master number check
   - 2178 THE IMMORTAL detection

### Confidence Tiers
| Tier | Score Range | Confidence % | Units |
|------|-------------|--------------|-------|
| IMMORTAL | 25+ or 2178 | 90-98% | 3u |
| SMASH | 20-24 | 82-95% | 2u (Gold Star) |
| HIGH | 16-19 | 72-85% | 1u (Edge Lean) |
| MEDIUM | 12-15 | 58-72% | 0.5u |
| LOW | <12 | <58% | No bet |

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
GET /live/best-bets/{sport}     # AI best bets (cached 2m)
GET /live/esoteric-edge         # Esoteric analysis
GET /live/noosphere/status      # Noosphere velocity
GET /live/gann-physics-status   # GANN physics
GET /esoteric/today-energy      # Daily energy
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
- JARVIS: `live_data_router.py:233-239` → `JARVIS_TRIGGERS`
- Esoteric: `live_data_router.py` → `get_daily_energy()`

### Debug Deployment
1. Check Railway logs
2. Verify PORT is read via Python `os.environ.get()`
3. Ensure `railway.toml` uses `python main.py`
