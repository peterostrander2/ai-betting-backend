# PRODUCTION BASELINE SPEC v14.9
## Locked: January 26, 2026

This document defines the "gold" production baseline for the ai-betting-backend.
**DO NOT BREAK** any behavior defined here.

---

## CONFIRMED WORKING STATE

### Production Endpoints
- `/live/best-bets/{sport}` ✅
- `/live/debug/pick-breakdown/{sport}` ✅
- Tested working for NBA + NHL with API Key auth

### Engine Separation (NO DOUBLE COUNTING)

| Engine | Scale | Inputs | Notes |
|--------|-------|--------|-------|
| **AI Engine** | 0-10 | Pure model output ONLY | NO sharp/public/RLM |
| **Research Engine** | 0-10 | ALL market pillars | Sharp, RLM, Public Fade, Line Value |
| **Esoteric Edge** | 0-10 | Environment scoring | Non-JARVIS numerology |
| **Jarvis Engine** | 0-10 | Sacred trigger ritual | Gematria, 2178/201/33/93/322 triggers |

### Research Engine Pillars (ONLY in Research)
- Sharp Split / Sharp Money boost (0-3 pts)
- Reverse Line Movement (0-3 pts)
- Line Value / best odds
- Public Fade (0-2 pts)
- Base research floor (2 pts)

### Jason Sim 2.0 Integration
Jason runs as POST-pick confluence only (not odds based).

**Required output fields on EVERY pick:**
```json
{
  "jason_ran": true,
  "jason_sim_boost": 0.0,
  "jason_blocked": false,
  "jason_win_pct_home": 50.8,
  "jason_win_pct_away": 49.2
}
```

**Confluence behavior:**
- Boost if pick-side win% >= 61%
- Downgrade if <= 55%
- Block if <= 52% AND base_score < 7.2

### Titanium Threshold
- Titanium = 3 of 4 engines >= 8.0
- Triggers TITANIUM_SMASH tier (2.5 units)

---

## FRONTEND-UNBLOCK REQUIREMENTS

Every returned pick (props + game_picks) MUST include:

```json
{
  "research_reasons": ["Sharp signal STRONG (+3.0)", ...],
  "pillars_passed": ["Sharp Money Detection", "Reverse Line Movement"],
  "pillars_failed": [],
  "research_breakdown": {
    "sharp_boost": 3.0,
    "line_boost": 3.0,
    "public_boost": 0.0,
    "base_research": 2.0,
    "total": 8.0
  },
  "ai_score": 6.25,
  "research_score": 8.0,
  "esoteric_score": 3.84,
  "jarvis_score": 5.0,
  "final_score": 6.63,
  "tier": "MONITOR"
}
```

Tier fields derived ONLY from `tiering.py` single-source-of-truth.

---

## BUGS FIXED (MUST NOT REGRESS)

1. **best-bets 500/502 while debug worked** - Fixed by initializing `mid_spread_mod = 0.0`
2. **Engine separation** - Sharp/RLM/Public now ONLY in Research, not AI
3. **Jason Sim missing** - Fully integrated into scoring pipeline
4. **Phantom games** - TODAY-only EST filter enforced via `time_filters.py`

---

## GRADING + LEARNING LOOP REQUIREMENTS

### Date Boundaries (America/New_York)
- Start: 12:01 AM ET
- End: 11:59 PM ET
- **NEVER** grade tomorrow games, yesterday games, or stale games

### Late Pull Handling
If pick generated after game started:
```json
{
  "already_started": true,
  "game_start_time_et": "7:30 PM ET",
  "reason": "late pull / live-bet eligible only"
}
```

### Grading Determinism
- Grade ONLY picks emitted by `/live/best-bets/{sport}` during today's window
- Store published picks to stable persistence (jsonl)
- Picks must include pick_id for tracking

### Learning Loop Safety
**ALLOWED to adjust:**
- Research weights (pillar boosts)
- Esoteric weights (non-jarvis)
- Jarvis internal tuning (ONLY sacred trigger scoring)
- Jason sim confluence tuning (boost/block thresholds)

**NEVER allowed:**
- Mutate engine separation
- Change which signals go to which engine
- Modify tiering.py thresholds without explicit approval

All changes MUST be logged in audit entry.

---

## DAILY PICK LOG SCHEMA (JSONL)

Each pick logged must include:
```json
{
  "date": "2026-01-26",
  "sport": "NBA",
  "pick_id": "abc123def456",
  "matchup": "Lakers @ Celtics",
  "player": "LeBron James",
  "prop_type": "points",
  "line": 25.5,
  "side": "Over",
  "odds": -110,
  "book": "DraftKings",
  "game_start_time_et": "7:30 PM ET",
  "ai_score": 6.25,
  "research_score": 8.0,
  "esoteric_score": 3.84,
  "jarvis_score": 5.0,
  "final_score": 7.8,
  "tier": "EDGE_LEAN",
  "titanium_flag": false,
  "research_breakdown": {...},
  "research_reasons": [...],
  "pillars_passed": [...],
  "pillars_failed": [...],
  "jason_ran": true,
  "jason_sim_boost": 0.0,
  "jason_blocked": false,
  "result": null,
  "units_won_lost": null
}
```

---

## DAILY AUDIT REPORT REQUIREMENTS

The 6 AM audit job must output:
1. Record by tier and by sport
2. ROI by tier
3. Top 10 false positives (high score loses)
4. Top 10 missed opportunities (low score wins)
5. Pillar hit-rate breakdown (which pillars correlate with wins)
6. Jarvis trigger performance (hit rate by trigger number)
7. Jason sim effect report (boost/block accuracy)

---

## INJURY / BOOK AVAILABILITY VALIDATION

**Hard validation step:**
- If player prop returned but player is:
  - Injured (OUT/DOUBTFUL/SUSPENDED)
  - Not active
  - Not listed at book
- Then:
  - Mark pick as `invalid: true`
  - Downgrade to PASS or remove entirely
  - Do NOT ship as bet

Example: Deni Avdija not on DraftKings props list → must be caught.

---

## OUTPUT FORMATTING (CONSISTENT)

**Game picks must include:**
- Team names
- Pick type (ML/Spread/Total)
- Line + odds
- Book name + deep link if available
- start_time_et
- already_started flag if applicable

**Prop picks must include:**
- Player name
- Prop type + line
- Odds + book + deep link
- start_time_et
- injury_status

---

## TIERING SINGLE SOURCE OF TRUTH

`tiering.py` is the ONLY tier assignment logic.

**No duplicate tier thresholds anywhere else.**

Tier hierarchy:
1. TITANIUM_SMASH - 3/4 engines >= 8.0
2. GOLD_STAR - final_score >= 9.0
3. EDGE_LEAN - final_score >= 7.5
4. ML_DOG_LOTTO - NHL Dog Protocol
5. MONITOR - final_score >= 6.0
6. PASS - final_score < 6.0

---

## FILES THAT DEFINE THIS SPEC

| File | Purpose |
|------|---------|
| `tiering.py` | Single source of truth for tiers |
| `time_filters.py` | TODAY-only EST gating |
| `jason_sim_confluence.py` | Win probability simulation |
| `live_data_router.py` | Main API endpoints + scoring |
| `auto_grader.py` | Grading + learning loop |
| `daily_scheduler.py` | 6 AM audit job |

---

## VERSION HISTORY

- v14.9 (2026-01-26): Production baseline locked
  - Engine separation fixed
  - Jason Sim integrated
  - Research transparency fields added
  - mid_spread_mod initialization fix
