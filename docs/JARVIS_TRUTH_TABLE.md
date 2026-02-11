# ENGINE 4 (JARVIS) - TRUTH TABLE

**Generated:** Step 1 Wiring Investigation (Feb 10, 2026)
**Updated:** Step 3 Implementation (Feb 11, 2026)
**Constraint:** Production selector now available via JARVIS_IMPL env var

---

## WIRING SUMMARY

- **Default Jarvis implementation:** `JarvisSavantEngine` v11.08 from `jarvis_savant_engine.py`
- **Alternative implementation:** `JarvisOphisHybrid` v2.0 from `core/jarvis_ophis_hybrid.py`
- **Selector:** `JARVIS_IMPL` env var ("savant" default, "hybrid" available)
- **Fallback conditions:** Invalid JARVIS_IMPL value defaults to "savant"
- **Hybrid status:** AVAILABLE (selectable via `JARVIS_IMPL=hybrid`)

---

## CODE POINTER INDEX

| Component | File | Lines | Purpose |
|-----------|------|-------|---------|
| Jarvis Entry Point | `live_data_router.py` | 2870-3091 | `calculate_jarvis_engine_score()` - v16.0 ADDITIVE |
| Call Site | `live_data_router.py` | 3995-4012 | Where Jarvis is called from `calculate_pick_score()` |
| Singleton Init | `live_data_router.py` | 13161-13171 | `get_jarvis_savant()` lazy loader |
| Savant Engine Class | `jarvis_savant_engine.py` | 282-1055 | `JarvisSavantEngine` class (v11.08) |
| Trigger Detection | `jarvis_savant_engine.py` | 350-425 | `check_jarvis_trigger()` |
| Gematria Calculation | `jarvis_savant_engine.py` | 437-456 | `calculate_gematria()` |
| Gematria Signal | `jarvis_savant_engine.py` | 458-503 | `calculate_gematria_signal()` |
| Mid-Spread Signal | `jarvis_savant_engine.py` | 856-888 | `calculate_mid_spread_signal()` |
| Hybrid (DEAD_CODE) | `core/jarvis_ophis_hybrid.py` | 1-515 | Never imported in scoring path |
| Trigger Contributions | `live_data_router.py` | 2912-2921 | `TRIGGER_CONTRIBUTIONS` dict |
| Stacking Decay | `live_data_router.py` | 2928 | `STACKING_DECAY = 0.7` |
| String Fallback | `live_data_router.py` | 3036-3057 | Fallback when jarvis_engine is None |

---

## IMPLEMENTATION SELECTOR

**File:** `live_data_router.py`
**Env Var:** `JARVIS_IMPL` (default: "savant", options: "savant" | "hybrid")
**Functions:** `get_jarvis_impl()`, `get_jarvis_engine()`

```python
JARVIS_IMPL = os.getenv("JARVIS_IMPL", "savant").lower()
if JARVIS_IMPL not in ("savant", "hybrid"):
    logger.warning("Invalid JARVIS_IMPL='%s', defaulting to 'savant'", JARVIS_IMPL)
    JARVIS_IMPL = "savant"

def get_jarvis_impl() -> str:
    """Get current Jarvis implementation name."""
    return JARVIS_IMPL

def get_jarvis_engine():
    """Get Jarvis engine based on JARVIS_IMPL selector."""
    if JARVIS_IMPL == "hybrid":
        return get_jarvis_hybrid()  # returns calculate_hybrid_jarvis_score function
    else:
        return get_jarvis_savant()  # returns JarvisSavantEngine singleton
```

**Selection Logic:**
1. Read `JARVIS_IMPL` env var at module load
2. Validate value is "savant" or "hybrid" (invalid defaults to "savant")
3. `JARVIS_IMPL=savant` → Use `JarvisSavantEngine` (default behavior)
4. `JARVIS_IMPL=hybrid` → Use `calculate_hybrid_jarvis_score` from `core/jarvis_ophis_hybrid.py`

