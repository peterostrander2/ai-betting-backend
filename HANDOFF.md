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
| `live_data_router.py` | All /live/* endpoints | Active - ~900 lines |
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

### New Features

1. **TTL Cache** - In-memory cache with configurable TTL
   - Default 5 minutes for API responses
   - 2 minutes for best-bets (includes daily energy)
   - Cache stats and clear endpoints available

2. **Optional Authentication**
   - Disabled by default
   - Enable with `API_AUTH_ENABLED=true` and `API_AUTH_KEY=...`
   - Clients send `X-API-Key` header

3. **Module Status Endpoints**
   - LSTM, Auto-grader, Scheduler status checks
   - Useful for debugging and monitoring

### Data Flow

```
Request → main.py → live_data_router.py → Cache Check
                                        ↓ (miss)
                                   External APIs
                                        ↓
                    ← Cache + Response (standardized schema)
```

### Response Schema

```json
{
  "sport": "NBA",
  "source": "playbook" | "odds_api" | "estimated",
  "count": 5,
  "data": [...]
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
1. **Enable authentication** - Set API keys in Railway for production security
2. **Add Redis caching** - Replace in-memory cache for multi-instance support
3. **Integrate LSTM predictions** - Needs historical player data

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
```

---

## Git History (Recent)

```
6d3937c Fix railway.toml: use python main.py instead of shell variable
c6166a0 Fix Procfile: use python main.py instead of shell variable
bcdd7fd Fix PORT handling: use Python os.environ instead of shell expansion
dbf3128 Fix Dockerfile: use shell form CMD for proper PORT variable expansion
65e7b8b Fix Dockerfile: use main.py entry point with dynamic PORT
```

---

*Last handoff: 2026-01-12*
