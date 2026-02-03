# MSRF Integration Plan: Mathematical Sequence Resonance Framework

## Executive Summary

The MSRF (Mathematical Sequence Resonance Framework) system calculates "turn dates" using mathematical constants (Pi, Phi, Phi², Heptagon) applied to time intervals between significant dates. This creates a resonance score that can identify cyclically significant days.

**Proposed Integration:** Add MSRF as a new signal in the Esoteric Engine, weighted at 10-15% of esoteric score.

---

## System Analysis

### Mathematical Constants Used
| Constant | Value | Significance |
|----------|-------|--------------|
| `OPH_PI` | 3.14159... | Circle constant, cycles |
| `OPH_PHI` | 1.618... | Golden Ratio, natural growth |
| `OPH_CRV` | 2.618... | Phi² (curved growth) |
| `OPH_HEP` | 7.0 | Heptagon (7-fold symmetry) |

### MSRF Number Lists
| List | Count | Purpose | Notable Numbers |
|------|-------|---------|-----------------|
| `MSRF_NORMAL` | ~250 | Standard resonant numbers | 666, 777, 888, 2178 |
| `MSRF_IMPORTANT` | 36 | High-significance numbers | 144, 432, 720, 1080, 2520 |
| `MSRF_VORTEX` | 19 | Decimal vortex points | 21.7, 144.3, 217.8 |

### 16 Operations (Time Transformations)
```
Alpha Ops (weight 1.0): O1, O2, O5, O6, O9, O10, O15, O16
Beta Ops (weight 0.5):  O3, O4, O7, O8, O11, O12, O13, O14

Transformations include:
- Direct/Flip (O1, O2)
- Division by Phi/CRV (O3, O5)
- Half × constant (O4, O6, O7, O8, O15)
- Multiplication by constant (O9, O10, O11, O12, O13, O16)
- Heptagon operations (O14, O15, O16)
```

---

## Integration Options

### Option A: Game Date Resonance (Recommended)
**Use Case:** Score how "resonant" a game date is based on team/player history

**Input:**
- Player's last 3 significant performance dates (games with standout stats)
- OR Team's last 3 significant wins/losses
- OR Last 3 times this prop line hit

**Output:** Resonance score (0-1) indicating if today is a "turn date"

**Integration Point:** `esoteric_engine.py` → new function `calculate_msrf_resonance()`

### Option B: Line Movement Timing
**Use Case:** Detect if line movements align with MSRF intervals

**Input:** Timestamps of significant line movements

**Output:** Score indicating if current timing is mathematically significant

### Option C: Player Performance Cycles
**Use Case:** Identify players entering/exiting hot streaks based on date cycles

**Input:** Player's last 3 career-high or standout game dates

**Output:** "Cycle alignment" score for today's game

---

## Recommended Implementation Plan

### Phase 1: Core MSRF Module (~150 LOC)

**File:** `signals/msrf_resonance.py`

```python
"""
MSRF - Mathematical Sequence Resonance Framework
Calculates turn date resonance using Pi, Phi, and sacred number sequences.
"""

import datetime as dt
from datetime import timedelta, date
from collections import defaultdict
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger("msrf")

# Constants
OPH_PI = 3.141592653589793
OPH_PHI = 1.618033988749895
OPH_CRV = 2.618033988749895  # phi^2
OPH_HEP = 7.0

# MSRF Number Lists (truncated for brevity - full lists in implementation)
MSRF_NORMAL = [12, 21, 24, 36, 40, 42, 48, 49, ...]  # ~250 numbers
MSRF_IMPORTANT = [138, 144, 207, 210, 216, 414, ...]  # 36 numbers
MSRF_VORTEX = [21.7, 32.6, 43.5, 65.3, ...]  # 19 numbers

MSRF_ENABLED = True  # Feature flag

def calculate_msrf_resonance(
    significant_dates: List[date],
    target_date: date = None,
    context: str = "general"
) -> Dict[str, Any]:
    """
    Calculate MSRF resonance score for a target date.

    Args:
        significant_dates: List of 3+ significant past dates
        target_date: Date to score (default: today)
        context: "player_performance", "line_movement", "team_cycle", "general"

    Returns:
        Dict with score (0-1), triggered, reason, breakdown
    """
    ...

def get_player_msrf_score(
    player_name: str,
    game_date: date,
    sport: str
) -> Dict[str, Any]:
    """
    Get MSRF resonance for a player based on their performance history.
    Pulls last 3 standout games and calculates if game_date is a turn date.
    """
    ...

def get_game_msrf_score(
    home_team: str,
    away_team: str,
    game_date: date,
    sport: str
) -> Dict[str, Any]:
    """
    Get MSRF resonance for a game based on team histories.
    """
    ...
```