**Deterministic:** No try/except fallback as primary selection. Selector is observable via `get_jarvis_impl()`.

---

## HYBRID IMPLEMENTATION STATUS

**Status:** AVAILABLE (selectable via `JARVIS_IMPL=hybrid`)

**Imports of `jarvis_ophis_hybrid` in codebase:**

| File | Usage | Scoring Path? |
|------|-------|---------------|
| `live_data_router.py` | `get_jarvis_hybrid()` lazy loader | YES (when `JARVIS_IMPL=hybrid`) |
| `tests/test_engine4_jarvis_guards.py` | Guard tests | NO (test file) |
| `tests/test_reconciliation.py` | Reconciliation tests | NO (test file) |
| `scripts/engine4_jarvis_audit.py` | Audit script | NO (script) |

**Hybrid is active when:** `JARVIS_IMPL=hybrid` environment variable is set

---

## INPUT SCHEMA

**Function:** `calculate_jarvis_engine_score()` (lines 2870-3091)

```python
def calculate_jarvis_engine_score(
    jarvis_engine,        # JarvisSavantEngine singleton from get_jarvis_savant()
    game_str: str,        # Source: Computed (concatenated matchup/player)
    player_name: str = "",# Source: Odds API (props) / BDL
    home_team: str = "",  # Source: Odds API / Playbook
    away_team: str = "",  # Source: Odds API / Playbook
    spread: float = 0,    # Source: Odds API (bookmakers)
    total: float = 0,     # Source: Odds API (bookmakers)
    prop_line: float = 0, # Source: Odds API (props market)
    date_et: str = ""     # Source: Computed via get_today_date_et()
) -> Dict[str, Any]
```

**NOT passed to this function:** `odds`, `public_pct`, `game_context` (these exist elsewhere but are not Jarvis inputs)

---

## OUTPUT SCHEMA

```python
{
    "jarvis_rs": float | None,           # 0-10 score (None if inputs missing)
    "jarvis_baseline": float,            # Always 4.5 when inputs present
    "jarvis_trigger_contribs": Dict,     # {trigger_name: contribution}
    "jarvis_active": bool,               # True if inputs present (Jarvis ran)
    "jarvis_hits_count": int,            # Count of triggers that fired
    "jarvis_triggers_hit": List[Dict],   # Trigger details with contributions
    "jarvis_reasons": List[str],         # Human-readable reasons
    "jarvis_fail_reasons": List[str],    # Why score is low
    "jarvis_no_trigger_reason": str|None,# "NO_TRIGGER_BASELINE" or None
    "jarvis_inputs_used": Dict,          # All inputs for transparency
    "immortal_detected": bool            # True if 2178 detected
}
```

---

## SCORING MODEL (v16.0 ADDITIVE)

**Baseline:** 4.5 (when inputs present but no triggers fire)

**Formula:**
```
jarvis_rs = 4.5 + total_trigger_contrib + gematria_contrib + goldilocks_contrib
jarvis_rs = clamp(0, 10, jarvis_rs)
```

**Trigger Contributions (ADD to baseline):**

| Trigger | Number | Contribution | Total Score |
|---------|--------|--------------|-------------|
| IMMORTAL | 2178 | +3.5 | 8.0 |
| ORDER | 201 | +2.5 | 7.0 |
| MASTER | 33 | +2.0 | 6.5 |
| WILL | 93 | +2.0 | 6.5 |
| SOCIETY | 322 | +2.0 | 6.5 |
| BEAST | 666 | +1.5 | 6.0 |
| JESUS | 888 | +1.5 | 6.0 |
| TESLA KEY | 369 | +1.5 | 6.0 |
| POWER_NUMBER | 11,22,44,55,66,77,88,99 | +0.8 | 5.3 |
| TESLA_REDUCTION | 3,6,9 digit sum | +0.5 | 5.0 |
| REDUCTION | Master number match | +0.5 | 5.0 |

