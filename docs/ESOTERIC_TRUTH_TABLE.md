# Engine 3 (Esoteric) Truth Table

**Version:** v20.18
**Last Updated:** 2026-02-10
**Status:** SEMANTICALLY AUDITABLE

---

## Overview

This document defines the **single source of truth** for Engine 3 (Esoteric) signals. Every signal listed here is either:
- **WIRED**: Actively called in the production scoring path
- **PRESENT-BUT-NOT-WIRED**: Code exists but function is never called (dead code)
- **DISABLED**: Code exists and is wired, but gated by missing configuration

**Key Principle**: The `esoteric_breakdown` in API responses MUST only contain signals from the `wired_signals` list. Signals in `present_not_wired` MUST NEVER appear in the breakdown.

---

## External API Dependencies

| API | Env Var | Auth Type | Signals Using It | Status |
|-----|---------|-----------|------------------|--------|
| **NOAA Space Weather** | `NOAA_BASE_URL` (optional), `NOAA_ENABLED` | **NONE** (public API) | kp_index, solar_flare | FREE, no key required |
| **SerpAPI** | `SERPAPI_KEY` | **API Key** | noosphere | DISABLED by default |
| **Astronomy API** | `ASTRONOMY_API_ID` | **API Key** (optional) | void_moon (optional enhancement) | Internal fallback exists |

### Auth Context Schema

```json
{
  "noaa": {
    "auth_type": "none",
    "enabled": true,
    "base_url_source": "env:NOAA_BASE_URL | default"
  },
  "serpapi": {
    "auth_type": "api_key",
    "key_present": false,
    "key_source": "none | env:SERPAPI_KEY"
  }
}
```

**NOAA Notes**:
- `auth_type: "none"` - NOAA is a free public API, no API key required
- `enabled: true` unless `NOAA_ENABLED=false` in environment
- `base_url_source` indicates where the URL config comes from

**SerpAPI Notes**:
- If `key_present: false`, noosphere.status MUST be `"DISABLED"`
- If `key_present: false`, noosphere.call_proof MUST be `null`

---

## Wired Signals (23 Total)

### GLITCH Protocol (6 signals)

Called via `get_glitch_aggregate()` in esoteric_engine.py (lines 1234-1450)

| Signal | Source Type | Source API | Required Inputs | Failure Behavior | Max Contribution |
|--------|-------------|------------|-----------------|------------------|------------------|
| `chrome_resonance` | INTERNAL | null | birth_date, game_date | NO_DATA if birth_date missing | 0.25 weight |
| `void_moon` | INTERNAL | null | game_date | Uses astronomical_api fallback | 0.20 weight |
| `noosphere` | EXTERNAL | serpapi | teams, player | DISABLED if SERPAPI_KEY absent | 0.15 weight |
| `hurst` | INTERNAL | null | line_history (10+ values) | NO_DATA if insufficient history | 0.25 weight |
| `kp_index` | EXTERNAL | noaa | none | Fallback to schumann simulation | 0.25 weight |
| `benford` | INTERNAL | null | value_for_benford (10+ values) | NO_DATA if insufficient values | 0.10 weight |

### Phase 8 (5 signals)

Called via `get_phase8_esoteric_signals()` in esoteric_engine.py (lines 2053-2188)

| Signal | Source Type | Source API | Required Inputs | Failure Behavior | Boost Range |
|--------|-------------|------------|-----------------|------------------|-------------|
| `lunar_phase` | INTERNAL | null | game_datetime | Uses synodic month calculation | ±0.30 |
| `mercury_retrograde` | INTERNAL | null | game_date | Uses hardcoded 2024-2027 dates | -0.20 to 0 |
| `rivalry_intensity` | INTERNAL | null | sport, home_team, away_team | Returns no boost if not rivalry | +0.30 |
| `streak_momentum` | INTERNAL | null | team, streak_length, streak_type | Returns no boost if no streak | ±0.25 |
| `solar_flare` | EXTERNAL | noaa | game_time | Fallback to kp_index estimate | +0.20 |

### Phase 1 (5 signals - Dormant→Active)

| Signal | Source Type | Source API | Required Inputs | Failure Behavior | Applies To |
|--------|-------------|------------|-----------------|------------------|------------|
| `biorhythm` | INTERNAL | null | birth_date, game_date | NO_DATA if birth_date missing | PROP only |
| `gann_square` | INTERNAL | null | spread, total | NO_DATA if both missing | GAME only |
| `founders_echo` | INTERNAL | null | home_team, away_team | NO_DATA if teams missing | GAME only |
| `numerology` | INTERNAL | null | player_name OR game_string, game_date | Uses game_string as fallback | ALL |
| `astro_score` | INTERNAL | null | game_date | Uses VedicAstrology module | ALL |

### Supporting Signals (7 signals)

