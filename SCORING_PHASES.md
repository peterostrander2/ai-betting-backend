# JARVIS SAVANT ENGINE v7.3 - Scoring Phases Documentation

**Status:** COMPLETE (Phase 1, 2, 3)
**Branch:** `claude/complete-scoring-phases-P8575`
**Audit Date:** 2026-01-14

---

## Overview

The JARVIS Savant Engine is a comprehensive esoteric scoring system for sports betting analysis. It combines numerology, gematria, astrology, and machine learning into a unified scoring framework with a learning loop for continuous improvement.

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    JARVIS SAVANT ENGINE v7.3                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │   PHASE 1   │  │   PHASE 2   │  │        PHASE 3          │ │
│  │ Confluence  │  │ Vedic/Astro │  │    Learning Loop        │ │
│  │    Core     │  │   Module    │  │                         │ │
│  └──────┬──────┘  └──────┬──────┘  └───────────┬─────────────┘ │
│         │                │                     │               │
│         └────────┬───────┴─────────────────────┘               │
│                  │                                              │
│                  ▼                                              │
│         ┌───────────────┐                                      │
│         │  CONFLUENCE   │ ──► Bet Tier ──► Action              │
│         │  (THE HEART)  │                                      │
│         └───────────────┘                                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Confluence Core

**Class:** `JarvisSavantEngine`
**File:** `jarvis_savant_engine.py`

### JARVIS Triggers

| Number | Name | Boost | Tier | Description |
|--------|------|-------|------|-------------|
| 2178 | THE IMMORTAL | 20 | LEGENDARY | n^4=reverse AND n^4=66^4. Never collapses. |
| 201 | THE ORDER | 12 | HIGH | Jesuit Order gematria. The Event of 201. |
| 33 | THE MASTER | 10 | HIGH | Highest master number. Masonic significance. |
| 93 | THE WILL | 10 | HIGH | Thelema sacred number. Will and Love. |
| 322 | THE SOCIETY | 10 | HIGH | Skull & Bones. Genesis 3:22. |
| 666 | THE BEAST | 8 | MEDIUM | Number of the beast. Solar square sum. |
| 888 | JESUS | 8 | MEDIUM | Greek gematria for Jesus. Divine counterbalance. |
| 369 | TESLA KEY | 7 | MEDIUM | Tesla's universe key. Vortex mathematics. |

### Methods

| Method | Description | Returns |
|--------|-------------|---------|
| `validate_2178()` | Mathematical proof of THE IMMORTAL | Dict with proof details |
| `check_jarvis_trigger(value)` | Check if value triggers JARVIS numbers | Triggers hit, total boost |
| `calculate_gematria(text)` | Simple, Reverse, Jewish gematria | Dict with values |
| `calculate_gematria_signal(player, team, opponent)` | Full gematria analysis | Signal strength, weight |
| `calculate_public_fade_signal(public_pct)` | Public fade detection | -13% in crush zone |
| `calculate_mid_spread_signal(spread)` | Goldilocks zone detection | +20% in 3-7 range |
| `calculate_large_spread_trap(spread, total)` | Trap game detection | -20% for spread >14 |
| `calculate_confluence(...)` | THE HEART - signal agreement | Level (GODMODE to AVOID) |
| `calculate_blended_probability(model, esoteric)` | 67/33 formula | Blended probability |
| `determine_bet_tier(confluence, blended, score)` | Final bet recommendation | Tier, unit size, action |

### Confluence Levels

| Level | Signals | Multiplier | Action |
|-------|---------|------------|--------|
| GODMODE | 6/6 | 1.5x | SMASH WITH CONFIDENCE |
| LEGENDARY | 5/6 | 1.3x | STRONG PLAY |
| STRONG | 4/6 | 1.2x | PLAY |
| MODERATE | 3/6 | 1.1x | LEAN |
| WEAK | 2/6 | 1.0x | MONITOR |
| AVOID | 0-1/6 | 0.8x | PASS |

### Bet Tiers

