# Bookie-o-em v14.1 - AI Sports Betting Backend

> "Someone always knows." - NOOSPHERE VELOCITY

Production-hardened FastAPI backend for AI-powered sports betting predictions with live odds, sharp money detection, and esoteric edge analysis.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables (or copy .env.example to .env)
export ODDS_API_KEY=your_key_here
export PLAYBOOK_API_KEY=your_key_here

# Run locally
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Visit `http://localhost:8000/docs` for interactive API documentation.

## Live Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | API info + all endpoints list |
| `GET /health` | Root health check |
| `GET /live/health` | Live router health |
| `GET /live/sharp/{sport}` | Sharp money signals |
| `GET /live/splits/{sport}` | Betting splits (public %) |
| `GET /live/props/{sport}` | Player props |
| `GET /live/best-bets/{sport}` | AI-scored best bets |
| `GET /live/esoteric-edge` | Esoteric edge analysis |
| `GET /live/noosphere/status` | Global consciousness indicators |
| `GET /live/gann-physics-status` | GANN physics module |
| `GET /esoteric/today-energy` | Today's energy reading |

**Supported Sports:** `nba`, `nfl`, `mlb`, `nhl`

## Response Schema

All live endpoints return standardized responses:

```json
{
  "sport": "NBA",
  "source": "playbook" | "odds_api" | "estimated",
  "count": 5,
  "data": [...]
}
```

### /live/best-bets/all Response (v10.48)

The unified multi-sport board returns picks in two tiers:

```json
{
  "source": "production_v10.48_all_sports",
  "scoring_system": "v10.48: Tier A (Official) + Tier B (Action Leans) with hard guarantees",

  "all_picks": {
    "count": 14,
    "picks": [...]
  },

  "action_leans": {
    "count": 8,
    "picks": [...],
    "threshold_min": 6.70,
    "threshold_max": 7.05,
    "max_units": 1.0
  },

  "by_sport": {
    "NBA": { "props": {...}, "game_picks": {...}, "total_picks": 10 },
    "NFL": { "props": {...}, "game_picks": {...}, "total_picks": 5 }
  },

  "summary": {
    "total_picks": 14,
    "gold_star_count": 5,
    "edge_lean_count": 9,
    "props_count": 12,
    "games_count": 2,
    "sports_with_picks": 4,
    "official_count": 14,
    "action_leans_count": 8,
    "total_published_count": 22
  },

  "timestamp": "2026-01-23T12:00:00Z"
}
```

**Tier A (Official Card)** - `all_picks`:
- Contains GOLD_STAR (≥7.5) and EDGE_LEAN (≥7.05) picks
- Max 14 picks
- These are the main plays for the day

**Tier B (Action Leans)** - `action_leans`:
- Contains picks with scores 6.70 ≤ score < 7.05
- Max 10 picks
- `recommended_units` capped at 1.0
- Cannot have GOLD_STAR or EDGE_LEAN badges

