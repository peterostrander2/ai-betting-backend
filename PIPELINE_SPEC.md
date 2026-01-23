# CANONICAL SCORING PIPELINE SPECIFICATION
## Version: v10.57 | Single Source of Truth

This document defines the EXACT deterministic pipeline used to calculate, validate, and score every pick (props + game picks) in the Bookie-o-em system.

---

## PIPELINE EXECUTION ORDER

```
PHASE 0: INGEST/NORMALIZE
    ↓
PHASE 1: TIME GATE (Same-day ET + Not Started)
    ↓
PHASE 2: FEATURE BUILD (Raw inputs)
    ↓
PHASE 3: MODEL LAYER (8 AI Models)
    ↓
PHASE 4: ESOTERIC LAYER (Jarvis/Gematria/Astro)
    ↓
PHASE 5: LIVE DATA SIGNALS
    ↓
PHASE 6: 8 PILLARS OF EXECUTION
    ↓
PHASE 7: SCORE AGGREGATION (Final Score)
    ↓
PHASE 8: CONFIDENCE FILTER
    ↓
PHASE 9: DATA INTEGRITY VALIDATORS (v10.57)
    ↓
PHASE 10: PUBLISH GATE (v10.43)
    ↓
PHASE 11: PICK FILTER (v10.56)
    ↓
PHASE 12: TIERING (tiering.py)
    ↓
PHASE 13: OUTPUT CONTRACT
```

---

## PHASE 0: INGEST/NORMALIZE

**Files:** `live_data_router.py:get_props()`, `live_data_router.py:get_best_bets()`

### 0.1 Fetch Slate
- Games from Odds API: `/sports/{sport}/events`
- Lines/odds from Odds API: `/sports/{sport}/odds`
- Schedule/start times extracted from `commence_time`

### 0.2 Fetch Props Markets
- Props from Odds API: `/sports/{sport}/events/{eventId}/odds`
- Markets: `player_points`, `player_rebounds`, `player_assists`, `player_threes` (NBA)
- Per-bookmaker dedup (first bookmaker only)

### 0.3 Normalize to PickCandidate

```python
PickCandidate = {
    "sport": str,              # NBA, NFL, MLB, NHL
    "game_id": str,            # Odds API event ID
    "game_time_et": str,       # ISO timestamp converted to ET
    "team": str,               # Player's team or bet team
    "opponent": str,           # Opposing team
    "home_team": str,
    "away_team": str,
    "market_type": "prop"|"game",
    "market_key": str,         # player_points, spreads, totals, h2h
    "player_name": str|None,   # For props only
    "player_id": str|None,     # If available
    "line": float,
    "odds": int,               # American odds (-110, +150, etc.)
    "side": str,               # Over, Under, home, away
    "book": str,               # draftkings, fanduel, etc.
}
```

---

## PHASE 1: TIME GATE (HARD FILTER)

**File:** `live_data_router.py:is_game_today()`, `live_data_router.py:is_game_started()`

### 1.1 Same-Day ET Check
```python
def is_game_today(commence_time: str) -> bool:
    # Convert UTC to ET
    # Return True only if game is today in ET timezone
```

### 1.2 Not Started Check
```python
def is_game_started(commence_time: str) -> bool:
    # Return True if game has already started
    # Filter out started games
```

### 1.3 Labels Added
- `team`: Player's team or bet team
- `opponent`: Opposing team
- `game_time_et`: Formatted ET time

### 1.4 Drop Reasons
- `TIME_GATE_NOT_TODAY`: Game not today
- `TIME_GATE_STARTED`: Game already started

---

## PHASE 2: FEATURE BUILD

**File:** `live_data_router.py:calculate_pick_score()`

### Raw Inputs Per Candidate

| Feature | Source | Purpose |
|---------|--------|---------|
| `odds` | Odds API | American odds (-110) |
| `line` | Odds API | Point spread or prop line |
| `line_movement` | Playbook API | Opening vs current line delta |
| `public_pct` | Playbook API | Ticket percentage on side |
| `money_pct` | Playbook API | Handle percentage on side |
| `sharp_diff` | Calculated | `money_pct - public_pct` |
| `injuries` | Playbook/ESPN | Player status (OUT/GTD/etc.) |
| `rest_days` | Schedule | Days since last game |
| `travel_miles` | Schedule | Travel distance |
| `games_in_7` | Schedule | Games in last 7 days |
| `pace` | Stats | Team pace rating |
| `def_rating` | Stats | Opponent defensive rating |
| `correlation_key` | Calculated | `game_id:team:player:market` |

