# ENGINE 4 (JARVIS) - TRUTH TABLE

**Generated:** Step 1 Wiring Investigation (Feb 10, 2026)
**Constraint:** NO BEHAVIOR CHANGES - Documentation Only

---

## WIRING SUMMARY

- **Default Jarvis implementation:** `JarvisSavantEngine` v11.08 from `jarvis_savant_engine.py`
- **Fallback conditions:** If import fails, falls back to string matching against `JARVIS_TRIGGERS` (NOT hybrid)
- **Hybrid status:** `core/jarvis_ophis_hybrid.py` is DEAD_CODE (only imported in tests/scripts, never in scoring path)

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
**Function:** `get_jarvis_savant()`
**Lines:** 13161-13171

```python
def get_jarvis_savant():
    """Lazy load JarvisSavantEngine."""
    global _jarvis_savant_engine
    if _jarvis_savant_engine is None:
        try:
            from jarvis_savant_engine import get_jarvis_engine
            _jarvis_savant_engine = get_jarvis_engine()
            logger.info("JarvisSavantEngine initialized")
        except ImportError as e:
            logger.warning("JarvisSavantEngine not available: %s", e)
    return _jarvis_savant_engine
```

**Selection Logic:**
1. Try to import `JarvisSavantEngine` from `jarvis_savant_engine.py`
2. If import succeeds: Use `JarvisSavantEngine` (always succeeds - file exists)
3. If import fails: Return `None`, scoring uses string fallback (lines 3036-3057)

---

## DEAD_CODE PROOF: `core/jarvis_ophis_hybrid.py`

**Grep for `jarvis_ophis_hybrid` in entire codebase:**

| File | Line | Usage | Scoring Path? |
|------|------|-------|---------------|
| `tests/test_reconciliation.py` | 28 | `from core.jarvis_ophis_hybrid import ...` | NO (test file) |
| `scripts/engine4_jarvis_audit.py` | 47 | `from core.jarvis_ophis_hybrid import ...` | NO (audit script) |
| `live_data_router.py` | - | **No matches** | N/A |

**Conclusion:** `jarvis_ophis_hybrid.py` is never imported in `live_data_router.py` or any transitive import in the scoring path. Status: **DEAD_CODE**

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

## INVARIANTS

1. **Score Range:** `jarvis_rs` always in [0, 10] (clamped at line 3063)
2. **No API Calls:** Jarvis engines receive pre-fetched inputs only
3. **Baseline Present:** 4.5 baseline when inputs present (never 0)
4. **Output Schema Stable:** All 11 fields always returned
5. **Stacking Decay:** 0.7^n decay for n-th trigger
6. **GOLD_STAR Gate:** `jarvis_rs >= 6.5` required for GOLD_STAR tier

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
    version: "11.08"
    file: jarvis_savant_engine.py
    class_lines: 282-1055
    status: ACTIVE
  alternative:
    name: JarvisOphisHybrid
    version: "1.1-TITAN"
    file: core/jarvis_ophis_hybrid.py
    status: DEAD_CODE
    proof:
      - "live_data_router.py: No matches for jarvis_ophis_hybrid"
      - "Only imported in tests/test_reconciliation.py:28 (test file)"
      - "Only imported in scripts/engine4_jarvis_audit.py:47 (audit script)"

selector_location:
  file: live_data_router.py
  function: get_jarvis_savant
  lines: 13161-13171
  fallback: string_matching_if_import_fails

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

invariants:
  - score_range: "[0, 10]"
  - no_api_calls_inside_engine: true
  - baseline_when_inputs_present: 4.5
  - output_schema_stable: true
  - stacking_decay: 0.7
  - gold_star_gate: "jarvis_rs >= 6.5"

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