**Debug Mode** (`?debug=1`):
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
    },
    "sports_in_season": ["NBA", "NFL", "NHL", "NCAAB"],
    "sports_errors": {},
    "global_publish_gate": {...},
    "jason_sim": {...}
  }
}
```

## Production Features (v14.1)

- **Shared HTTP Client** - Connection pooling via httpx.AsyncClient
- **Retry with Backoff** - Exponential backoff (0.5s, 1s, 2s), 2 retries
- **Rate Limit Handling** - 429 → HTTP 503 with informative message
- **Structured Logging** - Timestamped logs for debugging
- **Deterministic Fallbacks** - MD5 hash seeding for stable fallback data
- **Clean Shutdown** - Proper httpx client cleanup on app shutdown

## Architecture

```
main.py                    # FastAPI app entry point (v14.1)
├── live_data_router.py    # All /live/* endpoints + esoteric functions
├── services/
│   ├── odds_api_service.py      # The Odds API (standalone service)
│   └── playbook_api_service.py  # Playbook API (standalone service)
├── context_layer.py       # Context features for ML predictions
├── lstm_brain.py          # LSTM neural prediction engine
├── auto_grader.py         # Prediction grading & weight adjustment
├── daily_scheduler.py     # Scheduled audit jobs
├── prediction_api.py      # Legacy 8-model prediction API
└── advanced_ml_backend.py # Legacy ML models
```

### Active vs Legacy Files

| File | Status | Description |
|------|--------|-------------|
| `main.py` | **Active** | Current entry point |
| `live_data_router.py` | **Active** | All live endpoints |
| `services/` | Available | Standalone service classes |
| `context_layer.py` | Available | ML context features |
| `lstm_brain.py` | Available | LSTM prediction |
| `auto_grader.py` | Available | Auto-grading system |
| `daily_scheduler.py` | Available | Scheduler endpoints |
| `prediction_api.py` | Legacy | Old entry point |
| `new_endpoints.py` | Legacy | Not integrated |

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ODDS_API_KEY` | Yes | The Odds API key (https://the-odds-api.com/) |
| `PLAYBOOK_API_KEY` | Yes | Playbook Sports API key |
| `PORT` | No | Server port (default: 8000, auto-set by Railway) |
| `ODDS_API_BASE` | No | Override Odds API URL |
| `PLAYBOOK_API_BASE` | No | Override Playbook API URL |

## Railway Deployment

The project is configured for Railway:

- `Procfile` - `web: uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}`
- `runtime.txt` - `python-3.12.3`
- `railway.toml` - Health checks and restart policy

### Deploy Steps

1. Connect GitHub repo to Railway
2. Set environment variables in Railway dashboard:
   - `ODDS_API_KEY`
   - `PLAYBOOK_API_KEY`
3. Deploy from `main` branch
4. Test: `curl https://your-app.railway.app/health`

## Version History

| Version | Codename | Key Features |
|---------|----------|--------------|
| **v14.1** | PRODUCTION_HARDENED | Retries, logging, rate limits, deterministic fallbacks |
| v14.0 | NOOSPHERE_VELOCITY | Global consciousness indicators, 3 modules |
| v13.0 | GANN_PHYSICS | W.D. Gann geometric principles |
| v11.0 | OMNI_GLITCH | Vortex math, Shannon entropy, 6 modules |
| v10.4 | SCALAR_SAVANT | Bio-sine wave, chrome resonance, 6 modules |
| v10.1 | RESEARCH_OPTIMIZED | +94.40u YTD edge system |

## Esoteric Edge System

The system includes 18 esoteric modules for edge detection:

**NOOSPHERE VELOCITY (v14.0):**
- Insider Leak Detection
- Main Character Syndrome
- Phantom Injury Scanner

**GANN PHYSICS (v13.0):**
- 50% Retracement (Gravity Check)
- Rule of Three (Exhaustion Node)
- Annulifier Cycle (Harmonic Lock)

**OMNI-GLITCH (v11.0):**
- Vortex Math (Tesla 3-6-9)
- Shannon Entropy
- Atmospheric Drag
- Void of Course Moon
- Gann Spiral
- Mars-Uranus Nuclear

**SCALAR-SAVANT (v10.4):**
- Bio-Sine Wave
- Chrome Resonance
- Lunacy Factor
- Schumann Spike
- Saturn Block
- Zebra Privilege

## Testing

```bash
# Health check
curl http://localhost:8000/health

# Sharp money for NBA
curl http://localhost:8000/live/sharp/nba

# Splits for NFL
curl http://localhost:8000/live/splits/nfl

# Today's energy
curl http://localhost:8000/esoteric/today-energy

# Best bets
curl http://localhost:8000/live/best-bets/nba
```

## API Keys

| Provider | URL | Purpose |
|----------|-----|---------|
| The Odds API | https://the-odds-api.com/ | Live odds from 15+ sportsbooks |
| Playbook Sports | https://playbook-api.com/ | Sharp money, betting splits |

## License

Proprietary - Bookie-o-em

---

**Built with FastAPI + httpx for production-grade sports betting intelligence.**
