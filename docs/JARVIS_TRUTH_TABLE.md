# ENGINE 4 (JARVIS) - TRUTH TABLE

**Generated:** Step 1 Wiring Investigation (Feb 10, 2026)
**Updated:** v2.2 Weighted Blend Under Bounded Delta Cap (Feb 11, 2026)
**Constraint:** Production selector now available via JARVIS_IMPL env var

---

## v2.1 FIX (Feb 11, 2026)

**Critical A/B Bug Fixed:** Hybrid's `jarvis_score_before_ophis` now comes from the ACTUAL production savant scorer.

**Problem:** Hybrid v2.0 used its own simplified `calculate_jarvis_gematria_score()` which didn't match production savant scoring. This caused A/B comparison failures (e.g., Austin Peay vs Queens: Savant=7.35, Hybrid=5.25).

**Solution:** Created `core/jarvis_score_api.py` as a SHARED dependency-light module:
1. **Single source of truth:** Contains `calculate_jarvis_engine_score()` and `get_savant_engine()`
2. **No circular imports:** Only imports from `jarvis_savant_engine.py` (no FastAPI dependencies)
3. **Both use same code:** `live_data_router` and `hybrid` both import from this shared module
4. **No drift possible:** If savant logic changes, both implementations get the update automatically

**Architecture:**
```
jarvis_savant_engine.py (engine class)
           ↓
core/jarvis_score_api.py (shared scoring function) ← SINGLE SOURCE OF TRUTH
           ↓               ↓
live_data_router.py    core/jarvis_ophis_hybrid.py
(JARVIS_IMPL=savant)   (JARVIS_IMPL=hybrid)
```

**Why This Matters:** Previous approach of lazy-importing from `live_data_router` created circular import risk and required FastAPI to be installed for tests.

**Invariant Added:** `hybrid.jarvis_score_before_ophis == savant.jarvis_rs` (for same inputs)

**Test:** `test_hybrid_jarvis_before_matches_real_savant` imports from `core.jarvis_score_api` (same module hybrid uses). No skips, no FastAPI dependency.

**Fallback:** If `jarvis_savant_engine` can't be imported, returns `version: "JARVIS_FALLBACK_v1.0"` with simplified gematria.

**Version:** `JARVIS_OPHIS_HYBRID_v2.1` → Updated to `JARVIS_OPHIS_HYBRID_v2.2` (see v2.2 section below)

---

## v2.2 WEIGHTED BLEND (Feb 11, 2026)

**Enhancement:** Implements true 55/45 weighted blend under bounded delta cap.

**Problem:** v2.1 delta model wasn't a true 55/45 blend — Ophis was just a minor ±0.75 modifier.

**Solution:** v2.2 computes the 55/45 target blend, then bounds the adjustment toward target (max ±0.75).

**Formula:**
```python
# Constants
JARVIS_WEIGHT = 0.55
OPHIS_WEIGHT = 0.45
OPHIS_DELTA_CAP = 0.75
OPHIS_SCALE_FACTOR = 5.0

# 1. Normalize Ophis to 0-10 scale
ophis_score_norm = msrf_component * OPHIS_SCALE_FACTOR  # [0, 2.0] → [0, 10]

# 2. Compute 55/45 target blend
jarvis_target_blend = (0.55 * jarvis_before) + (0.45 * ophis_score_norm)

# 3. Delta from Jarvis anchor
ophis_delta_raw = jarvis_target_blend - jarvis_before

# 4. Bounded cap (safety invariant)
ophis_delta_applied = clamp(ophis_delta_raw, -0.75, +0.75)

# 5. Final score
jarvis_rs = clamp(jarvis_before + ophis_delta_applied, 0.0, 10.0)
```

**Key Semantics:**
- **Target:** True 55% Jarvis / 45% Ophis blend in `jarvis_target_blend`
- **Final:** Jarvis is the anchor; system applies bounded move toward target (max ±0.75)
- **Realized vs Target:** Full 45% Ophis influence only when |delta_raw| < 0.75
- **Saturation:** `ophis_delta_saturated = (abs(ophis_delta_raw) >= OPHIS_DELTA_CAP)` — uses `>=` not `>`

**v2.2 NEW Output Fields (added, no removals):**
```python
{
    "ophis_score_norm": float,           # Ophis on 0-10 scale (msrf * 5)
    "jarvis_target_blend": float,        # 55/45 target
    "ophis_delta_raw": float,            # Before clamping
    "ophis_delta_applied": float,        # After clamping (same as ophis_delta)
    "ophis_delta_saturated": bool,       # True when cap hit (>= not >)
    "jarvis_weight": 0.55,               # For transparency
    "ophis_weight": 0.45,                # For transparency
    "jarvis_blend_type": "JARVIS_WEIGHTED_BLEND_CAPPED_DELTA",  # For API output
    "blend_type": "JARVIS_WEIGHTED_BLEND_CAPPED_DELTA",         # Internal
}
```

**Backward Compatibility:** All v2.1 fields retained (`ophis_raw`, `ophis_component`, `ophis_delta`, etc.). No removals.

