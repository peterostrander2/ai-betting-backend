# 17 Pillars Scoring System (v18.0 Option A)

<!-- SCORING_CONTRACT_JSON
{
  "confluence_levels": {
    "DIVERGENT": 0.0,
    "HARMONIC_CONVERGENCE": 4.5,
    "IMMORTAL": 10.0,
    "JARVIS_PERFECT": 7.0,
    "MODERATE": 1.0,
    "PERFECT": 5.0,
    "STRONG": 3.0
  },
  "engine_weights": {
    "ai": 0.25,
    "research": 0.35,
    "esoteric": 0.20,
    "jarvis": 0.20
  },
  "gold_star_gates": {
    "ai_score": 6.8,
    "research_score": 5.5,
    "jarvis_score": 6.5,
    "esoteric_score": 4.0
  },
  "gold_star_threshold": 7.5,
  "min_final_score": 6.5,
  "boost_caps": {
    "confluence_boost_cap": 10.0,
    "msrf_boost_cap": 1.0,
    "serp_boost_cap_total": 4.3,
    "jason_sim_boost_cap": 1.5
  },
  "titanium_rule": {
    "min_engines_ge_threshold": 3,
    "threshold": 8.0
  },
  "weather_status_enum": [
    "APPLIED",
    "NOT_RELEVANT",
    "UNAVAILABLE",
    "ERROR"
  ]
}
SCORING_CONTRACT_JSON -->


## Formula (v18.0 Option A - 4 Base Engines + Context Modifier)
BASE_4 = (AI × 0.25) + (Research × 0.35) + (Esoteric × 0.20) + (Jarvis × 0.20)
FINAL = BASE_4 + context_modifier + confluence_boost + msrf_boost + jason_sim_boost + serp_boost

Boosts are additive (NOT engines). Each boost must be present in payloads with status + reasons.

Minimum output: 6.5

## ENGINE 1: AI Score (25%)
File: advanced_ml_backend.py
8 AI models, range 0-10

## ENGINE 2: Research Score (35%)
- Sharp Money (0-3 pts)
- Line Variance (0-3 pts)
- Public Fade (0-2 pts)
- Base (2-3 pts)

## ENGINE 3: Esoteric Score (20%)
File: live_data_router.py
Expected: 2.0-5.5 range

Components:
- Numerology (35%)
- Astro (25%)
- Fibonacci (15%)
- Vortex (15%)
- Daily Edge (10%)

For props: uses prop_line for magnitude calculation
For games: uses spread for magnitude calculation

## ENGINE 4: Jarvis Score (20%) - v16.0 ADDITIVE MODEL
File: live_data_router.py `calculate_jarvis_engine_score()`

### v16.0 Additive Trigger Scoring

Jarvis now uses **additive scoring** to enable legitimate GOLD_STAR qualification:

**Baseline:** 4.5 when inputs are present

**Trigger Contributions (ADD to baseline 4.5):**

| Trigger | Contribution | Total jarvis_rs |
|---------|-------------|-----------------|
| IMMORTAL (2178) | +3.5 | 8.0 |
| ORDER (201) | +2.5 | 7.0 |
| MASTER (33) | +2.0 | 6.5 |
| WILL (93) | +2.0 | 6.5 |
| SOCIETY (322) | +2.0 | 6.5 |
| BEAST (666) | +1.5 | 6.0 |
| JESUS (888) | +1.5 | 6.0 |
| TESLA KEY (369) | +1.5 | 6.0 |
| POWER_NUMBER | +0.8 | 5.3 |
| TESLA_REDUCTION | +0.5 | 5.0 |
| REDUCTION match | +0.5 | 5.0 |

**Additional Contributions:**
- Gematria strong (>0.7): +1.5
- Gematria moderate (>0.4): +0.8
- Mid-spread goldilocks: +0.5

**Stacking:** Each additional trigger adds 70% of previous (decay factor)

**Result Ranges:**
- No triggers: 4.5 (baseline)
- 1 minor trigger: ~5.0-6.2
- 1 strong trigger OR 2+ triggers: ≥6.5 (GOLD_STAR eligible)
- Stacked triggers: 8.5-10 (rare)

### Jarvis Audit Fields

Every pick includes these fields:

```python
{
    "jarvis_rs": float,                    # Final score (0-10)
    "jarvis_baseline": 4.5,                # Always 4.5 when inputs present
    "jarvis_trigger_contribs": {           # Each trigger's contribution
        "THE MASTER": 2.0,
        "gematria_strong": 1.5,
    },
    "jarvis_triggers_hit": [...],          # Trigger details
    "jarvis_active": bool,                 # True if inputs present
    "jarvis_hits_count": int,              # Number of triggers
    "jarvis_reasons": [...],               # Why score is what it is
    "jarvis_no_trigger_reason": str|None,  # "NO_TRIGGER_BASELINE" if no triggers
}
```

## Context Modifier (bounded, NOT a weighted engine)
File: live_data_router.py
Context derives from Pillars 13-15 (Defensive Rank, Pace, Vacuum) and is mapped to a bounded modifier.

### Components
| Component | Weight | Source | Formula |
|-----------|--------|--------|---------|
| Defensive Rank | 50% | DefensiveRankService | `(total_teams - rank) / (total_teams - 1) * 10` |
| Pace | 30% | PaceVectorService | `(pace - 90) / 20 * 10` (clamped 0-10) |
| Vacuum | 20% | UsageVacuumService | `5 + (vacuum / 5)` (clamped 0-10) |

### Context Score Formula
```python
context_score = (def_component * 0.5) + (pace_component * 0.3) + (vacuum_component * 0.2)
```
### Context Modifier
```python
context_modifier = ((context_score - 5.0) / 5.0) * CONTEXT_MODIFIER_CAP
context_modifier = clamp(context_modifier, -CONTEXT_MODIFIER_CAP, +CONTEXT_MODIFIER_CAP)
```

### LSTM Integration
- LSTM model receives real context data (`def_rank`, `pace`, `vacuum`)
- Previously hardcoded to `def_rank=16, pace=100, vacuum=0`
- Now fetches from context layer services

### Pillar 16: Officials (v17.0)
- Applied as adjustment to research_score
- Gets lead official, official_2, official_3 from candidate data
- OfficialsAnalyzer returns adjustment value

### Pillar 17: Park Factors (v17.0 - MLB Only)
- Applied as adjustment to esoteric_score
- ParkFactorService considers home venue effects
- Colorado (Coors Field) adds ~+0.3-0.5 for hitter props

---

## Tier Assignment

### TITANIUM_SMASH
- Rule: ≥3 of 4 engines ≥8.0 (STRICT)
- Overrides all other tiers
- File: `core/titanium.py`

### GOLD_STAR (Gem Tier - Strict + Rare)
- final_score ≥ 7.5 AND ALL gates must pass:
  - ai_score ≥ 6.8
  - research_score ≥ 5.5
  - esoteric_score ≥ 4.0
  - **jarvis_rs ≥ 6.5** (requires triggers to fire)
  - context gate removed (context is a modifier)
- If any gate fails → downgrade to EDGE_LEAN

### EDGE_LEAN
- final_score ≥ 6.5
- Default tier for playable picks

### Hidden Tiers (Not Returned)
- MONITOR: ≥ 5.5
- PASS: < 5.5

## Confluence Boost

| Level | Boost | Condition |
|-------|-------|-----------|
| IMMORTAL | +10 | 2178 + both ≥7.5 + alignment ≥80% |
| JARVIS_PERFECT | +7 | Trigger + both ≥7.5 + alignment ≥80% |
| PERFECT | +5 | both ≥7.5 + alignment ≥80% |
| **HARMONIC_CONVERGENCE** | +4.5 | **Research ≥8.0 AND Esoteric ≥8.0** (Math+Magic alignment) |
| STRONG | +3 | alignment ≥80% + active signal |
| MODERATE | +1 | alignment ≥60% |
| DIVERGENT | +0 | below 60% |

Alignment = 1 - |research - esoteric| / 10

## MSRF Boost (v17.2)
- Adds a separate boost (0.0 / 0.25 / 0.5 / 1.0)
- Must NOT be folded into confluence_boost

## SERP Boost (v17.4)
- Adds a separate boost (total capped by SERP_TOTAL_CAP in guardrails)
- Must NOT be folded into confluence_boost

## Jason Sim Boost (v11.08)
- Adds a separate boost/downgrade based on simulation
- Must remain separate and observable

### Harmonic Convergence (v17.0 "Golden Boost")
When both Research (Math/Market signals) AND Esoteric (Magic/Cosmic signals) score ≥8.0:
- Represents exceptional alignment between analytical and intuitive signals
- Adds +1.5 to final score (equivalent to +15 on 100-point scale)
- Overrides regular confluence level calculation

## Output Filter

NEVER return picks with final_score < 6.5 to frontend.
