# Engine 3 (Esoteric) Boundary Audit

**Version:** v20.14
**Last Updated:** 2026-02-08
**Status:** ACTIVE (Weight: 0.20)

## Overview

Engine 3 (Esoteric) contributes 20% of the BASE_4 score in the Option A scoring formula:

```
BASE_4 = (AI * 0.25) + (Research * 0.35) + (Esoteric * 0.20) + (Jarvis * 0.20)
FINAL  = clamp(0..10, BASE_4 + context_modifier + post_base_boosts)
```

---

## Canonical Modules

| Module | Purpose | Key Functions |
|--------|---------|---------------|
| `esoteric_engine.py` | Core orchestration | `compute_esoteric_score()`, `get_glitch_aggregate()`, `get_phase8_esoteric_signals()` |
| `signals/physics.py` | Physics signals | `analyze_spread_gann()`, `calculate_fibonacci_alignment()`, `calculate_fibonacci_retracement()`, `calculate_hurst_exponent()` |
| `signals/math_glitch.py` | Math anomaly signals | `check_benford_anomaly()` |
| `signals/hive_mind.py` | Void moon calculation | `get_void_moon()` |
| `alt_data_sources/noaa.py` | NOAA Space Weather API | `get_kp_betting_signal()`, `get_solar_flare_status()` |

---

## 29 Esoteric Signals (Derived from Code + Runtime)

| Status | Category | Signal | Source Module | Call Chain |
|--------|----------|--------|---------------|------------|
| ACTIVE | GLITCH | chrome_resonance | `esoteric_engine.py` | `get_glitch_aggregate()` -> `calculate_chrome_resonance()` |
| ACTIVE | GLITCH | void_moon | `signals/hive_mind.py` | `get_glitch_aggregate()` -> `get_void_moon()` |
| DISABLED | GLITCH | noosphere | `esoteric_engine.py` | Requires SERPAPI_KEY (cancelled) |
| ACTIVE | GLITCH | hurst | `signals/physics.py` | `get_glitch_aggregate()` -> `calculate_hurst_exponent()` |
| ACTIVE | GLITCH | kp_index | `alt_data_sources/noaa.py` | `get_glitch_aggregate()` -> `get_kp_betting_signal()` |
| ACTIVE | GLITCH | benford | `signals/math_glitch.py` | `get_glitch_aggregate()` -> `check_benford_anomaly()` |
| ACTIVE | Phase 8 | lunar_phase | `esoteric_engine.py` | `get_phase8_esoteric_signals()` -> `calculate_lunar_phase_intensity()` |
| ACTIVE | Phase 8 | mercury_retrograde | `esoteric_engine.py` | `get_phase8_esoteric_signals()` -> `check_mercury_retrograde()` |
| ACTIVE | Phase 8 | rivalry_intensity | `esoteric_engine.py` | `get_phase8_esoteric_signals()` -> `calculate_rivalry_intensity()` |
| ACTIVE | Phase 8 | streak_momentum | `esoteric_engine.py` | `get_phase8_esoteric_signals()` -> `calculate_streak_momentum()` |
| ACTIVE | Phase 8 | solar_flare | `alt_data_sources/noaa.py` | `get_phase8_esoteric_signals()` -> `get_solar_flare_status()` |
| ACTIVE | Physics | gann_angles | `signals/physics.py` | `analyze_spread_gann()` |
| ACTIVE | Physics | fibonacci_levels | `signals/physics.py` | `calculate_fibonacci_alignment()` |
| ACTIVE | Physics | fibonacci_retracement | `signals/physics.py` | `calculate_fibonacci_retracement()` |
| ACTIVE | Physics | barometric_pressure | `signals/physics.py` | `get_barometric_impact()` |
| DORMANT | Physics | schumann_resonance | `signals/physics.py` | `get_schumann_frequency()` - fallback only |
| ACTIVE | Math Glitch | vortex_energy | `esoteric_engine.py` | `calculate_vortex_energy()` |
| DORMANT | Math Glitch | golden_ratio | `signals/math_glitch.py` | `check_golden_ratio()` - not wired |
| DORMANT | Math Glitch | prime_detection | `signals/math_glitch.py` | `check_prime_number()` - not wired |
| DORMANT | Math Glitch | symmetry_analysis | `signals/math_glitch.py` | `check_symmetry()` - not wired |
| ACTIVE | Phase 1 | numerology | `esoteric_engine.py` | `calculate_generic_numerology()` |
| ACTIVE | Phase 1 | astro_transits | `esoteric_engine.py` | Vedic astrology integration |
| ACTIVE | Phase 1 | daily_edge | `esoteric_engine.py` | `get_daily_energy()` |
| ACTIVE | Phase 1 | biorhythms | `esoteric_engine.py` | `calculate_biorhythms()` - PROP only |
| ACTIVE | Phase 1 | founders_echo | `esoteric_engine.py` | `check_founders_echo()` - GAME only |
| ACTIVE | Context | altitude_impact | `alt_data_sources/stadium.py` | `calculate_altitude_impact()` |
| ACTIVE | Context | travel_fatigue | `live_data_router.py` | `_rest_days_for_team()` |
| ACTIVE | Context | park_factors | `context_layer.py` | `ParkFactorService` - MLB only |
| ACTIVE | Context | surface_impact | `alt_data_sources/stadium.py` | `get_surface_impact()` |