### Phase 2: Integration into Esoteric Engine

**File:** `esoteric_engine.py` - Add to `get_glitch_aggregate()`

```python
# In get_glitch_aggregate(), add after Benford:

# 7. MSRF Resonance (weight: 0.10) - Mathematical turn date detection
if MSRF_ENABLED:
    try:
        from signals.msrf_resonance import calculate_msrf_resonance

        # Use significant dates if available (player history, etc.)
        msrf_dates = _get_significant_dates_for_context(...)

        if msrf_dates and len(msrf_dates) >= 3:
            msrf = calculate_msrf_resonance(
                significant_dates=msrf_dates,
                target_date=game_date
            )
            results["msrf"] = msrf
            weight = 0.10
            msrf_score = msrf.get("score", 0.5)
            weighted_score += msrf_score * weight
            total_weight += weight
            if msrf.get("triggered"):
                triggered_signals.append(f"msrf_{msrf.get('resonance_type', 'turn')}")
            reasons.append(f"MSRF: {msrf.get('reason', 'NEUTRAL')}")
    except ImportError:
        pass
```

### Phase 3: Data Source for Significant Dates

**Challenge:** MSRF needs "significant dates" - where do we get them?

**Option 3A: Player Performance History (Best for Props)**
```python
# Query BallDontLie or stored data for player's standout games
def get_player_significant_dates(player_name: str, sport: str) -> List[date]:
    """
    Find dates where player exceeded their season average by 50%+
    Example: If avg 20 PPG, find games with 30+ points
    """
    # Use BallDontLie API for NBA
    # Use stored graded picks for patterns
    ...
```

**Option 3B: Line Movement History (For All Picks)**
```python
# Track when lines moved significantly
def get_line_significant_dates(event_id: str) -> List[date]:
    """
    Find dates of 2+ point line movements for this matchup
    """
    ...
```

**Option 3C: Team Win/Loss Cycles (For Game Picks)**
```python
# Team's last 3 significant wins/losses
def get_team_significant_dates(team: str, sport: str) -> List[date]:
    """
    Find last 3 blowout wins or upset losses
    """
    ...
```

**Option 3D: Stored Prediction History (Easiest)**
```python
# Use our own graded picks as significant dates
def get_pick_significant_dates(player_name: str = None, team: str = None) -> List[date]:
    """
    Find dates where our picks hit or missed significantly
    """
    from grader_store import load_predictions
    # Filter to relevant entity, find standout dates
    ...
```

---

## Weight Recommendation

### Current GLITCH Weights (After Benford)
| Signal | Weight | Total |
|--------|--------|-------|
| Chrome Resonance | 0.25 | 0.25 |
| Void Moon | 0.20 | 0.45 |
| Noosphere | 0.15 | 0.60 |
| Hurst Exponent | 0.25 | 0.85 |
| Kp-Index | 0.25 | 1.10 |
| Benford | 0.10 | 1.20 |

### Proposed with MSRF
| Signal | New Weight | Rationale |
|--------|------------|-----------|
| Chrome Resonance | 0.20 | Reduce slightly |
| Void Moon | 0.15 | Reduce slightly |
| Noosphere | 0.15 | Keep |
| Hurst Exponent | 0.20 | Reduce slightly |
| Kp-Index | 0.15 | Reduce slightly |
| Benford | 0.05 | Reduce (needs more data) |
| **MSRF** | **0.10** | **NEW** |
| **Total** | **1.00** | Normalized |

---

## Scoring Logic

### MSRF Score Interpretation
```python
def interpret_msrf_score(resonance_points: float) -> Dict:
    """
    Convert raw MSRF points to 0-1 score

    Points come from:
    - MSRF_VORTEX match: +2 per operation
    - MSRF_IMPORTANT match: +2 per operation
    - MSRF_NORMAL match: +1 per operation
    - Alpha operation multiplier: ×1.0
    - Beta operation multiplier: ×0.5

    Max theoretical points: ~50+ (many operations hit)
    Typical range: 0-15 points
    """
    if resonance_points >= 10:
        return {"score": 0.95, "level": "EXTREME_RESONANCE", "triggered": True}
    elif resonance_points >= 5:
        return {"score": 0.80, "level": "HIGH_RESONANCE", "triggered": True}
    elif resonance_points >= 2:
        return {"score": 0.65, "level": "MODERATE_RESONANCE", "triggered": False}
    elif resonance_points >= 1:
        return {"score": 0.55, "level": "MILD_RESONANCE", "triggered": False}
    else:
        return {"score": 0.50, "level": "NO_RESONANCE", "triggered": False}
```