**MSRF Note:** `ophis_score_norm = msrf_component * 5.0` assumes MSRF is the entire Ophis signal. If additional Ophis components are added later, this normalization must be revisited.

**Version:** `JARVIS_OPHIS_HYBRID_v2.2`

**Guard Tests Added:** 5 new tests in `tests/test_engine4_jarvis_guards.py`:
1. `test_weighted_blend_math_reconciles` — target == 0.55*jarvis + 0.45*ophis
2. `test_delta_raw_is_target_minus_jarvis` — delta_raw == target - jarvis_before
3. `test_delta_applied_is_clamped` — delta_applied in [-0.75, +0.75]
4. `test_final_equals_before_plus_applied_delta` — jarvis_rs == before + applied
5. `test_delta_saturation_flag_matches_math` — saturation flag uses `>=` predicate

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
| **SHARED SCORING API** | `core/jarvis_score_api.py` | 1-351 | **SINGLE SOURCE OF TRUTH** for Jarvis scoring |
| Shared: get_savant_engine() | `core/jarvis_score_api.py` | 68-83 | Engine singleton (imports from jarvis_savant_engine) |
| Shared: calculate_jarvis_engine_score() | `core/jarvis_score_api.py` | 90-295 | v16.0 ADDITIVE scoring function |
| Shared: score_jarvis() | `core/jarvis_score_api.py` | 302-334 | Convenience wrapper |
| Savant Engine Class | `jarvis_savant_engine.py` | 282-1055 | `JarvisSavantEngine` class (v11.08) |
| Trigger Detection | `jarvis_savant_engine.py` | 350-425 | `check_jarvis_trigger()` |
| Gematria Calculation | `jarvis_savant_engine.py` | 437-456 | `calculate_gematria()` |
| Gematria Signal | `jarvis_savant_engine.py` | 458-503 | `calculate_gematria_signal()` |
| Mid-Spread Signal | `jarvis_savant_engine.py` | 856-888 | `calculate_mid_spread_signal()` |
| Hybrid Implementation | `core/jarvis_ophis_hybrid.py` | 1-550 | v2.1 with shared module imports |
| Hybrid: _get_savant_jarvis_score() | `core/jarvis_ophis_hybrid.py` | 226-280 | Calls shared module |
| Call Site (live router) | `live_data_router.py` | 3995-4012 | Where Jarvis is called from `calculate_pick_score()` |
| Trigger Contributions | `core/jarvis_score_api.py` | 27-36 | `TRIGGER_CONTRIBUTIONS` dict |
| Stacking Decay | `core/jarvis_score_api.py` | 44 | `STACKING_DECAY = 0.7` |

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

## HYBRID BLEND MODEL (v2.2)

**Formula:** Weighted Blend (55/45) Under Bounded Delta Cap

```python
# Constants
JARVIS_WEIGHT = 0.55
OPHIS_WEIGHT = 0.45
OPHIS_DELTA_CAP = 0.75
OPHIS_SCALE_FACTOR = 5.0
JARVIS_MSRF_COMPONENT_CAP = 2.0

# 1. Calculate Jarvis score (unchanged from v2.1)
jarvis_score = JARVIS_BASELINE + trigger_contribs + gematria_contrib + goldilocks_contrib
jarvis_score = clamp(0, 10, jarvis_score)

# 2. Normalize Ophis to 0-10 scale
msrf_component = min(JARVIS_MSRF_COMPONENT_CAP, msrf_score)
ophis_score_norm = msrf_component * OPHIS_SCALE_FACTOR  # [0, 2.0] → [0, 10]

# 3. Compute 55/45 target blend
jarvis_target_blend = (JARVIS_WEIGHT * jarvis_score) + (OPHIS_WEIGHT * ophis_score_norm)

# 4. Delta from Jarvis anchor
ophis_delta_raw = jarvis_target_blend - jarvis_score

# 5. Apply bounded cap (safety invariant)
ophis_delta_applied = clamp(-OPHIS_DELTA_CAP, +OPHIS_DELTA_CAP, ophis_delta_raw)

# 6. Saturation flag (>= not >)
ophis_delta_saturated = abs(ophis_delta_raw) >= OPHIS_DELTA_CAP

# 7. Final = Jarvis + bounded delta
jarvis_rs = jarvis_score + ophis_delta_applied
jarvis_rs = clamp(0.0, 10.0, jarvis_rs)
```

**Delta Mapping Examples (v2.2):**

| jarvis_before | msrf | ophis_norm | target | delta_raw | delta_applied | final |
|---------------|------|------------|--------|-----------|---------------|-------|
| 7.0 | 1.0 | 5.0 | 6.1 | -0.9 | -0.75 | 6.25 |
| 7.0 | 2.0 | 10.0 | 8.35 | +1.35 | +0.75 | 7.75 |
| 7.0 | 0.0 | 0.0 | 3.85 | -3.15 | -0.75 | 6.25 |
| 5.0 | 1.1 | 5.5 | 5.225 | +0.225 | +0.225 | 5.225 |
| 4.5 | 1.0 | 5.0 | 4.725 | +0.225 | +0.225 | 4.725 |

**Hybrid Output Fields (v2.2 — all fields, no removals):**

