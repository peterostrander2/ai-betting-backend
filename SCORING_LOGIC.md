# 8 Pillars Scoring System

## Formula
BASE = (AI × 0.25) + (Research × 0.30) + (Esoteric × 0.20) + (Jarvis × 0.15)
FINAL = BASE + confluence_boost + jason_sim_boost

Minimum output: 6.5

## ENGINE 1: AI Score (25%)
File: advanced_ml_backend.py
8 AI models, range 0-10

## ENGINE 2: Research Score (30%)
- Sharp Money (0-3 pts)
- Line Variance (0-3 pts)  
- Public Fade (0-2 pts)
- Base (2-3 pts)

## ENGINE 3: Esoteric Score (20%)
File: live_data_router.py lines 2352-2435
Expected: 2.0-5.5 range

Components:
- Numerology (35%)
- Astro (25%)
- Fibonacci (15%)
- Vortex (15%)
- Daily Edge (10%)

**CRITICAL BUG:** Props use spread=0 for magnitude
Should use: prop_line for props, spread for games

## ENGINE 4: Jarvis Score (15%)
File: jarvis_savant_engine.py
Gematria triggers: 2178, 201, 33, 93, 322

## Tier Assignment
- TITANIUM: 3/4 engines >= 8.0
- GOLD_STAR: >= 7.5 + hard gates
- EDGE_LEAN: >= 6.5

## Current Bug
Zero picks because esoteric stuck at ~1.1 for props
Fix: Use prop_line for magnitude calculation