### Integration with Betting
```python
# High resonance on a turn date could mean:
# 1. Player breaks out of slump (OVER value)
# 2. Team reverses recent trend
# 3. Line movement incoming

# Betting signal interpretation:
if msrf["level"] == "EXTREME_RESONANCE":
    # Strong contrarian signal - expect reversal
    signal = "POTENTIAL_REVERSAL"
elif msrf["level"] == "HIGH_RESONANCE":
    # Notable cycle point - watch for volatility
    signal = "CYCLE_INFLECTION"
else:
    signal = "NEUTRAL"
```

---

## Files to Create/Modify

| File | Action | Changes |
|------|--------|---------|
| `signals/msrf_resonance.py` | CREATE | Core MSRF calculation (~200 LOC) |
| `signals/__init__.py` | MODIFY | Export MSRF functions |
| `esoteric_engine.py` | MODIFY | Add MSRF to get_glitch_aggregate() |
| `live_data_router.py` | MODIFY | Pass significant dates to GLITCH |
| `context_layer.py` | MODIFY | Add significant date lookup service |

---

## Data Requirements

### For Full Implementation
1. **Player Game Logs** - BallDontLie (NBA), or Playbook API
2. **Historical Line Data** - Odds API historical (may need upgrade)
3. **Our Own Predictions** - Already in `/data/grader/predictions.jsonl`

### Minimum Viable Product (MVP)
Use only our stored predictions as significant dates:
```python
# MVP: Use dates where our picks hit with high confidence
predictions = load_predictions(days=90)
significant = [p["game_date"] for p in predictions
               if p["result"] == "HIT" and p["final_score"] >= 8.0]
```

---

## Testing Plan

### Unit Tests
```python
def test_msrf_score_calculation():
    """Test MSRF with known dates that should produce resonance"""
    dates = [date(2025, 11, 15), date(2025, 12, 24), date(2026, 1, 15)]
    result = calculate_msrf_resonance(dates, target_date=date(2026, 2, 15))
    assert "score" in result
    assert 0 <= result["score"] <= 1

def test_msrf_important_numbers():
    """Verify MSRF_IMPORTANT numbers produce higher scores"""
    # Test that intervals matching 144, 432, 2178 produce +2 points
    ...

def test_msrf_integration_in_glitch():
    """Verify MSRF appears in GLITCH aggregate output"""
    result = get_glitch_aggregate(
        birth_date_str="1990-01-15",
        game_date=date(2026, 2, 1),
        significant_dates=[date(2025, 11, 15), date(2025, 12, 24), date(2026, 1, 15)]
    )
    assert "msrf" in result["breakdown"]
```

### Integration Tests
```bash
# After deployment, verify MSRF in output
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '.props.picks[0].esoteric_reasons | map(select(startswith("MSRF")))'
```

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Insufficient historical data | Medium | Medium | MVP uses our predictions only |
| Overfitting to sacred numbers | Low | Low | Weight at 10% max |
| Performance impact | Low | Low | Simple arithmetic operations |
| False positives on "resonant" days | Medium | Low | Require 5+ points to trigger |

---

## Implementation Order

### Week 1: Core Module
1. Create `signals/msrf_resonance.py` with full MSRF lists and operations
2. Add unit tests for core calculations
3. Export from `signals/__init__.py`

### Week 2: Integration
4. Add MSRF to `get_glitch_aggregate()` with 0.10 weight
5. Create significant date lookup using stored predictions
6. Update `live_data_router.py` to pass dates

### Week 3: Enhancement
7. Add BallDontLie player history lookup for NBA props
8. Add team performance history for game picks
9. Tune weights based on initial results

---

## Questions for Approval

1. **Weight:** Is 10% of GLITCH aggregate appropriate, or should MSRF be standalone?

2. **Data Source:**
   - Option A: Use only our stored predictions (easiest, MVP)
   - Option B: Add BallDontLie player history (more accurate, more API calls)
   - Option C: Both

3. **Trigger Threshold:** Should MSRF trigger signals at 5+ points or higher?

4. **Sacred Numbers:** The MSRF lists include 666, 777, 888, 2178 - should we highlight these specifically as "Jarvis-like" triggers?

5. **Implementation Priority:** Implement now, or after current system stabilizes?

---

## Summary

The MSRF system is a mathematically sophisticated date resonance calculator that fits naturally into the Esoteric Engine. It uses Pi, Phi, and sacred number sequences to identify "turn dates" - days where patterns suggest potential reversals or breakouts.

**Recommended approach:**
- Create standalone module `signals/msrf_resonance.py`
- Integrate into GLITCH aggregate at 10% weight
- MVP uses our stored predictions as significant dates
- Full version adds player/team history lookups

**Estimated effort:** ~250 LOC new code, 2-3 hours implementation

---

*Created: February 2026*
*Status: AWAITING APPROVAL*
