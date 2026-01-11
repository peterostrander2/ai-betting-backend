# Session Handoff Document

**Project:** ai-betting-backend (Bookie-o-em)
**Version:** v14.1 PRODUCTION_HARDENED
**Last Updated:** 2026-01-11
**Branch:** `main` (merged from `claude/fix-sports-api-railway-b8Sfp`)

---

## Current State

The backend is **production-ready** and deployed to Railway. All endpoints are functional.

### What Was Done This Session

1. **Fixed syntax error** - Removed embedded carriage returns in `live_data_router.py` causing Railway deployment failures
2. **Production hardening** - Added retries, logging, rate-limit handling, deterministic fallbacks
3. **Completed all endpoints** - 11 endpoints fully implemented
4. **Updated documentation** - README.md, .env.example, railway.toml
5. **Merged to main** - PR #1 merged

### Key Files

| File | Purpose | Status |
|------|---------|--------|
| `main.py` | FastAPI entry point | ✅ Active - v14.1 |
| `live_data_router.py` | All /live/* endpoints | ✅ Active - 742 lines |
| `Procfile` | Railway start command | ✅ Configured |
| `runtime.txt` | Python version | ✅ python-3.12.3 |
| `railway.toml` | Railway config | ✅ With health checks |

---

## API Endpoints

### Live Endpoints (All Working)

```
GET /                       # Root - API info
GET /health                 # Health check
GET /live/health            # Live router health
GET /live/sharp/{sport}     # Sharp money signals
GET /live/splits/{sport}    # Betting splits
GET /live/props/{sport}     # Player props
GET /live/best-bets/{sport} # AI-scored best bets
GET /live/esoteric-edge     # Esoteric analysis
GET /live/noosphere/status  # Global consciousness
GET /live/gann-physics-status # GANN physics
GET /esoteric/today-energy  # Today's energy
```

### Supported Sports
`nba`, `nfl`, `mlb`, `nhl`

---

## Environment Variables

**Required for Railway:**
```
ODDS_API_KEY=ceb2e3a6a3302e0f38fd0d34150294e9
PLAYBOOK_API_KEY=pbk_d6f65d6a74c53d5ef9b455a9a147c853b82b
```

Note: These keys are currently hardcoded as fallbacks in `live_data_router.py` (lines 13-14). For production security, set them as Railway environment variables and remove the fallbacks.

---

## Known Issues / Tech Debt

### Low Priority
1. **`new_endpoints.py`** - Legacy file using undefined `app`. Not integrated. Can be deleted or kept as reference.

2. **`services/` folder** - Contains standalone `OddsAPIService` and `PlaybookAPIService` classes. Currently NOT used by `main.py` - the `live_data_router.py` has its own inline implementation. Could be refactored to use these services.

3. **Playbook API URL inconsistency** - `services/playbook_api_service.py` uses `https://api.playbook.com/v1` but `live_data_router.py` uses `https://api.playbook-api.com/v1`. The router version is correct.

4. **API keys in code** - Fallback API keys are hardcoded. Should be rotated if repo is public.

---

## Architecture Notes

### Data Flow
```
Request → main.py → live_data_router.py → External APIs
                                        ↓
                    ← Response (standardized schema)
```

### External API Dependencies
- **The Odds API** - Live odds from 15+ sportsbooks
- **Playbook Sports API** - Sharp money, betting splits
- **ESPN API** - Free, no auth required (injuries)

### Response Schema (Standardized)
```json
{
  "sport": "NBA",
  "source": "playbook" | "odds_api" | "estimated",
  "count": 5,
  "data": [...]
}
```

---

## Files NOT Currently Used

These files exist but are not imported by `main.py`:

| File | Description | Potential Use |
|------|-------------|---------------|
| `context_layer.py` | ML context features | Future ML integration |
| `lstm_brain.py` | LSTM neural network | Future predictions |
| `auto_grader.py` | Prediction grading | Future tracking |
| `daily_scheduler.py` | Scheduled jobs | Future automation |
| `prediction_api.py` | Legacy 8-model API | Reference only |
| `advanced_ml_backend.py` | ML model classes | Reference only |

---

## Future Enhancements

### Suggested Next Steps
1. **Integrate services/** - Refactor to use standalone service classes
2. **Add LSTM predictions** - Connect `lstm_brain.py` to best-bets
3. **Add auto-grading** - Track prediction accuracy
4. **Add scheduler** - Daily audits and weight adjustments
5. **Rotate API keys** - Move all keys to environment variables only
6. **Add caching** - Redis or in-memory TTL cache for API responses
7. **Add authentication** - API key or JWT for endpoints

---

## Testing Commands

```bash
# Local testing
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Health check
curl http://localhost:8000/health

# Sharp money
curl http://localhost:8000/live/sharp/nba

# Splits
curl http://localhost:8000/live/splits/nfl

# Best bets
curl http://localhost:8000/live/best-bets/nba
```

---

## Git History (Recent)

```
009d248 Merge pull request #1 - v14.1 Production Hardening
571a5fe Update main.py to v14.1, configure Procfile and runtime.txt
6f5abfd Production hardening: v14.1 with retries, logging, rate-limit handling
15cd4a0 Complete live_data_router.py with all required endpoints
5970249 Add .gitignore for Python cache
9e1b1e1 Fix syntax error: remove embedded carriage returns
```

---

## Contact / Context

This backend serves the **bookie-member-app** frontend. The backend was consolidated from a previous split architecture where some code lived in the frontend repo.

**Repository:** `peterostrander2/ai-betting-backend`

---

*Last handoff: 2026-01-11*