---

## PHASE 3: MODEL LAYER (8 AI Models)

**File:** `advanced_ml_backend.py:MasterPredictionSystem`

### Model 1: Ensemble Stacking
```python
class EnsembleStackingModel:
    # XGBoost + LightGBM + RandomForest -> GradientBoosting meta
    def predict(features) -> float  # Returns blended prediction
```
- **Weight:** Part of AI engine composite
- **Output:** Predicted value (points, yards, etc.)

### Model 2: LSTM Neural Network
```python
class LSTMModel:
    # Time-series: LSTM(50) -> LSTM(50) -> Dense(25) -> Dense(1)
    def predict(recent_games) -> float  # Returns trend-adjusted value
```
- **Fallback:** Statistical weighting when TensorFlow unavailable
- **Output:** Temporal trend adjustment

### Model 3: Matchup-Specific
```python
class MatchupSpecificModel:
    def predict(player_id, opponent_id, features) -> float
```
- **Output:** Head-to-head adjusted prediction

### Model 4: Monte Carlo Simulator
```python
class MonteCarloSimulator:
    def simulate_game(team_a_stats, team_b_stats, n=10000) -> dict
    # Returns: {team_a_win_pct, team_b_win_pct, score_distributions}
```
- **Output:** Win probability distribution

### Model 5: Line Movement Analyzer
```python
class LineMovementAnalyzer:
    def analyze_line_movement(game_id, current, opening, time, betting_pct) -> dict
    # Detects: REVERSE_LINE_MOVE when public > 60% but line moved opposite
```
- **Output:** `{sharp_detected: bool, recommendation: FADE_PUBLIC|FOLLOW}`

### Model 6: Rest & Fatigue
```python
class RestFatigueModel:
    def analyze_rest(days_rest, travel_miles, games_in_7) -> float
    # Multipliers: B2B=0.85, travel>1500=0.95, 4+games=0.90
```
- **Output:** Fatigue multiplier (0.85-1.0)

### Model 7: Injury Impact
```python
class InjuryImpactCalculator:
    def calculate_impact(injuries, depth_chart) -> float
    # Starter out: -2.0, Bench out: -0.5
```
- **Output:** Negative adjustment

### Model 8: Betting Edge Calculator
```python
class BettingEdgeCalculator:
    def calculate_ev(your_probability, betting_odds) -> dict
    # Returns: {ev, edge_pct, kelly_pct, confidence}
```
- **Output:** Expected value and optimal bet size

---

## PHASE 4: ESOTERIC LAYER

**File:** `jarvis_savant_engine.py`

### 4.1 Gematria (52% weight)
```python
def calculate_gematria_signal(text) -> dict:
    # Simple gematria: A=1, B=2, ..., Z=26
    # Reverse gematria: A=26, B=25, ..., Z=1
    # Jewish gematria: Hebrew letter values
```

### 4.2 JARVIS Triggers (20% weight)
| Number | Name | Boost | Tier |
|--------|------|-------|------|
| 2178 | THE IMMORTAL | +1.0 | LEGENDARY |
| 201 | THE ORDER | +0.6 | HIGH |
| 33 | THE MASTER | +0.5 | HIGH |
| 93 | THE WILL | +0.5 | HIGH |
| 322 | THE SOCIETY | +0.5 | HIGH |
| 666 | THE BEAST | +0.4 | MEDIUM |
| 888 | JESUS | +0.4 | MEDIUM |
| 369 | TESLA KEY | +0.35 | MEDIUM |

### 4.3 Vedic Astrology (13% weight)
```python
class VedicAstroEngine:
    def get_planetary_hour() -> dict      # Chaldean cycle (40%)
    def get_nakshatra() -> dict           # Lunar mansion (35%)
    def check_retrograde() -> dict        # Mercury/Venus/Mars (25%)
```