### Signal Count Summary

| Status | Count | Description |
|--------|-------|-------------|
| **ACTIVE** | 23 | Wired and firing in production |
| **DORMANT** | 4 | Code exists but not called (golden_ratio, prime, symmetry, schumann) |
| **DISABLED** | 1 | Noosphere (SERP cancelled, no SERPAPI_KEY) |
| **Total** | 29 | |

---

## Functions Producing esoteric_score

| Function | Module | Purpose |
|----------|--------|---------|
| `compute_esoteric_score()` | `esoteric_engine.py` | Main entry point for Engine 3 |
| `get_glitch_aggregate()` | `esoteric_engine.py` | GLITCH protocol aggregation (6 signals) |
| `get_phase8_esoteric_signals()` | `esoteric_engine.py` | Phase 8 aggregation (5 signals) |

**Output Range:** `esoteric_score` in range [0.0, 10.0]

---

## Debug Payload Fields (Derived from Production)

These fields are emitted in best-bets responses when `?debug=1`:

| Field | Type | Description |
|-------|------|-------------|
| `esoteric_score` | float | Final Engine 3 score [0.0-10.0] |
| `esoteric_reasons` | List[str] | Contributing signals (strings) |
| `esoteric_contributions` | Dict[str, float] | Signal -> contribution value |
| `phase8_boost` | float | Total Phase 8 boost applied |
| `phase8_reasons` | List[str] | Phase 8 signal reasons |
| `phase8_breakdown` | Dict | lunar, mercury, rivalry, streak, solar details |
| `glitch_adjustment` | float | Adjustment from GLITCH aggregate |
| `glitch_signals` | Dict[str, float] | GLITCH signal -> value |
| `glitch_breakdown` | Dict | Detailed breakdown including benford.values_count |
| `kp_index_value` | float | Real-time Kp-Index from NOAA |
| `kp_index_source` | str | "noaa_live" or "fallback" |

---

## GLITCH Protocol Details

**Weight Sum:** Must equal 1.0

| Signal | Weight | Source | Trigger Condition |
|--------|--------|--------|-------------------|
| chrome_resonance | 0.25 | Player birthday + game date | Chromatic interval is Perfect 5th/4th/Unison |
| void_moon | 0.20 | Astronomical calculation | Moon is void-of-course |
| noosphere | 0.15 | SerpAPI (DISABLED) | Search velocity > ±0.2 |
| hurst | 0.25 | Line history analysis | H ≠ 0.5 (trending/mean-reverting) |
| kp_index | 0.25 | NOAA Space Weather API | Geomagnetic storm (Kp ≥ 5) |
| benford | 0.10 | Line value distribution | Chi-squared deviation ≥ 0.25 |

---

## Phase 8 Signals Details

| Signal | Boost Range | Trigger Condition |
|--------|-------------|-------------------|
| lunar_phase | ±0.3 | Full moon (0.45-0.55) or New moon (0.0-0.05) |
| mercury_retrograde | -0.2 | During 2026 retrograde periods |
| rivalry_intensity | +0.3 | Historic rivalry matchups (204 rivalries) |
| streak_momentum | ±0.25 | 2+ game win/loss streaks |
| solar_flare | +0.2 | X-class or M-class flare from NOAA |

---

## External Dependencies

| API | Env Var | Cost | Cache TTL | Fallback |
|-----|---------|------|-----------|----------|
| NOAA Space Weather | None (public) | FREE | 3 hours | Time-based simulation |
| Astronomy (VOC) | ASTRONOMY_API_ID (optional) | FREE tier | 24 hours | Meeus calculation |

---

## Verification Commands

```bash
# Check esoteric_score in production pick
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '.game_picks.picks[0] | {esoteric_score, esoteric_reasons}'

# Check GLITCH breakdown
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '.game_picks.picks[0].glitch_breakdown'

# Check Phase 8 signals
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '.game_picks.picks[0].phase8_breakdown'

# Check Kp-Index source
curl /live/best-bets/NBA?debug=1 -H "X-API-Key: KEY" | \
  jq '.game_picks.picks[0] | {kp_value: .glitch_breakdown.kp_index.kp_value, source: .glitch_breakdown.kp_index.source}'

# Verify esoteric weight in scoring_contract
grep -A5 "ENGINE_WEIGHTS" core/scoring_contract.py | grep esoteric
# Should show: "esoteric": 0.20
```

---

## Related Documentation

- `core/scoring_contract.py` - Engine weights (esoteric = 0.20)
- `core/scoring_pipeline.py` - Score computation
- `CLAUDE.md` - Master documentation (Invariant 16: 18-Pillar Scoring)
- `docs/JARVIS_SAVANT_MASTER_SPEC.md` - Full system specification