| Signal | Source Type | Source API | Required Inputs | Failure Behavior |
|--------|-------------|------------|-----------------|------------------|
| `vortex_energy` | INTERNAL | null | prop_line OR total OR spread | NO_DATA if all missing |
| `fibonacci` | INTERNAL | null | magnitude value | NO_DATA if missing |
| `fib_retracement` | INTERNAL | null | current_line, season_high, season_low | NO_DATA if no extremes |
| `altitude_impact` | INTERNAL | null | venue_city | NO_DATA if city unknown |
| `surface_impact` | INTERNAL | null | sport, venue | NO_DATA if not outdoor sport |
| `daily_edge` | INTERNAL | null | game_date | Always returns value |
| `trap_mod` | INTERNAL | null | spread, total | Always returns value (may be 0) |

---

## Present But Not Wired (6 signals)

**WARNING**: These signals have code but are NEVER CALLED in the production path. They MUST NOT appear in `esoteric_breakdown`.

| Signal | Location | Status | Why Not Wired |
|--------|----------|--------|---------------|
| `golden_ratio` | signals/math_glitch.py | DORMANT | Code exists but not called from get_glitch_aggregate() |
| `prime_resonance` | signals/math_glitch.py | DORMANT | Code exists but not called from get_glitch_aggregate() |
| `phoenix_resonance` | esoteric_engine.py | DORMANT | calculate_phoenix_resonance() exists but not called |
| `planetary_hour` | jarvis_savant_engine.py | DORMANT | VedicAstroEngine.calculate_planetary_hour() exists but not used in scoring |
| `symmetry_analysis` | signals/math_glitch.py | ORPHANED | Not called from get_glitch_aggregate() |
| `parlay_correlations` | esoteric_engine.py | ORPHANED | Only for parlay endpoint |

### Fallback Signals (not counted in total)

| Signal | Location | Status | Why Not Counted |
|--------|----------|--------|-----------------|
| `schumann_fallback` | esoteric_engine.py:375-417 | FALLBACK ONLY | Only used when NOAA fails |

---

## Signal Status Values

| Status | Meaning | When to Use |
|--------|---------|-------------|
| `SUCCESS` | Signal computed with valid data | External API returned 2xx OR internal calc succeeded with required inputs |
| `NO_DATA` | Required inputs missing | Internal signal with missing birth_date, line_history, etc. |
| `DISABLED` | Feature disabled by config | SERPAPI_KEY absent for noosphere |
| `ERROR` | Computation failed | Exception during calculation |
| `FALLBACK` | Using backup data source | NOAA failed, using Schumann simulation |

### Status Invariants

1. **SUCCESS for EXTERNAL signals** requires `request_proof.noaa_2xx >= 1` OR `call_proof.cache_hit == true`
2. **DISABLED** requires the feature flag to be explicitly off (not just missing data)
3. **NO_DATA** for INTERNAL signals when `required_inputs_present` has any `false` values
4. If `auth_context.serpapi.key_present == false` then `noosphere.status == "DISABLED"`
5. If `auth_context.noaa.enabled == false` then `kp_index.status == "DISABLED"` AND `solar_flare.status == "DISABLED"`

---

## Per-Signal Provenance Schema

Every signal in `esoteric_breakdown` MUST have this structure:

```json
{
  "signal_name": {
    "value": 0.8,
    "status": "SUCCESS | NO_DATA | DISABLED | ERROR | FALLBACK",
    "source_api": "noaa | serpapi | null",
    "source_type": "EXTERNAL | INTERNAL",
    "raw_inputs_summary": {
      "required_inputs_present": {
        "input_name_1": true,
        "input_name_2": false
      },
      "...signal-specific-data..."
    },
    "call_proof": {
      "source": "noaa_live | cache | fallback | null",
      "cache_hit": false,
      "fetched_at": "2026-02-10T12:00:00Z",
      "http_requests_delta": 1,
      "2xx_delta": 1
    },
    "triggered": true,
    "contribution": 0.8
  }
}
```

**Notes**:
- `source_api: null` for all INTERNAL signals
- `call_proof: null` for all INTERNAL signals
- `call_proof.http_requests_delta` MUST match request_proof counters

---

## Anti-Conflation Rules

1. **Separate objects**: Each signal returns its own dict, never shares state with others
2. **Exclusive meaning**: kp_index cannot modify lunar_phase strength or vice versa
3. **Failure truthfulness**:
   - NOAA enabled=false => kp_index AND solar_flare status MUST be DISABLED
   - SerpAPI key_present=false => noosphere status MUST be DISABLED
   - If 2xx_delta==0 AND cache_hit==false => status MUST be NO_DATA or ERROR (not SUCCESS)
4. **Source attribution**: Every signal MUST have source_api field (null for internal, string for external)
5. **Dead code isolation**: Signals not in wired_signals MUST NEVER appear in breakdown

---

## Cache Truthfulness Invariants

These invariants ensure call_proof claims match request_proof evidence:

1. **SUCCESS requires proof**: If status == SUCCESS for EXTERNAL signal, then:
   - `request_proof.noaa_2xx >= 1` OR `request_proof.noaa_cache_hits >= 1`