**Additional Contributions:**
- Gematria STRONG (signal_strength > 0.7): +1.5
- Gematria MODERATE (signal_strength > 0.4): +0.8
- Goldilocks Zone (spread 4.0-9.0): +0.5

**Stacking Decay:** 0.7^n decay for n-th trigger (each additional trigger contributes 70% of previous)

---

## HYBRID BLEND MODEL (v2.0)

**Formula:** Jarvis Primary + Bounded Ophis Delta (NOT weighted average)

```python
# Constants
JARVIS_BASELINE = 4.5
OPHIS_NEUTRAL = 5.5       # Center point where delta = 0
OPHIS_DELTA_CAP = 0.75    # Max adjustment ±0.75
JARVIS_MSRF_COMPONENT_CAP = 2.0

# 1. Calculate Jarvis score (unchanged)
jarvis_score = JARVIS_BASELINE + trigger_contribs + gematria_contrib + goldilocks_contrib
jarvis_score = clamp(0, 10, jarvis_score)

# 2. Calculate Ophis raw score
msrf_component = min(JARVIS_MSRF_COMPONENT_CAP, msrf_score)
ophis_raw = JARVIS_BASELINE + msrf_component  # Range: [4.5, 6.5]

# 3. Convert Ophis to bounded delta
ophis_delta = ((ophis_raw - OPHIS_NEUTRAL) / (OPHIS_MAX - OPHIS_NEUTRAL)) * OPHIS_DELTA_CAP
ophis_delta = clamp(-OPHIS_DELTA_CAP, +OPHIS_DELTA_CAP, ophis_delta)

# 4. Hybrid = Jarvis + Ophis delta
jarvis_rs = jarvis_score + ophis_delta
jarvis_rs = clamp(0.0, 10.0, jarvis_rs)
```

**Delta Mapping:**

| Ophis Raw | Delta | Effect |
|-----------|-------|--------|
| 4.5 (min) | -0.75 | Max penalty |
| 5.0 | -0.375 | Slight penalty |
| 5.5 (neutral) | 0.0 | No change |
| 6.0 | +0.375 | Slight boost |
| 6.5 (max) | +0.75 | Max boost |

**Hybrid Additional Output Fields:**

```python
{
    "blend_type": "JARVIS_PRIMARY_OPHIS_DELTA",
    "jarvis_score_before_ophis": float,  # Pure Jarvis [0, 10]
    "ophis_raw": float,                   # Raw Ophis [4.5, 6.5]
    "ophis_delta": float,                 # Bounded [-0.75, +0.75]
    "ophis_delta_cap": 0.75,
    "msrf_component": float,              # MSRF contribution (capped at 2.0)
    "msrf_status": "IN_JARVIS",
    "version": "JARVIS_OPHIS_HYBRID_v2.0",
}
```

---

## INVARIANTS

1. **Score Range:** `jarvis_rs` always in [0, 10] (clamped)
2. **Baseline Present:** `jarvis_baseline = 4.5` when inputs present
3. **Ophis Delta Bounded:** [-0.75, +0.75] (hybrid only)
4. **MSRF Cap:** 2.0 (hybrid only)
5. **Version Reflects Implementation:** Savant = "JARVIS_SAVANT_v11.08", Hybrid = "JARVIS_OPHIS_HYBRID_v2.0"
6. **jarvis_active:** True when inputs present
7. **Output Schema Stable:** All 11 required fields always returned
8. **Selector Deterministic:** Invalid JARVIS_IMPL defaults to "savant"
9. **Ophis Neutral:** When ophis_raw = 5.5, delta = 0 (hybrid only)
10. **Hybrid is Additive:** `jarvis_rs = jarvis_before + ophis_delta` (NOT weighted average)

---

## YAML MACHINE-CHECKABLE SECTION