| Tier | Criteria | Unit Size |
|------|----------|-----------|
| GOLD_STAR | LEGENDARY+ AND >70% probability | 3.0 units |
| EDGE_LEAN | STRONG+ AND >60% probability | 2.0 units |
| SPRINKLE | MODERATE+ AND >55% probability | 1.0 units |
| PASS | Below thresholds | 0 units |

---

## Phase 2: Vedic/Astro Module

**Class:** `VedicAstroEngine`
**File:** `jarvis_savant_engine.py`

### Components

#### Planetary Hours (Chaldean Order)
```
Saturn → Jupiter → Mars → Sun → Venus → Mercury → Moon
```

Day rulers follow traditional assignment:
- Sunday: Sun
- Monday: Moon
- Tuesday: Mars
- Wednesday: Mercury
- Thursday: Jupiter
- Friday: Venus
- Saturday: Saturn

#### 27 Nakshatras (Lunar Mansions)

| # | Name | Nature | Betting Signal |
|---|------|--------|----------------|
| 1 | Ashwini | Swift | Light |
| 2 | Bharani | Fierce | Balanced |
| 3 | Krittika | Sharp | Mixed |
| ... | ... | ... | ... |
| 24 | Shatabhisha | Moveable | Balanced |
| 27 | Revati | Soft | Auspicious |

#### Retrograde Tracking

| Planet | Effect on Betting |
|--------|-------------------|
| Mercury | Avoid parlays, miscommunication likely |
| Venus | Value bets unreliable |
| Mars | Underdogs favored, delayed action |

### Methods

| Method | Description | Weight |
|--------|-------------|--------|
| `calculate_planetary_hour()` | Current hour ruler | 40% |
| `calculate_nakshatra()` | Current lunar mansion | 35% |
| `is_planet_retrograde(planet)` | Retrograde check | 25% |
| `calculate_astro_score()` | Combined astro score | 0-100 |

### Astro Score Formula

```
ASTRO_SCORE = (hour_score × 0.40) + (nakshatra_score × 0.35) + (retrograde_score × 0.25)
```

---

## Phase 3: Learning Loop

**Class:** `EsotericLearningLoop`
**File:** `jarvis_savant_engine.py`
**Storage:** `./esoteric_learning_data/`

### Default Weights

| Signal | Weight | Range |
|--------|--------|-------|
| Gematria | 40% | 30-55% (dynamic) |
| Numerology | 17% | 15-20% |
| Astro | 13% | 13% |
| Vedic | 10% | 10% |
| Sacred | 8% | 5-10% |
| Fibonacci | 7% | 5-8% |
| Vortex | 5% | 5-7% |

### Methods

| Method | Description |
|--------|-------------|
| `log_pick(...)` | Track pick with all esoteric signals |
| `grade_pick(pick_id, result)` | Grade with WIN/LOSS/PUSH |
| `get_performance(days_back)` | Performance by signal type |
| `adjust_weights(learning_rate)` | Gradient-based weight adjustment |
| `get_weights()` | Current learned weights |
| `get_recent_picks(limit)` | Review recent picks |

### Learning Algorithm

```python
for signal in signals:
    hit_rate = wins / (wins + losses)

    if hit_rate > 0.55:
        delta = learning_rate * (hit_rate - 0.50)
    elif hit_rate < 0.48:
        delta = -learning_rate * (0.50 - hit_rate)
    else:
        delta = 0.0

    new_weight = clip(current_weight + delta, 0.05, 0.55)
```

### Data Persistence

Files saved to `./esoteric_learning_data/`:
- `weights.json` - Learned signal weights
- `picks.json` - All logged picks
- `performance.json` - Performance metrics

---

## API Endpoints

### Phase 1: Confluence Core

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/live/validate-immortal` | GET | 2178 mathematical proof |
| `/live/jarvis-triggers` | GET | All trigger numbers |
| `/live/check-trigger/{value}` | GET | Test any number/string |
| `/live/confluence/{sport}` | GET | Full confluence analysis |

### Phase 2: Vedic/Astro

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/live/astro-status` | GET | Full astrological analysis |
| `/live/planetary-hour` | GET | Current hour ruler |
| `/live/nakshatra` | GET | Current lunar mansion |
| `/live/retrograde-status` | GET | Mercury/Venus/Mars retrograde |