2. **Live call claim**: If `call_proof.source == "noaa_live"`, then:
   - `request_proof.noaa_2xx >= 1`

3. **Cache hit claim**: If `call_proof.cache_hit == true`, then:
   - `request_proof.noaa_cache_hits >= 1`

4. **Delta consistency**: `call_proof.http_requests_delta` MUST be derived from request_proof, not hardcoded

---

## Verification Commands

```bash
# Check esoteric_breakdown structure
curl /debug/esoteric-candidates/NBA?limit=1 -H "X-API-Key: KEY" | \
  jq '.candidates_pre_filter[0].esoteric_breakdown | keys'

# Verify auth_context for NOAA (should NOT have key_present)
curl /debug/esoteric-candidates/NBA?limit=1 -H "X-API-Key: KEY" | \
  jq '.auth_context.noaa'

# Check request_proof
curl /debug/esoteric-candidates/NBA?limit=1 -H "X-API-Key: KEY" | \
  jq '.request_proof'

# Verify kp_index source attribution
curl /debug/esoteric-candidates/NBA?limit=1 -H "X-API-Key: KEY" | \
  jq '.candidates_pre_filter[0].esoteric_breakdown.kp_index | {source_api, status, call_proof}'

# Check suppressed candidates have full breakdown
curl /debug/esoteric-candidates/NBA?limit=50 -H "X-API-Key: KEY" | \
  jq '[.candidates_pre_filter[] | select(.passed_filter == false)] | .[0].esoteric_breakdown | keys | length'
# Should be 23 (all wired signals present)
```

---

## Machine-Readable Signal Lists

```yaml
# Machine-readable signal lists for test assertions
# Tests assert: breakdown signals ⊆ wired_signals
# Tests assert: present_not_wired signals NOT in breakdown

wired_signals:
  # GLITCH Protocol (6)
  - chrome_resonance
  - void_moon
  - noosphere  # DISABLED but wired
  - hurst
  - kp_index
  - benford
  # Phase 8 (5)
  - lunar_phase
  - mercury_retrograde
  - rivalry_intensity
  - streak_momentum
  - solar_flare
  # Phase 1 (5)
  - biorhythm
  - gann_square
  - founders_echo
  - numerology
  - astro_score
  # Supporting (7)
  - vortex_energy
  - fibonacci
  - fib_retracement
  - altitude_impact
  - surface_impact
  - daily_edge
  - trap_mod

present_not_wired:
  - golden_ratio       # Code exists but not called
  - prime_resonance    # Code exists but not called
  - phoenix_resonance  # Code exists but not called
  - planetary_hour     # Code exists but not called
  - symmetry_analysis
  - parlay_correlations

# Fallback signals (not in wired count)
fallback_signals:
  - schumann_fallback

external_api_signals:
  noaa:
    - kp_index
    - solar_flare
  serpapi:
    - noosphere

internal_signals:
  - chrome_resonance
  - void_moon
  - hurst
  - benford
  - lunar_phase
  - mercury_retrograde
  - rivalry_intensity
  - streak_momentum
  - biorhythm
  - gann_square
  - founders_echo
  - numerology
  - astro_score
  - vortex_energy
  - fibonacci
  - fib_retracement
  - altitude_impact
  - surface_impact
  - daily_edge
  - trap_mod

required_inputs_by_signal:
  chrome_resonance:
    - birth_date
    - game_date
  void_moon:
    - game_date
  noosphere:
    - teams
    - player
  hurst:
    - line_history
  kp_index: []  # External API, no local inputs
  benford:
    - value_for_benford
  lunar_phase:
    - game_datetime
  mercury_retrograde:
    - game_date
  rivalry_intensity:
    - sport
    - home_team
    - away_team
  streak_momentum:
    - team
    - streak_length
    - streak_type
  solar_flare:
    - game_time
  biorhythm:
    - birth_date
    - game_date
  gann_square:
    - spread
    - total
  founders_echo:
    - home_team
    - away_team
  numerology:
    - player_name
    - game_date
  astro_score:
    - game_date
  vortex_energy:
    - prop_line
  fibonacci:
    - magnitude
  fib_retracement:
    - current_line
    - season_high
    - season_low
  altitude_impact:
    - venue_city
  surface_impact:
    - sport
    - venue
  daily_edge:
    - game_date
  trap_mod:
    - spread
    - total

signal_status_enum:
  - SUCCESS
  - NO_DATA
  - DISABLED
  - ERROR
  - FALLBACK

source_type_enum:
  - EXTERNAL
  - INTERNAL
```

---

## Related Documentation

- `docs/AUDIT_ENGINE3_ESOTERIC.md` - Existing audit document
- `core/scoring_contract.py` - Engine weights (esoteric = 0.15)
- `tests/test_esoteric_truthfulness.py` - Semantic truthfulness tests
- `scripts/engine3_esoteric_audit.py` - Runtime audit script
