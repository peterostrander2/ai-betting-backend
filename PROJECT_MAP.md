# Bookie-o-em Project Map

## Core Architecture
- **Type:** Python FastAPI backend
- **Deployment:** Railway (https://web-production-7b2a.up.railway.app)
- **Database:** PostgreSQL on Railway  
- **Storage:** `/app/grader_data` (Railway 5GB persistent volume)
- **Version:** v15.1 (Build: 5c0f104)

## Entry Points
- `main.py` - FastAPI app, health checks, routes
- `live_data_router.py` - All `/live/*` endpoints (67 routes)

## Critical Modules (SINGLE SOURCE OF TRUTH)
- `core/time_et.py` - **ET timezone filtering (ONLY use this)**
- `core/titanium.py` - **Titanium 3/4 rule (ONLY use this)**
- `core/invariants.py` - All system constants
- `grader_store.py` - Pick persistence (JSONL storage)
- `storage_paths.py` - Storage configuration

## Scoring System (4 Engines)
- `advanced_ml_backend.py` - **AI Score (25%)** - 8 AI models
- Research Score (30%) - Sharp money, splits, variance (in live_data_router.py)
- Esoteric Score (20%) - Numerology, astro, fib, vortex (in live_data_router.py)
- `jarvis_savant_engine.py` - **Jarvis Score (15%)** - Gematria triggers
- `jason_sim_confluence.py` - **Post-pick boost** - Confluence layer

## Data Sources (External APIs)
| API | Env Var | Purpose |
|-----|---------|---------|
| **Odds API** | `ODDS_API_KEY` | Live odds, props, games |
| **Playbook API** | `PLAYBOOK_API_KEY` | Splits, injuries, sharp money |
| **BallDontLie GOAT** | `BALLDONTLIE_API_KEY` | NBA grading, player stats |

## Storage Architecture (NEVER CHANGE THESE PATHS)
```
/app/grader_data/              ← Railway volume (persistent across restarts)
├── grader/
│   └── predictions.jsonl      ← Picks (JSONL, high-frequency writes)
└── grader_data/
    ├── weights.json           ← Weight learning (low-frequency updates)
    └── predictions.json       ← Auto-grader data
```

**CRITICAL FACTS:**
- `/app/grader_data` IS the Railway persistent volume (not ephemeral)
- Picks survive container restarts
- NEVER add code to block `/app/*` paths

## Active Development Areas
- ~~**Zero Picks Bug**~~ ✅ RESOLVED - System now returns picks correctly
- **Vacuum Score Integration** - Context modifiers not calculating correctly
- ~~**Esoteric for Props**~~ ✅ RESOLVED - Esoteric now 5.67-6.36 range (verified Jan 29)

## Quick Debug Commands

### Check Best-Bets Output
```bash
curl "https://web-production-7b2a.up.railway.app/live/best-bets/nba?debug=1" \
  -H "X-API-Key: bookie-prod-2026-xK9mP2nQ7vR4"
```

### Run Production Sanity Check
```bash
./scripts/prod_sanity_check.sh
```

## Git Workflow
- Main branch: `main`
- Railway auto-deploys from main branch
