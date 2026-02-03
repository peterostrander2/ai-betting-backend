# Bookie-o-em v18.2 - AI Sports Betting Backend

> "Someone always knows." - NOOSPHERE VELOCITY

Production-hardened FastAPI backend for AI-powered sports betting predictions with 4-engine scoring, 17-pillar signal system, and esoteric edge analysis.

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

**Supported Sports:** `nba`, `nfl`, `mlb`, `nhl`, `ncaab`

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

## Production Features (v18.2)

- **4-Engine Scoring** - AI (25%), Research (35%), Esoteric (20%), Jarvis (20%)
- **17-Pillar Signal System** - 8 AI models + 9 specialized pillars
- **17/17 Esoteric Signals** - Including Phase 8: Lunar, Mercury, Rivalry, Streak, Solar
- **GLITCH Protocol** - 6 signals: Chrome Resonance, Void Moon, Noosphere, Hurst, Kp-Index, Benford
- **Trap Learning Loop (v19.0)** - Automated weight adjustments based on game results
- **ESPN Integration** - Officials, odds cross-validation, injuries supplement
- **SERP Intelligence** - Search-trend signals for all 5 engines
- **Railway Persistence** - 5GB persistent volume at `/data`
- **ET-Only Public Payloads** - No UTC/telemetry leaks to frontend

## Architecture

```
main.py                    # FastAPI app entry point (v18.2)
├── live_data_router.py    # All /live/* endpoints + 4-engine scoring
├── esoteric_engine.py     # 17 esoteric signals including Phase 8
├── context_layer.py       # Pillars 13-16 (DefRank, Pace, Vacuum, Officials)
├── officials_data.py      # Referee tendency database
├── core/
│   ├── scoring_contract.py    # Engine weights, thresholds, gates
│   ├── titanium.py            # Titanium 3/4 rule
│   └── time_et.py             # ET timezone handling
├── alt_data_sources/
│   ├── espn_lineups.py        # ESPN Hidden API integration
│   ├── noaa.py                # Solar flare + Kp-Index
│   └── serp_intelligence.py   # SERP betting signals
├── signals/
│   ├── msrf_resonance.py      # Turn date resonance
│   └── math_glitch.py         # Benford anomaly
├── trap_learning_loop.py  # v19.0 automated weight adjustments
├── ml_integration.py      # LSTM + Ensemble models
├── auto_grader.py         # Prediction grading
└── daily_scheduler.py     # Scheduled jobs (6 AM audit, etc.)
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
| **v18.2** | PHASE_8_ESOTERIC | Lunar, Mercury, Rivalry, Streak, Solar signals (17/17 active) |
| v19.0 | TRAP_LEARNING | Automated weight adjustments from game results |
| v17.8 | OFFICIALS_PILLAR | Referee tendency database (25 NBA, 17 NFL, 15 NHL) |
| v17.6 | VORTEX_BENFORD | Tesla 3-6-9, multi-book Benford analysis |
| v17.2 | ML_GLITCH_ACTIVATION | LSTM models + GLITCH Protocol (6 signals) |
| v14.1 | PRODUCTION_HARDENED | Retries, logging, rate limits, fallbacks |
| v14.0 | NOOSPHERE_VELOCITY | Global consciousness indicators |
| v13.0 | GANN_PHYSICS | W.D. Gann geometric principles |

## Esoteric Edge System (17/17 Signals Active)

The system includes 17 active esoteric signals across multiple protocols:

**PHASE 8 (v18.2) - Advanced Cosmic Signals:**
- Lunar Phase Intensity (Full/New moon detection)
- Mercury Retrograde (2026 periods with pre-shadow)
- Rivalry Intensity (Historic matchup detection)
- Streak Momentum (Win/loss regression signals)
- Solar Flare Status (NOAA X-ray flux chaos boost)

**GLITCH Protocol (v17.2) - 6 Signals:**
- Chrome Resonance (Player birthday + game date)
- Void Moon (Void-of-course lunar)
- Noosphere Velocity (Google Trends momentum)
- Hurst Exponent (Line history trending)
- Kp-Index (Geomagnetic storm activity)
- Benford Anomaly (First-digit distribution)

**Core Esoteric Signals:**
- Numerology (Generic + daily edge)
- Astrology (Vedic calculations)
- Fibonacci Alignment + Retracement
- Vortex Math (Tesla 3-6-9)
- Biorhythms (Player birth cycles - props only)
- Gann Square (Sacred geometry - games only)
- Founder's Echo (Team gematria resonance)

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