```python
{
    # Version and blend type
    "version": "JARVIS_OPHIS_HYBRID_v2.2",
    "blend_type": "JARVIS_WEIGHTED_BLEND_CAPPED_DELTA",
    "jarvis_blend_type": "JARVIS_WEIGHTED_BLEND_CAPPED_DELTA",

    # Jarvis anchor
    "jarvis_score_before_ophis": float,  # Pure Jarvis [0, 10]
    "jarvis_component": float,            # Alias

    # v2.0 legacy fields (KEPT for backward compat)
    "ophis_raw": float,                   # = 4.5 + msrf_component
    "ophis_delta": float,                 # = ophis_delta_applied
    "ophis_delta_cap": 0.75,
    "ophis_component": float,             # Alias for ophis_raw

    # v2.2 NEW transparency fields
    "ophis_score_norm": float,            # Ophis on 0-10 scale (msrf * 5)
    "jarvis_target_blend": float,         # 55/45 target
    "ophis_delta_raw": float,             # Before clamping
    "ophis_delta_applied": float,         # After clamping
    "ophis_delta_saturated": bool,        # True when |delta_raw| >= 0.75
    "jarvis_weight": 0.55,
    "ophis_weight": 0.45,

    # MSRF components
    "msrf_component": float,              # MSRF contribution (capped at 2.0)
    "msrf_status": "IN_JARVIS",
}
```

---

## INVARIANTS (v2.2)

| # | Invariant | Enforced By |
|---|-----------|-------------|
| 1 | `jarvis_rs` in [0, 10] | Clamp at output |
| 2 | `jarvis_baseline` = 4.5 when inputs present | Unchanged |
| 3 | `ophis_delta_applied` bounded ±0.75 | `OPHIS_DELTA_CAP` clamp |
| 4 | MSRF cap = 2.0 | `JARVIS_MSRF_COMPONENT_CAP` |
| 5 | `version` = "JARVIS_OPHIS_HYBRID_v2.2" | Constant |
| 6 | `jarvis_active` = True when inputs present | Unchanged |
| 7 | All required output fields present | Schema validation |
| 8 | `jarvis_before` == savant.jarvis_rs | Shared module (v2.1 fix) |
| 9 | `ophis_score_norm` in [0, 10] | MSRF cap * 5 |
| 10 | `jarvis_target_blend` = 0.55*jarvis + 0.45*ophis | Formula check |
| 11 | `ophis_delta_raw` = target - jarvis_before | Formula check |
| 12 | `jarvis_rs` = jarvis_before + delta_applied | Formula check |
| 13 | `ophis_delta_saturated` = |delta_raw| >= 0.75 | Predicate uses >= not > |

---

## YAML MACHINE-CHECKABLE SECTION

```yaml
---
# JARVIS ENGINE 4 - TRUTH TABLE
# Generated: Step 1 Wiring Investigation
# Updated: v2.2 Weighted Blend (Feb 11, 2026)

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
    version: "JARVIS_OPHIS_HYBRID_v2.2"
    file: core/jarvis_ophis_hybrid.py
    status: AVAILABLE
    selected_when: "JARVIS_IMPL=hybrid"
    blend_model: "JARVIS_WEIGHTED_BLEND_CAPPED_DELTA"
    ophis_delta_cap: 0.75
    jarvis_weight: 0.55
    ophis_weight: 0.45
    ophis_scale_factor: 5.0

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

hybrid_v2_1_fields_kept:  # UNCHANGED (backward compat)
  - ophis_raw                  # = 4.5 + msrf_component
  - ophis_component            # Alias for ophis_raw
  - ophis_delta                # = ophis_delta_applied
  - ophis_delta_cap            # 0.75
  - msrf_component
  - jarvis_msrf_component
  - jarvis_msrf_component_raw
  - blend_type                 # Internal use
  - jarvis_score_before_ophis
  - jarvis_component

hybrid_v2_2_new_fields:       # ADDED in v2.2
  - ophis_score_norm           # Ophis on 0-10 scale (msrf * 5)
  - jarvis_target_blend        # 55/45 target
  - ophis_delta_raw            # Before clamping
  - ophis_delta_applied        # After clamping
  - ophis_delta_saturated      # True when cap hit (|delta_raw| >= 0.75)
  - jarvis_weight              # 0.55
  - ophis_weight               # 0.45
  - jarvis_blend_type          # For API output

invariants:
  1_score_range: "[0, 10]"
  2_jarvis_baseline: 4.5
  3_ophis_delta_bounded: "[-0.75, +0.75]"
  4_msrf_cap: 2.0
  5_version: "JARVIS_OPHIS_HYBRID_v2.2"
  6_jarvis_active_when_inputs: true
  7_output_schema_stable: true
  8_jarvis_before_equals_savant: "shared module guarantee"
  9_ophis_score_norm_range: "[0, 10]"
  10_target_blend_formula: "0.55*jarvis + 0.45*ophis"
  11_delta_raw_formula: "target - jarvis_before"
  12_final_formula: "jarvis_before + delta_applied"
  13_saturation_predicate: "|delta_raw| >= 0.75 (uses >=)"

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