### Phase 3: Learning Loop

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/live/learning/log-pick` | POST | Log a pick for tracking |
| `/live/learning/grade-pick` | POST | Grade with outcome |
| `/live/learning/performance` | GET | Performance summary |
| `/live/learning/weights` | GET | Current learned weights |
| `/live/learning/adjust-weights` | POST | Trigger weight adjustment |
| `/live/learning/recent-picks` | GET | Review recent picks |

### Combined Analysis

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/live/esoteric-analysis` | GET | Full Phase 1-3 analysis |

---

## Integration with Best-Bets

The `/live/best-bets/{sport}` endpoint now integrates all three phases:

1. **Scoring Enhancement**
   - Full JARVIS trigger detection
   - Gematria signal for player/team names
   - Confluence level calculation
   - Astro score integration

2. **Response Includes**
   - `confluence_level` per pick
   - `scoring_breakdown` with all components
   - `esoteric.daily_energy`
   - `esoteric.astro_status`
   - `esoteric.learned_weights`

3. **Score Formula**
   ```
   total_score = (ai_score + pillar_score + jarvis_score + esoteric_boost) × confluence_multiplier
   ```

---

## Testing

Run the test script:
```bash
python jarvis_savant_engine.py
```

Expected output:
```
======================================================================
JARVIS SAVANT ENGINE v7.3 - TESTING
======================================================================

[PHASE 1: CONFLUENCE CORE]
  2178 Validation: Is Immortal: True
  Trigger Detection: Total Boost: 20

[PHASE 2: VEDIC/ASTRO]
  Planetary Hour: Jupiter (favorable)
  Nakshatra: Shatabhisha (Moveable)
  Mercury Retrograde: False
  Astro Score: 62.8/100 (MEDIUM)

[PHASE 3: LEARNING LOOP]
  Current Weights: gematria=40%, numerology=17%...
  Total Picks Tracked: 0

[FULL ESOTERIC ANALYSIS]
  Total Esoteric Score: 7.58/10
  Confluence Level: STRONG
  Bet Tier: EDGE_LEAN
======================================================================
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 7.3 | 2026-01-14 | Phase 1, 2, 3 complete |
| 14.3 | 2026-01-14 | Router updated to JARVIS_SAVANT |

---

## Files Modified

| File | Changes |
|------|---------|
| `jarvis_savant_engine.py` | NEW - All Phase 1-3 classes |
| `live_data_router.py` | +555 lines - All new endpoints |

---

## Audit Checklist

- [x] Phase 1: Confluence Core
  - [x] JarvisSavantEngine class
  - [x] 8 JARVIS triggers defined
  - [x] validate_2178() working
  - [x] check_jarvis_trigger() working
  - [x] Gematria calculations working
  - [x] Confluence levels working
  - [x] Blended probability (67/33) working
  - [x] Bet tier determination working

- [x] Phase 2: Vedic/Astro
  - [x] VedicAstroEngine class
  - [x] 7 planets (Chaldean order)
  - [x] 27 nakshatras defined
  - [x] Planetary hour calculation
  - [x] Nakshatra calculation
  - [x] Retrograde detection
  - [x] Astro score formula (40/35/25)

- [x] Phase 3: Learning Loop
  - [x] EsotericLearningLoop class
  - [x] 7 default weights defined
  - [x] log_pick() working
  - [x] grade_pick() working
  - [x] Performance tracking
  - [x] Weight adjustment algorithm
  - [x] Data persistence

- [x] API Endpoints
  - [x] 4 Phase 1 endpoints
  - [x] 4 Phase 2 endpoints
  - [x] 6 Phase 3 endpoints
  - [x] 1 combined analysis endpoint
  - [x] best-bets integration

- [x] Documentation
  - [x] SCORING_PHASES.md created
  - [x] All methods documented
  - [x] All endpoints documented
  - [x] Test instructions included

**AUDIT COMPLETE - ALL PHASES VERIFIED**