```yaml
---
# JARVIS ENGINE 4 - TRUTH TABLE
# Generated: Step 1 Wiring Investigation
# NO BEHAVIOR CHANGES - Documentation Only

wired_implementations:
  primary:
    name: JarvisSavantEngine
    version: "JARVIS_SAVANT_v11.08"
    file: jarvis_savant_engine.py
    class_lines: 282-1055
    status: ACTIVE
    selected_when: "JARVIS_IMPL=savant (default)"
  alternative:
    name: JarvisOphisHybrid
    version: "JARVIS_OPHIS_HYBRID_v2.0"
    file: core/jarvis_ophis_hybrid.py
    status: AVAILABLE
    selected_when: "JARVIS_IMPL=hybrid"
    blend_model: "JARVIS_PRIMARY_OPHIS_DELTA"
    ophis_delta_cap: 0.75

selector:
  env_var: JARVIS_IMPL
  default: "savant"
  valid_values: ["savant", "hybrid"]
  invalid_handling: "default to savant with warning"
  file: live_data_router.py
  functions:
    - get_jarvis_impl
    - get_jarvis_engine
    - get_jarvis_savant
    - get_jarvis_hybrid

entrypoint:
  file: live_data_router.py
  function: calculate_jarvis_engine_score
  lines: 2870-3091
  called_from:
    file: live_data_router.py
    function: calculate_pick_score
    lines: 3995-4012

required_inputs:
  - name: jarvis_engine
    type: JarvisSavantEngine
    source: get_jarvis_savant() singleton
  - name: game_str
    type: str
    source: computed_matchup
  - name: player_name
    type: str
    source: odds_api_props
  - name: home_team
    type: str
    source: odds_api
  - name: away_team
    type: str
    source: odds_api
  - name: spread
    type: float
    source: odds_api_bookmakers
  - name: total
    type: float
    source: odds_api_bookmakers
  - name: prop_line
    type: float
    source: odds_api_props
  - name: date_et
    type: str
    source: computed_get_today_date_et

not_passed_to_jarvis:
  - odds
  - public_pct
  - game_context

required_output_fields:
  - jarvis_rs
  - jarvis_baseline
  - jarvis_trigger_contribs
  - jarvis_active
  - jarvis_hits_count
  - jarvis_triggers_hit
  - jarvis_reasons
  - jarvis_fail_reasons
  - jarvis_no_trigger_reason
  - jarvis_inputs_used
  - immortal_detected
  - version

hybrid_additional_fields:
  - blend_type
  - jarvis_score_before_ophis
  - ophis_raw
  - ophis_delta
  - ophis_delta_cap
  - msrf_component
  - msrf_status

invariants:
  1_score_range: "[0, 10]"
  2_jarvis_baseline: 4.5
  3_ophis_delta_bounded: "[-0.75, +0.75]"
  4_msrf_cap: 2.0
  5_version_reflects_impl: true
  6_jarvis_active_when_inputs: true
  7_output_schema_stable: true
  8_selector_deterministic: "invalid -> savant"
  9_ophis_neutral_yields_zero: "ophis_raw=5.5 -> delta=0"
  10_hybrid_is_additive: "NOT weighted average"

hard_guard_tests: tests/test_engine4_jarvis_guards.py

trigger_contributions:
  IMMORTAL_2178: 3.5
  ORDER_201: 2.5
  MASTER_33: 2.0
  WILL_93: 2.0
  SOCIETY_322: 2.0
  BEAST_666: 1.5
  JESUS_888: 1.5
  TESLA_KEY_369: 1.5
  POWER_NUMBER: 0.8
  TESLA_REDUCTION: 0.5
  REDUCTION_MATCH: 0.5
  GEMATRIA_STRONG: 1.5
  GEMATRIA_MODERATE: 0.8
  GOLDILOCKS_ZONE: 0.5
---
```