### 4.4 Sacred Geometry (5% weight)
- Fibonacci alignment
- PHI (1.618) metrics
- Tesla 3-6-9 vortex patterns

---

## PHASE 5: LIVE DATA SIGNALS

**File:** `live_data_router.py`

### Signal List

| Signal | Function | Threshold | Contribution |
|--------|----------|-----------|--------------|
| SHARP_MONEY | `get_sharp_money()` | diff >= 10 | +1.0 to +3.0 |
| PUBLIC_FADE | `calculate_pick_score()` | public >= 70% | +0.5 |
| REVERSE_LINE | Line moved vs public | public > 60% + line down | +1.0 to +2.5 |
| LINE_VALUE | `get_line_shopping()` | Best odds found | +0.2 |
| GOLDILOCKS | Spread 4-9 | Mid-spread | +0.2 |
| TRAP_GATE | Spread > 14 | Large spread | -0.2 |

---

## PHASE 6: 8 PILLARS OF EXECUTION

**File:** `advanced_ml_backend.py:PillarsAnalyzer`

### Pillar Summary

| # | Pillar | Method | Trigger | Score |
|---|--------|--------|---------|-------|
| 1 | Sharp Split | `_pillar_1_sharp_split` | Public > 60% | +2.0 |
| 2 | Reverse Line Move | `_pillar_2_reverse_line` | Public > 60% + line down | +2.5 |
| 3 | Hospital Fade | `_pillar_3_hospital_fade` | Key player OUT | -2.0 |
| 4 | Situational Spot | `_pillar_4_situational_spot` | B2B/travel/schedule | -2.5 |
| 5 | Expert Consensus | `_pillar_5_expert_consensus` | 3+ experts agree | +1.5 |
| 6 | Prop Correlation | `_pillar_6_prop_correlation` | Game script match | +0.5 |
| 7 | Hook Discipline | `_pillar_7_hook_discipline` | Bad hook (-3.5, -7.5) | Warning |
| 8 | Volume Discipline | `_pillar_8_volume_discipline` | AI score tier | 1-5% sizing |

---

## PHASE 7: SCORE AGGREGATION

**File:** `live_data_router.py:calculate_pick_score()`

### Master Formula

```python
# Step 1: Calculate base scores
research_score = base_ai + pillar_boosts + context_mods  # Range: 0-10
esoteric_score = ritual_base + jarvis + gematria + astro  # Range: 0-10

# Step 2: Calculate alignment
alignment_pct = 100 - abs(research_score - esoteric_score) * 10  # 0-100%

# Step 3: Calculate confluence boost
confluence_boost = compute_confluence_ladder(
    research_score, esoteric_score, alignment_pct, jarvis_active, immortal_active
)
# Boost values: IMMORTAL=+1.0, JARVIS_PERFECT=+0.6, PERFECT=+0.4, STRONG=+0.3

# Step 4: Combine with weights
final_score = (research_score * 0.67) + (esoteric_score * 0.33) + confluence_boost

# Step 5: Apply penalties
final_score -= correlation_penalty  # If crowded game
final_score -= under_penalty        # -0.15 for UNDER (pick_filter)

# Step 6: Clamp
final_score = max(0.0, min(10.0, final_score))
```

---

## PHASE 8: CONFIDENCE FILTER

**File:** `live_data_router.py`

```python
# Confidence grades based on confluence level
CONFIDENCE_PRIORITY = {"A": 1, "B": 2, "C": 3}

# Grade assignment
if confluence_level in ["IMMORTAL", "JARVIS_PERFECT", "PERFECT"]:
    confidence_grade = "A"
elif confluence_level in ["JARVIS_MODERATE", "STRONG"]:
    confidence_grade = "B"
else:
    confidence_grade = "C"

# Filter by min_confidence parameter
if min_confidence != "C":
    filter picks below threshold
```

---

## PHASE 9: DATA INTEGRITY VALIDATORS (v10.57)

**File:** `validators/`

### 9.1 Prop Integrity (`prop_integrity.py`)

| Check | Reason Code | Action |
|-------|-------------|--------|
| Missing required field | `MISSING_REQUIRED_{FIELD}` | DROP |
| Team not in game | `TEAM_NOT_IN_GAME` | DROP |
| No games played | `NO_GAMES_PLAYED` | DROP |
| Player inactive | `PLAYER_INACTIVE` | DROP |

