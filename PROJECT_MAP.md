# Bookie-o-em Project Map

## Core Architecture
- **Type:** Python FastAPI backend
- **Deployment:** Railway
- **Storage:** `/app/grader_data` (Railway 5GB persistent volume)

## Entry Points
- `main.py` - FastAPI app
- `live_data_router.py` - All `/live/*` endpoints

## Critical Modules (SINGLE SOURCE OF TRUTH)
- `core/time_et.py` - ET timezone filtering (ONLY use this)
- `core/titanium.py` - Titanium 3/4 rule (ONLY use this)
- `grader_store.py` - Pick persistence

## Scoring System
- AI Score (25%) - `advanced_ml_backend.py`
- Research Score (30%) - Sharp money, splits, variance
- Esoteric Score (20%) - Numerology, astro, fib, vortex
- Jarvis Score (15%) - `jarvis_savant_engine.py`
- Jason Sim (post-pick boost) - `jason_sim_confluence.py`

## Active Issues
- **Zero Picks Bug** - Analyzing 5000+ props, returning 0
- **Esoteric for Props** - Stuck at ~1.1 (should be 2.0-5.5)

## Storage Paths
/app/grader_data/grader/predictions.jsonl - Picks
/app/grader_data/grader_data/weights.json - Weight learning