### 9.2 Injury Guard (`injury_guard.py`)

| Status | Reason Code | Action |
|--------|-------------|--------|
| OUT | `INJURY_OUT` | DROP |
| SUSPENDED | `INJURY_SUSPENDED` | DROP |
| DOUBTFUL | `INJURY_DOUBTFUL` | DROP if BLOCK_DOUBTFUL=True |
| GTD | `INJURY_GTD` | DROP if BLOCK_GTD=True |

### 9.3 Market Availability (`market_availability.py`)

| Check | Reason Code | Action |
|-------|-------------|--------|
| Not in DK feed | `DK_MARKET_NOT_LISTED` | DROP |

**Example:** Deni Avdija has no props on DraftKings -> `DK_MARKET_NOT_LISTED` -> DROP

---

## PHASE 10: PUBLISH GATE (v10.43)

**File:** `publish_gate.py`

### 10.1 Dominance Dedup
- Keep only best pick per player per cluster (pts/reb/ast)
- Prevents: Same player, multiple similar markets

### 10.2 Quality Gate
- Escalate thresholds if too many picks
- Target: 14 max actionable picks

### 10.3 Correlation Penalty
- Penalize crowded games (3+ picks same game)
- Penalty: -0.1 per extra pick

---

## PHASE 11: PICK FILTER (v10.56)

**File:** `pick_filter.py`

### Caps & Limits

| Rule | Limit |
|------|-------|
| Max GOLD_STAR | 5 |
| Max EDGE_LEAN | 8 |
| Max Total | 13 |
| Max per Player | 2 |
| Max GOLD_STAR per Player | 1 |
| Max per Game | 3 |

### UNDER Penalty
```python
if side == "Under" and not under_supported:
    final_score -= 0.15
    # Re-tier after penalty
```

---

## PHASE 12: TIERING

**File:** `tiering.py`

### Thresholds (SINGLE SOURCE OF TRUTH)

```python
DEFAULT_TIERS = {
    "GOLD_STAR": {"min": 7.5, "badge": "GOLD_STAR", "units": 2.0, "action": "SMASH"},
    "EDGE_LEAN": {"min": 6.5, "badge": "EDGE_LEAN", "units": 1.0, "action": "PLAY"},
    "MONITOR":   {"min": 5.5, "badge": "MONITOR",   "units": 0.0, "action": "WATCH"},
    "PASS":      {"min": 0.0, "badge": "PASS",      "units": 0.0, "action": "SKIP"},
}

def tier_from_score(score: float) -> Tuple[str, dict]:
    if score >= 7.5: return ("GOLD_STAR", {...})
    if score >= 6.5: return ("EDGE_LEAN", {...})
    if score >= 5.5: return ("MONITOR", {...})
    return ("PASS", {...})
```

---

## PHASE 13: OUTPUT CONTRACT

### Response Schema

```json
{
    "sport": "NBA",
    "props": {
        "picks": [...],
        "count": 10
    },
    "game_picks": {
        "picks": [...],
        "count": 5
    },
    "summary": {
        "total_count": 15,
        "gold_star_count": 3,
        "edge_lean_count": 7
    },
    "debug": {
        "validators": {...},
        "publish_gate": {...},
        "pick_filter": {...}
    }
}
```

### Pick Receipt Schema

See `receipt_schema.py` for full schema definition.

---

## VERIFICATION COMMANDS

```bash
# Run all tests
python -m unittest test_validators test_tiering test_pick_filter test_pipeline -v

# Print receipts for top picks
python tools/print_receipts.py --limit 10

# Verify Deni Avdija case (should be blocked)
python tools/test_dk_market.py --player "Deni Avdija"
```

---

## CHANGELOG

- **v10.57**: Added data integrity validators (prop_integrity, injury_guard, market_availability)
- **v10.56**: Added pick filter (caps, correlation, UNDER penalty)
- **v10.55**: Unified tiering module
- **v10.54**: Production V3 contract compliance
- **v10.43**: Added publish gate (dedup, quality gate, correlation penalty)
